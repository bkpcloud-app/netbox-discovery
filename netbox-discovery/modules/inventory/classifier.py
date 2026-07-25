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
from collections import Counter

BASE = os.environ.get("NETBOX_DISCOVERY_BASE", "/opt/netbox-discovery")
REPORTS = os.path.join(BASE, "reports")
CLASSIFIER_VERSION = "2.0-product"


def clean(v):
    return "" if v is None else str(v).strip()


def norm_mac(v):
    s = re.sub(r"[^0-9A-Fa-f]", "", clean(v)).upper()
    if len(s) != 12 or s == "000000000000":
        return ""
    return ":".join(s[i:i+2] for i in range(0, 12, 2))


def ip_key(v):
    try:
        return int(ipaddress.ip_address(v))
    except Exception:
        return 0


def latest(pattern):
    files = glob.glob(pattern)
    return max(files, key=os.path.getmtime) if files else ""


def all_text(d):
    parts = [
        d.get("reverse_dns"), d.get("mac_vendor"), d.get("snmp_name"),
        d.get("snmp_description"), d.get("snmp_object_id"),
        d.get("snmp_lldp_name"), d.get("snmp_lldp_description"),
    ]
    ep = d.get("snmp_entity_primary") or {}
    for k in ("description", "name", "manufacturer", "model", "serial", "software_rev"):
        parts.append(ep.get(k))
    for e in d.get("snmp_entity_inventory") or []:
        for k in ("description", "name", "manufacturer", "model", "serial", "software_rev"):
            parts.append(e.get(k))
    for s in d.get("open_services") or []:
        for k in ("service", "product", "version", "extrainfo", "hostname", "ostype", "devicetype", "tunnel"):
            parts.append(s.get(k))
        parts.extend(s.get("cpes") or [])
        for k, v in (s.get("scripts") or {}).items():
            parts.append(k)
            parts.append(v)
    # Nmap OS guesses are intentionally excluded from strong classification text.
    # A deep scan may return several mutually incompatible matches with similar accuracy.
    return " ".join(clean(x) for x in parts if clean(x)).lower()


def ports(d, proto=None):
    out = set()
    for s in d.get("open_services") or []:
        if proto and clean(s.get("protocol")).lower() != proto:
            continue
        try:
            p = int(s.get("port") or 0)
        except Exception:
            p = 0
        if p > 0:
            out.add(p)
    return out


def script_values(d, name):
    vals = []
    for s in d.get("open_services") or []:
        v = (s.get("scripts") or {}).get(name)
        if v:
            vals.append(clean(v))
    return vals


def first_match(patterns, text, flags=re.I):
    for p in patterns:
        m = re.search(p, text or "", flags)
        if m:
            return clean(m.group(1))
    return ""


def normalize_manufacturer(v):
    s = clean(v)
    l = s.lower()
    if not s:
        return ""
    rules = [
        (("fortinet",), "Fortinet"),
        (("dell",), "Dell"),
        (("hewlett packard enterprise", "hpe networking", "aruba"), "HPE Aruba"),
        (("hewlett packard", " hp "), "HPE"),
        (("ubiquiti", "ubnt"), "Ubiquiti"),
        (("qnap",), "QNAP"),
        (("seagate", "segate"), "Seagate"),
        (("siemens",), "Siemens"),
        (("moxa",), "Moxa"),
        (("westermo",), "Westermo"),
        (("schneider", "apc"), "APC by Schneider Electric"),
        (("brother",), "Brother"),
        (("samsung",), "Samsung"),
        (("pantum",), "Pantum"),
        (("cisco",), "Cisco"),
        (("vmware",), "VMware"),
        (("microsoft",), "Microsoft"),
    ]
    padded = " " + l + " "
    for terms, target in rules:
        if any(t in l or t in padded for t in terms):
            return target
    return s[:80]


