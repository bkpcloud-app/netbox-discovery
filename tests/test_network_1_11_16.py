#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.product import plan_report

VERSION = "1.11.16"


def read(relative):
    return open(os.path.join(ROOT, relative), "r").read()


def sample_plan():
    return {
        "records": [
            {
                "decision": "BLOCKED", "action": "CREATE", "primary_ip": "10.0.0.1",
                "desired_name": "SW-01", "role": "SWITCH",
                "reasons": ["WRITE_GUARD_BLOCKED", "DUPLICATE_DESIRED_NAME"],
            },
            {
                "decision": "BLOCKED", "action": "CREATE", "primary_ip": "10.0.0.2",
                "desired_name": "SW-02", "role": "SWITCH",
                "reasons": ["WRITE_GUARD_BLOCKED"],
            },
            {
                "decision": "REVIEW", "action": "NOOP", "primary_ip": "10.0.0.3",
                "observed_name": "HOST-03", "role": "WINDOWS_HOST",
                "reasons": ["NEW_PHYSICAL_DEVICE_REQUIRES_STABLE_IDENTITY"],
            },
            {
                "decision": "READY", "action": "CREATE", "primary_ip": "10.0.0.4",
                "desired_name": "PRN-04", "role": "PRINTER", "reasons": ["NEW_DEVICE"],
            },
            {
                "decision": "DELEGATED", "action": "NOOP", "primary_ip": "10.0.0.5",
                "observed_name": "VM-05", "role": "VIRTUAL_MACHINE",
                "reasons": ["VM_INTERFACE_IP_OWNER"],
            },
        ]
    }


def sample_run():
    return {
        "run_id": "DCM-TEST-001",
        "status": "PLAN_READY",
        "apply_requested": False,
        "netbox_write": False,
    }


def test_01_release_versions_are_synced():
    assert read("VERSION").strip() == VERSION
    assert read("netbox-discovery/VERSION").strip() == VERSION


def test_02_payload_separates_decisions_actions_and_reasons():
    payload = plan_report.build_payload("DCM", "/tmp/plan.json", sample_plan(), "/tmp/run.json", sample_run())
    assert payload["decision_summary"] == {
        "BLOCKED": 2, "REVIEW": 1, "READY": 1, "DELEGATED": 1,
    }
    assert payload["actions_by_decision"]["BLOCKED"] == {"CREATE": 2}
    assert payload["actions_by_decision"]["READY"] == {"CREATE": 1}
    assert payload["reasons_by_decision"]["BLOCKED"]["WRITE_GUARD_BLOCKED"] == 2
    assert payload["reasons_by_decision"]["BLOCKED"]["DUPLICATE_DESIRED_NAME"] == 1
    assert payload["netbox_write"] is False


def test_03_native_summary_and_blocked_views_are_read_only():
    root = tempfile.mkdtemp(prefix="plan-report-1-11-16-")
    old_reports = plan_report.REPORTS
    old_site = plan_report.configured_site
    try:
        plan_report.REPORTS = root
        plan_report.configured_site = lambda: "DCM"
        with open(os.path.join(root, "DCM-plan-20260805-120000.json"), "w") as handle:
            json.dump(sample_plan(), handle)
        with open(os.path.join(root, "DCM-run-20260805-120100.json"), "w") as handle:
            json.dump(sample_run(), handle)

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            assert plan_report.main(["summary"]) == 0
        text = output.getvalue()
        assert "PLAN SUMMARY" in text
        assert "Run ID: DCM-TEST-001" in text
        assert "NetBox write: NÃO" in text
        assert "BLOCKED: 2" in text
        assert "WRITE_GUARD_BLOCKED: 2" in text
        assert "somente leitura" in text

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            assert plan_report.main(["blocked"]) == 0
        text = output.getvalue()
        assert "PLAN BLOCKED: 2" in text
        assert "10.0.0.1" in text
        assert "DUPLICATE_DESIRED_NAME" in text
    finally:
        plan_report.REPORTS = old_reports
        plan_report.configured_site = old_site
        shutil.rmtree(root)


def test_04_planner_command_preserves_generation_and_adds_native_views():
    source = read("netbox-discovery/modules/inventory/planner_v11.py")
    assert '"summary", "blocked", "review", "ready", "delegated", "all"' in source
    assert "return plan_report.main(args)" in source
    assert "return v10.main(args)" in source


def test_05_status_does_not_mix_historical_apply_into_dry_run():
    source = read("netbox-discovery/modules/product/status.py")
    assert 'not bool(run.get("apply_requested", False))' in source
    assert "IMPORT: NÃO EXECUTADO NESTE RUN (dry-run)" in source
    assert "AUDIT: NÃO EXECUTADO NESTE RUN (dry-run)" in source


def test_06_report_module_has_no_write_path():
    source = read("netbox-discovery/modules/product/plan_report.py")
    forbidden = ("importer_v", "--apply", "requests.post", "requests.patch", "requests.delete")
    for marker in forbidden:
        assert marker not in source


def test_07_documentation_is_current():
    markers = {
        "README.md": "**Versão atual:** 1.11.16",
        "docs/MANUAL.md": "**Versão:** 1.11.16",
        "docs/COMANDOS-RAPIDOS.md": "# netbox-discovery 1.11.16",
        "docs/HOMOLOGACAO.md": "# netbox-discovery 1.11.16",
        "RELEASE-NOTES.md": "## V1.11.16",
        "SECURITY.md": "**Versão da política:** 1.11.16",
        "docs/PATCH-1.11.16.md": "# netbox-discovery 1.11.16",
    }
    for relative, marker in markers.items():
        assert marker in read(relative), relative


def main():
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    assert len(tests) >= 7
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.11.16 NATIVE PLAN REPORT TESTS PASSED: {0}".format(len(tests)))


if __name__ == "__main__":
    main()
