#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("NETBOX_DISCOVERY_BASE", os.path.abspath(os.path.join(HERE, "..", "..")))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import configurator as base
from modules.hypervisor import scope as scope_tool

ORIG_SAVE = base.save_hypervisor_config


def sync_scheduler(data):
    if os.geteuid() != 0:
        raise RuntimeError("configuração do scheduler Hypervisor exige root")
    auto = (data or {}).get("automation") or {}
    enabled = bool(auto.get("enabled", False))
    schedule = base.clean(auto.get("schedule") or "daily")
    unit = "netbox-discovery-hypervisor.timer"
    dropin = "/etc/systemd/system/netbox-discovery-hypervisor.timer.d"
    if enabled:
        if not os.path.isdir(dropin):
            os.makedirs(dropin)
        with open(os.path.join(dropin, "schedule.conf"), "w") as handle:
            handle.write("[Timer]\nOnCalendar=\nOnCalendar={0}\n".format(schedule))
        subprocess.check_call(["systemctl", "daemon-reload"])
        subprocess.check_call(["systemctl", "enable", "--now", unit])
    else:
        subprocess.call(["systemctl", "disable", "--now", unit])


def save_hypervisor_config(data, path=None):
    if path is None:
        ORIG_SAVE(data)
    else:
        ORIG_SAVE(data, path)
    sync_scheduler(data)


def parse_args(argv=None):
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--scope", choices=("site_networks", "all"))
    ap.add_argument("--scope-status", action="store_true")
    args, rest = ap.parse_known_args(argv)
    if rest:
        raise RuntimeError("argumento desconhecido: {0}".format(" ".join(rest)))
    return args


def main(argv=None):
    args = parse_args(argv)
    if args.scope or args.scope_status:
        cfg = base.load_hypervisor_config(required=True)
        if args.scope_status:
            scope_tool.show(cfg)
            return 0
        scope_tool.set_scope(cfg, args.scope)
        return 0

    old = base.save_hypervisor_config
    try:
        base.save_hypervisor_config = save_hypervisor_config
        return base.main()
    finally:
        base.save_hypervisor_config = old


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("ERRO: {0}".format(exc), file=sys.stderr)
        sys.exit(1)
