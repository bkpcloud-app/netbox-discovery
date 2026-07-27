#!/usr/bin/env python3
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
sys.path.insert(0, BASE)

from modules.hypervisor import resolver
from modules.hypervisor import config as hv_config


def host(name, ip, prefix=24, cluster=""):
    return {
        "name": name,
        "cluster": cluster,
        "interfaces": [{
            "name": "vmk0", "management": True, "mac": "",
            "ips": [{"address": ip, "prefix_length": prefix, "primary": True}],
        }],
    }


def vm(name, host_name, ip=""):
    ips = [] if not ip else [{"address": ip, "prefix_length": 24, "primary": True}]
    return {"name": name, "host_name": host_name, "interfaces": [{"name": "eth0", "management": False, "ips": ips}]}


def test_management_network_grouping():
    raw = {"hosts": [host("ESX-DCM", "10.1.1.21"), host("ESX-FBA", "10.2.1.21")]}
    groups = resolver.management_network_groups(raw)
    assert [x["network"] for x in groups] == ["10.1.1.0/24", "10.2.1.0/24"]


def test_vm_inherits_host_context():
    source = {
        "id": "vc1", "inventory_mode": "multi_tenant",
        "mappings": [
            {"network": "10.1.1.0/24", "tenant_group": "POLIMIX", "tenant": "MIZU", "site": "DCM"},
            {"network": "10.2.1.0/24", "tenant_group": "POLIMIX", "tenant": "MIZU", "site": "FBA"},
        ],
    }
    h = host("ESX-FBA", "10.2.1.21")
    ctx = resolver.resolve_host(h, source, "MIZU", "DCM", "POLIMIX")
    host_contexts = {("vc1", "esx-fba"): ctx}
    vctx = resolver.resolve_vm(vm("APP01", "ESX-FBA", "192.168.50.10"), source, host_contexts, "MIZU", "DCM", "POLIMIX")
    assert vctx["tenant"] == "MIZU" and vctx["site"] == "FBA"


def test_unmapped_host_is_not_guessed():
    source = {
        "id": "vc1", "inventory_mode": "multi_tenant",
        "mappings": [{"network": "10.1.1.0/24", "tenant": "MIZU", "site": "DCM"}],
    }
    assert resolver.resolve_host(host("ESX-UNKNOWN", "10.7.1.21"), source, "MIZU", "DCM", "POLIMIX") is None


def test_multi_site_uses_default_tenant():
    source = {
        "id": "vc1", "inventory_mode": "multi_site",
        "mappings": [{"network": "10.2.1.0/24", "site": "FBA"}],
    }
    ctx = resolver.resolve_host(host("ESX-FBA", "10.2.1.22"), source, "MIZU", "DCM", "POLIMIX")
    assert ctx["tenant"] == "MIZU" and ctx["site"] == "FBA"


def test_config_requires_mapping_for_multi_mode():
    source = {
        "id": "vc1", "type": "vmware", "endpoint": "10.1.1.10",
        "username": "svc", "secret": "x", "inventory_mode": "multi_tenant", "mappings": [],
    }
    try:
        hv_config.validate_source(source)
        raise AssertionError("multi_tenant sem mapping deveria falhar")
    except RuntimeError as exc:
        assert "exige ao menos um mapping" in str(exc)


def test_config_accepts_multi_tenant_mapping():
    source = {
        "id": "vc1", "type": "vmware", "endpoint": "10.1.1.10",
        "username": "svc", "secret": "x", "inventory_mode": "multi_tenant",
        "mappings": [{"network": "10.2.1.0/24", "tenant_group": "POLIMIX", "tenant": "MIZU", "site": "FBA"}],
    }
    hv_config.validate_source(source)


def test_global_identity_guard_blocks_duplicate_create():
    from modules.hypervisor import engine_v3
    old_query = engine_v3.base.query
    try:
        def fake_query(nb, endpoint, **kwargs):
            if endpoint == "dcim/devices/":
                return [{"id": 77, "name": "ESX-OLD", "serial": "SERIAL-001"}]
            if endpoint == "virtualization/virtual-machines/":
                return []
            return []
        engine_v3.base.query = fake_query
        plan = {"records": [{
            "object_type": "HOST", "desired_name": "ESX-FBA", "serial": "SERIAL-001",
            "decision": "READY", "action": "CREATE", "target_tenant": "MIZU", "target_site": "FBA",
        }]}
        engine_v3._global_identity_guard(plan, object())
        row = plan["records"][0]
        assert row["decision"] == "REVIEW"
        assert "reclassificação/migração" in row["reason"]
    finally:
        engine_v3.base.query = old_query


def main():
    tests = [
        test_management_network_grouping,
        test_vm_inherits_host_context,
        test_unmapped_host_is_not_guessed,
        test_multi_site_uses_default_tenant,
        test_config_requires_mapping_for_multi_mode,
        test_config_accepts_multi_tenant_mapping,
        test_global_identity_guard_blocks_duplicate_create,
    ]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.10 HYPERVISOR TESTS PASSED")


if __name__ == "__main__":
    main()
