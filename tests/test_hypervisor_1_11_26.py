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
    if endpoint in (
        "ipam/ip-addresses/",
        "dcim/mac-addresses/",
        "dcim/devices/",
        "virtualization/clusters/",
        "ipam/prefixes/",
    ):
        return []
    return []


def plan_row(decision="READY", action="NOOP"):
    return {
        "object_type": "VM",
        "asset_id": "VM:UUID-SRV-AB01",
        "desired_name": "SRV-AB01",
        "serial": "UUID-SRV-AB01",
        "decision": decision,
        "action": action,
        "target_tenant": "MIZU",
        "target_site": "FAB",
        "interfaces": [],
        "source": {"host_name": "10.5.1.21"},
    }


def test_real_fab_shape_ready_noop_wrong_site_becomes_reclassify_safe():
    old_query = engine_v5.base.query
    try:
        engine_v5.base.query = fake_query
        plan = {"records": [plan_row("READY", "NOOP")]}
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


def test_review_noop_is_not_promoted():
    old_query = engine_v5.base.query
    try:
        engine_v5.base.query = fake_query
        plan = {"records": [plan_row("REVIEW", "NOOP")]}
        engine_v5._plan_reclassifications_with_parent_site(plan, object())
        row = plan["records"][0]
        assert row["decision"] == "REVIEW"
        assert row["action"] == "NOOP"
        assert row.get("pending_reason") != "VM_SITE_INHERIT_FROM_PARENT"
    finally:
        engine_v5.base.query = old_query


def test_engine_version_records_noop_fix():
    assert engine_v5.ENGINE_VERSION == "5.1-product"


def main():
    tests = [
        test_real_fab_shape_ready_noop_wrong_site_becomes_reclassify_safe,
        test_review_noop_is_not_promoted,
        test_engine_version_records_noop_fix,
    ]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.11.26 HYPERVISOR NOOP SITE INHERITANCE TESTS PASSED")


if __name__ == "__main__":
    main()
