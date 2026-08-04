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

from modules.inventory import planner_v7 as v7
from modules.inventory import planner_v8 as v8
from modules.inventory import planner_v9 as v9
from modules.inventory import planner_v9_core as core
from modules.product import identity

PLANNER_VERSION = "5.2-product"
ORIG_BUILD_PLAN = v9.build_plan
PRODUCT_DEVICE_DESCRIPTION = "Criado pelo netbox-discovery"
WINDOWS_ROLE_CANONICAL = {
    "WINDOWS_SERVER": "SERVER-WINDOWS",
    "SERVER-WINDOWS": "SERVER-WINDOWS",
    "WINDOWS_WORKSTATION": "WORKSTATION-WINDOWS",
    "WORKSTATION-WINDOWS": "WORKSTATION-WINDOWS",
}


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


def canonical_windows_role(value):
    raw = clean(value).upper()
    return WINDOWS_ROLE_CANONICAL.get(raw, clean(value))


def _assigned_id(row):
    assigned = row.get("assigned_object") or {}
    if isinstance(assigned, dict) and assigned.get("id") is not None:
        return assigned.get("id")
    return row.get("assigned_object_id")


def _device_from_ip(state, ip):
    address = norm_ip(ip)
    matches = [
        item for item in (state.get("ips") or [])
        if norm_ip(item.get("address")) == address
    ]
    if len(matches) != 1:
        return None
    row = matches[0]
    if clean(row.get("assigned_object_type")) != "dcim.interface":
        return None
    assigned = row.get("assigned_object") or {}
    if isinstance(assigned, dict):
        device = assigned.get("device") or {}
        did = nested_id(device)
        if did:
            return did
    interface_id = _assigned_id(row)
    if not interface_id:
        return None
    for interface in state.get("interfaces") or []:
        if interface.get("id") == interface_id:
            return nested_id(interface.get("device"))
    return None


def _device_type_parts(device):
    dtype = device.get("device_type") or {}
    if not isinstance(dtype, dict):
        return "", ""
    manufacturer = nested_name(dtype.get("manufacturer"))
    model = clean(dtype.get("model") or dtype.get("display") or dtype.get("name"))
    return manufacturer, model


def _manufacturer_equivalent(left, right):
    canonical = getattr(v8, "_canonical_manufacturer", None)
    if callable(canonical):
        return canonical(left) == canonical(right)
    return norm(left) == norm(right)


def _device_matches_row(device, row, state):
    expected_serial = identity.norm_serial(row.get("serial"))
    live_serial = identity.norm_serial(device.get("serial"))
    if not expected_serial or live_serial != expected_serial:
        return False

    ips = [norm_ip(value) for value in (row.get("ips") or []) if norm_ip(value)]
    if not ips and norm_ip(row.get("primary_ip")):
        ips = [norm_ip(row.get("primary_ip"))]
    if not ips or any(_device_from_ip(state, ip) != device.get("id") for ip in ips):
        return False

    live_role = nested_name(device.get("role"))
    expected_role = clean(row.get("target_role") or row.get("role"))
    if canonical_windows_role(live_role) != canonical_windows_role(expected_role):
        if norm(live_role) != norm(expected_role):
            return False

    live_manufacturer, live_model = _device_type_parts(device)
    expected_manufacturer = clean(row.get("manufacturer"))
    expected_model = clean(row.get("model"))
    if expected_model and norm(live_model) != norm(expected_model):
        return False
    if expected_manufacturer and not _manufacturer_equivalent(live_manufacturer, expected_manufacturer):
        return False

    live_platform = nested_name(device.get("platform"))
    expected_platform = clean(row.get("platform"))
    if expected_platform and norm(live_platform) != norm(expected_platform):
        return False
    return True


