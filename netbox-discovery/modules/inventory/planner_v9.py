#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, "..", ".."))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.inventory import planner_v9_core as core

PLANNER_VERSION = "5.0.3-product"
ORIG_WINDOWS_PLAN_POLICY = core._windows_plan_policy

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
        if clean(row.get("decision")) != "READY":
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


core._windows_plan_policy = _windows_plan_policy
core._fix_windows_prerequisites = _fix_windows_prerequisites
core.PLANNER_VERSION = PLANNER_VERSION


def main(argv=None):
    core._windows_plan_policy = _windows_plan_policy
    core._fix_windows_prerequisites = _fix_windows_prerequisites
    core.PLANNER_VERSION = PLANNER_VERSION
    return core.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())