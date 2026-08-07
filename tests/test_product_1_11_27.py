#!/usr/bin/env python3
import os
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
sys.path.insert(0, BASE)

from modules.product import config_migrations


OLD_URL = "https://inventory.bkpcloud.app.br:8080"
NEW_URL = "https://inventory.bkpcloud.app.br"


def write_config(path, url_line):
    with open(path, "w") as handle:
        handle.write(
            "netbox:\n"
            "  {0}\n"
            "  verify_ssl: false\n"
            "tenant: MIZU\n"
            "discovery:\n"
            "  site: FAB\n"
            "automation:\n"
            "  enabled: true\n"
            "  apply: false\n"
            "  schedule: daily\n".format(url_line)
        )


def test_exact_old_url_is_migrated_and_other_config_is_preserved():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "config.yml")
        write_config(path, "url: " + OLD_URL)
        before_mode = os.stat(path).st_mode & 0o777

        changed = config_migrations.migrate_netbox_url(path)
        text = open(path, "r").read()

        assert changed is True
        assert "url: " + NEW_URL in text
        assert OLD_URL not in text
        assert "verify_ssl: false" in text
        assert "tenant: MIZU" in text
        assert "site: FAB" in text
        assert "enabled: true" in text
        assert "apply: false" in text
        assert (os.stat(path).st_mode & 0o777) == before_mode
        assert config_migrations.migrate_netbox_url(path) is False


def test_quoted_exact_old_url_is_migrated_preserving_quotes():
    for quote in ('"', "'"):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "config.yml")
            write_config(path, "url: {0}{1}{0}".format(quote, OLD_URL))
            assert config_migrations.migrate_netbox_url(path) is True
            text = open(path, "r").read()
            assert "url: {0}{1}{0}".format(quote, NEW_URL) in text


def test_unrelated_url_is_never_changed():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "config.yml")
        other = "https://netbox.customer.example:8080"
        write_config(path, "url: " + other)
        original = open(path, "r").read()

        assert config_migrations.migrate_netbox_url(path) is False
        assert open(path, "r").read() == original


def test_old_url_outside_netbox_section_is_never_changed():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "config.yml")
        with open(path, "w") as handle:
            handle.write("notes:\n  url: {0}\nnetbox:\n  url: https://inventory.example\n".format(OLD_URL))
        original = open(path, "r").read()

        assert config_migrations.migrate_netbox_url(path) is False
        assert open(path, "r").read() == original


def main():
    tests = [
        test_exact_old_url_is_migrated_and_other_config_is_preserved,
        test_quoted_exact_old_url_is_migrated_preserving_quotes,
        test_unrelated_url_is_never_changed,
        test_old_url_outside_netbox_section_is_never_changed,
    ]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.11.27 NETBOX URL MIGRATION TESTS PASSED")


if __name__ == "__main__":
    main()
