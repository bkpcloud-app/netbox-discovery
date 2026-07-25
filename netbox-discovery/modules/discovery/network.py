#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import print_function

import csv
import concurrent.futures
import datetime
import ipaddress
import json
import os
import re
import socket
import ssl
import subprocess
import sys
import xml.etree.ElementTree as ET

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from lib.config import load_config

try:
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError
except ImportError:
    from urllib2 import Request, urlopen, HTTPError


DEFAULT_NETWORKS_FILE = os.path.join(PROJECT_ROOT, "config", "networks.conf")
DEFAULT_EXCLUSIONS_FILE = os.path.join(PROJECT_ROOT, "config", "exclusions.conf")
DEFAULT_COMMUNITIES_FILE = os.path.join(PROJECT_ROOT, "config", "snmp-communities.conf")
DEFAULT_OUTPUT_DIR = os.path.join(PROJECT_ROOT, "reports")

CORE_DISCOVERY_TCP_PORTS = [
    22, 53, 80, 135, 139, 389, 443, 445, 515, 631, 636,
    9100, 3389, 5985, 5986, 8006, 8080, 8443, 8291,
]

EXTENDED_DISCOVERY_TCP_PORTS = [
    # Infra / storage / virtualização
    25, 110, 111, 143, 427, 541, 548, 554, 902, 903,
    1433, 1521, 1720, 1883, 2049, 2222, 3260, 3306,
    5000, 5001, 5060, 5061, 5432, 5480, 5672, 5989,
    6379, 8081, 8883, 9200, 9443, 9600, 10000, 10443,
    27017, 34567, 37777,

    # Industrial / OT
    102, 502, 1962, 2404, 4840, 44818, 20000,
]

WEB_ENRICHMENT_PORTS = {
    80, 443, 631, 5000, 5001, 5480, 5985, 8006,
    8080, 8081, 8443, 9200, 9443, 10000, 10443,
}

UDP_EVIDENCE_PORTS = [
    53, 69, 123, 137, 161, 500, 623, 1900,
    2222, 4500, 5353, 47808, 44818,
]

DISCOVERY_RESCUE_TCP_PORTS = [
    22, 80, 102, 135, 139, 443, 445, 502, 554,
    902, 3389, 8006, 8080, 8291, 8443, 9100,
]

BROAD_TCP_TOP_PORTS = 100
RESIDUAL_TCP_TOP_PORTS = 1000

SYSNAME_OID = ".1.3.6.1.2.1.1.5.0"
SYSDESCR_OID = ".1.3.6.1.2.1.1.1.0"
SYSOBJECTID_OID = ".1.3.6.1.2.1.1.2.0"
SYSUPTIME_OID = ".1.3.6.1.2.1.1.3.0"
SYSCONTACT_OID = ".1.3.6.1.2.1.1.4.0"
SYSLOCATION_OID = ".1.3.6.1.2.1.1.6.0"
SYSSERVICES_OID = ".1.3.6.1.2.1.1.7.0"

ENTITY_PHYSICAL_TABLE_OID = ".1.3.6.1.2.1.47.1.1.1.1"
IF_DESCR_OID = ".1.3.6.1.2.1.2.2.1.2"
IF_TYPE_OID = ".1.3.6.1.2.1.2.2.1.3"
IF_PHYS_ADDRESS_OID = ".1.3.6.1.2.1.2.2.1.6"
IF_OPER_STATUS_OID = ".1.3.6.1.2.1.2.2.1.8"
IF_NAME_OID = ".1.3.6.1.2.1.31.1.1.1.1"
IF_ALIAS_OID = ".1.3.6.1.2.1.31.1.1.1.18"

IP_ADDR_TABLE_OID = ".1.3.6.1.2.1.4.20.1"
IP_AD_ENT_ADDR_OID = ".1.3.6.1.2.1.4.20.1.1"
IP_AD_ENT_IFINDEX_OID = ".1.3.6.1.2.1.4.20.1.2"
IP_AD_ENT_NETMASK_OID = ".1.3.6.1.2.1.4.20.1.3"

DOT1D_BASE_BRIDGE_ADDRESS_OID = ".1.3.6.1.2.1.17.1.1.0"
LLDP_LOC_CHASSIS_ID_OID = ".1.0.8802.1.1.2.1.3.2.0"
LLDP_LOC_SYS_NAME_OID = ".1.0.8802.1.1.2.1.3.3.0"
LLDP_LOC_SYS_DESC_OID = ".1.0.8802.1.1.2.1.3.4.0"

INVALID_SNMP_MARKERS = (
    "no such object",
    "no such instance",
    "end of mib",
    "unknown object identifier",
    "no more variables left in this mib view",
    "timeout: no response",
)


def load_discovery_settings():
    config = load_config()
    netbox = config.get("netbox", {})
    discovery = config.get("discovery", {})
    paths = config.get("paths", {})

    settings = {
        "NETBOX_URL": str(netbox.get("url", "")),
        "NETBOX_TOKEN": str(netbox.get("token", "")),
        "NETBOX_SSL_VERIFY": str(netbox.get("verify_ssl", False)).lower(),
        "CLIENT": str(config.get("tenant", "")),
        "SITE": str(discovery.get("site", "")),
        "NETWORKS_FILE": str(discovery.get("networks_file", DEFAULT_NETWORKS_FILE)),
        "EXCLUSIONS_FILE": str(discovery.get("exclusions_file", DEFAULT_EXCLUSIONS_FILE)),
        "COMMUNITIES_FILE": str(discovery.get("communities_file", DEFAULT_COMMUNITIES_FILE)),
        "OUTPUT_DIR": str(paths.get("reports", DEFAULT_OUTPUT_DIR)),
    }

    required = ("NETBOX_URL", "NETBOX_TOKEN", "CLIENT", "SITE")
    missing = [name for name in required if not settings[name]]
    if missing:
        raise RuntimeError("Configuração obrigatória ausente: {0}".format(", ".join(missing)))

    return settings


def read_lines(path):
    values = []

    if not os.path.exists(path):
        return values

    with open(path, "r") as handle:
        for raw in handle:
            line = raw.strip()

            if not line or line.startswith("#"):
                continue

            values.append(line)

    return values


def run_command(command, timeout=300):
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )

    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        return 124, stdout, stderr

    return process.returncode, stdout, stderr


def parse_exclusions(lines):
    exclusions = []

    for line in lines:
        if "-" in line and "/" not in line:
            start_text, end_text = line.split("-", 1)

            try:
                exclusions.append((
                    "range",
                    ipaddress.ip_address(start_text.strip()),
                    ipaddress.ip_address(end_text.strip()),
                ))
            except ValueError:
                pass

            continue

        try:
            if "/" in line:
                exclusions.append((
                    "network",
                    ipaddress.ip_network(line, strict=False),
                ))
            else:
                exclusions.append((
                    "ip",
                    ipaddress.ip_address(line),
                ))
        except ValueError:
            pass

    return exclusions


def is_excluded(ip_text, exclusions):
    address = ipaddress.ip_address(ip_text)

    for entry in exclusions:
        if entry[0] == "ip" and address == entry[1]:
            return True

        if entry[0] == "network" and address in entry[1]:
            return True

        if entry[0] == "range" and entry[1] <= address <= entry[2]:
            return True

    return False


def api_check(env):
    url = env["NETBOX_URL"].rstrip("/") + "/api/dcim/sites/?limit=1"

    request = Request(url)
    request.add_header(
        "Authorization",
        "Bearer " + env["NETBOX_TOKEN"],
    )
    request.add_header("Accept", "application/json")

    verify = env.get(
        "NETBOX_SSL_VERIFY",
        "false",
    ).lower() == "true"

    if verify:
        context = ssl.create_default_context()
    else:
        context = ssl._create_unverified_context()

    try:
        response = urlopen(
            request,
            context=context,
            timeout=15,
        )

        response.read()

        return response.getcode()

    except HTTPError as error:
        return error.code

    except Exception as error:
        return "ERROR: {0}".format(error)


def _all_candidate_ips(networks, exclusions):
    values = []

    for network_text in networks:
        network = ipaddress.ip_network(
            network_text,
            strict=False,
        )

        for address in network.hosts():
            ip = str(address)

            if is_excluded(ip, exclusions):
                continue

            values.append(ip)

    return sorted(
        set(values),
        key=lambda item: ipaddress.ip_address(item),
    )


def _parse_discovery_xml(stdout, source):
    hosts = {}

    if not stdout.strip():
        return hosts

    try:
        root = ET.fromstring(stdout)
    except ET.ParseError:
        return hosts

    for host in root.findall("host"):
        status = host.find("status")

        if status is None or status.get("state") != "up":
            continue

        ipv4 = ""
        mac = ""
        vendor = ""

        for address in host.findall("address"):
            if address.get("addrtype") == "ipv4":
                ipv4 = address.get("addr", "")

            if address.get("addrtype") == "mac":
                mac = address.get("addr", "")
                vendor = address.get("vendor", "")

        if not ipv4:
            continue

        hosts[ipv4] = {
            "ip": ipv4,
            "mac": mac,
            "mac_vendor": vendor,
            "reason": status.get("reason", ""),
            "reason_ttl": status.get("reason_ttl", ""),
            "discovery_sources": [source],
        }

    return hosts


