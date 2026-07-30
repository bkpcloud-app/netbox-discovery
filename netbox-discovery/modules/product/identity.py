#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import hashlib
import re

IDENTITY_ENGINE_VERSION = "1.0-product"

CONFIDENCE_SCORES = {
    "NONE": 0,
    "LOW": 45,
    "MEDIUM": 70,
    "HIGH": 95,
}

VIRTUAL_OUIS = {
    "00:05:69": "VMware",
    "00:0C:29": "VMware",
    "00:1C:14": "VMware",
    "00:50:56": "VMware",
    "00:15:5D": "Microsoft Hyper-V",
    "00:1C:42": "Parallels",
    "08:00:27": "VirtualBox",
    "52:54:00": "QEMU/KVM",
    "00:16:3E": "Xen",
}

MANUFACTURER_ALIASES = {
    "dell inc.": "Dell",
    "dell inc": "Dell",
    "dell technologies": "Dell",
    "dell emc": "Dell",
    "hewlett packard enterprise": "HPE",
    "hewlett-packard": "HP",
    "hp inc.": "HP",
    "hp inc": "HP",
    "aruba networks": "HPE Aruba",
    "hpe networking": "HPE Aruba",
    "ubiquiti networks": "Ubiquiti",
    "ubiquiti inc.": "Ubiquiti",
    "ubiquiti inc": "Ubiquiti",
    "kyocera document solutions": "Kyocera",
    "kyocera mita": "Kyocera",
    "hangzhou hikvision digital technology": "Hikvision",
    "zhejiang dahua technology": "Dahua",
    "axis communications ab": "Axis Communications",
    "hanwha techwin": "Hanwha Vision",
    "schneider electric": "Schneider Electric",
    "apc by schneider electric": "APC by Schneider Electric",
}

GENERIC_MODEL_MARKERS = (
    "generic ",
    "unknown server",
    "generic unknown",
    "unknown dell server",
    "generic printer",
    "generic wireless",
    "generic network",
    "generic storage",
    "generic industrial",
    "industrial device",
    "industrial switch",
    "unknown appliance",
)

GENERIC_NAME_PREFIXES = (
    "UNKNOWN-",
    "WEB_APPLIANCE-",
    "WINDOWS_HOST-",
    "LINUX_HOST-",
    "INDUSTRIAL_DEVICE-",
    "SNMP_DEVICE-",
    "ECOSYS-",
    "PRINTER-",
    "CAMERA-",
    "CCTV-",
)

INDUSTRIAL_OID_CATALOG = {
    ".1.3.6.1.4.1.8691.2.7": {
        "manufacturer": "Moxa",
        "model": "NPort 5210",
        "role": "INDUSTRIAL_COMMUNICATION",
        "source": "sysobjectid:moxa-nport-5210",
    },
}


def clean(value):
    return "" if value is None else str(value).strip()


def norm(value):
    return re.sub(r"\s+", " ", clean(value)).strip().casefold()


def norm_mac(value):
    compact = re.sub(r"[^0-9A-Fa-f]", "", clean(value)).upper()
    if len(compact) != 12 or compact in ("000000000000", "FFFFFFFFFFFF"):
        return ""
    try:
        if int(compact[:2], 16) & 1:
            return ""
    except ValueError:
        return ""
    return ":".join(compact[pos:pos + 2] for pos in range(0, 12, 2))


def norm_serial(value):
    compact = re.sub(r"[^A-Za-z0-9]", "", clean(value)).upper()
    invalid = {
        "", "UNKNOWN", "NA", "NONE", "NULL", "DEFAULT", "SERIAL",
        "SERIALNUMBER", "SYSTEMSERIALNUMBER", "CHASSISSERIALNUMBER",
        "NOTAVAILABLE", "NOTAPPLICABLE", "TOBEFILLEDBYOEM", "SVCTAG",
    }
    if compact in invalid:
        return ""
    if len(compact) >= 6 and len(set(compact)) == 1 and compact[0] in ("0", "F"):
        return ""
    return compact


