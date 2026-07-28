#!/usr/bin/env python3
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
sys.path.insert(0, BASE)

from modules.inventory import planner_v3


def test_ip_owned_delegated_row_is_never_downgraded_by_name_bridge():
    old = planner_v3.ORIG_BUILD_PLAN
    try:
        planner_v3.ORIG_BUILD_PLAN = lambda recon, classification, state: ([{
            "asset_id": "A1",
            "desired_name": "pagamento",
            "primary_ip": "10.1.1.155",
            "existing_device_id": None,
            "decision": "DELEGATED",
            "action": "NOOP",
            "match_state": "EXTERNAL_MANAGED",
            "match_reason": "IP(s) já vinculado(s) a virtualization.vminterface",
            "reasons": ["OWNED_BY_HYPERVISOR_VM"],
            "interfaces": [],
            "ip_intents": [],
        }], {})
        recon = {"records": [{
            "asset_id": "A1",
            "hostname": "pagamento",
            "asset_class": "VIRTUAL_MACHINE_CANDIDATE",
        }]}
        state = {"virtual_machines": []}
        plan, _ = planner_v3.build_plan(recon, {}, state)
        row = plan[0]
        assert row["decision"] == "DELEGATED"
        assert row["action"] == "NOOP"
        assert row["reasons"] == ["OWNED_BY_HYPERVISOR_VM"]
        assert row["match_reason"] == "IP(s) já vinculado(s) a virtualization.vminterface"
    finally:
        planner_v3.ORIG_BUILD_PLAN = old


def test_name_bridge_still_blocks_physical_device_vm_conflict():
    old = planner_v3.ORIG_BUILD_PLAN
    try:
        planner_v3.ORIG_BUILD_PLAN = lambda recon, classification, state: ([{
            "asset_id": "A2",
            "desired_name": "SRV-AE11",
            "primary_ip": "10.1.1.111",
            "existing_device_id": 999,
            "decision": "READY",
            "action": "NOOP",
            "reasons": [],
        }], {})
        recon = {"records": [{
            "asset_id": "A2",
            "hostname": "SRV-AE11",
            "asset_class": "VIRTUAL_MACHINE_CANDIDATE",
        }]}
        state = {"virtual_machines": [{"id": 359, "name": "SRV-AE11"}]}
        plan, _ = planner_v3.build_plan(recon, {}, state)
        row = plan[0]
        assert row["decision"] == "BLOCKED"
        assert row["action"] == "CONFLICT"
        assert "PHYSICAL_DEVICE_CONFLICT_WITH_HYPERVISOR_VM:359" in row["reasons"]
    finally:
        planner_v3.ORIG_BUILD_PLAN = old


def main():
    tests = [
        test_ip_owned_delegated_row_is_never_downgraded_by_name_bridge,
        test_name_bridge_still_blocks_physical_device_vm_conflict,
    ]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.10.13 IP DELEGATION PRECEDENCE TESTS PASSED")


if __name__ == "__main__":
    main()