def _merge_discovered_hosts(target, incoming):
    for ip, data in incoming.items():
        if ip not in target:
            target[ip] = data
            continue

        current = target[ip]

        if not current.get("mac") and data.get("mac"):
            current["mac"] = data["mac"]

        if not current.get("mac_vendor") and data.get("mac_vendor"):
            current["mac_vendor"] = data["mac_vendor"]

        if not current.get("reason") and data.get("reason"):
            current["reason"] = data["reason"]

        if not current.get("reason_ttl") and data.get("reason_ttl"):
            current["reason_ttl"] = data["reason_ttl"]

        sources = current.setdefault(
            "discovery_sources",
            [],
        )

        for source in data.get("discovery_sources", []):
            if source not in sources:
                sources.append(source)


def _primary_host_discovery(networks):
    command = [
        "nmap",
        "-sn",
        "-n",
        "-PE",
        "-PP",
        "-PS22,80,443,445,3389,8006,8080,8443,8291,9100",
        "-PA22,80,443,445,3389",
        "-PU53,123,161,500,4500",
        "--max-retries",
        "1",
        "--host-timeout",
        "8s",
        "--reason",
        "-oX",
        "-",
    ] + networks

    code, stdout, stderr = run_command(
        command,
        timeout=900,
    )

    if code not in (0, 1):
        raise RuntimeError(
            "Falha no nmap discovery: {0}".format(
                stderr
            )
        )

    return _parse_discovery_xml(
        stdout,
        "nmap-host-discovery",
    )


def _tcp_rescue_hosts(ip_addresses):
    hosts = {}

    if not ip_addresses:
        return hosts

    chunk_size = 64
    total_chunks = (
        len(ip_addresses) + chunk_size - 1
    ) // chunk_size

    for chunk_number, position in enumerate(
        range(0, len(ip_addresses), chunk_size),
        1,
    ):
        chunk = ip_addresses[
            position:position + chunk_size
        ]

        print(
            "  Rescue TCP: lote {0}/{1} ({2} IPs)...".format(
                chunk_number,
                total_chunks,
                len(chunk),
            ),
            flush=True,
        )

        command = [
            "nmap",
            "-Pn",
            "-sT",
            "-n",
            "-T4",
            "--max-retries",
            "0",
            "--host-timeout",
            "7s",
            "--open",
            "-p",
            ",".join(
                str(port)
                for port in DISCOVERY_RESCUE_TCP_PORTS
            ),
            "--reason",
            "-oX",
            "-",
        ] + chunk

        code, stdout, stderr = run_command(
            command,
            timeout=180,
        )

        if not stdout.strip():
            continue

        try:
            root = ET.fromstring(stdout)
        except ET.ParseError:
            continue

        for host in root.findall("host"):
            open_ports = []

            for port_node in host.findall("./ports/port"):
                state = port_node.find("state")

                if (
                    state is not None
                    and state.get("state") == "open"
                ):
                    open_ports.append(
                        port_node.get("portid", "")
                    )

            if not open_ports:
                continue

            ipv4 = ""
            mac = ""
            vendor = ""

            for address in host.findall("address"):
                if address.get("addrtype") == "ipv4":
                    ipv4 = address.get("addr", "")

                if address.get("addrtype") == "mac":
                    mac = address.get("addr", "")
                    vendor = address.get("vendor", "")

            if not ipv4:
                continue

            hosts[ipv4] = {
                "ip": ipv4,
                "mac": mac,
                "mac_vendor": vendor,
                "reason": "tcp-rescue",
                "reason_ttl": "",
                "discovery_sources": [
                    "tcp-rescue-open-port"
                ],
            }

    return hosts


def _quick_snmp_rescue(ip, communities):
    versions = [
        "-v2c",
        "-v1",
    ]

    for version_option in versions:
        for community in communities:
            command = [
                "snmpget",
                version_option,
                "-c",
                community,
                "-t",
                "1",
                "-r",
                "0",
                "-Oqv",
                ip,
                SYSOBJECTID_OID,
            ]

            code, stdout, stderr = run_command(
                command,
                timeout=3,
            )

            value = (
                stdout.splitlines()[0].strip()
                if stdout.strip()
                else ""
            )

            lowered = value.lower()

            if (
                value
                and not any(
                    marker in lowered
                    for marker in INVALID_SNMP_MARKERS
                )
            ):
                return ip

    return ""


def _snmp_rescue_hosts(ip_addresses, communities):
    hosts = {}

    if not ip_addresses or not communities:
        return hosts

    print(
        "  Rescue SNMP: testando {0} IPs restantes...".format(
            len(ip_addresses)
        ),
        flush=True,
    )

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=32
    ) as executor:
        futures = [
            executor.submit(
                _quick_snmp_rescue,
                ip,
                communities,
            )
            for ip in ip_addresses
        ]

        for future in concurrent.futures.as_completed(
            futures
        ):
            try:
                ip = future.result()
            except Exception:
                ip = ""

            if not ip:
                continue

            hosts[ip] = {
                "ip": ip,
                "mac": "",
                "mac_vendor": "",
                "reason": "snmp-response",
                "reason_ttl": "",
                "discovery_sources": [
                    "snmp-rescue"
                ],
            }

    return hosts


def discover_hosts(networks, communities, exclusions):
    hosts = _primary_host_discovery(
        networks
    )

    print(
        "  Discovery primário: {0} hosts".format(
            len(hosts)
        )
    )

    candidates = _all_candidate_ips(
        networks,
        exclusions,
    )

    missing = [
        ip
        for ip in candidates
        if ip not in hosts
    ]

    tcp_hosts = _tcp_rescue_hosts(
        missing
    )

    _merge_discovered_hosts(
        hosts,
        tcp_hosts,
    )

    print(
        "  Rescue TCP adicionou: {0}".format(
            len(tcp_hosts)
        )
    )

    missing = [
        ip
        for ip in candidates
        if ip not in hosts
    ]

    snmp_hosts = _snmp_rescue_hosts(
        missing,
        communities,
    )

    _merge_discovered_hosts(
        hosts,
        snmp_hosts,
    )

    print(
        "  Rescue SNMP adicionou: {0}".format(
            len(snmp_hosts)
        )
    )

    return hosts



def reverse_dns(ip):
    # Resolve PTR sem tornar DNS reverso requisito fatal do discovery.
    try:
        subprocess_mod = __import__("subprocess")
        output = subprocess_mod.check_output(
            ["dig", "+short", "-x", str(ip)],
            stderr=subprocess_mod.DEVNULL,
            universal_newlines=True,
            timeout=5,
        ).strip()

        if not output:
            return ""

        for line in output.splitlines():
            name = line.strip().rstrip(".")
            if name:
                return name

        return ""
    except Exception:
        # Reverse DNS é somente enriquecimento. Falha/ausência de PTR,
        # timeout ou ausência do binário não pode interromper DISCOVER.
        return ""


def _new_service_record(
    port_node,
    scan_source,
):
    state = port_node.find("state")
    service_node = port_node.find("service")

    record = {
        "port": int(port_node.get("portid")),
        "protocol": port_node.get("protocol", ""),
        "state_reason": (
            state.get("reason", "")
            if state is not None
            else ""
        ),
        "service": "",
        "product": "",
        "version": "",
        "extrainfo": "",
        "hostname": "",
        "ostype": "",
        "devicetype": "",
        "tunnel": "",
        "method": "",
        "confidence": "",
        "cpes": [],
        "scripts": {},
        "scan_sources": [scan_source],
    }

    if service_node is not None:
        record["service"] = service_node.get(
            "name",
            "",
        )
        record["product"] = service_node.get(
            "product",
            "",
        )
        record["version"] = service_node.get(
            "version",
            "",
        )
        record["extrainfo"] = service_node.get(
            "extrainfo",
            "",
        )
        record["hostname"] = service_node.get(
            "hostname",
            "",
        )
        record["ostype"] = service_node.get(
            "ostype",
            "",
        )
        record["devicetype"] = service_node.get(
            "devicetype",
            "",
        )
        record["tunnel"] = service_node.get(
            "tunnel",
            "",
        )
        record["method"] = service_node.get(
            "method",
            "",
        )
        record["confidence"] = service_node.get(
            "conf",
            "",
        )
        record["cpes"] = [
            (node.text or "").strip()
            for node in service_node.findall("cpe")
            if (node.text or "").strip()
        ]

    for script_node in port_node.findall("script"):
        script_id = script_node.get(
            "id",
            "",
        )
        output = script_node.get(
            "output",
            "",
        ).strip()

        if script_id and output:
            record["scripts"][script_id] = output

    return record


def _host_script_record(host, scan_source):
    scripts = {}

    for script_node in host.findall(
        "./hostscript/script"
    ):
        script_id = script_node.get(
            "id",
            "",
        )
        output = script_node.get(
            "output",
            "",
        ).strip()

        if script_id and output:
            scripts[script_id] = output

    if not scripts:
        return None

    return {
        "port": 0,
        "protocol": "host",
        "state_reason": "",
        "service": "host-evidence",
        "product": "",
        "version": "",
        "extrainfo": "",
        "hostname": "",
        "ostype": "",
        "devicetype": "",
        "tunnel": "",
        "method": "",
        "confidence": "",
        "cpes": [],
        "scripts": scripts,
        "scan_sources": [scan_source],
    }


def _parse_nmap_service_xml(
    stdout,
    scan_source,
):
    results = {}

    if not stdout.strip():
        return results

    try:
        root = ET.fromstring(stdout)
    except ET.ParseError:
        return results

    for host in root.findall("host"):
        ip = ""

        for address in host.findall("address"):
            if address.get("addrtype") == "ipv4":
                ip = address.get("addr", "")
                break

        if not ip:
            continue

        for port_node in host.findall("./ports/port"):
            state = port_node.find("state")

            if (
                state is None
                or state.get("state") != "open"
            ):
                continue

            results.setdefault(
                ip,
                [],
            ).append(
                _new_service_record(
                    port_node,
                    scan_source,
                )
            )

        host_record = _host_script_record(
            host,
            scan_source,
        )

        if host_record is not None:
            results.setdefault(
                ip,
                [],
            ).append(
                host_record
            )

    return results


