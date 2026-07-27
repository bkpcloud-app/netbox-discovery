#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import concurrent.futures
import csv
import datetime
import json
import os
import socket
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("NETBOX_DISCOVERY_BASE", os.path.abspath(os.path.join(HERE, "..", "..")))
REPORTS = os.path.join(BASE, "reports")
if HERE not in sys.path:
    sys.path.insert(0, HERE)
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import classifier as base

CLASSIFIER_VERSION = "3.0-product"
SPECIAL_TCP_PORTS = (3570, 51000)
TOPDATA_OUI = "00:18:E2"

ORIG_NORMALIZE_MANUFACTURER = base.normalize_manufacturer
ORIG_CLASSIFY_ROLE = base.classify_role
ORIG_INFER_MANUFACTURER = base.infer_manufacturer
ORIG_INFER_MODEL = base.infer_model
ORIG_ASSET_CLASS = base.asset_class
ORIG_CLASSIFY_DEVICE = base.classify_device
ORIG_WRITE_OUTPUTS = base.write_outputs


def clean(v):
    return "" if v is None else str(v).strip()


def _normalized_macs(d):
    values = []
    for value in (d.get("mac"), d.get("snmp_bridge_mac")):
        mac = base.norm_mac(value)
        if mac and mac not in values:
            values.append(mac)
    for row in d.get("snmp_interface_macs") or []:
        mac = base.norm_mac(row.get("mac"))
        if mac and mac not in values:
            values.append(mac)
    return values


def derive_management_mac(d):
    """Prefer the MAC of the SNMP interface that owns the discovered IP."""
    target_ip = clean(d.get("ip"))
    ifindex = ""
    for row in d.get("snmp_ip_addresses") or []:
        if clean(row.get("address")) == target_ip:
            ifindex = clean(row.get("ifindex"))
            break
    if ifindex:
        for row in d.get("snmp_interface_macs") or []:
            if clean(row.get("index")) == ifindex:
                mac = base.norm_mac(row.get("mac"))
                if mac:
                    return mac, "snmp-ip-ifindex"
    mac = base.norm_mac(d.get("mac"))
    if mac:
        return mac, "l2-observed"
    return "", ""


def _secondary_macs(d, management_mac):
    return sorted(set(x for x in _normalized_macs(d) if x and x != management_mac))


def _has_topdata_mac(d):
    return any(mac.startswith(TOPDATA_OUI) for mac in _normalized_macs(d))


def normalize_manufacturer(v):
    raw = clean(v)
    low = raw.lower()
    extra = [
        (("topdata", "inner"), "Topdata"),
        (("epson",), "Epson"),
        (("canon",), "Canon"),
        (("kyocera", "ecosys"), "Kyocera"),
        (("ricoh",), "Ricoh"),
        (("lexmark",), "Lexmark"),
        (("xerox",), "Xerox"),
        (("zebra",), "Zebra Technologies"),
        (("oki", "oki data"), "OKI"),
        (("hewlett-packard", "hewlett packard", "hp inc", "hp laserjet", "jetdirect"), "HP"),
    ]
    for terms, target in extra:
        if any(term in low for term in terms):
            return target
    return ORIG_NORMALIZE_MANUFACTURER(v)


def classify_role(d, text):
    tcp = base.ports(d, "tcp")
    low = clean(text).lower()
    topdata = _has_topdata_mac(d) or "topdata" in low or "inner " in low

    # OUI sozinho identifica fabricante, nunca função.
    if topdata and any(term in low for term in (
        "catraca", "turnstile", "controlecatraca", "catraca revolution",
    )):
        return "TURNSTILE", 98, ["Topdata/Inner turnstile fingerprint"]
    if topdata and any(term in low for term in (
        "inner rep", "rep plus", "inner 373", "pontto", "relogio de ponto",
        "relógio de ponto", "time attendance",
    )):
        return "TIME_ATTENDANCE", 98, ["Topdata/Inner time-attendance fingerprint"]
    if topdata and 51000 in tcp:
        return "TIME_ATTENDANCE", 92, ["Topdata identity + TCP/51000"]
    if topdata and any(term in low for term in ("inner acesso", "controle de acesso", "access control")):
        return "ACCESS_CONTROL", 97, ["Topdata/Inner access-control fingerprint"]
    if topdata and 3570 in tcp:
        return "ACCESS_CONTROL", 90, ["Topdata identity + TCP/3570"]

    return ORIG_CLASSIFY_ROLE(d, text)


def infer_manufacturer(d, text, ent, role):
    if _has_topdata_mac(d):
        return "Topdata", "mac-oui"
    low = clean(text).lower()
    if "topdata" in low or "inner " in low:
        return "Topdata", "device-fingerprint"
    manufacturer, source = ORIG_INFER_MANUFACTURER(d, text, ent, role)
    return normalize_manufacturer(manufacturer), source


