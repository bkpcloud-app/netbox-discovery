#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import hashlib
import ipaddress
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, "..", ".."))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.inventory import reconciler_v2 as v2
from modules.inventory import reconciler_v4 as v4

RECONCILER_VERSION = "3.3-product"
ORIG_V4_BUILD_ASSETS = v4.ORIG_BUILD_ASSETS


def clean(value):
    return "" if value is None else str(value).strip()


def _valid_pair_groups(records):
    grouped = defaultdict(list)
    for row in records:
        key = clean(row.get("md32xx_pair_key"))
        if key:
            grouped[key].append(row)

    allowed = set()
    for key, rows in grouped.items():
        if len(rows) != 2:
            continue
        if any(clean(row.get("role")) != "STORAGE" for row in rows):
            continue
        if any(clean(row.get("confidence")) != "HIGH" for row in rows):
            continue
        serials = sorted(set(
            v2.base.norm_serial(row.get("serial"))
            for row in rows if v2.base.norm_serial(row.get("serial"))
        ))
        if len(serials) > 1:
            continue
        try:
            values = sorted(int(ipaddress.ip_address(clean(row.get("ip")))) for row in rows)
        except Exception:
            continue
        if values[1] - values[0] != 1:
            continue
        allowed.add(key)
    return allowed


def build_assets_core(records):
    allowed = _valid_pair_groups(records)
    prepared = []
    for original in records:
        row = dict(original)
        key = clean(row.get("md32xx_pair_key"))
        row["md32xx_merge_token"] = key if key in allowed else ""
        prepared.append(row)

    # At runtime reconciler_v3 has already installed its FA-aware merge_reason
    # and asset_id. Wrap those current functions instead of reverting to the
    # legacy base implementation.
    current_merge_reason = v2.base.merge_reason
    current_asset_id = v2.base.asset_id

    def merge_reason(a, b):
        ta = clean(a.get("md32xx_merge_token"))
        tb = clean(b.get("md32xx_merge_token"))
        if ta and ta == tb:
            return "DELL_MD32XX_CONTROLLER_PAIR:{0}".format(ta), 99
        return current_merge_reason(a, b)

    def asset_id(rows):
        tokens = sorted(set(
            clean(row.get("md32xx_merge_token"))
            for row in rows if clean(row.get("md32xx_merge_token"))
        ))
        if len(tokens) == 1:
            digest = hashlib.sha1(tokens[0].encode("utf-8")).hexdigest()[:20].upper()
            return "MD32XX:{0}".format(digest)
        return current_asset_id(rows)

    old_merge = v2.base.merge_reason
    old_asset = v2.base.asset_id
    try:
        v2.base.merge_reason = merge_reason
        v2.base.asset_id = asset_id
        assets, edges, candidates = ORIG_V4_BUILD_ASSETS(prepared)
    finally:
        v2.base.merge_reason = old_merge
        v2.base.asset_id = old_asset

    by_ip = dict((clean(row.get("ip")), row) for row in prepared if clean(row.get("ip")))
    for asset in assets:
        tokens = sorted(set(
            clean((by_ip.get(clean(ip)) or {}).get("md32xx_merge_token"))
            for ip in (asset.get("ips") or [])
            if clean((by_ip.get(clean(ip)) or {}).get("md32xx_merge_token"))
        ))
        if len(tokens) == 1 and len(asset.get("ips") or []) == 2:
            asset["storage_pair_type"] = "DELL_MD32XX_DUAL_CONTROLLER"
            asset["storage_pair_key"] = tokens[0]
            asset["role"] = "STORAGE"
            asset["manufacturer"] = "Dell"
            asset["model"] = "PowerVault MD32xx"
            asset["asset_class"] = "PHYSICAL_DEVICE"
            asset["confidence"] = "HIGH"
            asset["classification_score"] = max(int(asset.get("classification_score") or 0), 96)
    return assets, edges, candidates


def main(argv=None):
    old_orig = v4.ORIG_BUILD_ASSETS
    old_version = v4.RECONCILER_VERSION
    try:
        v4.ORIG_BUILD_ASSETS = build_assets_core
        v4.RECONCILER_VERSION = RECONCILER_VERSION
        return v4.main(argv)
    finally:
        v4.ORIG_BUILD_ASSETS = old_orig
        v4.RECONCILER_VERSION = old_version


if __name__ == "__main__":
    sys.exit(main())
