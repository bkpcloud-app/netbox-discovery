#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import argparse
import csv
import datetime
import fcntl
import glob
import ipaddress
import json
import os
import re
import subprocess
import sys
import urllib.parse
from collections import Counter, defaultdict

BASE = os.environ.get("NETBOX_DISCOVERY_BASE", "/opt/netbox-discovery")
REPORTS = os.path.join(BASE, "reports")
LOCK_FILE = "/var/lock/netbox-discovery-audit.lock"
AUDITOR_VERSION = "5.2-product"


def clean(v):
    return "" if v is None else str(v).strip()


def norm(v):
    return re.sub(r"\s+", " ", clean(v)).strip().lower()


def norm_serial(v):
    return re.sub(r"[^A-Za-z0-9]", "", clean(v)).upper()


def norm_ip(v):
    s = clean(v)
    if not s:
        return ""
    try:
        return str(ipaddress.ip_interface(s).ip)
    except Exception:
        try:
            return str(ipaddress.ip_address(s.split("/")[0]))
        except Exception:
            return ""


def nested_id(v):
    if isinstance(v, dict):
        return v.get("id")
    if isinstance(v, int):
        return v
    return None


def nested_name(v):
    if isinstance(v, dict):
        return clean(v.get("name") or v.get("display") or v.get("model"))
    return clean(v)


def device_type_parts(device):
    dt = device.get("device_type") or {}
    if not isinstance(dt, dict):
        return "", ""
    model = clean(dt.get("model") or dt.get("display") or dt.get("name"))
    manufacturer = nested_name(dt.get("manufacturer"))
    return manufacturer, model


def query(nb, endpoint, **params):
    params = dict((k, v) for k, v in params.items() if v is not None and v != "")
    params.setdefault("limit", 1000)
    suffix = urllib.parse.urlencode(params)
    path = endpoint
    if suffix:
        path += ("&" if "?" in path else "?") + suffix
    return nb.get_all(path)


def choose_exact(rows, value, label, field="name"):
    found = [x for x in rows if norm(x.get(field)) == norm(value)]
    if len(found) == 1:
        return found[0]
    if len(found) > 1:
        raise RuntimeError("{0} duplicado no NetBox: {1}".format(label, value))
    return None


def latest_files(pattern):
    return sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)


def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def find_latest_successful_apply(path=""):
    candidates = [path] if path else latest_files(os.path.join(REPORTS, "*-import-*.json"))
    for candidate in candidates:
        if not candidate or not os.path.isfile(candidate):
            continue
        try:
            data = load_json(candidate)
        except Exception:
            continue
        if clean(data.get("stage")) != "IMPORT":
            continue
        if clean(data.get("mode")) != "APPLY" or data.get("netbox_write") is not True:
            continue
        summary = data.get("summary") or {}
        if data.get("errors"):
            continue
        if int(summary.get("errors") or 0) != 0:
            continue
        if int(summary.get("runtime_blocked") or 0) != 0:
            continue
        return candidate, data
    raise RuntimeError("Nenhum IMPORT APPLY concluído sem erros foi encontrado")


def get_device_id_from_ip(ipr):
    ao = ipr.get("assigned_object") or {}
    if isinstance(ao, dict):
        dev = ao.get("device") or {}
        if isinstance(dev, dict) and dev.get("id"):
            return dev.get("id")
        if clean(ipr.get("assigned_object_type")) == "dcim.interface" and ao.get("id"):
            # Some NetBox serializers may omit nested device on compact responses.
            # The caller can resolve the interface if necessary.
            return None
    return None


def assigned_object_id(ipr):
    ao = ipr.get("assigned_object") or {}
    if isinstance(ao, dict) and ao.get("id"):
        return ao.get("id")
    return ipr.get("assigned_object_id")


def live_state(nb, client, site_name):
    tenant = choose_exact(query(nb, "tenancy/tenants/", name=client), client, "Tenant")
    site = choose_exact(query(nb, "dcim/sites/", name=site_name), site_name, "Site")
    if not tenant:
        raise RuntimeError("Tenant não encontrado: {0}".format(client))
    if not site:
        raise RuntimeError("Site não encontrado: {0}".format(site_name))

    # Site-wide device query intentionally ignores tenant so tenant drift is visible.
    devices = query(nb, "dcim/devices/", site_id=site["id"])

    # NetBox IP uniqueness is global unless VRF is used. Audit the global table.
    ips = [x for x in query(nb, "ipam/ip-addresses/") if not x.get("vrf")]
    return tenant, site, devices, ips


