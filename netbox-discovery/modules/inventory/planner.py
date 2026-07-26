#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import argparse
import csv
import datetime
import glob
import ipaddress
import json
import os
import re
import sys
import urllib.parse
from collections import Counter, defaultdict

BASE = os.environ.get("NETBOX_DISCOVERY_BASE", "/opt/netbox-discovery")
REPORTS = os.path.join(BASE, "reports")
PLANNER_VERSION = "3.4-product"

# Classifier roles are product-internal. PLAN translates them into NetBox roles.
ROLE_TARGETS = {
    "DOMAIN_CONTROLLER": "SERVER-WINDOWS",
    "CAMERA": "CAMERA",
    "DVR": "DVR",
    "FIREWALL": "FIREWALL",
    "HYPERVISOR": "HYPERVISOR",
    "INDUSTRIAL_COMMUNICATION": "INDUSTRIAL-DEVICE",
    "INDUSTRIAL_DEVICE": "INDUSTRIAL-DEVICE",
    "INDUSTRIAL_IO": "INDUSTRIAL-DEVICE",
    "INDUSTRIAL_PLC": "INDUSTRIAL-PLC",
    "INDUSTRIAL_POWER_METER": "INDUSTRIAL-DEVICE",
    "INDUSTRIAL_SWITCH": "INDUSTRIAL-SWITCH",
    "LINUX_HOST": "SERVER-LINUX-OR-APPLIANCE",
    "MANAGEMENT_APPLIANCE": "MANAGEMENT APPLIANCE",
    "NETWORK_SWITCH": "NETWORK SWITCH",
    "OOB_MANAGEMENT": "MANAGEMENT APPLIANCE",
    "POWER_MANAGEMENT": "POWER MANAGEMENT",
    "PRINTER": "PRINTER",
    "SECURITY_APPLIANCE": "SECURITY APPLIANCE",
    "SMS_GATEWAY": "SMS GATEWAY",
    "STORAGE": "STORAGE",
    "NVR": "NVR",
    "VIDEO_ENCODER": "VIDEO ENCODER",
    "VIDEO_SURVEILLANCE_DEVICE": "VIDEO SURVEILLANCE",
    "VMWARE_APPLIANCE": "MANAGEMENT APPLIANCE",
    "WEB_APPLIANCE": "SERVER-LINUX-OR-APPLIANCE",
    "WINDOWS_HOST": "SERVER-WINDOWS",
    "WIRELESS_AP": "WIRELESS ACCESS POINT",
    "WIRELESS_BRIDGE": "WIRELESS BRIDGE",
}


def clean(v):
    return "" if v is None else str(v).strip()


def norm(v):
    return re.sub(r"\s+", " ", clean(v)).strip().lower()


def norm_serial(v):
    return re.sub(r"[^A-Za-z0-9]", "", clean(v)).upper()


def norm_ip(v):
    s = clean(v)
    if not s:
        return ""
    try:
        return str(ipaddress.ip_interface(s).ip)
    except Exception:
        try:
            return str(ipaddress.ip_address(s.split("/")[0]))
        except Exception:
            return ""


def ip_key(v):
    try:
        return int(ipaddress.ip_address(norm_ip(v)))
    except Exception:
        return 0


def slugify(v):
    s = clean(v).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:100] or "item"


def latest(pattern):
    files = glob.glob(pattern)
    return max(files, key=os.path.getmtime) if files else ""


def canonical_name(asset):
    h = clean(asset.get("hostname")).strip(".")
    generic = {
        "", "localhost", "localhost.localdomain", "unknown", "sem nome", "nil", "none",
        "sysname not set", "sysname_not_set", "sysname-not-set", "not configured",
    }
    if h and norm(h) not in generic:
        try:
            ipaddress.ip_address(h)
        except Exception:
            return h.split(".")[0][:64]
    role = clean(asset.get("role")) or "DEVICE"
    ip = norm_ip(asset.get("primary_ip")) or (asset.get("ips") or ["0.0.0.0"])[0]
    return (role + "-" + ip.replace(".", "-").replace(":", "-"))[:64]

