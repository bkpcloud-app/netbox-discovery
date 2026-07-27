#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import argparse
import datetime
import fcntl
import json
import os
import sys

BASE = os.environ.get("NETBOX_DISCOVERY_BASE", "/opt/netbox-discovery")
REPORTS = os.path.join(BASE, "reports")
LOCK_FILE = "/var/lock/netbox-discovery-global.lock"
RUNNER_VERSION = "2.1-product"

if BASE not in sys.path:
    sys.path.insert(0, BASE)

from lib.netbox import NetBox as RealNetBox
from modules.hypervisor.config import load_hypervisor_config
from modules.hypervisor import engine

WRITE_JOURNAL = []


class TracingNetBox(RealNetBox):
    def post(self, endpoint, data):
        obj = super(TracingNetBox, self).post(endpoint, data)
        WRITE_JOURNAL.append({"method": "POST", "endpoint": endpoint, "object_id": (obj or {}).get("id") if isinstance(obj, dict) else None})
        return obj

    def patch(self, endpoint, data):
        obj = super(TracingNetBox, self).patch(endpoint, data)
        WRITE_JOURNAL.append({"method": "PATCH", "endpoint": endpoint, "object_id": (obj or {}).get("id") if isinstance(obj, dict) else None})
        return obj


engine.NetBox = TracingNetBox


def plan_issue_lines(plan):
    records = (plan or {}).get("records") or []
    issues = [row for row in records if row.get("decision") in ("REVIEW", "BLOCKED")]
    lines = []
    if not issues:
        return ["HYPERVISOR PENDÊNCIAS: nenhuma"]

    lines.append("===== HYPERVISOR PENDÊNCIAS DO PLAN =====")
    for pos, row in enumerate(issues, 1):
        name = row.get("desired_name") or row.get("name") or row.get("prefix") or row.get("asset_id") or "?"
        lines.append("[{0}/{1}] {2} | {3} | {4} | {5}".format(
            pos,
            len(issues),
            row.get("decision") or "?",
            row.get("object_type") or "?",
            name,
            row.get("action") or "?",
        ))
        lines.append("  Motivo: {0}".format(row.get("reason") or "não informado"))
    lines.append("PENDÊNCIAS TOTAIS: {0}".format(len(issues)))
    return lines


def print_plan_issues(plan):
    for line in plan_issue_lines(plan):
        print(line)


def write_run(site, apply_mode, status, discovery_path, plan_path, import_path="", audit_path="", error=""):
    if not os.path.isdir(REPORTS):
        os.makedirs(REPORTS)
    stamp = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(REPORTS, "{0}-hypervisor-run-{1}.json".format(site or "SITE", stamp))
    with open(path, "w") as handle:
        json.dump({
            "stage": "HYPERVISOR_RUN", "runner_version": RUNNER_VERSION,
            "generated_at": engine.utc_now(), "status": status,
            "apply_requested": bool(apply_mode), "site": site,
            "discovery": discovery_path, "plan": plan_path,
            "import": import_path, "audit": audit_path, "error": error,
            "writes_completed": len(WRITE_JOURNAL),
            "last_write": WRITE_JOURNAL[-1] if WRITE_JOURNAL else None,
            "netbox_write": bool(import_path or WRITE_JOURNAL),
        }, handle, indent=2, sort_keys=True)
    print("HYPERVISOR RUN REPORT: {0}".format(path))
    return path


def write_failed_import(site, discovery_path, plan_path, error):
    if not WRITE_JOURNAL:
        return ""
    if not os.path.isdir(REPORTS):
        os.makedirs(REPORTS)
    stamp = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(REPORTS, "{0}-hypervisor-import-failed-{1}.json".format(site or "SITE", stamp))
    with open(path, "w") as handle:
        json.dump({
            "stage": "HYPERVISOR_IMPORT", "status": "FAILED",
            "generated_at": engine.utc_now(), "site": site,
            "discovery": discovery_path, "plan": plan_path,
            "writes_completed": len(WRITE_JOURNAL), "writes": WRITE_JOURNAL,
            "error": str(error), "netbox_write": True,
        }, handle, indent=2, sort_keys=True)
    print("HYPERVISOR FAILED IMPORT REPORT: {0}".format(path))
    return path


def execute(apply_mode):
    del WRITE_JOURNAL[:]
    lock = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        raise RuntimeError("outro processo netbox-discovery (Network/Hypervisor/Update) já está em execução")
    lock.write("hypervisor:{0}".format(os.getpid()))
    lock.flush()

    discovery = None
    discovery_path = ""
    plan = None
    plan_path = ""
    import_path = ""
    audit_path = ""
    site = ""
    try:
        discovery, discovery_path = engine.collect_all()
        site = discovery.get("site") or "SITE"
        plan, plan_path = engine.build_plan(discovery)
        print_plan_issues(plan)
        if not apply_mode:
            print("HYPERVISOR IMPORT NÃO EXECUTADO: use 'netbox-discovery hypervisor run --apply' para escrita real.")
            write_run(site, False, "PLAN_READY", discovery_path, plan_path)
            return 0

        import_path = engine.apply_plan(discovery, plan)
        status, audit_path = engine.audit(discovery, plan)
        write_run(site, True, status, discovery_path, plan_path, import_path, audit_path)
        return 0 if status != "FAIL" else 1
    except Exception as exc:
        if apply_mode:
            failed_path = write_failed_import(site or "SITE", discovery_path, plan_path, exc)
            if failed_path and not import_path:
                import_path = failed_path
        write_run(site or "SITE", apply_mode, "FAIL", discovery_path, plan_path, import_path, audit_path, str(exc))
        raise


def scheduled():
    cfg = load_hypervisor_config(required=True)
    auto = cfg.get("automation") or {}
    if not bool(auto.get("enabled", False)):
        print("HYPERVISOR AUTOMAÇÃO DESABILITADA: nenhuma execução iniciada.")
        return 0
    apply_mode = bool(auto.get("apply", False))
    print("HYPERVISOR AUTOMAÇÃO: habilitada | APPLY: {0}".format("SIM" if apply_mode else "NÃO"))
    return execute(apply_mode)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pipeline independente de virtualização do netbox-discovery")
    ap.add_argument("--apply", action="store_true", help="habilita escrita READY no NetBox")
    ap.add_argument("--scheduled", action="store_true", help="usa automation.enabled/apply do hypervisors.json")
    args = ap.parse_args(argv)
    if args.scheduled:
        return scheduled()
    return execute(args.apply)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("ERRO: {0}".format(exc), file=sys.stderr)
        sys.exit(1)
