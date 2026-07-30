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
from modules.product import identity

DISCOVERY_WRAPPER_VERSION = "4.4-product"
PRT_GENERAL_ROOT = ".1.3.6.1.2.1.43.5.1.1"
PRT_NAME_COLUMN = "16"
PRT_SERIAL_COLUMN = "17"
HR_DEVICE_DESCR = ".1.3.6.1.2.1.25.3.2.1.3"
ORIG_PROBE_SNMP_ENTITY = v2.probe_snmp_entity

SERIAL_PLACEHOLDERS = {
    "03000000", "12345678", "123456789", "1234567890", "0123456789",
    "00000001", "99999999", "XXXXXXXX", "TEST", "DEMO",
}


def clean(value):
    return "" if value is None else str(value).strip()


def _walk_column(rows, root, column):
    prefix = root + "." + column + "."
    values = []
    for oid, value_type, value in rows:
        if oid.startswith(prefix) and base.valid_snmp_value(value):
            item = clean(value)
            if item and item not in values:
                values.append(item)
    return values


def _printer_manufacturer(text):
    low = clean(text).lower()
    rules = (
        (("kyocera", "ecosys", "taskalfa"), "Kyocera"),
        (("hewlett-packard", "hewlett packard", "hp laserjet", "hp officejet", "hp pagewide", "jetdirect"), "HP"),
        (("brother",), "Brother"),
        (("epson", "workforce", "ecotank"), "Epson"),
        (("canon", "imagerunner", "i-sensys", "pixma"), "Canon"),
        (("ricoh", "aficio"), "Ricoh"),
        (("lexmark",), "Lexmark"),
        (("xerox", "versalink", "workcentre", "phaser"), "Xerox"),
        (("samsung", "proxpress"), "Samsung"),
        (("pantum",), "Pantum"),
        (("zebra",), "Zebra Technologies"),
        (("oki", "oki data"), "OKI"),
    )
    for terms, manufacturer in rules:
        if any(term in low for term in terms):
            return manufacturer
    return ""


def _first(patterns, text):
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return clean(match.group(1))[:120]
    return ""


def _printer_model(text, manufacturer):
    patterns = {
        "Kyocera": [r"\b((?:ECOSYS|TASKalfa)\s*[A-Z0-9][A-Z0-9._-]*(?:\s+[A-Z0-9][A-Z0-9._-]*)?)\b"],
        "HP": [r"\b((?:HP\s+)?(?:LaserJet|OfficeJet|PageWide|DesignJet)\s+(?:Pro\s+|Enterprise\s+|Managed\s+)?[A-Z0-9][A-Z0-9 ._-]{1,45})"],
        "Brother": [r"\b((?:MFC|DCP|HL|QL|TD|RJ)-?[A-Z0-9][A-Z0-9-]{2,})\b"],
        "Epson": [
            r"\b((?:WorkForce|EcoTank)\s+[A-Z0-9][A-Z0-9 ._-]{1,35})",
            r"\b((?:L|M|WF|ET|LQ|TM)-?[0-9][A-Z0-9-]{2,})\b",
        ],
        "Canon": [
            r"\b((?:imageRUNNER|i-SENSYS|PIXMA)\s+[A-Z0-9][A-Z0-9 ._-]{1,40})",
            r"\b((?:MF|LBP|IR|C)[0-9][A-Z0-9-]{2,})\b",
        ],
        "Ricoh": [r"\b((?:Aficio\s+)?(?:MP|IM|SP|M)\s*[A-Z0-9][A-Z0-9._-]{2,})\b"],
        "Lexmark": [r"\b((?:MS|MX|CS|CX|MB|MC)[0-9][A-Z0-9-]{2,})\b"],
        "Xerox": [r"\b((?:VersaLink|WorkCentre|Phaser|AltaLink)\s+[A-Z0-9][A-Z0-9 ._-]{1,35})"],
        "Samsung": [r"\b((?:ProXpress\s+)?(?:SL-)?[A-Z]{1,3}[0-9][A-Z0-9-]{2,})\b"],
        "Pantum": [r"\b((?:BM|M|P|CP|CM)[0-9][A-Z0-9-]{2,})\b"],
        "Zebra Technologies": [r"\b((?:ZT|ZD|GK|GX|ZE|ZQ)[0-9][A-Z0-9-]{2,})\b"],
        "OKI": [r"\b((?:C|B|MC|MB|ES)[0-9][A-Z0-9-]{2,})\b"],
    }
    return _first(patterns.get(manufacturer, []), clean(text))


