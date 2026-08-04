#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.inventory import planner_v10 as planner
from modules.importers import importer_v11 as importer
from modules.auditors import auditor_v10 as auditor


def _switch_state(model="Instant On 1930 48G 4SFP+ 370W Switch JL686B"):
    return {
        "devices": [{
            "id": 503,
            "name": "SW-BA17-LB43JZ",
            "serial": "TW37LB43JZ",
            "description": planner.PRODUCT_DEVICE_DESCRIPTION,
            "role": {"name": "NETWORK SWITCH"},
            "device_type": {
                "manufacturer": {"name": "HPE Aruba"},
                "model": model,
            },
            "platform": None,
        }],
        "ips": [{
            "address": "10.2.1.37/24",
            "assigned_object_type": "dcim.interface",
            "assigned_object": {"id": 900, "device": {"id": 503}},
        }],
        "interfaces": [],
    }


def _blocked_switch_row():
    return {
        "asset_id": "SERIAL:TW37LB43JZ",
        "desired_name": "SW-BA17",
        "primary_ip": "10.2.1.37",
        "ips": ["10.2.1.37"],
        "serial": "TW37LB43JZ",
        "decision": "BLOCKED",
        "action": "NOOP",
        "reasons": ["DUPLICATE_DESIRED_NAME", "RECONCILE_REVIEW_CANDIDATE"],
        "target_role": "NETWORK SWITCH",
        "role": "NETWORK_SWITCH",
        "manufacturer": "HPE Aruba",
        "model": "Instant On 1930 48G 4SFP+ 370W Switch JL686B",
        "platform": "",
        "safe_diffs": [],
        "ip_intents": [{"ip": "10.2.1.37", "action": "BLOCKED"}],
    }


def test_01_post_create_collision_matches_by_serial_and_ip():
    row = _blocked_switch_row()
    planner._recover_collision_created_devices([row], _switch_state())
    assert row["existing_device_id"] == 503
    assert row["desired_name"] == "SW-BA17-LB43JZ"
    assert row["decision"] == "READY"
    assert row["action"] == "NOOP"
    assert row["ip_intents"][0]["action"] == "NOOP"


def test_02_collision_recovery_fails_closed_on_type_mismatch():
    row = _blocked_switch_row()
    planner._recover_collision_created_devices([row], _switch_state(model="Wrong Model"))
    assert row.get("existing_device_id") is None
    assert row["decision"] == "BLOCKED"


def test_03_windows_legacy_alias_does_not_create_write():
    row = {
        "existing_device_id": 509,
        "role": "WINDOWS_WORKSTATION",
        "target_role": "WORKSTATION-WINDOWS",
        "decision": "READY",
        "action": "UPDATE_SAFE",
        "safe_diffs": ["role:SET:WORKSTATION-WINDOWS"],
        "reasons": ["ROLE_DRIFT:WINDOWS_WORKSTATION->WORKSTATION-WINDOWS"],
    }
    state = {"devices": [{"id": 509, "role": {"name": "WINDOWS_WORKSTATION"}}]}
    planner._normalize_windows_role_aliases([row], state)
    assert row["action"] == "NOOP"
    assert row["safe_diffs"] == []
    assert row["target_role"] == "WINDOWS_WORKSTATION"
    assert row["canonical_target_role"] == "WORKSTATION-WINDOWS"
    assert row["legacy_role_alias_preserved"] is True


def test_04_new_windows_uses_canonical_role():
    row = {
        "existing_device_id": None,
        "role": "WINDOWS_SERVER",
        "target_role": "WINDOWS_SERVER",
        "decision": "READY",
        "action": "CREATE",
        "safe_diffs": [],
    }
    planner._normalize_windows_role_aliases([row], {"devices": []})
    assert row["target_role"] == "SERVER-WINDOWS"


def test_05_stable_audit_key_ignores_name_change():
    left = {"asset_id": "SERIAL:1V683V1", "primary_ip": "10.2.1.22", "desired_name": "VM-BA02"}
    right = {"asset_id": "SERIAL:1V683V1", "primary_ip": "10.2.1.22", "desired_name": "10.2.1.22"}
    assert auditor.stable_plan_key(left) == auditor.stable_plan_key(right)


