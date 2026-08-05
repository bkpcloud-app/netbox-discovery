#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.discovery import network_v6 as v6
from modules.product import runner


def test_01_large_prefix_is_split_and_overlap_is_not_scanned_twice():
    targets = v6._scan_targets([
        "10.19.0.0/16",
        "10.19.1.0/24",
        "10.1.1.0/24",
    ])
    assert len(targets) == 257
    assert targets.count("10.19.1.0/24") == 1
    assert "10.19.0.0/24" in targets
    assert "10.19.255.0/24" in targets
    assert "10.1.1.0/24" in targets


def test_02_small_inventory_keeps_legacy_discovery_path():
    old_candidates = v6.base._all_candidate_ips
    old_legacy = v6.ORIG_DISCOVER_HOSTS
    marker = {"legacy": True}
    try:
        v6.base._all_candidate_ips = lambda networks, exclusions: ["10.0.0.1"]
        v6.ORIG_DISCOVER_HOSTS = lambda networks, communities, exclusions: marker
        assert v6.discover_hosts(["10.0.0.0/24"], ["public"], []) is marker
    finally:
        v6.ORIG_DISCOVER_HOSTS = old_legacy
        v6.base._all_candidate_ips = old_candidates


def test_03_large_inventory_uses_primary_and_snmp_without_legacy_tcp_rescue():
    old_threshold = v6.LARGE_CANDIDATE_THRESHOLD
    old_candidates = v6.base._all_candidate_ips
    old_filter = v6.base._filter_discovered_hosts
    old_targets = v6._scan_targets
    old_primary = v6._run_primary_targets
    old_snmp = v6._large_snmp_rescue
    old_legacy = v6.ORIG_DISCOVER_HOSTS
    called = {"legacy": 0, "snmp_missing": None}
    try:
        v6.LARGE_CANDIDATE_THRESHOLD = 2
        v6.base._all_candidate_ips = lambda networks, exclusions: [
            "10.0.0.1", "10.0.0.2", "10.0.0.3", "10.0.0.4"
        ]
        v6.base._filter_discovered_hosts = lambda hosts, candidates: hosts
        v6._scan_targets = lambda networks: ["10.0.0.0/24"]
        v6._run_primary_targets = lambda targets: {
            "10.0.0.1": {"ip": "10.0.0.1", "discovery_sources": ["primary"]}
        }

        def fake_snmp(missing, communities):
            called["snmp_missing"] = list(missing)
            return {
                "10.0.0.3": {"ip": "10.0.0.3", "discovery_sources": ["snmp"]}
            }

        v6._large_snmp_rescue = fake_snmp

        def legacy(*args):
            called["legacy"] += 1
            return {}

        v6.ORIG_DISCOVER_HOSTS = legacy
        result = v6.discover_hosts(["10.0.0.0/24"], ["public"], [])
        assert called["legacy"] == 0
        assert called["snmp_missing"] == ["10.0.0.2", "10.0.0.3", "10.0.0.4"]
        assert sorted(result) == ["10.0.0.1", "10.0.0.3"]
    finally:
        v6.ORIG_DISCOVER_HOSTS = old_legacy
        v6._large_snmp_rescue = old_snmp
        v6._run_primary_targets = old_primary
        v6._scan_targets = old_targets
        v6.base._filter_discovered_hosts = old_filter
        v6.base._all_candidate_ips = old_candidates
        v6.LARGE_CANDIDATE_THRESHOLD = old_threshold


def test_04_primary_timeout_is_explicit_instead_of_blank_error():
    old_run = v6.base.run_command
    try:
        v6.base.run_command = lambda command, timeout: (124, "", "")
        target, hosts, error = v6._scan_primary_target("10.19.0.0/24", 240)
        assert target == "10.19.0.0/24"
        assert hosts == {}
        assert "timeout após 240s" in error
        assert "exit=124" in error
    finally:
        v6.base.run_command = old_run


def test_05_primary_command_contains_ot_and_management_ports():
    command = v6._primary_command("10.19.0.0/24")
    ps = next(value for value in command if value.startswith("-PS"))
    pu = next(value for value in command if value.startswith("-PU"))
    assert "102" in ps.split("-PS", 1)[1].split(",")
    assert "502" in ps.split("-PS", 1)[1].split(",")
    assert "9100" in ps.split("-PS", 1)[1].split(",")
    assert "161" in pu.split("-PU", 1)[1].split(",")


def test_06_runner_uses_v6_for_normal_and_scheduled_runs():
    assert runner.RUNNER_VERSION == "3.4-product"
    assert runner.COMPONENTS["discovery"] == "network_v6.py"
    source = open(os.path.join(BASE, "modules", "product", "runner.py"), "r").read()
    assert '"modules/discovery/network_v6.py"' in source
    assert '"modules/discovery/network_v5.py"' not in source


def test_07_release_version():
    assert open(os.path.join(ROOT, "VERSION"), "r").read().strip() == "1.11.13"
    assert open(os.path.join(BASE, "VERSION"), "r").read().strip() == "1.11.13"


def main():
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    assert len(tests) >= 7
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.11.12 LARGE-CIDR TESTS PASSED: {0}".format(len(tests)))


if __name__ == "__main__":
    main()
