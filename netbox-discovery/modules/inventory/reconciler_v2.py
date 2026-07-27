#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("NETBOX_DISCOVERY_BASE", os.path.abspath(os.path.join(HERE, "..", "..")))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import reconciler as base

RECONCILER_VERSION = "3.0-product"
ORIG_IDENTITY_SETS = base.identity_sets


def identity_sets(record):
    """Use only the authoritative management MAC as strong MAC identity.

    Secondary/interface MACs remain evidence in CLASSIFY, but cannot merge two
    independent physical assets merely because an auxiliary MAC overlaps.
    """
    serial = base.norm_serial(record.get("serial"))
    macs = set()
    management = base.norm_mac(record.get("management_mac"))
    if management:
        macs.add(management)
    chassis = base.norm_chassis(record.get("snmp_lldp_chassis_id"))
    return serial, macs, chassis


def main(argv=None):
    old_identity = base.identity_sets
    old_version = base.RECONCILER_VERSION
    try:
        base.identity_sets = identity_sets
        base.RECONCILER_VERSION = RECONCILER_VERSION
        return base.main(argv)
    finally:
        base.identity_sets = old_identity
        base.RECONCILER_VERSION = old_version


if __name__ == "__main__":
    sys.exit(main())
