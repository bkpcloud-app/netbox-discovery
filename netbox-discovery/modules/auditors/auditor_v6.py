#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from modules.auditors import auditor_v4 as v4
from modules.auditors import auditor_v5 as v5

AUDITOR_VERSION = "6.4-product"
BASE = v5.BASE
REPORTS = v5.REPORTS


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


def generate_fresh_plan():
    planner = os.path.join(BASE, "modules", "inventory", "planner_v6.py")
    before = set(glob.glob(os.path.join(REPORTS, "*-plan-*.json")))
    v4.v3.v2.base.subprocess.check_call([sys.executable, planner])
    after = set(glob.glob(os.path.join(REPORTS, "*-plan-*.json")))
    created = sorted(after - before, key=os.path.getmtime, reverse=True)
    if created:
        return created[0]
    rows = sorted(after, key=os.path.getmtime, reverse=True)
    if not rows:
        raise RuntimeError("PLAN V6 não gerou JSON para idempotência")
    return rows[0]


def _vm_mac_checks(nb, row, checks):
    repair = row.get("repair") or {}
    if clean(repair.get("vm_mac_mode")) != "ENSURE_SINGLE_VM_INTERFACE":
        return

    aid = clean(row.get("asset_id"))
    label = clean(row.get("desired_name"))
    mac = v4.base.norm_mac(repair.get("vm_mac_address"))
    target_id = repair.get("vm_interface_id")

    rows = v4.base.query(nb, "dcim/mac-addresses/", limit=10000)
    matches = [
        item for item in rows
        if v4.base.norm_mac(item.get("mac_address") or item.get("mac")) == mac
    ]
    if len(matches) != 1:
        v4.base.add_check(checks, "FAIL", "REPAIR_VM_MAC_NOT_UNIQUE", aid, label,
                          "MAC {0}; rows={1}".format(mac, len(matches)))
        return

    mac_row = matches[0]
    if (clean(mac_row.get("assigned_object_type")) != "virtualization.vminterface"
            or _assigned_id(mac_row) != target_id):
        v4.base.add_check(checks, "FAIL", "REPAIR_VM_MAC_WRONG_OWNER", aid, label,
                          "type={0}; object={1}; esperado={2}".format(
                              clean(mac_row.get("assigned_object_type")),
                              _assigned_id(mac_row), target_id))
        return

    try:
        interface = nb.get("virtualization/interfaces/{0}/".format(target_id))
    except Exception:
        interface = None
    if not interface:
        v4.base.add_check(checks, "FAIL", "REPAIR_VM_MAC_INTERFACE_MISSING", aid, label,
                          "interface ID {0}".format(target_id))
        return

    primary_id = nested_id(interface.get("primary_mac_address") or {})
    if primary_id != mac_row.get("id"):
        v4.base.add_check(checks, "FAIL", "REPAIR_VM_PRIMARY_MAC_MISMATCH", aid, label,
                          "live={0}; esperado={1}".format(primary_id, mac_row.get("id")))
        return

    v4.base.add_check(checks, "PASS", "REPAIR_VM_MAC_OK", aid, label,
                      "{0} -> VM interface {1}".format(mac, target_id))


def main(argv=None):
    old_generate = v5.generate_fresh_plan
    old_version = v5.AUDITOR_VERSION
    old_repair_checks = v4._repair_checks

    def repair_checks(nb, row, fresh_plan, checks):
        old_repair_checks(nb, row, fresh_plan, checks)
        _vm_mac_checks(nb, row, checks)

    try:
        v5.generate_fresh_plan = generate_fresh_plan
        v5.AUDITOR_VERSION = AUDITOR_VERSION
        v4._repair_checks = repair_checks
        return v5.main(argv)
    finally:
        v4._repair_checks = old_repair_checks
        v5.generate_fresh_plan = old_generate
        v5.AUDITOR_VERSION = old_version


if __name__ == "__main__":
    sys.exit(main())
