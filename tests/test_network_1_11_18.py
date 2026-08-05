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

from modules.inventory import planner_v11
from modules.product import plan_report

VERSION = "1.11.18"
ENV_NAMES = (
    "NETBOX_DISCOVERY_MAX_CREATE",
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


def ready(action, total):
    return [
        {
            "decision": "READY",
            "action": action,
            "primary_ip": "10.0.0.{0}".format(index + 1),
            "reasons": ["TEST"],
            "interfaces": [],
            "ip_intents": [],
        }
        for index in range(total)
    ]


def test_01_release_versions_are_synced():
    assert read("VERSION").strip() == VERSION
    assert read("netbox-discovery/VERSION").strip() == VERSION


def test_02_small_site_uses_absolute_limits_and_allows_dcm_bootstrap():
    clear_guard_env()
    plan = ready("CREATE", 17)
    planner_v11._apply_final_write_guard(plan, {"devices": devices(13)})
    guard = plan[0]["write_guard"]
    assert guard["status"] == "PASS"
    assert guard["eligible_total"] == 17
    assert guard["live_devices"] == 13
    assert guard["change_percent"] == 131
    assert guard["percent_enforced"] is False
    assert guard["percent_min_base"] == 50
    assert guard["policy"] == "SMALL_SITE_BOOTSTRAP_ABSOLUTE_ONLY"
    assert guard["violations"] == []
    assert all(row["decision"] == "READY" and row["action"] == "CREATE" for row in plan)


def test_03_absolute_create_limit_still_blocks_small_site():
    clear_guard_env()
    plan = ready("CREATE", 26)
    planner_v11._apply_final_write_guard(plan, {"devices": devices(13)})
    guard = plan[0]["write_guard"]
    assert guard["status"] == "BLOCK"
    assert guard["percent_enforced"] is False
    assert "CREATE=26>25" in guard["violations"]
    assert all(row["decision"] == "BLOCKED" and row["action"] == "NOOP" for row in plan)


def test_04_percentage_limit_is_enforced_after_minimum_base():
    clear_guard_env()
    plan = ready("UPDATE_SAFE", 21)
    planner_v11._apply_final_write_guard(plan, {"devices": devices(100)})
    guard = plan[0]["write_guard"]
    assert guard["status"] == "BLOCK"
    assert guard["percent_enforced"] is True
    assert guard["policy"] == "ABSOLUTE_AND_PERCENT"
    assert guard["change_percent"] == 21
    assert "PERCENT=21%>20%" in guard["violations"]


def test_05_only_final_ready_changes_are_eligible():
    clear_guard_env()
    plan = ready("CREATE", 5)
    plan.extend([
        {"decision": "READY", "action": "NOOP"},
        {"decision": "REVIEW", "action": "CREATE"},
        {"decision": "BLOCKED", "action": "CREATE"},
        {"decision": "DELEGATED", "action": "NOOP"},
    ])
    planner_v11._apply_final_write_guard(plan, {"devices": devices(13)})
    guard = plan[0]["write_guard"]
    assert guard["eligible_total"] == 5
    assert guard["counts"] == {"CREATE": 5}
    assert guard["status"] == "PASS"


def test_06_minimum_base_is_configurable_but_safe_defaults_remain():
    clear_guard_env()
    os.environ["NETBOX_DISCOVERY_PERCENT_MIN_BASE"] = "10"
    try:
        plan = ready("UPDATE_SAFE", 11)
        planner_v11._apply_final_write_guard(plan, {"devices": devices(13)})
        guard = plan[0]["write_guard"]
        assert guard["percent_enforced"] is True
        assert guard["percent_min_base"] == 10
        assert guard["status"] == "BLOCK"
        assert "PERCENT=85%>20%" in guard["violations"]
    finally:
        clear_guard_env()


def test_07_native_report_shows_effective_policy():
    payload = {
        "site": "DCM",
        "run_id": "DCM-TEST",
        "run_status": "PLAN_READY",
        "netbox_write": False,
        "plan_path": "/tmp/DCM-plan.json",
        "record_count": 17,
        "decision_summary": {"READY": 17},
        "action_summary": {"CREATE": 17},
        "actions_by_decision": {"READY": {"CREATE": 17}},
        "reasons_by_decision": {},
        "write_guard": {
            "status": "PASS",
            "eligible_total": 17,
            "live_devices": 13,
            "change_percent": 131,
            "percent_enforced": False,
            "percent_min_base": 50,
            "policy": "SMALL_SITE_BOOTSTRAP_ABSOLUTE_ONLY",
            "violations": [],
        },
    }
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        plan_report.print_summary(payload)
    text = output.getvalue()
    assert "WRITE GUARD: PASS | elegíveis=17 | base=13 | mudanças=131%" in text
    assert "SMALL_SITE_BOOTSTRAP_ABSOLUTE_ONLY" in text
    assert "percentual=ADIADO" in text
    assert "base mínima=50" in text


def test_08_planner_v11_keeps_single_final_guard_contract():
    source = read("netbox-discovery/modules/inventory/planner_v11.py")
    assert "core._apply_write_guard = _defer_write_guard" in source
    assert "_apply_final_write_guard(plan, state)" in source
    assert '"PERCENT_MIN_BASE": _limit("NETBOX_DISCOVERY_PERCENT_MIN_BASE", 50)' in source
    assert "SMALL_SITE_BOOTSTRAP_ABSOLUTE_ONLY" in source


def test_09_documentation_is_current():
    markers = {
        "README.md": "**Versão atual:** 1.11.18",
        "docs/MANUAL.md": "**Versão:** 1.11.18",
        "docs/COMANDOS-RAPIDOS.md": "# netbox-discovery 1.11.18",
        "docs/HOMOLOGACAO.md": "# netbox-discovery 1.11.18",
        "RELEASE-NOTES.md": "## V1.11.18",
        "SECURITY.md": "**Versão da política:** 1.11.18",
        "docs/PATCH-1.11.18.md": "# netbox-discovery 1.11.18",
    }
    for relative, marker in markers.items():
        assert marker in read(relative), relative


def main():
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    assert len(tests) >= 9
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.11.18 SMALL-SITE WRITE GUARD TESTS PASSED: {0}".format(len(tests)))


if __name__ == "__main__":
    main()
