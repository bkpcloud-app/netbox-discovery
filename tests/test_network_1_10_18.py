#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TESTS = os.path.join(ROOT, "tests")
BASE = os.path.join(ROOT, "netbox-discovery")
for path in (TESTS, BASE):
    if path not in sys.path:
        sys.path.insert(0, path)

import test_network_1_10_17 as t17
from modules.importers import importer_v4, importer_v8


class StrictPrimaryNetBox(t17.FakeNetBox):
    def __init__(self):
        super(StrictPrimaryNetBox, self).__init__()
        self.device["primary_ip4"] = {"id": 22, "address": "10.1.1.111/24"}

    def patch(self, endpoint, payload):
        if endpoint == "ipam/ip-addresses/22/" and importer_v8.nested_id(self.device.get("primary_ip4")):
            raise RuntimeError(
                "Cannot reassign IP address while it is designated as the primary IP for the parent object")
        return super(StrictPrimaryNetBox, self).patch(endpoint, payload)


def existing_interface_row_and_state(nb):
    row = t17.repair_row()
    repair = row["repair"]
    repair.pop("vm_interface_mode", None)
    repair["vm_interface_id"] = 55
    repair["vm_interface_name"] = "MGMT"

    vm_interface = {
        "id": 55,
        "virtual_machine": {"id": 359},
        "name": "MGMT",
        "description": "Descoberto pelo netbox-discovery hypervisor",
        "primary_mac_address": {"id": 444, "mac_address": t17.VMWARE_MAC},
        "mac_addresses": [],
    }
    nb.vm_interfaces = [vm_interface]
    nb.mac_rows = [{
        "id": 444,
        "mac_address": t17.VMWARE_MAC,
        "assigned_object_type": "virtualization.vminterface",
        "assigned_object_id": 55,
        "assigned_object": {"id": 55},
        "description": "Descoberto pelo netbox-discovery hypervisor",
    }]
    verified = {
        "mode": "FULL",
        "device": nb.device,
        "vm": nb.vm,
        "vm_interface": vm_interface,
        "ip": nb.ip,
        "interfaces": [nb.device_interface],
        "macs": [],
    }
    return row, verified


def test_primary_reference_is_cleared_before_ip_reassignment():
    nb = StrictPrimaryNetBox()
    row, verified = existing_interface_row_and_state(nb)
    events = []

    importer_v8._execute_repair_primary_safe(
        nb, row, verified, events, importer_v4._execute_repair)

    clear_pos = next(pos for pos, call in enumerate(nb.calls)
                     if call[0] == "PATCH" and call[1] == "dcim/devices/999/"
                     and call[2].get("primary_ip4") is None)
    move_pos = next(pos for pos, call in enumerate(nb.calls)
                    if call[0] == "PATCH" and call[1] == "ipam/ip-addresses/22/")
    delete_pos = nb.calls.index(("DELETE", "dcim/devices/999/", None))

    assert clear_pos < move_pos < delete_pos
    assert nb.deleted_device is True
    assert nb.ip["assigned_object_type"] == "virtualization.vminterface"
    assert nb.ip["assigned_object_id"] == 55
    assert nb.vm["primary_ip4"]["id"] == 22
    assert any(item.get("action") == "PRIMARY_IP_CLEARED_BEFORE_MOVE" for item in events)


def test_different_device_primary_ip_blocks_before_any_write():
    nb = StrictPrimaryNetBox()
    row, verified = existing_interface_row_and_state(nb)
    nb.device["primary_ip4"] = {"id": 999, "address": "10.1.1.250/24"}

    try:
        importer_v8._execute_repair_primary_safe(
            nb, row, verified, [], importer_v4._execute_repair)
    except RuntimeError as exc:
        assert "outro IP ID 999" in str(exc)
    else:
        raise AssertionError("primary IP divergente deveria bloquear")

    assert nb.calls == []
    assert nb.deleted_device is False
    assert nb.ip["assigned_object_type"] == "dcim.interface"


def main():
    tests = [
        test_primary_reference_is_cleared_before_ip_reassignment,
        test_different_device_primary_ip_blocks_before_any_write,
    ]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.10.18 PRIMARY-IP ORDER TESTS PASSED")


if __name__ == "__main__":
    main()
