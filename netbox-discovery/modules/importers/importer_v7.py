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
from modules.importers import importer_v6 as v6

IMPORTER_VERSION = "5.5-product"
BASE = v6.BASE
REPORTS = v6.REPORTS
VM_INTERFACE_DESCRIPTION = "Descoberto pelo netbox-discovery hypervisor"
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
    planner = os.path.join(BASE, "modules", "inventory", "planner_v7.py")
    if not os.path.isfile(planner):
        raise RuntimeError("Planner V7 não encontrado: {0}".format(planner))
    v4.base.subprocess.check_call([sys.executable, planner])
    path = v4._latest(os.path.join(REPORTS, "*-plan-*.json"))
    if not path:
        raise RuntimeError("PLAN V7 não gerou JSON")
    return path


def _device_related_count(nb, endpoint, device_id):
    return len(v4.base.query(nb, endpoint, device_id=device_id, limit=10000))


def _vm_interfaces(nb, vm_id):
    rows = v4.base.query(nb, "virtualization/interfaces/", limit=10000)
    return [item for item in rows if nested_id(item.get("virtual_machine")) == vm_id]


def _all_macs(nb):
    return v4.base.query(nb, "dcim/mac-addresses/", limit=10000)


def _verify_create_interface_repair(nb, row, tenant_id, site_id):
    repair = row.get("repair") or {}
    required = ("device_id", "vm_id", "ip_id", "vm_mac_address")
    missing = [key for key in required if not repair.get(key)]
    if missing:
        raise RuntimeError("repair create-interface sem campos obrigatórios: {0}".format(
            ",".join(missing)))

    device = nb.get("dcim/devices/{0}/".format(repair["device_id"]))
    vm = nb.get("virtualization/virtual-machines/{0}/".format(repair["vm_id"]))
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

    live_vm_interfaces = _vm_interfaces(nb, repair["vm_id"])
    if live_vm_interfaces:
        raise RuntimeError("VM deixou de possuir zero interfaces: {0}".format(len(live_vm_interfaces)))

    interfaces = v4.base.query(nb, "dcim/interfaces/", device_id=repair["device_id"], limit=1000)
    live_ids = sorted(item.get("id") for item in interfaces if item.get("id"))
    expected_ids = sorted(repair.get("device_interface_ids") or [])
    if live_ids != expected_ids:
        raise RuntimeError("Interfaces do Device mudaram: live={0} expected={1}".format(
            live_ids, expected_ids))
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
    if assignment_type != "dcim.interface" or assignment_id not in set(expected_ids):
        raise RuntimeError("IP não permanece no Device duplicado: {0} ID {1}".format(
            assignment_type or "unassigned", assignment_id))

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
            raise RuntimeError("Device possui objetos relacionados em {0}: {1}".format(
                endpoint, count))

    all_macs = _all_macs(nb)
    live_macs = [
        item for item in all_macs
        if clean(item.get("assigned_object_type")) == "dcim.interface"
        and _assigned_id(item) in set(expected_ids)
    ]
    expected_mac_ids = sorted(repair.get("mac_ids") or [])
    live_mac_ids = sorted(item.get("id") for item in live_macs if item.get("id"))
    if live_mac_ids != expected_mac_ids:
        raise RuntimeError("MACs do Device mudaram: live={0} expected={1}".format(
            live_mac_ids, expected_mac_ids))
    for item in live_macs:
        description = clean(item.get("description"))
        if description and "netbox-discovery" not in description:
            raise RuntimeError("Device possui MAC não criado pelo produto")

    vm_mac = v5.v2.norm_mac(repair.get("vm_mac_address"))
    if not vm_mac:
        raise RuntimeError("MAC VMware inválido")
    matches = [
        item for item in all_macs
        if v5.v2.norm_mac(item.get("mac_address") or item.get("mac")) == vm_mac
    ]
    if len(matches) > 1:
        raise RuntimeError("MAC VMware duplicado no NetBox: {0}".format(vm_mac))
    vm_mac_row = matches[0] if matches else None
    if vm_mac_row:
        assigned_type = clean(vm_mac_row.get("assigned_object_type"))
        assigned_id = _assigned_id(vm_mac_row)
        if assigned_id:
            raise RuntimeError("MAC VMware já pertence a {0} ID {1}".format(
                assigned_type or "outro objeto", assigned_id))
        description = clean(vm_mac_row.get("description"))
        if description and "netbox-discovery" not in description:
            raise RuntimeError("MAC VMware sem vínculo não pertence ao produto")

    return {
        "mode": "FULL_CREATE_VM_INTERFACE",
        "device": device,
        "vm": vm,
        "ip": ip_obj,
        "interfaces": interfaces,
        "macs": live_macs,
        "vm_mac_row": vm_mac_row,
        "vm_mac_address": vm_mac,
    }


