#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import builtins
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from lib.netbox import NetBox
from modules.importers import importer_v2 as v2
from modules.importers import importer_v4 as v4

IMPORTER_VERSION = "5.3-product"
BASE = v4.BASE
REPORTS = v4.REPORTS
ORIG_NORMAL_MAIN = v4.v3.main
ORIG_PREFLIGHT_READY = v4.base.preflight_ready


def clean(value):
    return "" if value is None else str(value).strip()


def nested_id(value):
    if isinstance(value, dict):
        return value.get("id")
    if isinstance(value, int):
        return value
    return None


def refresh_plan():
    planner = os.path.join(BASE, "modules", "inventory", "planner_v5.py")
    if not os.path.isfile(planner):
        raise RuntimeError("Planner V5 não encontrado: {0}".format(planner))
    v4.base.subprocess.check_call([sys.executable, planner])
    path = v4._latest(os.path.join(REPORTS, "*-plan-*.json"))
    if not path:
        raise RuntimeError("PLAN V5 não gerou JSON")
    return path


def _all_macs(nb):
    return v4.base.query(nb, "dcim/mac-addresses/", limit=10000)


def _assigned_id(row):
    assigned = row.get("assigned_object") or {}
    if isinstance(assigned, dict) and assigned.get("id"):
        return assigned.get("id")
    return row.get("assigned_object_id")


def _expected_interface_id(indexes, spec):
    ip = v4.base.norm_ip(spec.get("ip"))
    rows = indexes.get("ip_objects", {}).get(ip, [])
    if len(rows) != 1:
        return None
    row = rows[0]
    if clean(row.get("assigned_object_type")) != "dcim.interface":
        return None
    return _assigned_id(row)


def preflight_ready(ready, indexes, tenant):
    """Extend the global preflight with MAC ownership validation.

    Missing MAC objects are safe and will be created after the normal importer.
    Existing MACs assigned anywhere else block before the first write.
    """
    errors = list(ORIG_PREFLIGHT_READY(ready, indexes, tenant))
    nb = NetBox()
    mac_rows = _all_macs(nb)

    for row in ready:
        label = clean(row.get("desired_name")) or clean(row.get("asset_id"))
        for spec in row.get("interfaces") or []:
            mac = v2.norm_mac(spec.get("mac"))
            if not mac:
                continue
            matches = [
                item for item in mac_rows
                if v2.norm_mac(item.get("mac_address") or item.get("mac")) == mac
            ]
            if len(matches) > 1:
                errors.append("{0}: MAC duplicado no NetBox: {1}".format(label, mac))
                continue
            if not matches:
                continue
            item = matches[0]
            assigned_type = clean(item.get("assigned_object_type"))
            assigned_id = _assigned_id(item)
            if not assigned_id:
                continue
            expected_interface_id = _expected_interface_id(indexes, spec)
            if assigned_type != "dcim.interface" or not expected_interface_id or assigned_id != expected_interface_id:
                errors.append(
                    "{0}: MAC {1} pertence a {2} ID {3}, esperado interface {4}".format(
                        label, mac, assigned_type or "outro objeto", assigned_id,
                        expected_interface_id or "ainda não existente",
                    )
                )
    return errors


def _plan_arg(argv):
    values = list(argv or [])
    for pos, value in enumerate(values):
        if value == "--plan" and pos + 1 < len(values):
            return values[pos + 1]
    return ""


def _write_mac_report(plan_path, events, errors):
    try:
        plan = json.load(open(plan_path, "r"))
        site = clean(plan.get("site")) or "SITE"
    except Exception:
        site = "SITE"
    stamp = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(REPORTS, "{0}-mac-reconcile-{1}.json".format(site, stamp))
    with open(path, "w") as handle:
        json.dump({
            "stage": "MAC_RECONCILE",
            "importer_version": IMPORTER_VERSION,
            "source_plan": plan_path,
            "status": "FAIL" if errors else "PASS",
            "records": events,
            "errors": errors,
            "netbox_write": True,
        }, handle, indent=2, sort_keys=True)
    return path


