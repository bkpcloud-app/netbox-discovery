#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import builtins
import datetime
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, "..", ".."))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from lib.netbox import NetBox
from modules.importers import importer as package_base
from modules.importers import importer_v2 as v2
from modules.importers import importer_v11 as v11

IMPORTER_VERSION = "6.1-product"
REPORTS = package_base.REPORTS
PRODUCT_DEVICE_DESCRIPTION = "Criado pelo netbox-discovery"


def clean(value):
    return "" if value is None else str(value).strip()


def norm(value):
    return " ".join(clean(value).split()).casefold()


def nested_id(value):
    if isinstance(value, dict):
        return value.get("id")
    if isinstance(value, int):
        return value
    return None


def _load(path):
    with open(path, "r") as handle:
        return json.load(handle)


def _created_report(before, pattern, stage):
    after = set(glob.glob(pattern))
    candidates = sorted(after - before, key=os.path.getmtime, reverse=True)
    if not candidates:
        candidates = sorted(after, key=os.path.getmtime, reverse=True)
    for path in candidates:
        try:
            data = _load(path)
        except Exception:
            continue
        if clean(data.get("stage")) == stage:
            return path, data
    return "", {}


def refresh_plan():
    planner = os.path.join(BASE, "modules", "inventory", "planner_v11.py")
    if not os.path.isfile(planner):
        raise RuntimeError("Planner V11 não encontrado: {0}".format(planner))
    before = set(glob.glob(os.path.join(REPORTS, "*-plan-*.json")))
    package_base.subprocess.check_call([sys.executable, planner])
    path, data = _created_report(before, os.path.join(REPORTS, "*-plan-*.json"), "PLAN")
    if not path:
        raise RuntimeError("PLAN V11 não gerou JSON")
    if clean(data.get("planner_version")) not in ("5.3-product", ""):
        raise RuntimeError("Planner inesperado no IMPORT: {0}".format(clean(data.get("planner_version"))))
    return path


def _all_global_ips(nb):
    cache = getattr(nb, "_device_type_ip_cache", None)
    if cache is None:
        cache = [
            row for row in package_base.query(nb, "ipam/ip-addresses/", limit=10000)
            if not row.get("vrf")
        ]
        setattr(nb, "_device_type_ip_cache", cache)
    return cache


def _device_id_for_ip(nb, ip):
    ipn = package_base.norm_ip(ip)
    exact = [
        row for row in _all_global_ips(nb)
        if package_base.norm_ip(row.get("address")) == ipn
    ]
    if len(exact) != 1:
        return None
    row = exact[0]
    assigned = row.get("assigned_object") or {}
    if isinstance(assigned, dict):
        device = assigned.get("device") or {}
        if isinstance(device, dict) and device.get("id"):
            return device.get("id")
    if clean(row.get("assigned_object_type")) != "dcim.interface":
        return None
    interface_id = package_base.assigned_object_id(row)
    if not interface_id:
        return None
    try:
        interface = nb.get("dcim/interfaces/{0}/".format(interface_id))
    except Exception:
        return None
    return nested_id((interface or {}).get("device"))


def _resolve_owned_device(nb, row, tenant, site):
    device_id = row.get("existing_device_id")
    if not isinstance(device_id, int):
        raise RuntimeError("device_type patch sem existing_device_id inteiro")
    current = nb.get("dcim/devices/{0}/".format(device_id))
    if not isinstance(current, dict) or current.get("id") != device_id:
        raise RuntimeError("Device ID {0} não encontrado".format(device_id))
    if nested_id(current.get("tenant")) != tenant.get("id"):
        raise RuntimeError("Device ID {0} mudou de Tenant".format(device_id))
    if nested_id(current.get("site")) != site.get("id"):
        raise RuntimeError("Device ID {0} mudou de Site".format(device_id))
    if clean(current.get("description")) != PRODUCT_DEVICE_DESCRIPTION:
        raise RuntimeError("Device ID {0} não pertence ao netbox-discovery".format(device_id))

    desired_serial = package_base.norm_serial(row.get("serial"))
    live_serial = package_base.norm_serial(current.get("serial"))
    if desired_serial:
        if live_serial != desired_serial:
            raise RuntimeError("serial do Device ID {0} divergiu do PLAN".format(device_id))
    else:
        ips = [package_base.norm_ip(value) for value in (row.get("ips") or [])]
        ips = [value for value in ips if value]
        if not ips:
            raise RuntimeError("Device sem serial exige IP estável para device_type patch")
        for ip in ips:
            owner = _device_id_for_ip(nb, ip)
            if owner != device_id:
                raise RuntimeError("IP {0} pertence ao Device {1}, esperado {2}".format(
                    ip, owner or "NONE", device_id))
    return current


