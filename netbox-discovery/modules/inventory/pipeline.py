#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import argparse
import glob
import os
import subprocess
import sys

BASE = os.environ.get("NETBOX_DISCOVERY_BASE", "/opt/netbox-discovery")
REPORTS = os.path.join(BASE, "reports")
HERE = os.path.dirname(os.path.abspath(__file__))


def latest(pattern):
    files = glob.glob(pattern)
    return max(files, key=os.path.getmtime) if files else ""


def main(argv=None):
    ap = argparse.ArgumentParser(description="netbox-discovery inventory pipeline (CLASSIFY -> RECONCILE -> PLAN)")
    ap.add_argument("--input", default="", help="Discovery JSON; default is latest discovery report")
    ap.add_argument("--output-dir", default=REPORTS)
    args = ap.parse_args(argv)

    classifier = os.path.join(HERE, "classifier.py")
    reconciler = os.path.join(HERE, "reconciler.py")
    planner = os.path.join(HERE, "planner.py")

    cmd = [sys.executable, classifier, "--output-dir", args.output_dir]
    if args.input:
        cmd.extend(["--input", args.input])
    subprocess.check_call(cmd)

    classification = latest(os.path.join(args.output_dir, "*-classification-*.json"))
    if not classification:
        raise RuntimeError("CLASSIFY terminou sem gerar JSON")
    subprocess.check_call([sys.executable, reconciler, "--input", classification, "--output-dir", args.output_dir])

    reconciliation = latest(os.path.join(args.output_dir, "*-reconciliation-*.json"))
    if not reconciliation:
        raise RuntimeError("RECONCILE terminou sem gerar JSON")
    subprocess.check_call([
        sys.executable, planner,
        "--input", reconciliation,
        "--classification", classification,
        "--output-dir", args.output_dir,
    ])

    print("===== INVENTORY PIPELINE =====")
    print("CLASSIFY: OK")
    print("RECONCILE: OK")
    print("PLAN: OK")
    print("NetBox write: NÃO")
    return 0


if __name__ == "__main__":
    sys.exit(main())
