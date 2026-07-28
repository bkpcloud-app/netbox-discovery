#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import copy
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from modules.auditors import auditor_v4 as v4
from modules.auditors import auditor_v6 as v6

AUDITOR_VERSION = "6.5-product"
BASE = v6.BASE
REPORTS = v6.REPORTS


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
    planner = os.path.join(BASE, "modules", "inventory", "planner_v7.py")
    before = set(glob.glob(os.path.join(REPORTS, "*-plan-*.json")))
    v4.v3.v2.base.subprocess.check_call([sys.executable, planner])
    after = set(glob.glob(os.path.join(REPORTS, "*-plan-*.json")))
    created = sorted(after - before, key=os.path.getmtime, reverse=True)
    if created:
        return created[0]
    rows = sorted(after, key=os.path.getmtime, reverse=True)
    if not rows:
        raise RuntimeError("PLAN V7 não gerou JSON para idempotência")
    return rows[0]


def _resolve_created_interface(nb, row):
    repair = row.get("repair") or {}
    vm_id = repair.get("vm_id")
    mac = v4.base.norm_mac(repair.get("vm_mac_address"))
    if not vm_id or not mac:
        return None, None, "repair sem VM/MAC válido"

    mac_rows = v4.base.query(nb, "dcim/mac-addresses/", limit=10000)
    matches = [
        item for item in mac_rows
        if v4.base.norm_mac(item.get("mac_address") or item.get("mac")) == mac
    ]
    if len(matches) != 1:
        return None, None, "MAC {0}; rows={1}".format(mac, len(matches))
    mac_row = matches[0]
    if clean(mac_row.get("assigned_object_type")) != "virtualization.vminterface":
        return None, mac_row, "MAC owner type={0}".format(clean(mac_row.get("assigned_object_type")))
    target_id = _assigned_id(mac_row)
    if not target_id:
        return None, mac_row, "MAC sem interface atribuída"

    try:
        interface = nb.get("virtualization/interfaces/{0}/".format(target_id))
    except Exception:
        interface = None
    if not interface:
        return None, mac_row, "interface ID {0} ausente".format(target_id)
    if nested_id(interface.get("virtual_machine")) != vm_id:
        return None, mac_row, "interface pertence à VM {0}, esperado {1}".format(
            nested_id(interface.get("virtual_machine")), vm_id)

    vm_interfaces = [
        item for item in v4.base.query(nb, "virtualization/interfaces/", limit=10000)
        if nested_id(item.get("virtual_machine")) == vm_id
    ]
    if len(vm_interfaces) != 1 or vm_interfaces[0].get("id") != target_id:
        return None, mac_row, "VM possui {0} interfaces; alvo={1}".format(
            len(vm_interfaces), target_id)

    primary_id = nested_id(interface.get("primary_mac_address") or {})
    if primary_id != mac_row.get("id"):
        return None, mac_row, "primary MAC live={0}; esperado={1}".format(
            primary_id, mac_row.get("id"))
    return interface, mac_row, ""


def main(argv=None):
    old_v6_generate = v6.generate_fresh_plan
    old_v6_version = v6.AUDITOR_VERSION
    original_repair_checks = v4._repair_checks

    def repair_checks(nb, row, fresh_plan, checks):
        repair = row.get("repair") or {}
        if clean(repair.get("vm_interface_mode")) != "CREATE_SINGLE_VM_INTERFACE":
            return original_repair_checks(nb, row, fresh_plan, checks)

        aid = clean(row.get("asset_id"))
        label = clean(row.get("desired_name"))
        interface, mac_row, error = _resolve_created_interface(nb, row)
        if error:
            v4.base.add_check(checks, "FAIL", "REPAIR_VM_INTERFACE_CREATE_FAILED", aid, label, error)
            return

        patched = copy.deepcopy(row)
        patched_repair = patched.get("repair") or {}
        patched_repair["vm_interface_id"] = interface.get("id")
        patched_repair["vm_interface_name"] = clean(interface.get("name"))
        patched_repair["vm_mac_mode"] = "ENSURE_SINGLE_VM_INTERFACE"
        patched["repair"] = patched_repair

        original_repair_checks(nb, patched, fresh_plan, checks)
        v4.base.add_check(
            checks, "PASS", "REPAIR_VM_INTERFACE_CREATED_OK", aid, label,
            "VM ID {0} / interface ID {1}".format(
                patched_repair.get("vm_id"), interface.get("id")))
        v4.base.add_check(
            checks, "PASS", "REPAIR_VM_MAC_OK", aid, label,
            "{0} -> VM interface {1}".format(
                clean(mac_row.get("mac_address") or mac_row.get("mac")), interface.get("id")))

    try:
        # auditor_v6.main injects its own globals into auditor_v5. Patch the
        # v6 globals themselves so the combined audit uses PLAN V7 and records
        # the 1.10.17 auditor version.
        v6.generate_fresh_plan = generate_fresh_plan
        v6.AUDITOR_VERSION = AUDITOR_VERSION
        v4._repair_checks = repair_checks
        return v6.main(argv)
    finally:
        v4._repair_checks = original_repair_checks
        v6.generate_fresh_plan = old_v6_generate
        v6.AUDITOR_VERSION = old_v6_version


if __name__ == "__main__":
    sys.exit(main())
