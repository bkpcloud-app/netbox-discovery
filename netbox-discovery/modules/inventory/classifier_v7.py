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

from modules.inventory import classifier_v6 as v6
from modules.product import identity

CLASSIFIER_VERSION = "5.2-product"
ORIG_CLASSIFY_DEVICE = v6.classify_device

PHYSICAL_ROLES = {
    "NETWORK_SWITCH", "WIRELESS_AP", "WIRELESS_BRIDGE", "FIREWALL",
    "PRINTER", "CAMERA", "NVR", "DVR", "VIDEO_ENCODER",
    "VIDEO_SURVEILLANCE_DEVICE", "OOB_MANAGEMENT", "STORAGE",
    "INDUSTRIAL_PLC", "INDUSTRIAL_IO", "INDUSTRIAL_SWITCH",
    "INDUSTRIAL_COMMUNICATION", "INDUSTRIAL_POWER_METER",
    "INDUSTRIAL_DRIVE", "INDUSTRIAL_MOTOR_PROTECTION",
    "INDUSTRIAL_CONTROLLER", "INDUSTRIAL_DEVICE",
}

CCTV_MANUFACTURERS = {
    "Hikvision", "Dahua", "Intelbras", "Axis Communications", "Vivotek",
    "Uniview", "Reolink", "Hanwha Vision", "Bosch Security Systems",
    "Ubiquiti", "TP-Link",
}

SERIAL_PLACEHOLDERS = {
    "03000000",  # Pantum live evidence: factory/default value, not asset identity.
}


def clean(value):
    return "" if value is None else str(value).strip()


def _candidate_rank(candidate):
    return (
        int(candidate.get("score") or 0),
        1 if candidate.get("serial") else 0,
        1 if candidate.get("model") else 0,
        1 if candidate.get("manufacturer") else 0,
    )


def _script_names(discovery):
    values = []
    for service in discovery.get("open_services") or []:
        for name in (service.get("scripts") or {}).keys():
            low = clean(name).lower()
            if low and low not in values:
                values.append(low)
    return values


def _valid_cctv_candidate(discovery, candidate):
    """Reject generic WS-Discovery/UPnP and arbitrary MAC OUI as CCTV proof."""
    if not candidate:
        return False
    source = clean(candidate.get("source"))
    model = clean(candidate.get("model"))
    manufacturer = identity.canonical_manufacturer(candidate.get("manufacturer"))
    text = identity.norm(identity.evidence_text(discovery))
    scripts = _script_names(discovery)

    explicit_video = any(token in text for token in (
        "networkvideotransmitter", "networkvideorecorder",
        "network video transmitter", "network video recorder",
        "network camera", "ip camera", "video encoder",
        " type:camera", " type:nvr", " type:dvr", "/onvif/",
    ))
    onvif_script = any("onvif" in name for name in scripts)

    if source == "onvif-device-information":
        return bool(onvif_script or explicit_video or "onvif" in text)

    if source == "cctv-fingerprint":
        if model:
            return True
        if manufacturer not in CCTV_MANUFACTURERS:
            return False
        rtsp_signal = "rtsp" in text or any("rtsp" in name for name in scripts)
        return bool(explicit_video or onvif_script or (rtsp_signal and manufacturer in CCTV_MANUFACTURERS))

    return False


def _normalize_model(manufacturer, model):
    value = re.sub(r"\s+", " ", clean(model)).strip()
    vendor = identity.canonical_manufacturer(manufacturer)
    if vendor == "Kyocera":
        match = re.search(r"\b(ECOSYS|TASKalfa)\s+([A-Z0-9][A-Z0-9._-]*)", value, re.I)
        if match:
            family = "ECOSYS" if match.group(1).lower() == "ecosys" else "TASKalfa"
            return "{0} {1}".format(family, match.group(2))[:120]
    return value[:120]


def _sanitize_identity(out):
    out["model"] = _normalize_model(out.get("manufacturer"), out.get("model"))
    serial = identity.norm_serial(out.get("serial"))
    if serial in SERIAL_PLACEHOLDERS:
        out["serial"] = ""
        out["serial_source"] = "rejected-placeholder"
        evidence = list(out.get("evidence") or [])
        marker = "Rejected placeholder serial: {0}".format(serial)
        if marker not in evidence:
            evidence.append(marker)
        out["evidence"] = evidence
    return out


def classify_device(discovery):
    out = ORIG_CLASSIFY_DEVICE(discovery)

    candidates = []
    industrial = identity.industrial_identity(discovery)
    cctv = identity.cctv_identity(discovery)
    if industrial:
        candidates.append(industrial)
    if _valid_cctv_candidate(discovery, cctv):
        candidates.append(cctv)

    if candidates:
        candidates.sort(key=_candidate_rank, reverse=True)
        identity.apply_identity_candidate(out, candidates[0])
        out["identity_candidates"] = [
            {
                "source": row.get("source"),
                "role": row.get("role"),
                "manufacturer": row.get("manufacturer"),
                "model": row.get("model"),
                "serial": row.get("serial"),
                "score": row.get("score"),
            }
            for row in candidates
        ]

    _sanitize_identity(out)
    identity.apply_observed_metadata(discovery, out)

    nature = clean(out.get("asset_nature"))
    role = clean(out.get("role"))
    if nature == "PHYSICAL_DEVICE" or role in PHYSICAL_ROLES:
        out["asset_class"] = "PHYSICAL_DEVICE"
    elif nature == "VIRTUAL_MACHINE":
        out["asset_class"] = "VIRTUAL_MACHINE"
    elif nature == "VIRTUAL_CANDIDATE" and clean(out.get("asset_class")) == "PHYSICAL_DEVICE":
        # MAC OUI alone never downgrades strong hardware evidence. This branch is
        # reached only for weak/conflicting evidence and is therefore explicit.
        if identity.is_generic_model(out.get("model")) or clean(out.get("confidence")) != "HIGH":
            out["asset_class"] = "HOST_OR_APPLIANCE"

    out["review_recommendations"] = identity.review_recommendations(out)
    out["classification_version"] = CLASSIFIER_VERSION
    return out


def main(argv=None):
    old_classify = v6.classify_device
    old_version = v6.CLASSIFIER_VERSION
    try:
        v6.classify_device = classify_device
        v6.CLASSIFIER_VERSION = CLASSIFIER_VERSION
        return v6.main(argv)
    finally:
        v6.classify_device = old_classify
        v6.CLASSIFIER_VERSION = old_version


if __name__ == "__main__":
    sys.exit(main())
