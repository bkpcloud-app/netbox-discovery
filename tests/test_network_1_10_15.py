#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.inventory import planner_v4, planner_v5
from modules.importers import importer_v5


def repair_state():
    return {
        "tenant": {"id": 4},
        "site": {"id": 1},
        "devices": [{
            "id": 999,
            "name": "SRV-AE11",
            "description": planner_v4.PRODUCT_DEVICE_DESCRIPTION,
            "serial": "",
            "tenant": {"id": 4},
            "site": {"id": 1},
            "primary_ip4": {"id": 22, "address": "10.1.1.111/24"},
            "rack": None,
            "location": None,
            "cluster": None,
            "virtual_chassis": None,
            "device_bay": None,
        }],
        "interfaces": [{
            "id": 11,
            "device": {"id": 999},
            "name": "MGMT",
            "description": planner_v4.PRODUCT_INTERFACE_DESCRIPTION,
            "primary_mac_address": None,
            "cable": None,
            "mark_connected": False,
        }],
        "vm_interfaces": [{
            "id": 55,
            "virtual_machine": {"id": 359},
            "name": "Network adapter 1",
            "primary_mac_address": {"id": 44, "mac_address": "00:50:56:9F:9E:70"},
            "mac_addresses": [],
        }],
        "virtual_machines": [{
            "id": 359,
            "name": "SRV-AE11",
            "tenant": {"id": 4},
            "site": {"id": 1},
            "primary_ip4": None,
        }],
        "ips": [{
            "id": 22,
            "address": "10.1.1.111/24",
            "description": planner_v4.PRODUCT_IP_DESCRIPTION,
            "tenant": {"id": 4},
            "assigned_object_type": "dcim.interface",
            "assigned_object_id": 11,
            "assigned_object": {"id": 11},
        }],
        "macs": [{
            "id": 44,
            "mac_address": "00:50:56:9F:9E:70",
            "description": "Descoberto pelo netbox-discovery hypervisor",
            "assigned_object_type": "virtualization.vminterface",
            "assigned_object_id": 55,
            "assigned_object": {"id": 55},
        }],
        "inventory_items": [],
        "console_ports": [],
        "console_server_ports": [],
        "power_ports": [],
        "power_outlets": [],
        "front_ports": [],
        "rear_ports": [],
        "device_bays": [],
        "module_bays": [],
    }


def test_historical_vmware_mac_promotes_safe_repair():
    old = planner_v4.ORIG_BUILD_PLAN
    try:
        planner_v4.ORIG_BUILD_PLAN = lambda recon, classification, state: ([{
            "asset_id": "A1",
            "desired_name": "SRV-AE11",
            "primary_ip": "10.1.1.111",
            "ips": ["10.1.1.111"],
            "existing_device_id": 999,
            "decision": "BLOCKED",
            "action": "CONFLICT",
            "reasons": ["PHYSICAL_DEVICE_CONFLICT_WITH_HYPERVISOR_VM:359"],
        }], {})
        recon = {"records": [{
            "asset_id": "A1",
            "hostname": "SRV-AE11",
            "ips": ["10.1.1.111"],
            "macs": [],
            "asset_class": "VIRTUAL_MACHINE_CANDIDATE",
        }]}
        classification = {"records": [{
            "ip": "10.1.1.111",
            "management_mac": "",
            "historical_vmware_mac": "00:50:56:9F:9E:70",
        }]}
        plan, _ = planner_v5.build_plan(recon, classification, repair_state())
        row = plan[0]
        assert row["decision"] == "READY"
        assert row["action"] == "REPAIR_SAFE_VM_DUPLICATE"
        assert row["repair"]["vm_interface_id"] == 55
    finally:
        planner_v4.ORIG_BUILD_PLAN = old


class PreflightNetBox(object):
    def __init__(self, macs):
        self.macs = macs

    def get_all(self, endpoint):
        if endpoint.startswith("dcim/mac-addresses/"):
            return self.macs
        return []


