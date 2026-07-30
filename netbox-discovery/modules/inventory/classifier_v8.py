#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, "..", ".."))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.inventory import classifier_v7 as v7

CLASSIFIER_VERSION = "5.4-product"
ORIG_CLASSIFY_DEVICE = v7.classify_device

PROTECTED_NON_WINDOWS_ROLES = set(v7.PHYSICAL_ROLES) | {
    "HYPERVISOR", "OOB_MANAGEMENT", "VMWARE_APPLIANCE",
    "MANAGEMENT_APPLIANCE", "SECURITY_APPLIANCE", "POWER_MANAGEMENT",
}


def clean(value):
    return "" if value is None else str(value).strip()


def _has_explicit_windows_evidence(discovery):
    for evidence in v7._windows_evidence(discovery):
        family, product = v7._canonical_windows(evidence.get("text"))
        if family and product and int(evidence.get("rank") or 0) >= 95:
            return True
    return False


def _prefer_specific_serial_source(discovery, out):
    """Keep the most specific authoritative source for the chosen serial.

    CLASSIFY V7 correctly ranks ONVIF/Hikvision above generic ENTITY-MIB, but
    both anonymous device-information variants previously collapsed into a
    generic ONVIF label. Preserve whether the serial came from Hikvision
    ISAPI/Hikvision enrichment or generic ONVIF so the PLAN is auditable.
    """
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
    out = ORIG_CLASSIFY_DEVICE(discovery)
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

    # The legacy classifier may leave a host UNKNOWN because its SMB text says
    # "Windows Server" or "Windows 11" instead of the literal phrase
    # "Microsoft Windows". Explicit high-authority SMB/CPE evidence is enough
    # to enter the Windows refinement gate, but not enough to override a
    # protected network/storage/industrial/OOB role.
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
    try:
        v7.classify_device = classify_device
        v7.CLASSIFIER_VERSION = CLASSIFIER_VERSION
        return v7.main(argv)
    finally:
        v7.classify_device = old_classify
        v7.CLASSIFIER_VERSION = old_version


if __name__ == "__main__":
    sys.exit(main())
