#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import ipaddress

from modules.hypervisor.config import clean

MODES = ("single_site", "multi_site", "multi_tenant")


def norm(value):
    return clean(value).casefold()


def valid_ip(value):
    value = clean(value)
    if not value:
        return ""
    try:
        obj = ipaddress.ip_address(value.split("%")[0].split("/")[0])
        if obj.is_loopback or obj.is_link_local or obj.is_multicast or obj.is_unspecified:
            return ""
        return str(obj)
    except Exception:
        return ""


def interface_networks(record, management_only=False):
    rows = []
    for interface in record.get("interfaces") or []:
        if management_only and not bool(interface.get("management")):
            continue
        for iprow in interface.get("ips") or []:
            ip = valid_ip(iprow.get("address"))
            prefix = iprow.get("prefix_length")
            if not ip or prefix is None:
                continue
            try:
                network = ipaddress.ip_network("{0}/{1}".format(ip, int(prefix)), strict=False)
            except Exception:
                continue
            text = str(network)
            if text not in rows:
                rows.append(text)
    return rows


def management_network_groups(raw):
    groups = {}
    for host in raw.get("hosts") or []:
        nets = interface_networks(host, management_only=True) or interface_networks(host, management_only=False)
        for network in nets:
            row = groups.setdefault(network, {"network": network, "hosts": [], "datacenters": [], "clusters": []})
            name = clean(host.get("name"))
            if name and name not in row["hosts"]:
                row["hosts"].append(name)
            dc = clean(host.get("datacenter"))
            if dc and dc not in row["datacenters"]:
                row["datacenters"].append(dc)
            cluster = clean(host.get("cluster"))
            if cluster and cluster not in row["clusters"]:
                row["clusters"].append(cluster)
    return [groups[key] for key in sorted(groups)]


def _network_detail(row):
    return {
        "network": clean(row.get("network")),
        "hosts": sorted(list(row.get("hosts") or [])),
        "datacenters": sorted(list(row.get("datacenters") or [])),
        "clusters": sorted(list(row.get("clusters") or [])),
    }


def management_placement_groups(raw):
    """Collapse management networks that clearly belong to one VMware Datacenter.

    ESXi can expose several vmkernel NICs with the VMware 'management' service
    enabled. Asking Tenant/Site once per vmkernel network is noisy and can lead
    to accidental inconsistent mappings. When a management network is observed
    only inside one Datacenter, group those networks by Datacenter and ask once.
    Ambiguous networks (no Datacenter or shared by multiple Datacenters) remain
    individual groups and therefore still require explicit mapping.

    Per-network evidence is retained so that opening a Datacenter group for
    detailed review shows only the Hosts/Clusters actually observed on each CIDR.
    """
    network_groups = management_network_groups(raw)
    by_dc = {}
    individual = []

    for row in network_groups:
        network = clean(row.get("network"))
        detail = _network_detail(row)
        dcs = [clean(x) for x in row.get("datacenters") or [] if clean(x)]
        if len(dcs) != 1:
            individual.append({
                "kind": "network",
                "label": network,
                "networks": [network],
                "hosts": list(detail["hosts"]),
                "datacenters": list(detail["datacenters"]),
                "clusters": list(detail["clusters"]),
                "network_details": {network: detail},
            })
            continue

        dc = dcs[0]
        group = by_dc.setdefault(dc, {
            "kind": "datacenter",
            "label": dc,
            "networks": [],
            "hosts": [],
            "datacenters": [dc],
            "clusters": [],
            "network_details": {},
        })
        if network and network not in group["networks"]:
            group["networks"].append(network)
        group["network_details"][network] = detail
        for key in ("hosts", "clusters"):
            for value in row.get(key) or []:
                if value not in group[key]:
                    group[key].append(value)

    rows = [by_dc[key] for key in sorted(by_dc)] + individual
    for row in rows:
        row["networks"] = sorted(row.get("networks") or [])
        row["hosts"] = sorted(row.get("hosts") or [])
        row["clusters"] = sorted(row.get("clusters") or [])
    return rows


def validate_mapping(mapping, mode):
    network = clean(mapping.get("network"))
    try:
        ipaddress.ip_network(network, strict=False)
    except Exception:
        raise RuntimeError("mapeamento Hypervisor com rede inválida: {0}".format(network))
    if not clean(mapping.get("site")):
        raise RuntimeError("mapeamento Hypervisor sem Site: {0}".format(network))
    if mode == "multi_tenant" and not clean(mapping.get("tenant")):
        raise RuntimeError("mapeamento Hypervisor sem Tenant: {0}".format(network))


def mapping_network(mapping):
    try:
        return ipaddress.ip_network(clean(mapping.get("network")), strict=False)
    except Exception:
        return None


def context_from_mapping(mapping, default_tenant="", default_group=""):
    return {
        "tenant_group": clean(mapping.get("tenant_group")) or clean(default_group),
        "tenant": clean(mapping.get("tenant")) or clean(default_tenant),
        "site": clean(mapping.get("site")),
        "network": clean(mapping.get("network")),
    }


def resolve_ip(ip, mappings, default_tenant="", default_group=""):
    ip = valid_ip(ip)
    if not ip:
        return None
    obj = ipaddress.ip_address(ip)
    hits = []
    for mapping in mappings or []:
        network = mapping_network(mapping)
        if network and network.version == obj.version and obj in network:
            hits.append((network.prefixlen, mapping))
    if not hits:
        return None
    hits.sort(key=lambda x: x[0], reverse=True)
    best_prefix = hits[0][0]
    best = [m for plen, m in hits if plen == best_prefix]
    contexts = set((clean(m.get("tenant")) or clean(default_tenant), clean(m.get("site"))) for m in best)
    if len(contexts) != 1:
        return None
    return context_from_mapping(best[0], default_tenant, default_group)


def record_ips(record, management_first=False):
    rows = []
    interfaces = list(record.get("interfaces") or [])
    if management_first:
        interfaces.sort(key=lambda x: 0 if x.get("management") else 1)
    for interface in interfaces:
        for iprow in interface.get("ips") or []:
            ip = valid_ip(iprow.get("address"))
            if ip and ip not in rows:
                rows.append(ip)
    return rows


def resolve_host(host, source, default_tenant, default_site, default_group=""):
    mode = clean(source.get("inventory_mode") or "single_site").lower()
    if mode == "single_site":
        return {"tenant_group": clean(default_group), "tenant": clean(default_tenant), "site": clean(default_site), "network": ""}
    mappings = source.get("mappings") or []
    for ip in record_ips(host, management_first=True):
        ctx = resolve_ip(ip, mappings, default_tenant if mode == "multi_site" else "", default_group)
        if ctx:
            return ctx
    return None


def resolve_vm(vm, source, host_contexts, default_tenant, default_site, default_group=""):
    mode = clean(source.get("inventory_mode") or "single_site").lower()
    if mode == "single_site":
        return {"tenant_group": clean(default_group), "tenant": clean(default_tenant), "site": clean(default_site), "network": ""}
    host_key = (clean(source.get("id")).casefold(), clean(vm.get("host_name")).casefold())
    if host_key in host_contexts:
        return host_contexts[host_key]
    mappings = source.get("mappings") or []
    for ip in record_ips(vm):
        ctx = resolve_ip(ip, mappings, default_tenant if mode == "multi_site" else "", default_group)
        if ctx:
            return ctx
    return None


def context_key(ctx):
    if not ctx:
        return None
    return (clean(ctx.get("tenant")), clean(ctx.get("site")))
