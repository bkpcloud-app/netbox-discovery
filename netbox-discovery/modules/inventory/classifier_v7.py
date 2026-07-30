#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import ipaddress
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, "..", ".."))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.inventory import classifier_v6 as v6
from modules.product import identity

CLASSIFIER_VERSION = "5.3-product"
ORIG_CLASSIFY_DEVICE = v6.classify_device

PHYSICAL_ROLES = {
    "NETWORK_SWITCH", "WIRELESS_AP", "WIRELESS_BRIDGE", "FIREWALL",
    "PRINTER", "CAMERA", "NVR", "DVR", "VIDEO_ENCODER",
    "VIDEO_SURVEILLANCE_DEVICE", "OOB_MANAGEMENT", "STORAGE",
    "INDUSTRIAL_PLC", "INDUSTRIAL_IO", "INDUSTRIAL_SWITCH",
    "INDUSTRIAL_COMMUNICATION", "INDUSTRIAL_POWER_METER",
    "INDUSTRIAL_DRIVE", "INDUSTRIAL_MOTOR_PROTECTION",
    "INDUSTRIAL_CONTROLLER", "INDUSTRIAL_DEVICE",
}

CCTV_MANUFACTURERS = {
    "Hikvision", "Dahua", "Intelbras", "Axis Communications", "Vivotek",
    "Uniview", "Reolink", "Hanwha Vision", "Bosch Security Systems",
    "Ubiquiti", "TP-Link",
}

SERIAL_PLACEHOLDERS = {
    "03000000", "12345678", "123456789", "1234567890", "0123456789",
    "00000001", "99999999", "XXXXXXXX", "XXXXXXXXXX", "TEST", "DEMO",
    "SAMPLE", "PLACEHOLDER", "SERIALNO", "SERIALNUM", "DEVICEID",
}

WINDOWS_ROLE_TARGETS = {
    "SERVER": "WINDOWS_SERVER",
    "WORKSTATION": "WINDOWS_WORKSTATION",
}


def clean(value):
    return "" if value is None else str(value).strip()


def norm(value):
    return re.sub(r"\s+", " ", clean(value)).strip().casefold()


def _candidate_rank(candidate):
    return (
        int(candidate.get("score") or 0),
        1 if candidate.get("serial") else 0,
        1 if candidate.get("model") else 0,
        1 if candidate.get("manufacturer") else 0,
    )


def _script_names(discovery):
    values = []
    for service in discovery.get("open_services") or []:
        for name in (service.get("scripts") or {}).keys():
            low = clean(name).lower()
            if low and low not in values:
                values.append(low)
    return values


def _valid_cctv_candidate(discovery, candidate):
    """Reject generic WS-Discovery/UPnP and arbitrary MAC OUI as CCTV proof."""
    if not candidate:
        return False
    source = clean(candidate.get("source"))
    model = clean(candidate.get("model"))
    manufacturer = identity.canonical_manufacturer(candidate.get("manufacturer"))
    text = identity.norm(identity.evidence_text(discovery))
    scripts = _script_names(discovery)

    explicit_video = any(token in text for token in (
        "networkvideotransmitter", "networkvideorecorder",
        "network video transmitter", "network video recorder",
        "network camera", "ip camera", "video encoder",
        " type:camera", " type:nvr", " type:dvr", "/onvif/",
    ))
    onvif_script = any("onvif" in name for name in scripts)

    if source == "onvif-device-information":
        return bool(onvif_script or explicit_video or "onvif" in text)

    if source == "cctv-fingerprint":
        if model:
            return True
        if manufacturer not in CCTV_MANUFACTURERS:
            return False
        rtsp_signal = "rtsp" in text or any("rtsp" in name for name in scripts)
        return bool(explicit_video or onvif_script or (rtsp_signal and manufacturer in CCTV_MANUFACTURERS))

    return False


