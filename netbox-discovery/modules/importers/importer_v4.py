#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import argparse
import datetime
import fcntl
import glob
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from lib.netbox import NetBox
from modules.importers import importer as base
from modules.importers import importer_v3 as v3

IMPORTER_VERSION = "5.2-product"
BASE = base.BASE
REPORTS = base.REPORTS
LOCK_FILE = "/var/lock/netbox-discovery-import-finalize.lock"


def clean(value):
    return "" if value is None else str(value).strip()


def nested_id(value):
    if isinstance(value, dict):
        return value.get("id")
    if isinstance(value, int):
        return value
    return None


def _assigned_id(row):
    assigned = row.get("assigned_object") or {}
    if isinstance(assigned, dict) and assigned.get("id"):
        return assigned.get("id")
    return row.get("assigned_object_id")


def _latest(pattern):
    files = glob.glob(pattern)
    return max(files, key=os.path.getmtime) if files else ""


def refresh_plan():
    planner = os.path.join(BASE, "modules", "inventory", "planner_v4.py")
    if not os.path.isfile(planner):
        raise RuntimeError("Planner V4 não encontrado: {0}".format(planner))
    base.subprocess.check_call([sys.executable, planner])
    path = _latest(os.path.join(REPORTS, "*-plan-*.json"))
    if not path:
        raise RuntimeError("PLAN V4 não gerou JSON")
    return path


def _query(nb, endpoint, **params):
    return base.query(nb, endpoint, **params)


def _device_related_count(nb, endpoint, device_id):
    # Fail closed: an API/query failure must block deletion instead of being
    # interpreted as an empty relationship set.
    return len(_query(nb, endpoint, device_id=device_id, limit=10000))


def _all_mac_rows(nb):
    return _query(nb, "dcim/mac-addresses/", limit=10000)


