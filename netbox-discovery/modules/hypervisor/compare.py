#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import fcntl
import json
import os
import sys
from collections import Counter, defaultdict

BASE = os.environ.get("NETBOX_DISCOVERY_BASE", "/opt/netbox-discovery")
LOCK_FILE = "/var/lock/netbox-discovery-global.lock"
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from lib.netbox import NetBox
from modules.hypervisor import engine_v4 as engine

base = engine.base
REPORTS = engine.REPORTS


def _scope_site_name(obj):
    scope = (obj or {}).get("scope") or {}
    if isinstance(scope, dict):
        return base.clean(scope.get("name") or scope.get("display"))
    return ""


def _vm_effective_site(vm, cluster_by_id, device_by_id):
    direct = base.nested_name((vm or {}).get("site"))
    if direct:
        return direct
    cluster_id = base.nested_id((vm or {}).get("cluster"))
    if cluster_id:
        return _scope_site_name(cluster_by_id.get(cluster_id) or {})
    device_id = base.nested_id((vm or {}).get("device"))
    if device_id:
        return base.nested_name((device_by_id.get(device_id) or {}).get("site"))
    return ""


def _status(current_tenant, current_site, target_tenant, target_site):
    if not current_tenant and not current_site:
        return "MISSING"
    if base.norm(current_tenant) == base.norm(target_tenant) and base.norm(current_site) == base.norm(target_site):
        return "OK"
    return "MISMATCH"


def _row(kind, name, current_tenant, current_site, target_tenant, target_site, object_id=None, evidence=""):
    return {
        "object_type": kind,
        "name": base.clean(name),
        "object_id": object_id,
        "current_tenant": base.clean(current_tenant),
        "current_site": base.clean(current_site),
        "target_tenant": base.clean(target_tenant),
        "target_site": base.clean(target_site),
        "status": _status(current_tenant, current_site, target_tenant, target_site),
        "evidence": evidence,
    }


def _unique_by_serial(index, serial):
    key = base.norm_serial(serial)
    rows = index.get(key, []) if key else []
    if len(rows) == 1:
        return rows[0], "serial/UUID"
    if len(rows) > 1:
        return None, "AMBIGUOUS"
    return None, ""


