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


def _row_name(row):
    return row.get("desired_name") or row.get("name") or row.get("prefix") or row.get("asset_id") or "?"


def _status_from_plan(row):
    decision = row.get("decision")
    action = row.get("action")
    if decision in ("REVIEW", "BLOCKED"):
        return "AMBIGUOUS"
    if decision == "READY" and action == "RECLASSIFY_SAFE":
        return "MISMATCH"
    if decision == "READY" and action == "CREATE":
        return "MISSING"
    return "OK"


def _load_current_objects(nb):
    devices = base.query(nb, "dcim/devices/", limit=20000)
    vms = base.query(nb, "virtualization/virtual-machines/", limit=30000)
    clusters = base.query(nb, "virtualization/clusters/", limit=10000)
    prefixes = [x for x in base.query(nb, "ipam/prefixes/", limit=30000) if not x.get("vrf")]
    return {
        "devices": dict((x.get("id"), x) for x in devices if x.get("id") is not None),
        "vms": dict((x.get("id"), x) for x in vms if x.get("id") is not None),
        "clusters": dict((x.get("id"), x) for x in clusters if x.get("id") is not None),
        "prefixes": dict((x.get("id"), x) for x in prefixes if x.get("id") is not None),
    }


def _current_context(row, current):
    status = _status_from_plan(row)
    target_tenant = base.clean(row.get("target_tenant"))
    target_site = base.clean(row.get("target_site"))
    kind = row.get("object_type")
    object_id = row.get("existing_id")

    if status == "OK":
        return target_tenant, target_site, object_id
    if status in ("MISSING", "AMBIGUOUS"):
        return "", "", object_id

    # RECLASSIFY_SAFE already carries the source context found by the global
    # identity guard. Enrich the Site from live NetBox for VMs whose Site is
    # effective through their Cluster/Device rather than stored directly.
    tenant = base.clean(row.get("migration_source_tenant"))
    site = base.clean(row.get("migration_source_site"))

    if kind == "HOST" and object_id:
        obj = current["devices"].get(object_id) or {}
        tenant = tenant or base.nested_name(obj.get("tenant"))
        site = site or base.nested_name(obj.get("site"))
    elif kind == "VM" and object_id:
        obj = current["vms"].get(object_id) or {}
        tenant = tenant or base.nested_name(obj.get("tenant"))
        site = site or _vm_effective_site(obj, current["clusters"], current["devices"])
    elif kind == "CLUSTER" and object_id:
        obj = current["clusters"].get(object_id) or {}
        tenant = tenant or base.nested_name(obj.get("tenant"))
        site = site or _scope_site_name(obj)
    elif kind == "PREFIX" and object_id:
        obj = current["prefixes"].get(object_id) or {}
        tenant = tenant or base.nested_name(obj.get("tenant"))
        site = site or _scope_site_name(obj)

    return base.clean(tenant), base.clean(site), object_id


def _compare_row(row, current):
    status = _status_from_plan(row)
    current_tenant, current_site, object_id = _current_context(row, current)
    return {
        "object_type": row.get("object_type") or "?",
        "name": _row_name(row),
        "object_id": object_id,
        "current_tenant": current_tenant,
        "current_site": current_site,
        "target_tenant": base.clean(row.get("target_tenant")),
        "target_site": base.clean(row.get("target_site")),
        "status": status,
        "plan_decision": row.get("decision"),
        "plan_action": row.get("action"),
        "evidence": row.get("migration_match") or row.get("reason") or "planner multi-contexto",
    }


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

    # Reuse the exact production planner/identity logic. This is important for
    # VMs that do not have serial/UUID and are safely correlated by IP/MAC.
    plan, plan_path = engine.build_plan(discovery, nb=nb)
    current = _load_current_objects(nb)
    rows = [_compare_row(row, current) for row in (plan.get("records") or [])]

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
            print("  Planner: {0}/{1} | Evidência: {2} | NetBox ID={3}".format(
                row.get("plan_decision") or "-", row.get("plan_action") or "-",
                row.get("evidence") or "-", row.get("object_id") or "-",
            ))

    base.ensure_reports_dir()
    path = os.path.join(REPORTS, "MULTI-hypervisor-compare-{0}.json".format(base.utc_stamp()))
    with open(path, "w") as handle:
        json.dump({
            "stage": "HYPERVISOR_COMPARE",
            "generated_at": engine.utc_now(),
            "discovery": discovery_path,
            "plan": plan_path,
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
