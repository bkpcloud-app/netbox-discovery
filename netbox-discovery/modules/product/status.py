#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import glob
import json
import os
import subprocess
import sys

BASE = os.environ.get("NETBOX_DISCOVERY_BASE", "/opt/netbox-discovery")
REPORTS = os.path.join(BASE, "reports")
UPDATE_STATE = "/var/lib/netbox-discovery/update-state.json"


def latest(pattern):
    rows = glob.glob(os.path.join(REPORTS, pattern))
    return max(rows, key=os.path.getmtime) if rows else ""


def load(path):
    if not path:
        return {}
    try:
        with open(path, "r") as handle:
            value = json.load(handle)
            return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def val(data, key, default=0):
    return (data or {}).get(key, default)


def enabled(unit):
    try:
        return subprocess.call(["systemctl", "is-enabled", "--quiet", unit]) == 0
    except Exception:
        return False


def execution_role(cfg):
    product = cfg.get("product") or {}
    virtualization = cfg.get("virtualization") or {}
    return str(product.get("execution_role") or cfg.get("execution_role") or "network_proxy"), str(
        virtualization.get("mode") or "centralized"
    )


def main():
    try:
        version = open(os.path.join(BASE, "VERSION"), "r").read().strip()
    except Exception:
        version = "?"

    update = load(UPDATE_STATE)
    print("===== NETBOX-DISCOVERY STATUS =====")
    print("Versão instalada: {0}".format(version))
    print("Canal de update: stable")
    print("Auto-update timer: {0}".format("ENABLED" if enabled("netbox-discovery-update.timer") else "DISABLED"))
    print("Versão disponível conhecida: {0}".format(update.get("available_version", "NÃO VERIFICADA")))
    print("Último update: {0}".format(update.get("last_status", "SEM HISTÓRICO")))
    if update.get("failed_version"):
        print("Versão em quarentena: {0} | rollback={1}".format(update.get("failed_version"), update.get("last_rollback", "")))

    config_path = os.path.join(BASE, "config.yml")
    if not os.path.isfile(config_path):
        print("CONFIG: ainda não criada")
        print("Network scheduler: DISABLED")
        print("Virtualização: CENTRALIZADA | coletor local NÃO REQUERIDO")
        return 0

    try:
        sys.path.insert(0, BASE)
        from lib.config import load_config
        cfg = load_config()
    except Exception as exc:
        print("CONFIG: ERRO - {0}".format(exc))
        return 1

    site = str((cfg.get("discovery") or {}).get("site") or "")
    tenant = str(cfg.get("tenant") or "")
    auto = cfg.get("automation") or {}
    role, virtualization_mode = execution_role(cfg)
    network_timer = enabled("netbox-discovery.timer")
    print("Tenant/Site: {0}/{1}".format(tenant, site))
    print("Função desta instalação: {0}".format(role))
    print("Inventário de virtualização: {0}".format(virtualization_mode.upper()))
    print("Network scheduler: config={0} systemd={1} APPLY={2}".format(
        "ENABLED" if auto.get("enabled") else "DISABLED",
        "ENABLED" if network_timer else "DISABLED",
        "SIM" if auto.get("apply") else "NÃO"))

    disc = load(latest("{0}-discovery-*.json".format(site)))
    recon = load(latest("{0}-reconciliation-*.json".format(site)))
    plan = load(latest("{0}-plan-*.json".format(site)))
    imp = load(latest("{0}-import-*.json".format(site)))
    audit = load(latest("{0}-audit-*.json".format(site)))
    run = load(latest("{0}-run-*.json".format(site)))

    print("Último Network RUN: {0}".format(run.get("status", "SEM EXECUÇÃO")))
    if run.get("run_id"):
        print("Run ID: {0}".format(run.get("run_id")))
    print("DISCOVER: {0}".format("{0} hosts".format(len(disc.get("devices") or [])) if disc else "sem relatório"))
    print("RECONCILE: {0}".format("{0} assets".format(recon.get("assets", len(recon.get("records") or []))) if recon else "sem relatório"))
    if plan:
        decisions = plan.get("decision_summary") or {}
        actions = plan.get("action_summary") or {}
        print("PLAN: READY={0} DELEGATED={1} REVIEW={2} BLOCKED={3}".format(
            val(decisions, "READY"), val(decisions, "DELEGATED"), val(decisions, "REVIEW"), val(decisions, "BLOCKED")))
        print("      CREATE={0} UPDATE_SAFE={1} NOOP={2}".format(
            val(actions, "CREATE"), val(actions, "UPDATE_SAFE"), val(actions, "NOOP")))
        records = plan.get("records") or []
        guard = next((row.get("write_guard") for row in records if row.get("write_guard")), {}) or {}
        if guard:
            print("WRITE GUARD: {0} | mudanças={1} ({2}%)".format(
                guard.get("status", "?"), guard.get("eligible_total", 0), guard.get("change_percent", 0)))
    else:
        print("PLAN: sem relatório")
    if imp:
        summary = imp.get("summary") or {}
        print("IMPORT: mode={0} processados={1} blocked={2} erros={3}".format(
            imp.get("mode", ""), val(summary, "assets_processed"), val(summary, "runtime_blocked"), val(summary, "errors")))
    else:
        print("IMPORT: sem relatório")
    if audit:
        assets = audit.get("asset_summary") or {}
        print("AUDIT: {0} | PASS={1} WARN={2} FAIL={3}".format(
            audit.get("status", ""), val(assets, "PASS"), val(assets, "WARN"), val(assets, "FAIL")))
    else:
        print("AUDIT: sem relatório")

    try:
        from modules.hypervisor.config import load_hypervisor_config
        hcfg = load_hypervisor_config(required=False)
        sources = hcfg.get("sources") or []
        hauto = hcfg.get("automation") or {}
        if sources:
            hrun = load(latest("{0}-hypervisor-run-*.json".format(site)))
            print("Hypervisor local sources: {0}".format(len(sources)))
            print("Hypervisor scheduler: config={0} systemd={1} APPLY={2}".format(
                "ENABLED" if hauto.get("enabled") else "DISABLED",
                "ENABLED" if enabled("netbox-discovery-hypervisor.timer") else "DISABLED",
                "SIM" if hauto.get("apply") else "NÃO"))
            print("Último Hypervisor RUN: {0}".format(hrun.get("status", "SEM EXECUÇÃO")))
        elif virtualization_mode.lower() == "centralized" or role == "network_proxy":
            print("Hypervisor local: NÃO REQUERIDO | inventário central consultado pelo NetBox")
        else:
            print("Hypervisor local: NÃO CONFIGURADO")
    except Exception as exc:
        if virtualization_mode.lower() == "centralized" or role == "network_proxy":
            print("Hypervisor local: NÃO REQUERIDO | inventário centralizado")
        else:
            print("Hypervisor: ERRO - {0}".format(exc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
