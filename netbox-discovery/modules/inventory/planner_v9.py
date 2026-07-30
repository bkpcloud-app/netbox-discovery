#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, "..", ".."))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.inventory import planner_v8 as v8
from modules.product import identity

PLANNER_VERSION = "4.9-product"
ORIG_BUILD_PLAN = v8.build_plan


def clean(value):
    return "" if value is None else str(value).strip()


def norm(value):
    return re.sub(r"\s+", " ", clean(value)).strip().casefold()


def norm_ip(value):
    return clean(value).split("/", 1)[0]


def nested_id(value):
    if isinstance(value, dict):
        return value.get("id")
    if isinstance(value, int):
        return value
    return None


def nested_name(value):
    if isinstance(value, dict):
        return clean(value.get("name") or value.get("display") or value.get("model"))
    return clean(value)


def _classification_by_ip(classification):
    return dict(
        (norm_ip(row.get("ip")), row)
        for row in (classification.get("records") or [])
        if norm_ip(row.get("ip"))
    )


def _asset_by_id(recon):
    return dict(
        (clean(row.get("asset_id")), row)
        for row in (recon.get("records") or [])
        if clean(row.get("asset_id"))
    )


def _device_by_id(state):
    return dict((row.get("id"), row) for row in (state.get("devices") or []) if row.get("id") is not None)


def _vm_by_id(state):
    rows = list(state.get("virtual_machines") or [])
    rows.extend(state.get("virtual_machines_global") or [])
    return dict((row.get("id"), row) for row in rows if row.get("id") is not None)


def _vm_interface_by_id(state):
    return dict((row.get("id"), row) for row in (state.get("vm_interfaces") or []) if row.get("id") is not None)


def _assigned_id(row):
    assigned = row.get("assigned_object") or {}
    if isinstance(assigned, dict) and assigned.get("id") is not None:
        return assigned.get("id")
    return row.get("assigned_object_id")


def _vm_interface_macs(interface, state):
    values = []
    primary = interface.get("primary_mac_address") or {}
    if isinstance(primary, dict):
        mac = identity.norm_mac(primary.get("mac_address") or primary.get("mac"))
        if mac:
            values.append(mac)
    for item in interface.get("mac_addresses") or []:
        if isinstance(item, dict):
            mac = identity.norm_mac(item.get("mac_address") or item.get("mac"))
            if mac and mac not in values:
                values.append(mac)
    iid = interface.get("id")
    for item in state.get("macs") or []:
        if clean(item.get("assigned_object_type")) != "virtualization.vminterface":
            continue
        if _assigned_id(item) != iid:
            continue
        mac = identity.norm_mac(item.get("mac_address") or item.get("mac"))
        if mac and mac not in values:
            values.append(mac)
    return values


def _nested_vm_reference(interface):
    value = interface.get("virtual_machine") or {}
    if isinstance(value, dict) and value.get("id") is not None:
        return dict(value)
    if isinstance(value, int):
        return {"id": value, "name": "VM-ID-{0}".format(value)}
    return {}


def _find_vm_target(row, state):
    ip = norm_ip(row.get("primary_ip"))
    ifaces = _vm_interface_by_id(state)
    vms = _vm_by_id(state)
    ip_matches = [
        item for item in (state.get("ips") or [])
        if norm_ip(item.get("address")) == ip
        and clean(item.get("assigned_object_type")) == "virtualization.vminterface"
    ]
    if len(ip_matches) == 1:
        ip_obj = ip_matches[0]
        assigned = ip_obj.get("assigned_object") or {}
        interface = ifaces.get(_assigned_id(ip_obj)) or (dict(assigned) if isinstance(assigned, dict) else {})
        vm_ref = _nested_vm_reference(interface)
        vm = vms.get(nested_id(vm_ref)) or vm_ref
        if vm:
            source = "ip-vminterface-owner" if nested_id(vm_ref) in vms else "ip-vminterface-owner-partial"
            return vm, interface, ip_obj, source

    ids = []
    for reason in row.get("reasons") or []:
        match = re.search(r"(?:VM_NAME|HYPERVISOR_VM_NAME):([0-9]+)", clean(reason))
        if match:
            ids.append(int(match.group(1)))
    match = re.search(r"VM ID\s+([0-9]+)", clean(row.get("match_reason")), re.I)
    if match:
        ids.append(int(match.group(1)))
    ids = sorted(set(ids))
    if len(ids) == 1 and ids[0] in vms:
        vm = vms[ids[0]]
        candidates = [
            item for item in (state.get("vm_interfaces") or [])
            if nested_id(item.get("virtual_machine")) == vm.get("id")
        ]
        interface = candidates[0] if len(candidates) == 1 else {}
        return vm, interface, {}, "unique-vm-name"
    return {}, {}, {}, ""