def _target_rows(plan):
    rows = []
    for row in plan.get("records") or []:
        if clean(row.get("decision")) != "READY" or clean(row.get("action")) != "UPDATE_SAFE":
            continue
        manufacturer, model = v11._device_type_diff(row)
        if not manufacturer and not model:
            continue
        rows.append((row, manufacturer, model))
    return rows


def _validate_row(row, manufacturer, model, current):
    if not manufacturer or not model:
        raise RuntimeError("Device Type de destino incompleto")
    if clean(row.get("manufacturer")) != manufacturer or clean(row.get("model")) != model:
        raise RuntimeError("Device Type do PLAN diverge do safe diff")
    if clean(row.get("confidence")) != "HIGH":
        raise RuntimeError("device_type patch exige confiança HIGH")
    if clean(row.get("identity_policy")) != "UPGRADE_PRODUCT_GENERIC_TYPE":
        raise RuntimeError("device_type patch exige política de upgrade genérico")
    live_manufacturer, live_model = v11._current_device_type(current)
    if norm(live_manufacturer) == norm(manufacturer) and norm(live_model) == norm(model):
        return "ALREADY_EXACT"
    if not v11.v9._generic_model(live_model):
        raise RuntimeError("Device Type atual deixou de ser genérico: {0}/{1}".format(
            live_manufacturer, live_model))
    if v11.v9._generic_model(model):
        raise RuntimeError("Device Type de destino continua genérico: {0}".format(model))
    return "PATCH_REQUIRED"


def _write_verify_report(plan, source_plan, events, errors, updated, verified):
    site = clean(plan.get("site")) or "SITE"
    stamp = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(REPORTS, "{0}-import-device-type-verify-{1}.json".format(site, stamp))
    with open(path, "w") as handle:
        json.dump({
            "stage": "IMPORT_DEVICE_TYPE_VERIFY",
            "importer_version": IMPORTER_VERSION,
            "source_plan": source_plan,
            "status": "FAIL" if errors else "PASS",
            "updated": updated,
            "verified": verified,
            "records": events,
            "errors": errors,
            "netbox_write": bool(updated),
        }, handle, indent=2, sort_keys=True)
    return path


