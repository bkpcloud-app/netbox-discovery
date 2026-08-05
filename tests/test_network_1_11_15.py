#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.product import runner
from modules.product import updater

VERSION = "1.11.15"
PREFLIGHT = "ExecStartPre=-/usr/local/bin/netbox-discovery update scheduled"


def read(relative):
    return open(os.path.join(ROOT, relative), "r").read()


def test_01_release_versions_are_1_11_15():
    assert read("VERSION").strip() == VERSION
    assert read("netbox-discovery/VERSION").strip() == VERSION


def _assert_update_before_collection(relative, collection_command):
    service = read(relative)
    assert PREFLIGHT in service
    assert collection_command in service
    assert service.index(PREFLIGHT) < service.index(collection_command)
    assert "TimeoutStartSec=0" in service
    assert "update run --apply" not in service
    assert "scheduled-run --apply" not in service


def test_02_network_service_updates_before_scheduled_collection():
    _assert_update_before_collection(
        "netbox-discovery/systemd/netbox-discovery.service",
        "ExecStart=/usr/local/bin/netbox-discovery scheduled-run",
    )


def test_03_hypervisor_service_updates_before_scheduled_collection():
    _assert_update_before_collection(
        "netbox-discovery/systemd/netbox-discovery-hypervisor.service",
        "ExecStart=/usr/local/bin/netbox-discovery hypervisor scheduled-run",
    )


def test_04_update_failure_is_tolerated_but_visible():
    for relative in (
        "netbox-discovery/systemd/netbox-discovery.service",
        "netbox-discovery/systemd/netbox-discovery-hypervisor.service",
    ):
        service = read(relative)
        # systemd '-' prefix keeps collection alive after an external updater error.
        assert "ExecStartPre=-/" in service
        assert "GitHub" in service
        assert "logged" in service or "registr" in service


def test_05_scheduled_updater_performs_real_validated_update():
    assert updater.CHANNEL == "stable"
    assert updater.LOCK_FILE == runner.LOCK_FILE
    source = read("netbox-discovery/modules/product/updater.py")
    assert 'choices=("status", "check", "run", "scheduled")' in source
    assert "return perform_update" in source
    assert "candidate_selftest(repo)" in source
    assert "backup_current(current)" in source
    assert "installed_selftest()" in source
    assert "restore_backup(backup)" in source


def test_06_update_preflight_does_not_enable_apply():
    for relative in (
        "netbox-discovery/systemd/netbox-discovery.service",
        "netbox-discovery/systemd/netbox-discovery-hypervisor.service",
    ):
        service = read(relative)
        assert "--apply" not in service
    docs = read("docs/MANUAL.md") + read("SECURITY.md")
    assert "não altera `automation.apply`" in docs or "não muda `automation.apply`" in docs


def test_07_documentation_is_current():
    markers = {
        "README.md": "**Versão atual:** 1.11.15",
        "docs/MANUAL.md": "**Versão:** 1.11.15",
        "docs/COMANDOS-RAPIDOS.md": "# netbox-discovery 1.11.15",
        "docs/HOMOLOGACAO.md": "# netbox-discovery 1.11.15",
        "RELEASE-NOTES.md": "## V1.11.15",
        "SECURITY.md": "**Versão da política:** 1.11.15",
        "docs/PATCH-1.11.15.md": "# netbox-discovery 1.11.15",
    }
    for relative, marker in markers.items():
        assert marker in read(relative), relative


def main():
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    assert len(tests) >= 7
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.11.15 UPDATE-BEFORE-SCHEDULED-RUN TESTS PASSED: {0}".format(len(tests)))


if __name__ == "__main__":
    main()
