#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import glob
import os
import sys

from modules.importers import importer_v2 as v2

IMPORTER_VERSION = "5.1-product"
BASE = v2.BASE
REPORTS = v2.base.REPORTS


def refresh_plan():
    """Always re-plan with the current anti-flap planner before IMPORT."""
    planner = os.path.join(BASE, "modules", "inventory", "planner_v3.py")
    if not os.path.isfile(planner):
        raise RuntimeError("Planner V3 não encontrado: {0}".format(planner))
    v2.base.subprocess.check_call([sys.executable, planner])
    files = glob.glob(os.path.join(REPORTS, "*-plan-*.json"))
    path = max(files, key=os.path.getmtime) if files else ""
    if not path:
        raise RuntimeError("PLAN V3 não gerou JSON")
    return path


def main(argv=None):
    old_refresh = v2.refresh_plan
    old_version = v2.IMPORTER_VERSION
    try:
        v2.refresh_plan = refresh_plan
        v2.IMPORTER_VERSION = IMPORTER_VERSION
        return v2.main(argv)
    finally:
        v2.refresh_plan = old_refresh
        v2.IMPORTER_VERSION = old_version


if __name__ == "__main__":
    sys.exit(main())
