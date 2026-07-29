#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, "..", ".."))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.inventory import planner_v7 as v7

PLANNER_VERSION = "4.8-product"
PRODUCT_DEVICE_DESCRIPTION = "Criado pelo netbox-discovery"
ORIG_BUILD_PLAN = v7.build_plan


def clean(value):
    return "" if value is None else str(value).strip()


def norm(value):
    return re.sub(r"\s+", " ", clean(value)).strip().casefold()


def nested_name(value):
    if isinstance(value, dict):
        return clean(value.get("name") or value.get("display") or value.get("model"))
    return clean(value)


def _canonical_manufacturer(value):
    low = norm(value)
    aliases = {
        "dell inc.": "dell", "dell inc": "dell", "dell technologies": "dell", "dell emc": "dell",
        "ubiquiti networks": "ubiquiti", "ubiquiti inc.": "ubiquiti", "ubiquiti inc": "ubiquiti",
        "hewlett packard enterprise": "hpe aruba", "aruba networks": "hpe aruba",
        "kyocera document solutions": "kyocera", "kyocera mita": "kyocera",
        "hewlett-packard": "hp", "hp inc.": "hp", "hp inc": "hp",
    }
    return aliases.get(low, low)


def _generic_model(value):
    low = norm(value)
    if not low:
        return True
    markers = (
        "generic ", "unknown server", "generic unknown", "unknown dell server",
        "generic printer", "generic wireless", "generic network", "industrial device",
        "industrial switch", "generic storage",
    )
    return any(low == marker.strip() or low.startswith(marker) for marker in markers)


def _current_device(state, device_id):
    return next((item for item in (state.get("devices") or []) if item.get("id") == device_id), None)


def _current_identity(device):
    dtype = device.get("device_type") or {}
    manufacturer = nested_name(dtype.get("manufacturer") if isinstance(dtype, dict) else "")
    model = clean(dtype.get("model") if isinstance(dtype, dict) else "")
    return {
        "name": clean(device.get("name")),
        "role": nested_name(device.get("role")),
        "manufacturer": manufacturer,
        "model": model,
        "platform": nested_name(device.get("platform")),
    }


def _strong_match(row):
    reason = clean(row.get("match_reason")).upper()
    return any(token in reason for token in ("SERIAL", "MAC", "IP"))


def _safe_reason_set(row, allowed_prefixes):
    for reason in row.get("reasons") or []:
        if not any(clean(reason).startswith(prefix) for prefix in allowed_prefixes):
            return False
    return True


def _append_reason(row, reason):
    values = list(row.get("reasons") or [])
    if reason not in values:
        values.append(reason)
    row["reasons"] = sorted(set(values))


def _remove_reason_prefixes(row, prefixes):
    row["reasons"] = [
        reason for reason in (row.get("reasons") or [])
        if not any(clean(reason).startswith(prefix) for prefix in prefixes)
    ]


def _apply_manufacturer_alias(row, current):
    identity = _current_identity(current)
    if not identity["manufacturer"] or not identity["model"]:
        return
    if norm(identity["model"]) != norm(row.get("model")):
        return
    if _canonical_manufacturer(identity["manufacturer"]) != _canonical_manufacturer(row.get("manufacturer")):
        return
    row["manufacturer"] = identity["manufacturer"]
    _remove_reason_prefixes(row, ("DEVICE_TYPE_DRIFT:",))
    row["manufacturer_alias_matched"] = True


def _preserve_strong_live_identity(row, current):
    if not current or not _strong_match(row):
        return False
    identity = _current_identity(current)
    if _generic_model(identity["model"]) or not identity["role"]:
        return False
    weak_observation = clean(row.get("confidence")) != "HIGH" or _generic_model(row.get("model"))
    if not weak_observation:
        return False
    allowed = ("CONFIDENCE_", "UNKNOWN_ROLE", "ROLE_DRIFT:", "PLATFORM_DRIFT:", "DEVICE_TYPE_DRIFT:")
    if not _safe_reason_set(row, allowed):
        return False

    row["decision"] = "READY"
    row["action"] = "NOOP"
    row["desired_name"] = identity["name"] or row.get("desired_name")
    row["target_role"] = identity["role"]
    row["manufacturer"] = identity["manufacturer"] or row.get("manufacturer")
    row["model"] = identity["model"] or row.get("model")
    row["platform"] = identity["platform"] or row.get("platform")
    row["safe_diffs"] = []
    row["reasons"] = ["LIVE_IDENTITY_PRESERVED_OVER_WEAK_OBSERVATION"]
    row["identity_policy"] = "PRESERVE_STRONG_LIVE"
    return True


