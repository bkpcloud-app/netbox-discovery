#!/usr/bin/env python3
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
sys.path.insert(0, BASE)

from modules.hypervisor import resolver
from modules.hypervisor import config as hv_config
from modules.hypervisor import configurator as hv_configurator


def host(name, ip, prefix=24, cluster="", datacenter="", extra_management=None, provider="vmware"):
    interfaces = [{
        "name": "vmk0", "management": True, "mac": "",
        "ips": [{"address": ip, "prefix_length": prefix, "primary": True}],
    }]
    for pos, item in enumerate(extra_management or [], 1):
        address, item_prefix = item
        interfaces.append({
            "name": "vmk{0}".format(pos), "management": True, "mac": "",
            "ips": [{"address": address, "prefix_length": item_prefix, "primary": True}],
        })
    return {
        "provider": provider,
        "name": name,
        "cluster": cluster,
        "datacenter": datacenter,
        "interfaces": interfaces,
    }


def vm(name, host_name, ip=""):
    ips = [] if not ip else [{"address": ip, "prefix_length": 24, "primary": True}]
    return {"name": name, "host_name": host_name, "interfaces": [{"name": "eth0", "management": False, "ips": ips}]}


def test_management_network_grouping():
    raw = {"hosts": [host("ESX-DCM", "10.1.1.21"), host("ESX-FBA", "10.2.1.21")]}
    groups = resolver.management_network_groups(raw)
    assert [x["network"] for x in groups] == ["10.1.1.0/24", "10.2.1.0/24"]


def test_authoritative_management_prefers_vmk0_over_auxiliary_service_networks():
    h = host(
        "ESX-DCM",
        "10.1.1.21",
        datacenter="DCM",
        extra_management=[("192.168.140.21", 24), ("192.168.160.21", 24), ("192.168.180.21", 24)],
    )
    assert resolver.authoritative_management_networks(h) == ["10.1.1.0/24"]
    groups = resolver.management_network_groups({"hosts": [h]})
    assert [x["network"] for x in groups] == ["10.1.1.0/24"]


def test_authoritative_management_dns_match_can_select_non_vmk0():
    h = {
        "provider": "vmware",
        "name": "esx-dns.example.local",
        "interfaces": [
            {"name": "vmk0", "management": True, "ips": [{"address": "192.168.200.21", "prefix_length": 24}]},
            {"name": "vmk2", "management": True, "ips": [{"address": "10.20.1.21", "prefix_length": 24}]},
        ],
    }
    old = resolver.socket.getaddrinfo
    try:
        resolver.socket.getaddrinfo = lambda name, port: [(2, 1, 6, "", ("10.20.1.21", 0))]
        assert resolver.authoritative_management_networks(h) == ["10.20.1.0/24"]
    finally:
        resolver.socket.getaddrinfo = old


def test_authoritative_management_ambiguous_without_dns_or_vmk0_is_unresolved():
    h = {
        "provider": "vmware",
        "name": "",
        "interfaces": [
            {"name": "vmk1", "management": True, "ips": [{"address": "10.10.1.21", "prefix_length": 24}]},
            {"name": "vmk2", "management": True, "ips": [{"address": "10.20.1.21", "prefix_length": 24}]},
        ],
    }
    assert resolver.authoritative_management_networks(h) == []


def test_management_placement_groups_collapse_same_datacenter():
    raw = {"hosts": [
        host("ESX01", "10.1.1.21", cluster="Cluster", datacenter="DCM", extra_management=[("192.168.140.21", 24)]),
        host("ESX02", "10.1.1.22", cluster="Cluster", datacenter="DCM", extra_management=[("192.168.140.22", 24)]),
    ]}
    groups = resolver.management_placement_groups(raw)
    assert len(groups) == 1
    group = groups[0]
    assert group["kind"] == "datacenter"
    assert group["label"] == "DCM"
    assert group["hosts"] == ["ESX01", "ESX02"]
    assert group["networks"] == ["10.1.1.0/24"]


def test_live_shape_four_hosts_eleven_management_service_networks_use_one_authoritative_network():
    names = ["vm-ae01.mizu.local", "vm-ae02.mizu.local", "vm-ae03.mizu.local", "vm-ae04.mizu.local"]
    rows = []
    auxiliary_networks = [140, 141, 142, 143, 160, 161, 180, 181, 190, 191]
    for idx, name in enumerate(names, 21):
        extras = [("192.168.{0}.{1}".format(net, idx), 24) for net in auxiliary_networks]
        rows.append(host(name, "10.1.1.{0}".format(idx), cluster="Cluster", datacenter="DCM", extra_management=extras))
    groups = resolver.management_placement_groups({"hosts": rows})
    assert len(groups) == 1
    group = groups[0]
    assert group["kind"] == "datacenter"
    assert group["label"] == "DCM"
    assert len(group["hosts"]) == 4
    assert group["networks"] == ["10.1.1.0/24"]


def test_network_subgroups_preserve_per_network_hosts():
    raw = {"hosts": [
        host("ESX01", "10.1.1.21", cluster="Cluster", datacenter="DCM"),
        host("ESX02", "10.2.1.22", cluster="Cluster", datacenter="DCM"),
    ]}
    group = resolver.management_placement_groups(raw)[0]
    rows = hv_configurator._network_subgroups(group)
    by_network = dict((x["label"], x) for x in rows)
    assert by_network["10.1.1.0/24"]["hosts"] == ["ESX01"]
    assert by_network["10.2.1.0/24"]["hosts"] == ["ESX02"]


def test_management_placement_groups_keep_datacenters_separate():
    raw = {"hosts": [
        host("ESX-DCM", "10.1.1.21", datacenter="DCM"),
        host("ESX-FBA", "10.2.1.21", datacenter="FBA"),
    ]}
    groups = resolver.management_placement_groups(raw)
    assert [(x["kind"], x["label"], x["networks"]) for x in groups] == [
        ("datacenter", "DCM", ["10.1.1.0/24"]),
        ("datacenter", "FBA", ["10.2.1.0/24"]),
    ]


def test_management_placement_group_does_not_merge_ambiguous_network():
    shared = "10.99.1.0/24"
    raw = {"hosts": [
        host("ESX-A", "10.99.1.21", datacenter="DC-A"),
        host("ESX-B", "10.99.1.22", datacenter="DC-B"),
    ]}
    groups = resolver.management_placement_groups(raw)
    assert len(groups) == 1
    assert groups[0]["kind"] == "network"
    assert groups[0]["label"] == shared
    assert sorted(groups[0]["datacenters"]) == ["DC-A", "DC-B"]


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
        test_authoritative_management_prefers_vmk0_over_auxiliary_service_networks,
        test_authoritative_management_dns_match_can_select_non_vmk0,
        test_authoritative_management_ambiguous_without_dns_or_vmk0_is_unresolved,
        test_management_placement_groups_collapse_same_datacenter,
        test_live_shape_four_hosts_eleven_management_service_networks_use_one_authoritative_network,
        test_network_subgroups_preserve_per_network_hosts,
        test_management_placement_groups_keep_datacenters_separate,
        test_management_placement_group_does_not_merge_ambiguous_network,
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
