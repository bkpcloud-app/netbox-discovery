#!/usr/bin/env python3
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
sys.path.insert(0, BASE)

from modules.discovery import network_v2
from modules.inventory import classifier_v3
from modules.inventory import reconciler_v3


FA_INDEX = ".16.16.0.0.80.19.176.82.17.0.0.0.0.0.0.0.0"


def _fake_fa_walk(ip, version_option, community, oid, timeout=12):
    if oid != network_v2.FA_CONN_UNIT_ENTRY_OID:
        return []
    prefix = network_v2.FA_CONN_UNIT_ENTRY_OID
    return [
        (prefix + ".1" + FA_INDEX, "Hex-STRING", "10 00 00 50 13 B0 52 11 00 00 00 00 00 00 00 00"),
        (prefix + ".3" + FA_INDEX, "INTEGER", "storage-subsystem(11)"),
        (prefix + ".5" + FA_INDEX, "INTEGER", "online(2)"),
        (prefix + ".6" + FA_INDEX, "INTEGER", "ok(3)"),
        (prefix + ".7" + FA_INDEX, "STRING", "ME4024"),
        (prefix + ".8" + FA_INDEX, "STRING", "MXA1234567"),
        (prefix + ".20" + FA_INDEX, "STRING", "ME4024"),
    ]


def test_fa_storage_identity_is_stable_across_controller_management_ips():
    old_walk = network_v2.base._snmp_walk
    try:
        network_v2.base._snmp_walk = _fake_fa_walk
        snmp = {
            "available": True,
            "_version_option": "-v2c",
            "_community": "test",
            "sysobjectid": ".1.3.6.1.4.1.674",
            "sysname": "ME4024",
        }
        left = network_v2.probe_snmp_fa_connectivity("10.1.1.52", snmp)
        right = network_v2.probe_snmp_fa_connectivity("10.1.1.53", snmp)
    finally:
        network_v2.base._snmp_walk = old_walk

    assert left["primary"]["type_id"] == "11"
    assert left["primary"]["product"] == "ME4024"
    assert left["primary"]["serial"] == "MXA1234567"
    assert left["primary"]["conn_unit_id"] == right["primary"]["conn_unit_id"]
    assert len(left["primary"]["conn_unit_id"]) == 32


def test_fa_storage_becomes_storage_high_with_real_serial():
    fa_row = {
        "fa_conn_unit_id": "1000005013B052110000000000000000",
        "fa_conn_unit_type": "storage-subsystem(11)",
        "fa_conn_unit_type_id": "11",
        "fa_conn_unit_product": "ME4024",
        "fa_conn_unit_serial": "MXA1234567",
        "fa_conn_unit_vendor": "Dell",
        "fa_conn_unit_status": "ok(3)",
        "fa_conn_unit_state": "online(2)",
        "manufacturer": "Dell",
        "model": "ME4024",
        "serial": "MXA1234567",
    }
    device = {
        "snmp_entity_primary": fa_row,
        "snmp_entity_inventory": [fa_row],
        "snmp_object_id": ".1.3.6.1.4.1.674",
        "snmp_available": True,
        "open_services": [],
    }
    role, score, evidence = classifier_v3.classify_role(device, "")
    assert role == "STORAGE"
    assert score == 99
    assert evidence


def test_same_fa_unit_merges_two_management_ips_but_different_unit_does_not():
    a = {
        "ip": "10.1.1.52",
        "role": "STORAGE",
        "storage_unit_id": "1000005013B052110000000000000000",
        "serial": "",
        "management_mac": "00:C0:FF:44:07:DA",
        "snmp_name": "ME4024",
    }
    b = dict(a)
    b["ip"] = "10.1.1.53"
    b["management_mac"] = "00:C0:FF:44:07:1F"

    reason, score = reconciler_v3.merge_reason(a, b)
    assert reason.startswith("FA_CONN_UNIT:")
    assert score == 100
    assert reconciler_v3.asset_id([a, b]).startswith("FA:")

    c = dict(b)
    c["storage_unit_id"] = "2000005013B052110000000000000000"
    reason, score = reconciler_v3.merge_reason(a, c)
    assert not reason


def test_fa_entity_row_marks_storage_chassis_not_controller_engine():
    old_walk = network_v2.base._snmp_walk
    old_entity = network_v2.ORIG_PROBE_SNMP_ENTITY
    try:
        network_v2.base._snmp_walk = _fake_fa_walk
        network_v2.ORIG_PROBE_SNMP_ENTITY = lambda ip, snmp: {"primary": {}, "inventory": [], "count": 0}
        snmp = {
            "available": True,
            "_version_option": "-v2c",
            "_community": "test",
            "sysobjectid": ".1.3.6.1.4.1.674",
            "sysname": "ME4024",
        }
        entity = network_v2.probe_snmp_entity("10.1.1.52", snmp)
    finally:
        network_v2.base._snmp_walk = old_walk
        network_v2.ORIG_PROBE_SNMP_ENTITY = old_entity

    primary = entity["primary"]
    assert primary["fa_conn_unit_type_id"] == "11"
    assert primary["manufacturer"] == "Dell"
    assert primary["model"] == "ME4024"
    assert primary["serial"] == "MXA1234567"
    assert primary["source"] == "fcmgmt-mib"


def main():
    tests = [
        test_fa_storage_identity_is_stable_across_controller_management_ips,
        test_fa_storage_becomes_storage_high_with_real_serial,
        test_same_fa_unit_merges_two_management_ips_but_different_unit_does_not,
        test_fa_entity_row_marks_storage_chassis_not_controller_engine,
    ]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.10.11 POWERVAULT FA-MIB TESTS PASSED")


if __name__ == "__main__":
    main()
