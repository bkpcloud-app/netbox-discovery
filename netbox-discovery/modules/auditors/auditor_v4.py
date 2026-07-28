#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import csv
import datetime
import glob
import json
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from lib.netbox import NetBox
from modules.auditors import auditor_v3 as v3
from modules.auditors import inventory as base

AUDITOR_VERSION = "6.2-product"
BASE = base.BASE
REPORTS = base.REPORTS


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


def _load(path):
    with open(path, "r") as handle:
        return json.load(handle)


def _latest_new(before, pattern):
    after = set(glob.glob(pattern))
    created = sorted(after - before, key=os.path.getmtime, reverse=True)
    if created:
        return created[0]
    rows = sorted(after, key=os.path.getmtime, reverse=True)
    return rows[0] if rows else ""


def generate_fresh_plan():
    planner = os.path.join(BASE, "modules", "inventory", "planner_v4.py")
    before = set(glob.glob(os.path.join(REPORTS, "*-plan-*.json")))
    v3.v2.base.subprocess.check_call([sys.executable, planner])
    return _latest_new(before, os.path.join(REPORTS, "*-plan-*.json"))


def _latest_successful_finalize():
    files = sorted(glob.glob(os.path.join(REPORTS, "*-import-finalize-*.json")), key=os.path.getmtime, reverse=True)
    for path in files:
        try:
            data = _load(path)
        except Exception:
            continue
        if clean(data.get("stage")) != "IMPORT_FINALIZE":
            continue
        if clean(data.get("mode")) != "APPLY" or data.get("netbox_write") is not True:
            continue
        if data.get("errors") or int((data.get("summary") or {}).get("errors") or 0) != 0:
            continue
        return path, data
    raise RuntimeError("Nenhum IMPORT_FINALIZE APPLY concluído sem erros foi encontrado")


def _get_or_none(nb, endpoint):
    try:
        value = nb.get(endpoint)
        return value if isinstance(value, dict) else None
    except Exception:
        return None


def _find_ip(nb, address):
    rows = base.query(nb, "ipam/ip-addresses/", address=clean(address), limit=100)
    exact = [row for row in rows if base.norm_ip(row.get("address")) == base.norm_ip(address)]
    return exact[0] if len(exact) == 1 else None


def _repair_checks(nb, row, fresh_plan, checks):
    aid = clean(row.get("asset_id"))
    label = clean(row.get("desired_name"))
    repair = row.get("repair") or {}

    device = _get_or_none(nb, "dcim/devices/{0}/".format(repair.get("device_id")))
    if device is None:
        base.add_check(checks, "PASS", "REPAIR_DUPLICATE_DEVICE_REMOVED", aid, label,
                       "Device ID {0}".format(repair.get("device_id")))
    else:
        base.add_check(checks, "FAIL", "REPAIR_DUPLICATE_DEVICE_STILL_EXISTS", aid, label,
                       "Device ID {0}".format(repair.get("device_id")))

    vm = _get_or_none(nb, "virtualization/virtual-machines/{0}/".format(repair.get("vm_id")))
    interface = _get_or_none(nb, "virtualization/interfaces/{0}/".format(repair.get("vm_interface_id")))
    ip_obj = _find_ip(nb, repair.get("ip_address"))

    if not vm:
        base.add_check(checks, "FAIL", "REPAIR_VM_MISSING", aid, label, "VM ID {0}".format(repair.get("vm_id")))
    else:
        base.add_check(checks, "PASS", "REPAIR_VM_FOUND", aid, label,
                       "VM ID {0} / {1}".format(vm.get("id"), clean(vm.get("name"))))

    if not interface or nested_id(interface.get("virtual_machine")) != repair.get("vm_id"):
        base.add_check(checks, "FAIL", "REPAIR_VM_INTERFACE_MISMATCH", aid, label,
                       "interface ID {0}".format(repair.get("vm_interface_id")))
    else:
        base.add_check(checks, "PASS", "REPAIR_VM_INTERFACE_OK", aid, label,
                       "interface ID {0}".format(interface.get("id")))

    if not ip_obj:
        base.add_check(checks, "FAIL", "REPAIR_IP_MISSING", aid, label, clean(repair.get("ip_address")))
    elif (clean(ip_obj.get("assigned_object_type")) != "virtualization.vminterface"
          or _assigned_id(ip_obj) != repair.get("vm_interface_id")):
        base.add_check(checks, "FAIL", "REPAIR_IP_WRONG_OWNER", aid, label,
                       "type={0}; object={1}".format(clean(ip_obj.get("assigned_object_type")), _assigned_id(ip_obj)))
    else:
        base.add_check(checks, "PASS", "REPAIR_IP_ON_VM", aid, label,
                       "{0} -> VM interface {1}".format(base.norm_ip(ip_obj.get("address")), repair.get("vm_interface_id")))

    if vm and ip_obj:
        primary = nested_id(vm.get("primary_ip4") or vm.get("primary_ip") or {})
        if primary == ip_obj.get("id"):
            base.add_check(checks, "PASS", "REPAIR_VM_PRIMARY_IP_OK", aid, label, base.norm_ip(ip_obj.get("address")))
        else:
            base.add_check(checks, "FAIL", "REPAIR_VM_PRIMARY_IP_MISMATCH", aid, label,
                           "live={0}; esperado={1}".format(primary, ip_obj.get("id")))

    candidates = [
        current for current in (fresh_plan.get("records") or [])
        if base.norm_ip(current.get("primary_ip")) == base.norm_ip(repair.get("ip_address"))
    ]
    if len(candidates) != 1:
        base.add_check(checks, "FAIL", "REPAIR_IDEMPOTENCY_ASSET_AMBIGUOUS", aid, label,
                       "fresh rows={0}".format(len(candidates)))
    else:
        current = candidates[0]
        if clean(current.get("decision")) == "DELEGATED" and clean(current.get("action")) == "NOOP":
            base.add_check(checks, "PASS", "REPAIR_IDEMPOTENCY_DELEGATED", aid, label,
                           clean(current.get("match_reason")))
        else:
            base.add_check(checks, "FAIL", "REPAIR_IDEMPOTENCY_PENDING", aid, label,
                           "decision={0}; action={1}; reasons={2}".format(
                               clean(current.get("decision")), clean(current.get("action")),
                               " | ".join(current.get("reasons") or [])))


