#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

from collections import defaultdict

from modules.hypervisor import engine_v3 as v3

ENGINE_VERSION = "4.0-product"
base = v3.base
v2 = v3.v2
NetBox = v3.NetBox
REPORTS = v3.REPORTS
_ORIGINAL_RECLASSIFY = v3._apply_reclassifications


def utc_now():
    return v3.utc_now()


def collect_all():
    return v3.collect_all()


def build_plan(discovery, nb=None):
    return v3.build_plan(discovery, nb=nb or NetBox())


def _reclassify_signature(plan):
    rows = []
    for row in plan.get("records") or []:
        if row.get("decision") != "READY" or row.get("action") != "RECLASSIFY_SAFE":
            continue
        rows.append((
            row.get("object_type"),
            row.get("asset_id"),
            row.get("existing_id"),
            row.get("target_tenant"),
            row.get("target_site"),
        ))
    return sorted(rows, key=lambda x: tuple("" if v is None else str(v) for v in x))


def _global_preflight(discovery, original_plan, nb):
    print("===== HYPERVISOR PREFLIGHT GLOBAL MULTI-CONTEXT =====")
    live_plan, live_path = v3.build_plan(discovery, nb=nb)
    bad = [
        row for row in live_plan.get("records") or []
        if row.get("decision") in ("REVIEW", "BLOCKED")
    ]
    if bad:
        raise RuntimeError(
            "PREFLIGHT GLOBAL: {0} REVIEW/BLOCKED no estado atual; nenhuma escrita iniciada".format(len(bad))
        )

    before = _reclassify_signature(original_plan)
    now = _reclassify_signature(live_plan)
    if before != now:
        raise RuntimeError(
            "PREFLIGHT GLOBAL: conjunto RECLASSIFY_SAFE mudou desde o dry-run; nenhuma escrita iniciada"
        )

    actions = live_plan.get("ready_action_summary") or {}
    print("PREFLIGHT GLOBAL: OK")
    print("  READY/CREATE: {0}".format(actions.get("CREATE", 0)))
    print("  READY/UPDATE_SAFE: {0}".format(actions.get("UPDATE_SAFE", 0)))
    print("  READY/RECLASSIFY_SAFE: {0}".format(actions.get("RECLASSIFY_SAFE", 0)))
    print("  REVIEW/BLOCKED: 0")
    print("  NetBox write até aqui: NÃO")
    print("PREFLIGHT PLAN: {0}".format(live_path))
    return live_plan


def _reclassify_identity_preflight(ctx, subplan, nb):
    rows = [
        row for row in subplan.get("records") or []
        if row.get("decision") == "READY" and row.get("action") == "RECLASSIFY_SAFE"
    ]
    if not rows:
        return True

    # Target Tenant/Site must still be unique and present immediately before writes.
    v3._target_objects(nb, ctx)

    devices = base.query(nb, "dcim/devices/", limit=20000)
    vms = base.query(nb, "virtualization/virtual-machines/", limit=20000)
    ips = [x for x in base.query(nb, "ipam/ip-addresses/", limit=30000) if not x.get("vrf")]
    macs = base.query(nb, "dcim/mac-addresses/", limit=30000)
    clusters = base.query(nb, "virtualization/clusters/", limit=10000)
    prefixes = [x for x in base.query(nb, "ipam/prefixes/", limit=20000) if not x.get("vrf")]

    device_by_id = dict((x.get("id"), x) for x in devices if x.get("id") is not None)
    vm_by_id = dict((x.get("id"), x) for x in vms if x.get("id") is not None)
    device_serials = defaultdict(list)
    vm_serials = defaultdict(list)
    for obj in devices:
        serial = base.norm_serial(obj.get("serial"))
        if serial:
            device_serials[serial].append(obj)
    for obj in vms:
        serial = base.norm_serial(obj.get("serial"))
        if serial:
            vm_serials[serial].append(obj)

    for row in rows:
        kind = row.get("object_type")
        expected_id = row.get("existing_id")
        if not expected_id:
            raise RuntimeError("RECLASSIFY PREFLIGHT: existing_id ausente para {0}".format(row.get("asset_id")))

        if kind in ("HOST", "VM"):
            obj, reason = v3._strong_global_match(
                row,
                device_by_id if kind == "HOST" else vm_by_id,
                device_serials if kind == "HOST" else vm_serials,
                ips,
                macs,
            )
            if not obj or obj.get("id") != expected_id:
                raise RuntimeError(
                    "RECLASSIFY PREFLIGHT: identidade mudou para {0} ({1}); nenhuma escrita deste contexto iniciada".format(
                        row.get("desired_name") or row.get("asset_id"), reason
                    )
                )
            continue

        if kind == "CLUSTER":
            candidates = [x for x in clusters if base.norm(x.get("name")) == base.norm(row.get("name"))]
            if len(candidates) != 1 or candidates[0].get("id") != expected_id:
                raise RuntimeError(
                    "RECLASSIFY PREFLIGHT: Cluster deixou de ser correspondência global única: {0}".format(row.get("name"))
                )
            continue

        if kind == "PREFIX":
            candidates = [x for x in prefixes if base.clean(x.get("prefix")) == base.clean(row.get("prefix"))]
            if len(candidates) != 1 or candidates[0].get("id") != expected_id:
                raise RuntimeError(
                    "RECLASSIFY PREFLIGHT: Prefix deixou de ser correspondência global única: {0}".format(row.get("prefix"))
                )
            continue

        raise RuntimeError("RECLASSIFY PREFLIGHT: tipo não suportado: {0}".format(kind))

    print("RECLASSIFY PREFLIGHT {0}/{1}: OK | objetos={2} | NetBox write: NÃO".format(
        ctx.get("tenant"), ctx.get("site"), len(rows)
    ))
    return True


def _safe_apply_reclassifications(ctx, subplan, nb):
    _reclassify_identity_preflight(ctx, subplan, nb)
    return _ORIGINAL_RECLASSIFY(ctx, subplan, nb)


def apply_plan(discovery, plan, nb=None):
    active_nb = nb or NetBox()

    # No write is allowed until the entire multi-context plan is rebuilt from live
    # NetBox state and all reclassification identities are unchanged.
    live_plan = _global_preflight(discovery, plan, active_nb)

    previous = v3._apply_reclassifications
    v3._apply_reclassifications = _safe_apply_reclassifications
    try:
        return v3.apply_plan(discovery, live_plan, nb=active_nb)
    finally:
        v3._apply_reclassifications = previous


def audit(discovery, original_plan, nb=None):
    return v3.audit(discovery, original_plan, nb=nb or NetBox())