def _merge_service_results(
    target,
    incoming,
):
    text_fields = [
        "state_reason",
        "service",
        "product",
        "version",
        "extrainfo",
        "hostname",
        "ostype",
        "devicetype",
        "tunnel",
        "method",
        "confidence",
    ]

    for ip, services in incoming.items():
        target.setdefault(
            ip,
            [],
        )

        for service in services:
            existing = None

            for current in target[ip]:
                if (
                    current.get("port")
                    == service.get("port")
                    and current.get("protocol")
                    == service.get("protocol")
                ):
                    existing = current
                    break

            if existing is None:
                target[ip].append(
                    service
                )
                continue

            for field in text_fields:
                if (
                    not existing.get(field)
                    and service.get(field)
                ):
                    existing[field] = service[
                        field
                    ]

            current_cpes = existing.setdefault(
                "cpes",
                [],
            )

            for cpe in service.get(
                "cpes",
                [],
            ):
                if cpe not in current_cpes:
                    current_cpes.append(cpe)

            existing.setdefault(
                "scripts",
                {},
            ).update(
                service.get(
                    "scripts",
                    {},
                )
            )

            sources = existing.setdefault(
                "scan_sources",
                [],
            )

            for source in service.get(
                "scan_sources",
                [],
            ):
                if source not in sources:
                    sources.append(source)


def _scan_service_pass(
    ip_addresses,
    ports,
    label,
    scan_source,
    host_timeout,
    process_timeout,
):
    results = {}

    if not ip_addresses or not ports:
        return results

    port_text = ",".join(
        str(port)
        for port in ports
    )

    chunk_size = 16
    total_chunks = (
        len(ip_addresses) + chunk_size - 1
    ) // chunk_size

    for chunk_number, position in enumerate(
        range(0, len(ip_addresses), chunk_size),
        1,
    ):
        chunk = ip_addresses[
            position:position + chunk_size
        ]

        print(
            "  {0}: lote {1}/{2} ({3} hosts)...".format(
                label,
                chunk_number,
                total_chunks,
                len(chunk),
            ),
            flush=True,
        )

        command = [
            "nmap",
            "-sT",
            "-sV",
            "--version-intensity",
            "1",
            "-Pn",
            "-n",
            "-T4",
            "--max-retries",
            "1",
            "--initial-rtt-timeout",
            "250ms",
            "--max-rtt-timeout",
            "750ms",
            "--host-timeout",
            host_timeout,
            "--open",
            "-p",
            port_text,
            "-oX",
            "-",
        ] + chunk

        code, stdout, stderr = run_command(
            command,
            timeout=process_timeout,
        )

        if code == 124:
            print(
                "  AVISO: {0} lote {1}/{2} excedeu {3}s.".format(
                    label,
                    chunk_number,
                    total_chunks,
                    process_timeout,
                )
            )

        parsed = _parse_nmap_service_xml(
            stdout,
            scan_source,
        )

        _merge_service_results(
            results,
            parsed,
        )

    return results


def _scan_top_tcp_pass(
    ip_addresses,
    top_ports,
    label,
    scan_source,
    chunk_size=12,
    host_timeout="25s",
    process_timeout=240,
    version_intensity="1",
    extra_args=None,
):
    results = {}
    os_results = {}

    if not ip_addresses:
        return results, os_results

    total_chunks = (
        len(ip_addresses) + chunk_size - 1
    ) // chunk_size

    for chunk_number, position in enumerate(
        range(0, len(ip_addresses), chunk_size),
        1,
    ):
        chunk = ip_addresses[
            position:position + chunk_size
        ]

        print(
            "  {0}: lote {1}/{2} ({3} hosts)...".format(
                label,
                chunk_number,
                total_chunks,
                len(chunk),
            ),
            flush=True,
        )

        command = [
            "nmap",
            "-sT",
            "-sV",
            "--version-intensity",
            version_intensity,
            "-Pn",
            "-n",
            "-T4",
            "--max-retries",
            "1",
            "--host-timeout",
            host_timeout,
            "--open",
            "--top-ports",
            str(top_ports),
        ]

        if extra_args:
            command.extend(extra_args)

        command.extend([
            "-oX",
            "-",
        ] + chunk)

        code, stdout, stderr = run_command(
            command,
            timeout=process_timeout,
        )

        parsed = _parse_nmap_service_xml(
            stdout,
            scan_source,
        )

        _merge_service_results(
            results,
            parsed,
        )

        if stdout.strip():
            try:
                root = ET.fromstring(stdout)
            except ET.ParseError:
                root = None

            if root is not None:
                for host in root.findall("host"):
                    ip = ""

                    for address in host.findall(
                        "address"
                    ):
                        if (
                            address.get("addrtype")
                            == "ipv4"
                        ):
                            ip = address.get(
                                "addr",
                                "",
                            )
                            break

                    if not ip:
                        continue

                    matches = []

                    for osmatch in host.findall(
                        "./os/osmatch"
                    ):
                        item = {
                            "name": osmatch.get(
                                "name",
                                "",
                            ),
                            "accuracy": osmatch.get(
                                "accuracy",
                                "",
                            ),
                            "line": osmatch.get(
                                "line",
                                "",
                            ),
                            "classes": [],
                        }

                        for osclass in osmatch.findall(
                            "osclass"
                        ):
                            item["classes"].append({
                                "type": osclass.get(
                                    "type",
                                    "",
                                ),
                                "vendor": osclass.get(
                                    "vendor",
                                    "",
                                ),
                                "osfamily": osclass.get(
                                    "osfamily",
                                    "",
                                ),
                                "osgen": osclass.get(
                                    "osgen",
                                    "",
                                ),
                                "accuracy": osclass.get(
                                    "accuracy",
                                    "",
                                ),
                                "cpes": [
                                    (cpe.text or "").strip()
                                    for cpe in osclass.findall(
                                        "cpe"
                                    )
                                    if (cpe.text or "").strip()
                                ],
                            })

                        matches.append(item)

                    if matches:
                        os_results[ip] = matches[:10]

    return results, os_results


def _nse_script_available(name):
    paths = [
        "/usr/share/nmap/scripts",
        "/usr/local/share/nmap/scripts",
    ]

    for base in paths:
        if os.path.isfile(
            os.path.join(
                base,
                name + ".nse",
            )
        ):
            return True

    return False


def _available_nse_scripts(names):
    return [
        name
        for name in names
        if _nse_script_available(name)
    ]


def _hosts_with_ports(results, ports, protocol="tcp"):
    values = []

    wanted = set(ports)

    for ip, services in results.items():
        if any(
            service.get("protocol") == protocol
            and service.get("port") in wanted
            for service in services
        ):
            values.append(ip)

    return sorted(
        set(values),
        key=lambda item: ipaddress.ip_address(item),
    )


def _run_targeted_nse(
    results,
    hosts,
    ports,
    scripts,
    label,
    protocol="tcp",
    chunk_size=12,
):
    if not hosts:
        return

    available = _available_nse_scripts(
        scripts
    )

    if not available:
        return

    total_chunks = (
        len(hosts) + chunk_size - 1
    ) // chunk_size

    for chunk_number, position in enumerate(
        range(0, len(hosts), chunk_size),
        1,
    ):
        chunk = hosts[
            position:position + chunk_size
        ]

        print(
            "  {0}: lote {1}/{2} ({3} hosts)...".format(
                label,
                chunk_number,
                total_chunks,
                len(chunk),
            ),
            flush=True,
        )

        command = [
            "nmap",
            "-Pn",
            "-n",
            "-T4",
            "--max-retries",
            "1",
            "--host-timeout",
            "25s",
            "--script",
            ",".join(available),
            "--script-timeout",
            "8s",
            "-p",
            ",".join(
                str(port)
                for port in ports
            ),
            "-oX",
            "-",
        ]

        if protocol == "udp":
            command.insert(
                1,
                "-sU",
            )
        else:
            command.insert(
                1,
                "-sT",
            )

        command.extend(chunk)

        code, stdout, stderr = run_command(
            command,
            timeout=240,
        )

        parsed = _parse_nmap_service_xml(
            stdout,
            "nse-" + label.lower().replace(
                " ",
                "-",
            ),
        )

        _merge_service_results(
            results,
            parsed,
        )


def _service_looks_web(service):
    port = service.get("port")

    if port in WEB_ENRICHMENT_PORTS:
        return True

    value = " ".join([
        service.get("service", ""),
        service.get("product", ""),
        service.get("tunnel", ""),
    ]).lower()

    return (
        "http" in value
        or "https" in value
        or "ssl" in value
    )