def _serial_valid(value, context=""):
    serial = identity.norm_serial(value)
    if not serial or serial in SERIAL_PLACEHOLDERS:
        return ""
    if len(serial) < 5 or len(serial) > 64:
        return ""
    if len(set(serial)) == 1:
        return ""
    if serial in ("ABCDEF", "ABCDEFG", "ABCDEFGHIJ"):
        return ""
    compact_context = identity.norm_serial(context)
    if compact_context and serial == compact_context:
        return ""
    return serial


def _extract_labeled_serials(text):
    values = []
    patterns = (
        r"(?:Serial(?:\s+Number|\s+No\.?|Number)?|Device\s+Serial(?:\s+No\.?)?|S/N)\s*[:=#-]\s*([A-Za-z0-9][A-Za-z0-9._/-]{3,63})",
        r"<(?:serialNumber|SerialNumber|SerialNO|serialNo)>\s*([^<]{4,64})\s*</",
        r"[\"'](?:serialNumber|serial_no|serialNo|SerialNO)[\"']\s*:\s*[\"']([^\"']{4,64})[\"']",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, clean(text), re.I):
            value = clean(match.group(1))
            if value and value not in values:
                values.append(value)
    return values


def _best_printer_serial(raw_serials, text, manufacturer, model, name):
    candidates = []

    def add(value, source, rank):
        serial = _serial_valid(value, model or name or manufacturer)
        if not serial:
            return
        existing = next((row for row in candidates if row[0] == serial), None)
        if existing is None:
            candidates.append((serial, source, rank))
            return
        if rank > existing[2]:
            candidates.remove(existing)
            candidates.append((serial, source, rank))

    for value in raw_serials:
        add(value, "printer-mib", 100)
    for value in _extract_labeled_serials(text):
        add(value, "printer-description", 88)

    candidates.sort(key=lambda row: (row[2], len(row[0])), reverse=True)
    if not candidates:
        return "", [], ""
    return candidates[0][0], [row[0] for row in candidates], candidates[0][1]


def _printer_entity(ip, snmp):
    if not snmp.get("available"):
        return {}
    version_option, community = base.snmp_command_context(snmp)
    rows = base._snmp_walk(ip, version_option, community, PRT_GENERAL_ROOT, timeout=8)
    names = _walk_column(rows, PRT_GENERAL_ROOT, PRT_NAME_COLUMN)
    serials = _walk_column(rows, PRT_GENERAL_ROOT, PRT_SERIAL_COLUMN)
    if not names and not serials:
        return {}

    hr_rows = base._snmp_walk(ip, version_option, community, HR_DEVICE_DESCR, timeout=8)
    hr_values = [clean(value) for oid, value_type, value in hr_rows if base.valid_snmp_value(value)]
    text = " ".join([
        clean(snmp.get("sysname")), clean(snmp.get("sysdescr")),
        " ".join(names), " ".join(hr_values), " ".join(serials),
    ])
    manufacturer = _printer_manufacturer(text)
    model = _printer_model(text, manufacturer)
    name = names[0] if names else clean(snmp.get("sysname"))
    serial, serial_candidates, serial_source = _best_printer_serial(serials, text, manufacturer, model, name)

    return {
        "index": "printer-mib:1",
        "description": "Printer-MIB managed printer",
        "contained_in": "",
        "class": "chassis(3)",
        "class_id": "3",
        "parent_rel_pos": "",
        "name": name,
        "hardware_rev": "",
        "firmware_rev": "",
        "software_rev": "",
        "serial": serial,
        "manufacturer": manufacturer,
        "model": model,
        "alias": "",
        "asset_id": "PRINTER-MIB:{0}".format(serial or name or ip),
        "is_fru": "",
        "source": "printer-mib",
        "management_ip": ip,
        "printer_mib_name": name,
        "printer_mib_serial": serial,
        "printer_mib_serial_source": serial_source,
        "printer_mib_serial_candidates": serial_candidates,
        "printer_mib_text": text[:1000],
    }


def probe_snmp_entity(ip, snmp):
    entity = ORIG_PROBE_SNMP_ENTITY(ip, snmp)
    printer = _printer_entity(ip, snmp)
    if not printer:
        return entity
    inventory = list(entity.get("inventory") or [])
    inventory.append(printer)
    entity["inventory"] = inventory
    entity["count"] = len(inventory)
    if printer.get("model") or printer.get("serial") or printer.get("manufacturer"):
        entity["primary"] = printer
    return entity


def main():
    old_probe = v2.probe_snmp_entity
    old_version = v3.DISCOVERY_WRAPPER_VERSION
    try:
        v2.probe_snmp_entity = probe_snmp_entity
        v3.DISCOVERY_WRAPPER_VERSION = DISCOVERY_WRAPPER_VERSION
        return v3.main()
    finally:
        v2.probe_snmp_entity = old_probe
        v3.DISCOVERY_WRAPPER_VERSION = old_version


if __name__ == "__main__":
    sys.exit(main())