def _create_vm_interface_and_mac(nb, row, verified, events, base_execute):
    repair = row.get("repair") or {}

    # Revalidate all non-destructive prerequisites immediately before creating
    # the missing VM interface. Any drift blocks before IP movement/deletion.
    tenant_id = nested_id(verified["device"].get("tenant"))
    site_id = nested_id(verified["device"].get("site"))
    verified = _verify_create_interface_repair(nb, row, tenant_id, site_id)

    interface = nb.post("virtualization/interfaces/", {
        "virtual_machine": repair["vm_id"],
        "name": clean(repair.get("vm_interface_name")) or "MGMT",
        "enabled": True,
        "description": clean(repair.get("vm_interface_description")) or VM_INTERFACE_DESCRIPTION,
    })
    if not interface or not interface.get("id"):
        raise RuntimeError("NetBox não retornou ID da interface criada na VM")
    events.append({
        "phase": "REPAIR", "object_type": "VM_INTERFACE", "action": "CREATED_FOR_REPAIR",
        "name": clean(interface.get("name")), "object_id": interface.get("id"),
        "detail": "VM ID {0}".format(repair.get("vm_id")),
    })

    # Re-read MAC ownership after interface creation and before assignment.
    all_macs = _all_macs(nb)
    vm_mac = verified["vm_mac_address"]
    matches = [
        item for item in all_macs
        if v5.v2.norm_mac(item.get("mac_address") or item.get("mac")) == vm_mac
    ]
    if len(matches) > 1:
        raise RuntimeError("MAC VMware duplicado após criar interface: {0}".format(vm_mac))
    mac_row = matches[0] if matches else None
    if mac_row:
        assigned_type = clean(mac_row.get("assigned_object_type"))
        assigned_id = _assigned_id(mac_row)
        if assigned_id:
            raise RuntimeError("MAC VMware ganhou owner durante reparo: {0} ID {1}".format(
                assigned_type or "outro", assigned_id))
        mac_row = nb.patch("dcim/mac-addresses/{0}/".format(mac_row["id"]), {
            "assigned_object_type": "virtualization.vminterface",
            "assigned_object_id": interface["id"],
            "description": clean(mac_row.get("description")) or VM_MAC_DESCRIPTION,
        })
        mac_action = "ASSIGNED_TO_CREATED_VM_INTERFACE"
    else:
        mac_row = nb.post("dcim/mac-addresses/", {
            "mac_address": vm_mac,
            "assigned_object_type": "virtualization.vminterface",
            "assigned_object_id": interface["id"],
            "description": VM_MAC_DESCRIPTION,
        })
        mac_action = "CREATED_ON_CREATED_VM_INTERFACE"
    if not mac_row or not mac_row.get("id"):
        raise RuntimeError("NetBox não retornou ID do MAC atribuído à VM")

    nb.patch("virtualization/interfaces/{0}/".format(interface["id"]), {
        "primary_mac_address": mac_row["id"],
    })
    events.append({
        "phase": "REPAIR", "object_type": "VM_MAC_ADDRESS", "action": mac_action,
        "name": vm_mac, "object_id": mac_row.get("id"),
        "detail": "VM ID {0} / interface ID {1}".format(
            repair.get("vm_id"), interface.get("id")),
    })

    repair["vm_interface_id"] = interface["id"]
    repair["vm_interface_name"] = clean(interface.get("name"))
    repair["vm_interface_created_id"] = interface["id"]
    verified["vm_interface"] = interface

    # The original finalizer now performs the already-protected IP move,
    # primary-IP assignment, product MAC cleanup and duplicate Device deletion.
    return base_execute(nb, row, verified, events)


def main(argv=None):
    old_refresh = v5.refresh_plan
    old_version = v5.IMPORTER_VERSION
    original_verify = v4._verify_repair
    original_execute = v4._execute_repair
    old_print = builtins.print

    def verify_repair(nb, row, tenant_id, site_id):
        repair = row.get("repair") or {}
        if clean(repair.get("vm_interface_mode")) == "CREATE_SINGLE_VM_INTERFACE":
            return _verify_create_interface_repair(nb, row, tenant_id, site_id)
        return original_verify(nb, row, tenant_id, site_id)

    def execute_repair(nb, row, verified, events):
        repair = row.get("repair") or {}
        if clean(repair.get("vm_interface_mode")) == "CREATE_SINGLE_VM_INTERFACE":
            return _create_vm_interface_and_mac(
                nb, row, verified, events, original_execute)
        return original_execute(nb, row, verified, events)

    def release_print(*args, **kwargs):
        if args and str(args[0]) in (
                "===== IMPORT FINALIZE 1.10.14 =====",
                "===== IMPORT FINALIZE 1.10.15 =====",
                "===== IMPORT FINALIZE 1.10.16 ====="):
            args = ("===== IMPORT FINALIZE 1.10.17 =====",) + tuple(args[1:])
        return old_print(*args, **kwargs)

    try:
        v5.refresh_plan = refresh_plan
        v5.IMPORTER_VERSION = IMPORTER_VERSION
        v4._verify_repair = verify_repair
        v4._execute_repair = execute_repair
        builtins.print = release_print
        return v6.main(argv)
    finally:
        builtins.print = old_print
        v4._verify_repair = original_verify
        v4._execute_repair = original_execute
        v5.refresh_plan = old_refresh
        v5.IMPORTER_VERSION = old_version


if __name__ == "__main__":
    sys.exit(main())
