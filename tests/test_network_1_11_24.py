#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.inventory import planner_v11
from modules.product import updater

MIN_VERSION = "1.11.24"
ENV_NAMES = (
    "NETBOX_DISCOVERY_MAX_CREATE",
    "NETBOX_DISCOVERY_MAX_INITIAL_CREATE",
    "NETBOX_DISCOVERY_INITIAL_MAX_BASE",
    "NETBOX_DISCOVERY_MAX_UPDATE",
    "NETBOX_DISCOVERY_MAX_REPAIR",
    "NETBOX_DISCOVERY_MAX_TOTAL_CHANGES",
    "NETBOX_DISCOVERY_MAX_CHANGE_PERCENT",
    "NETBOX_DISCOVERY_PERCENT_MIN_BASE",
)


def read(relative):
    return open(os.path.join(ROOT, relative), "r").read()


def clear_guard_env():
    for name in ENV_NAMES:
        os.environ.pop(name, None)


def devices(total):
    return [{"id": index + 1, "name": "DEVICE-{0}".format(index + 1)} for index in range(total)]


def ready_create(total):
    return [
        {
            "decision": "READY",
            "action": "CREATE",
            "primary_ip": "10.4.1.{0}".format(index + 1),
            "reasons": ["TEST"],
            "interfaces": [],
            "ip_intents": [],
        }
        for index in range(total)
    ]


def test_01_release_versions_include_1_11_24_or_newer():
    root_version = read("VERSION").strip()
    package_version = read("netbox-discovery/VERSION").strip()
    assert root_version == package_version
    assert updater.version_key(root_version) >= updater.version_key(MIN_VERSION)


def test_02_fvi_initial_bootstrap_27_creates_passes():
    clear_guard_env()
    plan = ready_create(27)
    planner_v11._apply_final_write_guard(plan, {"devices": devices(2)})
    guard = plan[0]["write_guard"]
    assert guard["status"] == "PASS"
    assert guard["eligible_total"] == 27
    assert guard["live_devices"] == 2
    assert guard["initial_bootstrap"] is True
    assert guard["effective_create_limit"] == 50
    assert guard["policy"] == "INITIAL_SITE_BOOTSTRAP_ABSOLUTE_ONLY"
    assert guard["violations"] == []
    assert all(row["decision"] == "READY" and row["action"] == "CREATE" for row in plan)


def test_03_initial_bootstrap_still_blocks_over_50_creates():
    clear_guard_env()
    plan = ready_create(51)
    planner_v11._apply_final_write_guard(plan, {"devices": devices(2)})
    guard = plan[0]["write_guard"]
    assert guard["status"] == "BLOCK"
    assert guard["effective_create_limit"] == 50
    assert "CREATE=51>50" in guard["violations"]
    assert all(row["decision"] == "BLOCKED" and row["action"] == "NOOP" for row in plan)


def test_04_legacy_small_site_cap_remains_25_after_initial_phase():
    clear_guard_env()
    plan = ready_create(26)
    planner_v11._apply_final_write_guard(plan, {"devices": devices(13)})
    guard = plan[0]["write_guard"]
    assert guard["status"] == "BLOCK"
    assert guard["initial_bootstrap"] is False
    assert guard["effective_create_limit"] == 25
    assert guard["policy"] == "SMALL_SITE_BOOTSTRAP_ABSOLUTE_ONLY"
    assert "CREATE=26>25" in guard["violations"]


def test_05_established_site_rules_are_unchanged():
    clear_guard_env()
    plan = ready_create(21)
    planner_v11._apply_final_write_guard(plan, {"devices": devices(100)})
    guard = plan[0]["write_guard"]
    assert guard["status"] == "BLOCK"
    assert guard["policy"] == "ABSOLUTE_AND_PERCENT"
    assert guard["effective_create_limit"] == 25
    assert "PERCENT=21%>20%" in guard["violations"]


def test_06_total_cap_remains_75_during_initial_bootstrap():
    clear_guard_env()
    os.environ["NETBOX_DISCOVERY_MAX_INITIAL_CREATE"] = "100"
    try:
        plan = ready_create(76)
        planner_v11._apply_final_write_guard(plan, {"devices": devices(2)})
        guard = plan[0]["write_guard"]
        assert guard["status"] == "BLOCK"
        assert "TOTAL=76>75" in guard["violations"]
    finally:
        clear_guard_env()


def test_07_patch_note_documents_guard_boundaries():
    text = read("docs/PATCH-1.11.24.md")
    assert "# netbox-discovery 1.11.24" in text
    assert "CREATE máximo: 50" in text
    assert "CREATE máximo: 25" in text
    assert "TOTAL máximo: 75" in text


def main():
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    assert len(tests) >= 7
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.11.24 INITIAL-SITE BOOTSTRAP TESTS PASSED: {0}".format(len(tests)))


if __name__ == "__main__":
    main()
