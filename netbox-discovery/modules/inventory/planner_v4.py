#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, "..", ".."))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.inventory import planner_v2 as v2
from modules.inventory import planner_v3 as v3

PLANNER_VERSION = "4.4-product"
ORIG_NETBOX_STATE = v3.netbox_state
ORIG_BUILD_PLAN = v3.build_plan
PRODUCT_DEVICE_DESCRIPTION = "Criado pelo netbox-discovery"
PRODUCT_INTERFACE_DESCRIPTION = "Gerenciamento criado pelo netbox-discovery"
PRODUCT_IP_DESCRIPTION = "Importado pelo netbox-discovery"


def clean(value):
    return "" if value is None else str(value).strip()


def nested_id(value):
    if isinstance(value, dict):
        return value.get("id")
    if isinstance(value, int):
        return value
    return None


def norm_mac(value):
    compact = re.sub(r"[^0-9A-Fa-f]", "", clean(value)).upper()
    if len(compact) != 12 or compact in ("000000000000", "FFFFFFFFFFFF"):
        return ""
    return ":".join(compact[i:i + 2] for i in range(0, 12, 2))


def _required_query(nb, endpoint):
    return v2.base.query(nb, endpoint, limit=10000)


def netbox_state(nb, client, site):
    state = ORIG_NETBOX_STATE(nb, client, site)
    state["vm_interfaces"] = _required_query(nb, "virtualization/interfaces/")
    state["inventory_items"] = _required_query(nb, "dcim/inventory-items/")
    state["console_ports"] = _required_query(nb, "dcim/console-ports/")
    state["console_server_ports"] = _required_query(nb, "dcim/console-server-ports/")
    state["power_ports"] = _required_query(nb, "dcim/power-ports/")
    state["power_outlets"] = _required_query(nb, "dcim/power-outlets/")
    state["front_ports"] = _required_query(nb, "dcim/front-ports/")
    state["rear_ports"] = _required_query(nb, "dcim/rear-ports/")
    state["device_bays"] = _required_query(nb, "dcim/device-bays/")
    state["module_bays"] = _required_query(nb, "dcim/module-bays/")
    return state


def _owner_id(row, field):
    return nested_id(row.get(field) or {})


def _device_interfaces(state, device_id):
    return [row for row in (state.get("interfaces") or []) if _owner_id(row, "device") == device_id]


def _vm_interfaces(state, vm_id):
    return [row for row in (state.get("vm_interfaces") or []) if _owner_id(row, "virtual_machine") == vm_id]


def _assigned_id(row):
    assigned = row.get("assigned_object") or {}
    if isinstance(assigned, dict) and assigned.get("id"):
        return assigned.get("id")
    return row.get("assigned_object_id")


def _rows_for_interface_ids(rows, interface_ids, assigned_type):
    wanted = set(interface_ids)
    return [
        row for row in (rows or [])
        if clean(row.get("assigned_object_type")) == assigned_type and _assigned_id(row) in wanted
    ]


def _vm_interface_macs(row, state):
    values = []
    primary = row.get("primary_mac_address") or {}
    if isinstance(primary, dict):
        values.append(norm_mac(primary.get("mac_address") or primary.get("mac")))
    for item in row.get("mac_addresses") or []:
        if isinstance(item, dict):
            values.append(norm_mac(item.get("mac_address") or item.get("mac")))
    iid = row.get("id")
    for item in state.get("macs") or []:
        if clean(item.get("assigned_object_type")) == "virtualization.vminterface" and _assigned_id(item) == iid:
            values.append(norm_mac(item.get("mac_address") or item.get("mac")))
    return set(value for value in values if value)


def _device_has_related_objects(state, device_id):
    checks = (
        ("inventory_items", "device"),
        ("console_ports", "device"),
        ("console_server_ports", "device"),
        ("power_ports", "device"),
        ("power_outlets", "device"),
        ("front_ports", "device"),
        ("rear_ports", "device"),
        ("device_bays", "device"),
        ("module_bays", "device"),
    )
    found = []
    for collection, field in checks:
        count = sum(1 for row in (state.get(collection) or []) if _owner_id(row, field) == device_id)
        if count:
            found.append("{0}={1}".format(collection, count))
    return found


def _device_scope_is_empty(device):
    fields = ("rack", "location", "cluster", "virtual_chassis", "device_bay")
    return not any(nested_id(device.get(field)) for field in fields)


