#!/usr/bin/env python3
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
sys.path.insert(0, BASE)

from modules.inventory import classifier_v2
from modules.inventory import planner_v2


def test_dell_switch_models_outrank_generic_linux_snmp():
    samples = [
        {
            "snmp_entity_primary": {"model": "N2024", "manufacturer": "Dell"},
            "snmp_entity_inventory": [],
            "open_services": [{"port": 22, "protocol": "tcp"}],
        },
        {
            "snmp_entity_primary": {"model": "PCT7024", "manufacturer": ""},
            "snmp_entity_inventory": [],
            "open_services": [{"port": 443, "protocol": "tcp"}],
        },
        {
            "snmp_entity_primary": {"model": "S4128F-ON", "manufacturer": "Dell"},
            "snmp_entity_inventory": [],
            "open_services": [],
        },
    ]
    for sample in samples:
        role, score, evidence = classifier_v2.classify_role(sample, "linux openssh web")
        assert role == "NETWORK_SWITCH"
        assert score == 98
        assert evidence
        manufacturer, source = classifier_v2.infer_manufacturer(sample, "", {}, role)
        assert manufacturer == "Dell"
        assert source == "hardware-model-fingerprint"


def _fake_plan_row(ip="10.1.1.3", asset_id="A1"):
    return {
        "asset_id": asset_id,
        "decision": "REVIEW",
        "action": "CREATE",
        "match_state": "NEW",
        "match_reason": "Sem correspondência",
        "existing_device_id": None,
        "primary_ip": ip,
        "ips": [ip],
        "oob_ips": [],
        "reasons": ["IP_ASSIGNED_TO_EXTERNAL_OBJECT:{0}:virtualization.vminterface".format(ip)],
        "interfaces": [{"ip": ip}],
        "ip_intents": [{"ip": ip, "action": "EXTERNAL_ASSIGNED"}],
    }


def test_vm_owned_ip_is_delegated_not_reviewed_or_created():
    original = planner_v2.ORIG_BUILD_PLAN
    try:
        planner_v2.ORIG_BUILD_PLAN = lambda recon, classification, state: ([_fake_plan_row()], {})
        recon = {"records": [{"asset_id": "A1", "asset_class": "HOST_OR_APPLIANCE", "macs": []}]}
        state = {
            "ips": [{
                "address": "10.1.1.3/24",
                "assigned_object_type": "virtualization.vminterface",
                "assigned_object_id": 123,
            }]
        }
        plan, _ = planner_v2.build_plan(recon, {"records": []}, state)
        row = plan[0]
        assert row["decision"] == "DELEGATED"
        assert row["action"] == "NOOP"
        assert row["reasons"] == ["OWNED_BY_HYPERVISOR_VM"]
        assert row["interfaces"] == []
        assert row["ip_intents"] == []
    finally:
        planner_v2.ORIG_BUILD_PLAN = original


def test_vmware_mac_without_vm_match_is_review_not_physical_create():
    original = planner_v2.ORIG_BUILD_PLAN
    try:
        row = _fake_plan_row(ip="10.1.1.111", asset_id="A2")
        row["decision"] = "READY"
        row["reasons"] = []
        row["interfaces"] = [{"ip": "10.1.1.111"}]
        row["ip_intents"] = [{"ip": "10.1.1.111", "action": "ENSURE"}]
        planner_v2.ORIG_BUILD_PLAN = lambda recon, classification, state: ([row], {})
        recon = {"records": [{
            "asset_id": "A2",
            "asset_class": "HOST_OR_APPLIANCE",
            "macs": ["00:50:56:AA:BB:CC"],
        }]}
        plan, _ = planner_v2.build_plan(recon, {"records": []}, {"ips": []})
        out = plan[0]
        assert out["decision"] == "REVIEW"
        assert out["action"] == "CREATE"
        assert "VIRTUAL_MACHINE_CANDIDATE_NO_VM_MATCH" in out["reasons"]
    finally:
        planner_v2.ORIG_BUILD_PLAN = original


def main():
    tests = [
        test_dell_switch_models_outrank_generic_linux_snmp,
        test_vm_owned_ip_is_delegated_not_reviewed_or_created,
        test_vmware_mac_without_vm_match_is_review_not_physical_create,
    ]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.10.10 NETWORK OWNERSHIP/SWITCH TESTS PASSED")


if __name__ == "__main__":
    main()