def _delegated_details(row, state):
    vm, interface, ip_obj, source = _find_vm_target(row, state)
    if not vm:
        row["delegation_status"] = "UNRESOLVED_DETAILS"
        row["delegation_source"] = "centralized-hypervisor"
        return
    device = vm.get("device") or vm.get("host") or {}
    complete = bool(clean(vm.get("name")) and (vm.get("cluster") or vm.get("site") or device))
    row["delegation_status"] = "PASS" if complete else "PASS_PARTIAL"
    row["delegation_source"] = "centralized-hypervisor"
    row["delegated_target"] = {
        "source": source,
        "vm_id": vm.get("id"),
        "vm_name": clean(vm.get("name")),
        "interface_id": interface.get("id"),
        "interface_name": clean(interface.get("name")),
        "interface_macs": _vm_interface_macs(interface, state) if interface else [],
        "ip_id": ip_obj.get("id"),
        "ip_address": clean(ip_obj.get("address")),
        "site": nested_name(vm.get("site")),
        "cluster": nested_name(vm.get("cluster")),
        "physical_host": nested_name(device),
        "tenant": nested_name(vm.get("tenant")),
        "details_complete": complete,
    }
    row["identity_policy"] = "CENTRALIZED_HYPERVISOR_AUTHORITY"


def _protect_existing_name(row, devices):
    device_id = row.get("existing_device_id")
    if not device_id:
        row.setdefault("name_authority", "DISCOVERY_NEW_OBJECT")
        return
    current = devices.get(device_id) or {}
    live_name = clean(current.get("name"))
    if live_name:
        row["desired_name"] = live_name
    row["name_authority"] = "NETBOX_EXISTING"
    row["name_write_allowed"] = False
    row["safe_diffs"] = [
        diff for diff in (row.get("safe_diffs") or [])
        if not clean(diff).startswith("name:")
    ]


def _attach_observed_identity(row, class_row):
    row["observed_name"] = clean(class_row.get("observed_name") or class_row.get("hostname"))
    row["observed_name_source"] = clean(class_row.get("observed_name_source") or class_row.get("hostname_source"))
    row["discovery_uid"] = clean(class_row.get("discovery_uid"))
    row["asset_nature"] = clean(class_row.get("asset_nature"))
    row["asset_nature_source"] = clean(class_row.get("asset_nature_source"))
    row["identity_provenance"] = class_row.get("identity_provenance") or {}
    row["review_recommendations"] = list(class_row.get("review_recommendations") or [])
    if row.get("existing_device_id"):
        row["effective_name"] = clean(row.get("desired_name"))
    else:
        row["effective_name"] = clean(row.get("desired_name") or row.get("observed_name"))


def _virtual_candidate_guard(row, class_row):
    if clean(class_row.get("asset_nature")) != "VIRTUAL_CANDIDATE":
        return
    if clean(row.get("decision")) == "DELEGATED":
        return
    if row.get("existing_device_id"):
        return
    if clean(row.get("decision")) == "READY" and clean(row.get("action")) == "CREATE":
        row["decision"] = "REVIEW"
        row["action"] = "NOOP"
        reasons = list(row.get("reasons") or [])
        marker = "VIRTUAL_CANDIDATE_REQUIRES_CENTRAL_INVENTORY_MATCH"
        if marker not in reasons:
            reasons.append(marker)
        row["reasons"] = sorted(set(reasons))
        row["identity_policy"] = "DO_NOT_CREATE_DEVICE_FOR_UNCONFIRMED_VM"
        row["interfaces"] = []
        row["ip_intents"] = []


def _serial_index(state):
    out = {}
    for device in state.get("devices") or []:
        serial = identity.norm_serial(device.get("serial"))
        if serial:
            out.setdefault(serial, []).append(device)
    return out


