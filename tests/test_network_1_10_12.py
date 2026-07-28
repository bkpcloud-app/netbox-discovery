#!/usr/bin/env python3
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
sys.path.insert(0, BASE)

from modules.discovery import network_v3
from modules.inventory import classifier_v4, planner_v3, reconciler_v4


def test_vmware_history_is_sticky_when_current_mac_is_missing():
    data = {"records": [{
        "ip": "10.1.1.111", "role": "WINDOWS_HOST", "asset_class": "HOST_OR_APPLIANCE",
        "classification_score": 95, "confidence": "HIGH", "evidence": ["Windows services/fingerprint"],
    }]}
    previous = {
        "ip": "10.1.1.111", "role": "WINDOWS_HOST", "asset_class": "VIRTUAL_MACHINE_CANDIDATE",
        "management_mac": "00:50:56:9F:9E:70", "evidence": ["Windows services/fingerprint"],
    }
    history = {"10.1.1.111": {"vm": ("old-classification.json", previous), "storage": None}}
    out = classifier_v4.apply_identity_history(data, history)
    row = out["records"][0]
    assert row["asset_class"] == "VIRTUAL_MACHINE_CANDIDATE"
    assert row["historical_vmware_mac"] == "00:50:56:9F:9E:70"
    assert "Historical VMware identity retained after transient MAC miss" in row["evidence"]


def test_vmware_history_does_not_override_strong_physical_switch():
    data = {"records": [{
        "ip": "10.1.1.31", "role": "NETWORK_SWITCH", "asset_class": "PHYSICAL_DEVICE",
        "serial": "ABC123", "snmp_object_id": ".1.3.6.1.4.1.674", "classification_score": 99,
        "confidence": "HIGH", "evidence": ["Dell network-switch hardware model fingerprint"],
    }]}
    previous = {"ip": "10.1.1.31", "asset_class": "VIRTUAL_MACHINE_CANDIDATE", "management_mac": "00:50:56:00:00:01"}
    history = {"10.1.1.31": {"vm": ("old.json", previous), "storage": None}}
    row = classifier_v4.apply_identity_history(data, history)["records"][0]
    assert row["asset_class"] == "PHYSICAL_DEVICE"
    assert not row.get("historical_vmware_mac")


def test_storage_history_restores_array_identity_after_fa_mib_miss():
    data = {"records": [{
        "ip": "10.1.1.53", "role": "SNMP_DEVICE", "asset_class": "HOST_OR_APPLIANCE",
        "manufacturer": "Seagate", "model": "Generic Snmp Device", "serial": "",
        "classification_score": 48, "confidence": "LOW", "evidence": ["SNMP responds but role unresolved"],
    }]}
    previous = {
        "ip": "10.1.1.53", "role": "STORAGE", "asset_class": "PHYSICAL_DEVICE",
        "manufacturer": "Dell", "model": "DELL EMC ME4024", "serial": "CN0PJ27VFCG0091F01VNA00",
        "storage_unit_id": "208000C0FFF069900000000000000000", "storage_unit_type": "storage-subsystem(11)",
        "storage_unit_product": "DELL EMC ME4024", "classification_score": 99, "confidence": "HIGH",
    }
    history = {"10.1.1.53": {"vm": None, "storage": ("old-storage.json", previous)}}
    row = classifier_v4.apply_identity_history(data, history)["records"][0]
    assert row["role"] == "STORAGE"
    assert row["confidence"] == "HIGH"
    assert row["manufacturer"] == "Dell"
    assert row["model"] == "DELL EMC ME4024"
    assert row["serial"] == "CN0PJ27VFCG0091F01VNA00"
    assert row["storage_unit_id"] == "208000C0FFF069900000000000000000"


def test_zero_fa_id_is_not_identity_but_serial_still_classifies_storage():
    d = {"snmp_entity_primary": {
        "fa_conn_unit_type_id": "11", "fa_conn_unit_type": "storage-subsystem(11)",
        "fa_conn_unit_id": "00000000000000000000000000000000",
        "fa_conn_unit_product": "DELL EMC ME4012", "fa_conn_unit_serial": "CN0H8X8MFCG0012402QXA01",
        "fa_conn_unit_vendor": "Dell",
    }}
    fa = classifier_v4.fa_storage(d)
    assert fa["unit_id"] == ""
    assert fa["serial"] == "CN0H8X8MFCG0012402QXA01"
    assert fa["product"] == "DELL EMC ME4012"


