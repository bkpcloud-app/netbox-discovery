#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from modules.auditors import auditor_v4 as v4
from modules.auditors import auditor_v7 as v7

AUDITOR_VERSION = "6.6-product"
BASE = v7.BASE
REPORTS = v7.REPORTS
ORIG_COMPARE = v4.base.compare_expected_inventory


def clean(value):
    return "" if value is None else str(value).strip()


def generate_fresh_plan():
    planner = os.path.join(BASE, "modules", "inventory", "planner_v8.py")
    before = set(glob.glob(os.path.join(REPORTS, "*-plan-*.json")))
    v4.v3.v2.base.subprocess.check_call([sys.executable, planner])
    after = set(glob.glob(os.path.join(REPORTS, "*-plan-*.json")))
    created = sorted(after - before, key=os.path.getmtime, reverse=True)
    if created:
        return created[0]
    rows = sorted(after, key=os.path.getmtime, reverse=True)
    if not rows:
        raise RuntimeError("PLAN V8 não gerou JSON para idempotência")
    return rows[0]


def compare_expected_inventory(row, device, tenant, site, checks):
    start = len(checks)
    ORIG_COMPARE(row, device, tenant, site, checks)
    upgrade = row.get("device_type_upgrade") or {}
    if clean(upgrade.get("mode")) != "UPGRADE_PRODUCT_GENERIC_PRINTER":
        return

    relevant = checks[start:]
    mismatch = next((item for item in relevant if item.get("code") == "DEVICE_TYPE_MISMATCH"), None)
    if mismatch:
        mismatch["severity"] = "FAIL"
        mismatch["code"] = "DEVICE_TYPE_UPGRADE_MISMATCH"
        return

    v4.base.add_check(
        checks, "PASS", "DEVICE_TYPE_UPGRADE_OK",
        row.get("asset_id"), row.get("desired_name"),
        "{0}/{1} ({2})".format(
            clean(upgrade.get("target_manufacturer")),
            clean(upgrade.get("target_model")),
            clean(upgrade.get("precision")),
        ),
    )


def main(argv=None):
    old_generate = v7.generate_fresh_plan
    old_version = v7.AUDITOR_VERSION
    old_compare = v4.base.compare_expected_inventory
    try:
        v7.generate_fresh_plan = generate_fresh_plan
        v7.AUDITOR_VERSION = AUDITOR_VERSION
        v4.base.compare_expected_inventory = compare_expected_inventory
        return v7.main(argv)
    finally:
        v4.base.compare_expected_inventory = old_compare
        v7.AUDITOR_VERSION = old_version
        v7.generate_fresh_plan = old_generate


if __name__ == "__main__":
    sys.exit(main())
