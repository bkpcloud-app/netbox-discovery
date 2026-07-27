#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

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


def main():
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
