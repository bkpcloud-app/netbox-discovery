#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import concurrent.futures
import ipaddress
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, "..", ".."))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.discovery import network_v5 as v5

DISCOVERY_WRAPPER_VERSION = "4.6-product"
LARGE_CANDIDATE_THRESHOLD = 4096
PRIMARY_CHUNK_PREFIX = 24
PRIMARY_WORKERS = 4
PRIMARY_TIMEOUT = 240
PRIMARY_RETRY_TIMEOUT = 600
SNMP_WORKERS = 64
SNMP_PROGRESS_EVERY = 2048

base = v5.v4.base
ORIG_DISCOVER_HOSTS = base.discover_hosts

PRIMARY_TCP_PORTS = sorted(set(
    list(base.DISCOVERY_RESCUE_TCP_PORTS)
    + [53, 88, 123, 161, 389, 515, 631, 1433, 1521, 2049, 3260,
       3306, 5060, 5432, 5985, 5986, 6379, 9200, 9443, 10000,
       10443, 27017, 44818]
))
PRIMARY_ACK_PORTS = [22, 80, 102, 135, 139, 443, 445, 502, 3389, 8006, 8080, 8291, 8443, 9100]
PRIMARY_UDP_PORTS = sorted(set(
    list(base.UDP_EVIDENCE_PORTS)
    + [53, 123, 161, 500, 623, 1900, 3702, 4500, 5353]
))


def _scan_targets(networks):
    """Return unique bounded IPv4 scan targets, splitting large prefixes at /24."""
    parsed = []
    for value in networks:
        network = ipaddress.ip_network(str(value), strict=False)
        if network.version != 4:
            raise RuntimeError("IPv6 ainda não é suportado pelo discovery Network: {0}".format(value))
        parsed.append(network)

    # Collapse overlapping entries before splitting. A /24 repeated inside a /16
    # must not be scanned twice.
    collapsed = list(ipaddress.collapse_addresses(parsed))
    targets = []
    for network in collapsed:
        if network.prefixlen < PRIMARY_CHUNK_PREFIX:
            targets.extend(network.subnets(new_prefix=PRIMARY_CHUNK_PREFIX))
        else:
            targets.append(network)
    return [str(item) for item in targets]


def _primary_command(target):
    return [
        "nmap",
        "-sn",
        "-n",
        "-T4",
        "-PE",
        "-PP",
        "-PS" + ",".join(str(port) for port in PRIMARY_TCP_PORTS),
        "-PA" + ",".join(str(port) for port in PRIMARY_ACK_PORTS),
        "-PU" + ",".join(str(port) for port in PRIMARY_UDP_PORTS),
        "--max-retries",
        "1",
        "--host-timeout",
        "8s",
        "--reason",
        "-oX",
        "-",
        target,
    ]


def _scan_primary_target(target, timeout):
    code, stdout, stderr = base.run_command(_primary_command(target), timeout=timeout)
    if code not in (0, 1):
        reason = (stderr or "").strip()
        if code == 124:
            reason = "timeout após {0}s".format(timeout)
        return target, {}, "exit={0} {1}".format(code, reason).strip()
    try:
        hosts = base._parse_discovery_xml(stdout, "nmap-host-discovery-large-cidr")
    except Exception as exc:
        return target, {}, "XML inválido: {0}".format(exc)
    return target, hosts, ""


