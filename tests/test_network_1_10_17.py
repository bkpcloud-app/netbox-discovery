#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.auditors import auditor_v7
from modules.importers import importer_v4, importer_v7
from modules.inventory import planner_v4, planner_v7

VMWARE_MAC = "00:50:56:9F:9E:70"


def state(vm_interfaces=None, macs=None):
    return {
        "tenant": {"id": 4},
        "site": {"id": 1},
        "devices": [{
            "id": 999, "name": "SRV-AE11",
            "description": planner_v4.PRODUCT_DEVICE_DESCRIPTION,
            "serial": "", "tenant": {"id": 4}, "site": {"id": 1},
            "primary_ip4": {"id": 22, "address": "10.1.1.111/24"},
            "rack": None, "location": None, "cluster": None,
            "virtual_chassis": None, "device_bay": None,
        }],
        "interfaces": [{
            "id": 11, "device": {"id": 999}, "name": "MGMT",
            "description": planner_v4.PRODUCT_INTERFACE_DESCRIPTION,
            "primary_mac_address": None, "cable": None, "mark_connected": False,
        }],
        "vm_interfaces": list(vm_interfaces or []),
        "virtual_machines": [{
            "id": 359, "name": "SRV-AE11", "tenant": {"id": 4},
            "site": {"id": 1}, "primary_ip4": None,
        }],
        "ips": [{
            "id": 22, "address": "10.1.1.111/24",
            "description": planner_v4.PRODUCT_IP_DESCRIPTION,
            "tenant": {"id": 4}, "assigned_object_type": "dcim.interface",
            "assigned_object_id": 11, "assigned_object": {"id": 11},
        }],
        "macs": list(macs or []),
        "inventory_items": [], "console_ports": [], "console_server_ports": [],
        "power_ports": [], "power_outlets": [], "front_ports": [],
        "rear_ports": [], "device_bays": [], "module_bays": [],
    }


def recon_and_classification():
    return ({"records": [{
        "asset_id": "A1", "hostname": "SRV-AE11",
        "ips": ["10.1.1.111"], "macs": [],
        "asset_class": "VIRTUAL_MACHINE_CANDIDATE",
    }]}, {"records": [{
        "ip": "10.1.1.111", "management_mac": VMWARE_MAC,
        "historical_vmware_mac": "",
    }]})


def blocked_row():
    return {
        "asset_id": "A1", "desired_name": "SRV-AE11",
        "primary_ip": "10.1.1.111", "ips": ["10.1.1.111"],
        "existing_device_id": 999, "decision": "BLOCKED", "action": "CONFLICT",
        "reasons": ["PHYSICAL_DEVICE_CONFLICT_WITH_HYPERVISOR_VM:359"],
    }


def build_with_state(live_state):
    old = planner_v4.ORIG_BUILD_PLAN
    try:
        planner_v4.ORIG_BUILD_PLAN = lambda recon, classification, current: ([blocked_row()], {})
        recon, classification = recon_and_classification()
        return planner_v7.build_plan(recon, classification, live_state)[0][0]
    finally:
        planner_v4.ORIG_BUILD_PLAN = old


def test_zero_vm_interfaces_promotes_safe_repair():
    row = build_with_state(state())
    assert row["decision"] == "READY"
    assert row["action"] == "REPAIR_SAFE_VM_DUPLICATE"
    repair = row["repair"]
    assert repair["vm_interface_mode"] == "CREATE_SINGLE_VM_INTERFACE"
    assert repair["vm_interface_name"] == "MGMT"
    assert repair["vm_mac_mode"] == "ENSURE_CREATED_VM_INTERFACE"
    assert repair["vm_mac_address"] == VMWARE_MAC
    assert str(repair["vm_interface_id"]).startswith("PLANNED:VM-INTERFACE:")


def test_zero_interface_repair_blocks_when_mac_owned_elsewhere():
    row = build_with_state(state(macs=[{
        "id": 88, "mac_address": VMWARE_MAC,
        "assigned_object_type": "dcim.interface", "assigned_object_id": 777,
        "assigned_object": {"id": 777},
    }]))
    assert row["decision"] == "BLOCKED"
    assert any("pertence a outro objeto" in reason for reason in row.get("reasons") or [])


def test_existing_single_interface_path_is_preserved():
    row = build_with_state(state(vm_interfaces=[{
        "id": 55, "virtual_machine": {"id": 359}, "name": "Network adapter 1",
        "primary_mac_address": None, "mac_addresses": [],
    }]))
    assert row["decision"] == "READY"
    assert row["repair"]["vm_interface_id"] == 55
    assert row["repair"]["vm_mac_mode"] == "ENSURE_SINGLE_VM_INTERFACE"
    assert not row["repair"].get("vm_interface_mode")


