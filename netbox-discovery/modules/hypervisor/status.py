#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import glob
import json
import os
import sys

BASE = os.environ.get("NETBOX_DISCOVERY_BASE", "/opt/netbox-discovery")
REPORTS = os.path.join(BASE, "reports")
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.hypervisor.config import load_hypervisor_config


def latest(pattern):
    rows = glob.glob(os.path.join(REPORTS, pattern))
    return max(rows, key=os.path.getmtime) if rows else ""


def load(path):
    if not path:
        return {}
    try:
        with open(path, "r") as handle:
            return json.load(handle)
    except Exception:
        return {}


def main():
    version = "?"
    try:
        version = open(os.path.join(BASE, "VERSION"), "r").read().strip()
    except Exception:
        pass
    try:
        from lib.config import load_config
        cfg = load_config()
        hv = load_hypervisor_config(required=False)
    except Exception as exc:
        print("netbox-discovery {0}".format(version))
        print("HYPERVISOR CONFIG: ERRO - {0}".format(exc))
        return 1
    site = str((cfg.get("discovery") or {}).get("site") or "")
    tenant = str(cfg.get("tenant") or "")
    sources = hv.get("sources") or []
    auto = hv.get("automation") or {}
    run = load(latest("{0}-hypervisor-run-*.json".format(site)))
    discovery = load(latest("{0}-hypervisor-discovery-*.json".format(site)))
    plan = load(latest("{0}-hypervisor-plan-*.json".format(site)))
    audit = load(latest("{0}-hypervisor-audit-*.json".format(site)))

    print("===== NETBOX-DISCOVERY HYPERVISOR STATUS =====")
    print("Versão: {0}".format(version))
    print("Tenant/Site: {0}/{1}".format(tenant, site))
    print("Sources: {0} ({1} habilitada(s))".format(len(sources), len([x for x in sources if x.get("enabled", True)])))
    for row in sources:
        print("  {0} | {1} | {2} | scope={3}".format(row.get("id"), row.get("type"), row.get("endpoint"), row.get("scope_mode", "site_networks")))
    print("Scheduler config: {0} | APPLY: {1} | {2}".format(
        "ENABLED" if auto.get("enabled") else "DISABLED",
        "SIM" if auto.get("apply") else "NÃO",
        auto.get("schedule") or "daily",
    ))
    print("Último RUN: {0}".format(run.get("status", "SEM EXECUÇÃO")))
    if discovery:
        results = discovery.get("results") or []
        print("DISCOVER: hosts={0} VMs={1} clusters={2}".format(
            sum(len(x.get("hosts") or []) for x in results),
            sum(len(x.get("vms") or []) for x in results),
            sum(len(x.get("clusters") or []) for x in results),
        ))
    else:
        print("DISCOVER: sem relatório")
    if plan:
        ds = plan.get("decision_summary") or {}
        ra = plan.get("ready_action_summary") or {}
        print("PLAN: READY={0} REVIEW={1} BLOCKED={2}".format(ds.get("READY", 0), ds.get("REVIEW", 0), ds.get("BLOCKED", 0)))
        print("      READY/CREATE={0} READY/UPDATE_SAFE={1} READY/NOOP={2}".format(ra.get("CREATE", 0), ra.get("UPDATE_SAFE", 0), ra.get("NOOP", 0)))
    else:
        print("PLAN: sem relatório")
    if audit:
        sm = audit.get("summary") or {}
        print("AUDIT: {0} | PASS={1} WARN={2} FAIL={3}".format(audit.get("status", ""), sm.get("PASS", 0), sm.get("WARN", 0), sm.get("FAIL", 0)))
    else:
        print("AUDIT: sem relatório")
    return 0


if __name__ == "__main__":
    sys.exit(main())
