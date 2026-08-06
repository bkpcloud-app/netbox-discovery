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

import importer as base

IMPORTER_VERSION = "5.1-product"
ORIG_REMATCH = base.rematch_record
ORIG_ENSURE_INTERFACE = base.ensure_interface
ORIG_REFRESH_PLAN = base.refresh_plan


def clean(v):
    return "" if v is None else str(v).strip()


def nested_id(value):
    if isinstance(value, dict):
        return value.get("id")
    if isinstance(value, int):
        return value
    return None


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


def refresh_plan():
    """Always re-plan with Device Identity V2 immediately before IMPORT."""
    planner = os.path.join(BASE, "modules", "inventory", "planner_v2.py")
    if not os.path.isfile(planner):
        raise RuntimeError("Planner V2 não encontrado: {0}".format(planner))
    base.subprocess.check_call([sys.executable, planner])
    path = base.latest(os.path.join(base.REPORTS, "*-plan-*.json"))
    if not path:
        raise RuntimeError("PLAN V2 não gerou JSON")
    return path


def rematch_record(row, indexes):
    current, state, reason = ORIG_REMATCH(row, indexes)
    expected = row.get("existing_device_id")
    if not expected:
        return current, state, reason
    if state == "CONFLICT":
        return current, state, reason
    if current is not None and current.get("id") != expected:
        return None, "CONFLICT", "PLAN aponta Device ID {0}, identidade runtime aponta {1}".format(expected, current.get("id"))
    target = indexes.get("by_id", {}).get(expected)
    if target is None:
        return current, state, reason
    desired_serial = base.norm_serial(row.get("serial"))
    live_serial = base.norm_serial(target.get("serial"))
    if desired_serial and live_serial and desired_serial != live_serial:
        return None, "CONFLICT", "serial divergiu do Device selecionado pelo PLAN"
    return target, "MATCHED", "plan-existing-device-id"


def _mac_cache(nb):
    cache = getattr(nb, "_network_mac_cache", None)
    if cache is None:
        cache = base.query(nb, "dcim/mac-addresses/", limit=10000)
        setattr(nb, "_network_mac_cache", cache)
    return cache


def _assigned_id(row):
    assigned = row.get("assigned_object") or {}
    if isinstance(assigned, dict) and assigned.get("id"):
        return assigned.get("id")
    return row.get("assigned_object_id")


def _interface_for_owned_mac(nb, device, mac):
    """Return the live interface when MAC already belongs to this Device.

    Interface names are not identity. A partial APPLY may already have created
    and populated an interface whose name differs from the current PLAN spec.
    Resolve the globally unique MAC first so the importer never creates a second
    interface and only afterwards discovers the existing MAC assignment.
    """
    mac = norm_mac(mac)
    device_id = device.get("id") if isinstance(device, dict) else None
    if not mac or not isinstance(device_id, int):
        return None

    matches = [
        item for item in _mac_cache(nb)
        if norm_mac(item.get("mac_address") or item.get("mac")) == mac
    ]
    if len(matches) > 1:
        raise RuntimeError("MAC duplicado no NetBox: {0}".format(mac))
    if not matches:
        return None

    obj = matches[0]
    assigned_id = _assigned_id(obj)
    assigned_type = clean(obj.get("assigned_object_type"))
    if not assigned_id:
        return None
    if assigned_type != "dcim.interface":
        raise RuntimeError("MAC {0} já pertence a {1} ID {2}".format(
            mac, assigned_type or "outro objeto", assigned_id))

    interface = nb.get("dcim/interfaces/{0}/".format(assigned_id))
    if not isinstance(interface, dict) or interface.get("id") != assigned_id:
        raise RuntimeError("MAC {0} aponta para interface ID {1} não resolvida".format(mac, assigned_id))
    owner_id = nested_id(interface.get("device"))
    if owner_id != device_id:
        raise RuntimeError("MAC {0} pertence à interface ID {1} do Device ID {2}, esperado Device ID {3}".format(
            mac, assigned_id, owner_id or "NONE", device_id))
    return interface


def ensure_mac(nb, apply_mode, interface, mac, report):
    mac = norm_mac(mac)
    if not mac or not interface.get("id"):
        return None
    rows = _mac_cache(nb)
    matches = [x for x in rows if norm_mac(x.get("mac_address") or x.get("mac")) == mac]
    if len(matches) > 1:
        raise RuntimeError("MAC duplicado no NetBox: {0}".format(mac))
    if not apply_mode:
        report.append({
            "phase": "MAC", "object_type": "MAC_ADDRESS", "action": "WOULD_ENSURE",
            "name": mac, "object_id": matches[0].get("id") if matches else "",
            "detail": clean(interface.get("name")),
        })
        return matches[0] if matches else {"id": "PLANNED:MAC:" + mac, "mac_address": mac, "_planned": True}

    if matches:
        obj = matches[0]
        aoid = _assigned_id(obj)
        atype = clean(obj.get("assigned_object_type"))
        if aoid and (atype != "dcim.interface" or aoid != interface.get("id")):
            raise RuntimeError("MAC {0} já pertence a {1} ID {2}".format(mac, atype, aoid))
        if not aoid:
            obj = nb.patch("dcim/mac-addresses/{0}/".format(obj["id"]), {
                "assigned_object_type": "dcim.interface",
                "assigned_object_id": interface["id"],
            })
        action = "PRESERVED"
    else:
        obj = nb.post("dcim/mac-addresses/", {
            "mac_address": mac,
            "assigned_object_type": "dcim.interface",
            "assigned_object_id": interface["id"],
            "description": "Descoberto pelo netbox-discovery",
        })
        rows.append(obj)
        action = "CREATED"

    current_primary = interface.get("primary_mac_address") or {}
    current_primary_id = current_primary.get("id") if isinstance(current_primary, dict) else current_primary
    if obj.get("id") and current_primary_id != obj.get("id"):
        nb.patch("dcim/interfaces/{0}/".format(interface["id"]), {"primary_mac_address": obj["id"]})

    report.append({
        "phase": "MAC", "object_type": "MAC_ADDRESS", "action": action,
        "name": mac, "object_id": obj.get("id"), "detail": clean(interface.get("name")),
    })
    return obj


def ensure_interface(nb, apply_mode, device, spec, report):
    interface = None
    if spec.get("mac"):
        interface = _interface_for_owned_mac(nb, device, spec.get("mac"))
    if interface is not None:
        report.append({
            "phase": "INTERFACE", "object_type": "INTERFACE", "action": "PRESERVED_BY_MAC",
            "name": clean(interface.get("name")), "object_id": interface.get("id"),
            "detail": clean(device.get("name")),
        })
    else:
        interface = ORIG_ENSURE_INTERFACE(nb, apply_mode, device, spec, report)
    if spec.get("mac"):
        ensure_mac(nb, apply_mode, interface, spec.get("mac"), report)
    return interface


def main(argv=None):
    old_rematch = base.rematch_record
    old_ensure = base.ensure_interface
    old_refresh = base.refresh_plan
    old_version = base.IMPORTER_VERSION
    try:
        base.rematch_record = rematch_record
        base.ensure_interface = ensure_interface
        base.refresh_plan = refresh_plan
        base.IMPORTER_VERSION = IMPORTER_VERSION
        return base.main(argv)
    finally:
        base.rematch_record = old_rematch
        base.ensure_interface = old_ensure
        base.refresh_plan = old_refresh
        base.IMPORTER_VERSION = old_version


if __name__ == "__main__":
    sys.exit(main())