def _verify_repair(nb, row, tenant_id, site_id):
    repair = row.get("repair") or {}
    required = ("device_id", "vm_id", "vm_interface_id", "ip_id")
    missing = [key for key in required if not repair.get(key)]
    if missing:
        raise RuntimeError("repair sem campos obrigatórios: {0}".format(",".join(missing)))

    device = nb.get("dcim/devices/{0}/".format(repair["device_id"]))
    vm = nb.get("virtualization/virtual-machines/{0}/".format(repair["vm_id"]))
    vm_interface = nb.get("virtualization/interfaces/{0}/".format(repair["vm_interface_id"]))
    ip_obj = nb.get("ipam/ip-addresses/{0}/".format(repair["ip_id"]))

    if clean(device.get("name")) != clean(repair.get("device_name")):
        raise RuntimeError("Device mudou de nome")
    if clean(device.get("description")) != clean(repair.get("expected_device_description")):
        raise RuntimeError("Device não possui ownership do netbox-discovery")
    if clean(device.get("serial")):
        raise RuntimeError("Device possui serial")
    if nested_id(device.get("tenant")) != tenant_id or nested_id(device.get("site")) != site_id:
        raise RuntimeError("Device mudou de Tenant/Site")
    for field in ("rack", "location", "cluster", "virtual_chassis", "device_bay"):
        if nested_id(device.get(field)):
            raise RuntimeError("Device ganhou vínculo manual: {0}".format(field))

    if clean(vm.get("name")) != clean(repair.get("vm_name")):
        raise RuntimeError("VM mudou de nome")
    if nested_id(vm.get("tenant")) not in (None, tenant_id):
        raise RuntimeError("VM mudou de Tenant")
    vm_site = nested_id(vm.get("site"))
    if vm_site not in (None, site_id):
        raise RuntimeError("VM mudou de Site")
    if nested_id(vm_interface.get("virtual_machine")) != repair["vm_id"]:
        raise RuntimeError("Interface alvo não pertence à VM")

    interfaces = _query(nb, "dcim/interfaces/", device_id=repair["device_id"], limit=1000)
    live_ids = sorted(item.get("id") for item in interfaces if item.get("id"))
    expected_ids = sorted(repair.get("device_interface_ids") or [])
    if live_ids != expected_ids:
        raise RuntimeError("Interfaces do Device mudaram: live={0} expected={1}".format(live_ids, expected_ids))
    for item in interfaces:
        if clean(item.get("description")) != clean(repair.get("expected_interface_description")):
            raise RuntimeError("Interface não pertence ao produto")
        if item.get("cable") or item.get("mark_connected"):
            raise RuntimeError("Interface recebeu cabo/conexão manual")

    if clean(ip_obj.get("description")) != clean(repair.get("expected_ip_description")):
        raise RuntimeError("IP não pertence ao produto")
    if clean(ip_obj.get("address")) != clean(repair.get("ip_address")):
        raise RuntimeError("Endereço IP mudou")
    if nested_id(ip_obj.get("tenant")) not in (None, tenant_id):
        raise RuntimeError("IP mudou de Tenant")

    assignment_type = clean(ip_obj.get("assigned_object_type"))
    assignment_id = _assigned_id(ip_obj)
    if assignment_type == "dcim.interface" and assignment_id in set(expected_ids):
        live_mode = "FULL"
    elif assignment_type == "virtualization.vminterface" and assignment_id == repair["vm_interface_id"]:
        live_mode = "RECOVERY_AFTER_IP_MOVE"
    else:
        raise RuntimeError("IP pertence a outro objeto: {0} ID {1}".format(assignment_type or "unassigned", assignment_id))

    primary = vm.get("primary_ip4") or vm.get("primary_ip") or {}
    current_primary_id = nested_id(primary)
    if current_primary_id not in (None, repair["ip_id"]):
        raise RuntimeError("VM já possui outro primary IPv4")

    related_endpoints = (
        "dcim/inventory-items/", "dcim/console-ports/", "dcim/console-server-ports/",
        "dcim/power-ports/", "dcim/power-outlets/", "dcim/front-ports/",
        "dcim/rear-ports/", "dcim/device-bays/", "dcim/module-bays/",
    )
    for endpoint in related_endpoints:
        count = _device_related_count(nb, endpoint, repair["device_id"])
        if count:
            raise RuntimeError("Device possui objetos relacionados em {0}: {1}".format(endpoint, count))

    all_macs = _all_mac_rows(nb)
    live_macs = [
        item for item in all_macs
        if clean(item.get("assigned_object_type")) == "dcim.interface" and _assigned_id(item) in set(expected_ids)
    ]
    expected_mac_ids = sorted(repair.get("mac_ids") or [])
    live_mac_ids = sorted(item.get("id") for item in live_macs if item.get("id"))
    # Recovery is allowed to have already removed the product MAC rows.
    if live_mode == "FULL" and live_mac_ids != expected_mac_ids:
        raise RuntimeError("MACs do Device mudaram: live={0} expected={1}".format(live_mac_ids, expected_mac_ids))
    if live_mode == "RECOVERY_AFTER_IP_MOVE" and any(mid not in expected_mac_ids for mid in live_mac_ids):
        raise RuntimeError("Device ganhou MAC inesperado após reparo parcial")
    for item in live_macs:
        desc = clean(item.get("description"))
        if desc and "netbox-discovery" not in desc:
            raise RuntimeError("Device possui MAC não criado pelo produto")

    return {
        "mode": live_mode,
        "device": device,
        "vm": vm,
        "vm_interface": vm_interface,
        "ip": ip_obj,
        "interfaces": interfaces,
        "macs": live_macs,
    }


def _execute_repair(nb, row, verified, events):
    repair = row.get("repair") or {}
    ip_obj = verified["ip"]
    vm = verified["vm"]
    device = verified["device"]

    if verified.get("mode") != "RECOVERY_AFTER_IP_MOVE":
        ip_obj = nb.patch("ipam/ip-addresses/{0}/".format(ip_obj["id"]), {
            "assigned_object_type": "virtualization.vminterface",
            "assigned_object_id": repair["vm_interface_id"],
        })
        events.append({
            "phase": "REPAIR", "object_type": "IP_ADDRESS", "action": "MOVED_TO_VM",
            "name": repair.get("ip_address"), "object_id": ip_obj.get("id"),
            "detail": "VM {0} / interface {1}".format(repair.get("vm_name"), repair.get("vm_interface_name")),
        })
    else:
        events.append({
            "phase": "REPAIR", "object_type": "IP_ADDRESS", "action": "PRESERVED_ON_VM",
            "name": repair.get("ip_address"), "object_id": ip_obj.get("id"),
            "detail": "recuperação de reparo parcial",
        })

    current_primary = nested_id(vm.get("primary_ip4") or vm.get("primary_ip"))
    if not current_primary:
        nb.patch("virtualization/virtual-machines/{0}/".format(repair["vm_id"]), {"primary_ip4": repair["ip_id"]})
        events.append({
            "phase": "REPAIR", "object_type": "VIRTUAL_MACHINE", "action": "PRIMARY_IP_SET",
            "name": repair.get("vm_name"), "object_id": repair.get("vm_id"),
            "detail": repair.get("ip_address"),
        })

    clear_payload = {}
    for field in ("primary_ip4", "primary_ip6", "oob_ip"):
        if nested_id(device.get(field)):
            clear_payload[field] = None
    if clear_payload:
        nb.patch("dcim/devices/{0}/".format(repair["device_id"]), clear_payload)

    for interface in verified.get("interfaces") or []:
        if nested_id(interface.get("primary_mac_address")):
            nb.patch("dcim/interfaces/{0}/".format(interface["id"]), {"primary_mac_address": None})
    for mac in verified.get("macs") or []:
        nb.delete("dcim/mac-addresses/{0}/".format(mac["id"]))
        events.append({
            "phase": "REPAIR", "object_type": "MAC_ADDRESS", "action": "DELETED_PRODUCT_DUPLICATE",
            "name": clean(mac.get("mac_address") or mac.get("mac")),
            "object_id": mac.get("id"), "detail": repair.get("device_name"),
        })

    nb.delete("dcim/devices/{0}/".format(repair["device_id"]))
    events.append({
        "phase": "REPAIR", "object_type": "DEVICE", "action": "DELETED_PRODUCT_DUPLICATE",
        "name": repair.get("device_name"), "object_id": repair.get("device_id"),
        "detail": "ownership transferido para VM ID {0}".format(repair.get("vm_id")),
    })


