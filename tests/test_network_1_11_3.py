#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.inventory import planner_v9


def windows_plan_row():
    return {
        "role": "WINDOWS_WORKSTATION",
        "manufacturer": "Generic",
        "model": "Windows Workstation",
    }


def test_live_list_prerequisites_are_supported():
    prereq = {
        "roles": [{"name": "WINDOWS_WORKSTATION", "slug": "windows-workstation"}],
        "device_types": [{
            "manufacturer": "Generic",
            "model": "Generic Windows Workstation",
            "slug": "generic-windows-workstation",
        }],
    }
    state = {"roles": [], "device_types": []}
    planner_v9._fix_windows_prerequisites([windows_plan_row()], prereq, state)

    assert isinstance(prereq["roles"], list)
    assert isinstance(prereq["device_types"], list)
    assert [row["name"] for row in prereq["roles"]] == ["WORKSTATION-WINDOWS"]
    assert [row["model"] for row in prereq["device_types"]] == ["Windows Workstation"]


def test_historical_dict_prerequisites_are_supported():
    prereq = {
        "roles": {
            "windows-workstation": {"name": "WINDOWS_WORKSTATION", "slug": "windows-workstation"},
        },
        "device_types": {
            "generic|generic windows workstation": {
                "manufacturer": "Generic",
                "model": "Generic Windows Workstation",
                "slug": "generic-windows-workstation",
            },
        },
    }
    state = {"roles": [], "device_types": []}
    planner_v9._fix_windows_prerequisites([windows_plan_row()], prereq, state)

    assert isinstance(prereq["roles"], list)
    assert prereq["roles"][0]["name"] == "WORKSTATION-WINDOWS"
    assert prereq["device_types"][0]["model"] == "Windows Workstation"


def test_existing_catalog_prevents_duplicate_prerequisites():
    prereq = {"roles": [], "device_types": []}
    state = {
        "roles": [{"id": 10, "name": "WORKSTATION-WINDOWS"}],
        "device_types": [{
            "id": 20,
            "manufacturer": {"name": "Generic"},
            "model": "Windows Workstation",
        }],
    }
    planner_v9._fix_windows_prerequisites([windows_plan_row()], prereq, state)
    assert prereq["roles"] == []
    assert prereq["device_types"] == []


def test_malformed_catalog_shape_does_not_crash():
    prereq = {"roles": "invalid", "device_types": 123}
    planner_v9._fix_windows_prerequisites(
        [windows_plan_row()], prereq, {"roles": [], "device_types": []}
    )
    assert prereq["roles"][0]["name"] == "WORKSTATION-WINDOWS"
    assert prereq["device_types"][0]["model"] == "Windows Workstation"


def main():
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.11.3 PLANNER PREREQUISITE SHAPE TESTS PASSED")


if __name__ == "__main__":
    main()