def prefix_length(netmask):
    try:
        return ipaddress.IPv4Network("0.0.0.0/{0}".format(netmask)).prefixlen
    except Exception:
        return None


def flatten_name(obj):
    if not obj:
        return ""
    if isinstance(obj, dict):
        return clean(obj.get("name") or obj.get("display") or obj.get("model"))
    return clean(obj)


def get_device_id_from_ip(ipr):
    ao = ipr.get("assigned_object") or {}
    if not isinstance(ao, dict):
        return None
    dev = ao.get("device") or {}
    if isinstance(dev, dict) and dev.get("id"):
        return dev.get("id")
    # Some serializers expose nested assigned object differently.
    if ipr.get("assigned_object_type") == "dcim.device" and ao.get("id"):
        return ao.get("id")
    return None


def query(nb, endpoint, **params):
    params = dict((k, v) for k, v in params.items() if v is not None and v != "")
    suffix = urllib.parse.urlencode(params)
    path = endpoint
    if suffix:
        path += ("&" if "?" in path else "?") + suffix
    return nb.get_all(path)


class SnapshotNetBox(object):
    """Offline adapter used only for product validation/tests."""
    MAP = {
        "tenancy/tenants/": "tenancy/tenants.json",
        "dcim/sites/": "dcim/sites.json",
        "dcim/devices/": "dcim/devices.json",
        "ipam/ip-addresses/": "ipam/ip-addresses.json",
        "dcim/device-roles/": "dcim/device-roles.json",
        "dcim/manufacturers/": "dcim/manufacturers.json",
        "dcim/device-types/": "dcim/device-types.json",
        "dcim/platforms/": "dcim/platforms.json",
    }
    def __init__(self, root):
        self.root = root
    def get_all(self, endpoint):
        base = endpoint.split("?", 1)[0]
        rel = self.MAP.get(base)
        if not rel:
            raise RuntimeError("Snapshot endpoint não suportado: {0}".format(base))
        with open(os.path.join(self.root, rel), "r") as f:
            data = json.load(f)
        rows = data.get("results", data) if isinstance(data, dict) else data
        # Apply only the filters PLAN relies on.
        qs = urllib.parse.parse_qs(endpoint.split("?", 1)[1] if "?" in endpoint else "")
        def keep(r):
            if "name" in qs and norm(r.get("name")) != norm(qs["name"][0]):
                return False
            if "tenant_id" in qs:
                t = r.get("tenant") or {}
                if str(t.get("id") or "") != str(qs["tenant_id"][0]):
                    return False
            if "site_id" in qs:
                s = r.get("site") or {}
                if str(s.get("id") or "") != str(qs["site_id"][0]):
                    return False
            return True
        return [r for r in rows if keep(r)]


def choose_named(rows, wanted, label):
    exact = [r for r in rows if norm(r.get("name")) == norm(wanted)]
    if len(exact) == 1:
        return exact[0]
    if not exact:
        raise RuntimeError("{0} não encontrado no NetBox: {1}".format(label, wanted))
    raise RuntimeError("{0} duplicado no NetBox: {1}".format(label, wanted))


