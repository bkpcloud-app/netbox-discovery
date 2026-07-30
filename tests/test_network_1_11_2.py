#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.discovery import network_v4, network_v5
from modules.inventory import classifier_v7, planner_v9
from modules.importers import importer_v10


class Catalog(object):
    def __init__(self):
        self.roles = {}

    def ensure_role(self, name):
        self.roles.setdefault(name, {"id": len(self.roles) + 100, "name": name})
        return self.roles[name]


def windows_discovery(script_name, script_output):
    return {
        "ip": "10.2.2.150",
        "open_services": [
            {"port": 445, "protocol": "tcp", "service": "microsoft-ds", "scripts": {script_name: script_output}},
            {"port": 3389, "protocol": "tcp", "service": "ms-wbt-server", "scripts": {}},
        ],
    }


def test_windows_server_is_separate():
    row = classifier_v7.classify_device(windows_discovery(
        "smb-os-discovery",
        "OS: Windows Server 2022 Standard 20348\nComputer name: SRV-APP01",
    ))
    assert row["role"] == "WINDOWS_SERVER"
    assert row["windows_family"] == "SERVER"
    assert row["platform"] == "Windows Server 2022"
    assert row["confidence"] == "HIGH"


def test_windows_11_is_workstation():
    row = classifier_v7.classify_device(windows_discovery(
        "smb-os-discovery",
        "OS: Windows 11 Pro 10.0.26100\nComputer name: AGL-BA133",
    ))
    assert row["role"] == "WINDOWS_WORKSTATION"
    assert row["windows_family"] == "WORKSTATION"
    assert row["platform"] == "Windows 11"
    assert row["confidence"] == "HIGH"


def test_rdp_version_alone_does_not_guess_workstation():
    discovery = {
        "ip": "10.2.2.151",
        "open_services": [{
            "port": 3389, "protocol": "tcp", "service": "ms-wbt-server",
            "scripts": {"rdp-ntlm-info": "Product_Version: 10.0.26100\nNetBIOS_Computer_Name: AGL-BA132"},
        }],
    }
    row = classifier_v7.classify_device(discovery)
    assert row["role"] == "WINDOWS_HOST"
    assert row["windows_family"] == "UNRESOLVED"


def test_conflicting_windows_evidence_is_not_applied():
    discovery = {
        "ip": "10.2.2.152",
        "open_services": [{
            "port": 445, "protocol": "tcp", "service": "microsoft-ds",
            "scripts": {
                "smb-os-discovery": "OS: Windows Server 2022 Standard",
                "smb-system-info": "OS: Windows 11 Pro",
            },
        }],
    }
    row = classifier_v7.classify_device(discovery)
    assert row["role"] == "WINDOWS_HOST"
    assert row["windows_family"] == "CONFLICT"
    assert row.get("windows_classification_conflict")


def test_printer_serial_prefers_valid_over_placeholder():
    serial, candidates, source = network_v4._best_printer_serial(
        ["03000000", "U64189D0N416627"],
        "Brother DCP-L5502DN Serial Number: U64189D0N416627",
        "Brother", "DCP-L5502DN", "imp-ba03",
    )
    assert serial == "U64189D0N416627"
    assert candidates == ["U64189D0N416627"]
    assert source == "printer-mib"


def test_hikvision_xml_identity_extracts_serial():
    xml = """<?xml version='1.0'?>
<DeviceInfo><deviceName>CAM-01</deviceName><deviceID>1</deviceID>
<model>DS-2CD2143G2-I</model><serialNumber>DS2CD2143-ABC123456</serialNumber>
<firmwareVersion>V5.7.20</firmwareVersion></DeviceInfo>"""
    row = network_v5._extract_device_info(xml, "Hikvision")
    assert row["manufacturer"] == "Hikvision"
    assert row["model"] == "DS-2CD2143G2-I"
    assert row["serial"] == "DS2CD2143ABC123456"
    assert row["firmware"] == "V5.7.20"


def test_hikvision_serial_has_priority_over_weak_entity_serial():
    discovery = {
        "ip": "10.2.2.31",
        "snmp_entity_primary": {"source": "entity-mib", "model": "Generic Camera", "serial": "ENTITY123"},
        "open_services": [{
            "port": 0, "protocol": "host", "service": "cctv-device-information",
            "scripts": {"onvif-hikvision-device-information": (
                "Manufacturer: Hikvision\nModel: DS-2CD2143G2-I\n"
                "Firmware Version: V5.7.20\nSerial Number: HIK987654321"
            )},
        }],
    }
    row = classifier_v7.classify_device(discovery)
    assert row["serial"] == "HIK987654321"
    assert row["serial_source"] == "onvif-hikvision-device-info"
    assert row["serial_confidence"] == "HIGH"


def test_equal_strength_serial_conflict_is_blocked():
    discovery = {
        "ip": "10.2.2.32",
        "open_services": [{
            "port": 0, "protocol": "host", "service": "cctv-device-information",
            "scripts": {
                "onvif-device-information": "Manufacturer: Hikvision\nModel: DS-2CD\nSerial Number: SERIALAAAA1",
                "hikvision-isapi-device-information": "Manufacturer: Hikvision\nModel: DS-2CD\nSerial Number: SERIALBBBB2",
            },
        }],
    }
    row = classifier_v7.classify_device(discovery)
    assert row["serial"] == ""
    assert row["serial_confidence"] == "CONFLICT"
    assert len(row["serial_conflict"]) >= 2