def _run_primary_targets(targets):
    hosts = {}
    failures = []
    completed = 0
    total = len(targets)

    print(
        "  Discovery escalável: {0} lotes IPv4, até /{1}, {2} workers...".format(
            total, PRIMARY_CHUNK_PREFIX, min(PRIMARY_WORKERS, max(1, total))
        ),
        flush=True,
    )

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=min(PRIMARY_WORKERS, max(1, total))
    ) as executor:
        futures = [
            executor.submit(_scan_primary_target, target, PRIMARY_TIMEOUT)
            for target in targets
        ]
        for future in concurrent.futures.as_completed(futures):
            target, found, error = future.result()
            completed += 1
            if error:
                failures.append(target)
            else:
                base._merge_discovered_hosts(hosts, found)
            if completed == total or completed % 16 == 0:
                print(
                    "  Discovery primário: {0}/{1} lotes | hosts={2} | retry={3}".format(
                        completed, total, len(hosts), len(failures)
                    ),
                    flush=True,
                )

    final_failures = []
    if failures:
        print(
            "  Retry controlado: {0} lote(s) com timeout/erro...".format(len(failures)),
            flush=True,
        )
        for position, target in enumerate(failures, 1):
            retry_target, found, error = _scan_primary_target(target, PRIMARY_RETRY_TIMEOUT)
            if error:
                final_failures.append("{0} ({1})".format(retry_target, error))
            else:
                base._merge_discovered_hosts(hosts, found)
            if position == len(failures) or position % 8 == 0:
                print(
                    "  Retry primário: {0}/{1} | falhas finais={2}".format(
                        position, len(failures), len(final_failures)
                    ),
                    flush=True,
                )

    if final_failures:
        preview = ", ".join(final_failures[:12])
        if len(final_failures) > 12:
            preview += ", ... (+{0})".format(len(final_failures) - 12)
        raise RuntimeError(
            "Falha no nmap discovery após retry em {0} lote(s): {1}".format(
                len(final_failures), preview
            )
        )

    return hosts


def _large_snmp_rescue(ip_addresses, communities):
    hosts = {}
    if not ip_addresses or not communities:
        return hosts

    total = len(ip_addresses)
    workers = min(SNMP_WORKERS, max(1, total))
    print(
        "  Rescue SNMP escalável: {0} IPs restantes, {1} workers...".format(
            total, workers
        ),
        flush=True,
    )

    completed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(base._quick_snmp_rescue, ip, communities)
            for ip in ip_addresses
        ]
        for future in concurrent.futures.as_completed(futures):
            completed += 1
            try:
                ip = future.result()
            except Exception:
                ip = ""
            if ip:
                hosts[ip] = {
                    "ip": ip,
                    "mac": "",
                    "mac_vendor": "",
                    "reason": "snmp-response",
                    "reason_ttl": "",
                    "discovery_sources": ["snmp-rescue-large-cidr"],
                }
            if completed == total or completed % SNMP_PROGRESS_EVERY == 0:
                print(
                    "  Rescue SNMP: {0}/{1} | adicionados={2}".format(
                        completed, total, len(hosts)
                    ),
                    flush=True,
                )
    return hosts


def discover_hosts(networks, communities, exclusions):
    candidates = base._all_candidate_ips(networks, exclusions)
    if len(candidates) <= LARGE_CANDIDATE_THRESHOLD:
        return ORIG_DISCOVER_HOSTS(networks, communities, exclusions)

    targets = _scan_targets(networks)
    print(
        "  Modo LARGE-CIDR: {0} endereços candidatos em {1} lotes.".format(
            len(candidates), len(targets)
        ),
        flush=True,
    )

    hosts = _run_primary_targets(targets)
    hosts = base._filter_discovered_hosts(hosts, candidates)
    print("  Discovery primário: {0} hosts".format(len(hosts)), flush=True)

    # The large-CIDR primary phase already probes every TCP port used by the
    # legacy connect-scan rescue. Repeating an exhaustive sT pass over tens of
    # thousands of absent addresses would create hours of redundant traffic.
    print(
        "  Rescue TCP: integrado ao discovery primário LARGE-CIDR "
        "({0} portas TCP).".format(len(PRIMARY_TCP_PORTS)),
        flush=True,
    )

    missing = [ip for ip in candidates if ip not in hosts]
    snmp_hosts = _large_snmp_rescue(missing, communities)
    base._merge_discovered_hosts(hosts, snmp_hosts)
    print("  Rescue SNMP adicionou: {0}".format(len(snmp_hosts)), flush=True)
    return hosts


def main():
    old_discover = base.discover_hosts
    old_version = v5.DISCOVERY_WRAPPER_VERSION
    try:
        base.discover_hosts = discover_hosts
        v5.DISCOVERY_WRAPPER_VERSION = DISCOVERY_WRAPPER_VERSION
        return v5.main()
    finally:
        v5.DISCOVERY_WRAPPER_VERSION = old_version
        base.discover_hosts = old_discover


if __name__ == "__main__":
    sys.exit(main())
