#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import re


GENERIC_MANUFACTURERS = {"", "generic", "unidentified", "unknown"}
GENERIC_MODELS = {"", "generic printer", "generic unknown", "unknown", "unknown server"}


def clean(value):
    return "" if value is None else str(value).strip()


def _compact_text(*values):
    return " ".join(clean(value) for value in values if clean(value))


def _first_match(patterns, text):
    for pattern, formatter in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return formatter(match)
    return ""


def _clean_model(value):
    value = re.sub(r"\s+", " ", clean(value)).strip(" .,:;/")
    return value[:120]


def _model_from_text(text):
    patterns = [
        (r"\b(ECOSYS\s+[A-Z]{1,4}\d{3,5}[A-Z0-9-]*)\b", lambda m: m.group(1).upper()),
        (r"\b(TASKalfa\s+\d{3,5}[A-Z0-9-]*)\b", lambda m: "TASKalfa " + m.group(1).split(None, 1)[1].upper()),
        (r"\b((?:BM|BP|CM|CP|M|P)\d{4}[A-Z0-9]*)\b", lambda m: m.group(1).upper()),
        (r"\b(SL-[A-Z]\d{4}[A-Z0-9-]*)\b", lambda m: m.group(1).upper()),
        (r"\b((?:MFC|DCP|HL|ADS|QL|TD|RJ|PJ)-?[A-Z0-9]{3,})\b", lambda m: m.group(1).upper()),
        (r"\b((?:imageRUNNER|imageCLASS|i-SENSYS|MAXIFY|PIXMA)\s+[A-Z0-9][A-Z0-9-]*)\b", lambda m: m.group(1)),
        (r"\b((?:EcoTank|WorkForce(?:\s+Pro)?|SureColor)\s+[A-Z0-9][A-Z0-9-]*)\b", lambda m: m.group(1)),
        (r"\b((?:LaserJet|OfficeJet|PageWide|DesignJet)(?:\s+(?:Pro|Enterprise|Managed))?\s+[A-Z0-9][A-Z0-9-]{1,20})\b", lambda m: "HP " + m.group(1)),
    ]
    model = _first_match(patterns, text)
    if model:
        return _clean_model(model)

    lower = text.lower()
    vendor_scoped = [
        ("ricoh", r"\b((?:IM|MP|M|P|SP|MPC)\s?C?\d{3,5}[A-Z]*)\b"),
        ("lexmark", r"\b([A-Z]{1,3}\d{3,4}[A-Z]?)\b"),
        ("oki", r"\b((?:MC|MB|C|B)\d{3,4}[A-Z]*)\b"),
        ("zebra", r"\b((?:ZT|ZD|GK|GX|ZQ)\d{3,4}[A-Z0-9-]*)\b"),
        ("xerox", r"\b((?:VersaLink|WorkCentre|AltaLink|Phaser)\s+[A-Z0-9][A-Z0-9-]*)\b"),
    ]
    for vendor, pattern in vendor_scoped:
        if vendor not in lower:
            continue
        match = re.search(pattern, text, re.I)
        if match:
            return _clean_model(match.group(1))
    return ""


def _manufacturer_from_model(model):
    value = clean(model).lower()
    if not value:
        return ""
    rules = [
        (("ecosys ", "taskalfa "), "Kyocera"),
        (("bm", "bp", "cm", "cp"), "Pantum"),
        (("sl-",), "Samsung"),
        (("mfc", "dcp", "hl", "ads", "ql", "td", "rj", "pj"), "Brother"),
        (("imagerunner", "imageclass", "i-sensys", "maxify", "pixma"), "Canon"),
        (("ecotank", "workforce", "surecolor"), "Epson"),
        (("hp laserjet", "hp officejet", "hp pagewide", "hp designjet"), "HP"),
    ]
    for prefixes, manufacturer in rules:
        if any(value.startswith(prefix) for prefix in prefixes):
            return manufacturer
    return ""


def _manufacturer_from_text(text):
    lower = text.lower()
    rules = [
        (("kyocera", "ecosys", "taskalfa"), "Kyocera"),
        (("pantum",), "Pantum"),
        (("brother",), "Brother"),
        (("epson", "ecotank", "workforce"), "Epson"),
        (("canon", "imagerunner", "imageclass", "i-sensys", "maxify", "pixma"), "Canon"),
        (("ricoh",), "Ricoh"),
        (("lexmark",), "Lexmark"),
        (("xerox", "versalink", "workcentre", "altalink", "phaser"), "Xerox"),
        (("zebra",), "Zebra"),
        (("oki", "oki data"), "OKI"),
        (("samsung", "syncthru"), "Samsung"),
        (("hewlett packard", "hewlett-packard", "hp laserjet", "jetdirect", "officejet", "pagewide", "designjet"), "HP"),
    ]
    for markers, manufacturer in rules:
        if any(marker in lower for marker in markers):
            return manufacturer
    if re.search(r"(?:^|\s)SEC[0-9A-F]{12}(?:\s|$)", text, re.I):
        return "Samsung"
    return ""


def infer(*values):
    """Return conservative printer manufacturer/model identity from observed text.

    Exact models are accepted only from strict vendor-family grammars. A vendor
    may be returned without a model (for example ECOSYS or SEC<MAC>), but this
    helper never invents an exact model from an IP-shaped hostname.
    """
    text = _compact_text(*values)
    model = _model_from_text(text)
    manufacturer = _manufacturer_from_model(model) or _manufacturer_from_text(text)
    evidence = []
    if manufacturer:
        evidence.append("printer manufacturer fingerprint")
    if model:
        evidence.append("printer exact model fingerprint")
    return {
        "manufacturer": manufacturer,
        "model": model,
        "evidence": evidence,
    }


def is_specific_manufacturer(value):
    return clean(value).lower() not in GENERIC_MANUFACTURERS


def is_specific_model(value):
    return clean(value).lower() not in GENERIC_MODELS
