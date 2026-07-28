#!/usr/bin/env python3
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
sys.path.insert(0, BASE)

from modules.inventory import classifier_v5, planner_v4, reconciler_v5
from modules.importers import importer_v4


def classification_row(ip, name="MD3200BKP"):
    return {
        "ip": ip,
        "hostname": name,
        "snmp_name": name,
        "snmp_object_id": classifier_v5.MD32XX_SYSOBJECTID,
        "role": "SNMP_DEVICE",
        "manufacturer": "Dell",
        "model": "Generic Snmp Device",
        "serial": "",
        "asset_class": "HOST_OR_APPLIANCE",
        "classification_score": 48,
        "confidence": "LOW",
        "evidence": ["SNMP responds but role unresolved"],
        "management_mac": "",
    }


def test_classifier_marks_exact_md32xx_endpoint_as_storage():
    data = {"records": [classification_row("10.1.1.56")]}
    out = classifier_v5.apply_identity_history(data, {})
    row = out["records"][0]
    assert row["role"] == "STORAGE"
    assert row["manufacturer"] == "Dell"
    assert row["model"] == "PowerVault MD32xx"
    assert row["confidence"] == "HIGH"
    assert row["asset_class"] == "PHYSICAL_DEVICE"
    assert row["md32xx_pair_key"].startswith("DELL_MD32XX|")


def test_md32xx_pair_requires_exact_two_consecutive_endpoints():
    rows = []
    for ip in ("10.1.1.56", "10.1.1.57"):
        row = classification_row(ip)
        row = classifier_v5.apply_identity_history({"records": [row]}, {})["records"][0]
        rows.append(row)
    allowed = reconciler_v5._valid_pair_groups(rows)
    assert len(allowed) == 1

    rows[1]["ip"] = "10.1.1.60"
    assert reconciler_v5._valid_pair_groups(rows) == set()


def repair_state(ip_assignment_type="dcim.interface"):
    device_interface = {
        "id": 11,
        "device": {"id": 999},
        "name": "MGMT",
        "description": planner_v4.PRODUCT_INTERFACE_DESCRIPTION,
        "primary_mac_address": None,
        "cable": None,
        "mark_connected": False,
    }
    vm_interface = {
        "id": 55,
        "virtual_machine": {"id": 359},
        "name": "Network adapter 1",
        "primary_mac_address": {"id": 44, "mac_address": "00:50:56:9F:9E:70"},
        "mac_addresses": [],
    }
    assigned_id = 11 if ip_assignment_type == "dcim.interface" else 55
    state = {
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
        "interfaces": [device_interface],
        "vm_interfaces": [vm_interface],
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
            "assigned_object_type": ip_assignment_type,
            "assigned_object_id": assigned_id,
            "assigned_object": {"id": assigned_id},
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
    return state


def repair_asset():
    return {
        "asset_id": "A1",
        "hostname": "SRV-AE11",
        "ips": ["10.1.1.111"],
        "macs": ["00:50:56:9F:9E:70"],
        "asset_class": "VIRTUAL_MACHINE_CANDIDATE",
    }


def test_safe_repair_candidate_full_and_recovery():
    row = {"existing_device_id": 999, "desired_name": "SRV-AE11"}
    full = repair_state("dcim.interface")
    repair, error = planner_v4._repair_candidate(row, repair_asset(), full["virtual_machines"][0], full)
    assert not error
    assert repair["mode"] == "FULL"
    assert repair["device_id"] == 999
    assert repair["vm_id"] == 359
    assert repair["vm_interface_id"] == 55
    assert repair["ip_id"] == 22

    recovery = repair_state("virtualization.vminterface")
    recovery["devices"][0]["primary_ip4"] = None
    repair2, error2 = planner_v4._repair_candidate(
        row, repair_asset(), recovery["virtual_machines"][0], recovery)
    assert not error2
    assert repair2["mode"] == "RECOVERY_AFTER_IP_MOVE"


def test_manual_device_is_never_repaired_automatically():
    state = repair_state("dcim.interface")
    state["devices"][0]["description"] = "Criado manualmente"
    repair, error = planner_v4._repair_candidate(
        {"existing_device_id": 999, "desired_name": "SRV-AE11"},
        repair_asset(), state["virtual_machines"][0], state)
    assert repair is None
    assert "não foi criado" in error


def test_planner_promotes_only_safe_duplicate_to_repair_ready():
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
        state = repair_state("dcim.interface")
        plan, _ = planner_v4.build_plan(
            {"records": [repair_asset()]}, {}, state)
        row = plan[0]
        assert row["decision"] == "READY"
        assert row["action"] == "REPAIR_SAFE_VM_DUPLICATE"
        assert row["repair"]["vm_id"] == 359
    finally:
        planner_v4.ORIG_BUILD_PLAN = old


class FakeNetBox(object):
    def __init__(self):
        self.calls = []

    def patch(self, endpoint, payload):
        self.calls.append(("PATCH", endpoint, payload))
        if endpoint.startswith("ipam/ip-addresses/"):
            return {"id": 22, "address": "10.1.1.111/24"}
        return {"id": int(endpoint.rstrip("/").split("/")[-1])}

    def delete(self, endpoint):
        self.calls.append(("DELETE", endpoint, None))
        return None


def test_execute_repair_moves_ip_sets_primary_and_deletes_only_duplicate_device():
    nb = FakeNetBox()
    row = {"repair": {
        "device_id": 999,
        "device_name": "SRV-AE11",
        "vm_id": 359,
        "vm_name": "SRV-AE11",
        "vm_interface_id": 55,
        "vm_interface_name": "Network adapter 1",
        "ip_id": 22,
        "ip_address": "10.1.1.111/24",
    }}
    verified = {
        "mode": "FULL",
        "ip": {"id": 22, "address": "10.1.1.111/24"},
        "vm": {"id": 359, "primary_ip4": None},
        "device": {"id": 999, "primary_ip4": {"id": 22}},
        "interfaces": [{"id": 11, "primary_mac_address": None}],
        "macs": [],
    }
    events = []
    importer_v4._execute_repair(nb, row, verified, events)
    assert ("PATCH", "ipam/ip-addresses/22/", {
        "assigned_object_type": "virtualization.vminterface",
        "assigned_object_id": 55,
    }) in nb.calls
    assert ("PATCH", "virtualization/virtual-machines/359/", {"primary_ip4": 22}) in nb.calls
    assert ("DELETE", "dcim/devices/999/", None) in nb.calls
    assert not any(call[0] == "DELETE" and call[1].startswith("virtualization/") for call in nb.calls)


def main():
    tests = [
        test_classifier_marks_exact_md32xx_endpoint_as_storage,
        test_md32xx_pair_requires_exact_two_consecutive_endpoints,
        test_safe_repair_candidate_full_and_recovery,
        test_manual_device_is_never_repaired_automatically,
        test_planner_promotes_only_safe_duplicate_to_repair_ready,
        test_execute_repair_moves_ip_sets_primary_and_deletes_only_duplicate_device,
    ]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.10.14 NETWORK FINALIZE TESTS PASSED")


if __name__ == "__main__":
    main()
