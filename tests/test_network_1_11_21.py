#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.importers import importer_v5

MIN_VERSION = (1, 11, 21)
MAC = "E8:B5:D0:72:9D:FC"


def read(relative):
    return open(os.path.join(ROOT, relative), "r").read()


def version_key(value):
    return tuple(int(part) for part in value.strip().split("."))


def row(existing=900, duplicate_specs=False):
    specs = [{"name": "MGMT", "mac": MAC, "ip": ""}]
    if duplicate_specs:
        specs.append({"name": "MGMT-ALIAS", "mac": MAC, "ip": "10.19.1.30"})
    return {
        "asset_id": "ASSET-SW-CORE-AE",
        "desired_name": "SW-CORE-AE",
        "existing_device_id": existing,
        "decision": "READY",
        "action": "NOOP",
        "interfaces": specs,
    }


def mac_rows(assigned_type="dcim.interface", assigned_id=543, duplicate=False):
    rows = [{
        "id": 700,
        "mac_address": MAC,
        "assigned_object_type": assigned_type,
        "assigned_object_id": assigned_id,
    }]
    if duplicate:
        rows.append({
            "id": 701,
            "mac_address": MAC,
            "assigned_object_type": assigned_type,
            "assigned_object_id": assigned_id + 1,
        })
    return rows


def interfaces(owner=900, interface_id=543):
    return [{
        "id": interface_id,
        "name": "MGMT",
        "device": {"id": owner, "name": "SW-CORE-AE" if owner == 900 else "OTHER-DEVICE"},
    }]


def rematch_existing(unused_row, unused_indexes):
    return {"id": 900, "name": "SW-CORE-AE"}, "MATCHED", "SERIAL+MAC+IP+NAME"


def rematch_new(unused_row, unused_indexes):
    return None, "NEW", "Sem correspondência"


def test_01_release_versions_include_1_11_21_or_newer():
    root = read("VERSION").strip()
    package = read("netbox-discovery/VERSION").strip()
    assert root == package
    assert version_key(root) >= MIN_VERSION


def test_02_partial_apply_owner_is_allowed_without_ip_inference():
    errors = importer_v5._mac_preflight_errors(
        [row()], {}, mac_rows(), interfaces(owner=900), rematch_existing)
    assert errors == []


def test_03_duplicate_specs_for_same_mac_are_evaluated_once():
    errors = importer_v5._mac_preflight_errors(
        [row(duplicate_specs=True)], {}, mac_rows(), interfaces(owner=321), rematch_existing)
    assert len(errors) == 1
    assert "dcim.interface ID 543" in errors[0]
    assert "Device ID 321" in errors[0]
    assert "alvo Device ID 900" in errors[0]


def test_04_mac_on_other_device_remains_blocked():
    errors = importer_v5._mac_preflight_errors(
        [row()], {}, mac_rows(), interfaces(owner=321), rematch_existing)
    assert len(errors) == 1
    assert "Device ID 321" in errors[0]
    assert "alvo Device ID 900" in errors[0]


def test_05_new_device_cannot_reuse_existing_owner_mac():
    candidate = row(existing=None)
    candidate["action"] = "CREATE"
    errors = importer_v5._mac_preflight_errors(
        [candidate], {}, mac_rows(), interfaces(owner=321), rematch_new)
    assert len(errors) == 1
    assert "alvo Device ID NOVO" in errors[0]


def test_06_mac_assigned_to_vm_remains_blocked():
    errors = importer_v5._mac_preflight_errors(
        [row()], {}, mac_rows(assigned_type="virtualization.vminterface"), [], rematch_existing)
    assert len(errors) == 1
    assert "virtualization.vminterface ID 543" in errors[0]


def test_07_global_duplicate_is_reported_once_even_with_duplicate_specs():
    errors = importer_v5._mac_preflight_errors(
        [row(duplicate_specs=True)], {}, mac_rows(duplicate=True), interfaces(owner=900), rematch_existing)
    assert errors == ["SW-CORE-AE: MAC duplicado no NetBox: E8:B5:D0:72:9D:FC"]


def test_08_legacy_preflight_uses_live_interface_owner():
    source = read("netbox-discovery/modules/importers/importer_v5.py")
    assert "_all_interfaces(nb)" in source
    assert "owner_id == target_device_id" in source
    assert "mac in seen" in source
    assert "esperado interface ainda não existente" not in source


def test_09_historical_documentation_remains_available():
    assert "# netbox-discovery 1.11.21" in read("docs/PATCH-1.11.21.md")
    assert "## V1.11.21" in read("RELEASE-NOTES.md")


def main():
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    assert len(tests) >= 9
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.11.21 LEGACY MAC OWNER PREFLIGHT TESTS PASSED: {0}".format(len(tests)))


if __name__ == "__main__":
    main()