def canonical_manufacturer(value):
    raw = clean(value)
    low = norm(raw)
    if not raw:
        return ""
    if low in MANUFACTURER_ALIASES:
        return MANUFACTURER_ALIASES[low]
    rules = (
        (("siemens",), "Siemens"),
        (("moxa",), "Moxa"),
        (("westermo",), "Westermo"),
        (("rockwell", "allen-bradley", "allen bradley"), "Rockwell Automation"),
        (("schneider", "modicon"), "Schneider Electric"),
        (("weg",), "WEG"),
        (("hikvision",), "Hikvision"),
        (("dahua",), "Dahua"),
        (("intelbras",), "Intelbras"),
        (("vivotek",), "Vivotek"),
        (("uniview",), "Uniview"),
        (("reolink",), "Reolink"),
        (("bosch security",), "Bosch Security Systems"),
        (("axis communications",), "Axis Communications"),
        (("kyocera",), "Kyocera"),
        (("brother",), "Brother"),
        (("epson",), "Epson"),
        (("canon",), "Canon"),
        (("ricoh",), "Ricoh"),
        (("lexmark",), "Lexmark"),
        (("xerox",), "Xerox"),
        (("pantum",), "Pantum"),
        (("zebra",), "Zebra Technologies"),
    )
    for terms, target in rules:
        if any(term in low for term in terms):
            return target
    return raw[:80]


def is_generic_model(value):
    low = norm(value)
    if not low:
        return True
    return any(low == marker.strip() or low.startswith(marker) for marker in GENERIC_MODEL_MARKERS)


def is_generic_name(value):
    upper = clean(value).upper()
    return not upper or any(upper.startswith(prefix) for prefix in GENERIC_NAME_PREFIXES)


def confidence_score(value):
    text = clean(value).upper()
    if text.isdigit():
        return int(text)
    return CONFIDENCE_SCORES.get(text, 0)


def confidence_name(score):
    if score >= 90:
        return "HIGH"
    if score >= 65:
        return "MEDIUM"
    if score >= 35:
        return "LOW"
    return "NONE"


def _append_unique(values, value):
    text = clean(value)
    if text and text not in values:
        values.append(text)


def service_script_values(discovery, accepted_names=None):
    values = []
    accepted = set(clean(name).lower() for name in (accepted_names or []))
    for service in discovery.get("open_services") or []:
        for name, value in (service.get("scripts") or {}).items():
            low = clean(name).lower()
            if accepted and low not in accepted and not any(token in low for token in accepted):
                continue
            if clean(value):
                values.append((low, clean(value)))
    return values


def evidence_text(discovery):
    values = []
    for key in (
        "reverse_dns", "mac_vendor", "snmp_name", "snmp_description",
        "snmp_object_id", "snmp_lldp_name", "snmp_lldp_description",
        "snmp_lldp_chassis_id",
    ):
        _append_unique(values, discovery.get(key))
    primary = discovery.get("snmp_entity_primary") or {}
    inventory = [primary] if primary else []
    inventory.extend(discovery.get("snmp_entity_inventory") or [])
    for row in inventory:
        for key in (
            "description", "name", "manufacturer", "model", "serial",
            "hardware_rev", "firmware_rev", "software_rev", "alias",
            "printer_mib_text", "protocol_text",
        ):
            _append_unique(values, row.get(key))
    for service in discovery.get("open_services") or []:
        for key in (
            "service", "product", "version", "extrainfo", "hostname",
            "ostype", "devicetype", "tunnel",
        ):
            _append_unique(values, service.get(key))
        for cpe in service.get("cpes") or []:
            _append_unique(values, cpe)
        for name, value in (service.get("scripts") or {}).items():
            _append_unique(values, name)
            _append_unique(values, value)
    return "\n".join(values)


def _field(patterns, text):
    for pattern in patterns:
        match = re.search(pattern, text or "", re.I | re.M)
        if match:
            return clean(match.group(1)).strip("\"'")[:160]
    return ""


def _model_from_patterns(text, patterns):
    for pattern in patterns:
        match = re.search(pattern, text or "", re.I)
        if match:
            return clean(match.group(1))[:120]
    return ""


def _identity(role="", manufacturer="", model="", serial="", firmware="",
              source="", score=0, evidence=None, facts=None):
    return {
        "role": clean(role),
        "manufacturer": canonical_manufacturer(manufacturer),
        "model": clean(model)[:120],
        "serial": norm_serial(serial),
        "firmware": clean(firmware)[:120],
        "source": clean(source),
        "score": int(score or 0),
        "confidence": confidence_name(int(score or 0)),
        "evidence": list(evidence or []),
        "facts": dict(facts or {}),
    }