def _normalize_model(manufacturer, model):
    value = re.sub(r"\s+", " ", clean(model)).strip()
    vendor = identity.canonical_manufacturer(manufacturer)
    if vendor == "Kyocera":
        match = re.search(r"\b(ECOSYS|TASKalfa)\s+([A-Z0-9][A-Z0-9._-]*)", value, re.I)
        if match:
            family = "ECOSYS" if match.group(1).lower() == "ecosys" else "TASKalfa"
            return "{0} {1}".format(family, match.group(2))[:120]
    return value[:120]


def _serial_context_values(discovery, out):
    values = [
        out.get("model"), out.get("manufacturer"), out.get("hostname"),
        discovery.get("snmp_name"), discovery.get("reverse_dns"),
        discovery.get("ip"), discovery.get("mac"), discovery.get("snmp_bridge_mac"),
    ]
    return [identity.norm_serial(value) for value in values if identity.norm_serial(value)]


def _validate_serial(value, contexts):
    serial = identity.norm_serial(value)
    if not serial:
        return "", "empty-or-generic"
    if serial in SERIAL_PLACEHOLDERS:
        return "", "known-placeholder"
    if len(serial) < 5:
        return "", "too-short"
    if len(serial) > 64:
        return "", "too-long"
    if len(set(serial)) == 1:
        return "", "repeated-character"
    if serial in ("ABCDEF", "ABCDEFG", "ABCDEFGHIJ"):
        return "", "sequential-placeholder"
    if serial in contexts:
        return "", "duplicates-model-name-ip-or-mac"
    try:
        ipaddress.ip_address(clean(value))
        return "", "ip-address"
    except Exception:
        pass
    compact_mac = re.sub(r"[^0-9A-Fa-f]", "", clean(value)).upper()
    if len(compact_mac) == 12 and identity.norm_mac(compact_mac):
        return "", "mac-address"
    return serial, ""


def _serial_rank(source, primary=False):
    low = clean(source).casefold()
    if "onvif" in low or "hikvision" in low or "isapi" in low:
        return 110
    if "printer-mib" in low:
        return 108
    if "fcmgmt" in low or "fibre" in low:
        return 106
    if "idrac" in low or "service-tag" in low:
        return 105
    if "s7" in low or "enip" in low or "bacnet" in low or "modbus" in low:
        return 104
    if "entity-mib" in low:
        return 102 if primary else 96
    if "snmp" in low:
        return 92
    if "description" in low or "script" in low:
        return 86
    return 80


def _extract_labeled_serials(text):
    values = []
    patterns = (
        r"(?:Serial(?:\s+Number|\s+No\.?|Number)?|Device\s+Serial(?:\s+No\.?)?|S/N)\s*[:=#-]\s*([A-Za-z0-9][A-Za-z0-9._/-]{3,63})",
        r"<(?:serialNumber|SerialNumber|SerialNO|serialNo)>\s*([^<]{4,64})\s*</",
        r"[\"'](?:serialNumber|serial_no|serialNo|SerialNO)[\"']\s*:\s*[\"']([^\"']{4,64})[\"']",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, clean(text), re.I):
            value = clean(match.group(1))
            if value and value not in values:
                values.append(value)
    return values


