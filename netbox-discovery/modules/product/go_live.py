#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import glob
import json
import os
import subprocess
import sys

BASE = os.environ.get("NETBOX_DISCOVERY_BASE", "/opt/netbox-discovery")
CORE = os.path.join(BASE, "bin", "netbox-discovery")
PENDING_ACTIONS = {"CREATE", "UPDATE_SAFE", "REPAIR_SAFE_VM_DUPLICATE"}


def run(*args):
    cmd = [CORE] + list(args)
    print("\n===== GO-LIVE: {0} =====".format(" ".join(args)))
    subprocess.check_call(cmd)


def latest_plan():
    files = glob.glob(os.path.join(BASE, "reports", "*-plan-*.json"))
    files = [path for path in files if "plan-summary" not in os.path.basename(path)]
    if not files:
        raise RuntimeError("nenhum PLAN JSON encontrado após a validação")
    return max(files, key=os.path.getmtime)


def validate_convergence():
    path = latest_plan()
    with open(path, "r") as handle:
        payload = json.load(handle)
    pending = []
    for record in payload.get("records", []):
        decision = str(record.get("decision") or "").strip().upper()
        action = str(record.get("action") or "").strip().upper()
        if decision == "READY" and action in PENDING_ACTIONS:
            pending.append(record)
    if pending:
        print("CONVERGÊNCIA: BLOQUEADA — {0} mudança(s) READY pendente(s)".format(len(pending)))
        for row in pending[:20]:
            print("  - {0} | {1} | {2}".format(
                row.get("ip") or row.get("address") or "SEM IP",
                row.get("desired_name") or row.get("name") or "SEM NOME",
                row.get("action") or "SEM AÇÃO",
            ))
        raise RuntimeError("GO-LIVE interrompido antes de habilitar o scheduler")
    print("CONVERGÊNCIA: PASS")
    print("PLAN VALIDADO: {0}".format(path))


def verify_safe_scheduler():
    if BASE not in sys.path:
        sys.path.insert(0, BASE)
    from lib.config import load_config
    cfg = load_config()
    automation = cfg.get("automation") or {}
    enabled = bool(automation.get("enabled", False))
    apply_mode = bool(automation.get("apply", False))
    if not enabled or apply_mode:
        try:
            run("scheduler", "disable")
        finally:
            raise RuntimeError(
                "estado inseguro após habilitação: enabled={0} apply={1}".format(enabled, apply_mode)
            )
    print("SCHEDULER NETWORK: ENABLED")
    print("APPLY AUTOMÁTICO: NÃO")


def main():
    if os.geteuid() != 0:
        raise RuntimeError("execute como root")
    if not os.path.isfile(CORE):
        raise RuntimeError("comando principal não encontrado: {0}".format(CORE))

    print("===== NETBOX-DISCOVERY GO-LIVE =====")
    print("Fluxo: IMPORT -> AUDIT -> PLAN -> CONVERGÊNCIA -> APPLY=NÃO -> SCHEDULER")

    run("import", "--apply")
    run("audit")
    run("plan")
    run("plan", "summary")
    validate_convergence()

    # Preserva Tenant, Site, token, redes, exclusões e comunidades existentes.
    # Força somente os campos de automação para o estado seguro.
    run("configure", "--non-interactive", "--no-automation", "--no-auto-apply", "--skip-test")
    run("scheduler", "enable")
    verify_safe_scheduler()
    run("status")

    print("\nGO-LIVE: PASS")
    print("SCHEDULER HABILITADO COM APPLY=NÃO")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as exc:
        print("GO-LIVE: FALHOU no comando com retorno {0}".format(exc.returncode), file=sys.stderr)
        sys.exit(exc.returncode or 1)
    except Exception as exc:
        print("GO-LIVE: FALHOU — {0}".format(exc), file=sys.stderr)
        sys.exit(1)
