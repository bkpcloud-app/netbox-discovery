#!/usr/bin/env python3
import copy
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
sys.path.insert(0, BASE)

from modules.hypervisor import engine_v5


def review_row(reason="serial/UUID da VM diverge do objeto existente"):
    return {
        "asset_id": "HV-VM:src:replica-uuid",
        "object_type": "VM",
        "existing_id": 501,
        "decision": "REVIEW",
        "action": "UPDATE_SAFE",
        "reason": reason,
        "target_tenant": "MIZU",
        "target_site": "FVI",
    }


def reclassify_row(site="FAB"):
    return {
        "asset_id": "HV-VM:src:vm-uuid",
        "object_type": "VM",
        "existing_id": 601,
        "decision": "READY",
        "action": "RECLASSIFY_SAFE",
        "target_tenant": "MIZU",
        "target_site": site,
    }


def plan(rows):
    ready = [x for x in rows if x.get("decision") == "READY"]
    summary = {}
    for row in ready:
        action = row.get("action")
        summary[action] = summary.get(action, 0) + 1
    return {"records": rows, "ready_action_summary": summary}


def run_preflight(original, live):
    previous = engine_v5.v3.build_plan
    engine_v5.v3.build_plan = lambda discovery, nb=None: (copy.deepcopy(live), "/tmp/live-plan.json")
    try:
        return engine_v5._global_preflight_with_stable_review({}, copy.deepcopy(original), object())
    finally:
        engine_v5.v3.build_plan = previous


def expect_runtime_error(original, live, expected):
    try:
        run_preflight(original, live)
    except RuntimeError as exc:
        assert expected in str(exc), str(exc)
        return
    raise AssertionError("RuntimeError esperado: " + expected)


def test_stable_review_is_ignored_but_not_written():
    original = plan([review_row(), reclassify_row()])
    live = copy.deepcopy(original)
    result = run_preflight(original, live)
    assert result["records"][0]["decision"] == "REVIEW"
    assert result["records"][1]["decision"] == "READY"


def test_changed_review_aborts_before_write():
    original = plan([review_row()])
    live = plan([review_row("conflito novo")])
    expect_runtime_error(original, live, "conjunto REVIEW mudou")


def test_new_review_aborts_before_write():
    original = plan([])
    live = plan([review_row()])
    expect_runtime_error(original, live, "conjunto REVIEW mudou")


def test_blocked_always_aborts_before_write():
    original = plan([])
    live = plan([{
        "asset_id": "BLOCKED:1", "object_type": "VM", "decision": "BLOCKED",
        "action": "NOOP", "reason": "bloqueio de segurança",
    }])
    expect_runtime_error(original, live, "1 BLOCKED")


def test_reclassify_drift_still_aborts_before_write():
    original = plan([reclassify_row("FAB")])
    live = plan([reclassify_row("FBA")])
    expect_runtime_error(original, live, "conjunto RECLASSIFY_SAFE mudou")


def main():
    tests = [
        test_stable_review_is_ignored_but_not_written,
        test_changed_review_aborts_before_write,
        test_new_review_aborts_before_write,
        test_blocked_always_aborts_before_write,
        test_reclassify_drift_still_aborts_before_write,
    ]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.11.29 HYPERVISOR PREFLIGHT TESTS PASSED")


if __name__ == "__main__":
    main()
