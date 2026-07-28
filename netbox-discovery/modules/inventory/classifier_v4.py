#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import csv
import glob
import json
import os
import re
import sys
import time
from collections import Counter

from modules.inventory import classifier_v2 as v2
from modules.inventory import classifier_v3 as v3

CLASSIFIER_VERSION = "4.0-product"
HISTORY_MAX_AGE_SECONDS = 48 * 60 * 60
HISTORY_MAX_FILES = 20
VMWARE_MAC_PREFIXES = ("00:05:69", "00:0C:29", "00:1C:14", "00:50:56")
ORIG_V2_WRITE_OUTPUTS = v2.write_outputs
ORIG_V3_FA_STORAGE = v3._fa_storage

CSV_FIELDS = [
    "ip", "hostname", "role", "manufacturer", "model", "serial", "platform", "asset_class",
    "classification_score", "confidence", "classification_state", "evidence_level",
    "management_mac", "management_mac_source", "primary_mac", "secondary_macs",
    "snmp_name", "snmp_object_id", "hostname_source", "manufacturer_source", "model_source",
    "serial_source", "evidence",
]


def clean(value):
    return "" if value is None else str(value).strip()


def norm_mac(value):
    compact = re.sub(r"[^0-9A-Fa-f]", "", clean(value)).upper()
    if len(compact) != 12:
        return ""
    return ":".join(compact[i:i + 2] for i in range(0, 12, 2))


def valid_fa_id(value):
    compact = re.sub(r"[^0-9A-Fa-f]", "", clean(value)).upper()
    if not compact or set(compact) == set("0"):
        return ""
    return compact


def fa_storage(d):
    """Treat an all-zero connUnitId as absent, not as array identity.

    Some PowerVault controllers return connUnitType=storage-subsystem and a
    valid product/serial while connUnitId is all zeros. Serial remains strong
    array evidence; the zero ID must never become an identity key.
    """
    primary = d.get("snmp_entity_primary") or {}
    type_id = clean(primary.get("fa_conn_unit_type_id"))
    unit_id = valid_fa_id(primary.get("fa_conn_unit_id"))
    serial = clean(primary.get("fa_conn_unit_serial") or primary.get("serial"))
    product = clean(primary.get("fa_conn_unit_product") or primary.get("model"))
    if type_id != "11" or not (unit_id or serial):
        return {}
    return {
        "unit_id": unit_id,
        "type": clean(primary.get("fa_conn_unit_type")),
        "product": product,
        "serial": serial,
        "vendor": clean(primary.get("fa_conn_unit_vendor") or primary.get("manufacturer")),
        "status": clean(primary.get("fa_conn_unit_status")),
        "state": clean(primary.get("fa_conn_unit_state")),
    }


def _vmware_candidate(row):
    if clean(row.get("asset_class")) == "VIRTUAL_MACHINE_CANDIDATE":
        return True
    mac = norm_mac(row.get("management_mac"))
    return bool(mac and any(mac.startswith(prefix) for prefix in VMWARE_MAC_PREFIXES))


def _strong_physical(row):
    if clean(row.get("asset_class")) != "PHYSICAL_DEVICE":
        return False
    role = clean(row.get("role"))
    physical_roles = {
        "NETWORK_SWITCH", "INDUSTRIAL_SWITCH", "STORAGE", "FIREWALL", "HYPERVISOR",
        "OOB_MANAGEMENT", "WIRELESS_AP", "WIRELESS_BRIDGE", "POWER_MANAGEMENT",
        "PRINTER", "CAMERA", "NVR", "DVR", "INDUSTRIAL_PLC", "INDUSTRIAL_DEVICE",
    }
    if role not in physical_roles:
        return False
    return bool(clean(row.get("serial")) or clean(row.get("snmp_object_id")) or valid_fa_id(row.get("storage_unit_id")))


def _strong_storage(row):
    return clean(row.get("role")) == "STORAGE" and bool(
        clean(row.get("serial")) or valid_fa_id(row.get("storage_unit_id"))
    )


def _history_files(output_dir, site):
    now = time.time()
    files = sorted(
        glob.glob(os.path.join(output_dir, "{0}-classification-*.json".format(site))),
        key=os.path.getmtime,
        reverse=True,
    )
    out = []
    for path in files:
        try:
            if now - os.path.getmtime(path) > HISTORY_MAX_AGE_SECONDS:
                continue
        except OSError:
            continue
        out.append(path)
        if len(out) >= HISTORY_MAX_FILES:
            break
    return out


def _load_history(output_dir, site):
    by_ip = {}
    for path in _history_files(output_dir, site):
        try:
            data = json.load(open(path, "r"))
        except Exception:
            continue
        if clean(data.get("site")) != site:
            continue
        for row in data.get("records") or []:
            ip = clean(row.get("ip"))
            if not ip:
                continue
            slot = by_ip.setdefault(ip, {"vm": None, "storage": None})
            if slot["vm"] is None and _vmware_candidate(row):
                slot["vm"] = (path, row)
            if slot["storage"] is None and _strong_storage(row):
                slot["storage"] = (path, row)
    return by_ip


