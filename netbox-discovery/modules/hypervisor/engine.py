#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import csv
import datetime
import ipaddress
import json
import os
import re
import sys
import urllib.parse
from collections import Counter, defaultdict

BASE = os.environ.get("NETBOX_DISCOVERY_BASE", "/opt/netbox-discovery")
REPORTS = os.path.join(BASE, "reports")
ENGINE_VERSION = "1.0-product"

if BASE not in sys.path:
    sys.path.insert(0, BASE)

from lib.config import load_config
from lib.netbox import NetBox
from modules.hypervisor.config import clean, enabled_sources, load_hypervisor_config, public_source
from modules.hypervisor.collectors import collect_source, norm_mac, valid_ip
from modules.importers.importer import (
    Catalog,
    build_indexes,
    create_device,
    ensure_interface,
    ensure_ip,
    get_device_id_from_ip,
    nested_id,
    nested_name,
    norm,
    norm_ip,
    norm_serial,
    query,
    rematch_record,
    safe_patch_for_existing,
    slugify,
)


def utc_stamp():
    return datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")


def utc_now():
    return datetime.datetime.utcnow().isoformat() + "Z"


def ensure_reports_dir():
    if not os.path.isdir(REPORTS):
        os.makedirs(REPORTS)


def load_site_networks(cfg):
    disc = cfg.get("discovery") or {}
    path = clean(disc.get("networks_file"))
    if not path or not os.path.isfile(path):
        raise RuntimeError("Arquivo de redes não encontrado: {0}".format(path))
    rows = []
    with open(path, "r") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            rows.append(ipaddress.ip_network(line, strict=False))
    if not rows:
        raise RuntimeError("Nenhuma rede configurada")
    return rows


def ip_in_networks(value, networks):
    ip = valid_ip(value)
    if not ip:
        return False
    obj = ipaddress.ip_address(ip)
    return any(obj in n for n in networks if n.version == obj.version)


def record_ips(record):
    out = []
    for interface in record.get("interfaces") or []:
        for iprow in interface.get("ips") or []:
            ip = valid_ip(iprow.get("address"))
            if ip and ip not in out:
                out.append(ip)
    return out


def infer_prefix_length(ip, networks):
    obj = ipaddress.ip_address(ip)
    matches = [n for n in networks if n.version == obj.version and obj in n]
    if len(matches) == 1:
        return matches[0].prefixlen
    return None


def normalize_interfaces(interfaces, networks):
    rows = []
    used_names = set()
    for idx, src in enumerate(interfaces or []):
        base_name = clean(src.get("name")) or "nic{0}".format(idx)
        name = base_name
        seq = 2
        while norm(name) in used_names:
            name = "{0}-{1}".format(base_name, seq)
            seq += 1
        used_names.add(norm(name))
        ips = []
        seen_ip = set()
        for iprow in src.get("ips") or []:
            ip = valid_ip(iprow.get("address"))
            if not ip or ip in seen_ip:
                continue
            seen_ip.add(ip)
            prefix = iprow.get("prefix_length")
            try:
                prefix = int(prefix) if prefix is not None and clean(prefix) != "" else None
            except Exception:
                prefix = None
            if prefix is None:
                prefix = infer_prefix_length(ip, networks)
            address = "{0}/{1}".format(ip, prefix) if prefix is not None else ""
            ips.append({
                "address": ip,
                "prefix_length": prefix,
                "cidr": address,
                "primary": bool(iprow.get("primary")),
            })
        rows.append({
            "name": name,
            "mac": norm_mac(src.get("mac")),
            "network": clean(src.get("network")),
            "management": bool(src.get("management")),
            "ips": ips,
        })
    return rows


def scope_inventory(raw, source, networks):
    mode = clean(source.get("scope_mode") or "site_networks").lower()
    if mode not in ("site_networks", "all"):
        mode = "site_networks"

    hosts = []
    for row in raw.get("hosts") or []:
        item = dict(row)
        item["interfaces"] = normalize_interfaces(item.get("interfaces"), networks)
        if mode == "all" or any(ip_in_networks(ip, networks) for ip in record_ips(item)):
            hosts.append(item)

    host_names = set(norm(x.get("name")) for x in hosts if clean(x.get("name")))
    vms = []
    for row in raw.get("vms") or []:
        item = dict(row)
        item["interfaces"] = normalize_interfaces(item.get("interfaces"), networks)
        by_host = norm(item.get("host_name")) in host_names if clean(item.get("host_name")) else False
        by_ip = any(ip_in_networks(ip, networks) for ip in record_ips(item))
        if mode == "all" or by_host or by_ip:
            vms.append(item)

    cluster_keys = set(norm(x.get("cluster")) for x in hosts + vms if clean(x.get("cluster")))
    clusters = [dict(x) for x in (raw.get("clusters") or []) if norm(x.get("name")) in cluster_keys]

    result = dict(raw)
    result["scope_mode"] = mode
    result["hosts"] = hosts
    result["vms"] = vms
    result["clusters"] = clusters
    result["scope_summary"] = {
        "raw_hosts": len(raw.get("hosts") or []),
        "hosts": len(hosts),
        "raw_vms": len(raw.get("vms") or []),
        "vms": len(vms),
        "clusters": len(clusters),
    }
    return result


def collect_all():
    cfg = load_config()
    hv_cfg = load_hypervisor_config(required=True)
    networks = load_site_networks(cfg)
    sources = enabled_sources(hv_cfg)
    if not sources:
        raise RuntimeError("Nenhum hypervisor habilitado. Execute: netbox-discovery hypervisor configure")

    results = []
    errors = []
    print("===== HYPERVISOR DISCOVER =====")
    print("Tenant/Site: {0}/{1}".format(cfg.get("tenant", ""), (cfg.get("discovery") or {}).get("site", "")))
    print("Sources habilitados: {0}".format(len(sources)))
    print("NetBox write: NÃO")

    for pos, source in enumerate(sources, 1):
        label = "{0} ({1})".format(source.get("id"), source.get("type"))
        print("[{0}/{1}] Coletando {2}...".format(pos, len(sources), label))
        try:
            raw = collect_source(source)
            scoped = scope_inventory(raw, source, networks)
            results.append(scoped)
            sm = scoped.get("scope_summary") or {}
            print("  OK: hosts {0}/{1} | VMs {2}/{3} | clusters {4}".format(
                sm.get("hosts", 0), sm.get("raw_hosts", 0), sm.get("vms", 0), sm.get("raw_vms", 0), sm.get("clusters", 0)
            ))
        except Exception as exc:
            errors.append({"source_id": source.get("id"), "error": str(exc)})
            print("  ERRO: {0}".format(exc))

    if errors:
        raise RuntimeError("Falha em {0} source(s) de hypervisor; nenhuma escrita foi iniciada".format(len(errors)))

    # Detect duplicate authoritative identities across sources. Do not silently merge.
    identity = defaultdict(list)
    for result in results:
        for host in result.get("hosts") or []:
            key = norm_serial(host_identity_serial(host))
            if key:
                identity[("HOST", key)].append((result.get("source_id"), host.get("name")))
        for vm in result.get("vms") or []:
            key = norm_serial(vm.get("serial")) or norm(vm.get("uuid"))
            if key:
                identity[("VM", key)].append((result.get("source_id"), vm.get("name")))
    duplicate_identities = []
    for (kind, key), refs in identity.items():
        unique = set((clean(a), clean(b)) for a, b in refs)
        if len(unique) > 1:
            duplicate_identities.append({"kind": kind, "identity": key, "refs": list(sorted(unique))})

    out = {
        "stage": "HYPERVISOR_DISCOVERY",
        "engine_version": ENGINE_VERSION,
        "generated_at": utc_now(),
        "tenant": cfg.get("tenant", ""),
        "site": (cfg.get("discovery") or {}).get("site", ""),
        "networks": [str(x) for x in networks],
        "sources": [public_source(x) for x in sources],
        "results": results,
        "duplicate_identities": duplicate_identities,
        "netbox_write": False,
    }
    ensure_reports_dir()
    path = os.path.join(REPORTS, "{0}-hypervisor-discovery-{1}.json".format(out["site"] or "SITE", utc_stamp()))
    with open(path, "w") as handle:
        json.dump(out, handle, indent=2, sort_keys=True)
    print("HYPERVISOR DISCOVERY: hosts={0} VMs={1} clusters={2}".format(
        sum(len(x.get("hosts") or []) for x in results),
        sum(len(x.get("vms") or []) for x in results),
        sum(len(x.get("clusters") or []) for x in results),
    ))
    if duplicate_identities:
        print("AVISO: identidades duplicadas entre sources: {0}".format(len(duplicate_identities)))
    print("JSON: {0}".format(path))
    return out, path


