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

from modules.inventory import planner_v8 as planner_v8
from modules.inventory import planner_v9_core as core

PLANNER_VERSION = "5.1-product"
ORIG_WINDOWS_PLAN_POLICY = core._windows_plan_policy
ORIG_CORE_BUILD_PLAN = core.build_plan
ORIG_V8_GENERIC_MODEL = planner_v8._generic_model

GENERIC_PRINTER_MODELS = {
    "printer-mib managed printer",
    "managed printer",
    "generic printer",
    "unknown printer",
    "printer",
}

# Re-export the public and diagnostic surface of Planner V9 so existing imports,
# tests and commands continue to work while patches remain isolated here.
for _name in dir(core):
    if not _name.startswith("__"):
        globals()[_name] = getattr(core, _name)


def _catalog_rows(value):
    """Return clean catalog rows for both historical dict and live list shapes."""
    if isinstance(value, dict):
        rows = list(value.values())
    elif isinstance(value, list):
        rows = list(value)
    elif value is None:
        rows = []
    else:
        rows = []
    return [dict(row) for row in rows if isinstance(row, dict)]


def _append_unique(rows, candidate, identity_key):
    wanted = identity_key(candidate)
    if not wanted:
        return
    for row in rows:
        if identity_key(row) == wanted:
            return
    rows.append(candidate)


def _generic_model(value):
    low = norm(value)
    return ORIG_V8_GENERIC_MODEL(value) or low in GENERIC_PRINTER_MODELS


def _stable_physical_identity(row, class_row):
    uid = clean(row.get("discovery_uid") or class_row.get("discovery_uid")).upper()
    if uid.startswith("SERIAL:") or "MAC:" in uid:
        return True
    serial = clean(row.get("serial") or class_row.get("serial"))
    serial_confidence = clean(row.get("serial_confidence") or class_row.get("serial_confidence")).upper()
    return bool(serial and serial_confidence in ("HIGH", "MEDIUM"))


def _windows_plan_policy(row, class_row, current):
    """Keep OS separation but do not create a physical Device from weak identity."""
    ORIG_WINDOWS_PLAN_POLICY(row, class_row, current)
    if current:
        return
    if clean(row.get("role")) not in WINDOWS_ROLE_MAP:
        return
    if clean(row.get("decision")) != "READY" or clean(row.get("action")) != "CREATE":
        return
    if _stable_physical_identity(row, class_row):
        return

    row["decision"] = "REVIEW"
    row["action"] = "NOOP"
    reasons = list(row.get("reasons") or [])
    marker = "WINDOWS_NEW_DEVICE_REQUIRES_STABLE_PHYSICAL_IDENTITY"
    if marker not in reasons:
        reasons.append(marker)
    row["reasons"] = sorted(set(reasons))
    row["identity_policy"] = "WINDOWS_EDITION_KNOWN_IDENTITY_NOT_STABLE"
    row["interfaces"] = []
    row["ip_intents"] = []


def _specific_printer_model(row, class_row):
    model = clean(row.get("model") or class_row.get("model"))
    if not model or _generic_model(model):
        return False
    provenance = class_row.get("identity_provenance") or row.get("identity_provenance") or {}
    model_source = norm(provenance.get("model")) if isinstance(provenance, dict) else ""
    if "rejected" in model_source or "generic" in model_source:
        return False
    return True


