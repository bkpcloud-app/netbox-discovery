#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

from collections import defaultdict

from modules.hypervisor import engine_v3 as v3
from modules.hypervisor import engine_v4 as v4

ENGINE_VERSION = "5.2-product"
base = v4.base
v2 = v4.v2
NetBox = v4.NetBox
REPORTS = v4.REPORTS
_ORIGINAL_PLAN_RECLASSIFICATIONS = v3._plan_reclassifications


def utc_now():
    return v4.utc_now()


def collect_all():
    return v4.collect_all()


def _review_signature(plan):
    rows = []
    for row in plan.get("records") or []:
        if row.get("decision") != "REVIEW":
            continue
        rows.append((
            row.get("asset_id"),
            row.get("object_type"),
            row.get("existing_id"),
            row.get("action"),
            row.get("reason"),
            row.get("target_tenant"),
            row.get("target_site"),
        ))
    return sorted(rows, key=lambda x: tuple("" if v is None else str(v) for v in x))


def _global_preflight_with_stable_review(discovery, original_plan, nb):
    """Allow only REVIEW rows that were already present and unchanged.

    REVIEW means the object itself is not eligible for write. The base importer
    already ignores existing REVIEW rows and aborts if a new REVIEW appears.
    Keep that behavior at the multi-context layer while still blocking any
    BLOCKED row, any changed/new REVIEW, and any change in RECLASSIFY_SAFE.
    """
    print("===== HYPERVISOR PREFLIGHT GLOBAL MULTI-CONTEXT =====")
    live_plan, live_path = v3.build_plan(discovery, nb=nb)

    blocked = [
        row for row in live_plan.get("records") or []
        if row.get("decision") == "BLOCKED"
    ]
    if blocked:
        raise RuntimeError(
            "PREFLIGHT GLOBAL: {0} BLOCKED no estado atual; nenhuma escrita iniciada".format(len(blocked))
        )

    before_reviews = _review_signature(original_plan)
    now_reviews = _review_signature(live_plan)
    if before_reviews != now_reviews:
        raise RuntimeError(
            "PREFLIGHT GLOBAL: conjunto REVIEW mudou desde o dry-run; nenhuma escrita iniciada"
        )

    before = v4._reclassify_signature(original_plan)
    now = v4._reclassify_signature(live_plan)
    if before != now:
        raise RuntimeError(
            "PREFLIGHT GLOBAL: conjunto RECLASSIFY_SAFE mudou desde o dry-run; nenhuma escrita iniciada"
        )

    actions = live_plan.get("ready_action_summary") or {}
    print("PREFLIGHT GLOBAL: OK")
    print("  READY/CREATE: {0}".format(actions.get("CREATE", 0)))
    print("  READY/UPDATE_SAFE: {0}".format(actions.get("UPDATE_SAFE", 0)))
    print("  READY/RECLASSIFY_SAFE: {0}".format(actions.get("RECLASSIFY_SAFE", 0)))
    print("  REVIEW ESTÁVEIS/IGNORADOS: {0}".format(len(now_reviews)))
    print("  BLOCKED: 0")
    print("  NetBox write até aqui: NÃO")
    print("PREFLIGHT PLAN: {0}".format(live_path))
    return live_plan


def _plan_reclassifications_with_parent_site(plan, nb):
    """Extend V3 reclassification planning for VMs already bound to a parent.

    V3 intentionally skipped VM Site comparison when a VM already had a
    Device or Cluster parent. That leaves an existing VM in an old/default Site
    even when the authoritative vCenter host context resolves to another Site.

    The apply engine already validates the live parent and patches VM
    tenant+site atomically. This planner extension promotes the existing
    strongly matched VM to RECLASSIFY_SAFE when its explicit Site differs from
    the target context and it has a Device/Cluster parent.

    Important: an already matched VM normally reaches this layer as READY/NOOP.
    NOOP therefore must still be inspected for Site inheritance. REVIEW/NOOP is
    intentionally not promoted by this extension.
    """
    _ORIGINAL_PLAN_RECLASSIFICATIONS(plan, nb)

    targets = v3._target_contexts(plan, nb)
    vms = base.query(nb, "virtualization/virtual-machines/", limit=20000)
    ips = [x for x in base.query(nb, "ipam/ip-addresses/", limit=30000) if not x.get("vrf")]
    macs = base.query(nb, "dcim/mac-addresses/", limit=30000)

    vm_by_id = dict((x.get("id"), x) for x in vms if x.get("id") is not None)
    vm_serials = defaultdict(list)
    for obj in vms:
        serial = base.norm_serial(obj.get("serial"))
        if serial:
            vm_serials[serial].append(obj)

    for row in plan.get("records") or []:
        if row.get("object_type") != "VM":
            continue

        action = v3.clean(row.get("action"))
        decision = v3.clean(row.get("decision"))
        if action not in ("CREATE", "UPDATE_SAFE", "NOOP"):
            continue
        if action == "NOOP" and decision != "READY":
            continue

        key = (v3.clean(row.get("target_tenant")), v3.clean(row.get("target_site")))
        target = targets.get(key)
        if not target:
            continue

        obj, match_reason = v3._strong_global_match(
            row, vm_by_id, vm_serials, ips, macs
        )
        if not obj:
            continue

        has_parent = bool(base.nested_id(obj.get("device")) or base.nested_id(obj.get("cluster")))
        if not has_parent:
            continue

        target_site_id = target["site"].get("id")
        if v3._site_id(obj) == target_site_id:
            continue

        v3._mark_reclassify(row, obj, target, match_reason)
        row["reason"] = (
            "VM vinculada a Host/Cluster com contexto autoritativo; Site atual difere do Site alvo; "
            "reclassificação segura para {0}/{1}"
        ).format(target["tenant"].get("name"), target["site"].get("name"))
        row["pending_reason"] = "VM_SITE_INHERIT_FROM_PARENT"

    return plan


def _with_fixed_planner(func, *args, **kwargs):
    previous = v3._plan_reclassifications
    previous_preflight = v4._global_preflight
    v3._plan_reclassifications = _plan_reclassifications_with_parent_site
    v4._global_preflight = _global_preflight_with_stable_review
    try:
        return func(*args, **kwargs)
    finally:
        v3._plan_reclassifications = previous
        v4._global_preflight = previous_preflight


def build_plan(discovery, nb=None):
    active_nb = nb or NetBox()
    return _with_fixed_planner(v4.build_plan, discovery, nb=active_nb)


def apply_plan(discovery, plan, nb=None):
    active_nb = nb or NetBox()
    return _with_fixed_planner(v4.apply_plan, discovery, plan, nb=active_nb)


def audit(discovery, original_plan, nb=None):
    active_nb = nb or NetBox()
    return _with_fixed_planner(v4.audit, discovery, original_plan, nb=active_nb)
