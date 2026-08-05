#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import contextlib
import io
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.inventory import planner_v11 as planner
from modules.inventory import planner_v9_core as core
from modules.product import plan_report

VERSION = "1.11.17"


def read(relative):
    return open(os.path.join(ROOT, relative), "r").read()


def prerequisites():
    return {
        "roles": [],
        "manufacturers": [],
        "platforms": [],
        "device_types": [],
    }


def live_state(total=13):
    return {"devices": [{"id": index + 1} for index in range(total)]}


def rows(total, decision="READY", action="CREATE"):
    return [
        {
            "asset_id": "ASSET-{0:03d}".format(index + 1),
            "primary_ip": "10.0.0.{0}".format(index + 1),
            "decision": decision,
            "action": action,
            "reasons": ["INTERMEDIATE_CANDIDATE"],
            "interfaces": [],
            "ip_intents": [],
        }
        for index in range(total)
    ]


def test_01_release_versions_are_1_11_17():
    assert read("VERSION").strip() == VERSION
    assert read("netbox-discovery/VERSION").strip() == VERSION


def test_02_dcm_intermediate_candidates_are_not_blocked_before_final_policies():
    original_builder = planner.ORIG_BUILD_PLAN

    def layered_builder(recon, classification, state):
        plan = rows(32)
        # This reproduces the lower Planner layer that previously saw
        # CREATE=32 and PERCENT=246% over 13 existing Devices.
        core._apply_write_guard(plan, state)
        # Final identity policies correctly turn every weak candidate into REVIEW.
        for row in plan:
            if row.get("decision") == "READY":
                row["decision"] = "REVIEW"
                row["action"] = "NOOP"
                row["reasons"] = ["FINAL_IDENTITY_REVIEW"]
        return plan, prerequisites()

    planner.ORIG_BUILD_PLAN = layered_builder
    try:
        plan, unused = planner.build_plan({}, {}, live_state(13))
    finally:
        planner.ORIG_BUILD_PLAN = original_builder

    assert len(plan) == 32
    assert set(row.get("decision") for row in plan) == {"REVIEW"}
    assert set(row.get("action") for row in plan) == {"NOOP"}
    assert not any(
        "WRITE_GUARD_LIMIT_EXCEEDED" in reason
        for row in plan for reason in (row.get("reasons") or [])
    )
    guard = plan[0].get("write_guard") or {}
    assert guard.get("status") == "PASS"
    assert guard.get("eligible_total") == 0
    assert guard.get("counts") == {}


def test_03_real_final_excess_is_still_blocked():
    original_builder = planner.ORIG_BUILD_PLAN

    def final_excess_builder(recon, classification, state):
        return rows(26), prerequisites()

    planner.ORIG_BUILD_PLAN = final_excess_builder
    try:
        plan, unused = planner.build_plan({}, {}, live_state(1000))
    finally:
        planner.ORIG_BUILD_PLAN = original_builder

    assert len(plan) == 26
    assert set(row.get("decision") for row in plan) == {"BLOCKED"}
    assert set(row.get("action") for row in plan) == {"NOOP"}
    guard = plan[0].get("write_guard") or {}
    assert guard.get("status") == "BLOCK"
    assert guard.get("eligible_total") == 26
    assert guard.get("counts", {}).get("CREATE") == 26
    assert "CREATE=26>25" in guard.get("violations", [])
    assert all(
        any("WRITE_GUARD_LIMIT_EXCEEDED" in reason for reason in row.get("reasons") or [])
        for row in plan
    )


def test_04_guard_function_is_restored_after_layer_failure():
    original_builder = planner.ORIG_BUILD_PLAN
    original_guard = core._apply_write_guard

    def failing_builder(recon, classification, state):
        assert core._apply_write_guard is planner._defer_write_guard
        raise RuntimeError("simulated planner failure")

    planner.ORIG_BUILD_PLAN = failing_builder
    try:
        try:
            planner.build_plan({}, {}, live_state())
            raise AssertionError("falha simulada não propagou")
        except RuntimeError as exc:
            assert "simulated planner failure" in str(exc)
    finally:
        planner.ORIG_BUILD_PLAN = original_builder

    assert core._apply_write_guard is original_guard


def test_05_plan_report_exposes_effective_guard():
    guard = {
        "status": "PASS",
        "eligible_total": 0,
        "live_devices": 13,
        "change_percent": 0,
        "counts": {},
        "violations": [],
    }
    plan = {
        "records": [
            {
                "decision": "REVIEW",
                "action": "NOOP",
                "primary_ip": "10.0.0.1",
                "reasons": ["FINAL_IDENTITY_REVIEW"],
                "write_guard": guard,
            }
        ]
    }
    payload = plan_report.build_payload(
        "DCM", "/tmp/DCM-plan.json", plan, "/tmp/DCM-run.json",
        {"run_id": "DCM-TEST", "status": "PLAN_READY", "netbox_write": False},
    )
    assert payload["write_guard"] == guard
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        plan_report.print_summary(payload)
    text = output.getvalue()
    assert "WRITE GUARD: PASS" in text
    assert "elegíveis=0" in text
    assert "base=13" in text


def test_06_only_planner_v11_performs_the_effective_final_guard():
    source = read("netbox-discovery/modules/inventory/planner_v11.py")
    assert "core._apply_write_guard = _defer_write_guard" in source
    assert "core._apply_write_guard = final_write_guard" in source
    assert "final_write_guard(plan, state)" in source
    assert source.index("plan, prereq = ORIG_BUILD_PLAN") < source.index("final_write_guard(plan, state)")


def test_07_documentation_is_current():
    markers = {
        "README.md": "**Versão atual:** 1.11.17",
        "docs/MANUAL.md": "**Versão:** 1.11.17",
        "docs/COMANDOS-RAPIDOS.md": "# netbox-discovery 1.11.17",
        "docs/HOMOLOGACAO.md": "# netbox-discovery 1.11.17",
        "RELEASE-NOTES.md": "## V1.11.17",
        "SECURITY.md": "**Versão da política:** 1.11.17",
        "docs/PATCH-1.11.17.md": "# netbox-discovery 1.11.17",
    }
    for relative, marker in markers.items():
        assert marker in read(relative), relative


def main():
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    assert len(tests) >= 7
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.11.17 FINAL WRITE-GUARD TESTS PASSED: {0}".format(len(tests)))


if __name__ == "__main__":
    main()