def _safe_generic_type_upgrade(row, current):
    if not current or clean(current.get("description")) != PRODUCT_DEVICE_DESCRIPTION:
        return False
    if not _strong_match(row) or clean(row.get("confidence")) != "HIGH":
        return False
    identity = _current_identity(current)
    desired_model = clean(row.get("model"))
    desired_mfg = clean(row.get("manufacturer"))
    if not _generic_model(identity["model"]) or _generic_model(desired_model):
        return False
    if not desired_mfg or norm(desired_mfg) in ("generic", "unidentified"):
        return False
    allowed = ("DEVICE_TYPE_DRIFT:",)
    if not _safe_reason_set(row, allowed):
        return False

    _remove_reason_prefixes(row, ("DEVICE_TYPE_DRIFT:",))
    diff = "device_type:SET:{0}|{1}".format(desired_mfg, desired_model)
    diffs = list(row.get("safe_diffs") or [])
    if diff not in diffs:
        diffs.append(diff)
    row["safe_diffs"] = diffs
    row["decision"] = "READY"
    row["action"] = "UPDATE_SAFE"
    _append_reason(row, "PRODUCT_GENERIC_DEVICE_TYPE_UPGRADE")
    row["identity_policy"] = "UPGRADE_PRODUCT_GENERIC_TYPE"
    return True


def _identity_suffix(asset):
    serial = re.sub(r"[^A-Za-z0-9]", "", clean(asset.get("serial"))).upper()
    if len(serial) >= 4:
        return serial[-6:]
    macs = []
    for value in asset.get("macs") or []:
        compact = re.sub(r"[^0-9A-Fa-f]", "", clean(value)).upper()
        if len(compact) == 12:
            macs.append(compact)
    if len(set(macs)) == 1:
        return macs[0][-6:]
    return ""


def _resolve_strong_name_collisions(plan, assets, state):
    groups = defaultdict(list)
    for row in plan:
        groups[norm(row.get("desired_name"))].append(row)
    live_names = set(norm(item.get("name")) for item in (state.get("devices") or []) if norm(item.get("name")))

    for key, rows in groups.items():
        if not key or len(rows) < 2:
            continue
        prepared = []
        for row in rows:
            asset = assets.get(clean(row.get("asset_id"))) or {}
            reasons = set(row.get("reasons") or [])
            allowed = {"DUPLICATE_DESIRED_NAME", "RECONCILE_REVIEW_CANDIDATE"}
            if not reasons or not reasons.issubset(allowed):
                prepared = []
                break
            if row.get("existing_device_id") or clean(row.get("confidence")) != "HIGH":
                prepared = []
                break
            if clean(asset.get("asset_class")) != "PHYSICAL_DEVICE":
                prepared = []
                break
            suffix = _identity_suffix(asset)
            if not suffix:
                prepared = []
                break
            new_name = (clean(row.get("desired_name")) + "-" + suffix)[:64]
            prepared.append((row, new_name, suffix))
        candidate_names = [norm(item[1]) for item in prepared]
        if not prepared or len(set(candidate_names)) != len(prepared):
            continue
        if any(name in live_names for name in candidate_names):
            continue
        for row, new_name, suffix in prepared:
            row["desired_name"] = new_name
            row["decision"] = "READY"
            row["action"] = "CREATE"
            row["reasons"] = ["COLLISION_SAFE_NAME_FROM_STRONG_IDENTITY"]
            row["match_state"] = "NEW"
            row["match_reason"] = "Nome SNMP repetido; identidade física forte preservada com sufixo {0}".format(suffix)
            row["identity_policy"] = "COLLISION_SAFE_NAME"


def build_plan(recon, classification, state):
    plan, prereq = ORIG_BUILD_PLAN(recon, classification, state)
    assets = dict((clean(item.get("asset_id")), item) for item in (recon.get("records") or []))

    _resolve_strong_name_collisions(plan, assets, state)

    for row in plan:
        current = _current_device(state, row.get("existing_device_id")) if row.get("existing_device_id") else None
        if current:
            _apply_manufacturer_alias(row, current)
            if _preserve_strong_live_identity(row, current):
                continue
            _safe_generic_type_upgrade(row, current)

    return plan, prereq


def main(argv=None):
    old_build = v7.build_plan
    old_version = v7.PLANNER_VERSION
    try:
        v7.build_plan = build_plan
        v7.PLANNER_VERSION = PLANNER_VERSION
        return v7.main(argv)
    finally:
        v7.build_plan = old_build
        v7.PLANNER_VERSION = old_version


if __name__ == "__main__":
    sys.exit(main())
