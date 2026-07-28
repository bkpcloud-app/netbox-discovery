#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, "..", ".."))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.inventory import planner_v4 as v4

PLANNER_VERSION = "4.5-product"
VMWARE_MAC_PREFIXES = (
    "00:05:69",
    "00:0C:29",
    "00:1C:14",
    "00:50:56",
)


def clean(value):
    return "" if value is None else str(value).strip()


def _is_vmware_mac(value):
    mac = v4.norm_mac(value)
    return bool(mac and any(mac.startswith(prefix) for prefix in VMWARE_MAC_PREFIXES))


def _classification_by_ip(classification):
    rows = {}
    for row in (classification.get("records") or []):
        ip = v4.v2.base.norm_ip(row.get("ip"))
        if ip:
            rows[ip] = row
    return rows


def _enrich_asset_vmware_identity(asset, classification_rows):
    """Carry strong anti-flap VMware identity into the safe repair gate.

    The classifier may intentionally retain historical_vmware_mac when the
    current scan misses L2 evidence. The repair is still safe because that MAC
    must match exactly one live NetBox VM interface before any write occurs.
    """
    enriched = dict(asset)
    macs = []
    for value in asset.get("macs") or []:
        mac = v4.norm_mac(value)
        if mac and mac not in macs:
            macs.append(mac)

    for ip in asset.get("ips") or []:
        row = classification_rows.get(v4.v2.base.norm_ip(ip)) or {}
        for field in ("management_mac", "historical_vmware_mac"):
            value = row.get(field)
            mac = v4.norm_mac(value)
            if _is_vmware_mac(mac) and mac not in macs:
                macs.append(mac)

    enriched["macs"] = macs
    return enriched


def build_plan(recon, classification, state):
    classification_rows = _classification_by_ip(classification)
    original_repair_candidate = v4._repair_candidate
    original_version = v4.PLANNER_VERSION

    def repair_candidate(row, asset, vm, live_state):
        enriched = _enrich_asset_vmware_identity(asset, classification_rows)
        return original_repair_candidate(row, enriched, vm, live_state)

    try:
        v4._repair_candidate = repair_candidate
        v4.PLANNER_VERSION = PLANNER_VERSION
        return v4.build_plan(recon, classification, state)
    finally:
        v4._repair_candidate = original_repair_candidate
        v4.PLANNER_VERSION = original_version


def main(argv=None):
    old_state = v4.v3.netbox_state
    old_build = v4.v3.build_plan
    old_version = v4.v3.PLANNER_VERSION
    try:
        v4.v3.netbox_state = v4.netbox_state
        v4.v3.build_plan = build_plan
        v4.v3.PLANNER_VERSION = PLANNER_VERSION
        return v4.v3.main(argv)
    finally:
        v4.v3.netbox_state = old_state
        v4.v3.build_plan = old_build
        v4.v3.PLANNER_VERSION = old_version


if __name__ == "__main__":
    sys.exit(main())