def build_indexes(devices, ips):
    by_id = dict((x.get("id"), x) for x in devices if x.get("id") is not None)
    by_name = defaultdict(list)
    by_serial = defaultdict(list)
    ip_objects = defaultdict(list)
    ip_device_ids = defaultdict(set)

    for d in devices:
        if clean(d.get("name")):
            by_name[norm(d.get("name"))].append(d)
        serial = norm_serial(d.get("serial"))
        if serial:
            by_serial[serial].append(d)

    for ipr in ips:
        ip = norm_ip(ipr.get("address"))
        if not ip:
            continue
        ip_objects[ip].append(ipr)
        did = get_device_id_from_ip(ipr)
        if did:
            ip_device_ids[ip].add(did)

    return {
        "by_id": by_id,
        "by_name": by_name,
        "by_serial": by_serial,
        "ip_objects": ip_objects,
        "ip_device_ids": ip_device_ids,
    }


def ensure_device_loaded(nb, indexes, device_id):
    if not device_id:
        return None
    current = indexes["by_id"].get(device_id)
    if current:
        return current
    try:
        obj = nb.get("dcim/devices/{0}/".format(device_id))
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None
    indexes["by_id"][device_id] = obj
    if clean(obj.get("name")):
        indexes["by_name"][norm(obj.get("name"))].append(obj)
    if norm_serial(obj.get("serial")):
        indexes["by_serial"][norm_serial(obj.get("serial"))].append(obj)
    return obj


def resolve_ip_device(nb, ipr):
    did = get_device_id_from_ip(ipr)
    if did:
        return did
    if clean(ipr.get("assigned_object_type")) != "dcim.interface":
        return None
    iid = assigned_object_id(ipr)
    if not iid:
        return None
    try:
        iface = nb.get("dcim/interfaces/{0}/".format(iid))
    except Exception:
        return None
    dev = iface.get("device") or {} if isinstance(iface, dict) else {}
    return nested_id(dev)


def resolve_target(nb, row, indexes):
    strong = set()
    serial = norm_serial(row.get("serial"))
    if serial:
        strong.update(x.get("id") for x in indexes["by_serial"].get(serial, []) if x.get("id"))

    for ip in row.get("ips") or []:
        ipn = norm_ip(ip)
        for ipr in indexes["ip_objects"].get(ipn, []):
            did = resolve_ip_device(nb, ipr)
            if did:
                strong.add(did)
                ensure_device_loaded(nb, indexes, did)

    if len(strong) > 1:
        return None, "CONFLICT", "serial/IP apontam para devices diferentes: {0}".format(sorted(strong))
    if len(strong) == 1:
        did = list(strong)[0]
        return ensure_device_loaded(nb, indexes, did), "MATCHED", "serial/IP"

    expected_existing = row.get("existing_device_id")
    if expected_existing:
        dev = ensure_device_loaded(nb, indexes, expected_existing)
        if dev:
            return dev, "MATCHED", "existing_device_id"

    names = indexes["by_name"].get(norm(row.get("desired_name")), [])
    unique_ids = sorted(set(x.get("id") for x in names if x.get("id")))
    if len(unique_ids) == 1:
        return ensure_device_loaded(nb, indexes, unique_ids[0]), "MATCHED", "name"
    if len(unique_ids) > 1:
        return None, "CONFLICT", "nome duplicado no site"
    return None, "MISSING", "device não encontrado"


def add_check(checks, severity, code, asset_id, name, detail=""):
    checks.append({
        "severity": severity,
        "code": code,
        "asset_id": clean(asset_id),
        "name": clean(name),
        "detail": clean(detail),
    })


def safe_diff_has(row, prefix):
    for item in row.get("safe_diffs") or []:
        if clean(item).startswith(prefix):
            return True
    return False


