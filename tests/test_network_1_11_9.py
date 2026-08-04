#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.inventory import planner_v11 as planner
from modules.inventory import pipeline
from modules.product import runner


def _state(serial="TW37LB43JZ", name="SW-BA17-LB43JZ", ip="10.2.1.37", device_id=503):
    return {
        "devices": [{
            "id": device_id,
            "name": name,
            "serial": serial,
            "description": planner.v10.PRODUCT_DEVICE_DESCRIPTION,
            "role": {"name": "NETWORK SWITCH"},
            "device_type": {
                "manufacturer": {"name": "HPE Aruba"},
                "model": "Instant On 1930 48G 4SFP+ 370W Switch JL686B",
            },
            "platform": None,
        }],
        "ips": [{
            "address": ip + "/24",
            "assigned_object_type": "dcim.interface",
            "assigned_object": {"id": 900, "device": {"id": device_id}},
        }],
        "interfaces": [],
    }


def _row(serial="TW37LB43JZ", ip="10.2.1.37", device_id=503):
    return {
        "asset_id": "SERIAL:" + serial,
        "existing_device_id": device_id,
        "desired_name": "SW-BA17-" + serial[-6:],
        "effective_name": "SW-BA17-" + serial[-6:],
        "primary_ip": ip,
        "ips": [ip],
        "serial": serial,
        "decision": "BLOCKED",
        "action": "NOOP",
        "reasons": ["DUPLICATE_DESIRED_NAME", "RECONCILE_REVIEW_CANDIDATE"],
        "target_role": "NETWORK SWITCH",
        "role": "NETWORK_SWITCH",
        "manufacturer": "HPE Aruba",
        "model": "Instant On 1930 48G 4SFP+ 370W Switch JL686B",
        "platform": "",
        "safe_diffs": [],
        "ip_intents": [{"ip": ip, "action": "BLOCKED"}],
    }


def test_01_existing_matched_collision_is_recovered():
    row = _row()
    planner._recover_existing_collision_devices([row], _state())
    assert row["decision"] == "READY"
    assert row["action"] == "NOOP"
    assert row["desired_name"] == "SW-BA17-LB43JZ"
    assert row["existing_device_id"] == 503
    assert row["ip_intents"][0]["action"] == "NOOP"
    assert row["identity_policy"] == "COLLISION_SAFE_EXISTING_MATCH"


def test_02_second_real_switch_is_recovered():
    row = _row(serial="TW37KPC2C1", ip="10.2.1.47", device_id=504)
    state = _state(serial="TW37KPC2C1", name="SW-BA17-KPC2C1", ip="10.2.1.47", device_id=504)
    state["devices"][0]["device_type"]["model"] = "Instant On 1930 8G 2SFP 124W Switch JL681A"
    row["model"] = "Instant On 1930 8G 2SFP 124W Switch JL681A"
    planner._recover_existing_collision_devices([row], state)
    assert row["decision"] == "READY"
    assert row["action"] == "NOOP"
    assert row["desired_name"] == "SW-BA17-KPC2C1"


def test_03_serial_mismatch_fails_closed():
    row = _row()
    state = _state(serial="OTHER-SERIAL")
    planner._recover_existing_collision_devices([row], state)
    assert row["decision"] == "BLOCKED"


def test_04_manual_device_fails_closed():
    row = _row()
    state = _state()
    state["devices"][0]["description"] = "Criado manualmente"
    planner._recover_existing_collision_devices([row], state)
    assert row["decision"] == "BLOCKED"


def test_05_pipeline_uses_planner_v11():
    source = open(os.path.join(BASE, "modules", "inventory", "pipeline.py"), "r").read()
    assert 'planner_v11.py' in source
    assert 'PLAN V11: OK' in source
    assert pipeline.PIPELINE_VERSION == "3.4-product"


def test_06_runner_uses_current_components():
    assert runner.COMPONENTS["planner"] == "planner_v11.py"
    assert runner.COMPONENTS["importer"] == "importer_v11.py"
    assert runner.COMPONENTS["auditor"] == "auditor_v10.py"
    assert runner.RUNNER_VERSION == "3.2-product"


def test_07_cli_routes_and_labels_are_current():
    source = open(os.path.join(BASE, "bin", "netbox-discovery"), "r").read()
    required = (
        "CLASSIFY V8: OK",
        "PLAN V11: OK",
        "IMPORT V11: OK",
        "AUDIT V10: OK",
        'classifier_v8.py',
        'planner_v11.py',
        'importer_v11.py',
        'auditor_v10.py',
    )
    for marker in required:
        assert marker in source, marker
    forbidden = (
        "CLASSIFY V7: OK",
        "PLAN V9: OK",
        "IMPORT V10: OK",
        "AUDIT V9: OK",
    )
    for marker in forbidden:
        assert marker not in source, marker


def test_08_planner_v11_direct_entrypoint():
    path = os.path.join(BASE, "modules", "inventory", "planner_v11.py")
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    result = subprocess.call([sys.executable, path, "--help"], cwd="/", env=env)
    assert result == 0


def test_09_release_component_version():
    assert planner.PLANNER_VERSION == "5.3-product"


def main():
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    assert len(tests) >= 9, len(tests)
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.11.9 SWITCH RECOVERY TESTS PASSED: {0}".format(len(tests)))


if __name__ == "__main__":
    main()
