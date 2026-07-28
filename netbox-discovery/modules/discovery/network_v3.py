#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import sys

from modules.discovery import network_v2 as v2

DISCOVERY_WRAPPER_VERSION = "4.2-product"
ORIG_FA_PROBE = v2.probe_snmp_fa_connectivity


def probe_snmp_fa_connectivity(ip, snmp):
    """Retry safe/read-only FA-MIB discovery to reduce transient identity loss.

    A missing SNMP walk must never be treated as evidence that a previously
    identified storage array stopped being that array. This wrapper only
    retries GET-like SNMP reads; it performs no write to the device.
    """
    last = {"primary": {}, "units": [], "count": 0}
    for _attempt in range(3):
        last = ORIG_FA_PROBE(ip, snmp)
        if (last.get("primary") or {}).get("conn_unit_id"):
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
