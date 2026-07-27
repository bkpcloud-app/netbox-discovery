#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import ipaddress
import json

from modules.hypervisor import engine as base

ENGINE_VERSION = "2.2-product"
_ACTIVE_NETWORKS = []
NetBox = base.NetBox
_BASE_BUILD_PLAN = base.build_plan


def _authoritative_ip(iprow, ip):
    if bool(iprow.get("primary")):
        return True
    try:
        obj = ipaddress.ip_address(ip)
    except Exception:
        return False
    return any(obj.version == network.version and obj in network for network in _ACTIVE_NETWORKS)


def desired_ip_specs(item):
    """Return only IPs safe to use as NetBox identity/bindings.

    Discovery keeps every guest IP for audit. The plan intentionally ignores
    secondary IPs outside the Site networks because container/bridge addresses
    are commonly repeated across unrelated VMs. A primary IP is always
    eligible, even when it is outside the Site networks.
    """
    rows = []
    for interface in item.get("interfaces") or []:
        for iprow in interface.get("ips") or []:
            ip = base.valid_ip(iprow.get("address"))
            cidr = base.clean(iprow.get("cidr"))
            if not ip or not cidr:
                continue
            if not _authoritative_ip(iprow, ip):
                continue
            rows.append({
                "name": base.clean(interface.get("name")) or "MGMT",
                "ip": ip,
                "address": cidr,
                "kind": "PRIMARY" if iprow.get("primary") else "SITE",
                "mgmt_only": bool(interface.get("management")),
                "primary": bool(iprow.get("primary")),
                "mac": base.clean(interface.get("mac")),
                "network": base.clean(interface.get("network")),
            })
    return rows


def _pending_fields_for_row(row, state, device_indexes, vm_index):
    if row.get("decision") != "READY" or row.get("action") != "UPDATE_SAFE":
        return []

    pending = []
    if row.get("object_type") == "HOST":
        current, match_state, _ = base.rematch_record(row, device_indexes)
        if current is None or match_state == "CONFLICT":
            return []
        if base.clean(row.get("serial")) and not base.clean(current.get("serial")):
            pending.append("serial")
        if base.clean(row.get("cluster")) and not base.nested_id(current.get("cluster")):
            pending.append("cluster")
        if base.clean(row.get("platform")) and not base.nested_id(current.get("platform")):
            pending.append("platform")
        if base.clean(row.get("target_role")) and not base.nested_id(current.get("role")):
            pending.append("role")
        if base.specs_need_update(row.get("interfaces") or [], state, "dcim.interface", current.get("id")):
            pending.append("interfaces")
        for spec in row.get("interfaces") or []:
            if spec.get("primary"):
                field = "primary_ip6" if ":" in spec.get("ip", "") else "primary_ip4"
                if not base.nested_id(current.get(field)):
                    pending.append(field)

    elif row.get("object_type") == "VM":
        current, match_state, _ = base.match_vm(row, vm_index, state)
        if current is None or match_state == "CONFLICT":
            return []
        patch = base.vm_safe_patch_preview(row, current)
        pending.extend(sorted(patch.keys()))
        if base.specs_need_update(row.get("interfaces") or [], state, "virtualization.vminterface", current.get("id")):
            pending.append("interfaces")
        for spec in row.get("interfaces") or []:
            if spec.get("primary"):
                field = "primary_ip6" if ":" in spec.get("ip", "") else "primary_ip4"
                if not base.nested_id(current.get(field)):
                    pending.append(field)

    out = []
    for value in pending:
        if value and value not in out:
            out.append(value)
    return out


def _annotate_update_safe(plan, discovery, nb):
    rows = plan.get("records") or []
    targets = [x for x in rows if x.get("decision") == "READY" and x.get("action") == "UPDATE_SAFE"]
    if not targets:
        return plan
    try:
        state = base.state_from_netbox(nb, discovery.get("tenant"), discovery.get("site"))
        device_indexes = base.build_indexes(state["devices"], state["ips"])
        vm_index = base.vm_indexes(state)
        for row in targets:
            fields = _pending_fields_for_row(row, state, device_indexes, vm_index)
            row["pending_fields"] = fields
            if fields:
                row["pending_reason"] = "campos pendentes: {0}".format(", ".join(fields))
    except Exception as exc:
        for row in targets:
            row["pending_fields"] = []
            row["pending_reason"] = "diagnóstico de campos indisponível: {0}".format(exc)
    return plan


