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
from modules.importers import importer_v12

VERSION = "1.11.20"
MAC = "E8:B5:D0:72:9D:FC"


def read(relative):
    return open(os.path.join(ROOT, relative), "r").read()


def ready(name="SW-CORE-AE", existing=None, mac=MAC):
    return {
        "asset_id": "ASSET-TEST",
        "desired_name": name,
        "existing_device_id": existing,
        "decision": "READY",
        "action": "CREATE" if existing is None else "NOOP",
        "discovery_uid": "SERIAL:dell:TW0YYTHYDNT0025R0536A00",
        "reasons": ["TEST"],
        "interfaces": [{"name": "MGMT", "mac": mac, "ip": "10.19.1.30"}],
        "ip_intents": [{"address": "10.19.1.30/24", "action": "CREATE"}],
        "safe_diffs": [],
    }


def state(owner_device=321, interface_id=543, duplicate=False, assigned_type="dcim.interface"):
    macs = [{
        "id": 700,
        "mac_address": MAC,
        "assigned_object_type": assigned_type,
        "assigned_object_id": interface_id,
    }]
    if duplicate:
        macs.append({
            "id": 701,
            "mac_address": MAC,
            "assigned_object_type": assigned_type,
            "assigned_object_id": interface_id + 1,
        })
    return {
        "devices": [{"id": owner_device, "name": "EXISTING-SWITCH"}],
        "interfaces": [{
            "id": interface_id,
            "name": "MGMT",
            "device": {"id": owner_device, "name": "EXISTING-SWITCH"},
        }],
        "macs": macs,
    }


def test_01_release_versions_are_synced():
    assert read("VERSION").strip() == VERSION
    assert read("netbox-discovery/VERSION").strip() == VERSION


def test_02_planner_blocks_new_device_when_mac_is_owned_elsewhere():
    row = ready()
    planner._enforce_global_mac_ownership([row], state())
    assert row["decision"] == "BLOCKED"
    assert row["action"] == "NOOP"
    assert row["interfaces"] == []
    assert row["ip_intents"] == []
    assert any("MAC_ALREADY_ASSIGNED_TO_OTHER_DEVICE" in reason for reason in row["reasons"])
    conflict = row["mac_ownership_conflicts"][0]
    assert conflict["device_id"] == 321
    assert conflict["interface_id"] == 543


def test_03_planner_allows_mac_owned_by_same_existing_device():
    row = ready(existing=321)
    planner._enforce_global_mac_ownership([row], state(owner_device=321))
    assert row["decision"] == "READY"
    assert row["action"] == "NOOP"
    assert row["interfaces"]


def test_04_planner_blocks_non_device_assignment_and_duplicates():
    other = ready()
    planner._enforce_global_mac_ownership(
        [other], state(assigned_type="virtualization.vminterface"))
    assert other["decision"] == "BLOCKED"
    assert any("MAC_ALREADY_ASSIGNED_TO_OBJECT" in reason for reason in other["reasons"])

    duplicate = ready()
    planner._enforce_global_mac_ownership([duplicate], state(duplicate=True))
    assert duplicate["decision"] == "BLOCKED"
    assert any("MAC_GLOBAL_DUPLICATE" in reason for reason in duplicate["reasons"])


def test_05_import_preflight_detects_mac_conflict_before_write():
    row = ready()

    def rematch(unused_row, unused_indexes):
        return None, "NEW", "sem correspondência"

    errors = importer_v12._global_mac_preflight_errors(
        [row], {}, state()["macs"], state()["interfaces"], rematch)
    assert len(errors) == 1
    assert "MAC E8:B5:D0:72:9D:FC pertence ao Device ID 321" in errors[0]
    assert "interface ID 543" in errors[0]
    assert "alvo=NOVO" in errors[0]


def test_06_import_preflight_allows_same_existing_owner():
    row = ready(existing=321)

    def rematch(unused_row, unused_indexes):
        return {"id": 321}, "MATCHED", "plan-existing-device-id"

    errors = importer_v12._global_mac_preflight_errors(
        [row], {}, state()["macs"], state()["interfaces"], rematch)
    assert errors == []


def test_07_dcm_partial_apply_isolated_and_other_candidates_remain_eligible():
    conflicted = ready(existing=900)
    safe = []
    for index in range(13):
        item = ready(
            name="SAFE-{0}".format(index + 1),
            mac="00:11:22:33:44:{0:02X}".format(index + 1),
        )
        safe.append(item)
    plan = [conflicted] + safe
    live = state(owner_device=321)
    live["devices"].append({"id": 900, "name": "SW-CORE-AE"})

    planner._enforce_global_mac_ownership(plan, live)
    planner._apply_final_write_guard(plan, live)

    assert conflicted["decision"] == "BLOCKED"
    eligible = [
        row for row in plan
        if row.get("decision") == "READY" and row.get("action") == "CREATE"
    ]
    assert len(eligible) == 13
    assert safe[0]["write_guard"]["status"] == "PASS"
    assert safe[0]["write_guard"]["eligible_total"] == 13


def test_08_mac_guard_runs_before_final_write_guard():
    source = read("netbox-discovery/modules/inventory/planner_v11.py")
    mac_call = source.index("_enforce_global_mac_ownership(plan, state)")
    write_call = source.index("_apply_final_write_guard(plan, state)")
    assert mac_call < write_call


def test_09_importer_patches_both_legacy_module_objects():
    source = read("netbox-discovery/modules/importers/importer_v12.py")
    assert "package_base.preflight_ready = global_mac_preflight" in source
    assert "v2.base.preflight_ready = global_mac_preflight" in source
    assert "GLOBAL_MAC_PREFLIGHT_UNAVAILABLE" in source


def test_10_documentation_is_current():
    markers = {
        "README.md": "**Versão atual:** 1.11.20",
        "docs/MANUAL.md": "**Versão:** 1.11.20",
        "docs/COMANDOS-RAPIDOS.md": "# netbox-discovery 1.11.20",
        "docs/HOMOLOGACAO.md": "# netbox-discovery 1.11.20",
        "RELEASE-NOTES.md": "## V1.11.20",
        "SECURITY.md": "**Versão da política:** 1.11.20",
        "docs/PATCH-1.11.20.md": "# netbox-discovery 1.11.20",
    }
    for relative, marker in markers.items():
        assert marker in read(relative), relative


def main():
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    assert len(tests) >= 10
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.11.20 GLOBAL MAC PREFLIGHT TESTS PASSED: {0}".format(len(tests)))


if __name__ == "__main__":
    main()
