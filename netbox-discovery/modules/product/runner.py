#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import argparse
import datetime
import fcntl
import json
import glob
import os
import subprocess
import sys

BASE = os.environ.get("NETBOX_DISCOVERY_BASE", "/opt/netbox-discovery")
REPORTS = os.path.join(BASE, "reports")
LOCK_FILE = "/var/lock/netbox-discovery-run.lock"
RUNNER_VERSION = "1.0-product"


def utc_stamp():
    return datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")


def load_cfg():
    sys.path.insert(0, BASE)
    from lib.config import load_config
    return load_config()


def run_step(name, cmd, stages):
    started = datetime.datetime.utcnow().isoformat() + "Z"
    print("===== {0} =====".format(name))
    try:
        subprocess.check_call(cmd)
        stages.append({"stage": name, "status": "OK", "started": started,
                       "finished": datetime.datetime.utcnow().isoformat() + "Z"})
    except Exception as exc:
        stages.append({"stage": name, "status": "FAIL", "started": started,
                       "finished": datetime.datetime.utcnow().isoformat() + "Z",
                       "error": str(exc)})
        raise


def write_report(site, apply_mode, status, stages, error=""):
    if not os.path.isdir(REPORTS):
        os.makedirs(REPORTS)
    path = os.path.join(REPORTS, "{0}-run-{1}.json".format(site or "SITE", utc_stamp()))
    import_ok = any(x.get("stage") == "IMPORT" and x.get("status") == "OK" for x in stages)
    with open(path, "w") as f:
        json.dump({
            "stage": "RUN", "runner_version": RUNNER_VERSION,
            "status": status, "apply_requested": bool(apply_mode), "site": site,
            "stages": stages, "error": error, "netbox_write": bool(import_ok),
        }, f, indent=2, sort_keys=True)
    print("RUN REPORT: {0}".format(path))
    return path


def execute(apply_mode):
    lock = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        raise RuntimeError("netbox-discovery run já está em execução")
    lock.write(str(os.getpid()))
    lock.flush()

    cfg = load_cfg()
    site = str((cfg.get("discovery") or {}).get("site") or "SITE")
    py = sys.executable
    stages = []
    try:
        run_step("DISCOVER", [py, os.path.join(BASE, "modules/discovery/network.py")], stages)
        run_step("CLASSIFY_RECONCILE_PLAN", [py, os.path.join(BASE, "modules/inventory/pipeline.py")], stages)
        if apply_mode:
            run_step("IMPORT", [py, os.path.join(BASE, "modules/importers/importer.py"), "--apply"], stages)
            run_step("AUDIT", [py, os.path.join(BASE, "modules/auditors/inventory.py")], stages)
            audit_files = glob.glob(os.path.join(REPORTS, "{0}-audit-*.json".format(site)))
            status = "PASS"
            if audit_files:
                audit_path = max(audit_files, key=os.path.getmtime)
                try:
                    with open(audit_path, "r") as f:
                        status = json.load(f).get("status") or "PASS"
                except Exception:
                    status = "PASS"
        else:
            status = "PLAN_READY"
            print("IMPORT NÃO EXECUTADO: use 'netbox-discovery run --apply' para escrita real.")
        write_report(site, apply_mode, status, stages)
        return 0
    except Exception as exc:
        write_report(site, apply_mode, "FAIL", stages, str(exc))
        raise


def scheduled():
    cfg = load_cfg()
    auto = cfg.get("automation") or {}
    if not bool(auto.get("enabled", False)):
        print("AUTOMAÇÃO DESABILITADA: nenhuma execução iniciada.")
        return 0
    apply_mode = bool(auto.get("apply", False))
    print("AUTOMAÇÃO: habilitada | APPLY: {0}".format("SIM" if apply_mode else "NÃO"))
    return execute(apply_mode)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pipeline único netbox-discovery")
    ap.add_argument("--apply", action="store_true", help="habilita escrita READY no NetBox")
    ap.add_argument("--scheduled", action="store_true", help="usa automation.enabled/apply do config.yml")
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