def _enrich_web_services(results):
    candidates = {}

    for ip, services in results.items():
        ports = sorted({
            service.get("port")
            for service in services
            if (
                service.get("protocol") == "tcp"
                and service.get("port")
                and _service_looks_web(service)
            )
        })

        if ports:
            candidates[ip] = ports

    if not candidates:
        return

    hosts = sorted(
        candidates.keys(),
        key=lambda item: ipaddress.ip_address(item),
    )

    chunk_size = 8
    total_chunks = (
        len(hosts) + chunk_size - 1
    ) // chunk_size

    scripts = _available_nse_scripts([
        "http-title",
        "http-server-header",
        "ssl-cert",
    ])

    if not scripts:
        return

    print("")
    print(
        "Executando enriquecimento HTTP/TLS em {0} hosts...".format(
            len(hosts)
        )
    )

    for chunk_number, position in enumerate(
        range(0, len(hosts), chunk_size),
        1,
    ):
        chunk = hosts[
            position:position + chunk_size
        ]

        ports = sorted({
            port
            for ip in chunk
            for port in candidates[ip]
        })

        print(
            "  HTTP/TLS: lote {0}/{1} ({2} hosts)...".format(
                chunk_number,
                total_chunks,
                len(chunk),
            ),
            flush=True,
        )

        command = [
            "nmap",
            "-sT",
            "-Pn",
            "-n",
            "-T4",
            "--max-retries",
            "1",
            "--host-timeout",
            "25s",
            "--script",
            ",".join(scripts),
            "--script-timeout",
            "8s",
            "--open",
            "-p",
            ",".join(
                str(port)
                for port in ports
            ),
            "-oX",
            "-",
        ] + chunk

        code, stdout, stderr = run_command(
            command,
            timeout=240,
        )

        parsed = _parse_nmap_service_xml(
            stdout,
            "web-enrichment",
        )

        _merge_service_results(
            results,
            parsed,
        )


def _scan_udp_evidence(
    ip_addresses,
    results,
):
    if not ip_addresses:
        return

    print("")
    print(
        "Executando evidências UDP selecionadas..."
    )

    basic_udp, ignored_os = _scan_udp_basic(
        ip_addresses
    )

    _merge_service_results(
        results,
        basic_udp,
    )

    _run_targeted_nse(
        results,
        ip_addresses,
        [137],
        ["nbstat"],
        "NetBIOS",
        protocol="udp",
        chunk_size=16,
    )

    _run_targeted_nse(
        results,
        ip_addresses,
        [47808],
        ["bacnet-info"],
        "BACnet",
        protocol="udp",
        chunk_size=16,
    )

    _run_targeted_nse(
        results,
        ip_addresses,
        [44818],
        ["enip-info"],
        "EtherNet-IP UDP",
        protocol="udp",
        chunk_size=16,
    )

    _run_targeted_nse(
        results,
        ip_addresses,
        [5353],
        ["dns-service-discovery"],
        "DNS-SD",
        protocol="udp",
        chunk_size=16,
    )

    _run_targeted_nse(
        results,
        ip_addresses,
        [1900],
        ["upnp-info"],
        "UPnP",
        protocol="udp",
        chunk_size=16,
    )


def _scan_udp_basic(ip_addresses):
    results = {}

    if not ip_addresses:
        return results, {}

    chunk_size = 16
    total_chunks = (
        len(ip_addresses) + chunk_size - 1
    ) // chunk_size

    for chunk_number, position in enumerate(
        range(0, len(ip_addresses), chunk_size),
        1,
    ):
        chunk = ip_addresses[
            position:position + chunk_size
        ]

        print(
            "  UDP básico: lote {0}/{1} ({2} hosts)...".format(
                chunk_number,
                total_chunks,
                len(chunk),
            ),
            flush=True,
        )

        command = [
            "nmap",
            "-sU",
            "-sV",
            "--version-intensity",
            "1",
            "-Pn",
            "-n",
            "-T4",
            "--max-retries",
            "0",
            "--host-timeout",
            "18s",
            "--open",
            "-p",
            ",".join(
                str(port)
                for port in UDP_EVIDENCE_PORTS
            ),
            "-oX",
            "-",
        ] + chunk

        code, stdout, stderr = run_command(
            command,
            timeout=240,
        )

        parsed = _parse_nmap_service_xml(
            stdout,
            "udp-evidence",
        )

        _merge_service_results(
            results,
            parsed,
        )

    return results, {}


def scan_services(ip_addresses):
    results = {}

    core_results = _scan_service_pass(
        ip_addresses,
        CORE_DISCOVERY_TCP_PORTS,
        "Serviços básicos",
        "core",
        "15s",
        180,
    )

    _merge_service_results(
        results,
        core_results,
    )

    extended_results = _scan_service_pass(
        ip_addresses,
        EXTENDED_DISCOVERY_TCP_PORTS,
        "Serviços adicionais",
        "extended",
        "20s",
        180,
    )

    _merge_service_results(
        results,
        extended_results,
    )

    broad_results, ignored_os = _scan_top_tcp_pass(
        ip_addresses,
        BROAD_TCP_TOP_PORTS,
        "Top TCP 100",
        "top-tcp-100",
        chunk_size=12,
        host_timeout="25s",
        process_timeout=240,
        version_intensity="1",
    )

    _merge_service_results(
        results,
        broad_results,
    )

    _enrich_web_services(
        results
    )

    _run_targeted_nse(
        results,
        _hosts_with_ports(
            results,
            [22],
        ),
        [22],
        ["ssh-hostkey"],
        "SSH host key",
    )

    _run_targeted_nse(
        results,
        _hosts_with_ports(
            results,
            [139, 445],
        ),
        [139, 445],
        ["smb-os-discovery"],
        "SMB OS",
    )

    _run_targeted_nse(
        results,
        _hosts_with_ports(
            results,
            [3389],
        ),
        [3389],
        ["rdp-ntlm-info"],
        "RDP NTLM",
    )

    _run_targeted_nse(
        results,
        _hosts_with_ports(
            results,
            [102],
        ),
        [102],
        ["s7-info"],
        "Siemens S7",
    )

    _run_targeted_nse(
        results,
        _hosts_with_ports(
            results,
            [44818],
        ),
        [44818],
        ["enip-info"],
        "EtherNet-IP TCP",
    )

    _scan_udp_evidence(
        ip_addresses,
        results,
    )

    return results


def deep_scan_residual(ip_addresses):
    if not ip_addresses:
        return {}, {}

    print("")
    print(
        "===== DEEP SCAN RESIDUAL ====="
    )
    print(
        "Aprofundando {0} hosts com pouca evidência.".format(
            len(ip_addresses)
        )
    )

    extra_args = [
        "-O",
        "--osscan-limit",
        "--osscan-guess",
        "--max-os-tries",
        "1",
    ]

    banner_scripts = _available_nse_scripts([
        "banner",
    ])

    if banner_scripts:
        extra_args.extend([
            "--script",
            ",".join(
                banner_scripts
            ),
            "--script-timeout",
            "5s",
        ])

    return _scan_top_tcp_pass(
        ip_addresses,
        RESIDUAL_TCP_TOP_PORTS,
        "Deep TCP 1000",
        "deep-tcp-1000",
        chunk_size=6,
        host_timeout="60s",
        process_timeout=420,
        version_intensity="3",
        extra_args=extra_args,
    )



def clean_snmp_value(value):
    value = (value or "").strip()

    if (
        len(value) >= 2
        and value.startswith('"')
        and value.endswith('"')
    ):
        value = value[1:-1]

    return value.strip()


def valid_snmp_value(value):
    value = clean_snmp_value(value)

    if not value:
        return False

    lowered = value.lower()

    return not any(
        marker in lowered
        for marker in INVALID_SNMP_MARKERS
    )


def normalize_mac(value):
    value = clean_snmp_value(value)

    if not value:
        return ""

    pairs = re.findall(
        r"(?i)(?<![0-9a-f])[0-9a-f]{2}(?![0-9a-f])",
        value,
    )

    if len(pairs) not in (6, 8):
        compact = re.sub(
            r"[^0-9A-Fa-f]",
            "",
            value,
        )

        if len(compact) in (12, 16):
            pairs = [
                compact[position:position + 2]
                for position in range(0, len(compact), 2)
            ]

    if len(pairs) not in (6, 8):
        return ""

    normalized = ":".join(
        pair.upper()
        for pair in pairs
    )

    if set(normalized.replace(":", "")) == set("0"):
        return ""

    return normalized


_OUI_VENDOR_CACHE = None


def _load_oui_vendor_cache():
    global _OUI_VENDOR_CACHE

    if _OUI_VENDOR_CACHE is not None:
        return _OUI_VENDOR_CACHE

    cache = {}

    paths = [
        "/usr/share/nmap/nmap-mac-prefixes",
        "/usr/local/share/nmap/nmap-mac-prefixes",
    ]

    for path in paths:
        if not os.path.isfile(path):
            continue

        try:
            with open(path, "r") as handle:
                for raw in handle:
                    line = raw.strip()

                    if (
                        not line
                        or line.startswith("#")
                    ):
                        continue

                    parts = line.split(
                        None,
                        1,
                    )

                    if len(parts) != 2:
                        continue

                    prefix = re.sub(
                        r"[^0-9A-Fa-f]",
                        "",
                        parts[0],
                    ).upper()

                    if len(prefix) == 6:
                        cache[prefix] = parts[1].strip()
        except Exception:
            pass

        if cache:
            break

    _OUI_VENDOR_CACHE = cache

    return cache


def mac_vendor_lookup(mac):
    normalized = normalize_mac(mac)

    if not normalized:
        return ""

    prefix = normalized.replace(
        ":",
        "",
    )[:6]

    return _load_oui_vendor_cache().get(
        prefix,
        "",
    )


def snmp_enterprise_id(sysobjectid):
    value = clean_snmp_value(
        sysobjectid
    )

    match = re.search(
        r"(?:^|\.)1\.3\.6\.1\.4\.1\.([0-9]+)(?:\.|$)",
        value,
    )

    if not match:
        return ""

    return match.group(1)


