#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.discovery import network_v6
from modules.product import selftest


def test_01_cli_check_reports_discovery_v6():
    source = open(os.path.join(BASE, "bin", "netbox-discovery"), "r").read()
    assert "DISCOVER V6: OK" in source
    assert "DISCOVER V5: OK" not in source


def test_02_cli_direct_discover_routes_to_v6():
    source = open(os.path.join(BASE, "bin", "netbox-discovery"), "r").read()
    assert 'discover) exec "$PYTHON" "$BASE/modules/discovery/network_v6.py"' in source
    assert 'discover) exec "$PYTHON" "$BASE/modules/discovery/network_v5.py"' not in source


def test_03_selftest_requires_v6_and_validates_component_version():
    source = open(os.path.join(BASE, "modules", "product", "selftest.py"), "r").read()
    assert 'modules/discovery/network_v6.py' in source
    assert "from modules.discovery import network_v6 as d" in source
    assert "assert d.DISCOVERY_WRAPPER_VERSION == '4.6-product'" in source
    assert network_v6.DISCOVERY_WRAPPER_VERSION == "4.6-product"


def test_04_selftest_passes_with_current_package():
    version, errors = selftest.check(BASE, ROOT)
    assert version == "1.11.13"
    assert errors == [], errors


def test_05_release_version():
    assert open(os.path.join(ROOT, "VERSION"), "r").read().strip() == "1.11.13"
    assert open(os.path.join(BASE, "VERSION"), "r").read().strip() == "1.11.13"


def main():
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    assert len(tests) >= 5
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.11.13 V6 ENTRYPOINT TESTS PASSED: {0}".format(len(tests)))


if __name__ == "__main__":
    main()