def apply_and_verify_device_types(source_plan):
    plan = _load(source_plan)
    rows = _target_rows(plan)
    events = []
    errors = []
    updated = 0
    verified = 0

    nb = NetBox()
    tenant = package_base.choose_exact(
        package_base.query(nb, "tenancy/tenants/", name=clean(plan.get("client"))),
        clean(plan.get("client")), "Tenant")
    site = package_base.choose_exact(
        package_base.query(nb, "dcim/sites/", name=clean(plan.get("site"))),
        clean(plan.get("site")), "Site")
    if not tenant or not site:
        raise RuntimeError("Tenant/Site do PLAN não encontrado")

    dry_events = []
    dry_catalog = package_base.Catalog(nb, False, dry_events)
    prepared = []
    for row, manufacturer, model in rows:
        current = _resolve_owned_device(nb, row, tenant, site)
        mode = _validate_row(row, manufacturer, model, current)
        dry_catalog.ensure_device_type(manufacturer, model)
        prepared.append((row, manufacturer, model, mode))

    catalog = package_base.Catalog(nb, True, events)
    try:
        for row, manufacturer, model, mode in prepared:
            current = _resolve_owned_device(nb, row, tenant, site)
            mode = _validate_row(row, manufacturer, model, current)
            target = catalog.ensure_device_type(manufacturer, model)
            if not target or not target.get("id"):
                raise RuntimeError("Device Type de destino sem ID: {0}/{1}".format(manufacturer, model))
            if mode == "PATCH_REQUIRED":
                nb.patch("dcim/devices/{0}/".format(current["id"]), {
                    "device_type": target["id"],
                })
                updated += 1
                action = "UPDATED"
            else:
                action = "PRESERVED"

            live = nb.get("dcim/devices/{0}/".format(current["id"]))
            live_manufacturer, live_model = v11._current_device_type(live)
            if norm(live_manufacturer) != norm(manufacturer) or norm(live_model) != norm(model):
                raise RuntimeError("readback divergente no Device ID {0}: live={1}/{2}, esperado={3}/{4}".format(
                    current["id"], live_manufacturer, live_model, manufacturer, model))
            verified += 1
            events.append({
                "phase": "DEVICE_TYPE_VERIFY",
                "object_type": "DEVICE",
                "action": action + "_AND_VERIFIED",
                "name": clean(live.get("name")),
                "object_id": live.get("id"),
                "detail": "{0} / {1}".format(manufacturer, model),
            })
    except Exception as exc:
        errors.append({"error": str(exc)})
        path = _write_verify_report(plan, source_plan, events, errors, updated, verified)
        print("DEVICE TYPE VERIFY: FAIL")
        print("JSON DEVICE TYPE: {0}".format(path))
        raise

    path = _write_verify_report(plan, source_plan, events, errors, updated, verified)
    print("===== DEVICE TYPE APPLY/READBACK =====")
    print("Device Types atualizados: {0}".format(updated))
    print("Device Types verificados: {0}".format(verified))
    print("Status: PASS")
    print("JSON DEVICE TYPE: {0}".format(path))
    return path


def _apply_requested(argv):
    return "--apply" in list(argv or [])


def main(argv=None):
    values = list(sys.argv[1:] if argv is None else argv)
    before_imports = set(glob.glob(os.path.join(REPORTS, "*-import-*.json")))
    old_version = v11.IMPORTER_VERSION
    old_top_safe = v2.base.safe_patch_for_existing
    old_package_safe = package_base.safe_patch_for_existing
    old_print = builtins.print
    refresh_modules = (
        v11, v11.v10, v11.v9, v11.v8, v11.v7,
        v11.v6, v11.v5, v11.v4, v11.v3, v11.v2,
        package_base, v2.base,
    )
    old_refresh = []
    for module in refresh_modules:
        if hasattr(module, "refresh_plan"):
            old_refresh.append((module, module.refresh_plan))

    def release_print(*args, **kwargs):
        if args and str(args[0]) == "===== IMPORT FINALIZE 1.11.2 =====":
            args = ("===== IMPORT FINALIZE 1.11.10 =====",) + tuple(args[1:])
        return old_print(*args, **kwargs)

    try:
        for module, unused in old_refresh:
            module.refresh_plan = refresh_plan
        v11.IMPORTER_VERSION = IMPORTER_VERSION
        # The legacy chain imports importer.py twice: as
        # modules.importers.importer and as top-level importer. Patch both
        # module objects so isolated device_type diffs reach the real main loop.
        package_base.safe_patch_for_existing = v11.safe_patch_for_existing
        v2.base.safe_patch_for_existing = v11.safe_patch_for_existing
        builtins.print = release_print
        rc = v11.main(values)
    finally:
        builtins.print = old_print
        v2.base.safe_patch_for_existing = old_top_safe
        package_base.safe_patch_for_existing = old_package_safe
        v11.IMPORTER_VERSION = old_version
        for module, function in reversed(old_refresh):
            module.refresh_plan = function

    if rc:
        return rc
    if not _apply_requested(values):
        return 0

    import_path, import_report = _created_report(
        before_imports, os.path.join(REPORTS, "*-import-*.json"), "IMPORT")
    if not import_path:
        raise RuntimeError("IMPORT APPLY não gerou relatório normal")
    source_plan = clean(import_report.get("source_plan"))
    if not source_plan or not os.path.isfile(source_plan):
        raise RuntimeError("IMPORT APPLY sem source_plan válido")
    apply_and_verify_device_types(source_plan)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
