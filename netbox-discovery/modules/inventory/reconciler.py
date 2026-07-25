#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import argparse
import csv
import datetime
import glob
import hashlib
import ipaddress
import json
import os
import re
import sys
from collections import Counter, defaultdict

BASE = os.environ.get("NETBOX_DISCOVERY_BASE", "/opt/netbox-discovery")
REPORTS = os.path.join(BASE, "reports")
RECONCILER_VERSION = "2.2-product"


def clean(v): return "" if v is None else str(v).strip()

def latest(pattern):
    files = glob.glob(pattern)
    return max(files, key=os.path.getmtime) if files else ""

def ip_key(v):
    try: return int(ipaddress.ip_address(v))
    except Exception: return 0

def norm_mac(v):
    s = re.sub(r"[^0-9A-Fa-f]", "", clean(v)).upper()
    if len(s) != 12:
        return ""
    if s in ("000000000000", "FFFFFFFFFFFF"):
        return ""
    try:
        first_octet = int(s[:2], 16)
    except ValueError:
        return ""
    if first_octet & 1:
        return ""
    return ":".join(s[i:i+2] for i in range(0, 12, 2))

def norm_serial(v):
    s = re.sub(r"[^A-Za-z0-9]", "", clean(v)).upper()
    invalid = {
        "", "UNKNOWN", "NA", "NONE", "NULL", "DEFAULT",
        "SVCTAG", "SERVICETAG", "SERIAL", "SERIALNUMBER",
        "SYSTEMSERIALNUMBER", "CHASSISSERIALNUMBER",
        "NOTAVAILABLE", "NOTAPPLICABLE", "TOBEFILLEDBYOEM",
    }
    if s in invalid:
        return ""
    if len(s) >= 6 and (set(s) == set("0") or set(s) == set("F")):
        return ""
    return s

def norm_chassis(v):
    raw = clean(v).strip()
    if not raw:
        return ""
    # If LLDP chassis is a MAC, apply the same unicast/validity rules.
    mac = norm_mac(raw)
    if mac:
        return "MAC:" + mac
    try:
        ipaddress.ip_address(raw)
        return ""
    except Exception:
        pass
    compact = re.sub(r"[^A-Za-z0-9]", "", raw).upper()
    if compact in (
        "", "UNKNOWN", "NONE", "NULL", "DEFAULT",
        "000000000000", "FFFFFFFFFFFF",
    ):
        return ""
    if len(compact) < 4:
        return ""
    return "LOCAL:" + compact

def norm_name(v):
    s = clean(v).lower().rstrip(".")
    return s


class DSU(object):
    def __init__(self, n):
        self.p = list(range(n))
    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x
    def union(self, a, b):
        a, b = self.find(a), self.find(b)
        if a != b: self.p[b] = a


def identity_sets(r):
    macs = set()
    for m in [r.get("primary_mac"), r.get("snmp_bridge_mac")]:
        m = norm_mac(m)
        if m: macs.add(m)
    for m in r.get("interface_macs") or []:
        m = norm_mac(m)
        if m: macs.add(m)
    serial = norm_serial(r.get("serial"))
    chassis = norm_chassis(r.get("snmp_lldp_chassis_id"))
    return serial, macs, chassis


def merge_reason(a, b):
    sa, ma, ca = identity_sets(a)
    sb, mb, cb = identity_sets(b)
    if sa and sb and sa == sb:
        return "SERIAL:{0}".format(sa), 100
    overlap = ma & mb
    if overlap:
        return "MAC_OVERLAP:{0}".format(sorted(overlap)[0]), 100
    if ca and cb and ca == cb:
        return "LLDP_CHASSIS:{0}".format(ca), 98
    # SNMP reported IP table: if one record explicitly reports the other's IP and has compatible identity.
    aip = set(clean(x.get("address")) for x in (a.get("reported_ip_addresses") or []))
    bip = set(clean(x.get("address")) for x in (b.get("reported_ip_addresses") or []))
    if clean(b.get("ip")) in aip or clean(a.get("ip")) in bip:
        # Reported interface IP table is strong for one managed device; require same SNMP name/serial/mac when present.
        na, nb = norm_name(a.get("snmp_name")), norm_name(b.get("snmp_name"))
        if (na and nb and na == nb) or (sa and sb and sa == sb) or (ma & mb):
            return "SNMP_IP_TABLE", 96
    return "", 0


