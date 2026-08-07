#!/usr/bin/env python3
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
sys.path.insert(0, BASE)

from lib import config as product_config
from modules.product import configurator

EXPECTED = "https://inventory.bkpcloud.app.br"


def main():
    assert product_config.LOCKED_NETBOX_URL == EXPECTED, product_config.LOCKED_NETBOX_URL
    assert configurator.LOCKED_NETBOX_URL == EXPECTED, configurator.LOCKED_NETBOX_URL
    assert ":8080" not in configurator.LOCKED_NETBOX_URL
    defaults = configurator.current_defaults()
    assert defaults["url"] == EXPECTED, defaults["url"]
    print("ALL 1.11.31 CONFIGURATOR HTTPS 443 TESTS PASSED")


if __name__ == "__main__":
    main()