def test_06_idempotency_accepts_renamed_existing_device():
    original = [{
        "asset_id": "SERIAL:R4P8Z28328", "desired_name": "ECOSYS",
        "primary_ip": "10.2.2.88", "serial": "R4P8Z28328",
    }]
    fresh = {"records": [{
        "asset_id": "SERIAL:R4P8Z28328", "desired_name": "ECOSYS-10-2-2-88",
        "primary_ip": "10.2.2.88", "serial": "R4P8Z28328",
        "decision": "READY", "action": "NOOP", "safe_diffs": [], "ip_intents": [],
    }]}
    checks = []
    auditor.audit_idempotency(original, fresh, checks)
    assert [row["code"] for row in checks] == ["IDEMPOTENCY_NOOP"]
    assert checks[0]["severity"] == "PASS"


def test_07_idempotency_still_reports_real_pending_device_type():
    original = [{
        "asset_id": "SERIAL:ZDEJB07KA24BRWA", "desired_name": "imp-ba01",
        "primary_ip": "10.2.2.80", "serial": "ZDEJB07KA24BRWA",
    }]
    fresh = {"records": [{
        "asset_id": "SERIAL:ZDEJB07KA24BRWA", "desired_name": "imp-ba01",
        "primary_ip": "10.2.2.80", "serial": "ZDEJB07KA24BRWA",
        "decision": "READY", "action": "UPDATE_SAFE",
        "safe_diffs": ["device_type:SET:Samsung|SL-M4020ND"], "ip_intents": [],
    }]}
    checks = []
    auditor.audit_idempotency(original, fresh, checks)
    assert checks[0]["severity"] == "FAIL"
    assert checks[0]["code"] == "IDEMPOTENCY_DEVICE_WRITE_PENDING"


class FakeCatalog(object):
    def __init__(self):
        self.calls = []

    def ensure_device_type(self, manufacturer, model):
        self.calls.append((manufacturer, model))
        return {"id": 777, "manufacturer": {"name": manufacturer}, "model": model}


def _printer_update_row():
    return {
        "decision": "READY",
        "action": "UPDATE_SAFE",
        "confidence": "HIGH",
        "identity_policy": "UPGRADE_PRODUCT_GENERIC_TYPE",
        "manufacturer": "Brother",
        "model": "DCP-L5502DN",
        "safe_diffs": ["device_type:SET:Brother|DCP-L5502DN"],
    }


def _generic_product_device():
    return {
        "description": importer.PRODUCT_DEVICE_DESCRIPTION,
        "device_type": {
            "manufacturer": {"name": "Unidentified"},
            "model": "Generic Printer",
        },
    }


def test_08_importer_applies_exact_device_type_patch():
    payload = {}
    catalog = FakeCatalog()
    importer._ensure_device_type_patch(payload, _printer_update_row(), _generic_product_device(), catalog)
    assert payload["device_type"] == 777
    assert catalog.calls == [("Brother", "DCP-L5502DN")]


def test_09_importer_noops_when_type_is_already_exact():
    payload = {"device_type": 777}
    current = _generic_product_device()
    current["device_type"] = {
        "manufacturer": {"name": "Brother"},
        "model": "DCP-L5502DN",
    }
    catalog = FakeCatalog()
    importer._ensure_device_type_patch(payload, _printer_update_row(), current, catalog)
    assert "device_type" not in payload
    assert catalog.calls == []


def test_10_importer_rejects_manual_device_type_change():
    current = _generic_product_device()
    current["description"] = "Criado manualmente"
    try:
        importer._ensure_device_type_patch({}, _printer_update_row(), current, FakeCatalog())
    except RuntimeError as exc:
        assert "criado pelo netbox-discovery" in str(exc)
    else:
        raise AssertionError("manual Device deveria ser bloqueado")


def test_11_role_alias_is_equivalent_in_direct_audit():
    captured = {}
    original = auditor.ORIGINAL_COMPARE

    def fake_compare(row, device, tenant, site, checks):
        captured["target_role"] = row.get("target_role")

    try:
        auditor.ORIGINAL_COMPARE = fake_compare
        auditor.compare_expected_inventory(
            {"target_role": "WORKSTATION-WINDOWS"},
            {"role": {"name": "WINDOWS_WORKSTATION"}}, {}, {}, [])
    finally:
        auditor.ORIGINAL_COMPARE = original
    assert captured["target_role"] == "WINDOWS_WORKSTATION"


def test_12_component_versions_are_effective_release_versions():
    assert planner.PLANNER_VERSION == "5.2-product"
    assert importer.IMPORTER_VERSION == "6.0-product"
    assert auditor.AUDITOR_VERSION == "6.8-product"


def main():
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    assert len(tests) >= 12, len(tests)
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.11.8 POST-APPLY CORRECTION TESTS PASSED: {0}".format(len(tests)))


if __name__ == "__main__":
    main()
