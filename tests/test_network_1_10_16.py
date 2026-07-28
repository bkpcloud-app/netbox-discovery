#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.inventory import planner_v4, planner_v6
from modules.importers import importer_v6

VMWARE_MAC = "00:50:56:9F:9E:70"


def repair_state(vm_interface_count=1, target_mac=None, global_mac=None):
    vm_interfaces = []
    for pos in range(vm_interface_count):
        iid = 55 + pos
        primary = None
        if pos == 0 and target_mac:
            primary = {"id": 44, "mac_address": target_mac}
        vm_interfaces.append({
            "id": iid,
            "virtual_machine": {"id": 359},
            "name": "Network adapter {0}".format(pos + 1),
            "primary_mac_address": primary,
            "mac_addresses": [],
        })

    macs = []
    if global_mac:
        macs.append(global_mac)

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
        "vm_interfaces": vm_interfaces,
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
        "macs": macs,
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


def recon_and_classification():
    recon = {"records": [{
        "asset_id": "A1",
        "hostname": "SRV-AE11",
        "ips": ["10.1.1.111"],
        "macs": [],
        "asset_class": "VIRTUAL_MACHINE_CANDIDATE",
    }]}
    classification = {"records": [{
        "ip": "10.1.1.111",
        "management_mac": VMWARE_MAC,
        "historical_vmware_mac": "",
    }]}
    return recon, classification


def blocked_plan_row():
    return {
        "asset_id": "A1",
        "desired_name": "SRV-AE11",
        "primary_ip": "10.1.1.111",
        "ips": ["10.1.1.111"],
        "existing_device_id": 999,
        "decision": "BLOCKED",
        "action": "CONFLICT",
        "reasons": ["PHYSICAL_DEVICE_CONFLICT_WITH_HYPERVISOR_VM:359"],
    }


def build_with_state(state):
    old = planner_v4.ORIG_BUILD_PLAN
    try:
        planner_v4.ORIG_BUILD_PLAN = lambda recon, classification, live: ([blocked_plan_row()], {})
        recon, classification = recon_and_classification()
        return planner_v6.build_plan(recon, classification, state)[0][0]
    finally:
        planner_v4.ORIG_BUILD_PLAN = old


def test_single_vm_interface_without_mac_promotes_safe_repair():
    row = build_with_state(repair_state())
    assert row["decision"] == "READY"
    assert row["action"] == "REPAIR_SAFE_VM_DUPLICATE"
    assert row["repair"]["vm_interface_id"] == 55
    assert row["repair"]["vm_mac_mode"] == "ENSURE_SINGLE_VM_INTERFACE"
    assert row["repair"]["vm_mac_address"] == VMWARE_MAC


def test_fallback_blocks_when_vm_has_multiple_interfaces():
    row = build_with_state(repair_state(vm_interface_count=2))
    assert row["decision"] == "BLOCKED"
    assert any("exatamente uma interface" in reason for reason in row.get("reasons") or [])


def test_fallback_blocks_when_unique_interface_has_different_mac():
    row = build_with_state(repair_state(target_mac="00:50:56:AA:BB:CC"))
    assert row["decision"] == "BLOCKED"
    assert any("já possui MAC diferente" in reason for reason in row.get("reasons") or [])


def test_fallback_blocks_when_vmware_mac_is_owned_elsewhere():
    row = build_with_state(repair_state(global_mac={
        "id": 88,
        "mac_address": VMWARE_MAC,
        "assigned_object_type": "dcim.interface",
        "assigned_object_id": 777,
        "assigned_object": {"id": 777},
    }))
    assert row["decision"] == "BLOCKED"
    assert any("pertence a outro objeto" in reason for reason in row.get("reasons") or [])


class FakeNetBox(object):
    def __init__(self):
        self.calls = []
        self.mac_rows = []
        self.interface = {
            "id": 55,
            "virtual_machine": {"id": 359},
            "name": "Network adapter 1",
            "primary_mac_address": None,
            "mac_addresses": [],
        }

    def get_all(self, endpoint):
        if endpoint.startswith("virtualization/interfaces/"):
            return [self.interface]
        if endpoint.startswith("dcim/mac-addresses/"):
            return self.mac_rows
        return []

    def post(self, endpoint, payload):
        self.calls.append(("POST", endpoint, payload))
        row = {
            "id": 444,
            "mac_address": payload["mac_address"],
            "assigned_object_type": payload["assigned_object_type"],
            "assigned_object_id": payload["assigned_object_id"],
            "assigned_object": {"id": payload["assigned_object_id"]},
            "description": payload.get("description", ""),
        }
        self.mac_rows.append(row)
        return row

    def patch(self, endpoint, payload):
        self.calls.append(("PATCH", endpoint, payload))
        if endpoint == "virtualization/interfaces/55/":
            self.interface["primary_mac_address"] = {
                "id": payload["primary_mac_address"],
                "mac_address": VMWARE_MAC,
            }
        return {"id": int(endpoint.rstrip("/").split("/")[-1])}


def test_importer_creates_vm_mac_before_repair():
    nb = FakeNetBox()
    row = {"repair": {
        "vm_mac_mode": "ENSURE_SINGLE_VM_INTERFACE",
        "vm_mac_address": VMWARE_MAC,
        "vm_interface_id": 55,
        "vm_id": 359,
    }}
    events = []
    importer_v6._ensure_vm_mac(nb, row, {}, events)
    assert any(call[0] == "POST" and call[1] == "dcim/mac-addresses/" for call in nb.calls)
    assert ("PATCH", "virtualization/interfaces/55/", {"primary_mac_address": 444}) in nb.calls
    assert events[0]["object_type"] == "VM_MAC_ADDRESS"


def main():
    tests = [
        test_single_vm_interface_without_mac_promotes_safe_repair,
        test_fallback_blocks_when_vm_has_multiple_interfaces,
        test_fallback_blocks_when_unique_interface_has_different_mac,
        test_fallback_blocks_when_vmware_mac_is_owned_elsewhere,
        test_importer_creates_vm_mac_before_repair,
    ]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.10.16 SINGLE-INTERFACE VM REPAIR TESTS PASSED")


if __name__ == "__main__":
    main()
