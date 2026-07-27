#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import argparse
import glob
import json
import os
import subprocess
import sys

BASE = os.environ.get("NETBOX_DISCOVERY_BASE", "/opt/netbox-discovery")
REPORTS = os.path.join(BASE, "reports")
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.product.selftest import check as selftest_check


def latest(pattern):
    rows = glob.glob(os.path.join(REPORTS, pattern))
    return max(rows, key=os.path.getmtime) if rows else ""


def load_json(path):
    try:
        with open(path, "r") as handle:
            value = json.load(handle)
            return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def timer_enabled(unit):
    try:
        return subprocess.call(["systemctl", "is-enabled", "--quiet", unit]) == 0
    except Exception:
        return False


def main(argv=None):
    ap = argparse.ArgumentParser(description="netbox-discovery health")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    result = {
        "status": "OK", "severity": 0, "version": "?",
        "product": "OK", "netbox": "UNCONFIGURED", "update": "OK",
        "network": "UNCONFIGURED", "hypervisor": "UNCONFIGURED", "problems": [],
    }

    version, errors = selftest_check(BASE)
    result["version"] = version or "?"
    if errors:
        result["product"] = "CRITICAL"
        result["severity"] = 2
        result["problems"].extend(errors)

    cfg = None
    config_path = os.path.join(BASE, "config.yml")
    if os.path.isfile(config_path):
        try:
            from lib.config import load_config
            from lib.netbox import NetBox
            cfg = load_config()
            NetBox().get("dcim/sites/?limit=1")
            result["netbox"] = "OK"
        except Exception as exc:
            result["netbox"] = "CRITICAL"
            result["severity"] = 2
            result["problems"].append("NetBox: {0}".format(exc))

    state = load_json("/var/lib/netbox-discovery/update-state.json")
    if state.get("last_status") == "FAILED":
        result["update"] = "WARNING"
        result["severity"] = max(result["severity"], 1)
        result["problems"].append("Update falhou para {0}; rollback={1}".format(
            state.get("failed_version", "?"), state.get("last_rollback", "?")))
    if not timer_enabled("netbox-discovery-update.timer"):
        result["update"] = "WARNING"
        result["severity"] = max(result["severity"], 1)
        result["problems"].append("Auto-update timer está desabilitado")

    if cfg is not None:
        site = str((cfg.get("discovery") or {}).get("site") or "")
        run = load_json(latest("{0}-run-*.json".format(site)))
        audit = load_json(latest("{0}-audit-*.json".format(site)))
        result["network"] = run.get("status", "SEM_EXECUCAO")
        if audit.get("status") == "FAIL" or run.get("status") == "FAIL":
            result["severity"] = 2
            result["problems"].append("Network último RUN/AUDIT falhou")
        elif audit.get("status") in ("PASS_WITH_WARNINGS",) or not run:
            result["severity"] = max(result["severity"], 1 if run else 0)
        configured = bool((cfg.get("automation") or {}).get("enabled", False))
        enabled = timer_enabled("netbox-discovery.timer")
        if configured != enabled:
            result["severity"] = max(result["severity"], 1)
            result["problems"].append("Network scheduler config/systemd divergentes")

    try:
        from modules.hypervisor.config import load_hypervisor_config
        hcfg = load_hypervisor_config(required=False)
        sources = hcfg.get("sources") or []
        if sources:
            site = str((cfg.get("discovery") or {}).get("site") or "") if cfg else ""
            hrun = load_json(latest("{0}-hypervisor-run-*.json".format(site)))
            result["hypervisor"] = hrun.get("status", "SEM_EXECUCAO")
            if hrun.get("status") == "FAIL":
                result["severity"] = 2
                result["problems"].append("Hypervisor último RUN falhou")
            configured = bool((hcfg.get("automation") or {}).get("enabled", False))
            enabled = timer_enabled("netbox-discovery-hypervisor.timer")
            if configured != enabled:
                result["severity"] = max(result["severity"], 1)
                result["problems"].append("Hypervisor scheduler config/systemd divergentes")
    except Exception as exc:
        result["hypervisor"] = "WARNING"
        result["severity"] = max(result["severity"], 1)
        result["problems"].append("Hypervisor config: {0}".format(exc))

    result["status"] = "CRITICAL" if result["severity"] >= 2 else ("WARNING" if result["severity"] == 1 else "OK")

    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print("===== NETBOX-DISCOVERY HEALTH =====")
        print("Status: {0}".format(result["status"]))
        print("Versão: {0}".format(result["version"]))
        print("Produto: {0}".format(result["product"]))
        print("NetBox: {0}".format(result["netbox"]))
        print("Update: {0}".format(result["update"]))
        print("Network: {0}".format(result["network"]))
        print("Hypervisor: {0}".format(result["hypervisor"]))
        for problem in result["problems"]:
            print("- {0}".format(problem))
    return int(result["severity"])


if __name__ == "__main__":
    sys.exit(main())
