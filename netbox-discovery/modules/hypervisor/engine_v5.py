#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

from collections import defaultdict

from modules.hypervisor import engine_v3 as v3
from modules.hypervisor import engine_v4 as v4

ENGINE_VERSION = "5.0-product"
base = v4.base
v2 = v4.v2
NetBox = v4.NetBox
REPORTS = v4.REPORTS
_ORIGINAL_PLAN_RECLASSIFICATIONS = v3._plan_reclassifications


def utc_now():
    return v4.utc_now()


def collect_all():
    return v4.collect_all()


def _plan_reclassifications_with_parent_site(plan, nb):
    """Extend V3 reclassification planning for VMs already bound to a parent.

    V3 intentionally skipped VM Site comparison when a VM already had a
    Device or Cluster parent. That leaves an existing VM in an old/default Site
    even when the authoritative vCenter host context resolves to another Site.

    The apply engine already validates the live parent and patches VM
    tenant+site atomically. This planner extension only promotes the existing
    strongly matched VM to RECLASSIFY_SAFE when its explicit Site differs from
    the target context and it has a Device/Cluster parent.
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
        if row.get("action") not in ("CREATE", "UPDATE_SAFE"):
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
    v3._plan_reclassifications = _plan_reclassifications_with_parent_site
    try:
        return func(*args, **kwargs)
    finally:
        v3._plan_reclassifications = previous


def build_plan(discovery, nb=None):
    active_nb = nb or NetBox()
    return _with_fixed_planner(v4.build_plan, discovery, nb=active_nb)


def apply_plan(discovery, plan, nb=None):
    active_nb = nb or NetBox()
    return _with_fixed_planner(v4.apply_plan, discovery, plan, nb=active_nb)


def audit(discovery, original_plan, nb=None):
    active_nb = nb or NetBox()
    return _with_fixed_planner(v4.audit, discovery, original_plan, nb=active_nb)