def _asset_summary(checks, ready_rows):
    grouped = defaultdict(list)
    for check in checks:
        if clean(check.get("asset_id")) == "SYSTEM":
            continue
        grouped[(clean(check.get("asset_id")), clean(check.get("name")))].append(check)
    summary = Counter()
    for row in ready_rows:
        key = (clean(row.get("asset_id")), clean(row.get("desired_name")))
        rows = grouped.get(key, [])
        if not rows or any(item.get("severity") == "FAIL" for item in rows):
            summary["FAIL"] += 1
        elif any(item.get("severity") == "WARN" for item in rows):
            summary["WARN"] += 1
        else:
            summary["PASS"] += 1
    return summary


def _write_combined(normal_audit_path, normal_audit, finalize_path, finalize, repair_rows, fresh_plan_path, checks):
    normal_plan = _load(normal_audit.get("source_plan"))
    normal_ready = [row for row in (normal_plan.get("records") or []) if clean(row.get("decision")) == "READY"]
    all_ready = normal_ready + repair_rows
    severity = Counter(item.get("severity") for item in checks)
    assets = _asset_summary(checks, all_ready)
    status = "FAIL" if severity.get("FAIL", 0) else ("PASS_WITH_WARNINGS" if severity.get("WARN", 0) else "PASS")
    site = clean(finalize.get("site")) or clean(normal_audit.get("site")) or "SITE"
    stamp = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    base_path = os.path.join(REPORTS, "{0}-audit-finalize-{1}".format(site, stamp))
    jpath, cpath = base_path + ".json", base_path + ".csv"
    data = {
        "stage": "AUDIT", "auditor_version": AUDITOR_VERSION,
        "mode": "READ-ONLY", "status": status, "site": site,
        "source_import": finalize_path, "normal_source_import": normal_audit.get("source_import"),
        "source_plan": finalize.get("source_plan"), "normal_source_plan": normal_audit.get("source_plan"),
        "fresh_plan": fresh_plan_path, "ready_assets_expected": len(all_ready),
        "import_summary": finalize.get("summary") or {},
        "check_summary": dict(severity), "asset_summary": dict(assets),
        "checks": checks, "netbox_write": False,
    }
    with open(jpath, "w") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
    with open(cpath, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["severity", "code", "asset_id", "name", "detail"])
        writer.writeheader()
        for row in checks:
            writer.writerow(dict((key, row.get(key, "")) for key in writer.fieldnames))
    return status, severity, assets, jpath, cpath


def _print_details(checks):
    relevant = [item for item in checks if item.get("severity") in ("WARN", "FAIL")]
    if not relevant:
        return
    print("===== AUDIT PENDÊNCIAS DETALHADAS =====")
    for pos, row in enumerate(relevant, 1):
        print("[{0}/{1}] {2} | {3} | {4} | {5}".format(
            pos, len(relevant), row.get("severity") or "-", row.get("code") or "-",
            row.get("name") or row.get("asset_id") or "-", row.get("detail") or "-"))


def main(argv=None):
    old_generate = v3.generate_fresh_plan
    before_audits = set(glob.glob(os.path.join(REPORTS, "*-audit-*.json")))
    try:
        v3.generate_fresh_plan = generate_fresh_plan
        normal_rc = v3.main(argv)
    finally:
        v3.generate_fresh_plan = old_generate

    normal_audit_path = _latest_new(before_audits, os.path.join(REPORTS, "*-audit-*.json"))
    if not normal_audit_path:
        raise RuntimeError("AUDIT normal não gerou JSON")
    normal_audit = _load(normal_audit_path)
    finalize_path, finalize = _latest_successful_finalize()
    source_plan = _load(finalize.get("source_plan"))
    repair_rows = [
        row for row in (source_plan.get("records") or [])
        if clean(row.get("decision")) == "READY" and clean(row.get("action")) == "REPAIR_SAFE_VM_DUPLICATE"
    ]
    fresh_plan_path = generate_fresh_plan()
    fresh_plan = _load(fresh_plan_path)
    checks = list(normal_audit.get("checks") or [])

    nb = NetBox()
    for row in repair_rows:
        _repair_checks(nb, row, fresh_plan, checks)

    status, severity, assets, jpath, cpath = _write_combined(
        normal_audit_path, normal_audit, finalize_path, finalize,
        repair_rows, fresh_plan_path, checks,
    )

    print("===== AUDIT FINALIZE RESULTADO =====")
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
    _print_details(checks)
    if normal_rc or status == "FAIL":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