def parse_snmp_walk_line(line):
    match = re.match(
        r"^\s*\.?([0-9.]+)\s*=\s*([^:]+):\s*(.*)$",
        line,
    )

    if not match:
        return "", "", ""

    oid = "." + match.group(1).strip(".")
    value_type = match.group(2).strip()
    value = clean_snmp_value(
        match.group(3)
    )

    if not valid_snmp_value(value):
        value = ""

    return oid, value_type, value


def snmp_command_context(snmp):
    return (
        snmp.get("_version_option", ""),
        snmp.get("_community", ""),
    )


def _snmp_get_one(
    ip,
    version_option,
    community,
    oid,
    timeout=5,
):
    command = [
        "snmpget",
        version_option,
        "-c",
        community,
        "-t",
        "1",
        "-r",
        "0",
        "-Oqv",
        ip,
        oid,
    ]

    code, stdout, stderr = run_command(
        command,
        timeout=timeout,
    )

    if not stdout.strip():
        return ""

    value = clean_snmp_value(
        stdout.splitlines()[0]
    )

    if not valid_snmp_value(value):
        return ""

    return value


def _snmp_system_walk(
    ip,
    version_option,
    community,
):
    values = {}

    command = [
        "snmpwalk",
        version_option,
        "-c",
        community,
        "-t",
        "1",
        "-r",
        "0",
        "-On",
        ip,
        ".1.3.6.1.2.1.1",
    ]

    code, stdout, stderr = run_command(
        command,
        timeout=10,
    )

    if not stdout.strip():
        return values

    wanted = {
        SYSNAME_OID: "sysname",
        SYSDESCR_OID: "sysdescr",
        SYSOBJECTID_OID: "sysobjectid",
        SYSUPTIME_OID: "sysuptime",
        SYSCONTACT_OID: "syscontact",
        SYSLOCATION_OID: "syslocation",
        SYSSERVICES_OID: "sysservices",
    }

    for line in stdout.splitlines():
        oid, value_type, value = parse_snmp_walk_line(
            line
        )

        field = wanted.get(oid)

        if field and value:
            values[field] = value

    return values


def probe_snmp(ip, communities):
    versions = [
        ("2c", "-v2c"),
        ("1", "-v1"),
    ]

    base_oids = [
        SYSNAME_OID,
        SYSDESCR_OID,
        SYSOBJECTID_OID,
    ]

    for version_name, version_option in versions:
        for community in communities:
            command = [
                "snmpget",
                version_option,
                "-c",
                community,
                "-t",
                "1",
                "-r",
                "0",
                "-Oqv",
                ip,
            ] + base_oids

            code, stdout, stderr = run_command(
                command,
                timeout=6,
            )

            raw_values = [
                clean_snmp_value(line)
                for line in stdout.splitlines()
                if line.strip()
            ]

            values = []

            if len(raw_values) == len(base_oids):
                values = [
                    value if valid_snmp_value(value) else ""
                    for value in raw_values
                ]
            else:
                # Fallback individual evita que um único OID problemático
                # invalide todo o SNMP básico.
                values = [
                    _snmp_get_one(
                        ip,
                        version_option,
                        community,
                        oid,
                    )
                    for oid in base_oids
                ]

            if not any(values):
                continue

            snmp = {
                "available": True,
                "version": version_name,
                "sysname": values[0],
                "sysdescr": values[1],
                "sysobjectid": values[2],
                "sysuptime": "",
                "syscontact": "",
                "syslocation": "",
                "sysservices": "",
                "_version_option": version_option,
                "_community": community,
            }

            # O walk opcional enriquece; jamais pode tornar available=False.
            enrichment = _snmp_system_walk(
                ip,
                version_option,
                community,
            )

            for field, value in enrichment.items():
                if value:
                    snmp[field] = value

            return snmp

    return {
        "available": False,
        "version": "",
        "sysname": "",
        "sysdescr": "",
        "sysobjectid": "",
        "sysuptime": "",
        "syscontact": "",
        "syslocation": "",
        "sysservices": "",
        "_version_option": "",
        "_community": "",
    }


def _snmp_lldp_walk(
    ip,
    version_option,
    community,
):
    result = {
        "lldp_chassis_id": "",
        "lldp_sys_name": "",
        "lldp_sys_descr": "",
    }

    command = [
        "snmpwalk",
        version_option,
        "-c",
        community,
        "-t",
        "1",
        "-r",
        "0",
        "-On",
        ip,
        ".1.0.8802.1.1.2.1.3",
    ]

    code, stdout, stderr = run_command(
        command,
        timeout=8,
    )

    if not stdout.strip():
        return result

    wanted = {
        LLDP_LOC_CHASSIS_ID_OID: "lldp_chassis_id",
        LLDP_LOC_SYS_NAME_OID: "lldp_sys_name",
        LLDP_LOC_SYS_DESC_OID: "lldp_sys_descr",
    }

    for line in stdout.splitlines():
        oid, value_type, value = parse_snmp_walk_line(
            line
        )

        field = wanted.get(oid)

        if field and value:
            result[field] = value

    return result


def probe_snmp_optional_identity(ip, snmp):
    if not snmp.get("available"):
        return {
            "bridge_mac": "",
            "lldp_chassis_id": "",
            "lldp_sys_name": "",
            "lldp_sys_descr": "",
        }

    version_option, community = snmp_command_context(
        snmp
    )

    # Bridge e LLDP são independentes. Falha de um não afeta o outro.
    bridge_value = _snmp_get_one(
        ip,
        version_option,
        community,
        DOT1D_BASE_BRIDGE_ADDRESS_OID,
        timeout=5,
    )

    lldp = _snmp_lldp_walk(
        ip,
        version_option,
        community,
    )

    return {
        "bridge_mac": normalize_mac(
            bridge_value
        ),
        "lldp_chassis_id": lldp.get(
            "lldp_chassis_id",
            "",
        ),
        "lldp_sys_name": lldp.get(
            "lldp_sys_name",
            "",
        ),
        "lldp_sys_descr": lldp.get(
            "lldp_sys_descr",
            "",
        ),
    }


def _snmp_walk(
    ip,
    version_option,
    community,
    oid,
    timeout=15,
):
    command = [
        "snmpwalk",
        version_option,
        "-c",
        community,
        "-t",
        "1",
        "-r",
        "0",
        "-On",
        ip,
        oid,
    ]

    code, stdout, stderr = run_command(
        command,
        timeout=timeout,
    )

    if not stdout.strip():
        return []

    values = []

    for line in stdout.splitlines():
        item_oid, value_type, value = parse_snmp_walk_line(
            line
        )

        if not item_oid:
            continue

        values.append((
            item_oid,
            value_type,
            value,
        ))

    return values


def probe_snmp_interfaces(ip, snmp):
    if not snmp.get("available"):
        return []

    version_option, community = snmp_command_context(
        snmp
    )

    fields = [
        (
            IF_DESCR_OID,
            "description",
        ),
        (
            IF_TYPE_OID,
            "type",
        ),
        (
            IF_PHYS_ADDRESS_OID,
            "mac",
        ),
        (
            IF_OPER_STATUS_OID,
            "oper_status",
        ),
        (
            IF_NAME_OID,
            "name",
        ),
        (
            IF_ALIAS_OID,
            "alias",
        ),
    ]

    interfaces = {}

    for base_oid, field in fields:
        for oid, value_type, value in _snmp_walk(
            ip,
            version_option,
            community,
            base_oid,
            timeout=15,
        ):
            prefix = base_oid + "."

            if not oid.startswith(prefix):
                continue

            index = oid[len(prefix):]

            interface = interfaces.setdefault(
                index,
                {
                    "index": index,
                    "name": "",
                    "description": "",
                    "alias": "",
                    "type": "",
                    "oper_status": "",
                    "mac": "",
                    "mac_vendor": "",
                },
            )

            if field == "mac":
                value = normalize_mac(
                    value
                )

                if value:
                    interface["mac_vendor"] = mac_vendor_lookup(
                        value
                    )

            interface[field] = value

    result = list(
        interfaces.values()
    )

    result.sort(
        key=lambda item: (
            int(item["index"])
            if item["index"].isdigit()
            else 999999,
            item["index"],
        )
    )

    return result[:256]


def probe_snmp_interface_macs(ip, snmp):
    interfaces = probe_snmp_interfaces(
        ip,
        snmp,
    )

    return [
        {
            "index": item.get(
                "index",
                "",
            ),
            "mac": item.get(
                "mac",
                "",
            ),
            "vendor": item.get(
                "mac_vendor",
                "",
            ),
        }
        for item in interfaces
        if item.get("mac")
    ]


def probe_snmp_ip_addresses(ip, snmp):
    if not snmp.get("available"):
        return []

    version_option, community = snmp_command_context(
        snmp
    )

    rows = {}

    columns = [
        (
            IP_AD_ENT_ADDR_OID,
            "address",
        ),
        (
            IP_AD_ENT_IFINDEX_OID,
            "ifindex",
        ),
        (
            IP_AD_ENT_NETMASK_OID,
            "netmask",
        ),
    ]

    for base_oid, field in columns:
        for oid, value_type, value in _snmp_walk(
            ip,
            version_option,
            community,
            base_oid,
            timeout=12,
        ):
            prefix = base_oid + "."

            if not oid.startswith(prefix):
                continue

            suffix = oid[len(prefix):]
            address = suffix

            row = rows.setdefault(
                address,
                {
                    "address": address,
                    "ifindex": "",
                    "netmask": "",
                },
            )

            if field == "address":
                if value:
                    row[field] = value
            else:
                row[field] = value

    result = []

    for row in rows.values():
        try:
            ipaddress.ip_address(
                row.get("address", "")
            )
        except ValueError:
            continue

        result.append(row)

    result.sort(
        key=lambda item: ipaddress.ip_address(
            item["address"]
        )
    )

    return result[:256]



