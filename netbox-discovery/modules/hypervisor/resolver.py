#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import ipaddress
import socket

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


def _interface_ip_networks(interface):
    rows = []
    for iprow in interface.get("ips") or []:
        ip = valid_ip(iprow.get("address"))
        prefix = iprow.get("prefix_length")
        if not ip or prefix is None:
            continue
        try:
            network = ipaddress.ip_network("{0}/{1}".format(ip, int(prefix)), strict=False)
        except Exception:
            continue
        rows.append((ip, str(network)))
    return rows


def interface_networks(record, management_only=False):
    rows = []
    for interface in record.get("interfaces") or []:
        if management_only and not bool(interface.get("management")):
            continue
        for _ip, network in _interface_ip_networks(interface):
            if network not in rows:
                rows.append(network)
    return rows


def _looks_like_vmware_host(record):
    if clean(record.get("provider")).lower() == "vmware":
        return True
    return any(clean(x.get("name")).lower().startswith("vmk") for x in (record.get("interfaces") or []))


def _resolved_name_ips(record):
    name = clean(record.get("name"))
    if not name:
        return []
    direct = valid_ip(name)
    if direct:
        return [direct]
    rows = []
    try:
        for item in socket.getaddrinfo(name, None):
            sockaddr = item[4] if len(item) > 4 else None
            address = sockaddr[0] if sockaddr else ""
            ip = valid_ip(address)
            if ip and ip not in rows:
                rows.append(ip)
    except Exception:
        pass
    return rows


def authoritative_management_interfaces(record):
    """Return only interfaces safe to use for Tenant/Site placement.

    VMware can mark several vmkernel NICs with the management service. Those
    interfaces remain useful inventory evidence, but they must not all become
    Site mappings. For VMware hosts, choose an authoritative management path
    conservatively:

    1. vmkernel IP matching the ESXi hostname/FQDN resolution;
    2. management vmk0;
    3. the only remaining management network;
    4. otherwise unresolved (empty list).

    Non-VMware providers preserve the previous behavior: explicitly marked
    management interfaces first, otherwise any interface carrying an IP.
    """
    interfaces = list(record.get("interfaces") or [])
    with_ip = [x for x in interfaces if _interface_ip_networks(x)]
    marked = [x for x in with_ip if bool(x.get("management"))]

    if not _looks_like_vmware_host(record):
        return marked or with_ip

    candidates = marked
    if not candidates:
        vmk0 = [x for x in with_ip if clean(x.get("name")).lower() == "vmk0"]
        return vmk0 if len(vmk0) == 1 else []

    resolved = set(_resolved_name_ips(record))
    if resolved:
        matched = []
        for interface in candidates:
            if any(ip in resolved for ip, _network in _interface_ip_networks(interface)):
                matched.append(interface)
        matched_networks = set(
            network for interface in matched for _ip, network in _interface_ip_networks(interface)
        )
        if matched and len(matched_networks) == 1:
            return matched

    vmk0 = [x for x in candidates if clean(x.get("name")).lower() == "vmk0"]
    if len(vmk0) == 1:
        return vmk0

    candidate_networks = set(
        network for interface in candidates for _ip, network in _interface_ip_networks(interface)
    )
    if len(candidate_networks) == 1:
        return candidates

    return []


def authoritative_management_networks(record):
    rows = []
    for interface in authoritative_management_interfaces(record):
        for _ip, network in _interface_ip_networks(interface):
            if network not in rows:
                rows.append(network)
    return rows


def authoritative_management_ips(record):
    rows = []
    for interface in authoritative_management_interfaces(record):
        for ip, _network in _interface_ip_networks(interface):
            if ip not in rows:
                rows.append(ip)
    return rows


def management_network_groups(raw):
    groups = {}
    for host in raw.get("hosts") or []:
        nets = authoritative_management_networks(host)
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
    """Group authoritative management networks by unambiguous Datacenter.

    Only the authoritative management network selected for each host participates
    in Tenant/Site placement. Auxiliary vmkernel networks remain in discovery but
    are not promoted to Site mappings merely because VMware has the management
    service enabled on them.
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
    for ip in authoritative_management_ips(host):
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
