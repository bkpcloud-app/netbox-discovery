#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from modules.discovery import network_v2 as v2

DISCOVERY_WRAPPER_VERSION = "4.2-product"
ORIG_FA_PROBE = v2.probe_snmp_fa_connectivity


def probe_snmp_fa_connectivity(ip, snmp):
    """Retry safe/read-only FA-MIB discovery to reduce transient identity loss."""
    last = {"primary": {}, "units": [], "count": 0}
    for _attempt in range(3):
        last = ORIG_FA_PROBE(ip, snmp)
        primary = last.get("primary") or {}
        if primary.get("conn_unit_id") or primary.get("serial"):
            return last
    return last


def main():
    old_probe = v2.probe_snmp_fa_connectivity
    old_version = v2.DISCOVERY_WRAPPER_VERSION
    try:
        v2.probe_snmp_fa_connectivity = probe_snmp_fa_connectivity
        v2.DISCOVERY_WRAPPER_VERSION = DISCOVERY_WRAPPER_VERSION
        return v2.main()
    finally:
        v2.probe_snmp_fa_connectivity = old_probe
        v2.DISCOVERY_WRAPPER_VERSION = old_version


if __name__ == "__main__":
    sys.exit(main())
