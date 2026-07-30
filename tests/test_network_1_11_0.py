#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.product import identity
from modules.inventory import planner_v9
from modules.importers import importer_v10


def test_s7_structured_identity():
    discovery = {
        "open_services": [{
            "port": 102, "protocol": "tcp",
            "scripts": {"s7-info": "Module Type: 6ES7 214-1AG40-0XB0\nModule name: CPU 1214C\nSerial Number: S C-X1234567\nFirmware: V4.5"},
        }],
    }
    row = identity.industrial_identity(discovery)
    assert row["manufacturer"] == "Siemens"
    assert row["role"] == "INDUSTRIAL_PLC"
    assert row["model"] == "6ES7 214-1AG40-0XB0"
    assert row["serial"] == "SCX1234567"
    assert row["confidence"] == "HIGH"


def test_ethernet_ip_identity():
    discovery = {
        "open_services": [{
            "port": 44818, "protocol": "tcp",
            "scripts": {"enip-info": "Vendor: Rockwell Automation\nDevice Type: Programmable Logic Controller\nProduct Name: CompactLogix 5380\nProduct Code: 166\nRevision: 35.11\nSerial Number: 1234ABCD"},
        }],
    }
    row = identity.industrial_identity(discovery)
    assert row["manufacturer"] == "Rockwell Automation"
    assert row["model"] == "CompactLogix 5380"
    assert row["role"] == "INDUSTRIAL_PLC"
    assert row["serial"] == "1234ABCD"


def test_onvif_camera_identity():
    discovery = {
        "open_services": [{
            "port": 3702, "protocol": "udp",
            "scripts": {"wsdd-discover": "ONVIF NetworkVideoTransmitter\nManufacturer: Hikvision\nModel: DS-2CD2143G2-I\nFirmware Version: V5.7\nSerial Number: ABC123456"},
        }],
    }
    row = identity.cctv_identity(discovery)
    assert row["role"] == "CAMERA"
    assert row["manufacturer"] == "Hikvision"
    assert row["model"] == "DS-2CD2143G2-I"
    assert row["serial"] == "ABC123456"


def test_virtual_mac_is_candidate_not_confirmation():
    nature, source, score = identity.infer_asset_nature({"mac": "00:50:56:AA:BB:CC"}, {"role": "WINDOWS_HOST"})
    assert nature == "VIRTUAL_CANDIDATE"
    assert source.startswith("virtual-mac-oui:VMware")
    assert score < 100


def test_physical_hardware_outweighs_mac_hint():
    discovery = {
        "mac": "00:50:56:AA:BB:CC",
        "snmp_entity_primary": {"serial": "ABC1234", "model": "PowerEdge R650"},
    }
    nature, source, score = identity.infer_asset_nature(discovery, {
        "role": "HYPERVISOR", "serial": "ABC1234", "model": "PowerEdge R650",
    })
    assert nature == "PHYSICAL_DEVICE"
    assert score >= 90


def test_stable_uid_prefers_serial():
    uid = identity.stable_discovery_uid({}, {"manufacturer": "Dell Inc.", "serial": "ABC-1234"})
    assert uid == "SERIAL:dell:ABC1234"


def test_existing_name_is_never_replaced():
    row = {"existing_device_id": 7, "desired_name": "SW-BA17", "safe_diffs": ["name:SET:SW-BA17"]}
    planner_v9._protect_existing_name(row, {7: {"id": 7, "name": "SW-FBA-27"}})
    assert row["desired_name"] == "SW-FBA-27"
    assert row["name_authority"] == "NETBOX_EXISTING"
    assert row["name_write_allowed"] is False
    assert not row["safe_diffs"]


def test_virtual_candidate_create_is_review():
    row = {"decision": "READY", "action": "CREATE", "reasons": [], "interfaces": [1], "ip_intents": [1]}
    planner_v9._virtual_candidate_guard(row, {"asset_nature": "VIRTUAL_CANDIDATE"})
    assert row["decision"] == "REVIEW"
    assert row["action"] == "NOOP"
    assert row["interfaces"] == []
    assert "VIRTUAL_CANDIDATE_REQUIRES_CENTRAL_INVENTORY_MATCH" in row["reasons"]


def test_delegated_vm_details_from_ip_owner():
    row = {"primary_ip": "10.2.1.3", "decision": "DELEGATED", "reasons": []}
    state = {
        "ips": [{"id": 10, "address": "10.2.1.3/24", "assigned_object_type": "virtualization.vminterface", "assigned_object_id": 20}],
        "vm_interfaces": [{"id": 20, "name": "Ethernet0", "virtual_machine": {"id": 30}, "primary_mac_address": {"mac_address": "00:50:56:AA:BB:CC"}}],
        "virtual_machines": [{"id": 30, "name": "SRV-BA01", "site": {"name": "FBA"}, "cluster": {"name": "FILIAIS"}, "device": {"name": "VM-BA02"}}],
        "macs": [],
    }
    planner_v9._delegated_details(row, state)
    assert row["delegation_status"] == "PASS"
    assert row["delegated_target"]["vm_name"] == "SRV-BA01"
    assert row["delegated_target"]["interface_name"] == "Ethernet0"
    assert row["identity_policy"] == "CENTRALIZED_HYPERVISOR_AUTHORITY"


def test_write_guard_blocks_abnormal_change():
    rows = [
        {"decision": "READY", "action": "CREATE", "reasons": [], "interfaces": [1], "ip_intents": [1]}
        for _ in range(101)
    ]
    planner_v9._apply_write_guard(rows, {"devices": [{"id": pos} for pos in range(200)]})
    assert all(row["decision"] == "BLOCKED" for row in rows)
    assert all(row["action"] == "NOOP" for row in rows)
    assert rows[0]["write_guard"]["status"] == "BLOCK"


def test_importer_rejects_name_payload():
    original = importer_v10.ORIG_SAFE_PATCH
    try:
        importer_v10.ORIG_SAFE_PATCH = lambda row, current, catalog: {"name": "WRONG"}
        try:
            importer_v10.safe_patch_for_existing({}, {}, object())
            raise AssertionError("name payload should be rejected")
        except RuntimeError as exc:
            assert "proíbe alteração automática" in str(exc)
    finally:
        importer_v10.ORIG_SAFE_PATCH = original


def main():
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.11.0 CONSOLIDATED TESTS PASSED")


if __name__ == "__main__":
    main()