def _recover_collision_created_devices(plan, state):
    serial_index = {}
    for device in state.get("devices") or []:
        serial = identity.norm_serial(device.get("serial"))
        if serial:
            serial_index.setdefault(serial, []).append(device)

    for row in plan or []:
        if row.get("existing_device_id"):
            continue
        if clean(row.get("decision")) != "BLOCKED":
            continue
        reasons = set(clean(reason) for reason in (row.get("reasons") or []))
        if "DUPLICATE_DESIRED_NAME" not in reasons:
            continue

        serial = identity.norm_serial(row.get("serial"))
        candidates = serial_index.get(serial, []) if serial else []
        if len(candidates) != 1:
            continue
        device = candidates[0]
        if clean(device.get("description")) != PRODUCT_DEVICE_DESCRIPTION:
            continue
        suffix = serial[-6:] if len(serial) >= 6 else serial
        live_name = clean(device.get("name"))
        if not suffix or not live_name.upper().endswith("-" + suffix.upper()):
            continue
        if not _device_matches_row(device, row, state):
            continue

        row["suppressed_reasons"] = list(row.get("reasons") or [])
        row["existing_device_id"] = device.get("id")
        row["desired_name"] = live_name
        row["effective_name"] = live_name
        row["name_authority"] = "NETBOX_EXISTING"
        row["name_write_allowed"] = False
        row["decision"] = "READY"
        row["action"] = "NOOP"
        row["safe_diffs"] = []
        row["match_state"] = "MATCHED"
        row["match_reason"] = "Serial/IP confirmam Device de colisão já criado"
        row["reasons"] = ["POST_CREATE_COLLISION_IDENTITY_MATCHED"]
        row["identity_policy"] = "COLLISION_SAFE_EXISTING_MATCH"
        for intent in row.get("ip_intents") or []:
            intent["action"] = "NOOP"


def _normalize_windows_role_aliases(plan, state):
    devices = dict(
        (item.get("id"), item)
        for item in (state.get("devices") or [])
        if item.get("id") is not None
    )
    for row in plan or []:
        role = clean(row.get("target_role") or row.get("role"))
        canonical = canonical_windows_role(role)
        if canonical not in ("SERVER-WINDOWS", "WORKSTATION-WINDOWS"):
            continue
        row["canonical_target_role"] = canonical
        if not row.get("existing_device_id"):
            row["target_role"] = canonical
            continue

        current = devices.get(row.get("existing_device_id")) or {}
        current_role = nested_name(current.get("role"))
        if canonical_windows_role(current_role) != canonical:
            row["target_role"] = canonical
            continue

        kept = []
        for diff in row.get("safe_diffs") or []:
            text = clean(diff)
            if text.startswith("role:SET:"):
                target = clean(text.split(":", 2)[2])
                if canonical_windows_role(target) == canonical:
                    continue
            kept.append(diff)
        row["safe_diffs"] = kept
        row["target_role"] = current_role or canonical
        row["legacy_role_alias_preserved"] = bool(
            current_role and norm(current_role) != norm(canonical)
        )
        row["reasons"] = [
            reason for reason in (row.get("reasons") or [])
            if not clean(reason).startswith("ROLE_DRIFT:")
        ]
        if clean(row.get("action")) == "UPDATE_SAFE" and not kept:
            row["action"] = "NOOP"
            row["identity_policy"] = "WINDOWS_ROLE_ALIAS_EQUIVALENT"


def _attach_idempotency_identity(plan):
    for row in plan or []:
        row["idempotency_identity"] = {
            "asset_id": clean(row.get("asset_id")),
            "serial": identity.norm_serial(row.get("serial")),
            "primary_ip": norm_ip(row.get("primary_ip")),
            "existing_device_id": row.get("existing_device_id"),
            "discovery_uid": clean(row.get("discovery_uid")),
        }


def build_plan(recon, classification, state):
    plan, prereq = ORIG_BUILD_PLAN(recon, classification, state)
    _recover_collision_created_devices(plan, state)
    _normalize_windows_role_aliases(plan, state)
    _attach_idempotency_identity(plan)
    v9._prune_prerequisites_to_ready_actions(plan, prereq)
    core._apply_write_guard(plan, state)
    return plan, prereq


def main(argv=None):
    old_build = v9.build_plan
    version_targets = (v9, core, v8, v7)
    old_versions = [getattr(module, "PLANNER_VERSION", "") for module in version_targets]
    try:
        v9.build_plan = build_plan
        for module in version_targets:
            module.PLANNER_VERSION = PLANNER_VERSION
        return v9.main(argv)
    finally:
        v9.build_plan = old_build
        for module, value in zip(version_targets, old_versions):
            module.PLANNER_VERSION = value


if __name__ == "__main__":
    raise SystemExit(main())