def compare_expected_inventory(row, device, tenant, site, checks):
    aid = row.get("asset_id")
    label = row.get("desired_name")
    created = clean(row.get("action")) == "CREATE"

    if nested_id(device.get("tenant")) != tenant.get("id"):
        add_check(checks, "FAIL", "TENANT_MISMATCH", aid, label,
                  "device tenant={0}, esperado={1}".format(nested_name(device.get("tenant")), tenant.get("name")))
    else:
        add_check(checks, "PASS", "TENANT_OK", aid, label)

    if nested_id(device.get("site")) != site.get("id"):
        add_check(checks, "FAIL", "SITE_MISMATCH", aid, label,
                  "device site={0}, esperado={1}".format(nested_name(device.get("site")), site.get("name")))
    else:
        add_check(checks, "PASS", "SITE_OK", aid, label)

    if clean(device.get("status", {}).get("value") if isinstance(device.get("status"), dict) else device.get("status")) not in ("active", ""):
        add_check(checks, "WARN", "STATUS_NOT_ACTIVE", aid, label, clean(device.get("status")))

    live_name = clean(device.get("name"))
    if norm(live_name) != norm(label):
        if created:
            add_check(checks, "FAIL", "NAME_MISMATCH", aid, label, "live={0}".format(live_name))
        else:
            add_check(checks, "WARN", "NAME_PRESERVED", aid, label, "live={0}".format(live_name))
    else:
        add_check(checks, "PASS", "NAME_OK", aid, label)

    expected_serial = norm_serial(row.get("serial"))
    if expected_serial:
        live_serial = norm_serial(device.get("serial"))
        if live_serial != expected_serial:
            add_check(checks, "FAIL", "SERIAL_MISMATCH", aid, label,
                      "live={0}, esperado={1}".format(clean(device.get("serial")), clean(row.get("serial"))))
        else:
            add_check(checks, "PASS", "SERIAL_OK", aid, label)

    expected_role = clean(row.get("target_role"))
    if expected_role:
        live_role = nested_name(device.get("role"))
        if norm(live_role) != norm(expected_role):
            severity = "FAIL" if created or safe_diff_has(row, "role:SET:") else "WARN"
            add_check(checks, severity, "ROLE_MISMATCH", aid, label,
                      "live={0}, esperado={1}".format(live_role, expected_role))
        else:
            add_check(checks, "PASS", "ROLE_OK", aid, label)

    expected_platform = clean(row.get("platform"))
    if expected_platform:
        live_platform = nested_name(device.get("platform"))
        if norm(live_platform) != norm(expected_platform):
            severity = "FAIL" if created or safe_diff_has(row, "platform:SET:") else "WARN"
            add_check(checks, severity, "PLATFORM_MISMATCH", aid, label,
                      "live={0}, esperado={1}".format(live_platform, expected_platform))
        else:
            add_check(checks, "PASS", "PLATFORM_OK", aid, label)

    expected_mfg = clean(row.get("manufacturer"))
    expected_model = clean(row.get("model"))
    live_mfg, live_model = device_type_parts(device)
    if expected_mfg or expected_model:
        if norm(live_mfg) != norm(expected_mfg) or norm(live_model) != norm(expected_model):
            severity = "FAIL" if created else "WARN"
            add_check(checks, severity, "DEVICE_TYPE_MISMATCH", aid, label,
                      "live={0}/{1}, esperado={2}/{3}".format(live_mfg, live_model, expected_mfg, expected_model))
        else:
            add_check(checks, "PASS", "DEVICE_TYPE_OK", aid, label)


