#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import ipaddress
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, "..", ".."))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.inventory import classifier_v7 as v7

CLASSIFIER_VERSION = "5.6-product"
ORIG_CLASSIFY_DEVICE = v7.classify_device
ORIG_VALIDATE_SERIAL = v7._validate_serial

PROTECTED_NON_WINDOWS_ROLES = set(v7.PHYSICAL_ROLES) | {
    "HYPERVISOR", "OOB_MANAGEMENT", "VMWARE_APPLIANCE",
    "MANAGEMENT_APPLIANCE", "SECURITY_APPLIANCE", "POWER_MANAGEMENT",
}

EXTRA_SERIAL_PLACEHOLDERS = {
    "123456789012", "012345678901", "000000000001", "999999999999",
    "NOTAVAILABLE", "NOTAPPLICABLE", "UNAVAILABLE", "UNSPECIFIED",
}

PRINTER_HOSTNAME_PATTERNS = {
    "Samsung": (r"^SEC[0-9A-F]{8,}$",),
    "Brother": (r"^BRN[0-9A-F]{8,}$",),
    "HP": (r"^NPI[0-9A-F]{6,}$",),
    "Xerox": (r"^XRX[0-9A-F]{8,}$",),
    "Epson": (r"^EPSON[0-9A-F]{6,}$",),
    "Canon": (r"^CANON[0-9A-F]{6,}$",),
}


def clean(value):
    return "" if value is None else str(value).strip()


def norm(value):
    return re.sub(r"\s+", " ", clean(value)).strip().casefold()


def _has_explicit_windows_evidence(discovery):
    for evidence in v7._windows_evidence(discovery):
        family, product = v7._canonical_windows(evidence.get("text"))
        if family and product and int(evidence.get("rank") or 0) >= 95:
            return True
    return False


def _mac_shaped(value):
    """Accept only values whose original syntax is actually MAC-like."""
    raw = clean(value)
    patterns = (
        r"^[0-9A-Fa-f]{12}$",
        r"^(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$",
        r"^[0-9A-Fa-f]{4}(?:\.[0-9A-Fa-f]{4}){2}$",
    )
    return any(re.match(pattern, raw) for pattern in patterns)


def _validate_serial(value, contexts):
    serial = v7.identity.norm_serial(value)
    if not serial:
        return "", "empty-or-generic"
    if serial in v7.SERIAL_PLACEHOLDERS or serial in EXTRA_SERIAL_PLACEHOLDERS:
        return "", "known-placeholder"
    if len(serial) < 5:
        return "", "too-short"
    if len(serial) > 64:
        return "", "too-long"
    if len(set(serial)) == 1:
        return "", "repeated-character"
    if serial in ("ABCDEF", "ABCDEFG", "ABCDEFGHIJ"):
        return "", "sequential-placeholder"
    if serial in contexts:
        return "", "duplicates-model-name-ip-or-mac"
    try:
        ipaddress.ip_address(clean(value))
        return "", "ip-address"
    except Exception:
        pass
    if _mac_shaped(value) and v7.identity.norm_mac(value):
        return "", "mac-address"
    return serial, ""


def _dedupe_serial_rejections(out):
    unique = []
    seen = set()
    for item in out.get("serial_rejections") or []:
        if not isinstance(item, dict):
            continue
        marker = (v7.identity.norm_serial(item.get("value")), clean(item.get("reason")))
        if marker in seen:
            continue
        seen.add(marker)
        unique.append(item)
    out["serial_rejections"] = unique[:12]


def _printer_model_is_hostname(model, manufacturer, names):
    model_norm = norm(model)
    if not model_norm:
        return False
    name_norms = set(norm(value) for value in names if norm(value))
    if model_norm not in name_norms:
        return False
    vendor = v7.identity.canonical_manufacturer(manufacturer)
    compact = re.sub(r"[^A-Za-z0-9]", "", clean(model)).upper()
    return any(
        re.match(pattern, compact, re.I)
        for pattern in PRINTER_HOSTNAME_PATTERNS.get(vendor, ())
    )


def _sanitize_printer_model(discovery, out):
    if clean(out.get("role")) != "PRINTER":
        return
    model = clean(out.get("model"))
    if not model:
        return
    names = [
        out.get("observed_name"), out.get("hostname"),
        discovery.get("snmp_name"), discovery.get("reverse_dns"),
    ]
    if not _printer_model_is_hostname(model, out.get("manufacturer"), names):
        return
    out["model_rejection"] = {
        "value": model,
        "reason": "printer-hostname-not-model",
    }
    out["model"] = ""
    out["model_source"] = ""
    provenance = dict(out.get("identity_provenance") or {})
    provenance["model"] = "rejected-hostname-like-model"
    out["identity_provenance"] = provenance


def _prefer_specific_serial_source(discovery, out):
    """Keep the most specific authoritative source for the chosen serial."""
    selected = v7.identity.norm_serial(out.get("serial"))
    if not selected:
        return

    matches = []
    for service in discovery.get("open_services") or []:
        for script_name, script_value in (service.get("scripts") or {}).items():
            low = clean(script_name).casefold()
            if not any(token in low for token in ("onvif", "hikvision", "isapi")):
                continue
            for value in v7._extract_labeled_serials(script_value):
                if v7.identity.norm_serial(value) != selected:
                    continue
                if "hikvision" in low or "isapi" in low:
                    matches.append((3, "onvif-hikvision-device-info"))
                else:
                    matches.append((2, "onvif-device-information"))

    if not matches:
        return
    matches.sort(reverse=True)
    out["serial_source"] = matches[0][1]
    out["serial_confidence"] = "HIGH"


def classify_device(discovery):
    old_validate = v7._validate_serial
    try:
        v7._validate_serial = _validate_serial
        out = ORIG_CLASSIFY_DEVICE(discovery)
    finally:
        v7._validate_serial = old_validate

    _dedupe_serial_rejections(out)
    _sanitize_printer_model(discovery, out)
    _prefer_specific_serial_source(discovery, out)

    if out.get("windows_family"):
        out["classification_version"] = CLASSIFIER_VERSION
        return out
    if not _has_explicit_windows_evidence(discovery):
        out["classification_version"] = CLASSIFIER_VERSION
        return out

    role = clean(out.get("role"))
    if role in PROTECTED_NON_WINDOWS_ROLES:
        out["classification_version"] = CLASSIFIER_VERSION
        return out

    original_role = role
    out["role"] = "WINDOWS_HOST"
    v7._refine_windows(discovery, out)

    if clean(out.get("windows_family")) == "CONFLICT":
        out["role"] = "WINDOWS_HOST"
        out["platform"] = "Windows"
        out["classification_state"] = "REVIEW"
        out["confidence"] = "MEDIUM"
        out["classification_score"] = min(int(out.get("classification_score") or 70), 70)
    elif not out.get("windows_family"):
        out["role"] = original_role or "WINDOWS_HOST"

    out["classification_version"] = CLASSIFIER_VERSION
    return out


def main(argv=None):
    old_classify = v7.classify_device
    old_version = v7.CLASSIFIER_VERSION
    old_validate = v7._validate_serial
    try:
        v7.classify_device = classify_device
        v7.CLASSIFIER_VERSION = CLASSIFIER_VERSION
        v7._validate_serial = _validate_serial
        return v7.main(argv)
    finally:
        v7._validate_serial = old_validate
        v7.classify_device = old_classify
        v7.CLASSIFIER_VERSION = old_version


if __name__ == "__main__":
    sys.exit(main())