def compare():
    lock = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        raise RuntimeError("outro processo netbox-discovery está em execução; compare não roda durante APPLY/Update")
    lock.write("hypervisor-compare:{0}".format(os.getpid()))
    lock.flush()

    print("===== HYPERVISOR COMPARE NETBOX x SOURCE =====")
    print("Modo: READ-ONLY")
    print("NetBox write: NÃO")

    discovery, discovery_path = engine.collect_all()
    nb = NetBox()
    devices = base.query(nb, "dcim/devices/", limit=20000)
    vms = base.query(nb, "virtualization/virtual-machines/", limit=30000)
    clusters = base.query(nb, "virtualization/clusters/", limit=10000)
    prefixes = [x for x in base.query(nb, "ipam/prefixes/", limit=30000) if not x.get("vrf")]

    device_by_id = dict((x.get("id"), x) for x in devices if x.get("id") is not None)
    cluster_by_id = dict((x.get("id"), x) for x in clusters if x.get("id") is not None)
    device_serials = defaultdict(list)
    vm_serials = defaultdict(list)
    cluster_names = defaultdict(list)
    prefix_values = defaultdict(list)

    for obj in devices:
        serial = base.norm_serial(obj.get("serial"))
        if serial:
            device_serials[serial].append(obj)
    for obj in vms:
        serial = base.norm_serial(obj.get("serial"))
        if serial:
            vm_serials[serial].append(obj)
    for obj in clusters:
        cluster_names[base.norm(obj.get("name"))].append(obj)
    for obj in prefixes:
        prefix_values[base.clean(obj.get("prefix"))].append(obj)

    rows = []
    for ctx in discovery.get("contexts") or []:
        target_tenant = base.clean(ctx.get("tenant"))
        target_site = base.clean(ctx.get("site"))

        for result in ctx.get("results") or []:
            for host in result.get("hosts") or []:
                serial = base.host_identity_serial(host)
                obj, evidence = _unique_by_serial(device_serials, serial)
                if evidence == "AMBIGUOUS":
                    rows.append({
                        "object_type": "HOST", "name": base.clean(host.get("name")), "object_id": None,
                        "current_tenant": "", "current_site": "", "target_tenant": target_tenant,
                        "target_site": target_site, "status": "AMBIGUOUS", "evidence": "serial duplicado no NetBox",
                    })
                elif obj:
                    rows.append(_row(
                        "HOST", obj.get("name") or host.get("name"),
                        base.nested_name(obj.get("tenant")), base.nested_name(obj.get("site")),
                        target_tenant, target_site, obj.get("id"), evidence,
                    ))
                else:
                    rows.append(_row("HOST", host.get("name"), "", "", target_tenant, target_site, None, "sem match forte"))

            for vm in result.get("vms") or []:
                serial = base.clean(vm.get("serial") or vm.get("uuid"))
                obj, evidence = _unique_by_serial(vm_serials, serial)
                if evidence == "AMBIGUOUS":
                    rows.append({
                        "object_type": "VM", "name": base.clean(vm.get("name")), "object_id": None,
                        "current_tenant": "", "current_site": "", "target_tenant": target_tenant,
                        "target_site": target_site, "status": "AMBIGUOUS", "evidence": "serial/UUID duplicado no NetBox",
                    })
                elif obj:
                    rows.append(_row(
                        "VM", obj.get("name") or vm.get("name"),
                        base.nested_name(obj.get("tenant")), _vm_effective_site(obj, cluster_by_id, device_by_id),
                        target_tenant, target_site, obj.get("id"), evidence,
                    ))
                else:
                    rows.append(_row("VM", vm.get("name"), "", "", target_tenant, target_site, None, "sem match forte"))

            for cluster in result.get("clusters") or []:
                matches = cluster_names.get(base.norm(cluster.get("name")), [])
                if len(matches) == 1:
                    obj = matches[0]
                    rows.append(_row(
                        "CLUSTER", obj.get("name"), base.nested_name(obj.get("tenant")), _scope_site_name(obj),
                        target_tenant, target_site, obj.get("id"), "nome global único",
                    ))
                elif len(matches) > 1:
                    rows.append({
                        "object_type": "CLUSTER", "name": base.clean(cluster.get("name")), "object_id": None,
                        "current_tenant": "", "current_site": "", "target_tenant": target_tenant,
                        "target_site": target_site, "status": "AMBIGUOUS", "evidence": "nome de cluster duplicado",
                    })
                else:
                    rows.append(_row("CLUSTER", cluster.get("name"), "", "", target_tenant, target_site, None, "não existe"))

        for network in ctx.get("networks") or []:
            matches = prefix_values.get(base.clean(network), [])
            if len(matches) == 1:
                obj = matches[0]
                rows.append(_row(
                    "PREFIX", obj.get("prefix"), base.nested_name(obj.get("tenant")), _scope_site_name(obj),
                    target_tenant, target_site, obj.get("id"), "prefixo exato",
                ))
            elif len(matches) > 1:
                rows.append({
                    "object_type": "PREFIX", "name": base.clean(network), "object_id": None,
                    "current_tenant": "", "current_site": "", "target_tenant": target_tenant,
                    "target_site": target_site, "status": "AMBIGUOUS", "evidence": "prefixo duplicado",
                })
            else:
                rows.append(_row("PREFIX", network, "", "", target_tenant, target_site, None, "não existe"))

    summary = dict(Counter(row.get("status") for row in rows))
    by_type = defaultdict(Counter)
    for row in rows:
        by_type[row.get("object_type")][row.get("status")] += 1

    divergences = [row for row in rows if row.get("status") != "OK"]
    print("===== RESUMO =====")
    print("Objetos comparados: {0}".format(len(rows)))
    print("OK: {0}".format(summary.get("OK", 0)))
    print("MISMATCH: {0}".format(summary.get("MISMATCH", 0)))
    print("MISSING: {0}".format(summary.get("MISSING", 0)))
    print("AMBIGUOUS: {0}".format(summary.get("AMBIGUOUS", 0)))
    for kind in sorted(by_type):
        counts = by_type[kind]
        print("  {0}: OK={1} MISMATCH={2} MISSING={3} AMBIGUOUS={4}".format(
            kind, counts.get("OK", 0), counts.get("MISMATCH", 0), counts.get("MISSING", 0), counts.get("AMBIGUOUS", 0)
        ))

    print("===== DIVERGÊNCIAS =====")
    if not divergences:
        print("Nenhuma divergência Tenant/Site encontrada.")
    else:
        for pos, row in enumerate(divergences, 1):
            print("[{0}/{1}] {2} | {3} | {4} | atual={5}/{6} | esperado={7}/{8}".format(
                pos, len(divergences), row.get("status"), row.get("object_type"), row.get("name"),
                row.get("current_tenant") or "-", row.get("current_site") or "-",
                row.get("target_tenant") or "-", row.get("target_site") or "-",
            ))
            print("  Evidência: {0} | NetBox ID={1}".format(row.get("evidence") or "-", row.get("object_id") or "-"))

    base.ensure_reports_dir()
    path = os.path.join(REPORTS, "MULTI-hypervisor-compare-{0}.json".format(base.utc_stamp()))
    with open(path, "w") as handle:
        json.dump({
            "stage": "HYPERVISOR_COMPARE",
            "generated_at": engine.utc_now(),
            "discovery": discovery_path,
            "summary": summary,
            "rows": rows,
            "netbox_write": False,
        }, handle, indent=2, sort_keys=True)
    print("COMPARE STATUS: {0}".format("OK" if not divergences else "DIVERGENT"))
    print("NetBox write: NÃO")
    print("JSON: {0}".format(path))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(compare())
    except Exception as exc:
        print("ERRO: {0}".format(exc), file=sys.stderr)
        sys.exit(1)