def _best_serial(discovery, out):
    contexts = _serial_context_values(discovery, out)
    candidates = []
    rejected = []

    def add(value, source, rank=None, primary=False):
        raw = clean(value)
        if not raw:
            return
        serial, reason = _validate_serial(raw, contexts)
        if not serial:
            marker = {"value": raw[:64], "source": clean(source), "reason": reason}
            if marker not in rejected:
                rejected.append(marker)
            return
        item = {
            "serial": serial,
            "source": clean(source) or "unknown",
            "rank": int(rank if rank is not None else _serial_rank(source, primary=primary)),
        }
        existing = next((row for row in candidates if row["serial"] == serial and row["source"] == item["source"]), None)
        if not existing:
            candidates.append(item)

    add(out.get("serial"), out.get("serial_source") or "classifier-current")

    primary = discovery.get("snmp_entity_primary") or {}
    inventory = []
    if primary:
        inventory.append((primary, True))
    inventory.extend((row, False) for row in (discovery.get("snmp_entity_inventory") or []))
    for row, is_primary in inventory:
        source = clean(row.get("source")) or "entity-mib"
        add(row.get("printer_mib_serial"), "printer-mib", primary=True)
        for value in row.get("printer_mib_serial_candidates") or []:
            add(value, "printer-mib-candidate", primary=True)
        add(row.get("fa_conn_unit_serial"), "fcmgmt-mib", primary=True)
        add(row.get("serial"), source, primary=is_primary)
        for text_field in ("printer_mib_text", "protocol_text", "description"):
            for value in _extract_labeled_serials(row.get(text_field)):
                add(value, source + "-description", rank=_serial_rank(source, primary=is_primary) - 6)

    for service in discovery.get("open_services") or []:
        for script_name, script_value in (service.get("scripts") or {}).items():
            low = clean(script_name).casefold()
            if any(token in low for token in ("onvif", "hikvision", "isapi")):
                source = "onvif-hikvision-device-info"
            elif "s7" in low:
                source = "s7-info"
            elif "enip" in low or "ethernet" in low:
                source = "enip-info"
            elif "bacnet" in low:
                source = "bacnet-info"
            elif "modbus" in low:
                source = "modbus-info"
            else:
                source = "script:{0}".format(low or "unknown")
            for value in _extract_labeled_serials(script_value):
                add(value, source)

    for value in _extract_labeled_serials(discovery.get("snmp_description")):
        add(value, "snmp-description")

    candidates.sort(key=lambda row: (row["rank"], len(row["serial"])), reverse=True)
    unique = []
    for row in candidates:
        if row["serial"] not in [item["serial"] for item in unique]:
            unique.append(row)

    out["serial_candidates"] = unique[:12]
    out["serial_rejections"] = rejected[:12]
    out["serial_evidence_count"] = len(unique)
    if not unique:
        out["serial"] = ""
        if out.get("serial_source"):
            out["serial_source"] = "rejected-or-unavailable"
        out["serial_confidence"] = "NONE"
        return

    best = unique[0]
    close_conflicts = [row for row in unique[1:] if row["rank"] >= best["rank"] - 1 and row["serial"] != best["serial"]]
    if close_conflicts:
        out["serial_conflict"] = [best] + close_conflicts
        out["serial"] = ""
        out["serial_source"] = "conflicting-strong-evidence"
        out["serial_confidence"] = "CONFLICT"
        return

    out["serial"] = best["serial"]
    out["serial_source"] = best["source"]
    out["serial_confidence"] = "HIGH" if best["rank"] >= 100 else ("MEDIUM" if best["rank"] >= 90 else "LOW")
    evidence = list(out.get("evidence") or [])
    marker = "serial:{0}".format(best["source"])
    if marker not in evidence:
        evidence.append(marker)
    out["evidence"] = evidence


def _windows_evidence(discovery):
    rows = []

    def add(source, text, rank):
        value = clean(text)
        if value:
            rows.append({"source": source, "text": value, "rank": rank})

    for service in discovery.get("open_services") or []:
        try:
            port = int(service.get("port") or 0)
        except Exception:
            port = 0
        for name, value in (service.get("scripts") or {}).items():
            low = clean(name).casefold()
            if low == "smb-os-discovery" or low == "smb-system-info":
                add(low, value, 110)
            elif low == "rdp-ntlm-info":
                add(low, value, 75)
        for cpe in service.get("cpes") or []:
            if "microsoft:windows" in clean(cpe).casefold():
                add("service-cpe", cpe, 105)
        if port in (135, 139, 445, 3389, 5985, 5986):
            add("windows-service", " ".join((
                clean(service.get("product")), clean(service.get("version")),
                clean(service.get("extrainfo")), clean(service.get("ostype")),
            )), 70)

    for match in discovery.get("os_matches") or []:
        try:
            accuracy = int(match.get("accuracy") or 0)
        except Exception:
            accuracy = 0
        if accuracy < 95:
            continue
        add("os-fingerprint-{0}".format(accuracy), match.get("name"), min(100, accuracy))
        for cls in match.get("classes") or []:
            try:
                class_accuracy = int(cls.get("accuracy") or 0)
            except Exception:
                class_accuracy = 0
            vendor = clean(cls.get("vendor"))
            family = clean(cls.get("osfamily"))
            generation = clean(cls.get("osgen"))
            if class_accuracy >= 95 and ("microsoft" in vendor.casefold() or "windows" in family.casefold()):
                add("os-class-{0}".format(class_accuracy), " ".join((vendor, family, generation)), class_accuracy)
            for cpe in cls.get("cpes") or []:
                if "microsoft:windows" in clean(cpe).casefold():
                    add("os-cpe-{0}".format(class_accuracy), cpe, max(95, class_accuracy))
    return rows


