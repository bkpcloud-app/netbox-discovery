#!/usr/bin/env python3
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
sys.path.insert(0, BASE)

from modules.hypervisor import engine_v5


def fake_query(nb, endpoint, **kwargs):
    if endpoint == "tenancy/tenants/":
        return [{"id": 4, "name": "MIZU"}]
    if endpoint == "dcim/sites/":
        return [
            {"id": 1, "name": "DCM"},
            {"id": 16, "name": "FAB"},
        ]
    if endpoint == "virtualization/virtual-machines/":
        return [{
            "id": 501,
            "name": "SRV-AB01",
            "serial": "UUID-SRV-AB01",
            "tenant": {"id": 4, "name": "MIZU"},
            "site": {"id": 1, "name": "DCM"},
            "device": {"id": 313, "name": "10.5.1.21"},
            "cluster": None,
        }]
    if endpoint == "ipam/ip-addresses/":
        return []
    if endpoint == "dcim/mac-addresses/":
        return []
    if endpoint == "dcim/devices/":
        return []
    if endpoint == "virtualization/clusters/":
        return []
    if endpoint == "ipam/prefixes/":
        return []
    return []


def test_parent_attached_vm_with_wrong_site_becomes_reclassify_safe():
    old_query = engine_v5.base.query
    try:
        engine_v5.base.query = fake_query
        plan = {"records": [{
            "object_type": "VM",
            "asset_id": "VM:UUID-SRV-AB01",
            "desired_name": "SRV-AB01",
            "serial": "UUID-SRV-AB01",
            "decision": "REVIEW",
            "action": "CREATE",
            "target_tenant": "MIZU",
            "target_site": "FAB",
            "interfaces": [],
            "source": {"host_name": "10.5.1.21"},
        }]}
        engine_v5._plan_reclassifications_with_parent_site(plan, object())
        row = plan["records"][0]
        assert row["decision"] == "READY"
        assert row["action"] == "RECLASSIFY_SAFE"
        assert row["existing_id"] == 501
        assert row["migration_source_site"] == "DCM"
        assert row["pending_reason"] == "VM_SITE_INHERIT_FROM_PARENT"
        assert "MIZU/FAB" in row["reason"]
    finally:
        engine_v5.base.query = old_query


def test_runtime_runner_uses_engine_v5():
    runner = open(os.path.join(BASE, "modules", "hypervisor", "runner.py"), "r").read()
    assert "from modules.hypervisor import engine_v5 as engine" in runner


def main():
    tests = [
        test_parent_attached_vm_with_wrong_site_becomes_reclassify_safe,
        test_runtime_runner_uses_engine_v5,
    ]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.11.25 HYPERVISOR VM SITE TESTS PASSED")


if __name__ == "__main__":
    main()
