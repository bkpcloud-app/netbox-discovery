#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import concurrent.futures
import json
import os
import re
import ssl
import sys
import xml.etree.ElementTree as ET

try:
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError, URLError
except ImportError:
    from urllib2 import Request, urlopen, HTTPError, URLError

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, "..", ".."))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.discovery import network_v4 as v4
from modules.product import identity

DISCOVERY_WRAPPER_VERSION = "4.5-product"
ORIG_PROBE_SNMP_ENTITY = v4.probe_snmp_entity
ORIG_SCAN_SERVICES = v4.base.scan_services

CCTV_WEB_PORTS = (80, 81, 88, 443, 8080, 8081, 8443, 10443)


def clean(value):
    return "" if value is None else str(value).strip()


def _catalog_identity(snmp):
    object_id = clean(snmp.get("sysobjectid") or snmp.get("object_id"))
    sysdescr = clean(snmp.get("sysdescr") or snmp.get("description"))
    sysname = clean(snmp.get("sysname") or snmp.get("name"))
    exact = identity.INDUSTRIAL_OID_CATALOG.get(object_id)
    if exact:
        return {
            "manufacturer": exact.get("manufacturer", ""),
            "model": exact.get("model", ""),
            "role_hint": exact.get("role", ""),
            "source": exact.get("source", "sysobjectid-catalog"),
        }

    raw = " ".join((sysname, sysdescr))
    patterns = (
        (r"\b(NPort\s+[0-9A-Z-]+)\b", "Moxa", "INDUSTRIAL_COMMUNICATION"),
        (r"\b(EDS-[0-9A-Z-]+)\b", "Moxa", "INDUSTRIAL_SWITCH"),
        (r"\b(SCALANCE\s+[0-9A-Z-]+)\b", "Siemens", "INDUSTRIAL_SWITCH"),
        (r"\b(PAC(?:3220|4200))\b", "Siemens", "INDUSTRIAL_POWER_METER"),
        (r"\b(SRW01[- ]?ETH)\b", "WEG", "INDUSTRIAL_MOTOR_PROTECTION"),
        (r"\b(Westermo\s+Lynx[^,;\r\n]*)", "Westermo", "INDUSTRIAL_SWITCH"),
    )
    for pattern, manufacturer, role in patterns:
        match = re.search(pattern, raw, re.I)
        if match:
            return {
                "manufacturer": manufacturer,
                "model": clean(match.group(1))[:120],
                "role_hint": role,
                "source": "snmp-protocol-catalog",
            }
    return {}


def _catalog_entity(ip, snmp):
    item = _catalog_identity(snmp)
    if not item:
        return {}
    sysname = clean(snmp.get("sysname") or snmp.get("name"))
    object_id = clean(snmp.get("sysobjectid") or snmp.get("object_id"))
    uid_seed = "{0}:{1}:{2}".format(object_id, item.get("model"), ip)
    return {
        "index": "protocol-catalog:1",
        "description": "Protocol identity catalog",
        "contained_in": "",
        "class": "chassis(3)",
        "class_id": "3",
        "parent_rel_pos": "",
        "name": sysname or item.get("model", ""),
        "hardware_rev": "",
        "firmware_rev": "",
        "software_rev": "",
        "serial": "",
        "manufacturer": item.get("manufacturer", ""),
        "model": item.get("model", ""),
        "alias": "",
        "asset_id": "PROTOCOL:{0}".format(uid_seed),
        "is_fru": "",
        "source": item.get("source", "protocol-catalog"),
        "management_ip": ip,
        "role_hint": item.get("role_hint", ""),
        "protocol_text": "sysObjectID={0}; sysName={1}".format(object_id, sysname),
    }


def _is_more_specific(candidate, current):
    if not candidate:
        return False
    if not current:
        return True
    current_model = clean(current.get("model"))
    candidate_model = clean(candidate.get("model"))
    if identity.is_generic_model(current_model) and not identity.is_generic_model(candidate_model):
        return True
    if not current_model and candidate_model:
        return True
    return False


