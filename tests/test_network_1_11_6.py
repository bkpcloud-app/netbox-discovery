#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.discovery import network_v4
from modules.inventory import classifier_v8 as classifier
from modules.inventory import planner_v9


def test_brother_serial_is_not_misread_as_mac():
    serial, reason = classifier._validate_serial("U64189M8N960565", [])
    assert serial == "U64189M8N960565", (serial, reason)
    assert reason == ""


def test_real_mac_is_still_rejected_as_serial():
    serial, reason = classifier._validate_serial("64:18:98:96:05:65", [])
    assert serial == ""
    assert reason == "mac-address"


def test_duplicate_serial_rejections_are_collapsed():
    out = {
        "serial_rejections": [
            {"value": "U64189M8N960565", "source": "printer-mib", "reason": "mac-address"},
            {"value": "U64189M8N960565", "source": "printer-mib-candidate", "reason": "mac-address"},
        ]
    }
    classifier._dedupe_serial_rejections(out)
    assert len(out["serial_rejections"]) == 1


def test_samsung_hostname_is_not_a_device_model():
    discovery = {"snmp_name": "SEC30CDA7FFE27C"}
    out = {
        "role": "PRINTER",
        "manufacturer": "Samsung",
        "model": "SEC30CDA7FFE27C",
        "observed_name": "SEC30CDA7FFE27C",
        "identity_provenance": {"model": "printer-mib"},
    }
    classifier._sanitize_printer_model(discovery, out)
    assert out["model"] == "Printer-MIB managed printer"
    assert out["model_rejection"]["reason"] == "duplicates-printer-hostname"


def test_printer_entity_rejects_model_equal_to_name():
    original_walk = network_v4.base._snmp_walk
    original_context = network_v4.base.snmp_command_context

    def fake_context(snmp):
        return "-v2c", "public"

    def fake_walk(ip, version, community, root, timeout=8):
        if root == network_v4.PRT_GENERAL_ROOT:
            return [
                (root + ".16.1", "STRING", "SEC30CDA7FFE27C"),
                (root + ".17.1", "STRING", "ZDEJBQAJ20003SL"),
            ]
        if root == network_v4.HR_DEVICE_DESCR:
            return [(root + ".1", "STRING", "Samsung SEC30CDA7FFE27C")]
        return []

    try:
        network_v4.base.snmp_command_context = fake_context
        network_v4.base._snmp_walk = fake_walk
        row = network_v4._printer_entity("10.2.2.86", {"available": True})
        assert row["manufacturer"] == "Samsung"
        assert row["name"] == "SEC30CDA7FFE27C"
        assert row["model"] == ""
        assert row["serial"] == "ZDEJBQAJ20003SL"
    finally:
        network_v4.base._snmp_walk = original_walk
        network_v4.base.snmp_command_context = original_context


def _windows_row(uid):
    return {
        "role": "WINDOWS_WORKSTATION",
        "target_role": "WINDOWS_WORKSTATION",
        "manufacturer": "Unidentified",
        "model": "Unknown Server",
        "confidence": "HIGH",
        "decision": "READY",
        "action": "CREATE",
        "safe_diffs": [],
        "reasons": [],
        "match_state": "NEW",
        "discovery_uid": uid,
        "interfaces": [{"name": "MGMT", "ip": "10.2.100.10"}],
        "ip_intents": [{"action": "ENSURE", "ip": "10.2.100.10"}],
    }


def _windows_class(uid):
    return {
        "role": "WINDOWS_WORKSTATION",
        "confidence": "HIGH",
        "windows_product": "Windows 7",
        "windows_evidence_source": "smb-os-discovery",
        "windows_evidence_rank": 110,
        "discovery_uid": uid,
        "serial": "",
        "serial_confidence": "NONE",
    }


def test_new_windows_with_weak_identity_is_review_only():
    row = _windows_row("WEAK:8D5A7F409E09E87E")
    planner_v9._windows_plan_policy(row, _windows_class(row["discovery_uid"]), None)
    assert row["target_role"] == "WORKSTATION-WINDOWS"
    assert row["decision"] == "REVIEW"
    assert row["action"] == "NOOP"
    assert "WINDOWS_NEW_DEVICE_REQUIRES_STABLE_PHYSICAL_IDENTITY" in row["reasons"]
    assert row["interfaces"] == []
    assert row["ip_intents"] == []


def test_new_windows_with_management_mac_can_remain_ready():
    row = _windows_row("MGMT-MAC:00:11:22:33:44:55")
    planner_v9._windows_plan_policy(row, _windows_class(row["discovery_uid"]), None)
    assert row["decision"] == "READY"
    assert row["action"] == "CREATE"
    assert row["target_role"] == "WORKSTATION-WINDOWS"


def main():
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.11.6 IDENTITY SAFETY TESTS PASSED")


if __name__ == "__main__":
    main()