def _s7_identity(discovery, text):
    scripts = service_script_values(discovery, ("s7-info", "s7"))
    combined = "\n".join(value for name, value in scripts)
    if not combined and not re.search(r"\bSIMATIC\b|\bS7[- ]?(?:300|400|1200|1500)\b", text, re.I):
        return {}
    raw = combined or text
    order_code = _field((
        r"(?:Order Code|Order number|Module Type|Module):\s*([^\r\n]+)",
        r"\b(6ES7\s*[0-9A-Z-]{6,})\b",
    ), raw)
    module_name = _field((r"Module name:\s*([^\r\n]+)", r"System Name:\s*([^\r\n]+)"), raw)
    serial = _field((r"Serial Number:\s*([^\r\n]+)", r"Serial:\s*([^\r\n]+)"), raw)
    firmware = _field((r"Firmware(?: Version)?:\s*([^\r\n]+)", r"Version:\s*([^\r\n]+)"), raw)
    model = order_code or module_name or _model_from_patterns(raw, (
        r"\b(CPU\s*[0-9A-Z-]+(?:\s+[0-9A-Z/-]+)*)\b",
        r"\b(SIMATIC\s+S7[- ]?(?:300|400|1200|1500)[^\r\n,;]*)",
        r"\b(IM\s*153-[0-9A-Z/-]+)\b",
        r"\b(CP\s*(?:1543-1|443-1))\b",
    ))
    low = norm(raw)
    if "io-device" in low or re.search(r"\bIM\s*153", raw, re.I):
        role = "INDUSTRIAL_IO"
    elif re.search(r"\bCP\s*(?:1543-1|443-1)\b", raw, re.I):
        role = "INDUSTRIAL_COMMUNICATION"
    else:
        role = "INDUSTRIAL_PLC"
    score = 99 if order_code and serial else (97 if model else 90)
    return _identity(
        role, "Siemens", model, serial, firmware, "siemens-s7", score,
        ["Siemens S7 structured identity"],
        {"order_code": order_code, "module_name": module_name},
    )


def _enip_identity(discovery, text):
    scripts = service_script_values(discovery, ("enip", "ethernet-ip", "ethernetip"))
    combined = "\n".join(value for name, value in scripts)
    if not combined and not re.search(r"EtherNet/IP|CIP Identity", text, re.I):
        return {}
    raw = combined or text
    vendor = _field((r"Vendor(?: Name)?:\s*([^\r\n]+)",), raw)
    product = _field((r"Product Name:\s*([^\r\n]+)", r"Product:\s*([^\r\n]+)"), raw)
    product_code = _field((r"Product Code:\s*([^\r\n]+)",), raw)
    serial = _field((r"Serial Number:\s*([^\r\n]+)", r"Serial:\s*([^\r\n]+)"), raw)
    revision = _field((r"Revision:\s*([^\r\n]+)",), raw)
    device_type = _field((r"Device Type:\s*([^\r\n]+)",), raw)
    role = "INDUSTRIAL_DEVICE"
    low = norm(" ".join((device_type, product, raw)))
    if any(token in low for token in ("programmable logic", "plc", "controller")):
        role = "INDUSTRIAL_PLC"
    elif any(token in low for token in ("remote i/o", "io adapter", "i/o adapter")):
        role = "INDUSTRIAL_IO"
    elif any(token in low for token in ("drive", "inverter", "variable frequency")):
        role = "INDUSTRIAL_DRIVE"
    elif any(token in low for token in ("communication adapter", "gateway", "bridge")):
        role = "INDUSTRIAL_COMMUNICATION"
    score = 98 if vendor and product and serial else (94 if vendor and product else 82)
    return _identity(
        role, vendor, product or product_code, serial, revision,
        "ethernet-ip-identity", score,
        ["EtherNet/IP CIP Identity"],
        {"product_code": product_code, "device_type": device_type, "revision": revision},
    )


