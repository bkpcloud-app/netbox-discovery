#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import os
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


def clean(value):
    return "" if value is None else str(value).strip()


def _candidate_rank(candidate):
    return (
        int(candidate.get("score") or 0),
        1 if candidate.get("serial") else 0,
        1 if candidate.get("model") else 0,
        1 if candidate.get("manufacturer") else 0,
    )


def classify_device(discovery):
    out = ORIG_CLASSIFY_DEVICE(discovery)

    candidates = []
    industrial = identity.industrial_identity(discovery)
    cctv = identity.cctv_identity(discovery)
    if industrial:
        candidates.append(industrial)
    if cctv:
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