def probe_snmp_entity(ip, snmp):
    if not snmp.get("available"):
        return {
            "primary": {},
            "inventory": [],
            "count": 0,
        }

    version_option, community = snmp_command_context(
        snmp
    )

    command = [
        "snmpwalk",
        version_option,
        "-c",
        community,
        "-t",
        "1",
        "-r",
        "0",
        "-On",
        ip,
        ENTITY_PHYSICAL_TABLE_OID,
    ]

    code, stdout, stderr = run_command(
        command,
        timeout=15,
    )

    if not stdout.strip():
        return {
            "primary": {},
            "inventory": [],
            "count": 0,
        }

    fields = {
        "2": "description",
        "4": "contained_in",
        "5": "class",
        "6": "parent_rel_pos",
        "7": "name",
        "8": "hardware_rev",
        "9": "firmware_rev",
        "10": "software_rev",
        "11": "serial",
        "12": "manufacturer",
        "13": "model",
        "14": "alias",
        "15": "asset_id",
        "16": "is_fru",
    }

    entries = {}
    prefix = ENTITY_PHYSICAL_TABLE_OID + "."

    for line in stdout.splitlines():
        oid, value_type, value = parse_snmp_walk_line(
            line
        )

        if not oid.startswith(prefix):
            continue

        suffix = oid[len(prefix):].split(".")

        if len(suffix) < 2:
            continue

        column = suffix[0]
        index = ".".join(suffix[1:])
        field = fields.get(column)

        if not field:
            continue

        entry = entries.setdefault(
            index,
            {
                "index": index,
                "description": "",
                "contained_in": "",
                "class": "",
                "class_id": "",
                "parent_rel_pos": "",
                "name": "",
                "hardware_rev": "",
                "firmware_rev": "",
                "software_rev": "",
                "serial": "",
                "manufacturer": "",
                "model": "",
                "alias": "",
                "asset_id": "",
                "is_fru": "",
            },
        )

        entry[field] = value

        if field == "class":
            class_match = re.search(
                r"\(([0-9]+)\)",
                value,
            )

            if class_match:
                entry["class_id"] = class_match.group(1)
            elif value.isdigit():
                entry["class_id"] = value

    inventory = [
        entry
        for entry in entries.values()
        if any(
            entry.get(field)
            for field in (
                "description",
                "class",
                "name",
                "serial",
                "manufacturer",
                "model",
            )
        )
    ]

    inventory.sort(
        key=lambda item: (
            int(item["index"])
            if item["index"].isdigit()
            else 999999,
            item["index"],
        )
    )

    def primary_score(entry):
        class_id = entry.get(
            "class_id",
            "",
        )

        class_score = {
            "3": 1000,
            "11": 900,
            "9": 800,
            "12": 700,
        }.get(class_id, 0)

        evidence_score = sum(
            50
            for field in (
                "serial",
                "manufacturer",
                "model",
            )
            if entry.get(field)
        )

        evidence_score += sum(
            10
            for field in (
                "name",
                "description",
            )
            if entry.get(field)
        )

        return class_score + evidence_score

    primary = {}

    if inventory:
        primary = max(
            inventory,
            key=primary_score,
        )

    return {
        "primary": primary,
        "inventory": inventory[:128],
        "count": len(inventory),
    }


def service_script_summary(services):
    values = []

    for service in services:
        port = service.get("port", "")

        for script_id, output in sorted(
            service.get("scripts", {}).items()
        ):
            clean_output = " ".join(
                (output or "").split()
            )

            values.append(
                "{0}/{1}={2}".format(
                    port,
                    script_id,
                    clean_output,
                )
            )

    return " | ".join(values)


def service_detail_summary(services):
    values = []

    for service in services:
        parts = [
            str(service.get("port", "")),
            service.get("service", ""),
            service.get("product", ""),
            service.get("version", ""),
            service.get("extrainfo", ""),
            service.get("ostype", ""),
            service.get("devicetype", ""),
        ]

        parts = [
            str(value).strip()
            for value in parts
            if str(value).strip()
        ]

        if parts:
            values.append(
                "/".join(parts)
            )

    return " | ".join(values)


def _service_script_text(services):
    values = []

    for service in services:
        values.extend(
            service.get(
                "scripts",
                {},
            ).values()
        )

    return " ".join(
        str(value)
        for value in values
        if value
    )


def _identification_text(
    dns_name,
    snmp,
    snmp_identity,
    snmp_entity,
    services,
    os_matches,
):
    primary = snmp_entity.get(
        "primary",
        {},
    )

    parts = [
        dns_name,
        snmp.get("sysname", ""),
        snmp.get("sysdescr", ""),
        snmp.get("sysobjectid", ""),
        snmp_identity.get(
            "lldp_sys_name",
            "",
        ),
        snmp_identity.get(
            "lldp_sys_descr",
            "",
        ),
        primary.get(
            "manufacturer",
            "",
        ),
        primary.get(
            "model",
            "",
        ),
        primary.get(
            "serial",
            "",
        ),
        _service_script_text(
            services
        ),
        " ".join(
            "{0} {1} {2} {3} {4} {5}".format(
                item.get("service", ""),
                item.get("product", ""),
                item.get("version", ""),
                item.get("extrainfo", ""),
                item.get("ostype", ""),
                item.get("devicetype", ""),
            )
            for item in services
        ),
        " ".join(
            item.get("name", "")
            for item in os_matches
        ),
    ]

    return " ".join(
        str(part)
        for part in parts
        if part
    )


def _evidence_sources(
    base,
    dns_name,
    snmp,
    snmp_identity,
    snmp_interfaces,
    snmp_ip_addresses,
    snmp_entity,
    services,
    os_matches,
):
    values = []

    if dns_name:
        values.append("dns")

    if base.get("mac", ""):
        values.append("l2-mac")

    if services:
        if any(
            service.get("protocol") == "tcp"
            and service.get("port", 0) > 0
            for service in services
        ):
            values.append("nmap-tcp-services")

        if any(
            service.get("protocol") == "udp"
            and service.get("port", 0) > 0
            for service in services
        ):
            values.append("nmap-udp-services")

    if any(
        item.get("scripts")
        for item in services
    ):
        values.append("nmap-safe-scripts")

    if os_matches:
        values.append("nmap-os-fingerprint")

    if snmp.get("available", False):
        values.append("snmp-system")

    if snmp_entity.get("inventory"):
        values.append("snmp-entity")

    if any(
        item.get("mac")
        for item in snmp_interfaces
    ):
        values.append("snmp-interface-macs")

    if snmp_interfaces:
        values.append("snmp-interface-inventory")

    if snmp_ip_addresses:
        values.append("snmp-ip-addresses")

    if (
        snmp_identity.get("bridge_mac")
        or snmp_identity.get("lldp_chassis_id")
        or snmp_identity.get("lldp_sys_name")
    ):
        values.append("snmp-l2-identity")

    return values


def _evidence_level(source_count):
    if source_count <= 0:
        return "NONE"

    if source_count == 1:
        return "LOW"

    if source_count == 2:
        return "MEDIUM"

    return "HIGH"


def suggested_manufacturer(text, mac_vendor):
    value = "{0} {1}".format(
        text,
        mac_vendor,
    ).lower()

    rules = [
        ("fortinet", "Fortinet"),
        ("fortigate", "Fortinet"),
        ("aruba", "HPE Aruba"),
        ("hewlett packard", "HPE"),
        ("procurve", "HPE"),
        ("cisco", "Cisco"),
        ("mikrotik", "MikroTik"),
        ("ubiquiti", "Ubiquiti"),
        ("vmware", "VMware"),
        ("microsoft", "Microsoft"),
        ("linux", "Linux"),
        ("dell", "Dell"),
        ("lenovo", "Lenovo"),
        ("epson", "Epson"),
        ("hewlett-packard", "HP"),
    ]

    for pattern, manufacturer in rules:
        if pattern in value:
            return manufacturer

    return mac_vendor or ""


def suggested_role(text, services):
    industrial_plc_terms = (
        "simatic s7",
        "s7 cpu",
        "6es7",
        "cpu 412",
        "cpu412",
    )

    if any(term in text.lower() for term in industrial_plc_terms):
        return "INDUSTRIAL-PLC"

    value = text.lower()
    ports = set(
        service["port"]
        for service in services
    )

    if "fortigate" in value or "fortios" in value:
        return "FIREWALL"

    if 9100 in ports or 515 in ports:
        return "PRINTER"

    if 8006 in ports or "proxmox" in value:
        return "HYPERVISOR"

    if (
        "aruba" in value
        or "procurve" in value
        or "cisco ios" in value
        or "mikrotik" in value
        or "switch" in value
    ):
        return "NETWORK"

    if ports.intersection(
        set([135, 139, 445, 3389, 5985, 5986])
    ):
        return "SERVER-WINDOWS"

    if 22 in ports:
        return "SERVER-LINUX-OR-APPLIANCE"

    if 80 in ports or 443 in ports or 8080 in ports or 8443 in ports:
        return "WEB-APPLIANCE"

    return "UNKNOWN"


