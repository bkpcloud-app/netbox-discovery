#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import glob
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("NETBOX_DISCOVERY_BASE", os.path.abspath(os.path.join(HERE, "..", "..")))
REPORTS = os.path.join(BASE, "reports")
if HERE not in sys.path:
    sys.path.insert(0, HERE)
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import inventory as base

AUDITOR_VERSION = "6.0-product"
ORIG_AUDIT_IPS = base.audit_ips
ORIG_GENERATE_FRESH_PLAN = base.generate_fresh_plan


def clean(v):
    return "" if v is None else str(v).strip()


def norm_mac(value):
    compact = re.sub(r"[^0-9A-Fa-f]", "", clean(value)).upper()
    if len(compact) != 12 or compact in ("000000000000", "FFFFFFFFFFFF"):
        return ""
    try:
        first = int(compact[:2], 16)
    except ValueError:
        return ""
    if first & 1:
        return ""
    return ":".join(compact[i:i + 2] for i in range(0, 12, 2))


def _mac_cache(nb):
    cache = getattr(nb, "_audit_mac_cache", None)
    if cache is None:
        cache = base.query(nb, "dcim/mac-addresses/", limit=10000)
        setattr(nb, "_audit_mac_cache", cache)
    return cache


def _assigned_id(row):
    assigned = row.get("assigned_object") or {}
    if isinstance(assigned, dict) and assigned.get("id"):
        return assigned.get("id")
    return row.get("assigned_object_id")


def audit_ips(nb, row, device, indexes, checks):
    ORIG_AUDIT_IPS(nb, row, device, indexes, checks)
    aid = row.get("asset_id")
    label = row.get("desired_name")
    mac_rows = _mac_cache(nb)
    for spec in row.get("interfaces") or []:
        expected_mac = norm_mac(spec.get("mac"))
        if not expected_mac:
            continue
        ip = base.norm_ip(spec.get("ip"))
        ip_objects = indexes["ip_objects"].get(ip, [])
        if len(ip_objects) != 1:
            base.add_check(checks, "FAIL", "MAC_INTERFACE_UNRESOLVED", aid, label,
                           "não foi possível resolver interface única via IP {0}".format(ip))
            continue
        interface_id = base.assigned_object_id(ip_objects[0])
        matches = [x for x in mac_rows if norm_mac(x.get("mac_address") or x.get("mac")) == expected_mac]
        if len(matches) == 0:
            base.add_check(checks, "FAIL", "MAC_MISSING", aid, label, expected_mac)
            continue
        if len(matches) > 1:
            base.add_check(checks, "FAIL", "MAC_DUPLICATE", aid, label,
                           "{0} objetos para {1}".format(len(matches), expected_mac))
            continue
        obj = matches[0]
        assigned_type = clean(obj.get("assigned_object_type"))
        assigned_id = _assigned_id(obj)
        if assigned_type != "dcim.interface" or assigned_id != interface_id:
            base.add_check(checks, "FAIL", "MAC_WRONG_INTERFACE", aid, label,
                           "mac={0}; type={1}; interface={2}; esperado={3}".format(
                               expected_mac, assigned_type or "unassigned", assigned_id, interface_id))
            continue
        base.add_check(checks, "PASS", "MAC_OK", aid, label, expected_mac)


def generate_fresh_plan():
    planner = os.path.join(BASE, "modules", "inventory", "planner_v2.py")
    before = set(glob.glob(os.path.join(REPORTS, "*-plan-*.json")))
    subprocess.check_call([sys.executable, planner])
    after = set(glob.glob(os.path.join(REPORTS, "*-plan-*.json")))
    created = sorted(after - before, key=os.path.getmtime, reverse=True)
    if created:
        return created[0]
    files = base.latest_files(os.path.join(REPORTS, "*-plan-*.json"))
    if not files:
        raise RuntimeError("PLAN V2 não gerou JSON para idempotência")
    return files[0]


def main(argv=None):
    old_audit_ips = base.audit_ips
    old_fresh = base.generate_fresh_plan
    old_version = base.AUDITOR_VERSION
    try:
        base.audit_ips = audit_ips
        base.generate_fresh_plan = generate_fresh_plan
        base.AUDITOR_VERSION = AUDITOR_VERSION
        return base.main(argv)
    finally:
        base.audit_ips = old_audit_ips
        base.generate_fresh_plan = old_fresh
        base.AUDITOR_VERSION = old_version


if __name__ == "__main__":
    sys.exit(main())
