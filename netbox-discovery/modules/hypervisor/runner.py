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
RUNNER_VERSION = "3.2-product"

if BASE not in sys.path:
    sys.path.insert(0, BASE)

from lib.netbox import NetBox as RealNetBox
from modules.hypervisor.config import load_hypervisor_config
from modules.hypervisor import engine_v3 as engine

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
engine.v2.NetBox = TracingNetBox
engine.v2.base.NetBox = TracingNetBox
engine.base.NetBox = TracingNetBox


def _target_label(row):
    tenant = row.get("target_tenant") or "?"
    site = row.get("target_site") or "?"
    return "{0}/{1}".format(tenant, site)


def _row_name(row):
    return row.get("desired_name") or row.get("name") or row.get("prefix") or row.get("asset_id") or "?"


def plan_issue_lines(plan):
    records = (plan or {}).get("records") or []
    issues = [row for row in records if row.get("decision") in ("REVIEW", "BLOCKED")]
    creates = [row for row in records if row.get("decision") == "READY" and row.get("action") == "CREATE"]
    residuals = [row for row in records if row.get("decision") == "READY" and row.get("action") in ("UPDATE_SAFE", "RECLASSIFY_SAFE")]
    lines = []

    if not issues and not creates and not residuals:
        return ["HYPERVISOR PENDÊNCIAS/AÇÕES READY: nenhum"]

    if issues:
        lines.append("===== HYPERVISOR PENDÊNCIAS DO PLAN =====")
        for pos, row in enumerate(issues, 1):
            lines.append("[{0}/{1}] {2} | {3} | {4} | {5} | alvo={6}".format(
                pos, len(issues), row.get("decision") or "?", row.get("object_type") or "?",
                _row_name(row), row.get("action") or "?", _target_label(row),
            ))
            lines.append("  Motivo: {0}".format(row.get("reason") or "não informado"))
        lines.append("PENDÊNCIAS TOTAIS: {0}".format(len(issues)))

    if creates:
        lines.append("===== HYPERVISOR NOVOS OBJETOS READY =====")
        for pos, row in enumerate(creates, 1):
            lines.append("[{0}/{1}] READY | {2} | {3} | CREATE | alvo={4}".format(
                pos, len(creates), row.get("object_type") or "?", _row_name(row), _target_label(row)
            ))
            if row.get("reason"):
                lines.append("  Motivo: {0}".format(row.get("reason")))
        lines.append("NOVOS OBJETOS READY: {0}".format(len(creates)))

    if residuals:
        lines.append("===== HYPERVISOR AJUSTES/MIGRAÇÕES SEGURAS PENDENTES =====")
        for pos, row in enumerate(residuals, 1):
            action = row.get("action") or "?"
            lines.append("[{0}/{1}] READY | {2} | {3} | {4} | alvo={5}".format(
                pos, len(residuals), row.get("object_type") or "?", _row_name(row), action, _target_label(row)
            ))
            detail = row.get("pending_reason") or row.get("reason") or "ajuste seguro pendente"
            lines.append("  Motivo: {0}".format(detail))
            if row.get("migration_match"):
                lines.append("  Correspondência global: {0}".format(row.get("migration_match")))
            elif row.get("reason") and row.get("reason") != detail:
                lines.append("  Correspondência: {0}".format(row.get("reason")))
        lines.append("AJUSTES PENDENTES: {0}".format(len(residuals)))

    lines.append("===== RESUMO DE ESCRITA DO DRY-RUN =====")
    lines.append("CREATE READY: {0}".format(len(creates)))
    lines.append("UPDATE_SAFE/RECLASSIFY_SAFE READY: {0}".format(len(residuals)))
    lines.append("REVIEW/BLOCKED: {0}".format(len(issues)))
    lines.append("NetBox write: NÃO")
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
            "netbox_write": bool(WRITE_JOURNAL),
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
    site = "MULTI"
    try:
        discovery, discovery_path = engine.collect_all()
        contexts = discovery.get("contexts") or []
        if len(contexts) == 1:
            site = contexts[0].get("site") or "SITE"
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
            failed_path = write_failed_import(site or "MULTI", discovery_path, plan_path, exc)
            if failed_path and not import_path:
                import_path = failed_path
        write_run(site or "MULTI", apply_mode, "FAIL", discovery_path, plan_path, import_path, audit_path, str(exc))
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
