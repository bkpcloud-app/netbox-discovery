#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
if BASE not in sys.path:
    sys.path.insert(0, BASE)
IMPORTERS = os.path.join(BASE, "modules", "importers")
if IMPORTERS not in sys.path:
    sys.path.insert(0, IMPORTERS)

from modules.importers import importer_v2

MIN_VERSION = (1, 11, 22)
MAC = "E8:B5:D0:72:9D:FC"


def read(relative):
    return open(os.path.join(ROOT, relative), "r").read()


def version_tuple(value):
    return tuple(int(part) for part in value.strip().split("."))


class FakeNetBox(object):
    def __init__(self, owner_device=900, assigned_type="dcim.interface", assigned=True):
        self.posts = []
        self.patches = []
        self.interface = {
            "id": 543,
            "name": "MGMT-10.19.1.30",
            "device": {"id": owner_device, "name": "SW-CORE-AE"},
            "primary_mac_address": {"id": 700},
        }
        self.macs = [{
            "id": 700,
            "mac_address": MAC,
            "assigned_object_type": assigned_type if assigned else "",
            "assigned_object_id": 543 if assigned else None,
        }]

    def get_all(self, endpoint):
        if endpoint.startswith("dcim/mac-addresses/"):
            return self.macs
        if endpoint.startswith("dcim/interfaces/"):
            return [self.interface]
        return []

    def get(self, endpoint):
        if endpoint == "dcim/interfaces/543/":
            return self.interface
        return {}

    def post(self, endpoint, payload):
        self.posts.append((endpoint, payload))
        return dict(payload, id=999)

    def patch(self, endpoint, payload):
        self.patches.append((endpoint, payload))
        return dict(payload, id=int(endpoint.rstrip("/").split("/")[-1]))


def test_01_versions_are_synced_and_not_older_than_1_11_22():
    root_version = read("VERSION").strip()
    packaged_version = read("netbox-discovery/VERSION").strip()
    assert root_version == packaged_version
    assert version_tuple(root_version) >= MIN_VERSION


def test_02_partial_apply_reuses_interface_543_before_name_lookup():
    nb = FakeNetBox(owner_device=900)
    device = {"id": 900, "name": "SW-CORE-AE"}
    spec = {"name": "MGMT", "ip": "10.19.1.30", "mac": MAC}
    events = []

    old = importer_v2.ORIG_ENSURE_INTERFACE
    importer_v2.ORIG_ENSURE_INTERFACE = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("name-based interface creation must not run"))
    try:
        interface = importer_v2.ensure_interface(nb, True, device, spec, events)
    finally:
        importer_v2.ORIG_ENSURE_INTERFACE = old

    assert interface["id"] == 543
    assert nb.posts == []
    assert any(event.get("action") == "PRESERVED_BY_MAC" for event in events)
    assert any(event.get("object_type") == "MAC_ADDRESS" and event.get("action") == "PRESERVED" for event in events)


def test_03_same_mac_repeated_does_not_create_interface():
    nb = FakeNetBox(owner_device=900)
    device = {"id": 900, "name": "SW-CORE-AE"}
    events = []
    old = importer_v2.ORIG_ENSURE_INTERFACE
    importer_v2.ORIG_ENSURE_INTERFACE = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("must reuse interface by MAC"))
    try:
        first = importer_v2.ensure_interface(nb, True, device, {"name": "MGMT-A", "mac": MAC}, events)
        second = importer_v2.ensure_interface(nb, True, device, {"name": "MGMT-B", "mac": MAC}, events)
    finally:
        importer_v2.ORIG_ENSURE_INTERFACE = old
    assert first["id"] == second["id"] == 543
    assert nb.posts == []


def test_04_foreign_owner_blocks_before_interface_creation():
    nb = FakeNetBox(owner_device=321)
    device = {"id": 900, "name": "SW-CORE-AE"}
    called = []
    old = importer_v2.ORIG_ENSURE_INTERFACE
    importer_v2.ORIG_ENSURE_INTERFACE = lambda *args, **kwargs: called.append(True)
    try:
        try:
            importer_v2.ensure_interface(nb, True, device, {"name": "MGMT", "mac": MAC}, [])
            raise AssertionError("foreign owner must block")
        except RuntimeError as exc:
            assert "Device ID 321" in str(exc)
            assert "esperado Device ID 900" in str(exc)
    finally:
        importer_v2.ORIG_ENSURE_INTERFACE = old
    assert called == []
    assert nb.posts == []


def test_05_non_interface_assignment_blocks_before_creation():
    nb = FakeNetBox(owner_device=900, assigned_type="virtualization.vminterface")
    device = {"id": 900, "name": "SW-CORE-AE"}
    called = []
    old = importer_v2.ORIG_ENSURE_INTERFACE
    importer_v2.ORIG_ENSURE_INTERFACE = lambda *args, **kwargs: called.append(True)
    try:
        try:
            importer_v2.ensure_interface(nb, True, device, {"name": "MGMT", "mac": MAC}, [])
            raise AssertionError("non-device interface owner must block")
        except RuntimeError as exc:
            assert "virtualization.vminterface" in str(exc)
    finally:
        importer_v2.ORIG_ENSURE_INTERFACE = old
    assert called == []


def test_06_unassigned_mac_falls_back_to_normal_interface_flow():
    nb = FakeNetBox(owner_device=900, assigned=False)
    device = {"id": 900, "name": "SW-CORE-AE"}
    normal = {"id": 777, "name": "MGMT", "device": {"id": 900}}
    called = []
    old = importer_v2.ORIG_ENSURE_INTERFACE
    importer_v2.ORIG_ENSURE_INTERFACE = lambda *args, **kwargs: called.append(True) or normal
    try:
        interface = importer_v2.ensure_interface(nb, True, device, {"name": "MGMT", "mac": MAC}, [])
    finally:
        importer_v2.ORIG_ENSURE_INTERFACE = old
    assert interface["id"] == 777
    assert called == [True]
    assert nb.patches and nb.patches[0][0] == "dcim/mac-addresses/700/"


def test_07_runtime_lookup_precedes_original_interface_creation():
    source = read("netbox-discovery/modules/importers/importer_v2.py")
    lookup = source.index("_interface_for_owned_mac(nb, device, spec.get(\"mac\"))")
    fallback = source.index("ORIG_ENSURE_INTERFACE(nb, apply_mode, device, spec, report)")
    assert lookup < fallback


def test_08_historical_release_documentation_remains_present():
    markers = {
        "RELEASE-NOTES.md": "## V1.11.22",
        "docs/PATCH-1.11.22.md": "# netbox-discovery 1.11.22",
    }
    for relative, marker in markers.items():
        assert marker in read(relative), relative


def main():
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    assert len(tests) >= 8
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.11.22 RUNTIME MAC INTERFACE REUSE TESTS PASSED: {0}".format(len(tests)))


if __name__ == "__main__":
    main()