def entity_identity(d):
    candidates = []
    ep = d.get("snmp_entity_primary") or {}
    if ep:
        candidates.append(ep)
    for e in d.get("snmp_entity_inventory") or []:
        if e not in candidates:
            candidates.append(e)
    # Prefer chassis/container entries with actual identity.
    candidates.sort(key=lambda e: (
        0 if clean(e.get("serial")) else 1,
        0 if clean(e.get("manufacturer")) else 1,
        0 if clean(e.get("model")) else 1,
        0 if clean(e.get("class_id")) in ("3", "4") else 1,
    ))
    for e in candidates:
        serial = clean(e.get("serial"))
        manufacturer = clean(e.get("manufacturer"))
        model = clean(e.get("model"))
        desc = clean(e.get("description"))
        if serial or manufacturer or model:
            return {
                "serial": serial,
                "manufacturer": normalize_manufacturer(manufacturer),
                "model": model or desc,
                "description": desc,
            }
    return {"serial": "", "manufacturer": "", "model": "", "description": ""}


def certificate_common_names(d):
    out = []
    for cert in script_values(d, "ssl-cert"):
        for pat in (r"Subject:\s*commonName=([^/\r\n]+)", r"DNS:([^,\r\n]+)"):
            for m in re.finditer(pat, cert, re.I):
                v = clean(m.group(1))
                if v and v not in out:
                    out.append(v)
    return out


def hostname_candidates(d):
    c = []
    def add(value, source, score):
        v = clean(value).strip(".")
        if not v or v.lower() in ("localhost", "localhost.localdomain", "unknown", "sem nome", "nil", "none"):
            return
        # Ignore IP-as-hostname.
        try:
            ipaddress.ip_address(v)
            return
        except Exception:
            pass
        if not any(x[0].lower() == v.lower() for x in c):
            c.append((v, source, score))

    add(d.get("snmp_name"), "snmp-name", 100)
    add(d.get("snmp_lldp_name"), "lldp-name", 95)
    add(d.get("reverse_dns"), "reverse-dns", 90)
    for s in d.get("open_services") or []:
        add(s.get("hostname"), "nmap-service-hostname", 75)
    for txt in script_values(d, "rdp-ntlm-info"):
        add(first_match([r"DNS_Computer_Name:\s*([^\s]+)"], txt), "rdp-dns-name", 92)
        add(first_match([r"NetBIOS_Computer_Name:\s*([^\s]+)"], txt), "rdp-netbios-name", 88)
    for txt in script_values(d, "nbstat"):
        add(first_match([r"NetBIOS name:\s*([^,\s]+)"], txt), "netbios-name", 85)
    for cn in certificate_common_names(d):
        cl = cn.lower()
        if (cl not in ("qnap nas",) and "default" not in cl and not cl.startswith("ca")
                and "_ca" not in cl and " ca " not in (" " + cl + " ")):
            add(cn, "tls-common-name", 65)
    c.sort(key=lambda x: -x[2])
    return c


def idrac_serial(d):
    text = " ".join(certificate_common_names(d))
    return first_match([r"idrac[-_]?([a-z0-9]+)"], text)


def infer_manufacturer(d, text, ent):
    # High-confidence signatures before ENTITY/MAC vendor because some devices put part numbers in entPhysicalMfgName.
    sigs = [
        (("fortigate", "fortinet", "enterprises.12356"), "Fortinet"),
        (("idrac", "restgui/start.html", "integrated dell remote access controller"), "Dell"),
        (("hpe networking instant on", "aruba instant on"), "HPE Aruba"),
        (("1920-", "v1910", "officeconnect switch"), "HPE"),
        (("ubiquiti", "ubnt", "u7-pro", "u6-lr", "uap-"), "Ubiquiti"),
        (("qnap", "ts-431", "ts-x41"), "QNAP"),
        (("seagate", "nas-ba02"), "Seagate"),
        (("siemens", "simatic", "pac4200"), "Siemens"),
        (("moxa", "eds-405", "eds-408"), "Moxa"),
        (("westermo", "westermo lynx"), "Westermo"),
        (("apc", "network management card"), "APC by Schneider Electric"),
        (("brother",), "Brother"), (("pantum",), "Pantum"), (("samsung",), "Samsung"),
    ]
    for terms, target in sigs:
        if any(t in text for t in terms):
            return target, "fingerprint"
    if ent.get("manufacturer"):
        em = clean(ent.get("manufacturer"))
        if re.search(r"[A-Za-z]{3,}", em):
            return normalize_manufacturer(em), "entity-mib"
    mv = normalize_manufacturer(d.get("mac_vendor"))
    if mv and mv not in ("VMware", "Microsoft", "Linux"):
        return mv, "mac-oui"
    return "", ""