def probe_snmp_entity(ip, snmp):
    entity = ORIG_PROBE_SNMP_ENTITY(ip, snmp)
    catalog = _catalog_entity(ip, snmp)
    if not catalog:
        return entity

    inventory = list(entity.get("inventory") or [])
    duplicate = any(
        clean(row.get("source")) == clean(catalog.get("source"))
        and clean(row.get("model")) == clean(catalog.get("model"))
        for row in inventory
    )
    if not duplicate:
        inventory.append(catalog)
    entity["inventory"] = inventory
    entity["count"] = len(inventory)
    if _is_more_specific(catalog, entity.get("primary") or {}):
        entity["primary"] = catalog
    return entity


def _local_tag(tag):
    return clean(tag).split("}", 1)[-1].split(":", 1)[-1].casefold()


def _extract_device_info(body, default_manufacturer=""):
    values = {}
    aliases = {
        "manufacturer": "manufacturer",
        "model": "model",
        "firmwareversion": "firmware",
        "firmware": "firmware",
        "serialnumber": "serial",
        "serialno": "serial",
        "hardwareid": "hardware_id",
        "deviceid": "device_id",
        "devicename": "device_name",
    }
    raw = clean(body)
    if not raw:
        return values

    try:
        root = ET.fromstring(raw)
    except Exception:
        root = None
    if root is not None:
        for node in root.iter():
            key = aliases.get(_local_tag(node.tag))
            value = clean(node.text)
            if key and value and not values.get(key):
                values[key] = value

    if not values:
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = None
        if isinstance(parsed, dict):
            stack = [parsed]
            while stack:
                current = stack.pop()
                for key, value in current.items():
                    normalized = aliases.get(_local_tag(key))
                    if normalized and not isinstance(value, (dict, list)) and clean(value) and not values.get(normalized):
                        values[normalized] = clean(value)
                    elif isinstance(value, dict):
                        stack.append(value)
                    elif isinstance(value, list):
                        stack.extend(item for item in value if isinstance(item, dict))

    if not values:
        patterns = {
            "manufacturer": r"Manufacturer\s*[:=]\s*([^\r\n<]+)",
            "model": r"Model\s*[:=]\s*([^\r\n<]+)",
            "firmware": r"Firmware(?:\s+Version)?\s*[:=]\s*([^\r\n<]+)",
            "serial": r"Serial(?:\s+Number|\s+No\.?)?\s*[:=]\s*([A-Za-z0-9._/-]{4,64})",
            "hardware_id": r"Hardware(?:\s+ID)?\s*[:=]\s*([^\r\n<]+)",
        }
        for key, pattern in patterns.items():
            match = re.search(pattern, raw, re.I)
            if match:
                values[key] = clean(match.group(1))

    if default_manufacturer and not values.get("manufacturer"):
        values["manufacturer"] = default_manufacturer
    serial = identity.norm_serial(values.get("serial"))
    if serial:
        values["serial"] = serial
    else:
        values.pop("serial", None)
    return values


def _http_call(url, method="GET", body=None, content_type=""):
    data = body.encode("utf-8") if isinstance(body, str) else body
    request = Request(url, data=data)
    request.add_header("User-Agent", "netbox-discovery/1.11 read-only identity")
    request.add_header("Accept", "application/xml, text/xml, application/json")
    if content_type:
        request.add_header("Content-Type", content_type)
    if method != "GET":
        request.get_method = lambda: method
    context = ssl._create_unverified_context() if url.lower().startswith("https://") else None
    try:
        response = urlopen(request, timeout=4, context=context)
        payload = response.read(262144)
        return int(getattr(response, "status", 200) or 200), payload.decode("utf-8", "replace")
    except HTTPError as exc:
        try:
            payload = exc.read(65536).decode("utf-8", "replace")
        except Exception:
            payload = ""
        return int(getattr(exc, "code", 0) or 0), payload
    except (URLError, OSError, ValueError):
        return 0, ""


def _service_web_endpoints(services):
    endpoints = []
    for service in services or []:
        if clean(service.get("protocol")) != "tcp":
            continue
        try:
            port = int(service.get("port") or 0)
        except Exception:
            port = 0
        if port not in CCTV_WEB_PORTS:
            continue
        text = " ".join((
            clean(service.get("service")), clean(service.get("product")),
            clean(service.get("tunnel")),
        )).casefold()
        https = port in (443, 8443, 10443) or "ssl" in text or "https" in text
        scheme = "https" if https else "http"
        default = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
        base_url = "{0}://{{ip}}{1}".format(scheme, "" if default else ":{0}".format(port))
        if base_url not in endpoints:
            endpoints.append(base_url)
    return endpoints


