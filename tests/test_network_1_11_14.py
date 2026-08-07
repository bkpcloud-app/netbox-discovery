#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")


def read(path):
    return open(path, "r").read()


def version_key(value):
    return tuple(int(part) for part in value.strip().split("."))


VERSION = read(os.path.join(ROOT, "VERSION")).strip()


def test_01_release_versions_are_synced_and_not_older_than_1_11_14():
    assert read(os.path.join(BASE, "VERSION")).strip() == VERSION
    assert version_key(VERSION) >= version_key("1.11.14")


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


def test_06_patch_release_documentation_matches_selftest_contract():
    patch = read(os.path.join(ROOT, "docs", "PATCH-{0}.md".format(VERSION)))
    assert "# netbox-discovery {0}".format(VERSION) in patch
    exact = {
        "README.md": "**Versão atual:** {0}".format(VERSION),
        "docs/MANUAL.md": "**Versão:** {0}".format(VERSION),
        "docs/COMANDOS-RAPIDOS.md": "# netbox-discovery {0}".format(VERSION),
        "docs/HOMOLOGACAO.md": "# netbox-discovery {0}".format(VERSION),
        "RELEASE-NOTES.md": "## V{0}".format(VERSION),
        "SECURITY.md": "**Versão da política:** {0}".format(VERSION),
    }
    for relative, marker in exact.items():
        assert marker in read(os.path.join(ROOT, relative)), relative


def test_07_ci_uses_same_patch_release_documentation_contract():
    workflow = read(os.path.join(ROOT, ".github", "workflows", "ci.yml"))
    assert 'test -f "docs/PATCH-$V.md"' in workflow
    assert 'grep -Fq "# netbox-discovery $V" "docs/PATCH-$V.md"' in workflow
    required_lines = (
        'grep -Fq "**Versão atual:** $V" README.md',
        'grep -Fq "**Versão:** $V" docs/MANUAL.md',
        'grep -Fq "# netbox-discovery $V" docs/COMANDOS-RAPIDOS.md',
        'grep -Fq "# netbox-discovery $V" docs/HOMOLOGACAO.md',
        'grep -Fq "## V$V" RELEASE-NOTES.md',
        'grep -Fq "**Versão da política:** $V" SECURITY.md',
    )
    for line in required_lines:
        assert line in workflow, line


def main():
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    assert len(tests) >= 7
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.11.14 SCHEDULER/AUTO-UPDATE/DOCS TESTS PASSED: {0}".format(len(tests)))


if __name__ == "__main__":
    main()