def audit_ips(nb, row, device, indexes, checks):
    aid = row.get("asset_id")
    label = row.get("desired_name")
    expected_device_id = device.get("id")

    for spec in row.get("interfaces") or []:
        ip = norm_ip(spec.get("ip"))
        if not ip:
            add_check(checks, "FAIL", "INVALID_EXPECTED_IP", aid, label, clean(spec.get("ip")))
            continue
        objects = indexes["ip_objects"].get(ip, [])
        if len(objects) == 0:
            add_check(checks, "FAIL", "IP_MISSING", aid, label, ip)
            continue
        if len(objects) > 1:
            add_check(checks, "FAIL", "IP_DUPLICATE", aid, label,
                      "{0} objetos para {1}".format(len(objects), ip))
            continue
        ipr = objects[0]
        assigned_type = clean(ipr.get("assigned_object_type"))
        if assigned_type != "dcim.interface":
            add_check(checks, "FAIL", "IP_WRONG_OBJECT_TYPE", aid, label,
                      "{0}: {1}".format(ip, assigned_type or "unassigned"))
            continue
        did = resolve_ip_device(nb, ipr)
        if did != expected_device_id:
            add_check(checks, "FAIL", "IP_WRONG_DEVICE", aid, label,
                      "{0}: device={1}, esperado={2}".format(ip, did, expected_device_id))
        else:
            add_check(checks, "PASS", "IP_OK", aid, label, ip)

    expected_primary = norm_ip(row.get("primary_ip"))
    if expected_primary:
        live_primary = ""
        for key in ("primary_ip4", "primary_ip"):
            val = device.get(key) or {}
            if isinstance(val, dict):
                live_primary = norm_ip(val.get("address"))
            else:
                live_primary = norm_ip(val)
            if live_primary:
                break
        if live_primary != expected_primary:
            # IMPORT is fill-only for primary_ip4 on an existing Device: it only
            # sets a primary when the Device has none. Therefore a non-empty
            # existing primary is intentionally preserved and must not fail the
            # post-import audit. CREATE remains strict because the importer owns
            # the primary IP for a newly created Device.
            severity = "FAIL" if clean(row.get("action")) == "CREATE" else "WARN"
            code = "PRIMARY_IP_MISMATCH" if severity == "FAIL" else "PRIMARY_IP_PRESERVED"
            add_check(checks, severity, code, aid, label,
                      "live={0}, descoberto={1}".format(live_primary or "NONE", expected_primary))
        else:
            add_check(checks, "PASS", "PRIMARY_IP_OK", aid, label, expected_primary)

    expected_oob = [norm_ip(x) for x in row.get("oob_ips") or [] if norm_ip(x)]
    if expected_oob:
        live_oob = ""
        val = device.get("oob_ip") or {}
        if isinstance(val, dict):
            live_oob = norm_ip(val.get("address"))
        else:
            live_oob = norm_ip(val)
        if live_oob not in expected_oob:
            severity = "FAIL" if clean(row.get("action")) == "CREATE" else "WARN"
            add_check(checks, severity, "OOB_IP_MISMATCH", aid, label,
                      "live={0}, esperado um de {1}".format(live_oob or "NONE", ",".join(expected_oob)))
        else:
            add_check(checks, "PASS", "OOB_IP_OK", aid, label, live_oob)


def audit_duplicates(row, indexes, checks):
    aid = row.get("asset_id")
    label = row.get("desired_name")
    names = indexes["by_name"].get(norm(label), [])
    if len(set(x.get("id") for x in names if x.get("id"))) > 1:
        add_check(checks, "FAIL", "DUPLICATE_DEVICE_NAME", aid, label,
                  "IDs={0}".format(sorted(set(x.get("id") for x in names if x.get("id")))))

    serial = norm_serial(row.get("serial"))
    if serial:
        rows = indexes["by_serial"].get(serial, [])
        ids = sorted(set(x.get("id") for x in rows if x.get("id")))
        if len(ids) > 1:
            add_check(checks, "FAIL", "DUPLICATE_DEVICE_SERIAL", aid, label,
                      "serial={0}, IDs={1}".format(clean(row.get("serial")), ids))


def generate_fresh_plan():
    planner = os.path.join(BASE, "modules", "inventory", "planner.py")
    before = set(glob.glob(os.path.join(REPORTS, "*-plan-*.json")))
    subprocess.check_call([sys.executable, planner])
    after = set(glob.glob(os.path.join(REPORTS, "*-plan-*.json")))
    created = sorted(after - before, key=os.path.getmtime, reverse=True)
    if created:
        return created[0]
    files = latest_files(os.path.join(REPORTS, "*-plan-*.json"))
    if not files:
        raise RuntimeError("PLAN não gerou JSON para idempotência")
    return files[0]


def plan_record_key(row):
    # asset_id was not unique in legacy reports when multiple devices exposed
    # the same generic SNMP name. desired_name + primary_ip makes the audit
    # key unique while remaining deterministic for the same PLAN input.
    return (
        clean(row.get("asset_id")),
        clean(row.get("desired_name")),
        norm_ip(row.get("primary_ip")),
    )