def _oob_parent_guard(row, class_row, serial_index):
    if clean(row.get("role")) != "OOB_MANAGEMENT":
        return
    serial = identity.norm_serial(row.get("serial") or class_row.get("serial"))
    if not serial:
        name = clean(row.get("observed_name") or row.get("desired_name"))
        match = re.search(r"iDRAC[-_]?([A-Za-z0-9-]+)", name, re.I)
        if match:
            serial = identity.norm_serial(match.group(1))
    matches = serial_index.get(serial, []) if serial else []
    matches = [item for item in matches if item.get("id") != row.get("existing_device_id")]
    if len(matches) != 1:
        return
    parent = matches[0]
    row["oob_parent_candidate"] = {
        "device_id": parent.get("id"),
        "device_name": clean(parent.get("name")),
        "serial": serial,
        "match": "service-tag",
    }
    if not row.get("existing_device_id") and clean(row.get("decision")) == "READY":
        row["decision"] = "REVIEW"
        row["action"] = "NOOP"
        row["interfaces"] = []
        row["ip_intents"] = []
        row["reasons"] = ["OOB_MANAGEMENT_SHOULD_ATTACH_TO_PHYSICAL_PARENT"]
        row["identity_policy"] = "OOB_PARENT_REVIEW"


def _limit(name, default):
    raw = clean(os.environ.get(name))
    if not raw:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default


def _apply_write_guard(plan, state):
    limits = {
        "CREATE": _limit("NETBOX_DISCOVERY_MAX_CREATE", 25),
        "UPDATE_SAFE": _limit("NETBOX_DISCOVERY_MAX_UPDATE", 50),
        "REPAIR_SAFE_VM_DUPLICATE": _limit("NETBOX_DISCOVERY_MAX_REPAIR", 20),
        "TOTAL": _limit("NETBOX_DISCOVERY_MAX_TOTAL_CHANGES", 75),
        "PERCENT": _limit("NETBOX_DISCOVERY_MAX_CHANGE_PERCENT", 20),
    }
    eligible = [
        row for row in plan
        if clean(row.get("decision")) == "READY"
        and clean(row.get("action")) in ("CREATE", "UPDATE_SAFE", "REPAIR_SAFE_VM_DUPLICATE")
    ]
    counts = Counter(clean(row.get("action")) for row in eligible)
    live_count = max(1, len(state.get("devices") or []))
    percent = int(round((100.0 * len(eligible)) / live_count))
    violations = []
    for action in ("CREATE", "UPDATE_SAFE", "REPAIR_SAFE_VM_DUPLICATE"):
        if counts.get(action, 0) > limits[action]:
            violations.append("{0}={1}>{2}".format(action, counts[action], limits[action]))
    if len(eligible) > limits["TOTAL"]:
        violations.append("TOTAL={0}>{1}".format(len(eligible), limits["TOTAL"]))
    if percent > limits["PERCENT"] and len(eligible) > 10:
        violations.append("PERCENT={0}%>{1}%".format(percent, limits["PERCENT"]))
    guard = {
        "status": "BLOCK" if violations else "PASS",
        "counts": dict(counts),
        "eligible_total": len(eligible),
        "live_devices": live_count,
        "change_percent": percent,
        "limits": limits,
        "violations": violations,
    }
    for row in plan:
        row["write_guard"] = guard
    if not violations:
        return
    reason = "WRITE_GUARD_LIMIT_EXCEEDED:{0}".format(",".join(violations))
    for row in eligible:
        row["decision"] = "BLOCKED"
        row["action"] = "NOOP"
        row["reasons"] = [reason]
        row["interfaces"] = []
        row["ip_intents"] = []
        row.pop("repair", None)
        row["identity_policy"] = "GLOBAL_WRITE_GUARD"


def build_plan(recon, classification, state):
    plan, prereq = ORIG_BUILD_PLAN(recon, classification, state)
    by_ip = _classification_by_ip(classification)
    assets = _asset_by_id(recon)
    devices = _device_by_id(state)
    serials = _serial_index(state)

    for row in plan:
        ip = norm_ip(row.get("primary_ip"))
        class_row = by_ip.get(ip) or {}
        asset = assets.get(clean(row.get("asset_id"))) or {}

        _protect_existing_name(row, devices)
        _attach_observed_identity(row, class_row)
        _virtual_candidate_guard(row, class_row)
        _oob_parent_guard(row, class_row, serials)

        if clean(row.get("decision")) == "DELEGATED":
            _delegated_details(row, state)

        if not clean(row.get("discovery_uid")):
            row["discovery_uid"] = clean(asset.get("discovery_uid"))
        if not clean(row.get("asset_nature")):
            row["asset_nature"] = clean(asset.get("asset_nature"))

    _apply_write_guard(plan, state)
    return plan, prereq


def main(argv=None):
    old_build = v8.build_plan
    old_version = v8.PLANNER_VERSION
    try:
        v8.build_plan = build_plan
        v8.PLANNER_VERSION = PLANNER_VERSION
        return v8.main(argv)
    finally:
        v8.build_plan = old_build
        v8.PLANNER_VERSION = old_version


if __name__ == "__main__":
    sys.exit(main())
