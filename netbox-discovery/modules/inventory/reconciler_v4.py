#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, "..", ".."))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.inventory import reconciler_v2 as v2
from modules.inventory import reconciler_v3 as v3

RECONCILER_VERSION = "3.2-product"
ORIG_BUILD_ASSETS = v2.base.build_assets


def clean(value):
    return "" if value is None else str(value).strip()


def build_assets(records):
    assets, edges, candidates = ORIG_BUILD_ASSETS(records)
    by_ip = dict((clean(row.get("ip")), row) for row in records if clean(row.get("ip")))
    for asset in assets:
        conflicts = []
        for ip in asset.get("ips") or []:
            value = clean((by_ip.get(clean(ip)) or {}).get("historical_identity_conflict"))
            if value:
                conflicts.append(value)
        conflicts = sorted(set(conflicts))
        if conflicts:
            asset["historical_identity_conflict"] = "+".join(conflicts)
    return assets, edges, candidates


def main(argv=None):
    old_build = v2.base.build_assets
    old_version = v3.RECONCILER_VERSION
    try:
        v2.base.build_assets = build_assets
        v3.RECONCILER_VERSION = RECONCILER_VERSION
        return v3.main(argv)
    finally:
        v2.base.build_assets = old_build
        v3.RECONCILER_VERSION = old_version


if __name__ == "__main__":
    sys.exit(main())
