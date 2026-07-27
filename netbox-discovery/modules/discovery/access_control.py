#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import argparse
import json
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

PORTS = (3570, 51000)
VERSION = "1.0-product"


def clean(value):
    return "" if value is None else str(value).strip()


def run_nmap(ips):
    if not ips:
        return {}
    command = [
        "nmap", "-sT", "-sV", "--version-intensity", "3", "-Pn", "-n", "-T3",
        "--max-retries", "1", "--host-timeout", "20s", "--open",
        "-p", ",".join(str(x) for x in PORTS), "-oX", "-",
    ] + ips
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    stdout, stderr = process.communicate()
    if process.returncode not in (0, 1):
        raise RuntimeError("nmap access-control falhou: {0}".format(clean(stderr)[:300]))
    return parse_xml(stdout)


def parse_xml(raw):
    results = {}
    if not clean(raw):
        return results
    root = ET.fromstring(raw)
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
            if state is None or state.get("state") != "open":
                continue
            service = port_node.find("service")
            row = {
                "port": int(port_node.get("portid") or 0),
                "protocol": port_node.get("protocol", "tcp"),
                "state_reason": state.get("reason", ""),
                "service": service.get("name", "") if service is not None else "",
                "product": service.get("product", "") if service is not None else "",
                "version": service.get("version", "") if service is not None else "",
                "extrainfo": service.get("extrainfo", "") if service is not None else "",
                "hostname": service.get("hostname", "") if service is not None else "",
                "ostype": service.get("ostype", "") if service is not None else "",
                "devicetype": service.get("devicetype", "") if service is not None else "",
                "tunnel": service.get("tunnel", "") if service is not None else "",
                "method": service.get("method", "") if service is not None else "",
                "confidence": service.get("conf", "") if service is not None else "",
                "cpes": [(x.text or "").strip() for x in (service.findall("cpe") if service is not None else []) if (x.text or "").strip()],
                "scripts": {},
                "scan_sources": ["access-control-targeted"],
            }
            results.setdefault(ip, []).append(row)
    return results


def merge_services(current, extra):
    for row in extra:
        match = None
        for existing in current:
            if existing.get("protocol") == row.get("protocol") and existing.get("port") == row.get("port"):
                match = existing
                break
        if match is None:
            current.append(row)
            continue
        for key in ("service", "product", "version", "extrainfo", "hostname", "ostype", "devicetype", "tunnel", "method", "confidence"):
            if not match.get(key) and row.get(key):
                match[key] = row[key]
        sources = match.setdefault("scan_sources", [])
        for source in row.get("scan_sources") or []:
            if source not in sources:
                sources.append(source)


def atomic_json(path, data):
    parent = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(prefix="access-control-", suffix=".json", dir=parent)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except Exception:
            pass
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description="Enriquecimento direcionado para Inner/Topdata e controle de acesso")
    parser.add_argument("--input", required=True)
    args = parser.parse_args(argv)

    with open(args.input, "r") as handle:
        report = json.load(handle)
    devices = report.get("devices") or []
    ips = [clean(x.get("ip")) for x in devices if clean(x.get("ip"))]

    found = {}
    chunk = 32
    for pos in range(0, len(ips), chunk):
        found.update(run_nmap(ips[pos:pos + chunk]))

    enriched = 0
    for device in devices:
        rows = found.get(clean(device.get("ip")), [])
        if not rows:
            continue
        before = len(device.get("open_services") or [])
        services = device.setdefault("open_services", [])
        merge_services(services, rows)
        if len(services) != before or rows:
            enriched += 1

    report["access_control_enricher_version"] = VERSION
    report["access_control_enriched_hosts"] = enriched
    atomic_json(args.input, report)
    print("ACCESS CONTROL ENRICH: {0} host(s) | portas 3570/51000".format(enriched))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("ERRO: {0}".format(exc), file=sys.stderr)
        sys.exit(1)
