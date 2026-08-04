#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import argparse
import glob
import json
import os
import re
import subprocess
import sys

BASE = os.environ.get("NETBOX_DISCOVERY_BASE", "/opt/netbox-discovery")
REPORTS = os.path.join(BASE, "reports")
HERE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.inventory import pipeline_legacy as legacy

PIPELINE_VERSION = "3.3-product"

print_plan_diagnostics = legacy.print_plan_diagnostics


def clean(value):
    return "" if value is None else str(value).strip()


def _load_json(path):
    try:
        with open(path, "r") as handle:
            return json.load(handle)
    except Exception:
        return {}


def _same_path(left, right):
    if not clean(left) or not clean(right):
        return False
    return os.path.realpath(clean(left)) == os.path.realpath(clean(right))


def _timestamp_key(path):
    match = re.search(r"-(\d{8}-\d{6})\.json$", os.path.basename(path))
    return match.group(1) if match else ""


def _configured_site():
    try:
        from lib.config import load_config
        cfg = load_config()
        return clean((cfg.get("discovery") or {}).get("site"))
    except Exception:
        return ""


def _valid_discovery(path, site):
    data = _load_json(path)
    if not isinstance(data.get("devices"), list):
        return False
    if site and clean(data.get("site")).casefold() != site.casefold():
        return False
    return True


def latest_discovery(output_dir, site=""):
    pattern = "{0}-discovery-*.json".format(site) if site else "*-discovery-*.json"
    candidates = [
        path for path in glob.glob(os.path.join(output_dir, pattern))
        if _valid_discovery(path, site)
    ]
    if not candidates:
        raise RuntimeError("Nenhum discovery JSON válido encontrado para o site {0}".format(site or "configurado"))
    return max(candidates, key=lambda path: (_timestamp_key(path), os.path.getmtime(path)))


def linked_report(output_dir, stage, expected):
    pattern = os.path.join(output_dir, "*-{0}-*.json".format(stage))
    matches = []
    for path in glob.glob(pattern):
        data = _load_json(path)
        if not data:
            continue
        ok = True
        for key, source in expected.items():
            if not _same_path(data.get(key), source):
                ok = False
                break
        if ok:
            matches.append(path)
    if not matches:
        details = ", ".join("{0}={1}".format(key, value) for key, value in sorted(expected.items()))
        raise RuntimeError("{0} terminou sem gerar relatório vinculado: {1}".format(stage.upper(), details))
    return max(matches, key=lambda path: (_timestamp_key(path), os.path.getmtime(path)))


def main(argv=None):
    parser = argparse.ArgumentParser(description="netbox-discovery inventory pipeline vinculado")
    parser.add_argument("--input", default="", help="Discovery JSON; por padrão usa o último relatório válido do site")
    parser.add_argument("--output-dir", default=REPORTS)
    args = parser.parse_args(argv)

    site = _configured_site()
    discovery = clean(args.input) or latest_discovery(args.output_dir, site)
    if not os.path.isfile(discovery) or not _valid_discovery(discovery, site):
        raise RuntimeError("Discovery JSON inválido ou de outro site: {0}".format(discovery))

    classifier = os.path.join(HERE, "classifier_v8.py")
    reconciler = os.path.join(HERE, "reconciler_v5.py")
    planner = os.path.join(HERE, "planner_v10.py")

    print("===== INVENTORY SOURCE =====")
    print("Discovery selecionado: {0}".format(discovery))
    print("Política: vínculo obrigatório entre DISCOVER, CLASSIFY, RECONCILE e PLAN")

    subprocess.check_call([
        sys.executable, classifier, "--input", discovery,
        "--output-dir", args.output_dir,
    ])
    classification = linked_report(
        args.output_dir, "classification", {"source_discovery": discovery}
    )

    subprocess.check_call([
        sys.executable, reconciler, "--input", classification,
        "--output-dir", args.output_dir,
    ])
    reconciliation = linked_report(
        args.output_dir, "reconciliation", {"source_classification": classification}
    )

    subprocess.check_call([
        sys.executable, planner, "--input", reconciliation,
        "--classification", classification,
        "--output-dir", args.output_dir,
    ])
    plan = linked_report(
        args.output_dir,
        "plan",
        {
            "source_reconciliation": reconciliation,
            "source_classification": classification,
        },
    )

    print_plan_diagnostics(plan, classification)
    print("===== INVENTORY PIPELINE =====")
    print("Pipeline version: {0}".format(PIPELINE_VERSION))
    print("DISCOVERY: {0}".format(discovery))
    print("CLASSIFICATION: {0}".format(classification))
    print("RECONCILIATION: {0}".format(reconciliation))
    print("PLAN: {0}".format(plan))
    print("CLASSIFY V8: OK")
    print("RECONCILE V5: OK")
    print("PLAN V10: OK")
    print("NetBox write: NÃO")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("ERRO: {0}".format(exc), file=sys.stderr)
        sys.exit(1)
