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

from modules.auditors import inventory as package_base
from modules.auditors import auditor_v2 as v2
from modules.auditors import auditor_v10 as v10

AUDITOR_VERSION = "6.9-product"
REPORTS = package_base.REPORTS


def generate_fresh_plan():
    planner = os.path.join(BASE, "modules", "inventory", "planner_v11.py")
    before = set(glob.glob(os.path.join(REPORTS, "*-plan-*.json")))
    package_base.subprocess.check_call([sys.executable, planner])
    after = set(glob.glob(os.path.join(REPORTS, "*-plan-*.json")))
    created = sorted(after - before, key=os.path.getmtime, reverse=True)
    if created:
        return created[0]
    rows = sorted(after, key=os.path.getmtime, reverse=True)
    if not rows:
        raise RuntimeError("PLAN V11 não gerou JSON para idempotência")
    return rows[0]


def main(argv=None):
    old_generate = v10.generate_fresh_plan
    old_version = v10.AUDITOR_VERSION
    old_package_idempotency = package_base.audit_idempotency
    old_package_compare = package_base.compare_expected_inventory
    old_top_idempotency = v2.base.audit_idempotency
    old_top_compare = v2.base.compare_expected_inventory
    try:
        v10.generate_fresh_plan = generate_fresh_plan
        v10.AUDITOR_VERSION = AUDITOR_VERSION
        # auditor_v2 imports inventory.py as a top-level module while newer
        # wrappers import modules.auditors.inventory. Patch both module objects
        # so the stable idempotency key and Windows role normalization reach the
        # actual audit main loop.
        package_base.audit_idempotency = v10.audit_idempotency
        package_base.compare_expected_inventory = v10.compare_expected_inventory
        v2.base.audit_idempotency = v10.audit_idempotency
        v2.base.compare_expected_inventory = v10.compare_expected_inventory
        return v10.main(argv)
    finally:
        v2.base.compare_expected_inventory = old_top_compare
        v2.base.audit_idempotency = old_top_idempotency
        package_base.compare_expected_inventory = old_package_compare
        package_base.audit_idempotency = old_package_idempotency
        v10.AUDITOR_VERSION = old_version
        v10.generate_fresh_plan = old_generate


if __name__ == "__main__":
    raise SystemExit(main())
