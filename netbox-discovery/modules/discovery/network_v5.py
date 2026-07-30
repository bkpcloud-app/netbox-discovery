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

from modules.discovery import network_v4 as v4
from modules.product import identity

DISCOVERY_WRAPPER_VERSION = "4.4-product"
ORIG_PROBE_SNMP_ENTITY = v4.probe_snmp_entity


def clean(value):
    return "" if value is None else str(value).strip()


def _catalog_identity(snmp):
    object_id = clean(snmp.get("sysobjectid") or snmp.get("object_id"))
    sysdescr = clean(snmp.get("sysdescr") or snmp.get("description"))
    sysname = clean(snmp.get("sysname") or snmp.get("name"))
    exact = identity.INDUSTRIAL_OID_CATALOG.get(object_id)
    if exact:
        return {
            "manufacturer": exact.get("manufacturer", ""),
            "model": exact.get("model", ""),
            "role_hint": exact.get("role", ""),
            "source": exact.get("source", "sysobjectid-catalog"),
        }

    raw = " ".join((sysname, sysdescr))
    patterns = (
        (r"\b(NPort\s+[0-9A-Z-]+)\b", "Moxa", "INDUSTRIAL_COMMUNICATION"),
        (r"\b(EDS-[0-9A-Z-]+)\b", "Moxa", "INDUSTRIAL_SWITCH"),
        (r"\b(SCALANCE\s+[0-9A-Z-]+)\b", "Siemens", "INDUSTRIAL_SWITCH"),
        (r"\b(PAC(?:3220|4200))\b", "Siemens", "INDUSTRIAL_POWER_METER"),
        (r"\b(SRW01[- ]?ETH)\b", "WEG", "INDUSTRIAL_MOTOR_PROTECTION"),
        (r"\b(Westermo\s+Lynx[^,;\r\n]*)", "Westermo", "INDUSTRIAL_SWITCH"),
    )
    for pattern, manufacturer, role in patterns:
        match = re.search(pattern, raw, re.I)
        if match:
            return {
                "manufacturer": manufacturer,
                "model": clean(match.group(1))[:120],
                "role_hint": role,
                "source": "snmp-protocol-catalog",
            }
    return {}


def _catalog_entity(ip, snmp):
    item = _catalog_identity(snmp)
    if not item:
        return {}
    sysname = clean(snmp.get("sysname") or snmp.get("name"))
    object_id = clean(snmp.get("sysobjectid") or snmp.get("object_id"))
    uid_seed = "{0}:{1}:{2}".format(object_id, item.get("model"), ip)
    return {
        "index": "protocol-catalog:1",
        "description": "Protocol identity catalog",
        "contained_in": "",
        "class": "chassis(3)",
        "class_id": "3",
        "parent_rel_pos": "",
        "name": sysname or item.get("model", ""),
        "hardware_rev": "",
        "firmware_rev": "",
        "software_rev": "",
        "serial": "",
        "manufacturer": item.get("manufacturer", ""),
        "model": item.get("model", ""),
        "alias": "",
        "asset_id": "PROTOCOL:{0}".format(uid_seed),
        "is_fru": "",
        "source": item.get("source", "protocol-catalog"),
        "management_ip": ip,
        "role_hint": item.get("role_hint", ""),
        "protocol_text": "sysObjectID={0}; sysName={1}".format(object_id, sysname),
    }


def _is_more_specific(candidate, current):
    if not candidate:
        return False
    if not current:
        return True
    current_model = clean(current.get("model"))
    candidate_model = clean(candidate.get("model"))
    if identity.is_generic_model(current_model) and not identity.is_generic_model(candidate_model):
        return True
    if not current_model and candidate_model:
        return True
    return False


def probe_snmp_entity(ip, snmp):
    entity = ORIG_PROBE_SNMP_ENTITY(ip, snmp)
    catalog = _catalog_entity(ip, snmp)
    if not catalog:
        return entity

    inventory = list(entity.get("inventory") or [])
    duplicate = any(
        clean(row.get("source")) == clean(catalog.get("source"))
        and clean(row.get("model")) == clean(catalog.get("model"))
        for row in inventory
    )
    if not duplicate:
        inventory.append(catalog)
    entity["inventory"] = inventory
    entity["count"] = len(inventory)
    if _is_more_specific(catalog, entity.get("primary") or {}):
        entity["primary"] = catalog
    return entity


def main():
    old_probe = v4.probe_snmp_entity
    old_version = v4.DISCOVERY_WRAPPER_VERSION
    try:
        v4.probe_snmp_entity = probe_snmp_entity
        v4.DISCOVERY_WRAPPER_VERSION = DISCOVERY_WRAPPER_VERSION
        return v4.main()
    finally:
        v4.probe_snmp_entity = old_probe
        v4.DISCOVERY_WRAPPER_VERSION = old_version


if __name__ == "__main__":
    sys.exit(main())