def _repair_candidate(row, asset, vm, state):
    device_id = row.get("existing_device_id")
    device = next((item for item in (state.get("devices") or []) if item.get("id") == device_id), None)
    if not device:
        return None, "Device não existe mais"
    if clean(device.get("description")) != PRODUCT_DEVICE_DESCRIPTION:
        return None, "Device não foi criado pelo netbox-discovery"
    if clean(device.get("serial")):
        return None, "Device possui serial"
    if not _device_scope_is_empty(device):
        return None, "Device possui rack/location/cluster/virtual chassis/device bay"

    related = _device_has_related_objects(state, device_id)
    if related:
        return None, "Device possui objetos relacionados: {0}".format(", ".join(related))

    interfaces = _device_interfaces(state, device_id)
    if not interfaces:
        return None, "Device sem interface criada pelo produto"
    if any(clean(item.get("description")) != PRODUCT_INTERFACE_DESCRIPTION for item in interfaces):
        return None, "Device possui interface não criada pelo produto"
    if any(item.get("cable") or item.get("mark_connected") for item in interfaces):
        return None, "Device possui cabo/conexão manual"

    interface_ids = [item.get("id") for item in interfaces if item.get("id")]
    expected_ips = sorted(set(v2.base.norm_ip(ip) for ip in (asset.get("ips") or []) if v2.base.norm_ip(ip)))
    if len(expected_ips) != 1:
        return None, "Reparo automático exige exatamente um IP descoberto"

    asset_macs = set(norm_mac(value) for value in (asset.get("macs") or []) if norm_mac(value))
    if not asset_macs:
        return None, "Asset sem MAC VMware forte"
    vm_interfaces = _vm_interfaces(state, vm.get("id"))
    matches = [item for item in vm_interfaces if _vm_interface_macs(item, state) & asset_macs]
    if len(matches) != 1:
        return None, "Interface da VM por MAC não é única: {0}".format(len(matches))
    target_interface = matches[0]

    ip_matches = [
        item for item in (state.get("ips") or [])
        if v2.base.norm_ip(item.get("address")) == expected_ips[0]
    ]
    if len(ip_matches) != 1:
        return None, "IP global não é único: {0}".format(len(ip_matches))
    ip_obj = ip_matches[0]
    if clean(ip_obj.get("description")) != PRODUCT_IP_DESCRIPTION:
        return None, "IP não foi criado pelo produto"

    assignment_type = clean(ip_obj.get("assigned_object_type"))
    assignment_id = _assigned_id(ip_obj)
    if assignment_type == "dcim.interface" and assignment_id in set(interface_ids):
        repair_mode = "FULL"
    elif assignment_type == "virtualization.vminterface" and assignment_id == target_interface.get("id"):
        repair_mode = "RECOVERY_AFTER_IP_MOVE"
    else:
        return None, "IP pertence a outro objeto: {0} ID {1}".format(assignment_type or "unassigned", assignment_id)

    live_device_ips = _rows_for_interface_ids(state.get("ips"), interface_ids, "dcim.interface")
    live_device_ip_values = sorted(set(v2.base.norm_ip(item.get("address")) for item in live_device_ips if v2.base.norm_ip(item.get("address"))))
    expected_device_values = expected_ips if repair_mode == "FULL" else []
    if live_device_ip_values != expected_device_values:
        return None, "IPs remanescentes do Device divergem: live={0} expected={1}".format(live_device_ip_values, expected_device_values)

    mac_rows = _rows_for_interface_ids(state.get("macs"), interface_ids, "dcim.interface")
    for item in mac_rows:
        description = clean(item.get("description"))
        if description and "netbox-discovery" not in description:
            return None, "Device possui MAC não criado pelo produto"

    vm_site_id = nested_id(vm.get("site"))
    site_id = nested_id(state.get("site"))
    if vm_site_id and site_id and vm_site_id != site_id:
        return None, "VM está em outro Site"
    if nested_id(vm.get("tenant")) not in (None, nested_id(state.get("tenant"))):
        return None, "VM está em outro Tenant"
    current_primary_id = nested_id(vm.get("primary_ip4") or vm.get("primary_ip") or {})
    if current_primary_id not in (None, ip_obj.get("id")):
        return None, "VM já possui outro primary IPv4"

    return {
        "mode": repair_mode,
        "device_id": device_id,
        "device_name": clean(device.get("name")),
        "vm_id": vm.get("id"),
        "vm_name": clean(vm.get("name")),
        "vm_interface_id": target_interface.get("id"),
        "vm_interface_name": clean(target_interface.get("name")),
        "device_interface_ids": interface_ids,
        "ip_id": ip_obj.get("id"),
        "ip_address": clean(ip_obj.get("address")),
        "mac_ids": [item.get("id") for item in mac_rows if item.get("id")],
        "expected_device_description": PRODUCT_DEVICE_DESCRIPTION,
        "expected_interface_description": PRODUCT_INTERFACE_DESCRIPTION,
        "expected_ip_description": PRODUCT_IP_DESCRIPTION,
    }, ""


def _append_reason(row, reason):
    reasons = list(row.get("reasons") or [])
    if reason not in reasons:
        reasons.append(reason)
    row["reasons"] = sorted(set(reasons))


def build_plan(recon, classification, state):
    plan, prereq = ORIG_BUILD_PLAN(recon, classification, state)
    assets = dict((clean(item.get("asset_id")), item) for item in (recon.get("records") or []))
    vm_names = v3._vm_name_index(state)

    for row in plan:
        if clean(row.get("decision")) != "BLOCKED" or not row.get("existing_device_id"):
            continue
        asset = assets.get(clean(row.get("asset_id"))) or {}
        if not v2._looks_like_vm_asset(asset):
            continue
        matches = v3._unique_vm_matches(asset, row, vm_names)
        if len(matches) != 1:
            continue
        repair, error = _repair_candidate(row, asset, matches[0], state)
        if not repair:
            _append_reason(row, "REPAIR_SAFE_NOT_ELIGIBLE:{0}".format(error))
            continue

        row["decision"] = "READY"
        row["action"] = "REPAIR_SAFE_VM_DUPLICATE"
        row["match_state"] = "REPAIR_SAFE"
        row["match_reason"] = "Device criado pelo produto duplica VM inequívoca; IP será transferido e Device removido"
        row["reasons"] = ["PRODUCT_CREATED_DEVICE_DUPLICATES_VM"]
        row["repair"] = repair
        row["interfaces"] = []
        row["ip_intents"] = []

    return plan, prereq


def main(argv=None):
    old_state = v3.netbox_state
    old_build = v3.build_plan
    old_version = v3.PLANNER_VERSION
    try:
        v3.netbox_state = netbox_state
        v3.build_plan = build_plan
        v3.PLANNER_VERSION = PLANNER_VERSION
        return v3.main(argv)
    finally:
        v3.netbox_state = old_state
        v3.build_plan = old_build
        v3.PLANNER_VERSION = old_version


if __name__ == "__main__":
    sys.exit(main())