def infer_model(d, text, ent, role):
    if ent.get("model"):
        return clean(ent["model"])[:120], "entity-mib"
    patterns = [
        r"(PowerEdge\s+[A-Za-z0-9-]+)",
        r"(FortiGate[-_ ]?[A-Za-z0-9-]+)", r"(FGT[_-][A-Za-z0-9_-]+)",
        r"(U7-Pro|U6-LR|UAP-[A-Za-z0-9-]+)",
        r"(JL\d{3}[A-Z])", r"(1930\s+[A-Za-z0-9 +/.-]+Switch)",
        r"(TS-431K|TS-X41)", r"(EDS-40[58]A-[A-Za-z0-9-]+)",
        r"(CP\s*1543-1|CP\s*443-1)", r"(CPU\s*412-2\s*PN/DP)",
        r"(IM153-4PN)", r"(PAC4200)",
    ]
    raw = " ".join([clean(d.get("snmp_description")), text])
    m = first_match(patterns, raw)
    return (m[:120], "fingerprint") if m else ("", "")


def platform_for(role, text, d):
    if role == "FIREWALL": return "FortiOS"
    if role == "HYPERVISOR": return "VMware ESXi"
    if role == "OOB_MANAGEMENT": return "Dell iDRAC"
    if role in ("WIRELESS_AP", "WIRELESS_BRIDGE", "WIRELESS_DEVICE"): return "UniFi"
    if role == "VMWARE_APPLIANCE": return "VMware"
    if role == "STORAGE" and "qnap" in text: return "QTS"
    if role.startswith("INDUSTRIAL_") and "simatic" in text: return "SIMATIC"
    if "microsoft windows" in text or "cpe:/o:microsoft:windows" in text: return "Windows"
    if "linux" in text or "cpe:/o:linux:linux_kernel" in text: return "Linux"
    return ""


