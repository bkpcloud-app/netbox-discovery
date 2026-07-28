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


def clean(value):
    return "" if value is None else str(value).strip()


def _assigned_id(row):
    assigned = row.get("assigned_object") or {}
    if isinstance(assigned, dict) and assigned.get("id"):
        return assigned.get("id")
    return row.get("assigned_object_id")


def _vm_interface_fallback(row, asset, vm, live_state, original_candidate, classification_rows):
    """Safely complete VM duplicate repair when VM interface inventory is incomplete.

    Supported live states:
    - one VM interface without MAC: ensure the MAC on that interface;
    - zero VM interfaces: plan creation of exactly one product-owned interface,
      then ensure the MAC before IP movement and duplicate Device deletion.

    Any ambiguity (multiple interfaces, multiple VMware MACs, globally-owned MAC)
    remains BLOCKED.
    """
    enriched = v5._enrich_asset_vmware_identity(asset, classification_rows)
    repair, error = original_candidate(row, enriched, vm, live_state)
    if repair or clean(error) != "Interface da VM por MAC não é única: 0":
        return repair, error

    strong_macs = sorted(set(
        v4.norm_mac(value) for value in (enriched.get("macs") or [])
        if v5._is_vmware_mac(value)
    ))
    if len(strong_macs) != 1:
        return None, "Fallback de interface VM exige exatamente um MAC VMware forte: {0}".format(len(strong_macs))
    vm_mac = strong_macs[0]

    vm_interfaces = v4._vm_interfaces(live_state, vm.get("id"))
    if len(vm_interfaces) > 1:
        return None, "Fallback de interface VM exige no máximo uma interface na VM: {0}".format(len(vm_interfaces))

    global_matches = [
        item for item in (live_state.get("macs") or [])
        if v4.norm_mac(item.get("mac_address") or item.get("mac")) == vm_mac
    ]
    if len(global_matches) > 1:
        return None, "MAC VMware duplicado globalmente: {0}".format(vm_mac)
    existing_mac_id = None

    if vm_interfaces:
        target = vm_interfaces[0]
        target_live_macs = v4._vm_interface_macs(target, live_state)
        if target_live_macs:
            return None, "Interface única da VM já possui MAC diferente: {0}".format(
                ",".join(sorted(target_live_macs)))
        interface_mode = "PRESERVE_SINGLE_VM_INTERFACE"
        mac_mode = "ENSURE_SINGLE_VM_INTERFACE"
        evidence = "VM única por nome + uma interface sem MAC + VMware MAC forte"
    else:
        target = {
            "id": "PLANNED:VM-INTERFACE:{0}".format(vm.get("id")),
            "virtual_machine": {"id": vm.get("id")},
            "name": "Network adapter 1",
            "enabled": True,
            "description": "Descoberto pelo netbox-discovery hypervisor",
            "primary_mac_address": None,
            "mac_addresses": [],
        }
        interface_mode = "CREATE_MISSING_VM_INTERFACE"
        mac_mode = "ENSURE_CREATED_VM_INTERFACE"
        evidence = "VM única por nome + zero interfaces + VMware MAC forte; criar interface antes do reparo"

    if global_matches:
        existing = global_matches[0]
        assigned_type = clean(existing.get("assigned_object_type"))
        assigned_id = _assigned_id(existing)
        target_id = target.get("id")
        if assigned_id and (assigned_type != "virtualization.vminterface" or assigned_id != target_id):
            return None, "MAC VMware pertence a outro objeto: {0} ID {1}".format(
                assigned_type or "outro", assigned_id)
        existing_mac_id = existing.get("id")

    synthetic_state = copy.deepcopy(live_state)
    synthetic_interfaces = list(synthetic_state.get("vm_interfaces") or [])
    found = False
    for pos, item in enumerate(synthetic_interfaces):
        if item.get("id") == target.get("id"):
            current = dict(item)
            current["primary_mac_address"] = {
                "id": existing_mac_id or "PLANNED:VM-MAC:{0}".format(vm_mac),
                "mac_address": vm_mac,
            }
            synthetic_interfaces[pos] = current
            target = current
            found = True
            break
    if not found:
        current = dict(target)
        current["primary_mac_address"] = {
            "id": existing_mac_id or "PLANNED:VM-MAC:{0}".format(vm_mac),
            "mac_address": vm_mac,
        }
        synthetic_interfaces.append(current)
        target = current
    synthetic_state["vm_interfaces"] = synthetic_interfaces

    repair, error = original_candidate(row, enriched, vm, synthetic_state)
    if not repair:
        return None, error

    repair["vm_interface_mode"] = interface_mode
    repair["vm_interface_planned_name"] = clean(target.get("name")) or "Network adapter 1"
    repair["vm_mac_mode"] = mac_mode
    repair["vm_mac_address"] = vm_mac
    repair["vm_mac_existing_id"] = existing_mac_id
    repair["vm_interface_count"] = len(vm_interfaces)
    repair["vm_mac_evidence"] = evidence
    return repair, ""


def build_plan(recon, classification, state):
    classification_rows = v5._classification_by_ip(classification)
    original_candidate = v4._repair_candidate
    original_version = v4.PLANNER_VERSION

    def repair_candidate(row, asset, vm, live_state):
        return _vm_interface_fallback(
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
