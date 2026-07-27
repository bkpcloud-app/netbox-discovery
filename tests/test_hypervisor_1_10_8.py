#!/usr/bin/env python3
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
sys.path.insert(0, BASE)

from modules.hypervisor import engine_v4


class FakeNB(object):
    def __init__(self, device_site_id=26):
        self.device_site_id = device_site_id
        self.patches = []

    def patch(self, endpoint, payload):
        payload = dict(payload)
        self.patches.append((endpoint, payload))
        if endpoint.startswith("virtualization/virtual-machines/"):
            if payload.get("site") != self.device_site_id:
                raise RuntimeError("NetBox device/site validation would fail")
            return {"id": 467, "name": "SRV-PXM-HIKCENTRAL", "tenant": {"id": payload.get("tenant")}, "site": {"id": payload.get("site")}}
        if endpoint.startswith("ipam/ip-addresses/"):
            return {"id": 9001, "address": "10.36.1.5/24", "tenant": {"id": payload.get("tenant")}}
        raise AssertionError("unexpected PATCH: {0}".format(endpoint))


def fake_query_factory(device_site_id=26):
    def fake_query(nb, endpoint, **kwargs):
        if endpoint == "tenancy/tenants/":
            return [{"id": 4, "name": "MIZU"}, {"id": 5, "name": "PXMETAIS"}]
        if endpoint == "dcim/sites/":
            return [{"id": 1, "name": "DCM"}, {"id": 26, "name": "MAC"}]
        if endpoint == "dcim/devices/":
            return [{
                "id": 312,
                "name": "10.36.1.21",
                "serial": "HOST-312",
                "tenant": {"id": 5, "name": "PXMETAIS"},
                "site": {"id": device_site_id, "name": "MAC" if device_site_id == 26 else "DCM"},
            }]
        if endpoint == "virtualization/virtual-machines/":
            return [{
                "id": 467,
                "name": "SRV-PXM-HIKCENTRAL",
                "serial": "",
                "tenant": {"id": 4, "name": "MIZU"},
                "site": {"id": 1, "name": "DCM"},
                "device": {"id": 312, "name": "10.36.1.21"},
                "cluster": None,
            }]
        if endpoint == "ipam/ip-addresses/":
            return [{
                "id": 9001,
                "address": "10.36.1.5/24",
                "tenant": {"id": 4, "name": "MIZU"},
                "assigned_object_type": "virtualization.vminterface",
                "assigned_object": {"id": 504, "virtual_machine": {"id": 467}},
            }]
        if endpoint == "dcim/mac-addresses/":
            return []
        if endpoint == "virtualization/clusters/":
            return []
        if endpoint == "ipam/prefixes/":
            return []
        return []
    return fake_query


def vm_subplan():
    return {"stage": "HYPERVISOR_PLAN", "records": [{
        "object_type": "VM",
        "asset_id": "VM:467",
        "desired_name": "SRV-PXM-HIKCENTRAL",
        "existing_id": 467,
        "serial": "",
        "interfaces": [{"name": "eth0", "ip": "10.36.1.5", "address": "10.36.1.5/24", "mac": ""}],
        "decision": "READY",
        "action": "RECLASSIFY_SAFE",
        "target_tenant": "PXMETAIS",
        "target_site": "MAC",
        "source": {"host_name": "10.36.1.21"},
    }], "netbox_write": False}


def test_vm_reclassification_patches_tenant_and_site_atomically():
    old_query = engine_v4.base.query
    try:
        engine_v4.base.query = fake_query_factory(device_site_id=26)
        nb = FakeNB(device_site_id=26)
        events = engine_v4._safe_apply_reclassifications(
            {"tenant": "PXMETAIS", "site": "MAC"},
            vm_subplan(),
            nb,
        )
    finally:
        engine_v4.base.query = old_query

    assert ("virtualization/virtual-machines/467/", {"tenant": 5, "site": 26}) in nb.patches
    assert ("ipam/ip-addresses/9001/", {"tenant": 5}) in nb.patches
    assert any(x.get("object_type") == "VM" and x.get("action") == "RECLASSIFIED_SAFE" for x in events)


def test_vm_parent_preflight_blocks_if_device_is_still_in_old_site():
    old_query = engine_v4.base.query
    try:
        engine_v4.base.query = fake_query_factory(device_site_id=1)
        nb = FakeNB(device_site_id=1)
        try:
            engine_v4._vm_parent_preflight(
                {"tenant": "PXMETAIS", "site": "MAC"},
                vm_subplan(),
                nb,
                26,
            )
            raise AssertionError("parent preflight should block VM while its device is outside target Site")
        except RuntimeError as exc:
            assert "ainda está fora do Site alvo" in str(exc)
    finally:
        engine_v4.base.query = old_query


def main():
    tests = [
        test_vm_reclassification_patches_tenant_and_site_atomically,
        test_vm_parent_preflight_blocks_if_device_is_still_in_old_site,
    ]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.10.8 HYPERVISOR TESTS PASSED")


if __name__ == "__main__":
    main()
