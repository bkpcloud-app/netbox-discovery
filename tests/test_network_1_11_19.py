#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.inventory import planner_v11 as planner

VERSION = "1.11.19"


def read(relative):
    return open(os.path.join(ROOT, relative), "r").read()


def row(uid, role="WINDOWS_HOST", asset_class="HOST_OR_APPLIANCE", existing=None):
    return {
        "asset_id": "TEST-ASSET",
        "primary_ip": "10.0.0.10",
        "existing_device_id": existing,
        "decision": "READY",
        "action": "CREATE",
        "role": role,
        "asset_class": asset_class,
        "discovery_uid": uid,
        "reasons": ["TEST"],
        "interfaces": [{"name": "MGMT"}],
        "ip_intents": [{"address": "10.0.0.10/24", "action": "CREATE"}],
    }


def test_01_release_versions_are_1_11_19():
    assert read("VERSION").strip() == VERSION
    assert read("netbox-discovery/VERSION").strip() == VERSION


def test_02_weak_generic_windows_host_is_review():
    candidate = row("WEAK:E20071661A46DCF5", role="WINDOWS_HOST")
    planner._enforce_stable_identity_for_new_creates([candidate])
    assert candidate["decision"] == "REVIEW"
    assert candidate["action"] == "NOOP"
    assert candidate["interfaces"] == []
    assert candidate["ip_intents"] == []
    assert "NEW_DEVICE_REQUIRES_STABLE_IDENTITY" in candidate["reasons"]


def test_03_weak_sms_gateway_is_review():
    candidate = row("WEAK:429D39959FBE898B", role="SMS_GATEWAY")
    planner._enforce_stable_identity_for_new_creates([candidate])
    assert candidate["decision"] == "REVIEW"
    assert candidate["action"] == "NOOP"
    assert candidate["identity_policy"] == "FINAL_NEW_CREATE_IDENTITY_NOT_STABLE"


def test_04_rule_is_role_and_asset_class_independent():
    candidate = row("WEAK:ABCDEF", role="ANY_NEW_ROLE", asset_class="ANY_CLASS")
    planner._enforce_stable_identity_for_new_creates([candidate])
    assert candidate["decision"] == "REVIEW"
    assert candidate["action"] == "NOOP"


def test_05_stable_serial_and_management_mac_remain_ready():
    serial = row("SERIAL:dell:ABC123", role="NETWORK_SWITCH", asset_class="PHYSICAL_DEVICE")
    mac = row("MGMT-MAC:74:83:C2:26:6B:DF", role="WIRELESS_AP", asset_class="PHYSICAL_DEVICE")
    planner._enforce_stable_identity_for_new_creates([serial, mac])
    assert serial["decision"] == "READY" and serial["action"] == "CREATE"
    assert mac["decision"] == "READY" and mac["action"] == "CREATE"


def test_06_existing_device_is_not_downgraded_by_new_create_guard():
    existing = row("WEAK:LEGACY", role="WINDOWS_HOST", existing=123)
    planner._enforce_stable_identity_for_new_creates([existing])
    assert existing["decision"] == "READY"
    assert existing["action"] == "CREATE"


def test_07_dcm_final_guard_counts_only_stable_candidates():
    plan = [row("SERIAL:vendor:{0}".format(index), role="NETWORK_SWITCH", asset_class="PHYSICAL_DEVICE") for index in range(5)]
    plan.extend(row("MGMT-MAC:00:11:22:33:44:{0:02X}".format(index), role="WIRELESS_AP", asset_class="PHYSICAL_DEVICE") for index in range(8))
    plan.append(row("SERIAL:apc:5A1424T01585", role="POWER_MANAGEMENT", asset_class="PHYSICAL_DEVICE"))
    plan.extend([
        row("WEAK:E20071661A46DCF5", role="WINDOWS_HOST"),
        row("WEAK:90940A43CCE4886A", role="WINDOWS_HOST"),
        row("WEAK:429D39959FBE898B", role="SMS_GATEWAY"),
    ])

    planner._enforce_stable_identity_for_new_creates(plan)
    planner._apply_final_write_guard(plan, {"devices": [{"id": value} for value in range(13)]})

    ready_create = [item for item in plan if item["decision"] == "READY" and item["action"] == "CREATE"]
    review = [item for item in plan if item["decision"] == "REVIEW"]
    guard = plan[0]["write_guard"]
    assert len(ready_create) == 14
    assert len(review) == 3
    assert guard["status"] == "PASS"
    assert guard["eligible_total"] == 14
    assert guard["counts"] == {"CREATE": 14}


def test_08_final_identity_guard_runs_before_write_guard():
    source = read("netbox-discovery/modules/inventory/planner_v11.py")
    identity_call = source.index("_enforce_stable_identity_for_new_creates(plan)")
    guard_call = source.index("_apply_final_write_guard(plan, state)")
    assert identity_call < guard_call


def test_09_documentation_is_current():
    markers = {
        "README.md": "**Versão atual:** 1.11.19",
        "docs/MANUAL.md": "**Versão:** 1.11.19",
        "docs/COMANDOS-RAPIDOS.md": "# netbox-discovery 1.11.19",
        "docs/HOMOLOGACAO.md": "# netbox-discovery 1.11.19",
        "RELEASE-NOTES.md": "## V1.11.19",
        "SECURITY.md": "**Versão da política:** 1.11.19",
        "docs/PATCH-1.11.19.md": "# netbox-discovery 1.11.19",
    }
    for relative, marker in markers.items():
        assert marker in read(relative), relative


def main():
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    assert len(tests) >= 9
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.11.19 FINAL STABLE IDENTITY TESTS PASSED: {0}".format(len(tests)))


if __name__ == "__main__":
    main()
