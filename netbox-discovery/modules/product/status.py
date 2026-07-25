#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import glob
import json
import os
import sys

BASE = os.environ.get("NETBOX_DISCOVERY_BASE", "/opt/netbox-discovery")
REPORTS = os.path.join(BASE, "reports")


def latest(pattern):
    rows = glob.glob(os.path.join(REPORTS, pattern))
    return max(rows, key=os.path.getmtime) if rows else ""


def load(path):
    if not path:
        return {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def val(d, key, default=0):
    return (d or {}).get(key, default)


def main():
    version = "?"
    try:
        version = open(os.path.join(BASE, "VERSION"), "r").read().strip()
    except Exception:
        pass
    try:
        sys.path.insert(0, BASE)
        from lib.config import load_config
        cfg = load_config()
    except Exception as exc:
        print("netbox-discovery {0}".format(version))
        print("CONFIG: ERRO - {0}".format(exc))
        return 1

    site = str((cfg.get("discovery") or {}).get("site") or "")
    tenant = str(cfg.get("tenant") or "")
    disc = load(latest("{0}-discovery-*.json".format(site)))
    recon = load(latest("{0}-reconciliation-*.json".format(site)))
    plan = load(latest("{0}-plan-*.json".format(site)))
    imp = load(latest("{0}-import-*.json".format(site)))
    audit = load(latest("{0}-audit-*.json".format(site)))
    run = load(latest("{0}-run-*.json".format(site)))

    print("===== NETBOX-DISCOVERY STATUS =====")
    print("Versão: {0}".format(version))
    print("Tenant/Site: {0}/{1}".format(tenant, site))
    print("Último RUN: {0}".format(run.get("status", "SEM EXECUÇÃO")))
    if disc:
        devices = disc.get("devices") or []
        print("DISCOVER: {0} hosts".format(len(devices)))
    else:
        print("DISCOVER: sem relatório")
    if recon:
        print("RECONCILE: {0} assets".format(recon.get("assets", len(recon.get("records") or []))))
    else:
        print("RECONCILE: sem relatório")
    if plan:
        ds = plan.get("decision_summary") or {}
        ac = plan.get("action_summary") or {}
        print("PLAN: READY={0} REVIEW={1} BLOCKED={2}".format(val(ds, "READY"), val(ds, "REVIEW"), val(ds, "BLOCKED")))
        print("      CREATE={0} UPDATE_SAFE={1} NOOP={2}".format(val(ac, "CREATE"), val(ac, "UPDATE_SAFE"), val(ac, "NOOP")))
    else:
        print("PLAN: sem relatório")
    if imp:
        sm = imp.get("summary") or {}
        print("IMPORT: mode={0} processados={1} blocked={2} erros={3}".format(
            imp.get("mode", ""), val(sm, "assets_processed"), val(sm, "runtime_blocked"), val(sm, "errors")))
    else:
        print("IMPORT: sem relatório")
    if audit:
        a = audit.get("asset_summary") or {}
        c = audit.get("check_summary") or {}
        print("AUDIT: {0} | PASS={1} WARN={2} FAIL={3}".format(
            audit.get("status", ""), val(a, "PASS"), val(a, "WARN"), val(a, "FAIL")))
        print("       checks FAIL={0}".format(val(c, "FAIL")))
    else:
        print("AUDIT: sem relatório")
    return 0


if __name__ == "__main__":
    sys.exit(main())