def _write_filtered_plan(plan, repairs):
    repair_ids = set(clean(row.get("asset_id")) for row in repairs)
    filtered = dict(plan)
    filtered["records"] = [
        row for row in (plan.get("records") or [])
        if clean(row.get("asset_id")) not in repair_ids
    ]
    stamp = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(REPORTS, "{0}-plan-finalize-normal-{1}.json".format(clean(plan.get("site")) or "SITE", stamp))
    with open(path, "w") as handle:
        json.dump(filtered, handle, indent=2, sort_keys=True)
    return path


def _write_journal(plan_path, repairs, normal_ready):
    with open(plan_path, "r") as handle:
        site = clean(json.load(handle).get("site")) or "SITE"
    stamp = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(REPORTS, "{0}-repair-journal-{1}.json".format(site, stamp))
    with open(path, "w") as handle:
        json.dump({
            "stage": "REPAIR_JOURNAL", "importer_version": IMPORTER_VERSION,
            "source_plan": plan_path, "site": site,
            "repair_rows": repairs, "normal_ready_count": len(normal_ready),
            "preflight": "PASS", "netbox_write": False,
        }, handle, indent=2, sort_keys=True)
    return path


def _write_finalize_report(plan_path, apply_mode, events, errors, summary, journal_path="", normal_import_report=""):
    with open(plan_path, "r") as handle:
        site = clean(json.load(handle).get("site")) or "SITE"
    stamp = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(REPORTS, "{0}-import-finalize-{1}.json".format(site, stamp))
    with open(path, "w") as handle:
        json.dump({
            "stage": "IMPORT_FINALIZE", "importer_version": IMPORTER_VERSION,
            "mode": "APPLY" if apply_mode else "DRY-RUN", "source_plan": plan_path,
            "normal_import_report": normal_import_report, "journal": journal_path,
            "site": site, "summary": dict(summary), "errors": errors,
            "records": events, "netbox_write": bool(apply_mode and not errors),
        }, handle, indent=2, sort_keys=True)
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Network finalizer importer")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--plan", default="")
    parser.add_argument("--no-refresh-plan", action="store_true")
    args = parser.parse_args(argv)

    lock = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        raise RuntimeError("IMPORT FINALIZE já está em execução")
    lock.write(str(os.getpid()))
    lock.flush()

    source_plan = args.plan or (
        None if not args.no_refresh_plan else _latest(os.path.join(REPORTS, "*-plan-*.json"))
    ) or refresh_plan()
    if not source_plan or not os.path.isfile(source_plan):
        raise RuntimeError("PLAN JSON não encontrado")
    with open(source_plan, "r") as handle:
        plan = json.load(handle)
    if clean(plan.get("stage")) != "PLAN" or plan.get("netbox_write") is not False:
        raise RuntimeError("PLAN inválido/proteção ausente")

    records = plan.get("records") or []
    repairs = [
        row for row in records
        if clean(row.get("decision")) == "READY" and clean(row.get("action")) == "REPAIR_SAFE_VM_DUPLICATE"
    ]
    normal_ready = [
        row for row in records
        if clean(row.get("decision")) == "READY" and clean(row.get("action")) != "REPAIR_SAFE_VM_DUPLICATE"
    ]

    print("===== IMPORT FINALIZE 1.10.14 =====")
    print("Modo: {0}".format("APPLY - ESCRITA REAL" if args.apply else "DRY-RUN - SEM ESCRITA"))
    print("Reparos seguros: {0}".format(len(repairs)))
    print("READY normais: {0}".format(len(normal_ready)))

    nb = NetBox()
    tenant, site, devices, ips = base.live_state(nb, clean(plan.get("client")), clean(plan.get("site")))
    indexes = base.build_indexes(devices, ips)
    normal_errors = base.preflight_ready(normal_ready, indexes, tenant)
    verified = []
    repair_errors = []
    for row in repairs:
        try:
            verified.append((row, _verify_repair(nb, row, tenant["id"], site["id"])))
        except Exception as exc:
            repair_errors.append("{0}: {1}".format(clean(row.get("desired_name")), exc))

    all_errors = normal_errors + repair_errors
    if all_errors:
        print("PREFLIGHT GLOBAL FINALIZE: BLOQUEADO - nenhuma escrita iniciada")
        for error in all_errors:
            print(" - {0}".format(error))
        raise RuntimeError("PREFLIGHT GLOBAL FINALIZE encontrou {0} conflito(s)".format(len(all_errors)))
    print("PREFLIGHT GLOBAL FINALIZE: OK")
    print("NetBox write até aqui: NÃO")

    events = []
    errors = []
    summary = Counter()
    journal_path = _write_journal(source_plan, repairs, normal_ready)
    print("REPAIR JOURNAL: {0}".format(journal_path))

    if not args.apply:
        for row, state in verified:
            repair = row.get("repair") or {}
            events.append({
                "phase": "REPAIR", "object_type": "DEVICE", "action": "WOULD_REPAIR_SAFE",
                "name": repair.get("device_name"), "object_id": repair.get("device_id"),
                "detail": "IP {0} -> VM {1}; remover Device duplicado".format(
                    repair.get("ip_address"), repair.get("vm_name")
                ),
            })
        path = _write_finalize_report(source_plan, False, events, errors, summary, journal_path)
        print("JSON FINALIZE: {0}".format(path))
        print("NetBox write: NÃO")
        return 0

    # Execute normal READY first. If it fails, no duplicate-Device repair has
    # started. The strict global preflight above has already validated both sets.
    filtered_plan = _write_filtered_plan(plan, repairs)
    before_imports = set(glob.glob(os.path.join(REPORTS, "*-import-*.json")))
    rc = v3.main(["--apply", "--plan", filtered_plan, "--no-refresh-plan"])
    after_imports = set(glob.glob(os.path.join(REPORTS, "*-import-*.json")))
    new_normal = sorted(after_imports - before_imports, key=os.path.getmtime, reverse=True)
    normal_import_report = new_normal[0] if new_normal else _latest(os.path.join(REPORTS, "*-import-*.json"))
    if rc:
        errors.append({"asset_id": "NORMAL_IMPORT", "name": "normal-ready", "error": "importer_v3 rc={0}".format(rc)})
        summary["errors"] += 1
        path = _write_finalize_report(source_plan, True, events, errors, summary, journal_path, normal_import_report)
        print("JSON FINALIZE: {0}".format(path))
        return 1

    # Revalidate immediately before each destructive repair. This catches any
    # live drift that occurred during the normal import phase.
    for row, _initial_state in verified:
        try:
            live_state = _verify_repair(nb, row, tenant["id"], site["id"])
            _execute_repair(nb, row, live_state, events)
            summary["repairs_safe"] += 1
        except Exception as exc:
            errors.append({
                "asset_id": clean(row.get("asset_id")),
                "name": clean(row.get("desired_name")), "error": str(exc),
            })
            summary["errors"] += 1
            path = _write_finalize_report(source_plan, True, events, errors, summary, journal_path, normal_import_report)
            print("ERRO no reparo {0}: {1}".format(clean(row.get("desired_name")), exc))
            print("JSON FINALIZE: {0}".format(path))
            raise

    summary["normal_ready"] = len(normal_ready)
    summary["assets_processed"] = len(normal_ready) + summary.get("repairs_safe", 0)
    summary["runtime_blocked"] = 0
    path = _write_finalize_report(source_plan, True, events, errors, summary, journal_path, normal_import_report)
    print("===== IMPORT FINALIZE RESULTADO =====")
    print("Reparos seguros concluídos: {0}".format(summary.get("repairs_safe", 0)))
    print("READY normais encaminhados: {0}".format(len(normal_ready)))
    print("Erros: {0}".format(summary.get("errors", 0)))
    print("JSON FINALIZE: {0}".format(path))
    print("NetBox write: SIM")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