def build_plan(discovery, nb=None):
    global _ACTIVE_NETWORKS
    previous_networks = _ACTIVE_NETWORKS
    previous_specs = base.desired_ip_specs
    _ACTIVE_NETWORKS = [ipaddress.ip_network(x, strict=False) for x in discovery.get("networks") or []]
    base.desired_ip_specs = desired_ip_specs
    try:
        active_nb = nb or NetBox()
        plan, path = _BASE_BUILD_PLAN(discovery, active_nb)
        plan["engine_version"] = ENGINE_VERSION
        plan["ip_policy"] = "primary_or_site_network"
        _annotate_update_safe(plan, discovery, active_nb)
        with open(path, "w") as handle:
            json.dump(plan, handle, indent=2, sort_keys=True)
        return plan, path
    finally:
        base.desired_ip_specs = previous_specs
        _ACTIVE_NETWORKS = previous_networks


def _call_base_with_v2_planner(func, *args, **kwargs):
    """Force base APPLY/AUDIT preflight to reuse the exact V2 planner policy."""
    previous_build_plan = base.build_plan
    base.build_plan = build_plan
    try:
        return func(*args, **kwargs)
    finally:
        base.build_plan = previous_build_plan


def apply_plan(discovery, plan, nb=None):
    # Use the runner-injected NetBox subclass so every write is journaled.
    active_nb = nb or NetBox()
    return _call_base_with_v2_planner(base.apply_plan, discovery, plan, nb=active_nb)


def audit_detail_lines(audit_path):
    try:
        with open(audit_path, "r") as handle:
            audit_doc = json.load(handle)
    except Exception as exc:
        return ["HYPERVISOR AUDIT DETALHES: indisponível ({0})".format(exc)]

    post_rows = {}
    post_path = audit_doc.get("post_plan") or ""
    if post_path:
        try:
            with open(post_path, "r") as handle:
                post_doc = json.load(handle)
            post_rows = dict((x.get("asset_id"), x) for x in post_doc.get("records") or [] if x.get("asset_id"))
        except Exception:
            post_rows = {}

    bad = [x for x in audit_doc.get("checks") or [] if x.get("status") in ("WARN", "FAIL")]
    if not bad:
        return ["HYPERVISOR AUDIT DETALHES: nenhuma pendência"]

    lines = ["===== HYPERVISOR AUDIT DETALHES ====="]
    for pos, check in enumerate(bad, 1):
        row = post_rows.get(check.get("asset_id")) or {}
        name = row.get("desired_name") or row.get("name") or row.get("prefix") or check.get("asset_id") or "?"
        lines.append("[{0}/{1}] {2} | {3} | {4} | {5}".format(
            pos, len(bad), check.get("status") or "?", row.get("object_type") or "?", name, row.get("action") or "?"
        ))
        detail = row.get("pending_reason") or check.get("detail") or row.get("reason") or "não informado"
        lines.append("  Motivo: {0}".format(detail))
        if row.get("reason") and row.get("reason") != detail:
            lines.append("  Plano: {0}".format(row.get("reason")))
    lines.append("AUDIT PENDÊNCIAS: {0}".format(len(bad)))
    return lines


def audit(discovery, original_plan, nb=None):
    # Audit must evaluate idempotency with the same V2 IP policy used by PLAN/APPLY.
    active_nb = nb or NetBox()
    status, path = _call_base_with_v2_planner(base.audit, discovery, original_plan, nb=active_nb)
    for line in audit_detail_lines(path):
        print(line)
    return status, path


# Public engine surface used by runner.py.
collect_all = base.collect_all
utc_now = base.utc_now