def audit_idempotency(original_ready, fresh_plan, checks):
    fresh_by_key = dict((plan_record_key(x), x) for x in fresh_plan.get("records") or [])
    for original in original_ready:
        aid = clean(original.get("asset_id"))
        label = clean(original.get("desired_name"))
        current = fresh_by_key.get(plan_record_key(original))
        if not current:
            add_check(checks, "FAIL", "IDEMPOTENCY_ASSET_MISSING", aid, label,
                      "key={0}".format(plan_record_key(original)))
            continue
        if clean(current.get("decision")) != "READY":
            add_check(checks, "FAIL", "IDEMPOTENCY_NOT_READY", aid, label,
                      "decision={0}; reasons={1}".format(clean(current.get("decision")), " | ".join(current.get("reasons") or [])))
            continue
        if clean(current.get("action")) != "NOOP":
            add_check(checks, "FAIL", "IDEMPOTENCY_DEVICE_WRITE_PENDING", aid, label,
                      "action={0}; diffs={1}".format(clean(current.get("action")), " | ".join(current.get("safe_diffs") or [])))
            continue
        pending_ips = [x for x in current.get("ip_intents") or [] if clean(x.get("action")) != "NOOP"]
        if pending_ips:
            detail = "; ".join("{0}:{1}".format(clean(x.get("ip")), clean(x.get("action"))) for x in pending_ips)
            add_check(checks, "FAIL", "IDEMPOTENCY_IP_WRITE_PENDING", aid, label, detail)
            continue
        add_check(checks, "PASS", "IDEMPOTENCY_NOOP", aid, label)