def _canonical_windows(text):
    raw = clean(text)
    low = raw.casefold()
    server_versions = (
        (r"windows[_ :/-]*server[_ :/-]*2025|windows\s+server\s+2025", "Windows Server 2025"),
        (r"windows[_ :/-]*server[_ :/-]*2022|windows\s+server\s+2022", "Windows Server 2022"),
        (r"windows[_ :/-]*server[_ :/-]*2019|windows\s+server\s+2019", "Windows Server 2019"),
        (r"windows[_ :/-]*server[_ :/-]*2016|windows\s+server\s+2016", "Windows Server 2016"),
        (r"windows[_ :/-]*server[_ :/-]*2012[_ :/-]*r2|windows\s+server\s+2012\s+r2", "Windows Server 2012 R2"),
        (r"windows[_ :/-]*server[_ :/-]*2012|windows\s+server\s+2012", "Windows Server 2012"),
        (r"windows[_ :/-]*server[_ :/-]*2008[_ :/-]*r2|windows\s+server\s+2008\s+r2", "Windows Server 2008 R2"),
        (r"windows[_ :/-]*server[_ :/-]*2008|windows\s+server\s+2008", "Windows Server 2008"),
        (r"windows\s+server|windows_server|serverstandard|serverdatacenter", "Windows Server"),
    )
    workstation_versions = (
        (r"windows[_ :/-]*11|windows\s+11", "Windows 11"),
        (r"windows[_ :/-]*10|windows\s+10", "Windows 10"),
        (r"windows[_ :/-]*8[._ ]1|windows\s+8\.1", "Windows 8.1"),
        (r"windows[_ :/-]*8(?:\D|$)|windows\s+8(?:\D|$)", "Windows 8"),
        (r"windows[_ :/-]*7|windows\s+7", "Windows 7"),
        (r"windows\s+vista|windows_vista", "Windows Vista"),
        (r"windows\s+xp|windows_xp", "Windows XP"),
    )
    for pattern, product in server_versions:
        if re.search(pattern, low, re.I):
            return "SERVER", product
    for pattern, product in workstation_versions:
        if re.search(pattern, low, re.I):
            return "WORKSTATION", product
    return "", ""