def classify_role(d, text):
    tcp = ports(d, "tcp")
    udp = ports(d, "udp")
    evidence = []

    def hit(role, score, reason):
        return role, score, [reason]

    if any(t in text for t in ("idrac", "restgui/start.html", "integrated dell remote access controller")):
        return hit("OOB_MANAGEMENT", 99, "Dell iDRAC fingerprint/TLS")
    if any(t in text for t in ("fortigate", "fortinet", "enterprises.12356")):
        return hit("FIREWALL", 99, "Fortinet/FortiGate fingerprint")
    if ("vmware esxi" in text or "enterprises.6876.4.1" in text or
            (902 in tcp and 427 in tcp) or
            (902 in tcp and "organizationname=vmware" in text and "vmware installer" not in text)):
        return hit("HYPERVISOR", 98, "VMware ESXi fingerprint/services")
    if 902 in tcp and ("organizationname=vmware" in text or "vmware installer" in text):
        return hit("VMWARE_APPLIANCE", 82, "VMware service/TLS fingerprint without ESXi proof")

    # Dell BMC/iDRAC can answer RMCP even when the HTTPS interface is unavailable.
    if 623 in udp and ("dell" in text or normalize_manufacturer(d.get("mac_vendor")) == "Dell"):
        return hit("OOB_MANAGEMENT", 78, "Dell management controller via RMCP/623")

    # OT/network-specific signatures first.
    if any(t in text for t in ("moxa eds-", "eds-405", "eds-408", "westermo lynx")):
        return hit("INDUSTRIAL_SWITCH", 98, "Industrial Ethernet switch fingerprint")
    if any(t in text for t in ("simatic s7 cpu", "cpu 412-2", "s7-info")):
        return hit("INDUSTRIAL_PLC", 99, "SIMATIC S7 CPU fingerprint")
    if any(t in text for t in ("hw-type: io-device", "im153-4pn", "io-device")):
        return hit("INDUSTRIAL_IO", 96, "Industrial I/O fingerprint")
    if "pac4200" in text:
        return hit("INDUSTRIAL_POWER_METER", 98, "Siemens PAC4200 fingerprint")
    if any(t in text for t in ("cp1543-1", "cp 443-1", "simatic net")):
        return hit("INDUSTRIAL_COMMUNICATION", 96, "SIMATIC NET communication processor")

    # Wireless vs switch distinction for Ubiquiti.
    if any(t in text for t in ("edgeswitch", "unifi switch", "usw-")):
        return hit("NETWORK_SWITCH", 96, "Ubiquiti switch fingerprint")
    if any(t in text for t in ("u7-pro", "u6-lr", "uap-", "unifi ap", "wireless access point")):
        return hit("WIRELESS_AP", 98, "Wireless AP model/fingerprint")
    if "ubiquiti" in text and any(t in text for t in ("u7", "u6", "uap", "access point")):
        return hit("WIRELESS_AP", 94, "Ubiquiti wireless fingerprint")
    if ("ubiquiti" in text or "enterprises.10002" in text) and not any(t in text for t in ("edgeswitch", "unifi switch", "usw-")):
        name_text = " ".join([clean(d.get("snmp_name")), clean(d.get("reverse_dns"))]).lower()
        if "wlink" in name_text:
            return hit("WIRELESS_BRIDGE", 86, "Ubiquiti wireless link/bridge identity")
        if "wifi" in name_text:
            return hit("WIRELESS_AP", 88, "Ubiquiti Wi-Fi identity")
        return hit("WIRELESS_DEVICE", 72, "Ubiquiti wireless device; exact function unresolved")

    if any(t in text for t in (
        "hpe networking instant on switch", "aruba instant on", "officeconnect switch",
        "1920-48g switch", "v1910-", "3com switch", "comware switch", "device: switch",
    )):
        return hit("NETWORK_SWITCH", 98, "Managed switch fingerprint")

    if any(t in text for t in ("qnap", "turbo nas", "ts-x41", "ts-431", "nas-ba")):
        return hit("STORAGE", 98, "NAS/storage fingerprint")
    if "seagate" in text and "nas" in text:
        return hit("STORAGE", 96, "Seagate NAS fingerprint")

    if any(t in text for t in ("network management card", "apc web/snmp", "apc", "smart-ups")) and not "apache" in text:
        return hit("POWER_MANAGEMENT", 94, "UPS/power-management fingerprint")

    if any(t in text for t in ("brother", "pantum", "samsung sl-", "samsung printer", "laserjet", "jetdirect", "printer")):
        return hit("PRINTER", 94, "Printer fingerprint")

    if any(t in text for t in ("home | netbox", "ubuntu-netbox", "netbox")):
        return hit("MANAGEMENT_APPLIANCE", 96, "NetBox fingerprint")
    if any(t in text for t in ("wazuh", "srv-syslog")):
        return hit("SECURITY_APPLIANCE", 95, "Security/logging appliance fingerprint")
    if any(t in text for t in ("agente http - sms", "microchip libraries")):
        return hit("SMS_GATEWAY", 92, "SMS gateway fingerprint")

    # AD/DC before generic Windows.
    if ((88 in tcp or 88 in udp) and 389 in tcp and (445 in tcp or 636 in tcp)) or "active directory ldap" in text:
        return hit("DOMAIN_CONTROLLER", 97, "Kerberos/LDAP/AD services")

    windows_score = 0
    if "microsoft windows" in text or "cpe:/o:microsoft:windows" in text: windows_score += 45
    if 445 in tcp: windows_score += 15
    if 3389 in tcp: windows_score += 15
    if 135 in tcp: windows_score += 10
    if 5985 in tcp or 5986 in tcp: windows_score += 10
    if script_values(d, "rdp-ntlm-info") or script_values(d, "smb-os-discovery"): windows_score += 20
    if windows_score >= 45:
        return hit("WINDOWS_HOST", min(95, windows_score), "Windows services/fingerprint")

    linux_score = 0
    if "linux" in text or "cpe:/o:linux:linux_kernel" in text: linux_score += 50
    if 22 in tcp: linux_score += 20
    if "openssh" in text: linux_score += 15
    if linux_score >= 50:
        return hit("LINUX_HOST", min(92, linux_score), "Linux/SSH fingerprint")

    # Generic OT protocol only after strong host fingerprints have had a chance to classify.
    if 102 in tcp or 502 in tcp or 44818 in tcp or 2404 in tcp or 20000 in tcp:
        return hit("INDUSTRIAL_DEVICE", 62, "Industrial protocol detected; exact function unresolved")

    if (9100 in tcp or 515 in tcp) and not ({135, 445} & tcp):
        return hit("PRINTER", 78, "Printing service ports")

    # Camera only with actual camera/vendor signal. RTSP alone is insufficient.
    if any(t in text for t in ("hikvision", "dahua", "axis communications", "network camera", "ip camera")):
        return hit("CAMERA", 92, "Camera fingerprint")

    web = bool({80, 443, 8080, 8081, 8443, 9443, 10443} & tcp)
    if web:
        return hit("WEB_APPLIANCE", 52, "Web management/service detected without stronger identity")
    if d.get("snmp_available"):
        return hit("SNMP_DEVICE", 48, "SNMP responds but role unresolved")
    if tcp or udp:
        return hit("UNKNOWN", 25, "Services detected but role unresolved")
    return hit("UNKNOWN", 5, "Host active with insufficient identity evidence")