def _reconcile_ready_macs(plan_path):
    """Ensure MAC objects even when an existing IP/interface was preserved.

    importer_v2 only calls ensure_mac through ensure_interface. For an existing
    IP already bound to the correct interface, the base importer preserves that
    interface directly. This post-normal phase closes that safe gap.
    """
    plan = json.load(open(plan_path, "r"))
    ready = [
        row for row in (plan.get("records") or [])
        if clean(row.get("decision")) == "READY"
        and clean(row.get("action")) != "REPAIR_SAFE_VM_DUPLICATE"
    ]

    nb = NetBox()
    ip_rows = [
        row for row in v4.base.query(nb, "ipam/ip-addresses/", limit=10000)
        if not row.get("vrf")
    ]
    by_ip = {}
    for row in ip_rows:
        ip = v4.base.norm_ip(row.get("address"))
        if ip:
            by_ip.setdefault(ip, []).append(row)

    setattr(nb, "_network_mac_cache", _all_macs(nb))
    events = []
    errors = []

    try:
        for row in ready:
            label = clean(row.get("desired_name")) or clean(row.get("asset_id"))
            expected_device_id = row.get("existing_device_id")
            for spec in row.get("interfaces") or []:
                mac = v2.norm_mac(spec.get("mac"))
                if not mac:
                    continue
                ip = v4.base.norm_ip(spec.get("ip"))
                matches = by_ip.get(ip, [])
                if len(matches) != 1:
                    raise RuntimeError("{0}: IP {1} não é único para reconciliar MAC".format(label, ip))
                ip_obj = matches[0]
                if clean(ip_obj.get("assigned_object_type")) != "dcim.interface":
                    raise RuntimeError("{0}: IP {1} não pertence a dcim.interface".format(label, ip))
                interface_id = _assigned_id(ip_obj)
                if not interface_id:
                    raise RuntimeError("{0}: IP {1} sem interface atribuída".format(label, ip))
                interface = nb.get("dcim/interfaces/{0}/".format(interface_id))
                live_device_id = nested_id(interface.get("device"))
                if expected_device_id and live_device_id != expected_device_id:
                    raise RuntimeError(
                        "{0}: interface do IP {1} pertence ao Device {2}, esperado {3}".format(
                            label, ip, live_device_id, expected_device_id,
                        )
                    )
                v2.ensure_mac(nb, True, interface, mac, events)
    except Exception as exc:
        errors.append({"error": str(exc)})
        report = _write_mac_report(plan_path, events, errors)
        print("MAC RECONCILE: FAIL")
        print("JSON MAC: {0}".format(report))
        raise

    report = _write_mac_report(plan_path, events, errors)
    print("===== MAC RECONCILE =====")
    print("Interfaces/MAC verificadas: {0}".format(len(events)))
    print("Status: PASS")
    print("JSON MAC: {0}".format(report))
    return report


def _normal_main(argv=None):
    rc = ORIG_NORMAL_MAIN(argv)
    if rc:
        return rc
    values = list(argv or [])
    if "--apply" in values:
        plan_path = _plan_arg(values)
        if not plan_path:
            raise RuntimeError("IMPORT normal sem --plan para MAC reconcile")
        _reconcile_ready_macs(plan_path)
    return rc


def main(argv=None):
    old_refresh = v4.refresh_plan
    old_normal_main = v4.v3.main
    old_preflight = v4.base.preflight_ready
    old_version = v4.IMPORTER_VERSION
    old_print = builtins.print

    def release_print(*args, **kwargs):
        if args and str(args[0]) == "===== IMPORT FINALIZE 1.10.14 =====":
            args = ("===== IMPORT FINALIZE 1.10.15 =====",) + tuple(args[1:])
        return old_print(*args, **kwargs)

    try:
        v4.refresh_plan = refresh_plan
        v4.v3.main = _normal_main
        v4.base.preflight_ready = preflight_ready
        v4.IMPORTER_VERSION = IMPORTER_VERSION
        builtins.print = release_print
        return v4.main(argv)
    finally:
        builtins.print = old_print
        v4.refresh_plan = old_refresh
        v4.v3.main = old_normal_main
        v4.base.preflight_ready = old_preflight
        v4.IMPORTER_VERSION = old_version


if __name__ == "__main__":
    sys.exit(main())
