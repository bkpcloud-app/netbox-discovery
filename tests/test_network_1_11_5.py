#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
PLANNER = os.path.join(BASE, "modules", "inventory", "planner_v9.py")


def test_planner_runs_directly_outside_package_cwd():
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    temp = tempfile.mkdtemp(prefix="nbd-1-11-5-")
    try:
        output = subprocess.check_output(
            [sys.executable, PLANNER, "--help"],
            cwd=temp,
            env=env,
            stderr=subprocess.STDOUT,
        ).decode("utf-8", "replace")
        assert "planner" in output.casefold() or "usage" in output.casefold()
    finally:
        try:
            os.rmdir(temp)
        except OSError:
            pass


def main():
    tests = [test_planner_runs_directly_outside_package_cwd]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL NETWORK 1.11.5 PLANNER ENTRYPOINT REGRESSIONS PASSED")


if __name__ == "__main__":
    main()