def confidence(score):
    if score >= 85: return "HIGH"
    if score >= 55: return "MEDIUM"
    if score >= 30: return "LOW"
    return "NONE"


def asset_class(d, role, text):
    mv = normalize_manufacturer(d.get("mac_vendor"))
    if role == "OOB_MANAGEMENT":
        return "OOB_INTERFACE"
    if role == "HYPERVISOR":
        return "PHYSICAL_DEVICE"
    if mv == "VMware" and role not in ("NETWORK_SWITCH", "WIRELESS_AP", "FIREWALL"):
        return "VIRTUAL_MACHINE_CANDIDATE"
    if role in (
        "FIREWALL", "NETWORK_SWITCH", "WIRELESS_AP", "WIRELESS_BRIDGE", "WIRELESS_DEVICE", "STORAGE", "POWER_MANAGEMENT", "PRINTER",
        "INDUSTRIAL_SWITCH", "INDUSTRIAL_PLC", "INDUSTRIAL_IO", "INDUSTRIAL_POWER_METER",
        "INDUSTRIAL_COMMUNICATION", "INDUSTRIAL_DEVICE", "CAMERA",
    ):
        return "PHYSICAL_DEVICE"
    return "HOST_OR_APPLIANCE"


def classify_device(d):
    text = all_text(d)
    ent = entity_identity(d)
    role, score, evidence = classify_role(d, text)
    manufacturer, manufacturer_source = infer_manufacturer(d, text, ent)
    model, model_source = infer_model(d, text, ent, role)
    platform = platform_for(role, text, d)
    names = hostname_candidates(d)
    hostname = names[0][0] if names else ""
    hostname_source = names[0][1] if names else ""
    serial = clean(ent.get("serial"))
    serial_source = "entity-mib" if serial else ""
    oob_serial = idrac_serial(d)
    if role == "OOB_MANAGEMENT" and oob_serial and not serial:
        serial = oob_serial.upper()
        serial_source = "idrac-tls-name"
    if manufacturer_source: evidence.append("manufacturer:{0}".format(manufacturer_source))
    if model_source: evidence.append("model:{0}".format(model_source))
    if serial_source: evidence.append("serial:{0}".format(serial_source))
    if hostname_source: evidence.append("hostname:{0}".format(hostname_source))

    out = {
        "classification_version": CLASSIFIER_VERSION,
        "client": clean(d.get("client")),
        "site": clean(d.get("site")),
        "source_proxy": clean(d.get("source_proxy")),
        "ip": clean(d.get("ip")),
        "hostname": hostname,
        "hostname_source": hostname_source,
        "role": role,
        "manufacturer": manufacturer,
        "manufacturer_source": manufacturer_source,
        "model": model,
        "model_source": model_source,
        "serial": serial,
        "serial_source": serial_source,
        "platform": platform,
        "asset_class": asset_class(d, role, text),
        "classification_score": score,
        "confidence": confidence(score),
        "evidence_level": clean(d.get("evidence_level")),
        "evidence": evidence,
        "primary_mac": norm_mac(d.get("mac")),
        "interface_macs": sorted(set(norm_mac(x.get("mac")) for x in (d.get("snmp_interface_macs") or []) if norm_mac(x.get("mac")))),
        "snmp_name": clean(d.get("snmp_name")),
        "snmp_object_id": clean(d.get("snmp_object_id")),
        "snmp_bridge_mac": norm_mac(d.get("snmp_bridge_mac")),
        "snmp_lldp_chassis_id": clean(d.get("snmp_lldp_chassis_id")),
        "reported_ip_addresses": [x for x in (d.get("snmp_ip_addresses") or []) if clean(x.get("address"))],
        "certificate_common_names": certificate_common_names(d),
        "netbox_write": False,
    }
    if out["confidence"] == "HIGH":
        out["classification_state"] = "IDENTIFIED"
    elif out["confidence"] == "MEDIUM":
        out["classification_state"] = "PROBABLE"
    else:
        out["classification_state"] = "UNRESOLVED"
    return out


