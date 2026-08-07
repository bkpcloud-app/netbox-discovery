#!/usr/bin/env python3
import os
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
sys.path.insert(0, BASE)

from lib import config as product_config

NEW_URL = "https://inventory.bkpcloud.app.br"
OLD_URL = "https://inventory.bkpcloud.app.br:8080"
OTHER_URL = "https://netbox.customer.example"


def write_config(path, url):
    with open(path, "w") as handle:
        handle.write(
            "netbox:\n"
            "  url: {0}\n"
            "  token: test-token\n"
            "  verify_ssl: false\n"
            "tenant: MIZU\n"
            "discovery:\n"
            "  site: DCM\n".format(url)
        )


def test_locked_url_is_public_https_443():
    assert product_config.LOCKED_NETBOX_URL == NEW_URL


def test_new_url_is_accepted_and_canonicalized():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "config.yml")
        write_config(path, NEW_URL + "/")
        cfg = product_config.load_config(path)
        assert cfg["netbox"]["url"] == NEW_URL
        assert cfg["netbox"]["token"] == "test-token"
        assert cfg["netbox"]["verify_ssl"] is False
        assert cfg["tenant"] == "MIZU"
        assert cfg["discovery"]["site"] == "DCM"


def assert_rejected(url):
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "config.yml")
        write_config(path, url)
        try:
            product_config.load_config(path)
        except RuntimeError as exc:
            message = str(exc)
            assert "Endpoint NetBox não autorizado" in message
            assert NEW_URL in message
            return
        raise AssertionError("URL não autorizada foi aceita: " + url)


def test_old_8080_url_is_rejected_after_migration():
    assert_rejected(OLD_URL)


def test_custom_url_is_rejected():
    assert_rejected(OTHER_URL)


def main():
    tests = [
        test_locked_url_is_public_https_443,
        test_new_url_is_accepted_and_canonicalized,
        test_old_8080_url_is_rejected_after_migration,
        test_custom_url_is_rejected,
    ]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.11.28 NETBOX HTTPS 443 LOCK TESTS PASSED")


if __name__ == "__main__":
    main()
