#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import ipaddress
import json

from modules.hypervisor import engine as base

ENGINE_VERSION = "2.0-product"
_ACTIVE_NETWORKS = []
NetBox = base.NetBox


def _authoritative_ip(iprow, ip):
    if bool(iprow.get("primary")):
        return True
    try:
        obj = ipaddress.ip_address(ip)
    except Exception:
        return False
    return any(obj.version == network.version and obj in network for network in _ACTIVE_NETWORKS)


def desired_ip_specs(item):
    """Return only IPs safe to use as NetBox identity/bindings.

    Discovery keeps every guest IP for audit. The plan intentionally ignores
    secondary IPs outside the Site networks because container/bridge addresses
    are commonly repeated across unrelated VMs. A primary IP is always
    eligible, even when it is outside the Site networks.
    """
    rows = []
    for interface in item.get("interfaces") or []:
        for iprow in interface.get("ips") or []:
            ip = base.valid_ip(iprow.get("address"))
            cidr = base.clean(iprow.get("cidr"))
            if not ip or not cidr:
                continue
            if not _authoritative_ip(iprow, ip):
                continue
            rows.append({
                "name": base.clean(interface.get("name")) or "MGMT",
                "ip": ip,
                "address": cidr,
                "kind": "PRIMARY" if iprow.get("primary") else "SITE",
                "mgmt_only": bool(interface.get("management")),
                "primary": bool(iprow.get("primary")),
                "mac": base.clean(interface.get("mac")),
                "network": base.clean(interface.get("network")),
            })
    return rows


def build_plan(discovery, nb=None):
    global _ACTIVE_NETWORKS
    previous_networks = _ACTIVE_NETWORKS
    previous_specs = base.desired_ip_specs
    _ACTIVE_NETWORKS = [ipaddress.ip_network(x, strict=False) for x in discovery.get("networks") or []]
    base.desired_ip_specs = desired_ip_specs
    try:
        active_nb = nb or NetBox()
        plan, path = base.build_plan(discovery, active_nb)
        plan["engine_version"] = ENGINE_VERSION
        plan["ip_policy"] = "primary_or_site_network"
        with open(path, "w") as handle:
            json.dump(plan, handle, indent=2, sort_keys=True)
        return plan, path
    finally:
        base.desired_ip_specs = previous_specs
        _ACTIVE_NETWORKS = previous_networks


# Public engine surface used by runner.py.
collect_all = base.collect_all
apply_plan = base.apply_plan
audit = base.audit
utc_now = base.utc_now
