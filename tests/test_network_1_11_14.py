#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
VERSION = "1.11.14"


def read(path):
    return open(path, "r").read()


def test_01_release_versions_are_synced():
    assert read(os.path.join(ROOT, "VERSION")).strip() == VERSION
    assert read(os.path.join(BASE, "VERSION")).strip() == VERSION


def test_02_network_scheduler_starts_update_timer_without_disable_coupling():
    timer = read(os.path.join(BASE, "systemd", "netbox-discovery.timer"))
    assert "Wants=netbox-discovery-update.timer" in timer
    assert "After=netbox-discovery-update.timer" in timer
    assert "Also=netbox-discovery-update.timer" not in timer


def test_03_hypervisor_scheduler_starts_update_timer_without_disable_coupling():
    timer = read(os.path.join(BASE, "systemd", "netbox-discovery-hypervisor.timer"))
    assert "Wants=netbox-discovery-update.timer" in timer
    assert "After=netbox-discovery-update.timer" in timer
    assert "Also=netbox-discovery-update.timer" not in timer


def test_04_update_timer_is_daily_persistent_and_randomized():
    timer = read(os.path.join(BASE, "systemd", "netbox-discovery-update.timer"))
    assert "OnCalendar=daily" in timer
    assert "Persistent=true" in timer
    assert "RandomizedDelaySec=30m" in timer


def test_05_installer_enables_update_but_not_collection_schedulers():
    installer = read(os.path.join(ROOT, "install.sh"))
    assert "systemctl enable --now netbox-discovery-update.timer" in installer
    assert "Schedulers network/hypervisor: NÃO HABILITADOS" in installer


def test_06_every_required_document_has_exact_release_version():
    markers = {
        "README.md": "**Versão atual:** {0}".format(VERSION),
        "docs/MANUAL.md": "**Versão:** {0}".format(VERSION),
        "docs/COMANDOS-RAPIDOS.md": "# netbox-discovery {0}".format(VERSION),
        "docs/HOMOLOGACAO.md": "# netbox-discovery {0}".format(VERSION),
        "RELEASE-NOTES.md": "## V{0}".format(VERSION),
        "SECURITY.md": "**Versão da política:** {0}".format(VERSION),
        "docs/PATCH-{0}.md".format(VERSION): "# netbox-discovery {0}".format(VERSION),
    }
    for relative, marker in markers.items():
        text = read(os.path.join(ROOT, relative))
        assert marker in text, "documentação fora da versão: {0}".format(relative)


def test_07_ci_requires_exact_document_markers():
    workflow = read(os.path.join(ROOT, ".github", "workflows", "ci.yml"))
    required = (
        'grep -Fq "**Versão atual:** $V" README.md',
        'grep -Fq "**Versão:** $V" docs/MANUAL.md',
        'grep -Fq "# netbox-discovery $V" docs/COMANDOS-RAPIDOS.md',
        'grep -Fq "# netbox-discovery $V" docs/HOMOLOGACAO.md',
        'grep -Fq "## V$V" RELEASE-NOTES.md',
        'grep -Fq "**Versão da política:** $V" SECURITY.md',
    )
    for marker in required:
        assert marker in workflow, marker


def main():
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    assert len(tests) >= 7
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.11.14 SCHEDULER/AUTO-UPDATE/DOCS TESTS PASSED: {0}".format(len(tests)))


if __name__ == "__main__":
    main()
