#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import builtins
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, "..", ".."))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.importers import importer_v4 as v4
from modules.importers import importer_v7 as v7
from modules.importers import importer_v8 as v8
from modules.importers import importer_v9 as v9

IMPORTER_VERSION = "5.8-product"
REPORTS = v4.REPORTS
ORIG_SAFE_PATCH = v9.safe_patch_for_existing


def safe_patch_for_existing(row, current, catalog):
    payload = ORIG_SAFE_PATCH(row, current, catalog)
    if "name" in payload:
        raise RuntimeError("política 1.11.0 proíbe alteração automática do nome de Device existente")
    if row.get("name_write_allowed") is False and "name" in payload:
        raise RuntimeError("PLAN marcou nome como administrado pelo NetBox")
    return payload


def refresh_plan():
    planner = os.path.join(BASE, "modules", "inventory", "planner_v9.py")
    if not os.path.isfile(planner):
        raise RuntimeError("Planner V9 não encontrado: {0}".format(planner))
    v4.base.subprocess.check_call([sys.executable, planner])
    path = v4._latest(os.path.join(REPORTS, "*-plan-*.json"))
    if not path:
        raise RuntimeError("PLAN V9 não gerou JSON")
    return path


def main(argv=None):
    old_refresh = v7.refresh_plan
    old_version = v8.IMPORTER_VERSION
    old_patch_v4 = v4.base.safe_patch_for_existing
    old_patch_v9 = v9.safe_patch_for_existing
    old_print = builtins.print

    def release_print(*args, **kwargs):
        if args and str(args[0]) in (
            "===== IMPORT FINALIZE 1.10.18 =====",
            "===== IMPORT FINALIZE 1.10.19 =====",
        ):
            args = ("===== IMPORT FINALIZE 1.11.0 =====",) + tuple(args[1:])
        return old_print(*args, **kwargs)

    try:
        v7.refresh_plan = refresh_plan
        v8.IMPORTER_VERSION = IMPORTER_VERSION
        v4.base.safe_patch_for_existing = safe_patch_for_existing
        v9.safe_patch_for_existing = safe_patch_for_existing
        builtins.print = release_print
        return v9.main(argv)
    finally:
        builtins.print = old_print
        v9.safe_patch_for_existing = old_patch_v9
        v4.base.safe_patch_for_existing = old_patch_v4
        v8.IMPORTER_VERSION = old_version
        v7.refresh_plan = old_refresh


if __name__ == "__main__":
    sys.exit(main())
