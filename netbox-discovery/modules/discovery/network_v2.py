#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from modules.discovery import network as base

DISCOVERY_WRAPPER_VERSION = "4.1-product"
FA_CONN_UNIT_ENTRY_OID = ".1.3.6.1.3.94.1.6.1"

FA_COLUMNS = {
    "1": "conn_unit_id",
    "2": "global_id",
    "3": "type",
    "5": "state",
    "6": "status",
    "7": "product",
    "8": "serial",
    "20": "name",
    "31": "vendor",
}

ORIG_PROBE_SNMP_ENTITY = base.probe_snmp_entity


def clean(value):
    return "" if value is None else str(value).strip()


def _enum_id(value):
    text = clean(value)
    match = re.search(r"\(([0-9]+)\)", text)
    if match:
        return match.group(1)
    return text if text.isdigit() else ""


def _conn_unit_identity(index):
    """Normalize the OCTET STRING table index into a stable uppercase hex ID.

    FCMGMT-MIB implementations may expose the variable-length OCTET STRING index
    as `<length>.<byte>...` or directly as the bytes. Both forms are accepted.
    """
    parts = [x for x in clean(index).split(".") if x != ""]
    if not parts:
        return ""
    try:
        numbers = [int(x) for x in parts]
    except ValueError:
        return re.sub(r"[^A-Za-z0-9]", "", clean(index)).upper()

    if len(numbers) > 1 and numbers[0] == len(numbers) - 1:
        numbers = numbers[1:]
    if not numbers or any(x < 0 or x > 255 for x in numbers):
        return ""
    value = "".join("{0:02X}".format(x) for x in numbers)
    if not value or set(value) == set("0"):
        return ""
    return value


def probe_snmp_fa_connectivity(ip, snmp):
    """Read FibreAlliance FCMGMT-MIB connectivity identity.

    Dell PowerVault ME4/ME5 exposes the array as connUnitType
    storage-subsystem(11). connUnitId/connUnitSn describe the storage unit,
    while the SNMP engine ID is controller-specific. We therefore use the FA
    connectivity unit as array identity and never the controller engine ID.
    """
    empty = {"primary": {}, "units": [], "count": 0}
    if not snmp.get("available"):
        return empty

    version_option, community = base.snmp_command_context(snmp)
    walked = base._snmp_walk(
        ip,
        version_option,
        community,
        FA_CONN_UNIT_ENTRY_OID,
        timeout=12,
    )
    if not walked:
        return empty

    entries = {}
    prefix = FA_CONN_UNIT_ENTRY_OID + "."
    for oid, value_type, value in walked:
        if not oid.startswith(prefix):
            continue
        suffix = oid[len(prefix):].split(".")
        if len(suffix) < 2:
            continue
        column = suffix[0]
        field = FA_COLUMNS.get(column)
        if not field:
            continue
        index = ".".join(suffix[1:])
        row = entries.setdefault(index, {
            "index": index,
            "conn_unit_id": "",
            "global_id": "",
            "type": "",
            "type_id": "",
            "state": "",
            "status": "",
            "product": "",
            "serial": "",
            "name": "",
            "vendor": "",
        })
        row[field] = clean(value)
        if field == "type":
            row["type_id"] = _enum_id(value)

    units = []
    for index, row in entries.items():
        stable_id = _conn_unit_identity(index)
        if not stable_id:
            stable_id = re.sub(r"[^A-Fa-f0-9]", "", clean(row.get("conn_unit_id"))).upper()
        row["conn_unit_id"] = stable_id
        if any(clean(row.get(k)) for k in ("conn_unit_id", "product", "serial", "type")):
            units.append(row)

    units.sort(key=lambda row: (0 if row.get("type_id") == "11" else 1, row.get("conn_unit_id") or row.get("index")))
    primary = next((row for row in units if row.get("type_id") == "11"), {})
    return {"primary": primary, "units": units, "count": len(units)}


def _fa_entity_row(ip, snmp, fa):
    unit = fa.get("primary") or {}
    if unit.get("type_id") != "11" or not unit.get("conn_unit_id"):
        return {}

    sysobjectid = clean(snmp.get("sysobjectid"))
    vendor = clean(unit.get("vendor"))
    product = clean(unit.get("product"))
    manufacturer = vendor
    if not manufacturer and sysobjectid.startswith(".1.3.6.1.4.1.674"):
        manufacturer = "Dell"
    if not manufacturer and re.match(r"^ME[45][0-9]{3}", product, re.I):
        manufacturer = "Dell"

    return {
        "index": "fa:" + unit.get("conn_unit_id", ""),
        "description": "FibreAlliance storage-subsystem",
        "contained_in": "",
        "class": "chassis(3)",
        "class_id": "3",
        "parent_rel_pos": "",
        "name": clean(unit.get("name")) or clean(snmp.get("sysname")) or product,
        "hardware_rev": "",
        "firmware_rev": "",
        "software_rev": "",
        "serial": clean(unit.get("serial")),
        "manufacturer": manufacturer,
        "model": product,
        "alias": "",
        "asset_id": "FA:" + unit.get("conn_unit_id", ""),
        "is_fru": "",
        "fa_conn_unit_id": unit.get("conn_unit_id", ""),
        "fa_conn_unit_type": clean(unit.get("type")),
        "fa_conn_unit_type_id": unit.get("type_id", ""),
        "fa_conn_unit_status": clean(unit.get("status")),
        "fa_conn_unit_state": clean(unit.get("state")),
        "fa_conn_unit_vendor": manufacturer,
        "fa_conn_unit_product": product,
        "fa_conn_unit_serial": clean(unit.get("serial")),
        "source": "fcmgmt-mib",
        "management_ip": ip,
    }


def probe_snmp_entity(ip, snmp):
    entity = ORIG_PROBE_SNMP_ENTITY(ip, snmp)
    fa = probe_snmp_fa_connectivity(ip, snmp)
    fa_row = _fa_entity_row(ip, snmp, fa)
    if not fa_row:
        return entity

    inventory = list(entity.get("inventory") or [])
    inventory.append(fa_row)
    entity["inventory"] = inventory
    entity["count"] = len(inventory)

    # For storage-subsystem identity the FA row represents the managed array,
    # not an individual controller/module. It is therefore authoritative as
    # the primary chassis identity for reconciliation.
    entity["primary"] = fa_row
    return entity


def main():
    old_probe = base.probe_snmp_entity
    try:
        base.probe_snmp_entity = probe_snmp_entity
        return base.main()
    finally:
        base.probe_snmp_entity = old_probe


if __name__ == "__main__":
    sys.exit(main())
