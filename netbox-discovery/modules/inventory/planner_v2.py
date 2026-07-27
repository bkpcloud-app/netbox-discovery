#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("NETBOX_DISCOVERY_BASE", os.path.abspath(os.path.join(HERE, "..", "..")))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import planner as base

PLANNER_VERSION = "4.1-product"
ORIG_NETBOX_STATE = base.netbox_state
ORIG_BUILD_INDEXES = base.build_indexes
ORIG_MATCH_ASSET = base.match_asset
ORIG_DESIRED_INTERFACES = base.desired_interfaces
ORIG_FALLBACK_MODEL = base.fallback_model
ORIG_BUILD_PLAN = base.build_plan

VMWARE_MAC_PREFIXES = (
    "00:05:69",
    "00:0C:29",
    "00:1C:14",
    "00:50:56",
)


def norm_mac(value):
    compact = re.sub(r"[^0-9A-Fa-f]", "", base.clean(value)).upper()
    if len(compact) != 12 or compact in ("000000000000", "FFFFFFFFFFFF"):
        return ""
    try:
        first = int(compact[:2], 16)
    except ValueError:
        return ""
    if first & 1:
        return ""
    return ":".join(compact[i:i + 2] for i in range(0, 12, 2))


def netbox_state(nb, client, site):
    state = ORIG_NETBOX_STATE(nb, client, site)
    try:
        state["macs"] = base.query(nb, "dcim/mac-addresses/", limit=10000)
    except Exception:
        state["macs"] = []
    try:
        state["interfaces"] = base.query(nb, "dcim/interfaces/", limit=10000)
    except Exception:
        state["interfaces"] = []
    return state


def build_indexes(state):
    indexes = ORIG_BUILD_INDEXES(state)
    interface_device = {}
    for iface in state.get("interfaces") or []:
        device = iface.get("device") or {}
        did = device.get("id") if isinstance(device, dict) else None
        iid = iface.get("id")
        if iid and did:
            interface_device[iid] = did

    mac_to_devices = {}
    for row in state.get("macs") or []:
        mac = norm_mac(row.get("mac_address") or row.get("mac"))
        if not mac:
            continue
        assigned = row.get("assigned_object") or {}
        did = None
        if isinstance(assigned, dict):
            device = assigned.get("device") or {}
            if isinstance(device, dict):
                did = device.get("id")
            if not did and row.get("assigned_object_type") == "dcim.interface":
                iid = assigned.get("id") or row.get("assigned_object_id")
                did = interface_device.get(iid)
        if did:
            mac_to_devices.setdefault(mac, set()).add(did)
    indexes["mac_to_devices"] = mac_to_devices
    return indexes


def match_asset(asset, indexes, desired_name=None, allow_name_match=True):
    votes = []
    serial = base.norm_serial(asset.get("serial"))
    if serial:
        ids = set(indexes["serials"].get(serial, []))
        if ids:
            votes.append(("SERIAL", ids))

    mac_ids = set()
    for raw in asset.get("macs") or []:
        mac = norm_mac(raw)
        mac_ids.update(indexes.get("mac_to_devices", {}).get(mac, set()))
    if mac_ids:
        votes.append(("MAC", mac_ids))

    ip_ids = set()
    for ip in (asset.get("ips") or []) + (asset.get("oob_ips") or []):
        ip_ids.update(indexes["ip_to_devices"].get(base.norm_ip(ip), set()))
    if ip_ids:
        votes.append(("IP", ip_ids))

    name = base.norm(desired_name if desired_name is not None else base.canonical_name(asset))
    if name and allow_name_match:
        ids = set(indexes["names"].get(name, []))
        if ids:
            votes.append(("NAME", ids))

    strong_sets = [ids for method, ids in votes if method in ("SERIAL", "MAC", "IP")]
    strong = set()
    for ids in strong_sets:
        strong.update(ids)

    if len(strong) > 1:
        return None, "CONFLICT", "SERIAL/MAC/IP apontam para devices diferentes", votes
    if len(strong) == 1:
        did = list(strong)[0]
        if did not in indexes["by_id"]:
            return None, "CONFLICT", "identidade forte aponta para device fora do tenant/site", votes
        conflicting_name = [ids for method, ids in votes if method == "NAME" and did not in ids]
        if conflicting_name:
            return None, "CONFLICT", "Nome aponta para outro device", votes
        return did, "MATCHED", "+".join(method for method, ids in votes if did in ids), votes

    all_ids = set()
    for method, ids in votes:
        all_ids.update(ids)
    if len(all_ids) == 1:
        return list(all_ids)[0], "MATCHED", "NAME", votes
    if len(all_ids) > 1:
        return None, "CONFLICT", "Nome ambíguo", votes
    return None, "NEW", "Sem correspondência", votes


