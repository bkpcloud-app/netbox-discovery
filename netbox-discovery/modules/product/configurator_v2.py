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

ORIG_WRITE_CONFIG = base.write_config


def sync_scheduler(enabled, schedule):
    if os.geteuid() != 0:
        raise RuntimeError("configuração do scheduler exige root")
    unit = "netbox-discovery.timer"
    dropin = "/etc/systemd/system/netbox-discovery.timer.d"
    if enabled:
        if not os.path.isdir(dropin):
            os.makedirs(dropin)
        with open(os.path.join(dropin, "schedule.conf"), "w") as handle:
            handle.write("[Timer]\nOnCalendar=\nOnCalendar={0}\n".format(schedule or "daily"))
        subprocess.check_call(["systemctl", "daemon-reload"])
        subprocess.check_call(["systemctl", "enable", "--now", unit])
    else:
        subprocess.call(["systemctl", "disable", "--now", unit])


def write_config(values):
    ORIG_WRITE_CONFIG(values)
    sync_scheduler(bool(values.get("automation_enabled")), values.get("schedule") or "daily")


def main(argv=None):
    old = base.write_config
    try:
        base.write_config = write_config
        return base.main(argv)
    finally:
        base.write_config = old


if __name__ == "__main__":
    sys.exit(main())
