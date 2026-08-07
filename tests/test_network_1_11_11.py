#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import shutil
import stat
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.product import config_migrations
from modules.product import configurator


def _version_key(value):
    return tuple(int(part) for part in value.strip().split("."))


def _tmp_config(text):
    root = tempfile.mkdtemp(prefix="network-1-11-11-")
    path = os.path.join(root, "config.yml")
    with open(path, "w") as handle:
        handle.write(text)
    os.chmod(path, 0o600)
    return root, path


def _legacy_config():
    return """netbox:\n  url: https://inventory.example:8080\n  token: SECRET-PRESERVED\n  verify_ssl: true\n\ntenant: MIZU\n\ndiscovery:\n  site: FBA\n  networks_file: /opt/netbox-discovery/config/sites/FBA/networks.conf\n\nproduct:\n  execution_role: network_proxy\n"""


def test_01_legacy_config_gets_safe_automation_defaults():
    root, path = _tmp_config(_legacy_config())
    try:
        changed = config_migrations.ensure_network_automation(path)
        assert changed is True
        cfg = configurator.parse_simple_yaml(path)
        assert cfg["automation"]["enabled"] is False
        assert cfg["automation"]["apply"] is False
        assert cfg["automation"]["schedule"] == "daily"
        text = open(path, "r").read()
        assert "SECRET-PRESERVED" in text
        assert text.count("automation:") == 1
        assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    finally:
        shutil.rmtree(root)


def test_02_migration_is_idempotent():
    root, path = _tmp_config(_legacy_config())
    try:
        assert config_migrations.ensure_network_automation(path) is True
        first = open(path, "r").read()
        assert config_migrations.ensure_network_automation(path) is False
        second = open(path, "r").read()
        assert first == second
        assert second.count("automation:") == 1
    finally:
        shutil.rmtree(root)


def test_03_existing_values_are_preserved_and_missing_key_is_added():
    text = _legacy_config() + "\nautomation:\n  enabled: true\n  schedule: *-*-* 03:00:00\n"
    root, path = _tmp_config(text)
    try:
        assert config_migrations.ensure_network_automation(path) is True
        cfg = configurator.parse_simple_yaml(path)
        assert cfg["automation"]["enabled"] is True
        assert cfg["automation"]["apply"] is False
        assert cfg["automation"]["schedule"] == "*-*-* 03:00:00"
    finally:
        shutil.rmtree(root)


def test_04_existing_apply_true_is_not_silently_overwritten():
    text = _legacy_config() + "\nautomation:\n  enabled: false\n  apply: true\n  schedule: weekly\n"
    root, path = _tmp_config(text)
    try:
        assert config_migrations.ensure_network_automation(path) is False
        cfg = configurator.parse_simple_yaml(path)
        assert cfg["automation"]["apply"] is True
        assert cfg["automation"]["schedule"] == "weekly"
    finally:
        shutil.rmtree(root)


def test_05_malformed_automation_fails_closed():
    text = _legacy_config() + "\nautomation: enabled\n"
    root, path = _tmp_config(text)
    try:
        try:
            config_migrations.ensure_network_automation(path)
        except RuntimeError as exc:
            assert "seção automation inválida" in str(exc)
        else:
            raise AssertionError("malformed automation must fail closed")
    finally:
        shutil.rmtree(root)


def test_06_installer_runs_migration_before_product_check():
    source = open(os.path.join(ROOT, "install.sh"), "r").read()
    migration = source.index("config_migrations.py")
    current_check = source.rfind("/usr/local/bin/netbox-discovery check")
    legacy_check = source.rfind('"$TARGET/bin/netbox-discovery" check')
    product_check = max(current_check, legacy_check)
    assert product_check >= 0
    assert migration < product_check
    assert "--ensure-network-automation" in source


def test_07_current_scheduler_command_can_toggle_migrated_config():
    cli = open(os.path.join(BASE, "bin", "netbox-discovery"), "r").read()
    assert "automation.enabled não encontrado" in cli
    root, path = _tmp_config(_legacy_config())
    try:
        config_migrations.ensure_network_automation(path)
        rows = open(path, "r").read().splitlines()
        assert any(row.strip() == "enabled: false" for row in rows)
        in_auto = False
        found = False
        for row in rows:
            stripped = row.strip()
            indent = len(row) - len(row.lstrip())
            if indent == 0 and stripped.endswith(":"):
                in_auto = stripped == "automation:"
            if in_auto and indent > 0 and stripped.startswith("enabled:"):
                found = True
        assert found
    finally:
        shutil.rmtree(root)


def test_08_release_version_is_at_least_scheduler_migration():
    root_version = open(os.path.join(ROOT, "VERSION"), "r").read().strip()
    package_version = open(os.path.join(BASE, "VERSION"), "r").read().strip()
    assert root_version == package_version
    assert _version_key(root_version) >= _version_key("1.11.11")


def main():
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    assert len(tests) >= 8
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.11.11 SCHEDULER MIGRATION TESTS PASSED: {0}".format(len(tests)))


if __name__ == "__main__":
    main()
