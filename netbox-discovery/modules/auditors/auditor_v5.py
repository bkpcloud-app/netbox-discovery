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

AUDITOR_VERSION = "6.3-product"
BASE = v4.BASE
REPORTS = v4.REPORTS


def generate_fresh_plan():
    planner = os.path.join(BASE, "modules", "inventory", "planner_v5.py")
    before = set(glob.glob(os.path.join(REPORTS, "*-plan-*.json")))
    v4.v3.v2.base.subprocess.check_call([sys.executable, planner])
    after = set(glob.glob(os.path.join(REPORTS, "*-plan-*.json")))
    created = sorted(after - before, key=os.path.getmtime, reverse=True)
    if created:
        return created[0]
    rows = sorted(after, key=os.path.getmtime, reverse=True)
    if not rows:
        raise RuntimeError("PLAN V5 não gerou JSON para idempotência")
    return rows[0]


def main(argv=None):
    old_generate = v4.generate_fresh_plan
    old_version = v4.AUDITOR_VERSION
    try:
        v4.generate_fresh_plan = generate_fresh_plan
        v4.AUDITOR_VERSION = AUDITOR_VERSION
        return v4.main(argv)
    finally:
        v4.generate_fresh_plan = old_generate
        v4.AUDITOR_VERSION = old_version


if __name__ == "__main__":
    sys.exit(main())