def _bacnet_identity(discovery, text):
    scripts = service_script_values(discovery, ("bacnet",))
    combined = "\n".join(value for name, value in scripts)
    if not combined and "bacnet" not in norm(text):
        return {}
    raw = combined or text
    vendor = _field((r"Vendor Name:\s*([^\r\n]+)", r"Vendor:\s*([^\r\n]+)"), raw)
    model = _field((r"Model Name:\s*([^\r\n]+)", r"Model:\s*([^\r\n]+)"), raw)
    firmware = _field((r"Firmware Revision:\s*([^\r\n]+)", r"Firmware:\s*([^\r\n]+)"), raw)
    app_version = _field((r"Application Software Version:\s*([^\r\n]+)",), raw)
    object_name = _field((r"Object Name:\s*([^\r\n]+)",), raw)
    instance = _field((r"(?:Device )?Instance:\s*([^\r\n]+)",), raw)
    score = 96 if vendor and model else (82 if object_name or instance else 65)
    return _identity(
        "INDUSTRIAL_CONTROLLER", vendor, model or object_name, "", firmware,
        "bacnet-device", score, ["BACnet device identity"],
        {"object_name": object_name, "instance": instance, "application_version": app_version},
    )


def _modbus_identity(discovery, text):
    scripts = service_script_values(discovery, ("modbus",))
    combined = "\n".join(value for name, value in scripts)
    if not combined:
        return {}
    raw = combined
    vendor = _field((r"Vendor(?:Name| Name)?:\s*([^\r\n]+)",), raw)
    product = _field((r"Product(?:Name| Name)?:\s*([^\r\n]+)",), raw)
    model = _field((r"Model(?:Name| Name)?:\s*([^\r\n]+)",), raw)
    revision = _field((r"(?:MajorMinorRevision|Revision):\s*([^\r\n]+)",), raw)
    if not any((vendor, product, model)):
        return {}
    score = 92 if vendor and (model or product) else 78
    return _identity(
        "INDUSTRIAL_DEVICE", vendor, model or product, "", revision,
        "modbus-device-identification", score,
        ["Modbus device identification"], {"product": product},
    )


def _industrial_snmp_identity(discovery, text):
    object_id = clean(discovery.get("snmp_object_id"))
    exact = INDUSTRIAL_OID_CATALOG.get(object_id)
    if exact:
        return _identity(
            exact["role"], exact["manufacturer"], exact["model"], "", "",
            exact["source"], 99, ["Exact industrial sysObjectID identity"],
        )
    raw = "\n".join((clean(discovery.get("snmp_description")), text))
    patterns = (
        (r"\b(NPort\s+[0-9A-Z-]+)\b", "Moxa", "INDUSTRIAL_COMMUNICATION"),
        (r"\b(EDS-[0-9A-Z-]+)\b", "Moxa", "INDUSTRIAL_SWITCH"),
        (r"\b(SCALANCE\s+[0-9A-Z-]+)\b", "Siemens", "INDUSTRIAL_SWITCH"),
        (r"\b(PAC(?:3220|4200))\b", "Siemens", "INDUSTRIAL_POWER_METER"),
        (r"\b(SRW01[- ]?ETH)\b", "WEG", "INDUSTRIAL_MOTOR_PROTECTION"),
        (r"\b(Westermo\s+Lynx[^\r\n,;]*)", "Westermo", "INDUSTRIAL_SWITCH"),
    )
    for pattern, manufacturer, role in patterns:
        model = _model_from_patterns(raw, (pattern,))
        if model:
            return _identity(
                role, manufacturer, model, "", "", "industrial-snmp-fingerprint", 96,
                ["Industrial SNMP model fingerprint"],
            )
    return {}


def industrial_identity(discovery):
    text = evidence_text(discovery)
    candidates = [
        _s7_identity(discovery, text),
        _enip_identity(discovery, text),
        _bacnet_identity(discovery, text),
        _modbus_identity(discovery, text),
        _industrial_snmp_identity(discovery, text),
    ]
    candidates = [row for row in candidates if row]
    if not candidates:
        return {}
    candidates.sort(key=lambda row: (row.get("score", 0), bool(row.get("serial")), bool(row.get("model"))), reverse=True)
    best = dict(candidates[0])
    best["corroborating_sources"] = [row.get("source") for row in candidates[1:] if row.get("source")]
    return best