def desired_interfaces(asset, classification_records):
    rows = ORIG_DESIRED_INTERFACES(asset, classification_records)
    by_ip = dict((base.norm_ip(row.get("ip")), row) for row in classification_records)
    for spec in rows:
        rec = by_ip.get(base.norm_ip(spec.get("ip"))) or {}
        mac = norm_mac(rec.get("management_mac"))
        if mac:
            spec["mac"] = mac
            spec["mac_source"] = base.clean(rec.get("management_mac_source"))
    return rows


def fallback_model(asset):
    role = base.clean(asset.get("role"))
    if role == "TIME_ATTENDANCE":
        return base.clean(asset.get("model")) or "Generic Time Attendance Device"
    if role == "ACCESS_CONTROL":
        return base.clean(asset.get("model")) or "Generic Access Control Device"
    if role == "TURNSTILE":
        return base.clean(asset.get("model")) or "Generic Turnstile"
    return ORIG_FALLBACK_MODEL(asset)


def _ip_objects_by_address(state):
    out = {}
    for obj in state.get("ips") or []:
        ip = base.norm_ip(obj.get("address"))
        if ip:
            out.setdefault(ip, []).append(obj)
    return out


def _all_ips_owned_by_vm(row, ip_objects):
    ips = [base.norm_ip(x) for x in row.get("ips") or [] if base.norm_ip(x)]
    if not ips:
        return False
    for ip in ips:
        objects = ip_objects.get(ip) or []
        if not objects:
            return False
        for obj in objects:
            if base.clean(obj.get("assigned_object_type")) != "virtualization.vminterface":
                return False
    return True


def _looks_like_vm_asset(asset):
    if base.clean(asset.get("asset_class")) == "VIRTUAL_MACHINE_CANDIDATE":
        return True
    for raw in asset.get("macs") or []:
        mac = norm_mac(raw)
        if mac and any(mac.startswith(prefix) for prefix in VMWARE_MAC_PREFIXES):
            return True
    return False


def build_plan(recon, classification, state):
    """Post-process the conservative base PLAN with cross-pipeline ownership.

    A network-discovered IP already assigned to a NetBox VM interface belongs to
    the Hypervisor inventory pipeline. It must not become a physical Device and
    it should not remain noisy REVIEW work for Network.
    """
    plan, prereq = ORIG_BUILD_PLAN(recon, classification, state)
    assets = dict((base.clean(x.get("asset_id")), x) for x in (recon.get("records") or []))
    ip_objects = _ip_objects_by_address(state)

    for row in plan:
        asset = assets.get(base.clean(row.get("asset_id"))) or {}
        row["asset_class"] = base.clean(asset.get("asset_class"))

        if not row.get("existing_device_id") and _all_ips_owned_by_vm(row, ip_objects):
            row["suppressed_reasons"] = list(row.get("reasons") or [])
            row["decision"] = "DELEGATED"
            row["action"] = "NOOP"
            row["match_state"] = "EXTERNAL_MANAGED"
            row["match_reason"] = "IP(s) já vinculado(s) a virtualization.vminterface"
            row["reasons"] = ["OWNED_BY_HYPERVISOR_VM"]
            row["interfaces"] = []
            row["ip_intents"] = []
            continue

        if (not row.get("existing_device_id") and _looks_like_vm_asset(asset)
                and row.get("decision") != "BLOCKED"):
            row["decision"] = "REVIEW"
            reasons = list(row.get("reasons") or [])
            reasons.append("VIRTUAL_MACHINE_CANDIDATE_NO_VM_MATCH")
            row["reasons"] = sorted(set(reasons))

    return plan, prereq


def main(argv=None):
    old_state = base.netbox_state
    old_indexes = base.build_indexes
    old_match = base.match_asset
    old_interfaces = base.desired_interfaces
    old_fallback = base.fallback_model
    old_build_plan = base.build_plan
    old_version = base.PLANNER_VERSION
    old_targets = dict(base.ROLE_TARGETS)
    try:
        base.netbox_state = netbox_state
        base.build_indexes = build_indexes
        base.match_asset = match_asset
        base.desired_interfaces = desired_interfaces
        base.fallback_model = fallback_model
        base.build_plan = build_plan
        base.PLANNER_VERSION = PLANNER_VERSION
        base.ROLE_TARGETS.update({
            "TIME_ATTENDANCE": "TIME ATTENDANCE",
            "ACCESS_CONTROL": "ACCESS CONTROL",
            "TURNSTILE": "TURNSTILE",
        })
        return base.main(argv)
    finally:
        base.netbox_state = old_state
        base.build_indexes = old_indexes
        base.match_asset = old_match
        base.desired_interfaces = old_interfaces
        base.fallback_model = old_fallback
        base.build_plan = old_build_plan
        base.PLANNER_VERSION = old_version
        base.ROLE_TARGETS.clear()
        base.ROLE_TARGETS.update(old_targets)


if __name__ == "__main__":
    sys.exit(main())
