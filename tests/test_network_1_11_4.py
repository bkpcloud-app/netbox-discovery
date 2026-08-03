#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import os
import shutil
import sys
import tempfile
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.inventory import pipeline


def write_json(path, data):
    with open(path, "w") as handle:
        json.dump(data, handle)


def test_discovery_filename_timestamp_beats_mtime():
    temp = tempfile.mkdtemp(prefix="nbd-1-11-4-")
    try:
        old = os.path.join(temp, "FBA-discovery-20260730-022052.json")
        new = os.path.join(temp, "FBA-discovery-20260803-155006.json")
        other = os.path.join(temp, "DCM-discovery-20260804-010000.json")
        write_json(old, {"site": "FBA", "mode": "DRY-RUN", "devices": []})
        write_json(new, {"site": "FBA", "mode": "DRY-RUN", "devices": []})
        write_json(other, {"site": "DCM", "mode": "DRY-RUN", "devices": []})
        now = time.time()
        os.utime(new, (now - 500, now - 500))
        os.utime(old, (now, now))
        assert pipeline.latest_discovery(temp, "FBA") == new
    finally:
        shutil.rmtree(temp)


def test_linked_stage_cannot_mix_old_source():
    temp = tempfile.mkdtemp(prefix="nbd-1-11-4-link-")
    try:
        old_discovery = os.path.join(temp, "FBA-discovery-20260730-022052.json")
        new_discovery = os.path.join(temp, "FBA-discovery-20260803-155006.json")
        stale = os.path.join(temp, "FBA-classification-20260803-170100.json")
        correct = os.path.join(temp, "FBA-classification-20260803-170000.json")
        write_json(stale, {"source_discovery": old_discovery})
        write_json(correct, {"source_discovery": new_discovery})
        now = time.time()
        os.utime(stale, (now, now))
        os.utime(correct, (now - 100, now - 100))
        selected = pipeline.linked_report(
            temp, "classification", {"source_discovery": new_discovery}
        )
        assert selected == correct
    finally:
        shutil.rmtree(temp)


def test_missing_link_fails_closed():
    temp = tempfile.mkdtemp(prefix="nbd-1-11-4-closed-")
    try:
        path = os.path.join(temp, "FBA-plan-20260803-170000.json")
        write_json(path, {"source_reconciliation": "/reports/old.json"})
        try:
            pipeline.linked_report(
                temp, "plan", {"source_reconciliation": "/reports/current.json"}
            )
        except RuntimeError as exc:
            assert "sem gerar relatório vinculado" in str(exc)
        else:
            raise AssertionError("pipeline aceitou PLAN de outra execução")
    finally:
        shutil.rmtree(temp)


def main():
    tests = [
        test_discovery_filename_timestamp_beats_mtime,
        test_linked_stage_cannot_mix_old_source,
        test_missing_link_fails_closed,
    ]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL NETWORK 1.11.4 LINKED INVENTORY REGRESSIONS PASSED")


if __name__ == "__main__":
    main()
