#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, "..", ".."))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.auditors import inventory as base
from modules.auditors import auditor_v2 as v2
from modules.auditors import auditor_v3 as v3
from modules.auditors import auditor_v4 as v4
from modules.auditors import auditor_v5 as v5
from modules.auditors import auditor_v6 as v6
from modules.auditors import auditor_v7 as v7
from modules.auditors import auditor_v8 as v8
from modules.auditors import auditor_v9 as v9

AUDITOR_VERSION = "6.8-product"
WINDOWS_ROLE_CANONICAL = {
    "WINDOWS_SERVER": "SERVER-WINDOWS",
    "SERVER-WINDOWS": "SERVER-WINDOWS",
    "WINDOWS_WORKSTATION": "WORKSTATION-WINDOWS",
    "WORKSTATION-WINDOWS": "WORKSTATION-WINDOWS",
}


def clean(value):
    return "" if value is None else str(value).strip()


def canonical_windows_role(value):
    raw = clean(value).upper()
    return WINDOWS_ROLE_CANONICAL.get(raw, clean(value))


def stable_plan_key(row):
    return (
        clean(row.get("asset_id")),
        base.norm_ip(row.get("primary_ip")),
    )


def _unique_index(rows, key_function):
    index = {}
    duplicates = set()
    for row in rows:
        key = key_function(row)
        if not key or key in ("", ("", "")):
            continue
        if key in index:
            duplicates.add(key)
        else:
            index[key] = row
    for key in duplicates:
        index.pop(key, None)
    return index


def _resolve_fresh_row(original, fresh_rows, indexes):
    key = stable_plan_key(original)
    current = indexes["stable"].get(key)
    if current:
        return current, "asset_id+primary_ip"

    serial = base.norm_serial(original.get("serial"))
    if serial:
        current = indexes["serial"].get(serial)
        if current:
            return current, "serial"

    asset_id = clean(original.get("asset_id"))
    if asset_id:
        current = indexes["asset"].get(asset_id)
        if current:
            return current, "asset_id"

    primary_ip = base.norm_ip(original.get("primary_ip"))
    if primary_ip:
        current = indexes["ip"].get(primary_ip)
        if current:
            return current, "primary_ip"
    return None, ""


def audit_idempotency(original_ready, fresh_plan, checks):
    fresh_rows = list(fresh_plan.get("records") or [])
    indexes = {
        "stable": _unique_index(fresh_rows, stable_plan_key),
        "serial": _unique_index(fresh_rows, lambda row: base.norm_serial(row.get("serial"))),
        "asset": _unique_index(fresh_rows, lambda row: clean(row.get("asset_id"))),
        "ip": _unique_index(fresh_rows, lambda row: base.norm_ip(row.get("primary_ip"))),
    }

    for original in original_ready:
        aid = clean(original.get("asset_id"))
        label = clean(original.get("desired_name"))
        current, matched_by = _resolve_fresh_row(original, fresh_rows, indexes)
        if not current:
            base.add_check(
                checks, "FAIL", "IDEMPOTENCY_ASSET_MISSING", aid, label,
                "stable_key={0}".format(stable_plan_key(original)))
            continue
        if clean(current.get("decision")) != "READY":
            base.add_check(
                checks, "FAIL", "IDEMPOTENCY_NOT_READY", aid, label,
                "matched_by={0}; decision={1}; reasons={2}".format(
                    matched_by, clean(current.get("decision")),
                    " | ".join(current.get("reasons") or [])))
            continue
        if clean(current.get("action")) != "NOOP":
            base.add_check(
                checks, "FAIL", "IDEMPOTENCY_DEVICE_WRITE_PENDING", aid, label,
                "matched_by={0}; action={1}; diffs={2}".format(
                    matched_by, clean(current.get("action")),
                    " | ".join(current.get("safe_diffs") or [])))
            continue
        pending_ips = [
            item for item in (current.get("ip_intents") or [])
            if clean(item.get("action")) != "NOOP"
        ]
        if pending_ips:
            detail = "; ".join(
                "{0}:{1}".format(clean(item.get("ip")), clean(item.get("action")))
                for item in pending_ips
            )
            base.add_check(
                checks, "FAIL", "IDEMPOTENCY_IP_WRITE_PENDING", aid, label,
                "matched_by={0}; {1}".format(matched_by, detail))
            continue
        base.add_check(
            checks, "PASS", "IDEMPOTENCY_NOOP", aid, label,
            "matched_by={0}".format(matched_by))


def compare_expected_inventory(row, device, tenant, site, checks):
    patched = row
    expected = clean(row.get("target_role"))
    live = base.nested_name(device.get("role"))
    if expected and canonical_windows_role(expected) == canonical_windows_role(live):
        patched = dict(row)
        patched["target_role"] = live
    return ORIGINAL_COMPARE(patched, device, tenant, site, checks)


def generate_fresh_plan():
    planner = os.path.join(BASE, "modules", "inventory", "planner_v10.py")
    before = set(glob.glob(os.path.join(v9.REPORTS, "*-plan-*.json")))
    v4.v3.v2.base.subprocess.check_call([sys.executable, planner])
    after = set(glob.glob(os.path.join(v9.REPORTS, "*-plan-*.json")))
    created = sorted(after - before, key=os.path.getmtime, reverse=True)
    if created:
        return created[0]
    rows = sorted(after, key=os.path.getmtime, reverse=True)
    if not rows:
        raise RuntimeError("PLAN V10 não gerou JSON para idempotência")
    return rows[0]


ORIGINAL_COMPARE = base.compare_expected_inventory


def main(argv=None):
    old_generate = v9.generate_fresh_plan
    old_idempotency = base.audit_idempotency
    old_compare = base.compare_expected_inventory
    modules = (base, v2, v3, v4, v5, v6, v7, v8, v9)
    old_versions = [getattr(module, "AUDITOR_VERSION", "") for module in modules]
    try:
        v9.generate_fresh_plan = generate_fresh_plan
        base.audit_idempotency = audit_idempotency
        base.compare_expected_inventory = compare_expected_inventory
        for module in modules:
            module.AUDITOR_VERSION = AUDITOR_VERSION
        return v9.main(argv)
    finally:
        v9.generate_fresh_plan = old_generate
        base.audit_idempotency = old_idempotency
        base.compare_expected_inventory = old_compare
        for module, value in zip(modules, old_versions):
            module.AUDITOR_VERSION = value


if __name__ == "__main__":
    raise SystemExit(main())
