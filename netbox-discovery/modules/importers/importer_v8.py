#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import builtins
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from modules.importers import importer_v4 as v4
from modules.importers import importer_v7 as v7

IMPORTER_VERSION = "5.6-product"


def clean(value):
    return "" if value is None else str(value).strip()


def nested_id(value):
    if isinstance(value, dict):
        return value.get("id")
    if isinstance(value, int):
        return value
    return None


def _clear_device_primary_before_ip_move(nb, row, verified, events):
    """Clear only target-IP parent references before NetBox reassignment.

    NetBox rejects reassignment while the IP is still primary/oob on the
    current parent Device. Any reference to a different IP is treated as
    unexpected drift and blocks before the IP move or Device deletion.
    """
    if clean(verified.get("mode")) == "RECOVERY_AFTER_IP_MOVE":
        return

    repair = row.get("repair") or {}
    device = verified.get("device") or {}
    target_ip_id = repair.get("ip_id")
    if not target_ip_id:
        raise RuntimeError("Reparo sem ip_id para liberar primary IP do Device")

    clear_payload = {}
    for field in ("primary_ip4", "primary_ip6", "oob_ip"):
        current_id = nested_id(device.get(field))
        if not current_id:
            continue
        if current_id != target_ip_id:
            raise RuntimeError(
                "Device possui {0} apontando para outro IP ID {1}; esperado {2}".format(
                    field, current_id, target_ip_id))
        clear_payload[field] = None

    if not clear_payload:
        return

    nb.patch("dcim/devices/{0}/".format(repair["device_id"]), clear_payload)
    for field in clear_payload:
        device[field] = None
    events.append({
        "phase": "REPAIR",
        "object_type": "DEVICE",
        "action": "PRIMARY_IP_CLEARED_BEFORE_MOVE",
        "name": repair.get("device_name"),
        "object_id": repair.get("device_id"),
        "detail": "{0} liberado(s) antes de mover IP {1}".format(
            ",".join(sorted(clear_payload)), repair.get("ip_address")),
    })


def _execute_repair_primary_safe(nb, row, verified, events, base_execute):
    _clear_device_primary_before_ip_move(nb, row, verified, events)
    return base_execute(nb, row, verified, events)


def main(argv=None):
    old_execute = v4._execute_repair
    old_version = v7.IMPORTER_VERSION
    old_print = builtins.print

    def execute_repair(nb, row, verified, events):
        return _execute_repair_primary_safe(
            nb, row, verified, events, old_execute)

    def release_print(*args, **kwargs):
        if args and str(args[0]) == "===== IMPORT FINALIZE 1.10.17 =====":
            args = ("===== IMPORT FINALIZE 1.10.18 =====",) + tuple(args[1:])
        return old_print(*args, **kwargs)

    try:
        # importer_v7 captures v4._execute_repair as its base executor. By
        # installing this wrapper first, every repair path (existing interface,
        # single empty interface and interface created in 1.10.17) clears the
        # Device primary/oob reference before attempting IP reassignment.
        v4._execute_repair = execute_repair
        v7.IMPORTER_VERSION = IMPORTER_VERSION
        builtins.print = release_print
        return v7.main(argv)
    finally:
        builtins.print = old_print
        v7.IMPORTER_VERSION = old_version
        v4._execute_repair = old_execute


if __name__ == "__main__":
    sys.exit(main())