def _onvif_identity(discovery, text):
    scripts = service_script_values(discovery, ("onvif", "ws-discovery", "wsdd", "upnp"))
    combined = "\n".join(value for name, value in scripts)
    raw = combined or text
    if not combined and not re.search(r"\bonvif\b|NetworkVideoTransmitter|NetworkVideoRecorder", raw, re.I):
        return {}
    manufacturer = _field((r"Manufacturer:\s*([^\r\n]+)", r"<[^>]*Manufacturer[^>]*>([^<]+)"), raw)
    model = _field((r"Model:\s*([^\r\n]+)", r"<[^>]*Model[^>]*>([^<]+)"), raw)
    firmware = _field((r"Firmware(?: Version)?:\s*([^\r\n]+)", r"<[^>]*FirmwareVersion[^>]*>([^<]+)"), raw)
    serial = _field((r"Serial(?: Number)?:\s*([^\r\n]+)", r"<[^>]*SerialNumber[^>]*>([^<]+)"), raw)
    hardware_id = _field((r"Hardware(?: ID|Id)?:\s*([^\r\n]+)", r"<[^>]*HardwareId[^>]*>([^<]+)"), raw)
    low = norm(raw)
    if any(token in low for token in ("networkvideorecorder", "network video recorder", " type:nvr", "/nvr")):
        role = "NVR"
    elif any(token in low for token in ("digital video recorder", " type:dvr", "/dvr", "xvr")):
        role = "DVR"
    elif any(token in low for token in ("videoencoder", "video encoder")):
        role = "VIDEO_ENCODER"
    elif any(token in low for token in ("networkvideotransmitter", "network camera", "ip camera", " type:camera")):
        role = "CAMERA"
    else:
        role = "VIDEO_SURVEILLANCE_DEVICE"
    score = 99 if manufacturer and model and serial else (97 if manufacturer and model else 88)
    return _identity(
        role, manufacturer, model, serial, firmware, "onvif-device-information", score,
        ["ONVIF/WS-Discovery identity"], {"hardware_id": hardware_id},
    )


def _cctv_fingerprint_identity(discovery, text):
    model_patterns = (
        (r"\b(DS-(?:2CD|2DE|2DF|76|77|96)[A-Z0-9-]+)\b", "Hikvision"),
        (r"\b(iDS-[A-Z0-9-]+)\b", "Hikvision"),
        (r"\b(DHI-(?:IPC|NVR|XVR|DVR)[A-Z0-9-]+)\b", "Dahua"),
        (r"\b((?:IPC|NVR|XVR|DVR)[-_]?[A-Z0-9-]{3,})\b", ""),
        (r"\b(MHDX\s*[A-Z0-9-]+)\b", "Intelbras"),
        (r"\b(VIP\s*[A-Z0-9-]+)\b", "Intelbras"),
        (r"\b(RLC-[A-Z0-9-]+)\b", "Reolink"),
        (r"\b(UVC-G[A-Z0-9-]+)\b", "Ubiquiti"),
        (r"\b(VIGI\s+[A-Z0-9-]+)\b", "TP-Link"),
        (r"\b(AXIS\s+[A-Z0-9-]+)\b", "Axis Communications"),
    )
    model = ""
    manufacturer = ""
    for pattern, vendor in model_patterns:
        model = _model_from_patterns(text, (pattern,))
        if model:
            manufacturer = vendor
            break
    low = norm(text)
    if not manufacturer:
        manufacturer = canonical_manufacturer(clean(discovery.get("mac_vendor")))
    if not manufacturer:
        for token, vendor in (
            ("hikvision", "Hikvision"), ("dahua", "Dahua"),
            ("intelbras", "Intelbras"), ("axis communications", "Axis Communications"),
            ("vivotek", "Vivotek"), ("uniview", "Uniview"),
            ("reolink", "Reolink"), ("hanwha", "Hanwha Vision"),
        ):
            if token in low:
                manufacturer = vendor
                break
    if not model and not manufacturer:
        return {}
    if re.search(r"\bNVR\b|network video recorder", text, re.I):
        role = "NVR"
    elif re.search(r"\b(?:DVR|XVR)\b|digital video recorder", text, re.I):
        role = "DVR"
    elif re.search(r"\b(?:2CD|2DE|2DF|IPC|VIP|RLC|UVC-G|VIGI|network camera|ip camera)\b", text, re.I):
        role = "CAMERA"
    else:
        role = "VIDEO_SURVEILLANCE_DEVICE"
    score = 96 if model and manufacturer else 82
    return _identity(role, manufacturer, model, "", "", "cctv-fingerprint", score, ["CCTV model/vendor fingerprint"])