def _suppress_untrusted_printer_device_type(row, class_row, current):
    if clean(row.get("role")) != "PRINTER":
        return

    specific = _specific_printer_model(row, class_row)
    if not current and clean(row.get("decision")) == "READY" and clean(row.get("action")) == "CREATE":
        if not specific:
            row["decision"] = "REVIEW"
            row["action"] = "NOOP"
            row["interfaces"] = []
            row["ip_intents"] = []
            reasons = list(row.get("reasons") or [])
            marker = "PRINTER_NEW_DEVICE_REQUIRES_SPECIFIC_MODEL"
            if marker not in reasons:
                reasons.append(marker)
            row["reasons"] = sorted(set(reasons))
            row["identity_policy"] = "PRINTER_MODEL_NOT_SPECIFIC"
        return

    if specific:
        return

    kept = []
    suppressed = list(row.get("suppressed_diffs") or [])
    for diff in row.get("safe_diffs") or []:
        if clean(diff).startswith("device_type:SET:"):
            if diff not in suppressed:
                suppressed.append(diff)
            continue
        kept.append(diff)
    row["safe_diffs"] = kept
    if suppressed:
        row["suppressed_diffs"] = suppressed
        row["device_type_write_suppressed"] = "PRINTER_MODEL_NOT_SPECIFIC"
        row["reasons"] = [
            reason for reason in (row.get("reasons") or [])
            if clean(reason) != "PRODUCT_GENERIC_DEVICE_TYPE_UPGRADE"
            and not clean(reason).startswith("DEVICE_TYPE_DRIFT:")
        ]
        if clean(row.get("action")) == "UPDATE_SAFE" and not kept:
            row["action"] = "NOOP"
            row["identity_policy"] = "PRINTER_GENERIC_DEVICE_TYPE_SUPPRESSED"


def _new_physical_identity_policy(row, class_row, current):
    if current:
        return
    if clean(row.get("decision")) != "READY" or clean(row.get("action")) != "CREATE":
        return
    if clean(row.get("asset_class")) != "PHYSICAL_DEVICE":
        return
    if clean(row.get("role")) in WINDOWS_ROLE_MAP:
        return
    if _stable_physical_identity(row, class_row):
        return
    uid = clean(row.get("discovery_uid") or class_row.get("discovery_uid")).upper()
    if not uid.startswith("WEAK:"):
        return

    row["decision"] = "REVIEW"
    row["action"] = "NOOP"
    row["interfaces"] = []
    row["ip_intents"] = []
    reasons = list(row.get("reasons") or [])
    marker = "NEW_PHYSICAL_DEVICE_REQUIRES_STABLE_IDENTITY"
    if marker not in reasons:
        reasons.append(marker)
    row["reasons"] = sorted(set(reasons))
    row["identity_policy"] = "PHYSICAL_IDENTITY_NOT_STABLE"


def _fix_windows_prerequisites(plan, prereq, state):
    """Normalize prerequisite catalogs after the base planner serializes them."""
    if not isinstance(prereq, dict):
        raise RuntimeError("PLAN prerequisites inválido: esperado objeto")

    roles = _catalog_rows(prereq.get("roles"))
    device_types = _catalog_rows(prereq.get("device_types"))

    roles = [
        row for row in roles
        if clean(row.get("name")) not in WINDOWS_ROLE_MAP
    ]
    device_types = [
        row for row in device_types
        if norm(row.get("model")) not in (
            "generic windows server", "generic windows workstation"
        )
    ]

    live_roles = set(
        norm(item.get("name"))
        for item in (state.get("roles") or [])
        if isinstance(item, dict) and norm(item.get("name"))
    )
    live_types = set(
        (norm(nested_name(item.get("manufacturer"))), norm(item.get("model")))
        for item in (state.get("device_types") or [])
        if isinstance(item, dict)
    )

    for row in plan or []:
        if not isinstance(row, dict):
            continue
        decision = clean(row.get("decision"))
        if decision and decision != "READY":
            continue
        role = clean(row.get("role"))
        if role not in WINDOWS_ROLE_MAP:
            continue
        target_role, target_model = WINDOWS_ROLE_MAP[role]

        if norm(target_role) not in live_roles:
            _append_unique(
                roles,
                {"name": target_role, "slug": slugify(target_role)},
                lambda item: norm(item.get("name")),
            )

        manufacturer = clean(row.get("manufacturer")) or "Generic"
        type_key = (norm(manufacturer), norm(target_model))
        if type_key not in live_types:
            _append_unique(
                device_types,
                {
                    "manufacturer": manufacturer,
                    "model": target_model,
                    "slug": slugify(manufacturer + "-" + target_model),
                },
                lambda item: (
                    norm(nested_name(item.get("manufacturer"))),
                    norm(item.get("model")),
                ),
            )

    prereq["roles"] = sorted(roles, key=lambda item: (norm(item.get("name")), norm(item.get("slug"))))
    prereq["device_types"] = sorted(
        device_types,
        key=lambda item: (
            norm(nested_name(item.get("manufacturer"))),
            norm(item.get("model")),
            norm(item.get("slug")),
        ),
    )