def test_mac_preflight_allows_missing_and_blocks_foreign_assignment():
    old_nb = importer_v5.NetBox
    old_preflight = importer_v5.ORIG_PREFLIGHT_READY
    row = {
        "asset_id": "ME5024",
        "desired_name": "ME5024",
        "interfaces": [{"ip": "10.1.1.55", "mac": "00:C0:FF:66:B4:BF"}],
    }
    indexes = {"ip_objects": {"10.1.1.55": [{
        "assigned_object_type": "dcim.interface",
        "assigned_object_id": 77,
        "assigned_object": {"id": 77},
    }]}}
    try:
        importer_v5.ORIG_PREFLIGHT_READY = lambda ready, idx, tenant: []
        importer_v5.NetBox = lambda: PreflightNetBox([])
        assert importer_v5.preflight_ready([row], indexes, {"id": 4}) == []

        importer_v5.NetBox = lambda: PreflightNetBox([{
            "id": 9,
            "mac_address": "00:C0:FF:66:B4:BF",
            "assigned_object_type": "dcim.interface",
            "assigned_object_id": 88,
            "assigned_object": {"id": 88},
        }])
        errors = importer_v5.preflight_ready([row], indexes, {"id": 4})
        assert len(errors) == 1
        assert "esperado interface 77" in errors[0]
    finally:
        importer_v5.NetBox = old_nb
        importer_v5.ORIG_PREFLIGHT_READY = old_preflight


class ReconcileNetBox(object):
    def __init__(self):
        self.calls = []
        self.macs = []

    def get_all(self, endpoint):
        if endpoint.startswith("ipam/ip-addresses/"):
            return [{
                "id": 222,
                "address": "10.1.1.55/24",
                "assigned_object_type": "dcim.interface",
                "assigned_object_id": 77,
                "assigned_object": {"id": 77},
                "vrf": None,
            }]
        if endpoint.startswith("dcim/mac-addresses/"):
            return self.macs
        return []

    def get(self, endpoint):
        assert endpoint == "dcim/interfaces/77/"
        return {
            "id": 77,
            "name": "MGMT",
            "device": {"id": 501},
            "primary_mac_address": None,
        }

    def post(self, endpoint, payload):
        self.calls.append(("POST", endpoint, payload))
        obj = {
            "id": 333,
            "mac_address": payload["mac_address"],
            "assigned_object_type": payload["assigned_object_type"],
            "assigned_object_id": payload["assigned_object_id"],
            "assigned_object": {"id": payload["assigned_object_id"]},
            "description": payload.get("description", ""),
        }
        self.macs.append(obj)
        return obj

    def patch(self, endpoint, payload):
        self.calls.append(("PATCH", endpoint, payload))
        return {"id": int(endpoint.rstrip("/").split("/")[-1])}


def test_post_normal_mac_reconcile_creates_missing_mac_on_preserved_interface():
    tmp = tempfile.mkdtemp(prefix="network-1-10-15-")
    old_nb = importer_v5.NetBox
    old_reports = importer_v5.REPORTS
    try:
        plan_path = os.path.join(tmp, "DCM-plan.json")
        with open(plan_path, "w") as handle:
            json.dump({
                "stage": "PLAN",
                "site": "DCM",
                "records": [{
                    "asset_id": "ME5024",
                    "desired_name": "ME5024",
                    "existing_device_id": 501,
                    "decision": "READY",
                    "action": "NOOP",
                    "interfaces": [{
                        "ip": "10.1.1.55",
                        "mac": "00:C0:FF:66:B4:BF",
                    }],
                }],
            }, handle)

        fake = ReconcileNetBox()
        importer_v5.NetBox = lambda: fake
        importer_v5.REPORTS = tmp
        report = importer_v5._reconcile_ready_macs(plan_path)
        assert os.path.isfile(report)
        assert any(call[0] == "POST" and call[1] == "dcim/mac-addresses/" for call in fake.calls)
        assert ("PATCH", "dcim/interfaces/77/", {"primary_mac_address": 333}) in fake.calls
        data = json.load(open(report, "r"))
        assert data["status"] == "PASS"
    finally:
        importer_v5.NetBox = old_nb
        importer_v5.REPORTS = old_reports
        shutil.rmtree(tmp)


def main():
    tests = [
        test_historical_vmware_mac_promotes_safe_repair,
        test_mac_preflight_allows_missing_and_blocks_foreign_assignment,
        test_post_normal_mac_reconcile_creates_missing_mac_on_preserved_interface,
    ]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.10.15 NETWORK FINAL FIX TESTS PASSED")


if __name__ == "__main__":
    main()
