#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

from collections import defaultdict

from modules.hypervisor import engine_v3 as v3

ENGINE_VERSION = "4.2-product"
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


def _cluster_member_preflight(ctx, rows, devices, clusters, target_site_id):
    host_rows_by_id = dict(
        (row.get("existing_id"), row)
        for row in rows
        if row.get("object_type") == "HOST" and row.get("existing_id")
    )

    for row in rows:
        if row.get("object_type") != "CLUSTER":
            continue
        cluster_id = row.get("existing_id")
        candidates = [x for x in clusters if x.get("id") == cluster_id]
        if len(candidates) != 1:
            raise RuntimeError("RECLASSIFY PREFLIGHT: Cluster ID {0} não está mais único/presente".format(cluster_id))

        members = [x for x in devices if base.nested_id(x.get("cluster")) == cluster_id]
        for device in members:
            current_site_id = base.nested_id(device.get("site"))
            if current_site_id == target_site_id:
                continue
            if device.get("id") not in host_rows_by_id:
                raise RuntimeError(
                    "RECLASSIFY PREFLIGHT: Cluster {0} possui host {1} fora do Site alvo sem HOST RECLASSIFY_SAFE; nenhuma escrita deste contexto iniciada".format(
                        row.get("name") or row.get("desired_name") or cluster_id,
                        device.get("name") or device.get("id"),
                    )
                )
            if base.nested_id(device.get("rack")) or base.nested_id(device.get("location")):
                raise RuntimeError(
                    "RECLASSIFY PREFLIGHT: Host {0} do Cluster {1} possui rack/location e não pode mudar de Site automaticamente".format(
                        device.get("name") or device.get("id"),
                        row.get("name") or row.get("desired_name") or cluster_id,
                    )
                )


def _reclassify_preflight_state(ctx, subplan, nb):
    rows = [
        row for row in subplan.get("records") or []
        if row.get("decision") == "READY" and row.get("action") == "RECLASSIFY_SAFE"
    ]
    if not rows:
        return {"rows": [], "tenant": None, "site": None, "devices": [], "clusters": []}

    target_tenant, target_site = v3._target_objects(nb, ctx)

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

    _cluster_member_preflight(ctx, rows, devices, clusters, target_site.get("id"))

    print("RECLASSIFY PREFLIGHT {0}/{1}: OK | objetos={2} | NetBox write: NÃO".format(
        ctx.get("tenant"), ctx.get("site"), len(rows)
    ))
    return {
        "rows": rows,
        "tenant": target_tenant,
        "site": target_site,
        "devices": devices,
        "clusters": clusters,
    }


def _reclassify_identity_preflight(ctx, subplan, nb):
    _reclassify_preflight_state(ctx, subplan, nb)
    return True


def _subset_plan(subplan, kinds):
    allowed = set(kinds)
    return {
        "stage": subplan.get("stage") or "HYPERVISOR_PLAN",
        "records": [
            row for row in subplan.get("records") or []
            if row.get("decision") == "READY"
            and row.get("action") == "RECLASSIFY_SAFE"
            and row.get("object_type") in allowed
        ],
        "netbox_write": False,
    }


def _release_cluster_scopes(ctx, state, nb):
    events = []
    cluster_by_id = dict((x.get("id"), x) for x in state.get("clusters") or [] if x.get("id") is not None)
    for row in state.get("rows") or []:
        if row.get("object_type") != "CLUSTER":
            continue
        cluster_id = row.get("existing_id")
        current = cluster_by_id.get(cluster_id) or {}
        if not base.nested_id(current.get("scope")) and not current.get("scope_id"):
            continue
        nb.patch("virtualization/clusters/{0}/".format(cluster_id), {
            "scope_type": None,
            "scope_id": None,
        })
        events.append({
            "phase": "RECLASSIFY", "object_type": "CLUSTER", "action": "SCOPE_RELEASED_SAFE",
            "name": row.get("name") or row.get("desired_name") or row.get("asset_id"),
            "object_id": cluster_id,
            "detail": "scope temporariamente removido antes de mover hosts para {0}/{1}".format(
                ctx.get("tenant"), ctx.get("site")
            ),
        })
        print("CLUSTER SCOPE RELEASE {0}: OK | NetBox write: SIM".format(
            row.get("name") or row.get("desired_name") or cluster_id
        ))
    return events