def _ready_prerequisite_keys(plan):
    needed = {
        "roles": set(),
        "manufacturers": set(),
        "platforms": set(),
        "device_types": set(),
    }
    for row in plan or []:
        if clean(row.get("decision")) != "READY":
            continue
        action = clean(row.get("action"))
        if action == "CREATE":
            role = clean(row.get("target_role"))
            manufacturer = clean(row.get("manufacturer"))
            model = clean(row.get("model"))
            platform = clean(row.get("platform"))
            if role:
                needed["roles"].add(norm(role))
            if manufacturer:
                needed["manufacturers"].add(norm(manufacturer))
            if manufacturer and model:
                needed["device_types"].add((norm(manufacturer), norm(model)))
            if platform:
                needed["platforms"].add(norm(platform))
        elif action == "UPDATE_SAFE":
            for diff in row.get("safe_diffs") or []:
                text = clean(diff)
                if text.startswith("role:SET:"):
                    needed["roles"].add(norm(text.split(":", 2)[2]))
                elif text.startswith("platform:SET:"):
                    needed["platforms"].add(norm(text.split(":", 2)[2]))
                elif text.startswith("device_type:SET:"):
                    payload = text.split(":", 2)[2]
                    if "|" in payload:
                        manufacturer, model = payload.split("|", 1)
                        needed["manufacturers"].add(norm(manufacturer))
                        needed["device_types"].add((norm(manufacturer), norm(model)))
    return needed


def _prune_prerequisites_to_ready_actions(plan, prereq):
    if not isinstance(prereq, dict):
        return
    needed = _ready_prerequisite_keys(plan)

    prereq["roles"] = [
        row for row in _catalog_rows(prereq.get("roles"))
        if norm(row.get("name")) in needed["roles"]
    ]
    prereq["manufacturers"] = [
        row for row in _catalog_rows(prereq.get("manufacturers"))
        if norm(row.get("name")) in needed["manufacturers"]
    ]
    prereq["platforms"] = [
        row for row in _catalog_rows(prereq.get("platforms"))
        if norm(row.get("name")) in needed["platforms"]
    ]
    prereq["device_types"] = [
        row for row in _catalog_rows(prereq.get("device_types"))
        if (
            norm(nested_name(row.get("manufacturer"))),
            norm(row.get("model")),
        ) in needed["device_types"]
        and norm(row.get("model")) not in GENERIC_PRINTER_MODELS
    ]

    for category in ("roles", "manufacturers", "platforms", "device_types"):
        prereq[category] = sorted(
            prereq.get(category) or [],
            key=lambda item: repr(sorted(item.items())),
        )


def build_plan(recon, classification, state):
    old_generic = planner_v8._generic_model
    try:
        planner_v8._generic_model = _generic_model
        plan, prereq = ORIG_CORE_BUILD_PLAN(recon, classification, state)
    finally:
        planner_v8._generic_model = old_generic

    by_ip = core._classification_by_ip(classification)
    devices = core._device_by_id(state)
    for row in plan or []:
        ip = core.norm_ip(row.get("primary_ip"))
        class_row = by_ip.get(ip) or {}
        current = devices.get(row.get("existing_device_id")) if row.get("existing_device_id") else None
        _suppress_untrusted_printer_device_type(row, class_row, current)
        _new_physical_identity_policy(row, class_row, current)

    _prune_prerequisites_to_ready_actions(plan, prereq)
    core._apply_write_guard(plan, state)
    return plan, prereq


core._windows_plan_policy = _windows_plan_policy
core._fix_windows_prerequisites = _fix_windows_prerequisites
core.PLANNER_VERSION = PLANNER_VERSION


def main(argv=None):
    old_build = core.build_plan
    core._windows_plan_policy = _windows_plan_policy
    core._fix_windows_prerequisites = _fix_windows_prerequisites
    core.PLANNER_VERSION = PLANNER_VERSION
    core.build_plan = build_plan
    try:
        return core.main(argv)
    finally:
        core.build_plan = old_build


if __name__ == "__main__":
    raise SystemExit(main())