def candidate_reason(a, b):
    na, nb = norm_name(a.get("snmp_name") or a.get("hostname")), norm_name(b.get("snmp_name") or b.get("hostname"))
    generic = (
        "lynx", "cpu 412-2 pn/dp", "tps1 mib", "ecosys", "sms agente snmp",
        "nil", "localhost.localdomain", "motorola_solutions_default_pcr_ca_sha256rsa"
    )
    if na and nb and na == nb and na not in generic and a.get("role") == b.get("role"):
        return "SAME_NAME_AND_ROLE", 70
    return "", 0


def choose_primary(records):
    # Prefer non-OOB, high classification score, then SNMP/entity-rich and lowest IP.
    def score(r):
        return (
            0 if r.get("role") == "OOB_MANAGEMENT" else 1,
            int(r.get("classification_score") or 0),
            1 if norm_serial(r.get("serial")) else 0,
            1 if r.get("snmp_name") else 0,
            -ip_key(r.get("ip")),
        )
    return max(records, key=score)


def asset_id(records):
    """Return a deterministic and unique reconciliation identity.

    Strong identities (serial/MAC) remain stable across IP changes. When no
    strong identity exists, a hostname by itself is not globally unique: OT,
    printers and appliances often ship with the same default SNMP name. In
    that case include the primary IP so two independent assets can never
    collapse into the same product key merely because their names match.
    """
    serials = sorted(set(norm_serial(r.get("serial")) for r in records if norm_serial(r.get("serial"))))
    if serials:
        return "SERIAL:{0}".format(serials[0])
    macs = []
    for r in records:
        _, ms, _ = identity_sets(r)
        macs.extend(ms)
    macs = sorted(set(macs))
    if macs:
        return "MAC:{0}".format(macs[0])
    chassis_ids = sorted(set(
        identity_sets(r)[2]
        for r in records
        if identity_sets(r)[2]
    ))
    if chassis_ids:
        return "CHASSIS:{0}".format(chassis_ids[0])
    primary = choose_primary(records)
    ip = clean(primary.get("ip"))
    name = norm_name(primary.get("snmp_name") or primary.get("hostname"))
    if name and ip:
        return "NAME:{0}|IP:{1}".format(name, ip)
    return "IP:{0}".format(ip)


def build_assets(records):
    dsu = DSU(len(records))
    merge_edges = []
    candidates = []
    for i in range(len(records)):
        for j in range(i + 1, len(records)):
            reason, score = merge_reason(records[i], records[j])
            if reason:
                dsu.union(i, j)
                merge_edges.append({"ip_a": records[i]["ip"], "ip_b": records[j]["ip"], "reason": reason, "score": score})
            else:
                reason, score = candidate_reason(records[i], records[j])
                if reason:
                    candidates.append({"ip_a": records[i]["ip"], "ip_b": records[j]["ip"], "reason": reason, "score": score})
    groups = defaultdict(list)
    for i, r in enumerate(records): groups[dsu.find(i)].append(r)
    assets = []
    for g in groups.values():
        g.sort(key=lambda r: ip_key(r.get("ip")))
        primary = choose_primary(g)
        aid = asset_id(g)
        ips = [r.get("ip") for r in g]
        serials = sorted(set(norm_serial(r.get("serial")) for r in g if norm_serial(r.get("serial"))))
        macs = sorted(set(m for r in g for m in identity_sets(r)[1]))
        roles = [r.get("role") for r in g]
        role = primary.get("role")
        # If a group combines host + iDRAC, keep host role and record OOB IP separately.
        non_oob = [r for r in g if r.get("role") != "OOB_MANAGEMENT"]
        if non_oob:
            role = choose_primary(non_oob).get("role")
        oob_ips = [r.get("ip") for r in g if r.get("role") == "OOB_MANAGEMENT"]
        score = max(int(r.get("classification_score") or 0) for r in g)
        conf = "HIGH" if score >= 85 else ("MEDIUM" if score >= 55 else ("LOW" if score >= 30 else "NONE"))
        assets.append({
            "asset_id": aid,
            "primary_ip": primary.get("ip"),
            "ips": ips,
            "oob_ips": oob_ips,
            "hostname": primary.get("hostname") or primary.get("snmp_name") or "",
            "role": role,
            "manufacturer": primary.get("manufacturer") or "",
            "model": primary.get("model") or "",
            "serial": serials[0] if serials else "",
            "platform": primary.get("platform") or "",
            "asset_class": primary.get("asset_class") or "",
            "confidence": conf,
            "classification_score": score,
            "macs": macs,
            "record_count": len(g),
            "roles_seen": sorted(set(x for x in roles if x)),
            "reconciliation_status": "MERGED" if len(g) > 1 else "SINGLE",
            "netbox_write": False,
        })
    # Product invariant: every reconciled record must have a unique asset_id.
    # Never pass ambiguous keys downstream to PLAN/IMPORT/AUDIT.
    seen = defaultdict(list)
    for a in assets:
        seen[a.get("asset_id")].append(a.get("primary_ip"))
    collisions = dict((k, v) for k, v in seen.items() if k and len(v) > 1)
    if collisions:
        raise RuntimeError("asset_id duplicado após RECONCILE: {0}".format(collisions))

    assets.sort(key=lambda a: ip_key(a.get("primary_ip")))
    return assets, merge_edges, candidates


