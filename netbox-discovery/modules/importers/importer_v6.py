#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import builtins
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from modules.importers import importer_v4 as v4
from modules.importers import importer_v5 as v5

IMPORTER_VERSION = "5.4-product"
BASE = v5.BASE
REPORTS = v5.REPORTS
VM_MAC_DESCRIPTION = "Descoberto pelo netbox-discovery hypervisor"


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


def refresh_plan():
    planner = os.path.join(BASE, "modules", "inventory", "planner_v6.py")
    if not os.path.isfile(planner):
        raise RuntimeError("Planner V6 não encontrado: {0}".format(planner))
    v4.base.subprocess.check_call([sys.executable, planner])
    path = v4._latest(os.path.join(REPORTS, "*-plan-*.json"))
    if not path:
        raise RuntimeError("PLAN V6 não gerou JSON")
    return path


def _interface_mac_values(interface, mac_rows):
    values = set()
    primary = interface.get("primary_mac_address") or {}
    if isinstance(primary, dict):
        value = v5.v2.norm_mac(primary.get("mac_address") or primary.get("mac"))
        if value:
            values.add(value)
    for item in interface.get("mac_addresses") or []:
        if isinstance(item, dict):
            value = v5.v2.norm_mac(item.get("mac_address") or item.get("mac"))
            if value:
                values.add(value)
    for item in mac_rows:
        if (clean(item.get("assigned_object_type")) == "virtualization.vminterface"
                and _assigned_id(item) == interface.get("id")):
            value = v5.v2.norm_mac(item.get("mac_address") or item.get("mac"))
            if value:
                values.add(value)
    return values


def _verify_vm_mac(nb, row, verified):
    repair = row.get("repair") or {}
    if clean(repair.get("vm_mac_mode")) != "ENSURE_SINGLE_VM_INTERFACE":
        return verified

    mac = v5.v2.norm_mac(repair.get("vm_mac_address"))
    if not mac:
        raise RuntimeError("Reparo exige vm_mac_address válido")
    target_id = repair.get("vm_interface_id")
    vm_id = repair.get("vm_id")

    all_vm_interfaces = v4.base.query(nb, "virtualization/interfaces/", limit=10000)
    vm_interfaces = [
        item for item in all_vm_interfaces
        if nested_id(item.get("virtual_machine")) == vm_id
    ]
    if len(vm_interfaces) != 1:
        raise RuntimeError("VM deixou de possuir exatamente uma interface: {0}".format(len(vm_interfaces)))
    target = vm_interfaces[0]
    if target.get("id") != target_id:
        raise RuntimeError("Interface única da VM mudou: live={0} expected={1}".format(target.get("id"), target_id))

    mac_rows = v5._all_macs(nb)
    target_values = _interface_mac_values(target, mac_rows)
    if target_values and target_values != set([mac]):
        raise RuntimeError("Interface da VM ganhou MAC diferente: {0}".format(",".join(sorted(target_values))))

    matches = [
        item for item in mac_rows
        if v5.v2.norm_mac(item.get("mac_address") or item.get("mac")) == mac
    ]
    if len(matches) > 1:
        raise RuntimeError("MAC VMware duplicado no NetBox: {0}".format(mac))

    mac_row = matches[0] if matches else None
    if mac_row:
        assigned_type = clean(mac_row.get("assigned_object_type"))
        assigned_id = _assigned_id(mac_row)
        if assigned_id and (assigned_type != "virtualization.vminterface" or assigned_id != target_id):
            raise RuntimeError("MAC VMware pertence a {0} ID {1}".format(assigned_type or "outro objeto", assigned_id))
        if not assigned_id:
            description = clean(mac_row.get("description"))
            if description and "netbox-discovery" not in description:
                raise RuntimeError("MAC VMware sem vínculo não pertence ao produto")

    primary = target.get("primary_mac_address") or {}
    primary_id = nested_id(primary)
    if primary_id and (not mac_row or primary_id != mac_row.get("id")):
        raise RuntimeError("Interface da VM já possui outro primary MAC")

    result = dict(verified)
    result["vm_mac_target"] = target
    result["vm_mac_row"] = mac_row
    result["vm_mac_address"] = mac
    return result


def _ensure_vm_mac(nb, row, verified, events):
    repair = row.get("repair") or {}
    if clean(repair.get("vm_mac_mode")) != "ENSURE_SINGLE_VM_INTERFACE":
        return

    # Re-read the MAC collection immediately before writing. Any ownership drift
    # blocks before IP movement or Device deletion.
    checked = _verify_vm_mac(nb, row, verified)
    target = checked["vm_mac_target"]
    mac = checked["vm_mac_address"]
    mac_row = checked.get("vm_mac_row")

    if not mac_row:
        mac_row = nb.post("dcim/mac-addresses/", {
            "mac_address": mac,
            "assigned_object_type": "virtualization.vminterface",
            "assigned_object_id": target["id"],
            "description": VM_MAC_DESCRIPTION,
        })
        action = "CREATED_ON_VM_INTERFACE"
    else:
        assigned_id = _assigned_id(mac_row)
        if not assigned_id:
            mac_row = nb.patch("dcim/mac-addresses/{0}/".format(mac_row["id"]), {
                "assigned_object_type": "virtualization.vminterface",
                "assigned_object_id": target["id"],
                "description": clean(mac_row.get("description")) or VM_MAC_DESCRIPTION,
            })
            action = "ASSIGNED_TO_VM_INTERFACE"
        else:
            action = "PRESERVED_ON_VM_INTERFACE"

    primary_id = nested_id(target.get("primary_mac_address") or {})
    if primary_id != mac_row.get("id"):
        nb.patch("virtualization/interfaces/{0}/".format(target["id"]), {
            "primary_mac_address": mac_row["id"],
        })

    events.append({
        "phase": "REPAIR",
        "object_type": "VM_MAC_ADDRESS",
        "action": action,
        "name": mac,
        "object_id": mac_row.get("id"),
        "detail": "VM ID {0} / interface ID {1}".format(repair.get("vm_id"), target.get("id")),
    })


def main(argv=None):
    old_refresh = v5.refresh_plan
    old_version = v5.IMPORTER_VERSION
    old_verify = v4._verify_repair
    old_execute = v4._execute_repair
    old_print = builtins.print

    def verify_repair(nb, row, tenant_id, site_id):
        verified = old_verify(nb, row, tenant_id, site_id)
        return _verify_vm_mac(nb, row, verified)

    def execute_repair(nb, row, verified, events):
        _ensure_vm_mac(nb, row, verified, events)
        return old_execute(nb, row, verified, events)

    def release_print(*args, **kwargs):
        if args and str(args[0]) in (
                "===== IMPORT FINALIZE 1.10.14 =====",
                "===== IMPORT FINALIZE 1.10.15 ====="):
            args = ("===== IMPORT FINALIZE 1.10.16 =====",) + tuple(args[1:])
        return old_print(*args, **kwargs)

    try:
        v5.refresh_plan = refresh_plan
        v5.IMPORTER_VERSION = IMPORTER_VERSION
        v4._verify_repair = verify_repair
        v4._execute_repair = execute_repair
        builtins.print = release_print
        return v5.main(argv)
    finally:
        builtins.print = old_print
        v4._verify_repair = old_verify
        v4._execute_repair = old_execute
        v5.refresh_plan = old_refresh
        v5.IMPORTER_VERSION = old_version


if __name__ == "__main__":
    sys.exit(main())
