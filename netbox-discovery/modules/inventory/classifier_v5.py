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

from modules.inventory import classifier_v4 as v4

CLASSIFIER_VERSION = "5.0-product"
MD32XX_SYSOBJECTID = ".1.3.6.1.4.1.674.10893.2.31"
ORIG_APPLY_HISTORY = v4.apply_identity_history


def clean(value):
    return "" if value is None else str(value).strip()


def norm_name(value):
    return re.sub(r"\s+", " ", clean(value)).strip().casefold()


def md32xx_pair_key(row):
    object_id = clean(row.get("snmp_object_id"))
    name = norm_name(row.get("snmp_name") or row.get("hostname"))
    generic = {"", "unknown", "none", "nil", "sysname not set", "localhost.localdomain"}
    if object_id != MD32XX_SYSOBJECTID or name in generic:
        return ""
    return "DELL_MD32XX|{0}|{1}".format(object_id, name)


def apply_identity_history(data, history):
    data = ORIG_APPLY_HISTORY(data, history)
    for row in data.get("records") or []:
        key = md32xx_pair_key(row)
        if not key:
            row["classification_version"] = CLASSIFIER_VERSION
            continue

        row["role"] = "STORAGE"
        row["manufacturer"] = "Dell"
        row["manufacturer_source"] = "sysobjectid:md32xx"
        row["model"] = "PowerVault MD32xx"
        row["model_source"] = "sysobjectid:md32xx"
        row["asset_class"] = "PHYSICAL_DEVICE"
        row["classification_score"] = max(int(row.get("classification_score") or 0), 96)
        row["confidence"] = "HIGH"
        row["md32xx_pair_key"] = key
        evidence = list(row.get("evidence") or [])
        marker = "Dell PowerVault MD32xx dual-controller SNMP endpoint"
        if marker not in evidence:
            evidence.append(marker)
        row["evidence"] = evidence
        row["classification_version"] = CLASSIFIER_VERSION

    data["classification_version"] = CLASSIFIER_VERSION
    return data


def main(argv=None):
    old_apply = v4.apply_identity_history
    old_version = v4.CLASSIFIER_VERSION
    try:
        v4.apply_identity_history = apply_identity_history
        v4.CLASSIFIER_VERSION = CLASSIFIER_VERSION
        return v4.main(argv)
    finally:
        v4.apply_identity_history = old_apply
        v4.CLASSIFIER_VERSION = old_version


if __name__ == "__main__":
    sys.exit(main())
