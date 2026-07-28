#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from modules.auditors import auditor_v2 as v2

AUDITOR_VERSION = "6.1-product"
BASE = v2.BASE
REPORTS = v2.REPORTS


def generate_fresh_plan():
    planner = os.path.join(BASE, "modules", "inventory", "planner_v3.py")
    before = set(glob.glob(os.path.join(REPORTS, "*-plan-*.json")))
    v2.base.subprocess.check_call([sys.executable, planner])
    after = set(glob.glob(os.path.join(REPORTS, "*-plan-*.json")))
    created = sorted(after - before, key=os.path.getmtime, reverse=True)
    if created:
        return created[0]
    files = sorted(glob.glob(os.path.join(REPORTS, "*-plan-*.json")), key=os.path.getmtime, reverse=True)
    if not files:
        raise RuntimeError("PLAN V3 não gerou JSON para idempotência")
    return files[0]


def _print_latest_details():
    files = sorted(glob.glob(os.path.join(REPORTS, "*-audit-*.json")), key=os.path.getmtime, reverse=True)
    if not files:
        return
    try:
        data = json.load(open(files[0], "r"))
    except Exception:
        return
    relevant = [x for x in (data.get("checks") or []) if x.get("severity") in ("WARN", "FAIL")]
    if not relevant:
        return
    print("===== AUDIT PENDÊNCIAS DETALHADAS =====")
    for pos, row in enumerate(relevant, 1):
        print("[{0}/{1}] {2} | {3} | {4} | {5}".format(
            pos, len(relevant), row.get("severity") or "-", row.get("code") or "-",
            row.get("name") or row.get("asset_id") or "-", row.get("detail") or "-",
        ))


def main(argv=None):
    old_generate = v2.generate_fresh_plan
    old_version = v2.AUDITOR_VERSION
    try:
        v2.generate_fresh_plan = generate_fresh_plan
        v2.AUDITOR_VERSION = AUDITOR_VERSION
        rc = v2.main(argv)
        _print_latest_details()
        return rc
    finally:
        v2.generate_fresh_plan = old_generate
        v2.AUDITOR_VERSION = old_version


if __name__ == "__main__":
    sys.exit(main())