def choose_exact(rows, value, label, field="name"):
    matches = [x for x in rows if norm(x.get(field)) == norm(value)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise RuntimeError("{0} duplicado no NetBox: {1}".format(label, value))
    return None


def nested_vm_id(iprow):
    ao = iprow.get("assigned_object") or {}
    if not isinstance(ao, dict):
        return None
    vm = ao.get("virtual_machine") or {}
    if isinstance(vm, dict) and vm.get("id"):
        return vm.get("id")
    if clean(iprow.get("assigned_object_type")) == "virtualization.virtualmachine" and ao.get("id"):
        return ao.get("id")
    return None


def assigned_object_id(row):
    ao = row.get("assigned_object") or {}
    if isinstance(ao, dict) and ao.get("id"):
        return ao.get("id")
    return row.get("assigned_object_id")


def mac_owner_id(row):
    ao = row.get("assigned_object") or {}
    if not isinstance(ao, dict):
        return None
    atype = clean(row.get("assigned_object_type"))
    if atype == "dcim.interface":
        device = ao.get("device") or {}
        if isinstance(device, dict):
            return device.get("id")
    if atype == "virtualization.vminterface":
        vm = ao.get("virtual_machine") or {}
        if isinstance(vm, dict):
            return vm.get("id")
    return None


def mac_conflicts_for_target(specs, state, expected_type, target_id=None):
    conflicts = []
    for spec in specs:
        mac = norm_mac(spec.get("mac"))
        if not mac:
            continue
        matches = [x for x in state["macs"] if norm_mac(mac_value(x)) == mac]
        if len(matches) > 1:
            conflicts.append("MAC duplicado no NetBox: {0}".format(mac))
            continue
        if not matches:
            continue
        obj = matches[0]
        aoid = mac_assigned_id(obj)
        atype = clean(obj.get("assigned_object_type"))
        if not aoid:
            continue
        owner_id = mac_owner_id(obj)
        if not target_id or atype != expected_type or owner_id != target_id:
            conflicts.append("MAC {0} pertence a {1} ID {2}".format(mac, atype or "outro objeto", aoid))
    return conflicts


def ip_owner_id(row):
    atype = clean(row.get("assigned_object_type"))
    if atype == "dcim.interface":
        return get_device_id_from_ip(row)
    if atype == "virtualization.vminterface":
        return nested_vm_id(row)
    return None


def binding_conflicts_for_target(specs, state, expected_type, target_id=None):
    conflicts = []
    if not target_id:
        return conflicts
    for spec in specs:
        bound = set()
        ip = norm_ip(spec.get("ip"))
        if ip:
            matches = [x for x in state["ips"] if norm_ip(x.get("address")) == ip]
            if len(matches) == 1:
                obj = matches[0]
                if clean(obj.get("assigned_object_type")) == expected_type and ip_owner_id(obj) == target_id and assigned_object_id(obj):
                    bound.add(assigned_object_id(obj))
        mac = norm_mac(spec.get("mac"))
        if mac:
            matches = [x for x in state["macs"] if norm_mac(mac_value(x)) == mac]
            if len(matches) == 1:
                obj = matches[0]
                if clean(obj.get("assigned_object_type")) == expected_type and mac_owner_id(obj) == target_id and mac_assigned_id(obj):
                    bound.add(mac_assigned_id(obj))
        if len(bound) > 1:
            conflicts.append("IP/MAC da mesma interface apontam para interfaces diferentes no NetBox: {0}".format(clean(spec.get("name"))))
    return conflicts


def specs_need_update(specs, state, expected_type, target_id=None):
    for spec in specs:
        ip = norm_ip(spec.get("ip"))
        if ip:
            matches = [x for x in state["ips"] if norm_ip(x.get("address")) == ip]
            if len(matches) != 1:
                return True
            obj = matches[0]
            if clean(obj.get("assigned_object_type")) != expected_type or ip_owner_id(obj) != target_id or not assigned_object_id(obj):
                return True
        mac = norm_mac(spec.get("mac"))
        if mac:
            matches = [x for x in state["macs"] if norm_mac(mac_value(x)) == mac]
            if len(matches) != 1:
                return True
            obj = matches[0]
            if clean(obj.get("assigned_object_type")) != expected_type or mac_owner_id(obj) != target_id or not mac_assigned_id(obj):
                return True
    return False


def existing_interface_for_spec(state, spec, expected_type, target_id):
    candidates = []
    ip = norm_ip(spec.get("ip"))
    if ip:
        matches = [x for x in state["ips"] if norm_ip(x.get("address")) == ip]
        if len(matches) == 1:
            obj = matches[0]
            if clean(obj.get("assigned_object_type")) == expected_type and ip_owner_id(obj) == target_id:
                ao = obj.get("assigned_object") or {}
                if isinstance(ao, dict) and ao.get("id"):
                    candidates.append(ao)
    mac = norm_mac(spec.get("mac"))
    if mac:
        matches = [x for x in state["macs"] if norm_mac(mac_value(x)) == mac]
        if len(matches) == 1:
            obj = matches[0]
            if clean(obj.get("assigned_object_type")) == expected_type and mac_owner_id(obj) == target_id:
                ao = obj.get("assigned_object") or {}
                if isinstance(ao, dict) and ao.get("id"):
                    candidates.append(ao)
    ids = set(x.get("id") for x in candidates if x.get("id"))
    if len(ids) > 1:
        raise RuntimeError("IP/MAC apontam para interfaces diferentes no mesmo objeto")
    return candidates[0] if candidates else None


def state_from_netbox(nb, tenant_name, site_name):
    tenants = query(nb, "tenancy/tenants/", name=tenant_name, limit=100)
    tenant = choose_exact(tenants, tenant_name, "Tenant")
    sites = query(nb, "dcim/sites/", name=site_name, limit=100)
    site = choose_exact(sites, site_name, "Site")
    if not tenant:
        raise RuntimeError("Tenant não encontrado no NetBox: {0}".format(tenant_name))
    if not site:
        raise RuntimeError("Site não encontrado no NetBox: {0}".format(site_name))

    devices = query(nb, "dcim/devices/", tenant_id=tenant["id"], site_id=site["id"], limit=5000)
    ips = [x for x in query(nb, "ipam/ip-addresses/", limit=10000) if not x.get("vrf")]
    vms = query(nb, "virtualization/virtual-machines/", tenant_id=tenant["id"], limit=10000)
    clusters = query(nb, "virtualization/clusters/", limit=5000)
    prefixes = [x for x in query(nb, "ipam/prefixes/", limit=10000) if not x.get("vrf")]
    macs = query(nb, "dcim/mac-addresses/", limit=10000)
    roles = query(nb, "dcim/device-roles/", limit=5000)
    cluster_types = query(nb, "virtualization/cluster-types/", limit=1000)
    platforms = query(nb, "dcim/platforms/", limit=5000)
    manufacturers = query(nb, "dcim/manufacturers/", limit=5000)
    device_types = query(nb, "dcim/device-types/", limit=10000)
    return {
        "tenant": tenant,
        "site": site,
        "devices": devices,
        "ips": ips,
        "vms": vms,
        "clusters": clusters,
        "prefixes": prefixes,
        "macs": macs,
        "roles": roles,
        "cluster_types": cluster_types,
        "platforms": platforms,
        "manufacturers": manufacturers,
        "device_types": device_types,
    }


def cluster_scope_site_id(cluster):
    scope = cluster.get("scope") or {}
    if isinstance(scope, dict):
        return scope.get("id")
    return None


def cluster_provider_name(provider):
    return {
        "vmware": "VMware vSphere",
        "proxmox": "Proxmox VE",
        "hyperv": "Microsoft Hyper-V",
    }.get(clean(provider).lower(), "Virtualization")


def normalize_guest_platform(value):
    text = clean(value)
    low = text.lower()
    if not text:
        return ""
    if "windows server" in low:
        return "Windows Server"
    if "windows 11" in low:
        return "Windows 11"
    if "windows 10" in low:
        return "Windows 10"
    if "windows" in low:
        return "Windows"
    if "ubuntu" in low:
        return "Ubuntu Linux"
    if "debian" in low:
        return "Debian Linux"
    if "red hat" in low or "rhel" in low:
        return "Red Hat Enterprise Linux"
    if "centos" in low:
        return "CentOS Linux"
    if "linux" in low or low in ("l26", "l24"):
        return "Linux"
    return text[:100]


def vm_status(value):
    low = clean(value).lower()
    if low in ("poweredon", "running", "on"):
        return "active"
    return "offline"


def host_identity_serial(host):
    serial = clean(host.get("serial"))
    generic = {
        "", "UNKNOWN", "NONE", "N/A", "NA", "NOTSPECIFIED", "NOTSPECIFIEDBYOEM",
        "TOBEFILLEDBYOEM", "DEFAULTSTRING", "SYSTEMSERIALNUMBER", "SVCTAG",
        "00000000", "000000000000",
    }
    if norm_serial(serial) not in generic:
        return serial
    return clean(host.get("uuid"))


def flatten_discovery(discovery):
    hosts = []
    vms = []
    clusters = []
    for result in discovery.get("results") or []:
        hosts.extend(result.get("hosts") or [])
        vms.extend(result.get("vms") or [])
        clusters.extend(result.get("clusters") or [])
    return hosts, vms, clusters


def vm_indexes(state):
    by_id = dict((x.get("id"), x) for x in state["vms"] if x.get("id") is not None)
    by_serial = defaultdict(list)
    by_name = defaultdict(list)
    ip_vm = defaultdict(set)
    ip_objects = defaultdict(list)
    for vm in state["vms"]:
        serial = norm_serial(vm.get("serial"))
        if serial:
            by_serial[serial].append(vm)
        if clean(vm.get("name")):
            by_name[norm(vm.get("name"))].append(vm)
        for key in ("primary_ip4", "primary_ip6", "primary_ip"):
            obj = vm.get(key) or {}
            ip = norm_ip(obj.get("address") if isinstance(obj, dict) else obj)
            if ip:
                ip_vm[ip].add(vm.get("id"))
    for row in state["ips"]:
        ip = norm_ip(row.get("address"))
        if not ip:
            continue
        ip_objects[ip].append(row)
        vid = nested_vm_id(row)
        if vid:
            ip_vm[ip].add(vid)
    return {"by_id": by_id, "by_serial": by_serial, "by_name": by_name, "ip_vm": ip_vm, "ip_objects": ip_objects}


def desired_ip_specs(item):
    rows = []
    for interface in item.get("interfaces") or []:
        for iprow in interface.get("ips") or []:
            ip = valid_ip(iprow.get("address"))
            cidr = clean(iprow.get("cidr"))
            if not ip or not cidr:
                continue
            rows.append({
                "name": clean(interface.get("name")) or "MGMT",
                "ip": ip,
                "address": cidr,
                "kind": "PRIMARY" if iprow.get("primary") else "OTHER",
                "mgmt_only": bool(interface.get("management")),
                "primary": bool(iprow.get("primary")),
                "mac": clean(interface.get("mac")),
                "network": clean(interface.get("network")),
            })
    return rows


def host_plan_row(host, device_indexes, state):
    specs = desired_ip_specs(host)
    identity_serial = host_identity_serial(host)
    row = {
        "object_type": "HOST",
        "asset_id": "HV-HOST:{0}:{1}".format(host.get("source_id"), norm_serial(identity_serial) or norm(host.get("name"))),
        "provider": host.get("provider"),
        "source_id": host.get("source_id"),
        "desired_name": clean(host.get("name")),
        "serial": identity_serial,
        "manufacturer": clean(host.get("manufacturer")) or "Generic",
        "model": clean(host.get("model")) or "Hypervisor Host",
        "target_role": "HYPERVISOR",
        "platform": clean(host.get("platform")),
        "cluster": clean(host.get("cluster")),
        "interfaces": specs,
        "ips": [x.get("ip") for x in specs],
        "source": host,
    }
    current, match_state, reason = rematch_record(row, device_indexes)
    conflicts = []
    if not row.get("desired_name"):
        conflicts.append("host sem nome utilizável")
    for spec in specs:
        ip = spec.get("ip")
        objects = [x for x in state["ips"] if norm_ip(x.get("address")) == ip]
        if len(objects) > 1:
            conflicts.append("IP duplicado no NetBox: {0}".format(ip))
            continue
        if objects:
            obj = objects[0]
            tenant_id = nested_id(obj.get("tenant"))
            if tenant_id and tenant_id != state["tenant"]["id"]:
                conflicts.append("IP {0} pertence a outro tenant ID {1}".format(ip, tenant_id))
            atype = clean(obj.get("assigned_object_type"))
            if atype and atype != "dcim.interface":
                conflicts.append("IP {0} pertence a {1}".format(ip, atype))
    conflicts.extend(mac_conflicts_for_target(specs, state, "dcim.interface", current.get("id") if current else None))
    conflicts.extend(binding_conflicts_for_target(specs, state, "dcim.interface", current.get("id") if current else None))
    if match_state == "CONFLICT":
        conflicts.append(reason)
    if current is not None:
        desired_serial = norm_serial(row.get("serial"))
        current_serial = norm_serial(current.get("serial"))
        if desired_serial and current_serial and desired_serial != current_serial:
            conflicts.append("serial do host diverge do objeto existente")
        desired_cluster = norm(row.get("cluster"))
        current_cluster = norm(nested_name(current.get("cluster")))
        if desired_cluster and current_cluster and desired_cluster != current_cluster:
            conflicts.append("cluster do host diverge: NetBox={0} API={1}".format(nested_name(current.get("cluster")), row.get("cluster")))
    if conflicts:
        row.update({"decision": "REVIEW", "action": "CREATE" if current is None else "UPDATE_SAFE", "reason": "; ".join(conflicts), "existing_id": current.get("id") if current else None})
        return row
    if current is None:
        row.update({"decision": "READY", "action": "CREATE", "reason": "API de virtualização", "existing_id": None})
        return row
    patch_needed = bool(clean(row.get("serial")) and not clean(current.get("serial")))
    patch_needed = patch_needed or (bool(row.get("cluster")) and not nested_id(current.get("cluster")))
    patch_needed = patch_needed or (bool(row.get("platform")) and not nested_id(current.get("platform")))
    patch_needed = patch_needed or (bool(row.get("target_role")) and not nested_id(current.get("role")))
    patch_needed = patch_needed or specs_need_update(specs, state, "dcim.interface", current.get("id"))
    for spec in specs:
        if spec.get("primary"):
            field = "primary_ip6" if ":" in spec.get("ip", "") else "primary_ip4"
            if not nested_id(current.get(field)):
                patch_needed = True
    row.update({"decision": "READY", "action": "UPDATE_SAFE" if patch_needed else "NOOP", "reason": reason, "existing_id": current.get("id")})
    return row


def vm_scope_name(vm):
    return clean(vm.get("cluster")) or clean(vm.get("host_name"))


def match_vm(row, indexes, state):
    strong = set()
    serial = norm_serial(row.get("serial"))
    if serial:
        strong.update(x.get("id") for x in indexes["by_serial"].get(serial, []))
    for ip in row.get("ips") or []:
        strong.update(indexes["ip_vm"].get(norm_ip(ip), set()))
    if len(strong) > 1:
        return None, "CONFLICT", "serial/IP apontam para VMs diferentes"
    if len(strong) == 1:
        vid = list(strong)[0]
        current = indexes["by_id"].get(vid)
        if not current:
            return None, "CONFLICT", "IP aponta para VM fora do tenant"
        return current, "MATCHED", "serial/IP"

    names = indexes["by_name"].get(norm(row.get("desired_name")), [])
    scope = norm(row.get("cluster") or row.get("host_name"))
    if scope and len(names) > 1:
        scoped = []
        for vm in names:
            current_scope = norm(nested_name(vm.get("cluster")) or nested_name(vm.get("device")))
            if current_scope == scope:
                scoped.append(vm)
        names = scoped
    if len(names) == 1:
        return names[0], "MATCHED", "nome/escopo"
    if len(names) > 1:
        return None, "CONFLICT", "nome de VM ambíguo"
    return None, "NEW", "sem correspondência"


def vm_plan_row(vm, indexes, state):
    specs = desired_ip_specs(vm)
    row = {
        "object_type": "VM",
        "asset_id": "HV-VM:{0}:{1}".format(vm.get("source_id"), norm_serial(vm.get("serial")) or norm(vm.get("name"))),
        "provider": vm.get("provider"),
        "source_id": vm.get("source_id"),
        "kind": clean(vm.get("kind")) or "vm",
        "desired_name": clean(vm.get("name")),
        "serial": clean(vm.get("serial")),
        "host_name": clean(vm.get("host_name")),
        "cluster": clean(vm.get("cluster")),
        "platform": normalize_guest_platform(vm.get("platform")),
        "status": vm_status(vm.get("status")),
        "vcpus": vm.get("vcpus") or 0,
        "memory_mb": vm.get("memory_mb") or 0,
        "disk_gb": vm.get("disk_gb") or 0,
        "disk_mb": int(round(float(vm.get("disk_gb") or 0) * 1024.0)),
        "interfaces": specs,
        "ips": [x.get("ip") for x in specs],
        "source": vm,
    }
    current, match_state, reason = match_vm(row, indexes, state)
    conflicts = []
    if not row.get("desired_name"):
        conflicts.append("VM sem nome utilizável")
    for spec in specs:
        ip = spec.get("ip")
        objects = indexes["ip_objects"].get(ip, [])
        if len(objects) > 1:
            conflicts.append("IP duplicado no NetBox: {0}".format(ip))
            continue
        if not objects:
            continue
        obj = objects[0]
        tenant_id = nested_id(obj.get("tenant"))
        if tenant_id and tenant_id != state["tenant"]["id"]:
            conflicts.append("IP {0} pertence a outro tenant ID {1}".format(ip, tenant_id))
        atype = clean(obj.get("assigned_object_type"))
        vid = nested_vm_id(obj)
        if atype and atype != "virtualization.vminterface":
            conflicts.append("IP {0} pertence a {1}".format(ip, atype))
        elif current and vid and vid != current.get("id"):
            conflicts.append("IP {0} pertence a outra VM ID {1}".format(ip, vid))
        elif not current and vid:
            conflicts.append("IP {0} já pertence a VM ID {1}".format(ip, vid))
    conflicts.extend(mac_conflicts_for_target(specs, state, "virtualization.vminterface", current.get("id") if current else None))
    conflicts.extend(binding_conflicts_for_target(specs, state, "virtualization.vminterface", current.get("id") if current else None))
    role_name = "CONTAINER" if row.get("kind") == "container" else "VIRTUAL MACHINE"
    role_exact = [x for x in state["roles"] if norm(x.get("name")) == norm(role_name)]
    if len(role_exact) > 1:
        conflicts.append("Role de VM duplicada no NetBox: {0}".format(role_name))
    elif role_exact and role_exact[0].get("vm_role") is False:
        conflicts.append("Role {0} existe mas não permite Virtual Machines".format(role_name))
    elif not role_exact:
        role_slug = slugify(role_name)
        slug_hits = [x for x in state["roles"] if norm(x.get("slug")) == norm(role_slug)]
        if slug_hits:
            conflicts.append("Slug de Role de VM em uso: {0}".format(role_slug))
    if match_state == "CONFLICT":
        conflicts.append(reason)
    if current is not None:
        desired_serial = norm_serial(row.get("serial"))
        current_serial = norm_serial(current.get("serial"))
        if desired_serial and current_serial and desired_serial != current_serial:
            conflicts.append("serial/UUID da VM diverge do objeto existente")
        desired_cluster = norm(row.get("cluster"))
        current_cluster = norm(nested_name(current.get("cluster")))
        if desired_cluster and current_cluster and desired_cluster != current_cluster:
            conflicts.append("cluster da VM diverge: NetBox={0} API={1}".format(nested_name(current.get("cluster")), row.get("cluster")))
        desired_host = norm(row.get("host_name"))
        current_host = norm(nested_name(current.get("device")))
        if desired_host and current_host and desired_host != current_host:
            # VM migration between hosts is authoritative only when both hosts belong to the same cluster.
            # Leave as UPDATE_SAFE only for clustered VMs; standalone movement is REVIEW.
            if not desired_cluster:
                conflicts.append("host standalone da VM diverge: NetBox={0} API={1}".format(nested_name(current.get("device")), row.get("host_name")))
    if conflicts:
        row.update({"decision": "REVIEW", "action": "CREATE" if current is None else "UPDATE_SAFE", "reason": "; ".join(conflicts), "existing_id": current.get("id") if current else None})
        return row
    if current is None:
        row.update({"decision": "READY", "action": "CREATE", "reason": "API de virtualização", "existing_id": None})
        return row

    patch = vm_safe_patch_preview(row, current)
    if specs_need_update(specs, state, "virtualization.vminterface", current.get("id")):
        patch["interfaces"] = "NEEDED"
    for spec in specs:
        if spec.get("primary"):
            field = "primary_ip6" if ":" in spec.get("ip", "") else "primary_ip4"
            if not nested_id(current.get(field)):
                patch[field] = "NEEDED"
    row.update({"decision": "READY", "action": "UPDATE_SAFE" if patch else "NOOP", "reason": reason, "existing_id": current.get("id")})
    return row


def vm_safe_patch_preview(row, current):
    patch = {}
    if clean(row.get("serial")) and not clean(current.get("serial")):
        patch["serial"] = clean(row.get("serial"))
    status_obj = current.get("status") or {}
    cur_status = status_obj.get("value") if isinstance(status_obj, dict) else clean(status_obj)
    if clean(row.get("status")) and clean(cur_status) != clean(row.get("status")):
        patch["status"] = row.get("status")
    for key, current_key in (("vcpus", "vcpus"), ("memory_mb", "memory"), ("disk_mb", "disk")):
        desired = row.get(key) or 0
        current_value = current.get(current_key) or 0
        try:
            if float(desired) > 0 and abs(float(desired) - float(current_value)) > 0.01:
                patch[current_key] = desired
        except Exception:
            pass
    if clean(row.get("platform")) and not nested_id(current.get("platform")):
        patch["platform"] = "NEEDED"
    if clean(row.get("cluster")) and not nested_id(current.get("cluster")):
        patch["cluster"] = "NEEDED"
    if clean(row.get("host_name")):
        current_device_id = nested_id(current.get("device"))
        current_host_name = norm(nested_name(current.get("device")))
        desired_host_name = norm(row.get("host_name"))
        if not current_device_id or (clean(row.get("cluster")) and desired_host_name and current_host_name != desired_host_name):
            patch["device"] = "NEEDED"
    if not nested_id(current.get("role")):
        patch["role"] = "NEEDED"
    return patch


def prefix_plan_rows(networks, state):
    rows = []
    for network in networks:
        exact = [x for x in state["prefixes"] if clean(x.get("prefix")) == str(network)]
        if len(exact) == 0:
            rows.append({"object_type": "PREFIX", "asset_id": "PREFIX:{0}".format(network), "prefix": str(network), "decision": "READY", "action": "CREATE", "reason": "rede configurada do site"})
        elif len(exact) == 1:
            rows.append({"object_type": "PREFIX", "asset_id": "PREFIX:{0}".format(network), "prefix": str(network), "decision": "READY", "action": "NOOP", "reason": "prefixo já existe", "existing_id": exact[0].get("id")})
        else:
            rows.append({"object_type": "PREFIX", "asset_id": "PREFIX:{0}".format(network), "prefix": str(network), "decision": "REVIEW", "action": "NOOP", "reason": "mais de um prefixo exato no NetBox"})
    return rows


def cluster_plan_rows(clusters, state):
    rows = []
    seen = set()
    site_id = state["site"]["id"]
    for cluster in clusters:
        name = clean(cluster.get("name"))
        provider = clean(cluster.get("provider"))
        if not name:
            continue
        key = (norm(name), norm(provider))
        if key in seen:
            continue
        seen.add(key)
        candidates = [x for x in state["clusters"] if norm(x.get("name")) == norm(name)]
        scoped = [x for x in candidates if cluster_scope_site_id(x) in (None, site_id)]
        if len(scoped) == 1:
            current = scoped[0]
            current_type = nested_name(current.get("type"))
            expected_type = cluster_provider_name(provider)
            if current_type and norm(current_type) != norm(expected_type):
                rows.append({"object_type": "CLUSTER", "asset_id": "CLUSTER:{0}:{1}".format(provider, name), "name": name, "provider": provider, "decision": "REVIEW", "action": "NOOP", "reason": "tipo do cluster diverge: NetBox={0} API={1}".format(current_type, expected_type), "existing_id": current.get("id")})
            else:
                rows.append({"object_type": "CLUSTER", "asset_id": "CLUSTER:{0}:{1}".format(provider, name), "name": name, "provider": provider, "decision": "READY", "action": "NOOP", "reason": "cluster já existe", "existing_id": current.get("id")})
        elif len(scoped) > 1:
            rows.append({"object_type": "CLUSTER", "asset_id": "CLUSTER:{0}:{1}".format(provider, name), "name": name, "provider": provider, "decision": "REVIEW", "action": "NOOP", "reason": "cluster duplicado no site"})
        else:
            type_name = cluster_provider_name(provider)
            exact_type = [x for x in state["cluster_types"] if norm(x.get("name")) == norm(type_name)]
            type_slug = slugify(type_name)
            slug_collision = [x for x in state["cluster_types"] if norm(x.get("slug")) == norm(type_slug) and norm(x.get("name")) != norm(type_name)]
            if len(exact_type) > 1 or slug_collision:
                reason = "Cluster Type ambíguo/slug em uso: {0}".format(type_name)
                rows.append({"object_type": "CLUSTER", "asset_id": "CLUSTER:{0}:{1}".format(provider, name), "name": name, "provider": provider, "decision": "REVIEW", "action": "CREATE", "reason": reason})
            else:
                rows.append({"object_type": "CLUSTER", "asset_id": "CLUSTER:{0}:{1}".format(provider, name), "name": name, "provider": provider, "decision": "READY", "action": "CREATE", "reason": "API de virtualização"})
    return rows


def build_plan(discovery, nb=None):
    networks = [ipaddress.ip_network(x, strict=False) for x in discovery.get("networks") or []]
    nb = nb or NetBox()
    state = state_from_netbox(nb, discovery.get("tenant"), discovery.get("site"))
    device_indexes = build_indexes(state["devices"], state["ips"])
    vi = vm_indexes(state)
    hosts, vms, clusters = flatten_discovery(discovery)
    records = []
    records.extend(prefix_plan_rows(networks, state))
    records.extend(cluster_plan_rows(clusters, state))
    records.extend(host_plan_row(x, device_indexes, state) for x in hosts)
    records.extend(vm_plan_row(x, vi, state) for x in vms)

    # Dependentes nunca podem ficar READY quando o cluster autoritativo está
    # em REVIEW. Isso impede associar host/VM a um cluster homônimo do tipo
    # errado enquanto a linha de cluster é corretamente ignorada.
    bad_clusters = set(
        (norm(x.get("provider")), norm(x.get("name")))
        for x in records
        if x.get("object_type") == "CLUSTER" and x.get("decision") != "READY"
    )
    if bad_clusters:
        for row in records:
            if row.get("object_type") not in ("HOST", "VM") or not clean(row.get("cluster")):
                continue
            if (norm(row.get("provider")), norm(row.get("cluster"))) in bad_clusters:
                row["decision"] = "REVIEW"
                extra = "cluster dependente não está READY: {0}".format(row.get("cluster"))
                row["reason"] = (clean(row.get("reason")) + "; " if clean(row.get("reason")) else "") + extra

    duplicate_keys = set()
    for duplicate in discovery.get("duplicate_identities") or []:
        kind = duplicate.get("kind")
        identity = duplicate.get("identity")
        duplicate_keys.add((kind, identity))
    if duplicate_keys:
        for row in records:
            identity = norm_serial(row.get("serial"))
            if identity and (row.get("object_type"), identity) in duplicate_keys:
                row["decision"] = "REVIEW"
                row["reason"] = "identidade duplicada entre sources"

    desired_ips = defaultdict(list)
    desired_macs = defaultdict(list)
    for row in records:
        if row.get("object_type") not in ("HOST", "VM"):
            continue
        for spec in row.get("interfaces") or []:
            if spec.get("ip"):
                desired_ips[spec.get("ip")].append(row)
            mac = norm_mac(spec.get("mac"))
            if mac:
                desired_macs[mac].append(row)
    for ip, owners in desired_ips.items():
        unique = set(x.get("asset_id") for x in owners)
        if len(unique) > 1:
            for row in owners:
                row["decision"] = "REVIEW"
                row["reason"] = (clean(row.get("reason")) + "; " if clean(row.get("reason")) else "") + "IP duplicado no inventário hypervisor: {0}".format(ip)
    for mac, owners in desired_macs.items():
        unique = set(x.get("asset_id") for x in owners)
        if len(unique) > 1:
            for row in owners:
                row["decision"] = "REVIEW"
                row["reason"] = (clean(row.get("reason")) + "; " if clean(row.get("reason")) else "") + "MAC duplicado no inventário hypervisor: {0}".format(mac)

    desired_names = defaultdict(list)
    for row in records:
        if row.get("object_type") == "HOST" and clean(row.get("desired_name")):
            desired_names[("HOST", norm(row.get("desired_name")), norm(discovery.get("site")))].append(row)
        elif row.get("object_type") == "VM" and clean(row.get("desired_name")):
            scope = norm(row.get("cluster")) or norm(row.get("host_name")) or norm(discovery.get("site"))
            desired_names[("VM", norm(row.get("desired_name")), scope)].append(row)
    for key, owners in desired_names.items():
        unique = set(x.get("asset_id") for x in owners)
        if len(unique) > 1:
            for row in owners:
                row["decision"] = "REVIEW"
                row["reason"] = (clean(row.get("reason")) + "; " if clean(row.get("reason")) else "") + "nome duplicado no inventário hypervisor/escopo: {0}".format(row.get("desired_name"))

    decisions = Counter(x.get("decision") for x in records)
    actions = Counter(x.get("action") for x in records)
    ready_actions = Counter(x.get("action") for x in records if x.get("decision") == "READY")
    plan = {
        "stage": "HYPERVISOR_PLAN",
        "engine_version": ENGINE_VERSION,
        "generated_at": utc_now(),
        "tenant": discovery.get("tenant"),
        "site": discovery.get("site"),
        "source_discovery": "",
        "records": records,
        "decision_summary": dict(decisions),
        "action_summary": dict(actions),
        "ready_action_summary": dict(ready_actions),
        "netbox_write": False,
    }
    ensure_reports_dir()
    path = os.path.join(REPORTS, "{0}-hypervisor-plan-{1}.json".format(discovery.get("site") or "SITE", utc_stamp()))
    with open(path, "w") as handle:
        json.dump(plan, handle, indent=2, sort_keys=True)
    print("===== HYPERVISOR PLAN =====")
    print("Objetos planejados: {0}".format(len(records)))
    print("READY: {0} REVIEW: {1} BLOCKED: {2}".format(decisions.get("READY", 0), decisions.get("REVIEW", 0), decisions.get("BLOCKED", 0)))
    print("Ações totais: CREATE={0} UPDATE_SAFE={1} NOOP={2}".format(actions.get("CREATE", 0), actions.get("UPDATE_SAFE", 0), actions.get("NOOP", 0)))
    print("ELEGÍVEIS PARA ESCRITA (READY): {0}".format(decisions.get("READY", 0)))
    print("  READY/CREATE: {0}".format(ready_actions.get("CREATE", 0)))
    print("  READY/UPDATE_SAFE: {0}".format(ready_actions.get("UPDATE_SAFE", 0)))
    print("  READY/NOOP: {0}".format(ready_actions.get("NOOP", 0)))
    print("NetBox write: NÃO")
    print("JSON: {0}".format(path))
    return plan, path


class HypervisorCatalog(object):
    def __init__(self, nb, state, events):
        self.nb = nb
        self.state = state
        self.events = events
        self.physical = Catalog(nb, True, events)

    def ensure_vm_role(self, name):
        exact = [obj for obj in self.state["roles"] if norm(obj.get("name")) == norm(name)]
        if len(exact) > 1:
            raise RuntimeError("Role de VM duplicada no NetBox: {0}".format(name))
        if exact:
            if exact[0].get("vm_role") is False:
                raise RuntimeError("Role {0} existe mas não permite Virtual Machines".format(name))
            return exact[0]
        slug = slugify(name)
        collision = [obj for obj in self.state["roles"] if norm(obj.get("slug")) == norm(slug)]
        if collision:
            raise RuntimeError("Slug de Role de VM em uso: {0}".format(slug))
        obj = self.nb.post("dcim/device-roles/", {"name": name, "slug": slug, "color": "607d8b", "vm_role": True})
        self.state["roles"].append(obj)
        self.events.append({"phase": "CATALOG", "object_type": "VM_ROLE", "action": "CREATED", "name": name, "object_id": obj.get("id"), "detail": slug})
        return obj

    def ensure_cluster_type(self, provider):
        name = cluster_provider_name(provider)
        exact = [obj for obj in self.state["cluster_types"] if norm(obj.get("name")) == norm(name)]
        if len(exact) > 1:
            raise RuntimeError("Cluster Type duplicado: {0}".format(name))
        if exact:
            return exact[0]
        slug = slugify(name)
        if any(norm(obj.get("slug")) == norm(slug) for obj in self.state["cluster_types"]):
            raise RuntimeError("Slug de Cluster Type em uso: {0}".format(slug))
        obj = self.nb.post("virtualization/cluster-types/", {"name": name, "slug": slug})
        self.state["cluster_types"].append(obj)
        self.events.append({"phase": "CATALOG", "object_type": "CLUSTER_TYPE", "action": "CREATED", "name": name, "object_id": obj.get("id"), "detail": ""})
        return obj

    def ensure_platform(self, name):
        return self.physical.ensure_platform(name)


def ensure_prefix(nb, state, row, events):
    prefix = row.get("prefix")
    exact = [x for x in state["prefixes"] if clean(x.get("prefix")) == clean(prefix)]
    if exact:
        events.append({"phase": "PREFIX", "object_type": "PREFIX", "action": "PRESERVED", "name": prefix, "object_id": exact[0].get("id"), "detail": ""})
        return exact[0]
    obj = nb.post("ipam/prefixes/", {
        "prefix": prefix,
        "status": "active",
        "tenant": state["tenant"]["id"],
        "scope_type": "dcim.site",
        "scope_id": state["site"]["id"],
        "description": "Gerenciado pelo netbox-discovery",
    })
    state["prefixes"].append(obj)
    events.append({"phase": "PREFIX", "object_type": "PREFIX", "action": "CREATED", "name": prefix, "object_id": obj.get("id"), "detail": ""})
    return obj


def ensure_cluster(nb, state, catalog, row, events):
    name = row.get("name")
    for obj in state["clusters"]:
        if norm(obj.get("name")) == norm(name) and cluster_scope_site_id(obj) in (None, state["site"]["id"]):
            current_type = nested_name(obj.get("type"))
            expected_type = cluster_provider_name(row.get("provider"))
            if current_type and norm(current_type) != norm(expected_type):
                raise RuntimeError("Tipo do cluster {0} diverge: NetBox={1} API={2}".format(name, current_type, expected_type))
            events.append({"phase": "CLUSTER", "object_type": "CLUSTER", "action": "PRESERVED", "name": name, "object_id": obj.get("id"), "detail": ""})
            return obj
    ctype = catalog.ensure_cluster_type(row.get("provider"))
    obj = nb.post("virtualization/clusters/", {
        "name": name,
        "type": ctype["id"],
        "status": "active",
        "tenant": state["tenant"]["id"],
        "scope_type": "dcim.site",
        "scope_id": state["site"]["id"],
        "description": "Descoberto pelo netbox-discovery hypervisor",
    })
    state["clusters"].append(obj)
    events.append({"phase": "CLUSTER", "object_type": "CLUSTER", "action": "CREATED", "name": name, "object_id": obj.get("id"), "detail": row.get("provider")})
    return obj


def mac_value(row):
    return clean(row.get("mac_address") or row.get("mac"))


def mac_assigned_id(row):
    ao = row.get("assigned_object") or {}
    if isinstance(ao, dict) and ao.get("id"):
        return ao.get("id")
    return row.get("assigned_object_id")


def ensure_mac(nb, state, interface, mac, assigned_type, events):
    mac = norm_mac(mac)
    if not mac or not interface.get("id"):
        return None
    matches = [x for x in state["macs"] if norm_mac(mac_value(x)) == mac]
    if len(matches) > 1:
        raise RuntimeError("MAC duplicado no NetBox: {0}".format(mac))
    if matches:
        obj = matches[0]
        aoid = mac_assigned_id(obj)
        atype = clean(obj.get("assigned_object_type"))
        if aoid and (aoid != interface.get("id") or atype != assigned_type):
            raise RuntimeError("MAC {0} já pertence a {1} ID {2}".format(mac, atype, aoid))
        if not aoid:
            obj = nb.patch("dcim/mac-addresses/{0}/".format(obj["id"]), {"assigned_object_type": assigned_type, "assigned_object_id": interface["id"]})
        events.append({"phase": "MAC", "object_type": "MAC_ADDRESS", "action": "PRESERVED", "name": mac, "object_id": obj.get("id"), "detail": clean(interface.get("name"))})
    else:
        obj = nb.post("dcim/mac-addresses/", {
            "mac_address": mac,
            "assigned_object_type": assigned_type,
            "assigned_object_id": interface["id"],
            "description": "Descoberto pelo netbox-discovery hypervisor",
        })
        state["macs"].append(obj)
        events.append({"phase": "MAC", "object_type": "MAC_ADDRESS", "action": "CREATED", "name": mac, "object_id": obj.get("id"), "detail": clean(interface.get("name"))})
    if obj.get("id") and not nested_id(interface.get("primary_mac_address")):
        if assigned_type == "dcim.interface":
            interface = nb.patch("dcim/interfaces/{0}/".format(interface["id"]), {"primary_mac_address": obj["id"]})
        else:
            interface = nb.patch("virtualization/interfaces/{0}/".format(interface["id"]), {"primary_mac_address": obj["id"]})
    return obj


def get_vm_interface(nb, vm_id, name, mac=""):
    rows = query(nb, "virtualization/interfaces/", virtual_machine_id=vm_id, limit=1000)
    if mac:
        for row in rows:
            primary = row.get("primary_mac_address") or {}
            candidates = [norm_mac(primary.get("mac_address") if isinstance(primary, dict) else "")]
            for m in row.get("mac_addresses") or []:
                if isinstance(m, dict):
                    candidates.append(norm_mac(m.get("mac_address")))
            if norm_mac(mac) and norm_mac(mac) in candidates:
                return row
    exact = [x for x in rows if norm(x.get("name")) == norm(name)]
    if len(exact) > 1:
        raise RuntimeError("VM interface duplicada: VM {0} / {1}".format(vm_id, name))
    return exact[0] if exact else None


def ensure_vm_interface(nb, vm, spec, events):
    name = clean(spec.get("name")) or "eth0"
    current = get_vm_interface(nb, vm["id"], name, spec.get("mac"))
    if current:
        events.append({"phase": "VM_INTERFACE", "object_type": "VM_INTERFACE", "action": "PRESERVED", "name": clean(current.get("name")), "object_id": current.get("id"), "detail": clean(vm.get("name"))})
        return current
    obj = nb.post("virtualization/interfaces/", {
        "virtual_machine": vm["id"],
        "name": name,
        "enabled": True,
        "description": "Descoberto pelo netbox-discovery hypervisor" + ((" | " + clean(spec.get("network"))) if clean(spec.get("network")) else ""),
    })
    events.append({"phase": "VM_INTERFACE", "object_type": "VM_INTERFACE", "action": "CREATED", "name": name, "object_id": obj.get("id"), "detail": clean(vm.get("name"))})
    return obj


def ensure_vm_ip(nb, state, vm, interface, spec, events):
    ip = norm_ip(spec.get("ip"))
    address = clean(spec.get("address"))
    if not ip or not address:
        return None
    matches = [x for x in state["ips"] if norm_ip(x.get("address")) == ip]
    if len(matches) > 1:
        raise RuntimeError("IP duplicado no NetBox: {0}".format(ip))
    if matches:
        obj = matches[0]
        tenant_id = nested_id(obj.get("tenant"))
        if tenant_id and tenant_id != state["tenant"]["id"]:
            raise RuntimeError("IP {0} pertence a outro tenant".format(ip))
        atype = clean(obj.get("assigned_object_type"))
        aoid = assigned_object_id(obj)
        if aoid and (atype != "virtualization.vminterface" or aoid != interface.get("id")):
            raise RuntimeError("IP {0} já pertence a {1} ID {2}".format(ip, atype, aoid))
        if not aoid:
            payload = {"assigned_object_type": "virtualization.vminterface", "assigned_object_id": interface["id"]}
            if not tenant_id:
                payload["tenant"] = state["tenant"]["id"]
            obj = nb.patch("ipam/ip-addresses/{0}/".format(obj["id"]), payload)
        events.append({"phase": "VM_IP", "object_type": "IP_ADDRESS", "action": "PRESERVED", "name": address, "object_id": obj.get("id"), "detail": clean(vm.get("name"))})
        return obj
    obj = nb.post("ipam/ip-addresses/", {
        "address": address,
        "status": "active",
        "tenant": state["tenant"]["id"],
        "assigned_object_type": "virtualization.vminterface",
        "assigned_object_id": interface["id"],
        "description": "Descoberto pelo netbox-discovery hypervisor",
    })
    state["ips"].append(obj)
    events.append({"phase": "VM_IP", "object_type": "IP_ADDRESS", "action": "CREATED", "name": address, "object_id": obj.get("id"), "detail": clean(vm.get("name"))})
    return obj


def host_map_key(source_id, name):
    return (norm(source_id), norm(name))


def cluster_map_key(provider, name):
    return (norm(provider), norm(name))


def vm_safe_patch(row, current, catalog, cluster_obj, host_obj):
    payload = {}
    if clean(row.get("serial")) and not clean(current.get("serial")):
        payload["serial"] = clean(row.get("serial"))
    status_obj = current.get("status") or {}
    cur_status = status_obj.get("value") if isinstance(status_obj, dict) else clean(status_obj)
    if clean(row.get("status")) and clean(cur_status) != clean(row.get("status")):
        payload["status"] = row.get("status")
    if row.get("vcpus"):
        try:
            if abs(float(row.get("vcpus")) - float(current.get("vcpus") or 0)) > 0.01:
                payload["vcpus"] = row.get("vcpus")
        except Exception:
            pass
    if row.get("memory_mb"):
        if int(float(row.get("memory_mb"))) != int(float(current.get("memory") or 0)):
            payload["memory"] = int(float(row.get("memory_mb")))
    if row.get("disk_mb"):
        if abs(float(row.get("disk_mb")) - float(current.get("disk") or 0)) > 0.01:
            payload["disk"] = int(float(row.get("disk_mb")))
    if not nested_id(current.get("role")):
        payload["role"] = catalog.ensure_vm_role("CONTAINER" if row.get("kind") == "container" else "VIRTUAL MACHINE")["id"]
    if clean(row.get("platform")) and not nested_id(current.get("platform")):
        payload["platform"] = catalog.ensure_platform(row.get("platform"))["id"]
    if cluster_obj and not nested_id(current.get("cluster")):
        payload["cluster"] = cluster_obj["id"]
    if host_obj:
        current_device_id = nested_id(current.get("device"))
        if not current_device_id or (clean(row.get("cluster")) and current_device_id != host_obj.get("id")):
            payload["device"] = host_obj["id"]
    return payload


def find_current_vm(row, state):
    indexes = vm_indexes(state)
    current, match_state, reason = match_vm(row, indexes, state)
    if match_state == "CONFLICT":
        raise RuntimeError("VM {0}: {1}".format(row.get("desired_name"), reason))
    return current


def create_vm(nb, state, catalog, row, cluster_obj, host_obj, events):
    role = catalog.ensure_vm_role("CONTAINER" if row.get("kind") == "container" else "VIRTUAL MACHINE")
    payload = {
        "name": row.get("desired_name"),
        "status": row.get("status") or "offline",
        "tenant": state["tenant"]["id"],
        "role": role["id"],
        "description": "Descoberto pelo netbox-discovery hypervisor ({0})".format(row.get("provider")),
    }
    if row.get("serial"):
        payload["serial"] = row.get("serial")
    if row.get("platform"):
        payload["platform"] = catalog.ensure_platform(row.get("platform"))["id"]
    if row.get("vcpus"):
        payload["vcpus"] = row.get("vcpus")
    if row.get("memory_mb"):
        payload["memory"] = int(float(row.get("memory_mb")))
    if row.get("disk_mb"):
        payload["disk"] = int(float(row.get("disk_mb")))
    if cluster_obj:
        payload["cluster"] = cluster_obj["id"]
    if host_obj:
        payload["device"] = host_obj["id"]
    if not cluster_obj and not host_obj:
        payload["site"] = state["site"]["id"]
    obj = nb.post("virtualization/virtual-machines/", payload)
    state["vms"].append(obj)
    events.append({"phase": "VM", "object_type": "VIRTUAL_MACHINE", "action": "CREATED", "name": payload["name"], "object_id": obj.get("id"), "detail": row.get("provider")})
    return obj


def catalog_preflight(nb, state, ready):
    events = []
    physical = Catalog(nb, False, events)
    for row in ready:
        if row.get("object_type") == "HOST":
            physical.ensure_role(clean(row.get("target_role")))
            physical.ensure_device_type(clean(row.get("manufacturer")), clean(row.get("model")))
            if clean(row.get("platform")):
                physical.ensure_platform(clean(row.get("platform")))
        elif row.get("object_type") == "VM" and clean(row.get("platform")):
            physical.ensure_platform(clean(row.get("platform")))
    # VM roles and Cluster Types are validated by PLAN, but validate again against live state.
    for role_name in set("CONTAINER" if r.get("kind") == "container" else "VIRTUAL MACHINE" for r in ready if r.get("object_type") == "VM"):
        exact = [x for x in state["roles"] if norm(x.get("name")) == norm(role_name)]
        if len(exact) > 1:
            raise RuntimeError("Role de VM duplicada: {0}".format(role_name))
        if exact and exact[0].get("vm_role") is False:
            raise RuntimeError("Role {0} existe mas não permite Virtual Machines".format(role_name))
        if not exact:
            slug = slugify(role_name)
            if any(norm(x.get("slug")) == norm(slug) for x in state["roles"]):
                raise RuntimeError("Slug de Role de VM em uso: {0}".format(slug))
    for row in ready:
        if row.get("object_type") != "CLUSTER":
            continue
        name = cluster_provider_name(row.get("provider"))
        exact = [x for x in state["cluster_types"] if norm(x.get("name")) == norm(name)]
        if len(exact) > 1:
            raise RuntimeError("Cluster Type duplicado: {0}".format(name))
        if not exact:
            slug = slugify(name)
            if any(norm(x.get("slug")) == norm(slug) for x in state["cluster_types"]):
                raise RuntimeError("Slug de Cluster Type em uso: {0}".format(slug))
    return True


def apply_plan(discovery, plan, nb=None):
    nb = nb or NetBox()
    state = state_from_netbox(nb, discovery.get("tenant"), discovery.get("site"))
    networks = [ipaddress.ip_network(x, strict=False) for x in discovery.get("networks") or []]
    ready = [x for x in plan.get("records") or [] if x.get("decision") == "READY"]
    review = [x for x in plan.get("records") or [] if x.get("decision") == "REVIEW"]
    print("===== HYPERVISOR IMPORT =====")
    print("Modo: APPLY - ESCRITA REAL")
    print("READY: {0}".format(len(ready)))
    print("REVIEW ignorados: {0}".format(len(review)))

    # Re-plan against the live state before first write. Any new REVIEW aborts the batch.
    live_plan, _ = build_plan(discovery, nb=nb)
    new_review = [x for x in live_plan.get("records") or [] if x.get("decision") == "REVIEW"]
    original_review_ids = set(x.get("asset_id") for x in review)
    unexpected = [x for x in new_review if x.get("asset_id") not in original_review_ids]
    if unexpected:
        raise RuntimeError("PREFLIGHT: {0} novo(s) conflito(s); nenhuma escrita iniciada".format(len(unexpected)))
    catalog_preflight(nb, state, ready)
    print("PREFLIGHT: OK")

    events = []
    errors = []
    summary = Counter()
    catalog = HypervisorCatalog(nb, state, events)
    cluster_map = {}
    host_map = {}

    # Prefixes first: establish the base network only from explicit site networks.
    for row in ready:
        if row.get("object_type") != "PREFIX":
            continue
        try:
            ensure_prefix(nb, state, row, events)
            summary["prefixes"] += 1
        except Exception as exc:
            errors.append({"asset_id": row.get("asset_id"), "error": str(exc)})
            raise

    for row in ready:
        if row.get("object_type") != "CLUSTER":
            continue
        try:
            obj = ensure_cluster(nb, state, catalog, row, events)
            cluster_map[cluster_map_key(row.get("provider"), row.get("name"))] = obj
            summary["clusters"] += 1
        except Exception as exc:
            errors.append({"asset_id": row.get("asset_id"), "error": str(exc)})
            raise

    # Include clusters which were NOOP but still needed for host/VM association.
    for cluster in state["clusters"]:
        for provider in ("vmware", "proxmox", "hyperv"):
            cluster_map.setdefault(cluster_map_key(provider, cluster.get("name")), cluster)

    device_indexes = build_indexes(state["devices"], state["ips"])
    physical_catalog = catalog.physical

    for row in ready:
        if row.get("object_type") != "HOST":
            continue
        try:
            current, match_state, reason = rematch_record(row, device_indexes)
            if match_state == "CONFLICT":
                raise RuntimeError(reason)
            if current is None:
                current = create_device(nb, True, row, state["tenant"], state["site"], physical_catalog, events)
                state["devices"].append(current)
                summary["hosts_created"] += 1
            else:
                patch = safe_patch_for_existing(row, current, physical_catalog)
                cluster_obj = cluster_map.get(cluster_map_key(row.get("provider"), row.get("cluster"))) if row.get("cluster") else None
                if cluster_obj and not nested_id(current.get("cluster")):
                    patch["cluster"] = cluster_obj["id"]
                if patch:
                    current = nb.patch("dcim/devices/{0}/".format(current["id"]), patch)
                    summary["hosts_updated"] += 1
                    events.append({"phase": "HOST", "object_type": "DEVICE", "action": "UPDATED_SAFE", "name": clean(current.get("name")), "object_id": current.get("id"), "detail": json.dumps(patch, sort_keys=True)})
                else:
                    summary["hosts_preserved"] += 1
            # A newly created host also needs cluster association (create_device does not set it).
            cluster_obj = cluster_map.get(cluster_map_key(row.get("provider"), row.get("cluster"))) if row.get("cluster") else None
            if cluster_obj and not nested_id(current.get("cluster")):
                current = nb.patch("dcim/devices/{0}/".format(current["id"]), {"cluster": cluster_obj["id"]})
            # Refresh indexes before IP operations.
            device_indexes = build_indexes(state["devices"], state["ips"])
            for spec in row.get("interfaces") or []:
                interface = existing_interface_for_spec(state, spec, "dcim.interface", current.get("id"))
                if interface:
                    events.append({"phase": "INTERFACE", "object_type": "INTERFACE", "action": "PRESERVED", "name": clean(interface.get("name")), "object_id": interface.get("id"), "detail": clean(current.get("name"))})
                else:
                    interface = ensure_interface(nb, True, current, spec, events)
                if spec.get("mac"):
                    ensure_mac(nb, state, interface, spec.get("mac"), "dcim.interface", events)
                if spec.get("ip") and spec.get("address"):
                    ip_obj = ensure_ip(nb, True, state["tenant"], current, interface, spec, device_indexes["ip_objects"], networks, events)
                    if ip_obj and ip_obj.get("id") and not any(x.get("id") == ip_obj.get("id") for x in state["ips"]):
                        state["ips"].append(ip_obj)
                    if spec.get("primary") and ip_obj and ip_obj.get("id"):
                        field = "primary_ip6" if ":" in spec.get("ip", "") else "primary_ip4"
                        if not nested_id(current.get(field)):
                            current = nb.patch("dcim/devices/{0}/".format(current["id"]), {field: ip_obj["id"]})
            host_map[host_map_key(row.get("source_id"), row.get("desired_name"))] = current
            summary["hosts_processed"] += 1
        except Exception as exc:
            errors.append({"asset_id": row.get("asset_id"), "error": str(exc)})
            raise

    # Map existing/preserved hosts by source host name even when the HOST row was NOOP.
    current_device_indexes = build_indexes(state["devices"], state["ips"])
    for row in plan.get("records") or []:
        if row.get("object_type") != "HOST" or row.get("decision") != "READY":
            continue
        current, match_state, _ = rematch_record(row, current_device_indexes)
        if current:
            host_map[host_map_key(row.get("source_id"), row.get("desired_name"))] = current

    for row in ready:
        if row.get("object_type") != "VM":
            continue
        try:
            cluster_obj = cluster_map.get(cluster_map_key(row.get("provider"), row.get("cluster"))) if row.get("cluster") else None
            host_obj = host_map.get(host_map_key(row.get("source_id"), row.get("host_name"))) if row.get("host_name") else None
            current = find_current_vm(row, state)
            if current is None:
                current = create_vm(nb, state, catalog, row, cluster_obj, host_obj, events)
                summary["vms_created"] += 1
            else:
                patch = vm_safe_patch(row, current, catalog, cluster_obj, host_obj)
                if patch:
                    current = nb.patch("virtualization/virtual-machines/{0}/".format(current["id"]), patch)
                    summary["vms_updated"] += 1
                    events.append({"phase": "VM", "object_type": "VIRTUAL_MACHINE", "action": "UPDATED_SAFE", "name": clean(current.get("name")), "object_id": current.get("id"), "detail": json.dumps(patch, sort_keys=True)})
                else:
                    summary["vms_preserved"] += 1
            primary_ip4 = None
            primary_ip6 = None
            for spec in row.get("interfaces") or []:
                interface = existing_interface_for_spec(state, spec, "virtualization.vminterface", current.get("id"))
                if interface:
                    events.append({"phase": "VM_INTERFACE", "object_type": "VM_INTERFACE", "action": "PRESERVED", "name": clean(interface.get("name")), "object_id": interface.get("id"), "detail": clean(current.get("name"))})
                else:
                    interface = ensure_vm_interface(nb, current, spec, events)
                if spec.get("mac"):
                    ensure_mac(nb, state, interface, spec.get("mac"), "virtualization.vminterface", events)
                if spec.get("ip") and spec.get("address"):
                    ip_obj = ensure_vm_ip(nb, state, current, interface, spec, events)
                    if spec.get("primary") and ip_obj:
                        if ":" in spec.get("ip", ""):
                            primary_ip6 = ip_obj
                        else:
                            primary_ip4 = ip_obj
            if primary_ip4 and primary_ip4.get("id") and not nested_id(current.get("primary_ip4")):
                current = nb.patch("virtualization/virtual-machines/{0}/".format(current["id"]), {"primary_ip4": primary_ip4["id"]})
            if primary_ip6 and primary_ip6.get("id") and not nested_id(current.get("primary_ip6")):
                current = nb.patch("virtualization/virtual-machines/{0}/".format(current["id"]), {"primary_ip6": primary_ip6["id"]})
            summary["vms_processed"] += 1
        except Exception as exc:
            errors.append({"asset_id": row.get("asset_id"), "error": str(exc)})
            raise

    ensure_reports_dir()
    path = os.path.join(REPORTS, "{0}-hypervisor-import-{1}.json".format(discovery.get("site") or "SITE", utc_stamp()))
    with open(path, "w") as handle:
        json.dump({
            "stage": "HYPERVISOR_IMPORT",
            "engine_version": ENGINE_VERSION,
            "generated_at": utc_now(),
            "site": discovery.get("site"),
            "tenant": discovery.get("tenant"),
            "summary": dict(summary),
            "review_ignored": len(review),
            "events": events,
            "errors": errors,
            "netbox_write": True,
        }, handle, indent=2, sort_keys=True)
    print("===== HYPERVISOR IMPORT RESULTADO =====")
    print("Hosts processados: {0}".format(summary.get("hosts_processed", 0)))
    print("VMs processadas: {0}".format(summary.get("vms_processed", 0)))
    print("Erros: {0}".format(len(errors)))
    print("NetBox write: SIM")
    print("JSON: {0}".format(path))
    return path


def audit(discovery, original_plan, nb=None):
    nb = nb or NetBox()
    post_plan, post_path = build_plan(discovery, nb=nb)
    original_ready = set(x.get("asset_id") for x in original_plan.get("records") or [] if x.get("decision") == "READY")
    checks = []
    fail = 0
    warn = 0
    for row in post_plan.get("records") or []:
        aid = row.get("asset_id")
        if aid not in original_ready:
            continue
        # After APPLY, objects which originally required CREATE/UPDATE should be idempotent.
        if row.get("decision") != "READY":
            checks.append({"asset_id": aid, "status": "FAIL", "detail": row.get("reason")})
            fail += 1
        elif row.get("action") == "NOOP":
            checks.append({"asset_id": aid, "status": "PASS", "detail": "idempotente"})
        else:
            checks.append({"asset_id": aid, "status": "WARN", "detail": "ação residual: {0}".format(row.get("action"))})
            warn += 1
    status = "PASS" if not fail and not warn else ("PASS_WITH_WARNINGS" if not fail else "FAIL")
    ensure_reports_dir()
    path = os.path.join(REPORTS, "{0}-hypervisor-audit-{1}.json".format(discovery.get("site") or "SITE", utc_stamp()))
    with open(path, "w") as handle:
        json.dump({
            "stage": "HYPERVISOR_AUDIT",
            "engine_version": ENGINE_VERSION,
            "generated_at": utc_now(),
            "status": status,
            "checks": checks,
            "summary": dict(Counter(x.get("status") for x in checks)),
            "post_plan": post_path,
            "netbox_write": False,
        }, handle, indent=2, sort_keys=True)
    sm = Counter(x.get("status") for x in checks)
    print("===== HYPERVISOR AUDIT =====")
    print("Status: {0}".format(status))
    print("PASS: {0} WARN: {1} FAIL: {2}".format(sm.get("PASS", 0), sm.get("WARN", 0), sm.get("FAIL", 0)))
    print("JSON: {0}".format(path))
    return status, path