def netbox_state(nb, client, site):
    tenants = query(nb, "tenancy/tenants/", name=client, limit=100)
    tenant = choose_named(tenants, client, "Tenant")
    sites = query(nb, "dcim/sites/", name=site, limit=100)
    site_obj = choose_named(sites, site, "Site")

    devices = query(nb, "dcim/devices/", tenant_id=tenant["id"], site_id=site_obj["id"], limit=1000)
    # IMPORTANT: IP uniqueness in the global table is not tenant-scoped.
    # Query every global-table IP so PLAN can see an address even when it has
    # no tenant (or another tenant) and avoid a later duplicate POST.
    ips = query(nb, "ipam/ip-addresses/", limit=10000)
    ips = [x for x in ips if not x.get("vrf")]
    roles = query(nb, "dcim/device-roles/", limit=1000)
    manufacturers = query(nb, "dcim/manufacturers/", limit=1000)
    device_types = query(nb, "dcim/device-types/", limit=1000)
    platforms = query(nb, "dcim/platforms/", limit=1000)

    # Keep foreign/global assignments visible. They are safety evidence:
    # PLAN must BLOCK/REVIEW them instead of pretending the address is free.
    return {
        "tenant": tenant, "site": site_obj, "devices": devices, "ips": ips,
        "roles": roles, "manufacturers": manufacturers,
        "device_types": device_types, "platforms": platforms,
    }


def build_indexes(state):
    serials = defaultdict(list)
    names = defaultdict(list)
    by_id = {}
    ip_to_devices = defaultdict(set)
    ip_objects = defaultdict(list)

    for d in state["devices"]:
        did = d.get("id")
        by_id[did] = d
        s = norm_serial(d.get("serial"))
        if s:
            serials[s].append(did)
        n = norm(d.get("name"))
        if n:
            names[n].append(did)
        for k in ("primary_ip", "primary_ip4", "oob_ip"):
            obj = d.get(k) or {}
            ip = norm_ip(obj.get("address") if isinstance(obj, dict) else obj)
            if ip:
                ip_to_devices[ip].add(did)

    for x in state["ips"]:
        ip = norm_ip(x.get("address"))
        if not ip:
            continue
        ip_objects[ip].append(x)
        did = get_device_id_from_ip(x)
        if did:
            ip_to_devices[ip].add(did)

    return {
        "serials": serials, "names": names, "by_id": by_id,
        "ip_to_devices": ip_to_devices, "ip_objects": ip_objects,
    }


def match_asset(asset, indexes, desired_name=None, allow_name_match=True):
    votes = []
    serial = norm_serial(asset.get("serial"))
    if serial:
        ids = set(indexes["serials"].get(serial, []))
        if ids:
            votes.append(("SERIAL", ids))

    ip_ids = set()
    for ip in (asset.get("ips") or []) + (asset.get("oob_ips") or []):
        ip_ids.update(indexes["ip_to_devices"].get(norm_ip(ip), set()))
    if ip_ids:
        votes.append(("IP", ip_ids))

    name = norm(desired_name if desired_name is not None else canonical_name(asset))
    if name and allow_name_match:
        ids = set(indexes["names"].get(name, []))
        if ids:
            votes.append(("NAME", ids))

    strong = set()
    for method, ids in votes:
        if method in ("SERIAL", "IP"):
            strong.update(ids)
    all_ids = set()
    for method, ids in votes:
        all_ids.update(ids)

    if len(strong) > 1:
        return None, "CONFLICT", "SERIAL/IP apontam para devices diferentes", votes
    if len(strong) == 1:
        did = list(strong)[0]
        # An IP may belong to a Device outside this tenant/site. That is a
        # conflict, never a match to a new local Device.
        if did not in indexes["by_id"]:
            return None, "CONFLICT", "IP aponta para device fora do tenant/site", votes
        # A name pointing elsewhere is drift/duplicate, not a safe auto-update.
        conflicting_name = [ids for method, ids in votes if method == "NAME" and did not in ids]
        if conflicting_name:
            return None, "CONFLICT", "Nome aponta para outro device", votes
        return did, "MATCHED", "+".join(method for method, ids in votes if did in ids), votes
    if len(all_ids) == 1:
        return list(all_ids)[0], "MATCHED", "NAME", votes
    if len(all_ids) > 1:
        return None, "CONFLICT", "Nome ambíguo", votes
    return None, "NEW", "Sem correspondência", votes


def target_role(asset):
    return ROLE_TARGETS.get(clean(asset.get("role")), clean(asset.get("role")))