def _append_evidence(row, text):
    evidence = list(row.get("evidence") or [])
    if text not in evidence:
        evidence.append(text)
    row["evidence"] = evidence


def _restore_storage(current, source_path, previous):
    current_serial = v2.base.norm_serial(current.get("serial"))
    previous_serial = v2.base.norm_serial(previous.get("serial"))
    current_fa = valid_fa_id(current.get("storage_unit_id"))
    previous_fa = valid_fa_id(previous.get("storage_unit_id"))
    if current_serial and previous_serial and current_serial != previous_serial:
        current["historical_identity_conflict"] = "storage-serial"
        return
    if current_fa and previous_fa and current_fa != previous_fa:
        current["historical_identity_conflict"] = "storage-fa-id"
        return

    current["role"] = "STORAGE"
    current["classification_score"] = max(int(current.get("classification_score") or 0), 99)
    current["confidence"] = "HIGH"
    current["asset_class"] = "PHYSICAL_DEVICE"

    # FA-MIB/array serial is stronger than controller MAC OUI/generic SNMP text.
    if clean(previous.get("manufacturer")):
        current["manufacturer"] = previous.get("manufacturer")
        current["manufacturer_source"] = "history:fcmgmt-mib"
    if clean(previous.get("model")):
        current["model"] = previous.get("model")
        current["model_source"] = "history:fcmgmt-mib"
    if clean(previous.get("serial")):
        current["serial"] = previous.get("serial")
        current["serial_source"] = "history:fcmgmt-mib"
    if previous_fa:
        current["storage_unit_id"] = previous_fa
    for key in ("storage_unit_type", "storage_unit_product", "storage_unit_status", "storage_unit_state"):
        if clean(previous.get(key)):
            current[key] = previous.get(key)

    current["identity_history_source"] = source_path
    _append_evidence(current, "Historical strong storage identity retained after transient FA-MIB miss")


def _restore_vm_candidate(current, source_path, previous):
    if _strong_physical(current):
        return
    current["asset_class"] = "VIRTUAL_MACHINE_CANDIDATE"
    current["identity_history_source"] = source_path
    prior_mac = norm_mac(previous.get("management_mac") or previous.get("historical_vmware_mac"))
    if prior_mac:
        current["historical_vmware_mac"] = prior_mac
    _append_evidence(current, "Historical VMware identity retained after transient MAC miss")


def apply_identity_history(data, history):
    for row in data.get("records") or []:
        ip = clean(row.get("ip"))
        slot = history.get(ip) or {}
        if not _strong_storage(row) and slot.get("storage") and not _strong_physical(row):
            _restore_storage(row, slot["storage"][0], slot["storage"][1])
        if not _vmware_candidate(row) and slot.get("vm"):
            _restore_vm_candidate(row, slot["vm"][0], slot["vm"][1])
        if clean(row.get("storage_unit_id")) and not valid_fa_id(row.get("storage_unit_id")):
            row["storage_unit_id"] = ""
        row["classification_version"] = CLASSIFIER_VERSION

    roles = Counter(clean(x.get("role")) for x in data.get("records") or [])
    conf = Counter(clean(x.get("confidence")) for x in data.get("records") or [])
    data["classification_version"] = CLASSIFIER_VERSION
    data["role_summary"] = dict(sorted((k, v) for k, v in roles.items() if k))
    data["confidence_summary"] = dict(sorted((k, v) for k, v in conf.items() if k))
    return data


def _rewrite_csv(path, records):
    with open(path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for item in records:
            row = dict(item)
            row["evidence"] = " | ".join(item.get("evidence") or [])
            row["secondary_macs"] = " | ".join(item.get("secondary_macs") or [])
            writer.writerow(dict((key, row.get(key, "")) for key in CSV_FIELDS))


def write_outputs(source, report, output_dir):
    site = clean(report.get("site")) or "SITE"
    history = _load_history(output_dir, site)
    jpath, cpath, data = ORIG_V2_WRITE_OUTPUTS(source, report, output_dir)
    data = apply_identity_history(data, history)
    with open(jpath, "w") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
    _rewrite_csv(cpath, data.get("records") or [])
    return jpath, cpath, data


def main(argv=None):
    old_write = v2.write_outputs
    old_version = v3.CLASSIFIER_VERSION
    old_fa = v3._fa_storage
    try:
        v2.write_outputs = write_outputs
        v3.CLASSIFIER_VERSION = CLASSIFIER_VERSION
        v3._fa_storage = fa_storage
        return v3.main(argv)
    finally:
        v2.write_outputs = old_write
        v3.CLASSIFIER_VERSION = old_version
        v3._fa_storage = old_fa


if __name__ == "__main__":
    sys.exit(main())