def test_reconciler_preserves_history_conflict_for_planner():
    old = reconciler_v4.ORIG_BUILD_ASSETS
    try:
        reconciler_v4.ORIG_BUILD_ASSETS = lambda records: ([{
            "asset_id": "A1", "primary_ip": "10.1.1.53", "ips": ["10.1.1.53"],
            "asset_class": "PHYSICAL_DEVICE", "role": "STORAGE",
        }], [], [])
        assets, _, _ = reconciler_v4.build_assets([{
            "ip": "10.1.1.53", "historical_identity_conflict": "storage-serial",
        }])
        assert assets[0]["historical_identity_conflict"] == "storage-serial"
    finally:
        reconciler_v4.ORIG_BUILD_ASSETS = old


def test_unique_vm_name_delegates_vm_candidate():
    old = planner_v3.ORIG_BUILD_PLAN
    try:
        planner_v3.ORIG_BUILD_PLAN = lambda recon, classification, state: ([{
            "asset_id": "A1", "desired_name": "SRV-AE11", "primary_ip": "10.1.1.111",
            "existing_device_id": None, "decision": "REVIEW", "action": "CREATE",
            "reasons": ["VIRTUAL_MACHINE_CANDIDATE_NO_VM_MATCH"], "interfaces": [{"ip": "10.1.1.111"}],
            "ip_intents": [{"ip": "10.1.1.111", "action": "CREATE"}],
        }], {})
        recon = {"records": [{"asset_id": "A1", "hostname": "SRV-AE11", "asset_class": "VIRTUAL_MACHINE_CANDIDATE"}]}
        state = {"virtual_machines": [{"id": 321, "name": "SRV-AE11"}]}
        plan, _ = planner_v3.build_plan(recon, {}, state)
        row = plan[0]
        assert row["decision"] == "DELEGATED"
        assert row["action"] == "NOOP"
        assert row["reasons"] == ["OWNED_BY_HYPERVISOR_VM_NAME:321"]
        assert row["interfaces"] == []
    finally:
        planner_v3.ORIG_BUILD_PLAN = old


def test_existing_physical_device_is_blocked_when_vm_identity_matches():
    old = planner_v3.ORIG_BUILD_PLAN
    try:
        planner_v3.ORIG_BUILD_PLAN = lambda recon, classification, state: ([{
            "asset_id": "A1", "desired_name": "SRV-AE11", "primary_ip": "10.1.1.111",
            "existing_device_id": 999, "decision": "READY", "action": "NOOP", "reasons": [],
        }], {})
        recon = {"records": [{"asset_id": "A1", "hostname": "SRV-AE11", "asset_class": "VIRTUAL_MACHINE_CANDIDATE"}]}
        state = {"virtual_machines": [{"id": 321, "name": "SRV-AE11"}]}
        plan, _ = planner_v3.build_plan(recon, {}, state)
        row = plan[0]
        assert row["decision"] == "BLOCKED"
        assert row["action"] == "CONFLICT"
        assert "PHYSICAL_DEVICE_CONFLICT_WITH_HYPERVISOR_VM:321" in row["reasons"]
    finally:
        planner_v3.ORIG_BUILD_PLAN = old


def test_fa_probe_retries_safe_reads():
    old = network_v3.ORIG_FA_PROBE
    calls = []
    try:
        def fake(ip, snmp):
            calls.append(ip)
            if len(calls) < 3:
                return {"primary": {}, "units": [], "count": 0}
            return {"primary": {"conn_unit_id": "ABCDEF"}, "units": [], "count": 1}
        network_v3.ORIG_FA_PROBE = fake
        out = network_v3.probe_snmp_fa_connectivity("10.1.1.53", {"available": True})
        assert out["primary"]["conn_unit_id"] == "ABCDEF"
        assert len(calls) == 3
    finally:
        network_v3.ORIG_FA_PROBE = old


def main():
    tests = [
        test_vmware_history_is_sticky_when_current_mac_is_missing,
        test_vmware_history_does_not_override_strong_physical_switch,
        test_storage_history_restores_array_identity_after_fa_mib_miss,
        test_zero_fa_id_is_not_identity_but_serial_still_classifies_storage,
        test_reconciler_preserves_history_conflict_for_planner,
        test_unique_vm_name_delegates_vm_candidate,
        test_existing_physical_device_is_blocked_when_vm_identity_matches,
        test_fa_probe_retries_safe_reads,
    ]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.10.12 IDENTITY ANTI-FLAP TESTS PASSED")


if __name__ == "__main__":
    main()
