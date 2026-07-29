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
from modules.inventory import classifier_v5 as v5
from modules.inventory import printer_identity

CLASSIFIER_VERSION = "6.0-product"
MOXA_NPORT_5210_OID = ".1.3.6.1.4.1.8691.2.7"
ORIG_V2_CLASSIFY_DEVICE = v2.classify_device


def clean(value):
    return "" if value is None else str(value).strip()


def _append_evidence(row, marker):
    evidence = list(row.get("evidence") or [])
    if marker and marker not in evidence:
        evidence.append(marker)
    row["evidence"] = evidence


def _service_ports(d, protocol="tcp"):
    return set(
        int(item.get("port"))
        for item in (d.get("open_services") or [])
        if item.get("protocol") == protocol and str(item.get("port") or "").isdigit()
    )


def _printer_rows(d):
    return [
        item for item in (d.get("snmp_entity_inventory") or [])
        if clean(item.get("source")) == "printer-mib"
    ]


def _printer_text(d, rows):
    parts = [
        clean(d.get("reverse_dns")), clean(d.get("snmp_name")),
        clean(d.get("snmp_description")), clean(d.get("snmp_object_id")),
        clean(d.get("mac_vendor")),
    ]
    for item in rows:
        parts.extend([
            clean(item.get("name")), clean(item.get("manufacturer")),
            clean(item.get("model")), clean(item.get("serial")),
            " ".join(clean(value) for value in (item.get("printer_descriptions") or [])),
        ])
    for service in d.get("open_services") or []:
        parts.extend([
            clean(service.get("service")), clean(service.get("product")),
            clean(service.get("version")), clean(service.get("extrainfo")),
            " ".join(clean(value) for value in (service.get("scripts") or {}).values()),
        ])
    return " ".join(value for value in parts if value)


def _best_printer_serial(rows):
    for item in rows:
        serial = v2.base.norm_serial(item.get("serial"))
        if serial:
            return serial
    return ""


def _apply_printer_identity(d, out):
    rows = _printer_rows(d)
    text = _printer_text(d, rows)
    identity = printer_identity.infer(text)
    tcp = _service_ports(d, "tcp")
    print_service = bool({515, 631, 9100} & tcp)
    current_role = clean(out.get("role"))

    # Printer-MIB, an exact printer family/model, or an already classified
    # printer with a vendor fingerprint are required. Open port 9100 alone does
    # not fabricate manufacturer/model identity.
    strong_identity = bool(rows or identity.get("model"))
    vendor_identity = bool(identity.get("manufacturer"))
    if not strong_identity and not (current_role == "PRINTER" and vendor_identity):
        return out
    if current_role != "PRINTER" and not (print_service and (strong_identity or vendor_identity)):
        return out

    out["role"] = "PRINTER"
    out["asset_class"] = "PHYSICAL_DEVICE"
    out["classification_score"] = max(int(out.get("classification_score") or 0), 96 if strong_identity else 92)
    out["confidence"] = "HIGH"
    out["classification_state"] = "IDENTIFIED"

    manufacturer = clean(identity.get("manufacturer"))
    model = clean(identity.get("model"))
    if manufacturer:
        out["manufacturer"] = manufacturer
        out["manufacturer_source"] = "printer-mib/fingerprint" if rows else "printer-fingerprint"
        _append_evidence(out, "manufacturer:{0}".format(out["manufacturer_source"]))
    if model:
        out["model"] = model
        out["model_source"] = "printer-mib/fingerprint" if rows else "printer-fingerprint"
        _append_evidence(out, "model:{0}".format(out["model_source"]))

    serial = _best_printer_serial(rows)
    if serial:
        current_serial = v2.base.norm_serial(out.get("serial"))
        if not current_serial or current_serial == serial:
            out["serial"] = serial
            out["serial_source"] = "printer-mib"
            _append_evidence(out, "serial:printer-mib")

    _append_evidence(out, "Printer identity from standard read-only MIB/fingerprint")
    return out


def _apply_moxa_nport_5210(d, out):
    object_id = clean(d.get("snmp_object_id"))
    names = " ".join([
        clean(d.get("snmp_name")), clean(d.get("reverse_dns")),
        clean(out.get("hostname")), clean(d.get("snmp_description")),
    ])
    if object_id != MOXA_NPORT_5210_OID or not re.search(r"\bNP?5210(?:[_-]|\b)", names, re.I):
        return out

    out["role"] = "INDUSTRIAL_COMMUNICATION"
    out["manufacturer"] = "Moxa"
    out["manufacturer_source"] = "sysobjectid+nport-name"
    out["model"] = "NPort 5210"
    out["model_source"] = "sysobjectid+nport-name"
    out["asset_class"] = "PHYSICAL_DEVICE"
    out["classification_score"] = max(int(out.get("classification_score") or 0), 98)
    out["confidence"] = "HIGH"
    out["classification_state"] = "IDENTIFIED"
    _append_evidence(out, "Moxa NPort 5210 exact sysObjectID + NP5210 identity")
    return out


def classify_device(d):
    out = ORIG_V2_CLASSIFY_DEVICE(d)
    out = _apply_printer_identity(d, out)
    out = _apply_moxa_nport_5210(d, out)
    out["classification_version"] = CLASSIFIER_VERSION
    return out


def main(argv=None):
    old_classify = v2.classify_device
    old_version = v5.CLASSIFIER_VERSION
    try:
        v2.classify_device = classify_device
        v5.CLASSIFIER_VERSION = CLASSIFIER_VERSION
        return v5.main(argv)
    finally:
        v5.CLASSIFIER_VERSION = old_version
        v2.classify_device = old_classify


if __name__ == "__main__":
    sys.exit(main())