def fallback_model(asset):
    manufacturer = clean(asset.get("manufacturer"))
    role = clean(asset.get("role"))
    exact = clean(asset.get("model"))
    if exact:
        return exact
    rules = {
        ("Dell", "HYPERVISOR"): "Unknown Dell Server",
        ("QNAP", "STORAGE"): "Generic Storage",
        ("Seagate", "STORAGE"): "Generic Storage",
        ("Ubiquiti", "WIRELESS_AP"): "Generic Wireless AP",
        ("HPE", "NETWORK_SWITCH"): "Generic Network Switch",
        ("HPE Aruba", "NETWORK_SWITCH"): "Generic Network Switch",
        ("Moxa", "INDUSTRIAL_SWITCH"): "Industrial Switch",
        ("Westermo", "INDUSTRIAL_SWITCH"): "Industrial Switch",
        ("Siemens", "INDUSTRIAL_PLC"): "PLC",
        ("Siemens", "INDUSTRIAL_SWITCH"): "Industrial Device",
        ("Siemens", "INDUSTRIAL_DEVICE"): "Industrial Device",
    }
    if (manufacturer, role) in rules:
        return rules[(manufacturer, role)]
    if role in ("WINDOWS_HOST", "DOMAIN_CONTROLLER", "LINUX_HOST", "WEB_APPLIANCE"):
        return "Unknown Server"
    if role == "CAMERA":
        return "Generic IP Camera"
    if role == "NVR":
        return "Generic NVR"
    if role == "DVR":
        return "Generic DVR"
    if role == "VIDEO_ENCODER":
        return "Generic Video Encoder"
    if role == "VIDEO_SURVEILLANCE_DEVICE":
        return "Generic Video Surveillance Device"
    if role == "PRINTER":
        return "Generic Printer"
    if role:
        return "Generic " + role.replace("_", " ").title()
    return "Generic Device"


def target_manufacturer(asset):
    m = clean(asset.get("manufacturer"))
    if m:
        return m
    role = clean(asset.get("role"))
    if role in ("WINDOWS_HOST", "LINUX_HOST", "WEB_APPLIANCE", "DOMAIN_CONTROLLER"):
        return "Generic"
    return "Unidentified"


def existing_catalog(state):
    roles = dict((norm(x.get("name")), x) for x in state["roles"])
    manufacturers = dict((norm(x.get("name")), x) for x in state["manufacturers"])
    platforms = dict((norm(x.get("name")), x) for x in state["platforms"])
    types = {}
    for x in state["device_types"]:
        m = flatten_name(x.get("manufacturer"))
        types[(norm(m), norm(x.get("model")))] = x
    return roles, manufacturers, platforms, types


def desired_interfaces(asset, classification_records):
    """Only plan management/OOB interfaces that are backed by an observed IP.
    Do not expand every switch port merely because IF-MIB exposed it.
    """
    by_ip = dict((norm_ip(r.get("ip")), r) for r in classification_records)
    rows = []
    used_names = set()
    ordered_ips = []
    for ip in asset.get("ips") or []:
        nip = norm_ip(ip)
        if nip and nip not in ordered_ips:
            ordered_ips.append(nip)
    for ip in asset.get("oob_ips") or []:
        nip = norm_ip(ip)
        if nip and nip not in ordered_ips:
            ordered_ips.append(nip)

    for pos, ip in enumerate(ordered_ips):
        rec = by_ip.get(ip) or {}
        is_oob = ip in [norm_ip(x) for x in asset.get("oob_ips") or []] or rec.get("role") == "OOB_MANAGEMENT"
        if is_oob:
            name = "iDRAC" if clean(asset.get("manufacturer")) == "Dell" else "OOB"
        else:
            name = "MGMT" if pos == 0 else "MGMT-{0}".format(pos + 1)

        # Exact SNMP ifIndex mapping, when present, wins over a synthetic name.
        mappings = rec.get("reported_ip_addresses") or []
        # classifier doesn't carry full snmp_interfaces, so preserve deterministic fallback here.
        if name in used_names:
            name = name + "-{0}".format(pos + 1)
        used_names.add(name)

        mask = ""
        ifindex = ""
        for m in mappings:
            if norm_ip(m.get("address")) == ip:
                mask = clean(m.get("netmask"))
                ifindex = clean(m.get("ifindex"))
                break
        plen = prefix_length(mask)
        address = ip + ("/{0}".format(plen) if plen is not None else "")
        rows.append({
            "name": name, "ip": ip, "address": address, "ifindex": ifindex,
            "mgmt_only": bool(is_oob), "kind": "OOB" if is_oob else "MGMT",
            "primary": ip == norm_ip(asset.get("primary_ip")),
        })
    return rows