def _vm_parent_preflight(ctx, vm_plan, nb, target_site_id):
    rows = [
        row for row in vm_plan.get("records") or []
        if row.get("decision") == "READY" and row.get("action") == "RECLASSIFY_SAFE" and row.get("object_type") == "VM"
    ]
    if not rows:
        return True

    vms = base.query(nb, "virtualization/virtual-machines/", limit=20000)
    devices = base.query(nb, "dcim/devices/", limit=20000)
    clusters = base.query(nb, "virtualization/clusters/", limit=10000)
    vm_by_id = dict((x.get("id"), x) for x in vms if x.get("id") is not None)
    device_by_id = dict((x.get("id"), x) for x in devices if x.get("id") is not None)
    cluster_by_id = dict((x.get("id"), x) for x in clusters if x.get("id") is not None)

    for row in rows:
        vm_id = row.get("existing_id")
        vm = vm_by_id.get(vm_id)
        if not vm:
            raise RuntimeError("VM PARENT PREFLIGHT: VM ID {0} não encontrada".format(vm_id))

        device_id = base.nested_id(vm.get("device"))
        if device_id:
            device = device_by_id.get(device_id)
            if not device:
                raise RuntimeError("VM PARENT PREFLIGHT: device ID {0} da VM {1} não encontrado".format(device_id, vm_id))
            device_site_id = base.nested_id(device.get("site"))
            if device_site_id != target_site_id:
                raise RuntimeError(
                    "VM PARENT PREFLIGHT: device {0} da VM {1} ainda está fora do Site alvo {2}; nenhuma VM deste contexto foi reclassificada".format(
                        device.get("name") or device_id, row.get("desired_name") or vm.get("name") or vm_id, ctx.get("site")
                    )
                )

        cluster_id = base.nested_id(vm.get("cluster"))
        if cluster_id:
            cluster = cluster_by_id.get(cluster_id)
            if not cluster:
                raise RuntimeError("VM PARENT PREFLIGHT: cluster ID {0} da VM {1} não encontrado".format(cluster_id, vm_id))
            cluster_site_id = v3._scope_site_id(cluster)
            if cluster_site_id not in (None, target_site_id):
                raise RuntimeError(
                    "VM PARENT PREFLIGHT: cluster {0} da VM {1} ainda está fora do Site alvo {2}; nenhuma VM deste contexto foi reclassificada".format(
                        cluster.get("name") or cluster_id, row.get("desired_name") or vm.get("name") or vm_id, ctx.get("site")
                    )
                )

    print("VM PARENT PREFLIGHT {0}/{1}: OK | VMs={2} | NetBox write: NÃO".format(
        ctx.get("tenant"), ctx.get("site"), len(rows)
    ))
    return True


def _apply_vm_reclassifications(ctx, vm_plan, nb):
    rows = [
        row for row in vm_plan.get("records") or []
        if row.get("decision") == "READY" and row.get("action") == "RECLASSIFY_SAFE" and row.get("object_type") == "VM"
    ]
    if not rows:
        return []

    tenant, site = v3._target_objects(nb, ctx)
    tenant_id = tenant["id"]
    site_id = site["id"]
    events = []
    for row in rows:
        object_id = row.get("existing_id")
        if not object_id:
            raise RuntimeError("VM RECLASSIFY sem existing_id: {0}".format(row.get("asset_id")))
        nb.patch("virtualization/virtual-machines/{0}/".format(object_id), {
            "tenant": tenant_id,
            "site": site_id,
        })
        events.append({
            "phase": "RECLASSIFY", "object_type": "VM", "action": "RECLASSIFIED_SAFE",
            "name": row.get("desired_name") or row.get("name") or row.get("asset_id"),
            "object_id": object_id,
            "detail": "tenant={0}; site={1}".format(ctx.get("tenant"), ctx.get("site")),
        })
        v3._patch_owned_ip_tenant(nb, "VM", object_id, tenant_id, events)
    return events


def _safe_apply_reclassifications(ctx, subplan, nb):
    state = _reclassify_preflight_state(ctx, subplan, nb)
    rows = state.get("rows") or []
    if not rows:
        return []

    events = []

    prefix_plan = _subset_plan(subplan, ("PREFIX",))
    if prefix_plan["records"]:
        events.extend(_ORIGINAL_RECLASSIFY(ctx, prefix_plan, nb))

    # NetBox enforces Site consistency in both directions between a scoped
    # Cluster and its host Devices. Use an unscoped Cluster as the safe bridge.
    cluster_plan = _subset_plan(subplan, ("CLUSTER",))
    if cluster_plan["records"]:
        events.extend(_release_cluster_scopes(ctx, state, nb))

    host_plan = _subset_plan(subplan, ("HOST",))
    if host_plan["records"]:
        events.extend(_ORIGINAL_RECLASSIFY(ctx, host_plan, nb))

    if cluster_plan["records"]:
        events.extend(_ORIGINAL_RECLASSIFY(ctx, cluster_plan, nb))

    # VMs inherit the authoritative Tenant/Site of their Host/Cluster. Re-read
    # the live parents after Host/Cluster migration, revalidate VM identity, then
    # patch tenant+site atomically so NetBox never sees device/site inconsistency.
    vm_plan = _subset_plan(subplan, ("VM",))
    if vm_plan["records"]:
        vm_state = _reclassify_preflight_state(ctx, vm_plan, nb)
        _vm_parent_preflight(ctx, vm_plan, nb, vm_state["site"].get("id"))
        events.extend(_apply_vm_reclassifications(ctx, vm_plan, nb))

    return events


def apply_plan(discovery, plan, nb=None):
    active_nb = nb or NetBox()

    live_plan = _global_preflight(discovery, plan, active_nb)

    previous = v3._apply_reclassifications
    v3._apply_reclassifications = _safe_apply_reclassifications
    try:
        return v3.apply_plan(discovery, live_plan, nb=active_nb)
    finally:
        v3._apply_reclassifications = previous


def audit(discovery, original_plan, nb=None):
    return v3.audit(discovery, original_plan, nb=nb or NetBox())
