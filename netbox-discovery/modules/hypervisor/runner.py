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
LOCK_FILE = "/var/lock/netbox-discovery-hypervisor-run.lock"
RUNNER_VERSION = "1.0-product"

if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.hypervisor.config import load_hypervisor_config
from modules.hypervisor.engine import audit, apply_plan, build_plan, collect_all, utc_now


def write_run(site, apply_mode, status, discovery_path, plan_path, import_path="", audit_path="", error=""):
    if not os.path.isdir(REPORTS):
        os.makedirs(REPORTS)
    stamp = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(REPORTS, "{0}-hypervisor-run-{1}.json".format(site or "SITE", stamp))
    with open(path, "w") as handle:
        json.dump({
            "stage": "HYPERVISOR_RUN",
            "runner_version": RUNNER_VERSION,
            "generated_at": utc_now(),
            "status": status,
            "apply_requested": bool(apply_mode),
            "site": site,
            "discovery": discovery_path,
            "plan": plan_path,
            "import": import_path,
            "audit": audit_path,
            "error": error,
            "netbox_write": bool(import_path),
        }, handle, indent=2, sort_keys=True)
    print("HYPERVISOR RUN REPORT: {0}".format(path))
    return path


def execute(apply_mode):
    lock = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        raise RuntimeError("netbox-discovery hypervisor run já está em execução")
    lock.write(str(os.getpid()))
    lock.flush()

    discovery = None
    discovery_path = ""
    plan = None
    plan_path = ""
    import_path = ""
    audit_path = ""
    site = ""
    try:
        discovery, discovery_path = collect_all()
        site = discovery.get("site") or "SITE"
        plan, plan_path = build_plan(discovery)
        if not apply_mode:
            print("HYPERVISOR IMPORT NÃO EXECUTADO: use 'netbox-discovery hypervisor run --apply' para escrita real.")
            write_run(site, False, "PLAN_READY", discovery_path, plan_path)
            return 0

        import_path = apply_plan(discovery, plan)
        status, audit_path = audit(discovery, plan)
        write_run(site, True, status, discovery_path, plan_path, import_path, audit_path)
        return 0 if status != "FAIL" else 1
    except Exception as exc:
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