def cctv_identity(discovery):
    text = evidence_text(discovery)
    candidates = [_onvif_identity(discovery, text), _cctv_fingerprint_identity(discovery, text)]
    candidates = [row for row in candidates if row]
    if not candidates:
        return {}
    candidates.sort(key=lambda row: (row.get("score", 0), bool(row.get("serial")), bool(row.get("model"))), reverse=True)
    return candidates[0]


def all_macs(discovery, classified=None):
    values = []
    classified = classified or {}
    for value in (
        discovery.get("mac"), discovery.get("snmp_bridge_mac"),
        classified.get("management_mac"), classified.get("primary_mac"),
    ):
        mac = norm_mac(value)
        if mac and mac not in values:
            values.append(mac)
    for row in discovery.get("snmp_interface_macs") or []:
        mac = norm_mac(row.get("mac"))
        if mac and mac not in values:
            values.append(mac)
    for value in classified.get("secondary_macs") or []:
        mac = norm_mac(value)
        if mac and mac not in values:
            values.append(mac)
    return values


def virtual_mac_vendor(mac):
    normalized = norm_mac(mac)
    return VIRTUAL_OUIS.get(normalized[:8], "") if normalized else ""


def infer_asset_nature(discovery, classified=None):
    classified = classified or {}
    if discovery.get("netbox_virtual_machine_id") or discovery.get("virtual_machine_id"):
        return "VIRTUAL_MACHINE", "netbox-virtualization-match", 100
    if discovery.get("assigned_object_type") == "virtualization.vminterface":
        return "VIRTUAL_MACHINE", "netbox-vminterface-owner", 100
    role = clean(classified.get("role"))
    if role in (
        "NETWORK_SWITCH", "WIRELESS_AP", "FIREWALL", "PRINTER", "CAMERA", "NVR", "DVR",
        "VIDEO_ENCODER", "OOB_MANAGEMENT", "STORAGE", "INDUSTRIAL_PLC", "INDUSTRIAL_IO",
        "INDUSTRIAL_SWITCH", "INDUSTRIAL_COMMUNICATION", "INDUSTRIAL_POWER_METER",
        "INDUSTRIAL_DRIVE", "INDUSTRIAL_MOTOR_PROTECTION", "INDUSTRIAL_CONTROLLER",
    ):
        return "PHYSICAL_DEVICE", "role-physical", 98
    primary = discovery.get("snmp_entity_primary") or {}
    serial = norm_serial(classified.get("serial") or primary.get("serial"))
    model = clean(classified.get("model") or primary.get("model"))
    if serial and model and not is_generic_model(model):
        return "PHYSICAL_DEVICE", "hardware-serial-model", 96
    virtual = sorted(set(virtual_mac_vendor(mac) for mac in all_macs(discovery, classified) if virtual_mac_vendor(mac)))
    if len(virtual) == 1:
        return "VIRTUAL_CANDIDATE", "virtual-mac-oui:{0}".format(virtual[0]), 72
    if canonical_manufacturer(discovery.get("mac_vendor")) and not virtual:
        return "PHYSICAL_CANDIDATE", "physical-mac-oui", 65
    return "UNKNOWN", "insufficient-evidence", 0


def observed_name(discovery, classified=None):
    classified = classified or {}
    candidates = (
        (classified.get("printer_mib_name"), "printer-mib"),
        (discovery.get("snmp_name"), "snmp-name"),
        (discovery.get("snmp_lldp_name"), "lldp-name"),
        (classified.get("hostname"), classified.get("hostname_source") or "classifier"),
        (discovery.get("reverse_dns"), "reverse-dns"),
    )
    for value, source in candidates:
        name = clean(value).strip(".")
        if name and norm(name) not in ("unknown", "sem nome", "sysname not set"):
            return name, source
    return "", ""


def stable_discovery_uid(discovery, classified=None):
    classified = classified or {}
    manufacturer = canonical_manufacturer(classified.get("manufacturer"))
    serial = norm_serial(classified.get("serial"))
    if serial:
        return "SERIAL:{0}:{1}".format(norm(manufacturer) or "unknown", serial)
    chassis = clean(discovery.get("snmp_lldp_chassis_id"))
    chassis_mac = norm_mac(chassis)
    if chassis_mac:
        return "CHASSIS-MAC:{0}".format(chassis_mac)
    macs = all_macs(discovery, classified)
    management = norm_mac(classified.get("management_mac"))
    if management:
        return "MGMT-MAC:{0}".format(management)
    if len(macs) == 1:
        return "MAC:{0}".format(macs[0])
    object_id = clean(discovery.get("snmp_object_id"))
    if object_id and macs:
        return "OID-MAC:{0}:{1}".format(object_id, macs[0])
    seed = "|".join((
        clean(discovery.get("ip")), object_id,
        clean(discovery.get("snmp_name")), clean(classified.get("model")),
    ))
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16].upper()
    return "WEAK:{0}".format(digest)