def write_outputs(source, report, output_dir):
    site = clean(report.get("site")) or "SITE"
    stamp = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    base = os.path.join(output_dir, "{0}-classification-{1}".format(site, stamp))
    jpath, cpath = base + ".json", base + ".csv"
    devices = [classify_device(x) for x in report.get("devices") or []]
    devices.sort(key=lambda x: ip_key(x.get("ip")))
    roles = Counter(x["role"] for x in devices)
    conf = Counter(x["confidence"] for x in devices)
    data = {
        "mode": "DRY-RUN",
        "stage": "CLASSIFY",
        "classification_version": CLASSIFIER_VERSION,
        "source_discovery": source,
        "client": clean(report.get("client")),
        "site": site,
        "total": len(devices),
        "role_summary": dict(sorted(roles.items())),
        "confidence_summary": dict(sorted(conf.items())),
        "records": devices,
        "netbox_write": False,
    }
    with open(jpath, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    fields = [
        "ip", "hostname", "role", "manufacturer", "model", "serial", "platform", "asset_class",
        "classification_score", "confidence", "classification_state", "evidence_level", "primary_mac",
        "snmp_name", "snmp_object_id", "hostname_source", "manufacturer_source", "model_source", "serial_source",
        "evidence",
    ]
    with open(cpath, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for x in devices:
            row = dict(x)
            row["evidence"] = " | ".join(x.get("evidence") or [])
            w.writerow({k: row.get(k, "") for k in fields})
    return jpath, cpath, data


def main(argv=None):
    ap = argparse.ArgumentParser(description="netbox-discovery CLASSIFY (read-only)")
    ap.add_argument("--input", default="", help="Discovery JSON. Default: latest *-discovery-*.json")
    ap.add_argument("--output-dir", default=REPORTS)
    args = ap.parse_args(argv)
    source = args.input or latest(os.path.join(REPORTS, "*-discovery-*.json"))
    if not source or not os.path.isfile(source):
        raise RuntimeError("Nenhum discovery JSON encontrado em {0}".format(REPORTS))
    with open(source, "r") as f:
        report = json.load(f)
    if not isinstance(report.get("devices"), list):
        raise RuntimeError("Discovery JSON inválido: campo devices ausente.")
    if clean(report.get("mode")).upper() != "DRY-RUN":
        print("AVISO: origem não marcada DRY-RUN; CLASSIFY continua sem escrita no NetBox.")
    if not os.path.isdir(args.output_dir):
        os.makedirs(args.output_dir)
    jpath, cpath, data = write_outputs(source, report, args.output_dir)
    print("===== CLASSIFY =====")
    print("Origem: {0}".format(source))
    print("Registros: {0}".format(data["total"]))
    print("Confiança: HIGH={0} MEDIUM={1} LOW={2} NONE={3}".format(
        data["confidence_summary"].get("HIGH", 0), data["confidence_summary"].get("MEDIUM", 0),
        data["confidence_summary"].get("LOW", 0), data["confidence_summary"].get("NONE", 0)))
    print("JSON: {0}".format(jpath))
    print("CSV:  {0}".format(cpath))
    print("NetBox write: NÃO")
    return 0


if __name__ == "__main__":
    sys.exit(main())