def _refine_windows(discovery, out):
    role = clean(out.get("role"))
    if role not in ("WINDOWS_HOST", "DOMAIN_CONTROLLER", "WINDOWS_SERVER", "WINDOWS_WORKSTATION"):
        return
    matches = []
    for evidence in _windows_evidence(discovery):
        family, product = _canonical_windows(evidence["text"])
        if family:
            matches.append({
                "family": family,
                "product": product,
                "source": evidence["source"],
                "rank": evidence["rank"],
                "text": evidence["text"][:300],
            })
    matches.sort(key=lambda row: (row["rank"], len(row["product"])), reverse=True)
    out["windows_evidence"] = matches[:10]
    if not matches:
        out["windows_family"] = "UNRESOLVED"
        return

    best = matches[0]
    conflict = [row for row in matches[1:] if row["rank"] >= best["rank"] - 2 and row["family"] != best["family"]]
    if conflict:
        out["windows_family"] = "CONFLICT"
        out["windows_classification_conflict"] = [best] + conflict
        evidence = list(out.get("evidence") or [])
        if "Windows server/workstation evidence conflict" not in evidence:
            evidence.append("Windows server/workstation evidence conflict")
        out["evidence"] = evidence
        return

    family = "SERVER" if role == "DOMAIN_CONTROLLER" else best["family"]
    out["windows_family"] = family
    out["windows_product"] = best["product"]
    out["windows_evidence_source"] = best["source"]
    out["windows_evidence_rank"] = best["rank"]
    out["platform"] = best["product"]
    if role != "DOMAIN_CONTROLLER":
        out["role"] = WINDOWS_ROLE_TARGETS[family]
    out["classification_score"] = max(int(out.get("classification_score") or 0), 96)
    out["confidence"] = "HIGH"
    out["classification_state"] = "IDENTIFIED"
    evidence = list(out.get("evidence") or [])
    marker = "Windows {0} explicit edition via {1}".format(family.lower(), best["source"])
    if marker not in evidence:
        evidence.append(marker)
    out["evidence"] = evidence


def classify_device(discovery):
    out = ORIG_CLASSIFY_DEVICE(discovery)

    candidates = []
    industrial = identity.industrial_identity(discovery)
    cctv = identity.cctv_identity(discovery)
    if industrial:
        candidates.append(industrial)
    if _valid_cctv_candidate(discovery, cctv):
        candidates.append(cctv)

    if candidates:
        candidates.sort(key=_candidate_rank, reverse=True)
        identity.apply_identity_candidate(out, candidates[0])
        out["identity_candidates"] = [
            {
                "source": row.get("source"),
                "role": row.get("role"),
                "manufacturer": row.get("manufacturer"),
                "model": row.get("model"),
                "serial": row.get("serial"),
                "score": row.get("score"),
            }
            for row in candidates
        ]

    out["model"] = _normalize_model(out.get("manufacturer"), out.get("model"))
    _refine_windows(discovery, out)
    _best_serial(discovery, out)
    identity.apply_observed_metadata(discovery, out)

    nature = clean(out.get("asset_nature"))
    role = clean(out.get("role"))
    if nature == "PHYSICAL_DEVICE" or role in PHYSICAL_ROLES:
        out["asset_class"] = "PHYSICAL_DEVICE"
    elif nature == "VIRTUAL_MACHINE":
        out["asset_class"] = "VIRTUAL_MACHINE"
    elif nature == "VIRTUAL_CANDIDATE" and clean(out.get("asset_class")) == "PHYSICAL_DEVICE":
        if identity.is_generic_model(out.get("model")) or clean(out.get("confidence")) != "HIGH":
            out["asset_class"] = "HOST_OR_APPLIANCE"

    out["review_recommendations"] = identity.review_recommendations(out)
    if out.get("windows_family") == "UNRESOLVED":
        recommendation = "obter edição do Windows via SMB OS/CPE para separar Server de Workstation"
        if recommendation not in out["review_recommendations"]:
            out["review_recommendations"].append(recommendation)
    if not out.get("serial"):
        recommendation = "obter serial por protocolo específico, ENTITY-MIB, Printer-MIB ou ONVIF/ISAPI"
        if recommendation not in out["review_recommendations"]:
            out["review_recommendations"].append(recommendation)

    out["classification_version"] = CLASSIFIER_VERSION
    return out


def main(argv=None):
    old_classify = v6.classify_device
    old_version = v6.CLASSIFIER_VERSION
    try:
        v6.classify_device = classify_device
        v6.CLASSIFIER_VERSION = CLASSIFIER_VERSION
        return v6.main(argv)
    finally:
        v6.classify_device = old_classify
        v6.CLASSIFIER_VERSION = old_version


if __name__ == "__main__":
    sys.exit(main())
