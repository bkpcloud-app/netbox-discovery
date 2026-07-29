#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, "..", ".."))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.inventory import classifier_v2 as v2
from modules.inventory import classifier_v3 as v3
from modules.inventory import classifier_v5 as v5

CLASSIFIER_VERSION = "5.1-product"
MOXA_NPORT_5210_OID = ".1.3.6.1.4.1.8691.2.7"
ORIG_CLASSIFY_DEVICE = v3.classify_device


def clean(value):
    return "" if value is None else str(value).strip()


def _append_evidence(row, text):
    evidence = list(row.get("evidence") or [])
    if text not in evidence:
        evidence.append(text)
    row["evidence"] = evidence


def _norm_serial(value):
    return v2.base.norm_serial(value)


def _printer_row(discovery):
    rows = []
    primary = discovery.get("snmp_entity_primary") or {}
    if primary:
        rows.append(primary)
    rows.extend(discovery.get("snmp_entity_inventory") or [])
    for row in rows:
        if clean(row.get("source")) == "printer-mib":
            return row
    return {}


def _apply_printer_mib(out, discovery, printer):
    out["role"] = "PRINTER"
    out["asset_class"] = "PHYSICAL_DEVICE"
    out["classification_score"] = max(int(out.get("classification_score") or 0), 96)
    out["confidence"] = "HIGH"
    out["classification_state"] = "IDENTIFIED"
    out["printer_mib_detected"] = True
    out["printer_mib_name"] = clean(printer.get("printer_mib_name") or printer.get("name"))
    out["printer_mib_serial"] = clean(printer.get("printer_mib_serial") or printer.get("serial"))

    manufacturer = v2.normalize_manufacturer(printer.get("manufacturer"))
    model = clean(printer.get("model"))
    serial = _norm_serial(printer.get("serial") or printer.get("printer_mib_serial"))
    name = clean(printer.get("name") or printer.get("printer_mib_name"))

    if manufacturer:
        out["manufacturer"] = manufacturer
        out["manufacturer_source"] = "printer-mib"
    if model:
        out["model"] = model[:120]
        out["model_source"] = "printer-mib"
    if serial:
        out["serial"] = serial
        out["serial_source"] = "printer-mib"
    if name and not clean(out.get("hostname")):
        out["hostname"] = name
        out["hostname_source"] = "printer-mib"

    _append_evidence(out, "Printer-MIB identity")
    if manufacturer:
        _append_evidence(out, "manufacturer:printer-mib")
    if model:
        _append_evidence(out, "model:printer-mib")
    if serial:
        _append_evidence(out, "serial:printer-mib")


def _apply_moxa_nport(out, discovery):
    object_id = clean(discovery.get("snmp_object_id"))
    name = clean(discovery.get("snmp_name") or discovery.get("reverse_dns"))
    exact_oid = object_id == MOXA_NPORT_5210_OID
    strong_name = bool(re.search(r"\bNP\s*-?\s*5210\b", name, re.I)) and object_id.startswith(".1.3.6.1.4.1.8691")
    if not (exact_oid or strong_name):
        return

    out["role"] = "INDUSTRIAL_COMMUNICATION"
    out["manufacturer"] = "Moxa"
    out["manufacturer_source"] = "sysobjectid:nport-5210"
    out["model"] = "NPort 5210"
    out["model_source"] = "sysobjectid:nport-5210"
    out["asset_class"] = "PHYSICAL_DEVICE"
    out["classification_score"] = max(int(out.get("classification_score") or 0), 98)
    out["confidence"] = "HIGH"
    out["classification_state"] = "IDENTIFIED"
    _append_evidence(out, "Moxa NPort 5210 exact SNMP identity")


def classify_device(discovery):
    out = ORIG_CLASSIFY_DEVICE(discovery)
    printer = _printer_row(discovery)
    if printer:
        _apply_printer_mib(out, discovery, printer)
    _apply_moxa_nport(out, discovery)
    out["classification_version"] = CLASSIFIER_VERSION
    return out


def main(argv=None):
    old_classify = v3.classify_device
    old_version = v5.CLASSIFIER_VERSION
    try:
        v3.classify_device = classify_device
        v5.CLASSIFIER_VERSION = CLASSIFIER_VERSION
        return v5.main(argv)
    finally:
        v3.classify_device = old_classify
        v5.CLASSIFIER_VERSION = old_version


if __name__ == "__main__":
    sys.exit(main())