def main():
    env = load_discovery_settings()
    networks = read_lines(
        env["NETWORKS_FILE"]
    )
    communities = read_lines(
        env["COMMUNITIES_FILE"]
    )
    exclusions = parse_exclusions(
        read_lines(
            env["EXCLUSIONS_FILE"]
        )
    )
    output_dir = env["OUTPUT_DIR"]

    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)

    valid_networks = []

    for network in networks:
        try:
            valid_networks.append(
                str(
                    ipaddress.ip_network(
                        network,
                        strict=False,
                    )
                )
            )
        except ValueError:
            print(
                "Rede inválida ignorada: {0}".format(
                    network
                )
            )

    proxy_name = socket.gethostname()
    api_status = api_check(env)

    print("Proxy: {0}".format(proxy_name))
    print(
        "Cliente: {0}".format(
            env.get("CLIENT", "")
        )
    )
    print(
        "Site: {0}".format(
            env.get("SITE", "")
        )
    )
    print(
        "Redes: {0}".format(
            ", ".join(valid_networks)
        )
    )
    print(
        "NetBox API: HTTP {0}".format(
            api_status
        )
    )
    print("")
    print(
        "===== EVIDENCE V4 FINAL ====="
    )
    print(
        "Executando descoberta multi-método de hosts..."
    )

    discovered = discover_hosts(
        valid_networks,
        communities,
        exclusions,
    )

    filtered = {}

    for ip, data in discovered.items():
        if not is_excluded(
            ip,
            exclusions,
        ):
            filtered[ip] = data

    active_ips = sorted(
        filtered.keys(),
        key=lambda item: ipaddress.ip_address(
            item
        ),
    )

    print(
        "Hosts ativos encontrados: {0}".format(
            len(active_ips)
        )
    )
    print("")
    print(
        "Executando identificação de serviços e protocolos..."
    )

    service_results = scan_services(
        active_ips
    )

    now = datetime.datetime.utcnow().replace(
        microsecond=0
    ).isoformat() + "Z"

    host_evidence = {}

    print("")
    print(
        "Executando enriquecimento SNMP por host..."
    )

    total_hosts = len(active_ips)

    for position, ip in enumerate(
        active_ips,
        1,
    ):
        if (
            position == 1
            or position % 20 == 0
            or position == total_hosts
        ):
            print(
                "  SNMP/evidências: {0}/{1}".format(
                    position,
                    total_hosts,
                ),
                flush=True,
            )

        base = filtered[ip]
        dns_name = reverse_dns(ip)
        snmp = probe_snmp(
            ip,
            communities,
        )

        snmp_identity = probe_snmp_optional_identity(
            ip,
            snmp,
        )

        snmp_interfaces = probe_snmp_interfaces(
            ip,
            snmp,
        )

        snmp_ip_addresses = probe_snmp_ip_addresses(
            ip,
            snmp,
        )

        snmp_entity = probe_snmp_entity(
            ip,
            snmp,
        )

        host_evidence[ip] = {
            "base": base,
            "dns_name": dns_name,
            "snmp": snmp,
            "snmp_identity": snmp_identity,
            "snmp_interfaces": snmp_interfaces,
            "snmp_ip_addresses": snmp_ip_addresses,
            "snmp_entity": snmp_entity,
        }

    # Identifica hosts realmente pobres de evidência.
    residual_ips = []

    for ip in active_ips:
        evidence = host_evidence[ip]
        services = service_results.get(
            ip,
            [],
        )

        sources = _evidence_sources(
            evidence["base"],
            evidence["dns_name"],
            evidence["snmp"],
            evidence["snmp_identity"],
            evidence["snmp_interfaces"],
            evidence["snmp_ip_addresses"],
            evidence["snmp_entity"],
            services,
            [],
        )

        strong_identity = bool(
            evidence["base"].get("mac")
            or evidence["snmp"].get(
                "available"
            )
            or evidence["dns_name"]
            or evidence["snmp_entity"].get(
                "inventory"
            )
        )

        if (
            len(sources) <= 1
            and not strong_identity
        ):
            residual_ips.append(ip)

    deep_os_results = {}

    if residual_ips:
        deep_services, deep_os_results = deep_scan_residual(
            residual_ips
        )

        _merge_service_results(
            service_results,
            deep_services,
        )

    records = []

    for ip in active_ips:
        evidence = host_evidence[ip]
        base = evidence["base"]
        dns_name = evidence["dns_name"]
        snmp = evidence["snmp"]
        snmp_identity = evidence[
            "snmp_identity"
        ]
        snmp_interfaces = evidence[
            "snmp_interfaces"
        ]
        snmp_ip_addresses = evidence[
            "snmp_ip_addresses"
        ]
        snmp_entity = evidence[
            "snmp_entity"
        ]
        services = service_results.get(
            ip,
            [],
        )
        os_matches = deep_os_results.get(
            ip,
            [],
        )

        identification_text = _identification_text(
            dns_name,
            snmp,
            snmp_identity,
            snmp_entity,
            services,
            os_matches,
        )

        evidence_sources = _evidence_sources(
            base,
            dns_name,
            snmp,
            snmp_identity,
            snmp_interfaces,
            snmp_ip_addresses,
            snmp_entity,
            services,
            os_matches,
        )

        snmp_interface_macs = [
            {
                "index": item.get(
                    "index",
                    "",
                ),
                "mac": item.get(
                    "mac",
                    "",
                ),
                "vendor": item.get(
                    "mac_vendor",
                    "",
                ),
            }
            for item in snmp_interfaces
            if item.get("mac")
        ]

        record = {
            "evidence_version": "4.0-final",
            "classification_version": "legacy-v1-unchanged",
            "source_proxy": proxy_name,
            "client": env.get(
                "CLIENT",
                "",
            ),
            "site": env.get(
                "SITE",
                "",
            ),
            "ip": ip,
            "reverse_dns": dns_name,
            "mac": base.get(
                "mac",
                "",
            ),
            "mac_vendor": base.get(
                "mac_vendor",
                "",
            ),
            "discovery_reason": base.get(
                "reason",
                "",
            ),
            "discovery_reason_ttl": base.get(
                "reason_ttl",
                "",
            ),
            "discovery_sources": base.get(
                "discovery_sources",
                [],
            ),
            "snmp_available": snmp.get(
                "available",
                False,
            ),
            "snmp_version": snmp.get(
                "version",
                "",
            ),
            "snmp_name": snmp.get(
                "sysname",
                "",
            ),
            "snmp_description": snmp.get(
                "sysdescr",
                "",
            ),
            "snmp_object_id": snmp.get(
                "sysobjectid",
                "",
            ),
            "snmp_enterprise_id": snmp_enterprise_id(
                snmp.get(
                    "sysobjectid",
                    "",
                )
            ),
            "snmp_uptime": snmp.get(
                "sysuptime",
                "",
            ),
            "snmp_contact": snmp.get(
                "syscontact",
                "",
            ),
            "snmp_location": snmp.get(
                "syslocation",
                "",
            ),
            "snmp_services": snmp.get(
                "sysservices",
                "",
            ),
            "snmp_bridge_mac": snmp_identity.get(
                "bridge_mac",
                "",
            ),
            "snmp_lldp_chassis_id": snmp_identity.get(
                "lldp_chassis_id",
                "",
            ),
            "snmp_lldp_name": snmp_identity.get(
                "lldp_sys_name",
                "",
            ),
            "snmp_lldp_description": snmp_identity.get(
                "lldp_sys_descr",
                "",
            ),
            "snmp_interfaces": snmp_interfaces,
            "snmp_interface_macs": snmp_interface_macs,
            "snmp_ip_addresses": snmp_ip_addresses,
            "snmp_entity_primary": snmp_entity.get(
                "primary",
                {},
            ),
            "snmp_entity_inventory": snmp_entity.get(
                "inventory",
                [],
            ),
            "snmp_entity_count": snmp_entity.get(
                "count",
                0,
            ),
            "nmap_os_matches": os_matches,
            "deep_scan_used": (
                ip in residual_ips
            ),
            "suggested_manufacturer": suggested_manufacturer(
                identification_text,
                base.get(
                    "mac_vendor",
                    "",
                ),
            ),
            "suggested_role": suggested_role(
                identification_text,
                services,
            ),
            "open_services": services,
            "evidence_sources": evidence_sources,
            "evidence_source_count": len(
                evidence_sources
            ),
            "evidence_level": _evidence_level(
                len(evidence_sources)
            ),
            "discovered_at": now,
            "netbox_write": False,
        }

        records.append(record)

    timestamp = datetime.datetime.now().strftime(
        "%Y%m%d-%H%M%S"
    )

    site_slug = re.sub(
        r"[^A-Za-z0-9_-]+",
        "-",
        env["SITE"],
    ).strip("-") or "SITE"

    json_file = os.path.join(
        output_dir,
        "{0}-discovery-{1}.json".format(
            site_slug,
            timestamp,
        ),
    )

    csv_file = os.path.join(
        output_dir,
        "{0}-discovery-{1}.csv".format(
            site_slug,
            timestamp,
        ),
    )

    evidence_summary = {
        "total_active": len(records),
        "with_dns": sum(
            1
            for row in records
            if row.get("reverse_dns")
        ),
        "with_l2_mac": sum(
            1
            for row in records
            if row.get("mac")
        ),
        "with_services": sum(
            1
            for row in records
            if row.get("open_services")
        ),
        "with_tcp_services": sum(
            1
            for row in records
            if any(
                item.get("protocol") == "tcp"
                and item.get("port", 0) > 0
                for item in row.get(
                    "open_services",
                    [],
                )
            )
        ),
        "with_udp_services": sum(
            1
            for row in records
            if any(
                item.get("protocol") == "udp"
                and item.get("port", 0) > 0
                for item in row.get(
                    "open_services",
                    [],
                )
            )
        ),
        "with_safe_script_evidence": sum(
            1
            for row in records
            if any(
                service.get("scripts")
                for service in row.get(
                    "open_services",
                    [],
                )
            )
        ),
        "with_snmp_system": sum(
            1
            for row in records
            if row.get("snmp_available")
        ),
        "with_snmp_entity": sum(
            1
            for row in records
            if row.get(
                "snmp_entity_inventory"
            )
        ),
        "with_snmp_interfaces": sum(
            1
            for row in records
            if row.get("snmp_interfaces")
        ),
        "with_snmp_interface_macs": sum(
            1
            for row in records
            if row.get(
                "snmp_interface_macs"
            )
        ),
        "with_snmp_ip_addresses": sum(
            1
            for row in records
            if row.get(
                "snmp_ip_addresses"
            )
        ),
        "with_snmp_l2_identity": sum(
            1
            for row in records
            if (
                row.get("snmp_bridge_mac")
                or row.get(
                    "snmp_lldp_chassis_id"
                )
                or row.get(
                    "snmp_lldp_name"
                )
            )
        ),
        "with_os_fingerprint": sum(
            1
            for row in records
            if row.get(
                "nmap_os_matches"
            )
        ),
        "deep_scan_hosts": len(
            residual_ips
        ),
        "evidence_none": sum(
            1
            for row in records
            if row.get("evidence_level")
            == "NONE"
        ),
        "evidence_low": sum(
            1
            for row in records
            if row.get("evidence_level")
            == "LOW"
        ),
        "evidence_medium": sum(
            1
            for row in records
            if row.get("evidence_level")
            == "MEDIUM"
        ),
        "evidence_high": sum(
            1
            for row in records
            if row.get("evidence_level")
            == "HIGH"
        ),
    }

    report = {
        "mode": "DRY-RUN",
        "evidence_version": "4.0-final",
        "classification_version": "legacy-v1-unchanged",
        "netbox_api_http": api_status,
        "source_proxy": proxy_name,
        "client": env.get(
            "CLIENT",
            "",
        ),
        "site": env.get(
            "SITE",
            "",
        ),
        "networks": valid_networks,
        "total_active": len(records),
        "evidence_summary": evidence_summary,
        "devices": records,
    }

    with open(
        json_file,
        "w",
    ) as handle:
        json.dump(
            report,
            handle,
            indent=2,
            sort_keys=False,
        )

    csv_fields = [
        "evidence_version",
        "source_proxy",
        "client",
        "site",
        "ip",
        "reverse_dns",
        "mac",
        "mac_vendor",
        "discovery_reason",
        "discovery_reason_ttl",
        "discovery_sources",
        "snmp_available",
        "snmp_version",
        "snmp_name",
        "snmp_description",
        "snmp_object_id",
        "snmp_enterprise_id",
        "snmp_uptime",
        "snmp_contact",
        "snmp_location",
        "snmp_services",
        "snmp_bridge_mac",
        "snmp_lldp_chassis_id",
        "snmp_lldp_name",
        "snmp_entity_manufacturer",
        "snmp_entity_model",
        "snmp_entity_serial",
        "snmp_entity_asset_id",
        "snmp_entity_name",
        "snmp_interface_count",
        "snmp_interface_macs",
        "snmp_ip_addresses",
        "nmap_os_best",
        "deep_scan_used",
        "suggested_manufacturer",
        "suggested_role",
        "open_ports",
        "service_details",
        "service_scripts",
        "evidence_sources",
        "evidence_source_count",
        "evidence_level",
        "discovered_at",
    ]

    with open(
        csv_file,
        "w",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=csv_fields,
        )

        writer.writeheader()

        for record in records:
            row = dict(record)

            row["discovery_sources"] = ",".join(
                record.get(
                    "discovery_sources",
                    [],
                )
            )

            row["open_ports"] = ",".join(
                "{0}/{1}/{2}".format(
                    item.get(
                        "port",
                        "",
                    ),
                    item.get(
                        "protocol",
                        "",
                    ),
                    item.get(
                        "service",
                        "",
                    ),
                )
                for item in record[
                    "open_services"
                ]
                if item.get("port", 0) > 0
            )

            row["service_details"] = service_detail_summary(
                record.get(
                    "open_services",
                    [],
                )
            )

            row["service_scripts"] = service_script_summary(
                record.get(
                    "open_services",
                    [],
                )
            )

            primary_entity = record.get(
                "snmp_entity_primary",
                {},
            )

            row["snmp_entity_manufacturer"] = primary_entity.get(
                "manufacturer",
                "",
            )
            row["snmp_entity_model"] = primary_entity.get(
                "model",
                "",
            )
            row["snmp_entity_serial"] = primary_entity.get(
                "serial",
                "",
            )
            row["snmp_entity_asset_id"] = primary_entity.get(
                "asset_id",
                "",
            )
            row["snmp_entity_name"] = primary_entity.get(
                "name",
                "",
            )

            row["snmp_interface_count"] = len(
                record.get(
                    "snmp_interfaces",
                    [],
                )
            )

            row["snmp_interface_macs"] = ";".join(
                "{0}|{1}".format(
                    item.get(
                        "mac",
                        "",
                    ),
                    item.get(
                        "vendor",
                        "",
                    ),
                )
                for item in record.get(
                    "snmp_interface_macs",
                    [],
                )
                if item.get("mac")
            )

            row["snmp_ip_addresses"] = ";".join(
                "{0}/{1}@if{2}".format(
                    item.get(
                        "address",
                        "",
                    ),
                    item.get(
                        "netmask",
                        "",
                    ),
                    item.get(
                        "ifindex",
                        "",
                    ),
                )
                for item in record.get(
                    "snmp_ip_addresses",
                    [],
                )
            )

            os_matches = record.get(
                "nmap_os_matches",
                [],
            )

            row["nmap_os_best"] = (
                "{0} ({1}%)".format(
                    os_matches[0].get(
                        "name",
                        "",
                    ),
                    os_matches[0].get(
                        "accuracy",
                        "",
                    ),
                )
                if os_matches
                else ""
            )

            row["evidence_sources"] = ",".join(
                record.get(
                    "evidence_sources",
                    [],
                )
            )

            for key in (
                "open_services",
                "snmp_entity_primary",
                "snmp_entity_inventory",
                "snmp_interfaces",
                "snmp_interface_macs",
                "snmp_ip_addresses",
                "nmap_os_matches",
                "netbox_write",
            ):
                row.pop(
                    key,
                    None,
                )

            writer.writerow({
                field: row.get(
                    field,
                    "",
                )
                for field in csv_fields
            })

    print("")
    print(
        "===== RESULTADO ====="
    )
    print(
        "Modo: DRY-RUN"
    )
    print(
        "Gravação no NetBox: NÃO"
    )
    print(
        "Hosts ativos: {0}".format(
            len(records)
        )
    )
    print(
        "JSON: {0}".format(
            json_file
        )
    )
    print(
        "CSV:  {0}".format(
            csv_file
        )
    )
    print("")
    print(
        "===== COBERTURA DE EVIDÊNCIAS V4 FINAL ====="
    )
    print(
        "DNS:                 {0}".format(
            evidence_summary["with_dns"]
        )
    )
    print(
        "MAC L2:              {0}".format(
            evidence_summary[
                "with_l2_mac"
            ]
        )
    )
    print(
        "TCP services:        {0}".format(
            evidence_summary[
                "with_tcp_services"
            ]
        )
    )
    print(
        "UDP services:        {0}".format(
            evidence_summary[
                "with_udp_services"
            ]
        )
    )
    print(
        "NSE safe/discovery:  {0}".format(
            evidence_summary[
                "with_safe_script_evidence"
            ]
        )
    )
    print(
        "SNMP system:         {0}".format(
            evidence_summary[
                "with_snmp_system"
            ]
        )
    )
    print(
        "SNMP ENTITY-MIB:     {0}".format(
            evidence_summary[
                "with_snmp_entity"
            ]
        )
    )
    print(
        "SNMP interfaces:     {0}".format(
            evidence_summary[
                "with_snmp_interfaces"
            ]
        )
    )
    print(
        "SNMP interface MAC:  {0}".format(
            evidence_summary[
                "with_snmp_interface_macs"
            ]
        )
    )
    print(
        "SNMP IP addresses:   {0}".format(
            evidence_summary[
                "with_snmp_ip_addresses"
            ]
        )
    )
    print(
        "SNMP L2 identity:    {0}".format(
            evidence_summary[
                "with_snmp_l2_identity"
            ]
        )
    )
    print(
        "OS fingerprint:      {0}".format(
            evidence_summary[
                "with_os_fingerprint"
            ]
        )
    )
    print(
        "Deep scan residual:  {0}".format(
            evidence_summary[
                "deep_scan_hosts"
            ]
        )
    )
    print(
        "Evidence HIGH:       {0}".format(
            evidence_summary[
                "evidence_high"
            ]
        )
    )
    print(
        "Evidence MEDIUM:     {0}".format(
            evidence_summary[
                "evidence_medium"
            ]
        )
    )
    print(
        "Evidence LOW:        {0}".format(
            evidence_summary[
                "evidence_low"
            ]
        )
    )
    print(
        "Evidence NONE:       {0}".format(
            evidence_summary[
                "evidence_none"
            ]
        )
    )

    if records:
        print("")
        print(
            "Primeiros equipamentos encontrados:"
        )

        for record in records[:20]:
            name = (
                record["snmp_name"]
                or record["reverse_dns"]
                or "SEM NOME"
            )

            print(
                "{0:15} | {1:30} | {2} | {3}".format(
                    record["ip"],
                    name[:30],
                    record[
                        "suggested_role"
                    ],
                    record[
                        "evidence_level"
                    ],
                )
            )


if __name__ == "__main__":
    main()
