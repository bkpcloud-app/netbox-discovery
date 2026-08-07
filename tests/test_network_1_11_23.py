#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MIN_VERSION = (1, 11, 23)


def read(relative):
    return open(os.path.join(ROOT, relative), "r").read()


def version_tuple(value):
    return tuple(int(part) for part in value.strip().split("."))


def test_01_versions_include_1_11_23_or_newer():
    root_version = read("VERSION").strip()
    package_version = read("netbox-discovery/VERSION").strip()
    assert root_version == package_version
    assert version_tuple(root_version) >= MIN_VERSION


def test_02_public_wrapper_exposes_go_live_and_delegates_legacy_commands():
    source = read("netbox-discovery/bin/netbox-discovery-wrapper")
    assert 'COMMAND="${1:-help}"' in source
    assert 'go-live)' in source
    assert 'modules/product/go_live.py' in source
    assert 'exec "$BASE/bin/netbox-discovery" "$@"' in source
    assert 'netbox-discovery go-live' in source


def test_03_installer_activates_wrapper():
    source = read("install.sh")
    assert 'chmod +x "$TARGET/bin/netbox-discovery" "$TARGET/bin/netbox-discovery-wrapper"' in source
    assert 'ln -sfn "$TARGET/bin/netbox-discovery-wrapper" /usr/local/bin/netbox-discovery' in source


def test_04_go_live_uses_standard_native_stages_in_order():
    source = read("netbox-discovery/modules/product/go_live.py")
    main_body = source[source.index("def main():"):]
    markers = [
        'run("import", "--apply")',
        'run("audit")',
        'run("plan")',
        'run("plan", "summary")',
        'validate_convergence()',
        'run("configure", "--non-interactive", "--no-automation", "--no-auto-apply", "--skip-test")',
        'run("scheduler", "enable")',
        'verify_safe_scheduler()',
        'run("status")',
    ]
    positions = [main_body.index(marker) for marker in markers]
    assert positions == sorted(positions)


def test_05_go_live_fails_closed_on_pending_ready_changes():
    source = read("netbox-discovery/modules/product/go_live.py")
    assert 'PENDING_ACTIONS = {"CREATE", "UPDATE_SAFE", "REPAIR_SAFE_VM_DUPLICATE"}' in source
    assert 'decision == "READY" and action in PENDING_ACTIONS' in source
    assert 'GO-LIVE interrompido antes de habilitar o scheduler' in source


def test_06_go_live_verifies_scheduler_read_only_state():
    source = read("netbox-discovery/modules/product/go_live.py")
    assert 'enabled = bool(automation.get("enabled", False))' in source
    assert 'apply_mode = bool(automation.get("apply", False))' in source
    assert 'if not enabled or apply_mode:' in source
    assert 'run("scheduler", "disable")' in source
    assert 'APPLY AUTOMÁTICO: NÃO' in source


def test_07_historical_1_11_23_documentation_remains_available():
    markers = {
        "RELEASE-NOTES.md": "## V1.11.23",
        "docs/PATCH-1.11.23.md": "# netbox-discovery 1.11.23",
        "docs/NOVA-UNIDADE-DOIS-PASSOS.md": "netbox-discovery go-live",
    }
    for relative, marker in markers.items():
        assert marker in read(relative), relative


def main():
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    assert len(tests) >= 7
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.11.23 NATIVE GO-LIVE TESTS PASSED: {0}".format(len(tests)))


if __name__ == "__main__":
    main()