class FakeNetBox(object):
    def __init__(self):
        self.calls = []
        self.device = state()["devices"][0]
        self.vm = state()["virtual_machines"][0]
        self.ip = state()["ips"][0]
        self.device_interface = state()["interfaces"][0]
        self.vm_interfaces = []
        self.mac_rows = []
        self.deleted_device = False

    def get_all(self, endpoint):
        if endpoint.startswith("virtualization/interfaces/"):
            return list(self.vm_interfaces)
        if endpoint.startswith("dcim/interfaces/"):
            return [] if self.deleted_device else [self.device_interface]
        if endpoint.startswith("dcim/mac-addresses/"):
            return list(self.mac_rows)
        if endpoint.startswith("ipam/ip-addresses/"):
            return [self.ip]
        if endpoint.startswith("dcim/devices/"):
            return [] if self.deleted_device else [self.device]
        if endpoint.startswith("tenancy/tenants/"):
            return [{"id": 4, "name": "MIZU"}]
        if endpoint.startswith("dcim/sites/"):
            return [{"id": 1, "name": "DCM"}]
        return []

    def get(self, endpoint):
        if endpoint == "dcim/devices/999/":
            if self.deleted_device:
                raise RuntimeError("404")
            return self.device
        if endpoint == "virtualization/virtual-machines/359/":
            return self.vm
        if endpoint == "ipam/ip-addresses/22/":
            return self.ip
        if endpoint.startswith("virtualization/interfaces/"):
            iid = int(endpoint.rstrip("/").split("/")[-1])
            return next(item for item in self.vm_interfaces if item["id"] == iid)
        if endpoint == "dcim/interfaces/11/":
            return self.device_interface
        raise RuntimeError("unknown GET " + endpoint)

    def post(self, endpoint, payload):
        self.calls.append(("POST", endpoint, dict(payload)))
        if endpoint == "virtualization/interfaces/":
            row = {
                "id": 55, "virtual_machine": {"id": payload["virtual_machine"]},
                "name": payload["name"], "enabled": payload.get("enabled", True),
                "description": payload.get("description", ""),
                "primary_mac_address": None, "mac_addresses": [],
            }
            self.vm_interfaces.append(row)
            return row
        if endpoint == "dcim/mac-addresses/":
            row = {
                "id": 444, "mac_address": payload["mac_address"],
                "assigned_object_type": payload["assigned_object_type"],
                "assigned_object_id": payload["assigned_object_id"],
                "assigned_object": {"id": payload["assigned_object_id"]},
                "description": payload.get("description", ""),
            }
            self.mac_rows.append(row)
            return row
        raise RuntimeError("unknown POST " + endpoint)

    def patch(self, endpoint, payload):
        self.calls.append(("PATCH", endpoint, dict(payload)))
        if endpoint == "virtualization/interfaces/55/":
            target = self.vm_interfaces[0]
            target["primary_mac_address"] = {
                "id": payload["primary_mac_address"], "mac_address": VMWARE_MAC,
            }
            return target
        if endpoint == "ipam/ip-addresses/22/":
            self.ip["assigned_object_type"] = payload["assigned_object_type"]
            self.ip["assigned_object_id"] = payload["assigned_object_id"]
            self.ip["assigned_object"] = {"id": payload["assigned_object_id"]}
            return self.ip
        if endpoint == "virtualization/virtual-machines/359/":
            self.vm["primary_ip4"] = {"id": payload["primary_ip4"]}
            return self.vm
        if endpoint == "dcim/devices/999/":
            for key, value in payload.items():
                self.device[key] = value
            return self.device
        if endpoint == "dcim/interfaces/11/":
            self.device_interface["primary_mac_address"] = None
            return self.device_interface
        if endpoint.startswith("dcim/mac-addresses/"):
            row = self.mac_rows[0]
            row.update(payload)
            row["assigned_object"] = {"id": payload["assigned_object_id"]}
            return row
        raise RuntimeError("unknown PATCH " + endpoint)

    def delete(self, endpoint):
        self.calls.append(("DELETE", endpoint, None))
        if endpoint == "dcim/devices/999/":
            self.deleted_device = True
            return None
        if endpoint.startswith("dcim/mac-addresses/"):
            return None
        raise RuntimeError("unknown DELETE " + endpoint)


def repair_row():
    row = build_with_state(state())
    return row


def test_importer_creates_interface_mac_moves_ip_and_deletes_duplicate():
    nb = FakeNetBox()
    row = repair_row()
    verified = importer_v7._verify_create_interface_repair(nb, row, 4, 1)
    events = []
    importer_v7._create_vm_interface_and_mac(
        nb, row, verified, events, importer_v4._execute_repair)

    assert nb.deleted_device is True
    assert nb.ip["assigned_object_type"] == "virtualization.vminterface"
    assert nb.ip["assigned_object_id"] == 55
    assert nb.vm["primary_ip4"]["id"] == 22
    assert nb.vm_interfaces[0]["primary_mac_address"]["id"] == 444
    assert row["repair"]["vm_interface_id"] == 55

    post_interface = nb.calls.index(("POST", "virtualization/interfaces/", {
        "virtual_machine": 359, "name": "MGMT", "enabled": True,
        "description": planner_v7.VM_INTERFACE_DESCRIPTION,
    }))
    ip_move = next(pos for pos, call in enumerate(nb.calls)
                   if call[0] == "PATCH" and call[1] == "ipam/ip-addresses/22/")
    device_delete = nb.calls.index(("DELETE", "dcim/devices/999/", None))
    assert post_interface < ip_move < device_delete


def test_auditor_resolves_created_interface_by_vmware_mac():
    nb = FakeNetBox()
    row = repair_row()
    verified = importer_v7._verify_create_interface_repair(nb, row, 4, 1)
    importer_v7._create_vm_interface_and_mac(
        nb, row, verified, [], importer_v4._execute_repair)
    interface, mac_row, error = auditor_v7._resolve_created_interface(nb, row)
    assert error == ""
    assert interface["id"] == 55
    assert mac_row["id"] == 444


def main():
    tests = [
        test_zero_vm_interfaces_promotes_safe_repair,
        test_zero_interface_repair_blocks_when_mac_owned_elsewhere,
        test_existing_single_interface_path_is_preserved,
        test_importer_creates_interface_mac_moves_ip_and_deletes_duplicate,
        test_auditor_resolves_created_interface_by_vmware_mac,
    ]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.10.17 ZERO-INTERFACE VM REPAIR TESTS PASSED")


if __name__ == "__main__":
    main()
