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
from modules.discovery import network_v2 as v2
from modules.discovery import network_v3 as v3
from modules.inventory import printer_identity

DISCOVERY_WRAPPER_VERSION = "4.3-product"
PRINTER_GENERAL_ENTRY_OID = ".1.3.6.1.2.1.43.5.1.1"
HR_DEVICE_DESCR_OID = ".1.3.6.1.2.1.25.3.2.1.3"
ORIG_V2_PROBE_SNMP_ENTITY = v2.probe_snmp_entity


def clean(value):
    return "" if value is None else str(value).strip()


def _valid_serial(value):
    compact = re.sub(r"[^A-Za-z0-9]", "", clean(value)).upper()
    invalid = {
        "", "UNKNOWN", "NONE", "NULL", "DEFAULT", "SERIAL", "SERIALNUMBER",
        "NOTAVAILABLE", "NOTAPPLICABLE", "TOBEFILLEDBYOEM",
    }
    if compact in invalid:
        return ""
    if len(compact) < 4:
        return ""
    if set(compact) in (set("0"), set("F")):
        return ""
    return clean(value)[:120]


def _printer_general(ip, version_option, community):
    values = {
        "names": [],
        "serials": [],
    }
    walked = base._snmp_walk(
        ip, version_option, community, PRINTER_GENERAL_ENTRY_OID, timeout=10)
    prefix = PRINTER_GENERAL_ENTRY_OID + "."
    for oid, value_type, value in walked:
        if not oid.startswith(prefix) or not clean(value):
            continue
        suffix = oid[len(prefix):].split(".")
        if not suffix:
            continue
        column = suffix[0]
        if column == "16" and clean(value) not in values["names"]:
            values["names"].append(clean(value)[:160])
        elif column == "17":
            serial = _valid_serial(value)
            if serial and serial not in values["serials"]:
                values["serials"].append(serial)
    return values


def _hr_device_descriptions(ip, version_option, community):
    rows = base._snmp_walk(
        ip, version_option, community, HR_DEVICE_DESCR_OID, timeout=10)
    values = []
    for oid, value_type, value in rows:
        text = clean(value)
        if text and text not in values:
            values.append(text[:240])
    return values


def _strong_printer_text(value):
    text = clean(value).lower()
    markers = (
        "printer", "laserjet", "officejet", "pagewide", "designjet", "jetdirect",
        "ecosys", "taskalfa", "syncthru", "brother", "pantum", "kyocera",
        "xerox", "lexmark", "ricoh", "ecotank", "workforce", "imagerunner",
        "imageclass", "i-sensys", "zebra printer", "oki printer",
    )
    return any(marker in text for marker in markers)


def probe_snmp_printer_identity(ip, snmp):
    if not snmp.get("available"):
        return {}

    version_option, community = base.snmp_command_context(snmp)
    general = _printer_general(ip, version_option, community)
    base_text = " ".join([
        clean(snmp.get("sysname")), clean(snmp.get("sysdescr")),
        " ".join(general.get("names") or []),
    ])

    # HOST-RESOURCES-MIB is only queried when Printer-MIB answered or the SNMP
    # system identity itself is printer-specific. This keeps the probe bounded
    # on switches, servers and OT devices.
    descriptions = []
    if general.get("names") or general.get("serials") or _strong_printer_text(base_text):
        descriptions = _hr_device_descriptions(ip, version_option, community)

    identity = printer_identity.infer(
        base_text,
        " ".join(descriptions),
    )
    serial = (general.get("serials") or [""])[0]
    printer_name = (general.get("names") or [""])[0]

    # Require actual Printer-MIB evidence or a strict vendor/model fingerprint.
    # A generic hrDeviceDescr alone is never sufficient.
    if not (general.get("names") or general.get("serials") or identity.get("manufacturer") or identity.get("model")):
        return {}

    return {
        "index": "printer-mib:1",
        "description": "Printer-MIB/HOST-RESOURCES-MIB identity",
        "contained_in": "",
        "class": "chassis(3)",
        "class_id": "3",
        "parent_rel_pos": "",
        "name": printer_name or clean(snmp.get("sysname")),
        "hardware_rev": "",
        "firmware_rev": "",
        "software_rev": "",
        "serial": serial,
        "manufacturer": clean(identity.get("manufacturer")),
        "model": clean(identity.get("model")),
        "alias": "",
        "asset_id": "",
        "is_fru": "",
        "source": "printer-mib",
        "printer_name": printer_name,
        "printer_descriptions": descriptions[:32],
        "management_ip": ip,
    }


def probe_snmp_entity(ip, snmp):
    entity = ORIG_V2_PROBE_SNMP_ENTITY(ip, snmp)
    printer_row = probe_snmp_printer_identity(ip, snmp)
    if not printer_row:
        return entity

    inventory = list(entity.get("inventory") or [])
    inventory.append(printer_row)
    entity["inventory"] = inventory
    entity["count"] = len(inventory)

    primary = entity.get("primary") or {}
    primary_has_identity = any(clean(primary.get(key)) for key in ("manufacturer", "model", "serial"))
    if not primary_has_identity:
        entity["primary"] = printer_row
    return entity


def main():
    old_probe = v2.probe_snmp_entity
    old_version = v3.DISCOVERY_WRAPPER_VERSION
    try:
        v2.probe_snmp_entity = probe_snmp_entity
        v3.DISCOVERY_WRAPPER_VERSION = DISCOVERY_WRAPPER_VERSION
        return v3.main()
    finally:
        v3.DISCOVERY_WRAPPER_VERSION = old_version
        v2.probe_snmp_entity = old_probe


if __name__ == "__main__":
    sys.exit(main())
