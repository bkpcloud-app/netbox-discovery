#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import copy
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, "..", ".."))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.inventory import planner_v4 as v4
from modules.inventory import planner_v5 as v5

PLANNER_VERSION = "4.7-product"
VM_INTERFACE_NAME = "MGMT"
VM_INTERFACE_DESCRIPTION = "Descoberto pelo netbox-discovery hypervisor"


def clean(value):
    return "" if value is None else str(value).strip()


def _assigned_id(row):
    assigned = row.get("assigned_object") or {}
    if isinstance(assigned, dict) and assigned.get("id"):
        return assigned.get("id")
    return row.get("assigned_object_id")


def _strong_vmware_macs(asset):
    return sorted(set(
        v4.norm_mac(value) for value in (asset.get("macs") or [])
        if v5._is_vmware_mac(value)
    ))


def _global_mac_state(live_state, vm_mac, allowed_interface_id=None):
    matches = [
        item for item in (live_state.get("macs") or [])
        if v4.norm_mac(item.get("mac_address") or item.get("mac")) == vm_mac
    ]
    if len(matches) > 1:
        return None, "MAC VMware duplicado globalmente: {0}".format(vm_mac)
    existing_mac_id = None
    if matches:
        existing = matches[0]
        assigned_type = clean(existing.get("assigned_object_type"))
        assigned_id = _assigned_id(existing)
        if assigned_id:
            if assigned_type != "virtualization.vminterface" or assigned_id != allowed_interface_id:
                return None, "MAC VMware pertence a outro objeto: {0} ID {1}".format(
                    assigned_type or "outro", assigned_id)
        existing_mac_id = existing.get("id")
    return existing_mac_id, ""


def _synthetic_interface(vm_id, interface_id, vm_mac, mac_id):
    return {
        "id": interface_id,
        "name": VM_INTERFACE_NAME,
        "virtual_machine": {"id": vm_id},
        "enabled": True,
        "description": VM_INTERFACE_DESCRIPTION,
        "primary_mac_address": {
            "id": mac_id or "PLANNED:VM-MAC:{0}".format(vm_mac),
            "mac_address": vm_mac,
        },
        "mac_addresses": [],
    }


def _repair_candidate(row, asset, vm, live_state, original_candidate, classification_rows):
    enriched = v5._enrich_asset_vmware_identity(asset, classification_rows)
    repair, error = original_candidate(row, enriched, vm, live_state)
    if repair or clean(error) != "Interface da VM por MAC não é única: 0":
        return repair, error

    strong_macs = _strong_vmware_macs(enriched)
    if len(strong_macs) != 1:
        return None, "Fallback exige exatamente um MAC VMware forte: {0}".format(len(strong_macs))
    vm_mac = strong_macs[0]

    vm_interfaces = v4._vm_interfaces(live_state, vm.get("id"))
    if len(vm_interfaces) == 1:
        target = vm_interfaces[0]
        target_live_macs = v4._vm_interface_macs(target, live_state)
        if target_live_macs:
            return None, "Interface única da VM já possui MAC diferente: {0}".format(
                ",".join(sorted(target_live_macs)))
        existing_mac_id, mac_error = _global_mac_state(live_state, vm_mac, target.get("id"))
        if mac_error:
            return None, mac_error

        synthetic_state = copy.deepcopy(live_state)
        synthetic_interfaces = []
        for item in synthetic_state.get("vm_interfaces") or []:
            current = item
            if item.get("id") == target.get("id"):
                current = dict(item)
                current["primary_mac_address"] = {
                    "id": existing_mac_id or "PLANNED:VM-MAC:{0}".format(vm_mac),
                    "mac_address": vm_mac,
                }
            synthetic_interfaces.append(current)
        synthetic_state["vm_interfaces"] = synthetic_interfaces

        repair, error = original_candidate(row, enriched, vm, synthetic_state)
        if not repair:
            return None, error
        repair["vm_mac_mode"] = "ENSURE_SINGLE_VM_INTERFACE"
        repair["vm_mac_address"] = vm_mac
        repair["vm_mac_existing_id"] = existing_mac_id
        repair["vm_interface_count"] = 1
        repair["vm_mac_evidence"] = "VM única por nome + uma interface sem MAC + VMware MAC forte"
        return repair, ""

    if len(vm_interfaces) != 0:
        return None, "Fallback exige zero ou uma interface na VM: {0}".format(len(vm_interfaces))

    existing_mac_id, mac_error = _global_mac_state(live_state, vm_mac, None)
    if mac_error:
        return None, mac_error

    planned_interface_id = "PLANNED:VM-INTERFACE:{0}".format(vm.get("id"))
    synthetic_state = copy.deepcopy(live_state)
    synthetic_state["vm_interfaces"] = list(synthetic_state.get("vm_interfaces") or []) + [
        _synthetic_interface(vm.get("id"), planned_interface_id, vm_mac, existing_mac_id)
    ]

    repair, error = original_candidate(row, enriched, vm, synthetic_state)
    if not repair:
        return None, error

    repair["vm_interface_mode"] = "CREATE_SINGLE_VM_INTERFACE"
    repair["vm_interface_id"] = planned_interface_id
    repair["vm_interface_name"] = VM_INTERFACE_NAME
    repair["vm_interface_description"] = VM_INTERFACE_DESCRIPTION
    repair["vm_mac_mode"] = "ENSURE_CREATED_VM_INTERFACE"
    repair["vm_mac_address"] = vm_mac
    repair["vm_mac_existing_id"] = existing_mac_id
    repair["vm_interface_count"] = 0
    repair["vm_mac_evidence"] = "VM única por nome + zero interfaces + VMware MAC forte"
    return repair, ""


def build_plan(recon, classification, state):
    classification_rows = v5._classification_by_ip(classification)
    original_candidate = v4._repair_candidate
    original_version = v4.PLANNER_VERSION

    def repair_candidate(row, asset, vm, live_state):
        return _repair_candidate(
            row, asset, vm, live_state, original_candidate, classification_rows)

    try:
        v4._repair_candidate = repair_candidate
        v4.PLANNER_VERSION = PLANNER_VERSION
        return v4.build_plan(recon, classification, state)
    finally:
        v4._repair_candidate = original_candidate
        v4.PLANNER_VERSION = original_version


def main(argv=None):
    old_state = v4.v3.netbox_state
    old_build = v4.v3.build_plan
    old_version = v4.v3.PLANNER_VERSION
    try:
        v4.v3.netbox_state = v4.netbox_state
        v4.v3.build_plan = build_plan
        v4.v3.PLANNER_VERSION = PLANNER_VERSION
        return v4.v3.main(argv)
    finally:
        v4.v3.netbox_state = old_state
        v4.v3.build_plan = old_build
        v4.v3.PLANNER_VERSION = old_version


if __name__ == "__main__":
    sys.exit(main())
