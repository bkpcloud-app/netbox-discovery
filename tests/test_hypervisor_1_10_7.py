#!/usr/bin/env python3
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
sys.path.insert(0, BASE)

from modules.hypervisor import engine_v3
from modules.hypervisor import engine_v4
from modules.hypervisor import compare as hv_compare


class FakeClusterNetBox(object):
    def __init__(self):
        self.cluster_scope_site = 1
        self.cluster_tenant = 4
        self.device_sites = {301: 1, 302: 1}
        self.patches = []

    def patch(self, endpoint, payload):
        payload = dict(payload)
        self.patches.append((endpoint, payload))
        if endpoint == "virtualization/clusters/4/":
            scope_id = payload.get("scope_id")
            if scope_id is not None:
                wrong = [device_id for device_id, site_id in self.device_sites.items() if site_id != scope_id]
                if wrong:
                    raise RuntimeError("cluster scope validation would fail; hosts still outside target site")
            self.cluster_scope_site = scope_id
            if "tenant" in payload:
                self.cluster_tenant = payload["tenant"]
            return self.cluster_object()
        if endpoint.startswith("dcim/devices/"):
            device_id = int(endpoint.rstrip("/").split("/")[-1])
            target_site = payload.get("site")
            if self.cluster_scope_site is not None and self.cluster_scope_site != target_site:
                raise RuntimeError("device cluster/site validation would fail while cluster remains scoped elsewhere")
            self.device_sites[device_id] = target_site
            return self.device_object(device_id)
        if endpoint.startswith("ipam/ip-addresses/"):
            return {"id": 1, "address": "10.2.1.21/24"}
        raise AssertionError("unexpected patch endpoint: {0}".format(endpoint))

    def cluster_object(self):
        scope = None if self.cluster_scope_site is None else {"id": self.cluster_scope_site, "name": "FBA" if self.cluster_scope_site == 17 else "DCM"}
        return {
            "id": 4,
            "name": "FBA",
            "tenant": {"id": self.cluster_tenant, "name": "MIZU"},
            "scope": scope,
            "scope_id": self.cluster_scope_site,
        }

    def device_object(self, device_id):
        serial = "SERIAL-{0}".format(device_id)
        site_id = self.device_sites[device_id]
        return {
            "id": device_id,
            "name": "10.2.1.{0}".format(21 if device_id == 301 else 22),
            "serial": serial,
            "tenant": {"id": 4, "name": "MIZU"},
            "site": {"id": site_id, "name": "FBA" if site_id == 17 else "DCM"},
            "cluster": {"id": 4, "name": "FBA"},
            "rack": None,
            "location": None,
        }


def _fake_query(nb, endpoint, **kwargs):
    if endpoint == "tenancy/tenants/":
        return [{"id": 4, "name": "MIZU"}]
    if endpoint == "dcim/sites/":
        return [{"id": 1, "name": "DCM"}, {"id": 17, "name": "FBA"}]
    if endpoint == "dcim/devices/":
        return [nb.device_object(301), nb.device_object(302)]
    if endpoint == "virtualization/virtual-machines/":
        return []
    if endpoint == "ipam/ip-addresses/":
        return []
    if endpoint == "dcim/mac-addresses/":
        return []
    if endpoint == "virtualization/clusters/":
        return [nb.cluster_object()]
    if endpoint == "ipam/prefixes/":
        return []
    return []


def _fba_subplan(include_second_host=True):
    rows = [
        {
            "object_type": "CLUSTER", "name": "FBA", "asset_id": "CLUSTER:FBA", "existing_id": 4,
            "decision": "READY", "action": "RECLASSIFY_SAFE", "target_tenant": "MIZU", "target_site": "FBA",
        },
        {
            "object_type": "HOST", "desired_name": "10.2.1.21", "asset_id": "HOST:301", "existing_id": 301,
            "serial": "SERIAL-301", "interfaces": [], "decision": "READY", "action": "RECLASSIFY_SAFE",
            "target_tenant": "MIZU", "target_site": "FBA",
        },
    ]
    if include_second_host:
        rows.append({
            "object_type": "HOST", "desired_name": "10.2.1.22", "asset_id": "HOST:302", "existing_id": 302,
            "serial": "SERIAL-302", "interfaces": [], "decision": "READY", "action": "RECLASSIFY_SAFE",
            "target_tenant": "MIZU", "target_site": "FBA",
        })
    return {"stage": "HYPERVISOR_PLAN", "records": rows, "netbox_write": False}


def test_cluster_scope_is_released_before_hosts_move_and_restored_after():
    nb = FakeClusterNetBox()
    old_query = engine_v4.base.query
    try:
        engine_v4.base.query = _fake_query
        events = engine_v4._safe_apply_reclassifications(
            {"tenant": "MIZU", "site": "FBA"},
            _fba_subplan(),
            nb,
        )
    finally:
        engine_v4.base.query = old_query

    assert nb.patches[0] == ("virtualization/clusters/4/", {"scope_type": None, "scope_id": None})
    assert nb.patches[1][0] == "dcim/devices/301/"
    assert nb.patches[2][0] == "dcim/devices/302/"
    assert nb.patches[3] == ("virtualization/clusters/4/", {"tenant": 4, "scope_type": "dcim.site", "scope_id": 17})
    assert nb.cluster_scope_site == 17
    assert nb.device_sites == {301: 17, 302: 17}
    assert any(event.get("action") == "SCOPE_RELEASED_SAFE" for event in events)


def test_cluster_preflight_blocks_when_member_host_is_not_in_migration_plan():
    nb = FakeClusterNetBox()
    old_query = engine_v4.base.query
    try:
        engine_v4.base.query = _fake_query
        try:
            engine_v4._reclassify_identity_preflight(
                {"tenant": "MIZU", "site": "FBA"},
                _fba_subplan(include_second_host=False),
                nb,
            )
            raise AssertionError("preflight should have blocked incomplete cluster host migration")
        except RuntimeError as exc:
            assert "sem HOST RECLASSIFY_SAFE" in str(exc)
    finally:
        engine_v4.base.query = old_query


def test_compare_effective_vm_site_follows_cluster_scope():
    vm = {"cluster": {"id": 4, "name": "FBA"}, "device": {"id": 301}}
    clusters = {4: {"id": 4, "name": "FBA", "scope": {"id": 17, "name": "FBA"}}}
    devices = {301: {"id": 301, "site": {"id": 17, "name": "FBA"}}}
    assert hv_compare._vm_effective_site(vm, clusters, devices) == "FBA"


def main():
    tests = [
        test_cluster_scope_is_released_before_hosts_move_and_restored_after,
        test_cluster_preflight_blocks_when_member_host_is_not_in_migration_plan,
        test_compare_effective_vm_site_follows_cluster_scope,
    ]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.10.7 HYPERVISOR TESTS PASSED")


if __name__ == "__main__":
    main()