def infer_model(d, text, ent, role):
    model, source = ORIG_INFER_MODEL(d, text, ent, role)
    if model:
        return model, source
    if role in ("TIME_ATTENDANCE", "ACCESS_CONTROL", "TURNSTILE"):
        patterns = [
            r"(Inner\s+REP\s+Plus)",
            r"(Inner\s+373)",
            r"(Inner\s+Acesso)",
            r"(Catraca\s+Revolution[^\r\n,;]*)",
            r"(Pontto[^\r\n,;]*)",
        ]
        found = base.first_match(patterns, text)
        if found:
            return found[:120], "fingerprint"
    return "", ""


def asset_class(d, role, text):
    if role in ("TIME_ATTENDANCE", "ACCESS_CONTROL", "TURNSTILE"):
        return "PHYSICAL_DEVICE"
    return ORIG_ASSET_CLASS(d, role, text)


def classify_device(d):
    old_norm = base.normalize_manufacturer
    old_role = base.classify_role
    old_mfg = base.infer_manufacturer
    old_model = base.infer_model
    old_asset = base.asset_class
    try:
        base.normalize_manufacturer = normalize_manufacturer
        base.classify_role = classify_role
        base.infer_manufacturer = infer_manufacturer
        base.infer_model = infer_model
        base.asset_class = asset_class
        base.CLASSIFIER_VERSION = CLASSIFIER_VERSION
        out = ORIG_CLASSIFY_DEVICE(d)
    finally:
        base.normalize_manufacturer = old_norm
        base.classify_role = old_role
        base.infer_manufacturer = old_mfg
        base.infer_model = old_model
        base.asset_class = old_asset

    mgmt, source = derive_management_mac(d)
    out["classification_version"] = CLASSIFIER_VERSION
    out["management_mac"] = mgmt
    out["management_mac_source"] = source
    out["secondary_macs"] = _secondary_macs(d, mgmt)
    return out


def _probe_one(item):
    ip, port = item
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.35)
    try:
        return ip, port, sock.connect_ex((ip, port)) == 0
    except Exception:
        return ip, port, False
    finally:
        try:
            sock.close()
        except Exception:
            pass


def enrich_special_ports(records):
    targets = []
    by_ip = {}
    for row in records:
        ip = clean(row.get("ip"))
        if not ip:
            continue
        by_ip[ip] = row
        existing = set()
        for svc in row.get("open_services") or []:
            if clean(svc.get("protocol")).lower() == "tcp":
                try:
                    existing.add(int(svc.get("port") or 0))
                except Exception:
                    pass
        for port in SPECIAL_TCP_PORTS:
            if port not in existing:
                targets.append((ip, port))
    if not targets:
        return
    workers = min(32, max(1, len(targets)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for ip, port, opened in pool.map(_probe_one, targets):
            if not opened:
                continue
            row = by_ip.get(ip)
            if row is None:
                continue
            row.setdefault("open_services", []).append({
                "port": port, "protocol": "tcp", "service": "unknown",
                "product": "", "version": "", "extrainfo": "", "hostname": "",
                "ostype": "", "devicetype": "", "tunnel": "", "method": "connect",
                "confidence": "", "cpes": [], "scripts": {},
                "scan_sources": ["identity-v2-special-port"],
            })


def write_outputs(source, report, output_dir):
    site = clean(report.get("site")) or "SITE"
    stamp = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    out_base = os.path.join(output_dir, "{0}-classification-{1}".format(site, stamp))
    jpath, cpath = out_base + ".json", out_base + ".csv"
    raw_devices = report.get("devices") or []
    enrich_special_ports(raw_devices)
    devices = [classify_device(x) for x in raw_devices]
    devices.sort(key=lambda x: base.ip_key(x.get("ip")))
    from collections import Counter
    roles = Counter(x["role"] for x in devices)
    conf = Counter(x["confidence"] for x in devices)
    data = {
        "mode": "DRY-RUN", "stage": "CLASSIFY",
        "classification_version": CLASSIFIER_VERSION,
        "source_discovery": source, "client": clean(report.get("client")), "site": site,
        "total": len(devices), "role_summary": dict(sorted(roles.items())),
        "confidence_summary": dict(sorted(conf.items())), "records": devices,
        "netbox_write": False,
    }
    with open(jpath, "w") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
    fields = [
        "ip", "hostname", "role", "manufacturer", "model", "serial", "platform", "asset_class",
        "classification_score", "confidence", "classification_state", "evidence_level",
        "management_mac", "management_mac_source", "primary_mac", "secondary_macs",
        "snmp_name", "snmp_object_id", "hostname_source", "manufacturer_source", "model_source",
        "serial_source", "evidence",
    ]
    with open(cpath, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in devices:
            row = dict(item)
            row["evidence"] = " | ".join(item.get("evidence") or [])
            row["secondary_macs"] = " | ".join(item.get("secondary_macs") or [])
            writer.writerow(dict((key, row.get(key, "")) for key in fields))
    return jpath, cpath, data


def main(argv=None):
    old_write = base.write_outputs
    old_classify = base.classify_device
    try:
        base.write_outputs = write_outputs
        base.classify_device = classify_device
        base.CLASSIFIER_VERSION = CLASSIFIER_VERSION
        return base.main(argv)
    finally:
        base.write_outputs = old_write
        base.classify_device = old_classify


if __name__ == "__main__":
    sys.exit(main())
