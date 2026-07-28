#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("NETBOX_DISCOVERY_BASE", os.path.abspath(os.path.join(HERE, "..", "..")))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.inventory import classifier_v2 as v2

CLASSIFIER_VERSION = "3.2-product"

ORIG_CLASSIFY_ROLE = v2.classify_role
ORIG_INFER_MANUFACTURER = v2.infer_manufacturer
ORIG_INFER_MODEL = v2.infer_model
ORIG_CLASSIFY_DEVICE = v2.classify_device


def clean(value):
    return "" if value is None else str(value).strip()


def _fa_storage(d):
    primary = d.get("snmp_entity_primary") or {}
    type_id = clean(primary.get("fa_conn_unit_type_id"))
    unit_id = re.sub(r"[^A-Fa-f0-9]", "", clean(primary.get("fa_conn_unit_id"))).upper()
    if type_id != "11" or not unit_id:
        return {}
    return {
        "unit_id": unit_id,
        "type": clean(primary.get("fa_conn_unit_type")),
        "product": clean(primary.get("fa_conn_unit_product") or primary.get("model")),
        "serial": clean(primary.get("fa_conn_unit_serial") or primary.get("serial")),
        "vendor": clean(primary.get("fa_conn_unit_vendor") or primary.get("manufacturer")),
        "status": clean(primary.get("fa_conn_unit_status")),
        "state": clean(primary.get("fa_conn_unit_state")),
    }


def classify_role(d, text):
    fa = _fa_storage(d)
    if fa:
        return "STORAGE", 99, ["FibreAlliance connUnitType storage-subsystem(11)"]
    return ORIG_CLASSIFY_ROLE(d, text)


def infer_manufacturer(d, text, ent, role):
    fa = _fa_storage(d)
    if fa:
        vendor = fa.get("vendor")
        if vendor:
            return v2.normalize_manufacturer(vendor), "fcmgmt-mib"
        if clean(d.get("snmp_object_id")).startswith(".1.3.6.1.4.1.674"):
            return "Dell", "fcmgmt-mib+enterprise"
        if re.match(r"^ME[45][0-9]{3}", fa.get("product") or "", re.I):
            return "Dell", "fcmgmt-mib-product"
    return ORIG_INFER_MANUFACTURER(d, text, ent, role)


def infer_model(d, text, ent, role):
    fa = _fa_storage(d)
    if fa and fa.get("product"):
        return fa["product"][:120], "fcmgmt-mib"
    return ORIG_INFER_MODEL(d, text, ent, role)


def classify_device(d):
    out = ORIG_CLASSIFY_DEVICE(d)
    fa = _fa_storage(d)
    if not fa:
        out["classification_version"] = CLASSIFIER_VERSION
        return out

    out["classification_version"] = CLASSIFIER_VERSION
    out["storage_unit_id"] = fa.get("unit_id", "")
    out["storage_unit_type"] = fa.get("type", "")
    out["storage_unit_product"] = fa.get("product", "")
    out["storage_unit_status"] = fa.get("status", "")
    out["storage_unit_state"] = fa.get("state", "")

    serial = v2.base.norm_serial(fa.get("serial"))
    if serial:
        out["serial"] = serial
        out["serial_source"] = "fcmgmt-mib"
    if fa.get("product"):
        out["model"] = fa["product"][:120]
        out["model_source"] = "fcmgmt-mib"
    if fa.get("vendor"):
        out["manufacturer"] = v2.normalize_manufacturer(fa["vendor"])
        out["manufacturer_source"] = "fcmgmt-mib"
    elif clean(d.get("snmp_object_id")).startswith(".1.3.6.1.4.1.674"):
        out["manufacturer"] = "Dell"
        out["manufacturer_source"] = "fcmgmt-mib+enterprise"

    out["role"] = "STORAGE"
    out["classification_score"] = 99
    out["confidence"] = "HIGH"
    out["asset_class"] = "PHYSICAL_DEVICE"
    evidence = list(out.get("evidence") or [])
    marker = "FibreAlliance connUnit identity: {0}".format(fa.get("unit_id"))
    if marker not in evidence:
        evidence.append(marker)
    out["evidence"] = evidence
    return out


def main(argv=None):
    old_role = v2.classify_role
    old_mfg = v2.infer_manufacturer
    old_model = v2.infer_model
    old_device = v2.classify_device
    old_version = v2.CLASSIFIER_VERSION
    try:
        v2.classify_role = classify_role
        v2.infer_manufacturer = infer_manufacturer
        v2.infer_model = infer_model
        v2.classify_device = classify_device
        v2.CLASSIFIER_VERSION = CLASSIFIER_VERSION
        return v2.main(argv)
    finally:
        v2.classify_role = old_role
        v2.infer_manufacturer = old_mfg
        v2.infer_model = old_model
        v2.classify_device = old_device
        v2.CLASSIFIER_VERSION = old_version


if __name__ == "__main__":
    sys.exit(main())
