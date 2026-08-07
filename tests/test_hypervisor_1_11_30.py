#!/usr/bin/env python3
import os
import sys
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
sys.path.insert(0, BASE)

from modules.hypervisor import engine_v5

base = engine_v5.base


def vm_source(name="SRV-VI01_replica", serial="NEW-UUID", provider="vmware"):
    return {
        "source_id": "vmware-test",
        "provider": provider,
        "name": name,
        "serial": serial,
        "status": "poweredOff",
        "vcpus": 2,
        "memory_mb": 4096,
        "disk_gb": 10,
        "interfaces": [],
    }


def current_vm(vm_id=447, name="SRV-VI01_replica", serial="OLD-UUID"):
    return {
        "id": vm_id,
        "name": name,
        "serial": serial,
        "status": {"value": "offline"},
        "vcpus": 2,
        "memory": 4096,
        "disk": 10240,
        "role": {"id": 10, "name": "VIRTUAL MACHINE"},
        "platform": None,
        "cluster": None,
        "device": None,
        "site": {"id": 1, "name": "DCM"},
        "tenant": {"id": 1, "name": "MIZU"},
    }


def state(vms):
    return {
        "vms": vms,
        "ips": [],
        "macs": [],
        "roles": [{"id": 10, "name": "VIRTUAL MACHINE", "vm_role": True}],
    }


def test_unique_vmware_replica_uuid_rotation_becomes_ready_update_safe():
    current = current_vm()
    st = state([current])
    indexes = base.vm_indexes(st)
    row = engine_v5._vm_plan_row_with_replica_identity(vm_source(), indexes, st)
    assert row["decision"] == "READY", row
    assert row["action"] == "UPDATE_SAFE", row
    assert row["existing_id"] == 447, row
    assert row["replica_uuid_refresh"] is True, row
    assert row["replica_identity_match"] == "nome exato único (_replica)", row

    preview = engine_v5._vm_safe_patch_preview_with_replica(row, current)
    assert preview.get("serial") == "NEW-UUID", preview

    payload = engine_v5._vm_safe_patch_with_replica(row, current, object(), None, None)
    assert payload.get("serial") == "NEW-UUID", payload


def test_normal_vm_uuid_mismatch_remains_review():
    current = current_vm(name="SRV-VI01")
    st = state([current])
    indexes = base.vm_indexes(st)
    row = engine_v5._vm_plan_row_with_replica_identity(
        vm_source(name="SRV-VI01"), indexes, st
    )
    assert row["decision"] == "REVIEW", row
    assert "serial/UUID" in row["reason"], row
    assert not row.get("replica_uuid_refresh"), row


def test_non_vmware_replica_uuid_mismatch_remains_review():
    current = current_vm()
    st = state([current])
    indexes = base.vm_indexes(st)
    row = engine_v5._vm_plan_row_with_replica_identity(
        vm_source(provider="hyperv"), indexes, st
    )
    assert row["decision"] == "REVIEW", row
    assert not row.get("replica_uuid_refresh"), row


def test_duplicate_replica_name_never_bypasses_identity_guard():
    first = current_vm(447)
    second = current_vm(448)
    st = state([first, second])
    indexes = base.vm_indexes(st)
    row = engine_v5._vm_plan_row_with_replica_identity(vm_source(), indexes, st)
    assert row["decision"] == "REVIEW", row
    assert not row.get("replica_uuid_refresh"), row


def test_replica_exact_unique_name_is_accepted_by_global_reclassify_guard():
    current = current_vm()
    row = {
        "object_type": "VM",
        "provider": "vmware",
        "desired_name": "SRV-VI01_replica",
        "serial": "NEW-UUID",
        "existing_id": 447,
        "interfaces": [],
        "replica_uuid_refresh": True,
    }
    obj, reason = engine_v5._strong_global_match_with_replica(
        row,
        {447: current},
        defaultdict(list),
        [],
        [],
    )
    assert obj and obj["id"] == 447, (obj, reason)
    assert reason == "nome exato único (_replica)", reason


def test_replica_global_duplicate_name_is_rejected():
    first = current_vm(447)
    second = current_vm(448)
    row = {
        "object_type": "VM",
        "provider": "vmware",
        "desired_name": "SRV-VI01_replica",
        "serial": "NEW-UUID",
        "existing_id": 447,
        "interfaces": [],
        "replica_uuid_refresh": True,
    }
    obj, reason = engine_v5._strong_global_match_with_replica(
        row,
        {447: first, 448: second},
        defaultdict(list),
        [],
        [],
    )
    assert obj is None, obj
    assert "ambíguo" in reason, reason


def main():
    tests = [
        test_unique_vmware_replica_uuid_rotation_becomes_ready_update_safe,
        test_normal_vm_uuid_mismatch_remains_review,
        test_non_vmware_replica_uuid_mismatch_remains_review,
        test_duplicate_replica_name_never_bypasses_identity_guard,
        test_replica_exact_unique_name_is_accepted_by_global_reclassify_guard,
        test_replica_global_duplicate_name_is_rejected,
    ]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.11.30 VMWARE REPLICA IDENTITY TESTS PASSED")


if __name__ == "__main__":
    main()
