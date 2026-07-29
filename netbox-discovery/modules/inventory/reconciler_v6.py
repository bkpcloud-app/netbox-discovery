#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, "..", ".."))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.inventory import reconciler_v2 as v2
from modules.inventory import reconciler_v5 as v5

RECONCILER_VERSION = "3.4-product"
ORIG_CANDIDATE_REASON = v2.base.candidate_reason


def candidate_reason(a, b):
    """Do not flag two same-name assets as merge candidates when serials prove
    they are different physical devices.

    This lets PLAN apply its existing deterministic IP suffix instead of
    blocking independent switches that share a copied/default sysName.
    """
    serial_a = v2.base.norm_serial(a.get("serial"))
    serial_b = v2.base.norm_serial(b.get("serial"))
    if serial_a and serial_b and serial_a != serial_b:
        return "", 0
    return ORIG_CANDIDATE_REASON(a, b)


def main(argv=None):
    old_candidate = v2.base.candidate_reason
    old_version = v5.RECONCILER_VERSION
    try:
        v2.base.candidate_reason = candidate_reason
        v5.RECONCILER_VERSION = RECONCILER_VERSION
        return v5.main(argv)
    finally:
        v5.RECONCILER_VERSION = old_version
        v2.base.candidate_reason = old_candidate


if __name__ == "__main__":
    sys.exit(main())