def build_plan(recon, classification, state):
    indexes = build_indexes(state)
    roles_catalog, manufacturers_catalog, platforms_catalog, types_catalog = existing_catalog(state)
    review_ips = set()
    for c in recon.get("review_candidates") or []:
        review_ips.add(norm_ip(c.get("ip_a")))
        review_ips.add(norm_ip(c.get("ip_b")))

    class_records = classification.get("records") or []
    class_by_ip = dict((norm_ip(r.get("ip")), r) for r in class_records)

    assets = recon.get("records") or []
    raw_names = [canonical_name(a) for a in assets]
    raw_name_count = Counter(norm(x) for x in raw_names if norm(x))

    prereq = {"roles": {}, "manufacturers": {}, "platforms": {}, "device_types": {}}
    plan = []
    desired_name_seen = defaultdict(list)
    desired_serial_seen = defaultdict(list)

    for asset, raw_name in zip(assets, raw_names):
        ips = [norm_ip(x) for x in asset.get("ips") or [] if norm_ip(x)]
        conf = clean(asset.get("confidence"))
        role_internal = clean(asset.get("role"))
        t_role = target_role(asset)
        t_mfg = target_manufacturer(asset)
        t_model = fallback_model(asset)
        t_platform = clean(asset.get("platform"))
        dname = raw_name
        serial = clean(asset.get("serial"))
        duplicate_raw_name = raw_name_count.get(norm(raw_name), 0) > 1
        in_reconcile_review = any(ip in review_ips for ip in ips)
        # Repeated SNMP sysName/model strings are common (e.g. "lynx", "CPU 412-2 PN/DP").
        # Keep a real reconciliation conflict untouched, but make generic repeated names unique
        # instead of blocking a whole site.
        if duplicate_raw_name and not in_reconcile_review:
            suffix_ip = norm_ip(asset.get("primary_ip")) or (ips[0] if ips else "")
            if suffix_ip:
                dname = (raw_name + "-" + suffix_ip.replace(".", "-").replace(":", "-"))[:64]

        desired_name_seen[norm(dname)].append(asset.get("asset_id"))
        if norm_serial(serial):
            desired_serial_seen[norm_serial(serial)].append(asset.get("asset_id"))

        did, match_state, match_reason, votes = match_asset(
            asset, indexes, desired_name=dname, allow_name_match=not duplicate_raw_name
        )
        current = indexes["by_id"].get(did) if did else None
        reasons = []
        decision = "READY"
        action = "CREATE" if not current else "NOOP"

        if in_reconcile_review:
            decision = "REVIEW"
            reasons.append("RECONCILE_REVIEW_CANDIDATE")
        if conf != "HIGH":
            decision = "REVIEW"
            reasons.append("CONFIDENCE_{0}".format(conf or "NONE"))
        if role_internal == "UNKNOWN":
            decision = "REVIEW"
            reasons.append("UNKNOWN_ROLE")
        if role_internal == "OOB_MANAGEMENT" and not current:
            decision = "REVIEW"
            reasons.append("STANDALONE_OOB_NEEDS_PARENT")
        if match_state == "CONFLICT":
            decision = "BLOCKED"
            action = "CONFLICT"
            reasons.append("IDENTITY_CONFLICT")
            reasons.append(match_reason)

        # Catalog prerequisites are generated even for review records so the report is complete,
        # but importers must only consume READY records.
        if t_role and norm(t_role) not in roles_catalog:
            prereq["roles"][norm(t_role)] = {"name": t_role, "slug": slugify(t_role)}
        if t_mfg and norm(t_mfg) not in manufacturers_catalog:
            prereq["manufacturers"][norm(t_mfg)] = {"name": t_mfg, "slug": slugify(t_mfg)}
        if t_platform and norm(t_platform) not in platforms_catalog:
            prereq["platforms"][norm(t_platform)] = {"name": t_platform, "slug": slugify(t_platform)}
        type_key = (norm(t_mfg), norm(t_model))
        if t_model and type_key not in types_catalog:
            prereq["device_types"]["{0}|{1}".format(type_key[0], type_key[1])] = {
                "manufacturer": t_mfg, "model": t_model, "slug": slugify(t_mfg + "-" + t_model)
            }

        diffs = []
        if current and match_state == "MATCHED":
            # Only safe/fill-only changes are auto-ready. Conflicting non-empty inventory is review.
            cur_serial = clean(current.get("serial"))
            if serial and not cur_serial:
                diffs.append("serial:SET:{0}".format(serial))
            elif serial and cur_serial and norm_serial(serial) != norm_serial(cur_serial):
                decision = "REVIEW" if decision != "BLOCKED" else decision
                reasons.append("SERIAL_DRIFT")

            cur_role = flatten_name(current.get("role"))
            if t_role and not cur_role:
                diffs.append("role:SET:{0}".format(t_role))
            elif t_role and cur_role and norm(t_role) != norm(cur_role):
                # Preserve existing non-empty role; report drift instead of overwriting it blindly.
                reasons.append("ROLE_DRIFT:{0}->{1}".format(cur_role, t_role))

            cur_platform = flatten_name(current.get("platform"))
            if t_platform and not cur_platform:
                diffs.append("platform:SET:{0}".format(t_platform))
            elif t_platform and cur_platform and norm(t_platform) != norm(cur_platform):
                reasons.append("PLATFORM_DRIFT:{0}->{1}".format(cur_platform, t_platform))

            cur_dt = current.get("device_type") or {}
            cur_model = clean(cur_dt.get("model") if isinstance(cur_dt, dict) else "")
            cur_mfg = flatten_name(cur_dt.get("manufacturer") if isinstance(cur_dt, dict) else "")
            if cur_model and t_model and (norm(cur_model) != norm(t_model) or (cur_mfg and norm(cur_mfg) != norm(t_mfg))):
                # Exact serial + better model evidence is useful, but model replacement can be destructive.
                reasons.append("DEVICE_TYPE_DRIFT:{0}/{1}->{2}/{3}".format(cur_mfg, cur_model, t_mfg, t_model))

            if diffs:
                action = "UPDATE_SAFE"
            else:
                action = "NOOP"

        # IP intents: PLAN only; importer will ENSURE idempotently.
        source_records = [class_by_ip.get(ip, {}) for ip in ips]
        iface_intents = desired_interfaces(asset, source_records)
        ip_intents = []
        for interface in iface_intents:
            ip = interface["ip"]
            existing_ip = indexes["ip_objects"].get(ip, [])
            assigned_ids = set(get_device_id_from_ip(x) for x in existing_ip if get_device_id_from_ip(x))
            if current and did in assigned_ids:
                ip_action = "NOOP"
            elif existing_ip and assigned_ids and (not current or did not in assigned_ids):
                ip_action = "CONFLICT"
                decision = "BLOCKED"
                reasons.append("IP_ASSIGNED_TO_OTHER_DEVICE:{0}".format(ip))
            elif existing_ip:
                # An address already attached to a VM interface or another non-DCIM
                # object must never be converted into a physical Device automatically.
                external_types = sorted(set(
                    clean(x.get("assigned_object_type"))
                    for x in existing_ip
                    if clean(x.get("assigned_object_type")) and not get_device_id_from_ip(x)
                ))
                if external_types:
                    ip_action = "EXTERNAL_ASSIGNED"
                    if decision != "BLOCKED":
                        decision = "REVIEW"
                    reasons.append(
                        "IP_ASSIGNED_TO_EXTERNAL_OBJECT:{0}:{1}".format(
                            ip, ",".join(external_types)
                        )
                    )
                else:
                    ip_action = "ASSIGN_EXISTING"
            else:
                ip_action = "ENSURE"
            ip_intents.append(dict(interface, action=ip_action))

        plan.append({
            "asset_id": clean(asset.get("asset_id")),
            "decision": decision, "action": action,
            "match_state": match_state, "match_reason": match_reason,
            "existing_device_id": did,
            "existing_device_name": clean(current.get("name")) if current else "",
            "desired_name": dname,
            "primary_ip": norm_ip(asset.get("primary_ip")),
            "ips": ips,
            "oob_ips": [norm_ip(x) for x in asset.get("oob_ips") or [] if norm_ip(x)],
            "role": role_internal, "target_role": t_role,
            "manufacturer": t_mfg, "model": t_model,
            "serial": serial, "platform": t_platform,
            "confidence": conf, "classification_score": asset.get("classification_score"),
            "reconciliation_status": clean(asset.get("reconciliation_status")),
            "reasons": sorted(set(reasons)), "safe_diffs": diffs,
            "interfaces": iface_intents, "ip_intents": ip_intents,
            "netbox_write": False,
        })

    # In-plan duplicates are never safe to import automatically.
    duplicated_names = set(k for k, v in desired_name_seen.items() if k and len(v) > 1)
    duplicated_serials = set(k for k, v in desired_serial_seen.items() if k and len(v) > 1)
    for row in plan:
        if norm(row["desired_name"]) in duplicated_names:
            row["decision"] = "BLOCKED"
            row["reasons"] = sorted(set(row["reasons"] + ["DUPLICATE_DESIRED_NAME"]))
        if norm_serial(row["serial"]) in duplicated_serials and norm_serial(row["serial"]):
            row["decision"] = "BLOCKED"
            row["reasons"] = sorted(set(row["reasons"] + ["DUPLICATE_DESIRED_SERIAL"]))

    # Catalog prerequisites should only be auto-applied if at least one READY record needs them.
    for category in prereq:
        prereq[category] = sorted(prereq[category].values(), key=lambda x: json.dumps(x, sort_keys=True))
    return plan, prereq