def write_reports(site_name, source_import, source_plan, fresh_plan_path, checks, ready_rows, import_summary):
    severity = Counter(x.get("severity") for x in checks)

    # Summarize exactly the READY records, not a dict keyed only by asset_id.
    # This fixes legacy generic-name collisions and excludes SYSTEM checks from
    # the asset count. (SYSTEM remains in check_summary.)
    per_record = defaultdict(list)
    for c in checks:
        if clean(c.get("asset_id")) == "SYSTEM":
            continue
        per_record[(clean(c.get("asset_id")), clean(c.get("name")))].append(c)

    asset_summary = Counter()
    for row in ready_rows:
        key = (clean(row.get("asset_id")), clean(row.get("desired_name")))
        rows = per_record.get(key, [])
        if not rows:
            asset_summary["FAIL"] += 1
        elif any(x.get("severity") == "FAIL" for x in rows):
            asset_summary["FAIL"] += 1
        elif any(x.get("severity") == "WARN" for x in rows):
            asset_summary["WARN"] += 1
        else:
            asset_summary["PASS"] += 1

    ready_count = len(ready_rows)

    status = "FAIL" if severity.get("FAIL", 0) else ("PASS_WITH_WARNINGS" if severity.get("WARN", 0) else "PASS")
    stamp = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    base = os.path.join(REPORTS, "{0}-audit-{1}".format(site_name, stamp))
    jpath, cpath = base + ".json", base + ".csv"

    out = {
        "stage": "AUDIT",
        "auditor_version": AUDITOR_VERSION,
        "mode": "READ-ONLY",
        "status": status,
        "site": site_name,
        "source_import": source_import,
        "source_plan": source_plan,
        "fresh_plan": fresh_plan_path,
        "ready_assets_expected": ready_count,
        "import_summary": import_summary,
        "check_summary": dict(severity),
        "asset_summary": dict(asset_summary),
        "checks": checks,
        "netbox_write": False,
    }
    with open(jpath, "w") as f:
        json.dump(out, f, indent=2, sort_keys=True)

    fields = ["severity", "code", "asset_id", "name", "detail"]
    with open(cpath, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in checks:
            w.writerow(dict((k, row.get(k, "")) for k in fields))
    return status, severity, asset_summary, jpath, cpath


def main(argv=None):
    ap = argparse.ArgumentParser(description="netbox-discovery AUDIT pós-import (read-only)")
    ap.add_argument("--import-report", default="", help="IMPORT APPLY JSON específico")
    args = ap.parse_args(argv)

    lock = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        raise RuntimeError("AUDIT já está em execução")
    lock.write(str(os.getpid()))
    lock.flush()

    sys.path.insert(0, BASE)
    from lib.netbox import NetBox

    source_import, import_report = find_latest_successful_apply(args.import_report)
    source_plan = clean(import_report.get("source_plan"))
    if not source_plan or not os.path.isfile(source_plan):
        raise RuntimeError("PLAN do IMPORT não encontrado: {0}".format(source_plan))
    plan = load_json(source_plan)
    if clean(plan.get("stage")) != "PLAN":
        raise RuntimeError("source_plan não é um PLAN válido")

    client = clean(plan.get("client"))
    site_name = clean(plan.get("site"))
    records = plan.get("records") or []
    ready = [x for x in records if clean(x.get("decision")) == "READY"]
    import_summary = import_report.get("summary") or {}

    print("===== AUDIT =====")
    print("IMPORT: {0}".format(source_import))
    print("PLAN:   {0}".format(source_plan))
    print("READY esperados: {0}".format(len(ready)))
    print("Modo: READ-ONLY")

    checks = []

    processed = int(import_summary.get("assets_processed") or 0)
    if processed != len(ready):
        add_check(checks, "FAIL", "IMPORT_COUNT_MISMATCH", "SYSTEM", site_name,
                  "processados={0}, READY={1}".format(processed, len(ready)))
    else:
        add_check(checks, "PASS", "IMPORT_COUNT_OK", "SYSTEM", site_name, str(processed))
    if int(import_summary.get("runtime_blocked") or 0) != 0:
        add_check(checks, "FAIL", "IMPORT_RUNTIME_BLOCKED", "SYSTEM", site_name,
                  str(import_summary.get("runtime_blocked")))
    if int(import_summary.get("errors") or 0) != 0 or import_report.get("errors"):
        add_check(checks, "FAIL", "IMPORT_ERRORS", "SYSTEM", site_name,
                  str(import_report.get("errors") or import_summary.get("errors")))

    nb = NetBox()
    tenant, site, devices, ips = live_state(nb, client, site_name)
    indexes = build_indexes(devices, ips)

    print("NetBox: {0} devices no site; {1} IPs globais sem VRF".format(len(devices), len(ips)))

    for pos, row in enumerate(ready, 1):
        label = clean(row.get("desired_name")) or clean(row.get("asset_id"))
        device, state, reason = resolve_target(nb, row, indexes)
        if state == "CONFLICT":
            add_check(checks, "FAIL", "IDENTITY_CONFLICT", row.get("asset_id"), label, reason)
            continue
        if not device:
            add_check(checks, "FAIL", "DEVICE_MISSING", row.get("asset_id"), label, reason)
            continue
        add_check(checks, "PASS", "DEVICE_FOUND", row.get("asset_id"), label,
                  "id={0}; via={1}".format(device.get("id"), reason))
        compare_expected_inventory(row, device, tenant, site, checks)
        audit_ips(nb, row, device, indexes, checks)
        audit_duplicates(row, indexes, checks)
        if pos % 25 == 0 or pos == len(ready):
            print("Auditados: {0}/{1}".format(pos, len(ready)))

    print("===== IDEMPOTENCY PREVIEW =====")
    fresh_plan_path = generate_fresh_plan()
    fresh_plan = load_json(fresh_plan_path)
    audit_idempotency(ready, fresh_plan, checks)

    status, severity, assets, jpath, cpath = write_reports(
        site_name, source_import, source_plan, fresh_plan_path, checks, ready, import_summary
    )

    print("===== AUDIT RESULTADO =====")
    print("Status: {0}".format(status))
    print("Assets PASS: {0}".format(assets.get("PASS", 0)))
    print("Assets WARN: {0}".format(assets.get("WARN", 0)))
    print("Assets FAIL: {0}".format(assets.get("FAIL", 0)))
    print("Checks PASS: {0}".format(severity.get("PASS", 0)))
    print("Checks WARN: {0}".format(severity.get("WARN", 0)))
    print("Checks FAIL: {0}".format(severity.get("FAIL", 0)))
    print("JSON: {0}".format(jpath))
    print("CSV:  {0}".format(cpath))
    print("NetBox write: NÃO")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