def _summary(values):
    lines = []
    labels = (
        ("manufacturer", "Manufacturer"),
        ("model", "Model"),
        ("firmware", "Firmware Version"),
        ("serial", "Serial Number"),
        ("hardware_id", "Hardware ID"),
        ("device_id", "Device ID"),
        ("device_name", "Device Name"),
    )
    for key, label in labels:
        value = clean(values.get(key))
        if value:
            lines.append("{0}: {1}".format(label, value[:160]))
    return "\n".join(lines)


def _probe_cctv_identity(item):
    ip, services = item
    if not v4.base._strong_cctv_service_signature(services):
        return ip, {}
    combined = {}
    source = ""
    endpoints = _service_web_endpoints(services)
    soap = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<s:Envelope xmlns:s=\"http://www.w3.org/2003/05/soap-envelope\"><s:Body>
<GetDeviceInformation xmlns=\"http://www.onvif.org/ver10/device/wsdl\"/>
</s:Body></s:Envelope>"""
    for template in endpoints[:3]:
        root = template.format(ip=ip)
        code, body = _http_call(root + "/ISAPI/System/deviceInfo")
        if code == 200:
            found = _extract_device_info(body, "Hikvision")
            if found:
                combined.update(dict((key, value) for key, value in found.items() if value))
                source = "hikvision-isapi-anonymous"
        if not combined.get("serial") or not combined.get("model"):
            code, body = _http_call(
                root + "/onvif/device_service", method="POST", body=soap,
                content_type="application/soap+xml; charset=utf-8",
            )
            if code == 200:
                found = _extract_device_info(body)
                for key, value in found.items():
                    if value and not combined.get(key):
                        combined[key] = value
                if found:
                    source = source or "onvif-getdeviceinformation-anonymous"
        if combined.get("serial") and combined.get("model"):
            break
    if not combined:
        return ip, {}
    combined["identity_source"] = source
    return ip, combined


def _enrich_cctv_identity(results):
    candidates = [
        (ip, services) for ip, services in results.items()
        if v4.base._strong_cctv_service_signature(services)
    ]
    if not candidates:
        return
    print("  Hikvision/ONVIF identity: {0} candidatos...".format(len(candidates)), flush=True)
    workers = min(8, max(1, len(candidates)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for ip, values in pool.map(_probe_cctv_identity, candidates):
            if not values:
                continue
            output = _summary(values)
            if not output:
                continue
            incoming = {
                ip: [{
                    "port": 0,
                    "protocol": "host",
                    "state_reason": "",
                    "service": "cctv-device-information",
                    "product": clean(values.get("model")),
                    "version": clean(values.get("firmware")),
                    "extrainfo": clean(values.get("identity_source")),
                    "hostname": clean(values.get("device_name")),
                    "ostype": "",
                    "devicetype": "camera",
                    "tunnel": "",
                    "method": "read-only-http",
                    "confidence": "10",
                    "cpes": [],
                    "scripts": {"onvif-hikvision-device-information": output},
                    "scan_sources": ["cctv-read-only-device-info"],
                }]
            }
            v4.base._merge_service_results(results, incoming)


def scan_services(ip_addresses):
    results = ORIG_SCAN_SERVICES(ip_addresses)
    _enrich_cctv_identity(results)
    return results


def main():
    old_probe = v4.probe_snmp_entity
    old_scan = v4.base.scan_services
    old_version = v4.DISCOVERY_WRAPPER_VERSION
    try:
        v4.probe_snmp_entity = probe_snmp_entity
        v4.base.scan_services = scan_services
        v4.DISCOVERY_WRAPPER_VERSION = DISCOVERY_WRAPPER_VERSION
        return v4.main()
    finally:
        v4.DISCOVERY_WRAPPER_VERSION = old_version
        v4.base.scan_services = old_scan
        v4.probe_snmp_entity = old_probe


if __name__ == "__main__":
    sys.exit(main())
