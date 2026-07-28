#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("NETBOX_DISCOVERY_BASE", os.path.abspath(os.path.join(HERE, "..", "..")))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.inventory import reconciler_v2 as v2

RECONCILER_VERSION = "3.1-product"

ORIG_MERGE_REASON = v2.base.merge_reason
ORIG_ASSET_ID = v2.base.asset_id


def clean(value):
    return "" if value is None else str(value).strip()


def storage_unit_id(record):
    if clean(record.get("role")) != "STORAGE":
        return ""
    value = re.sub(r"[^A-Fa-f0-9]", "", clean(record.get("storage_unit_id"))).upper()
    if not value or set(value) == set("0"):
        return ""
    return value


def merge_reason(a, b):
    fa_a = storage_unit_id(a)
    fa_b = storage_unit_id(b)
    if fa_a and fa_b and fa_a == fa_b:
        return "FA_CONN_UNIT:{0}".format(fa_a), 100
    return ORIG_MERGE_REASON(a, b)


def asset_id(records):
    # Prefer a real serial when FA-MIB supplies connUnitSn. If a storage unit has
    # no serial, connUnitId remains a persistent strong identity for the array.
    serials = [v2.base.norm_serial(row.get("serial")) for row in records]
    serials = [value for value in serials if value]
    if serials:
        return ORIG_ASSET_ID(records)

    fa_ids = sorted(set(storage_unit_id(row) for row in records if storage_unit_id(row)))
    if len(fa_ids) == 1:
        return "FA:{0}".format(fa_ids[0])
    return ORIG_ASSET_ID(records)


def main(argv=None):
    old_identity = v2.base.identity_sets
    old_merge = v2.base.merge_reason
    old_asset_id = v2.base.asset_id
    old_version = v2.base.RECONCILER_VERSION
    try:
        v2.base.identity_sets = v2.identity_sets
        v2.base.merge_reason = merge_reason
        v2.base.asset_id = asset_id
        v2.base.RECONCILER_VERSION = RECONCILER_VERSION
        return v2.base.main(argv)
    finally:
        v2.base.identity_sets = old_identity
        v2.base.merge_reason = old_merge
        v2.base.asset_id = old_asset_id
        v2.base.RECONCILER_VERSION = old_version


if __name__ == "__main__":
    sys.exit(main())