def main(argv=None):
    ap = argparse.ArgumentParser(description="netbox-discovery RECONCILE (read-only)")
    ap.add_argument("--input", default="", help="Classification JSON. Default: latest *-classification-*.json")
    ap.add_argument("--output-dir", default=REPORTS)
    args = ap.parse_args(argv)
    source = args.input or latest(os.path.join(REPORTS, "*-classification-*.json"))
    if not source or not os.path.isfile(source):
        raise RuntimeError("Nenhum classification JSON encontrado em {0}".format(REPORTS))
    with open(source, "r") as f: data = json.load(f)
    records = data.get("records") or []
    assets, edges, candidates = build_assets(records)
    site = clean(data.get("site")) or "SITE"
    stamp = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    base = os.path.join(args.output_dir, "{0}-reconciliation-{1}".format(site, stamp))
    jpath, cpath = base + ".json", base + ".csv"
    out = {
        "mode": "DRY-RUN", "stage": "RECONCILE", "reconciler_version": RECONCILER_VERSION,
        "source_classification": source, "client": clean(data.get("client")), "site": site,
        "input_records": len(records), "assets": len(assets),
        "merged_assets": sum(1 for a in assets if a["record_count"] > 1),
        "merge_edges": edges, "review_candidates": candidates, "records": assets, "netbox_write": False,
    }
    if not os.path.isdir(args.output_dir): os.makedirs(args.output_dir)
    with open(jpath, "w") as f: json.dump(out, f, indent=2, sort_keys=True)
    fields = ["asset_id", "primary_ip", "ips", "oob_ips", "hostname", "role", "manufacturer", "model", "serial", "platform", "asset_class", "confidence", "classification_score", "record_count", "reconciliation_status", "roles_seen", "macs"]
    with open(cpath, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
        for a in assets:
            r = dict(a)
            for k in ("ips", "oob_ips", "roles_seen", "macs"): r[k] = " | ".join(r.get(k) or [])
            w.writerow({k: r.get(k, "") for k in fields})
    print("===== RECONCILE =====")
    print("Origem: {0}".format(source))
    print("Registros de IP: {0}".format(len(records)))
    print("Assets reconciliados: {0}".format(len(assets)))
    print("Assets com múltiplos registros/IPs: {0}".format(out["merged_assets"]))
    print("Candidatos para revisão (não mesclados): {0}".format(len(candidates)))
    print("JSON: {0}".format(jpath)); print("CSV:  {0}".format(cpath)); print("NetBox write: NÃO")
    return 0

if __name__ == "__main__": sys.exit(main())