def collision_suffix(asset):
    serial = norm_serial(asset.get("serial"))
    if len(serial) >= 4:
        return serial[-6:]
    macs = []
    for value in asset.get("macs") or []:
        mac = norm_mac(value)
        if mac and mac not in macs:
            macs.append(mac)
    if len(macs) == 1:
        return macs[0].replace(":", "")[-6:]
    uid = clean(asset.get("discovery_uid"))
    if uid and not uid.startswith("WEAK:"):
        return hashlib.sha256(uid.encode("utf-8")).hexdigest()[:6].upper()
    return ""


def apply_identity_candidate(out, candidate, allow_role=True):
    if not candidate:
        return out
    current_score = int(out.get("classification_score") or 0)
    candidate_score = int(candidate.get("score") or 0)
    current_generic = is_generic_model(out.get("model")) or norm(out.get("manufacturer")) in ("", "generic", "unidentified")
    if candidate_score < current_score and not current_generic:
        return out
    if allow_role and candidate.get("role"):
        out["role"] = candidate["role"]
    if candidate.get("manufacturer"):
        out["manufacturer"] = candidate["manufacturer"]
        out["manufacturer_source"] = candidate.get("source")
    if candidate.get("model"):
        out["model"] = candidate["model"]
        out["model_source"] = candidate.get("source")
    if candidate.get("serial"):
        out["serial"] = candidate["serial"]
        out["serial_source"] = candidate.get("source")
    if candidate.get("firmware"):
        out["firmware"] = candidate["firmware"]
        out["firmware_source"] = candidate.get("source")
    out["classification_score"] = max(current_score, candidate_score)
    out["confidence"] = confidence_name(out["classification_score"])
    if out["confidence"] == "HIGH":
        out["classification_state"] = "IDENTIFIED"
    out["identity_source"] = candidate.get("source")
    out["protocol_facts"] = candidate.get("facts") or {}
    evidence = list(out.get("evidence") or [])
    for value in candidate.get("evidence") or []:
        if value not in evidence:
            evidence.append(value)
    out["evidence"] = evidence
    return out


def apply_observed_metadata(discovery, out):
    name, name_source = observed_name(discovery, out)
    nature, nature_source, nature_score = infer_asset_nature(discovery, out)
    out["observed_name"] = name
    out["observed_name_source"] = name_source
    out["asset_nature"] = nature
    out["asset_nature_source"] = nature_source
    out["asset_nature_score"] = nature_score
    out["discovery_uid"] = stable_discovery_uid(discovery, out)
    out["identity_engine_version"] = IDENTITY_ENGINE_VERSION
    out["identity_provenance"] = {
        "name": name_source,
        "manufacturer": clean(out.get("manufacturer_source")),
        "model": clean(out.get("model_source")),
        "serial": clean(out.get("serial_source")),
        "firmware": clean(out.get("firmware_source")),
        "asset_nature": nature_source,
    }
    return out


def review_recommendations(classified):
    recommendations = []
    role = clean(classified.get("role"))
    confidence = clean(classified.get("confidence"))
    nature = clean(classified.get("asset_nature"))
    if confidence in ("LOW", "NONE"):
        recommendations.append("habilitar SNMP read-only ou protocolo de identidade específico")
    if role in ("WEB_APPLIANCE", "VIDEO_SURVEILLANCE_DEVICE") and not clean(classified.get("model")):
        recommendations.append("validar ONVIF/WS-Discovery e credencial de consulta do equipamento")
    if role.startswith("INDUSTRIAL_") and is_generic_model(classified.get("model")):
        recommendations.append("coletar identidade estruturada S7, EtherNet/IP, BACnet ou Modbus")
    if nature == "VIRTUAL_CANDIDATE":
        recommendations.append("correlacionar IP/MAC com o inventário central do vCenter")
    if not clean(classified.get("management_mac")):
        recommendations.append("obter MAC por SNMP da interface proprietária do IP")
    return recommendations