def main(argv=None):
    ap = argparse.ArgumentParser(description="netbox-discovery PLAN (read-only)")
    ap.add_argument("--input", default="", help="Reconciliation JSON. Default: latest report")
    ap.add_argument("--classification", default="", help="Classification JSON. Default: source from reconciliation")
    ap.add_argument("--output-dir", default=REPORTS)
    ap.add_argument("--snapshot-dir", default="", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    source = args.input or latest(os.path.join(REPORTS, "*-reconciliation-*.json"))
    if not source or not os.path.isfile(source):
        raise RuntimeError("Nenhum reconciliation JSON encontrado em {0}".format(REPORTS))
    with open(source, "r") as f:
        recon = json.load(f)

    class_source = args.classification or clean(recon.get("source_classification"))
    if not class_source or not os.path.isfile(class_source):
        class_source = latest(os.path.join(REPORTS, "*-classification-*.json"))
    if not class_source or not os.path.isfile(class_source):
        raise RuntimeError("Nenhum classification JSON encontrado")
    with open(class_source, "r") as f:
        classification = json.load(f)

    client = clean(recon.get("client"))
    site = clean(recon.get("site"))
    if not client or not site:
        raise RuntimeError("Reconciliation sem client/site")

    if args.snapshot_dir:
        nb = SnapshotNetBox(args.snapshot_dir)
    else:
        sys.path.insert(0, BASE)
        from lib.netbox import NetBox
        nb = NetBox()

    state = netbox_state(nb, client, site)
    plan, prereq = build_plan(recon, classification, state)

    summary = Counter(x["decision"] for x in plan)
    actions = Counter(x["action"] for x in plan)
    ready_actions = Counter(x["action"] for x in plan if x.get("decision") == "READY")
    ip_actions = Counter(i["action"] for x in plan for i in x.get("ip_intents") or [])
    stamp = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    if not os.path.isdir(args.output_dir):
        os.makedirs(args.output_dir)
    base = os.path.join(args.output_dir, "{0}-plan-{1}".format(site, stamp))
    jpath, cpath = base + ".json", base + ".csv"

    out = {
        "mode": "DRY-RUN", "stage": "PLAN", "planner_version": PLANNER_VERSION,
        "client": client, "site": site, "source_reconciliation": source,
        "source_classification": class_source,
        "netbox_snapshot": {
            "tenant_id": state["tenant"].get("id"), "site_id": state["site"].get("id"),
            "devices_at_site": len(state["devices"]), "tenant_ip_addresses": len(state["ips"]),
        },
        "total_assets": len(plan), "decision_summary": dict(summary),
        "action_summary": dict(actions), "ready_action_summary": dict(ready_actions),
        "ip_action_summary": dict(ip_actions),
        "prerequisites": prereq, "records": plan, "netbox_write": False,
        "policy": {
            "automatic_write_eligibility": "READY only",
            "non_high_confidence": "REVIEW",
            "unknown_role": "REVIEW",
            "standalone_oob": "REVIEW unless matched to an existing device",
            "identity_or_ip_conflict": "BLOCKED",
            "existing_nonempty_drift": "report, do not overwrite blindly",
        },
    }
    with open(jpath, "w") as f:
        json.dump(out, f, indent=2, sort_keys=True)

    fields = [
        "decision", "action", "asset_id", "existing_device_id", "existing_device_name",
        "desired_name", "primary_ip", "ips", "oob_ips", "role", "target_role",
        "manufacturer", "model", "serial", "platform", "confidence",
        "classification_score", "match_state", "match_reason", "reasons", "safe_diffs",
    ]
    with open(cpath, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for x in plan:
            r = dict(x)
            for k in ("ips", "oob_ips", "reasons", "safe_diffs"):
                r[k] = " | ".join(clean(v) for v in r.get(k) or [])
            w.writerow(dict((k, r.get(k, "")) for k in fields))

    print("===== PLAN =====")
    print("Origem RECONCILE: {0}".format(source))
    print("NetBox: {0} devices atuais no site".format(len(state["devices"])))
    print("Assets planejados: {0}".format(len(plan)))
    print("READY: {0}".format(summary.get("READY", 0)))
    print("REVIEW: {0}".format(summary.get("REVIEW", 0)))
    print("BLOCKED: {0}".format(summary.get("BLOCKED", 0)))
    print("Ações totais (incluem REVIEW/BLOCKED):")
    print("  CREATE: {0}".format(actions.get("CREATE", 0)))
    print("  UPDATE_SAFE: {0}".format(actions.get("UPDATE_SAFE", 0)))
    print("  NOOP: {0}".format(actions.get("NOOP", 0)))
    print("ELEGÍVEIS PARA ESCRITA (READY): {0}".format(summary.get("READY", 0)))
    print("  READY/CREATE: {0}".format(ready_actions.get("CREATE", 0)))
    print("  READY/UPDATE_SAFE: {0}".format(ready_actions.get("UPDATE_SAFE", 0)))
    print("  READY/NOOP: {0}".format(ready_actions.get("NOOP", 0)))
    print("JSON: {0}".format(jpath))
    print("CSV:  {0}".format(cpath))
    print("NetBox write: NÃO")
    return 0


if __name__ == "__main__":
    sys.exit(main())