def test_windows_workstation_plan_target():
    row = {
        "role": "WINDOWS_WORKSTATION", "target_role": "WINDOWS_WORKSTATION",
        "manufacturer": "Generic", "model": "Unknown Server",
        "confidence": "HIGH", "decision": "READY", "action": "CREATE",
        "safe_diffs": [], "reasons": [], "match_state": "NEW",
    }
    class_row = {
        "role": "WINDOWS_WORKSTATION", "confidence": "HIGH",
        "windows_family": "WORKSTATION", "windows_product": "Windows 11",
        "windows_evidence_source": "smb-os-discovery", "windows_evidence_rank": 110,
    }
    planner_v9._windows_plan_policy(row, class_row, None)
    assert row["target_role"] == "WORKSTATION-WINDOWS"
    assert row["model"] == "Windows Workstation"


def test_product_windows_role_correction_is_safe_update():
    row = {
        "role": "WINDOWS_WORKSTATION", "target_role": "WINDOWS_WORKSTATION",
        "manufacturer": "Generic", "model": "Unknown Server",
        "confidence": "HIGH", "decision": "READY", "action": "NOOP",
        "safe_diffs": [], "reasons": ["ROLE_DRIFT:SERVER-WINDOWS->WORKSTATION-WINDOWS"],
        "match_state": "MATCHED", "match_reason": "IP",
    }
    class_row = {
        "role": "WINDOWS_WORKSTATION", "confidence": "HIGH",
        "windows_family": "WORKSTATION", "windows_product": "Windows 11",
        "windows_evidence_source": "smb-os-discovery", "windows_evidence_rank": 110,
    }
    current = {
        "id": 10, "description": "Criado pelo netbox-discovery",
        "role": {"name": "SERVER-WINDOWS"},
    }
    planner_v9._windows_plan_policy(row, class_row, current)
    assert row["action"] == "UPDATE_SAFE"
    assert "role:SET:WORKSTATION-WINDOWS" in row["safe_diffs"]
    assert row["identity_policy"] == "WINDOWS_ROLE_CORRECTION_EXPLICIT_OS"


def test_manual_windows_device_role_is_never_corrected():
    row = {
        "role": "WINDOWS_WORKSTATION", "target_role": "WINDOWS_WORKSTATION",
        "manufacturer": "Generic", "model": "Unknown Server",
        "confidence": "HIGH", "decision": "READY", "action": "NOOP",
        "safe_diffs": [], "reasons": [], "match_state": "MATCHED", "match_reason": "IP",
    }
    class_row = {
        "role": "WINDOWS_WORKSTATION", "confidence": "HIGH",
        "windows_family": "WORKSTATION", "windows_product": "Windows 11",
        "windows_evidence_source": "smb-os-discovery", "windows_evidence_rank": 110,
    }
    current = {"id": 10, "description": "Administrado manualmente", "role": {"name": "SERVER-WINDOWS"}}
    planner_v9._windows_plan_policy(row, class_row, current)
    assert row["action"] == "NOOP"
    assert not row["safe_diffs"]


def test_importer_applies_only_protected_windows_role():
    original = importer_v10.ORIG_SAFE_PATCH
    catalog = Catalog()
    row = {
        "safe_diffs": ["role:SET:WORKSTATION-WINDOWS"],
        "target_role": "WORKSTATION-WINDOWS",
        "identity_policy": "WINDOWS_ROLE_CORRECTION_EXPLICIT_OS",
        "confidence": "HIGH", "windows_evidence_source": "smb-os-discovery",
    }
    current = {"description": "Criado pelo netbox-discovery", "role": {"name": "SERVER-WINDOWS"}}
    try:
        importer_v10.ORIG_SAFE_PATCH = lambda row, current, catalog: {}
        payload = importer_v10.safe_patch_for_existing(row, current, catalog)
        assert payload["role"] == catalog.roles["WORKSTATION-WINDOWS"]["id"]
    finally:
        importer_v10.ORIG_SAFE_PATCH = original


def test_importer_rejects_arbitrary_role_change():
    original = importer_v10.ORIG_SAFE_PATCH
    catalog = Catalog()
    row = {
        "safe_diffs": ["role:SET:FIREWALL"], "target_role": "FIREWALL",
        "identity_policy": "WINDOWS_ROLE_CORRECTION_EXPLICIT_OS",
        "confidence": "HIGH", "windows_evidence_source": "smb-os-discovery",
    }
    current = {"description": "Criado pelo netbox-discovery", "role": {"name": "SERVER-WINDOWS"}}
    try:
        importer_v10.ORIG_SAFE_PATCH = lambda row, current, catalog: {}
        try:
            importer_v10.safe_patch_for_existing(row, current, catalog)
            raise AssertionError("arbitrary role change should be blocked")
        except RuntimeError as exc:
            assert "não autorizada" in str(exc)
    finally:
        importer_v10.ORIG_SAFE_PATCH = original


def main():
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.11.2 WINDOWS + SERIAL TESTS PASSED")


if __name__ == "__main__":
    main()
