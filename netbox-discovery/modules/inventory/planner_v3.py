#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import sys

from modules.inventory import planner_v2 as v2

PLANNER_VERSION = "4.2-product"
ORIG_NETBOX_STATE = v2.netbox_state
ORIG_BUILD_PLAN = v2.build_plan


def clean(value):
    return "" if value is None else str(value).strip()


def netbox_state(nb, client, site):
    state = ORIG_NETBOX_STATE(nb, client, site)
    tenant = state.get("tenant") or {}
    site_obj = state.get("site") or {}
    vms = []
    try:
        vms = v2.base.query(
            nb, "virtualization/virtual-machines/",
            tenant_id=tenant.get("id"), site_id=site_obj.get("id"), limit=10000,
        )
    except Exception:
        try:
            vms = v2.base.query(nb, "virtualization/virtual-machines/", tenant_id=tenant.get("id"), limit=10000)
            sid = site_obj.get("id")
            if sid:
                filtered = []
                for vm in vms:
                    vm_site = vm.get("site") or {}
                    vm_sid = vm_site.get("id") if isinstance(vm_site, dict) else vm_site
                    if vm_sid == sid:
                        filtered.append(vm)
                vms = filtered
        except Exception:
            vms = []
    state["virtual_machines"] = vms
    return state


def _vm_name_index(state):
    out = {}
    for vm in state.get("virtual_machines") or []:
        name = v2.base.norm(vm.get("name"))
        if name:
            out.setdefault(name, []).append(vm)
    return out


def _candidate_names(asset, row):
    values = []
    for raw in (row.get("desired_name"), asset.get("hostname")):
        value = clean(raw).strip(".")
        if not value:
            continue
        for candidate in (value, value.split(".")[0]):
            normalized = v2.base.norm(candidate)
            if normalized and normalized not in values:
                values.append(normalized)
    return values


def _unique_vm_matches(asset, row, vm_names):
    found = {}
    for name in _candidate_names(asset, row):
        for vm in vm_names.get(name, []):
            if vm.get("id") is not None:
                found[vm.get("id")] = vm
    return list(found.values())


def _append_reason(row, reason):
    reasons = list(row.get("reasons") or [])
    if reason not in reasons:
        reasons.append(reason)
    row["reasons"] = sorted(set(reasons))


def build_plan(recon, classification, state):
    plan, prereq = ORIG_BUILD_PLAN(recon, classification, state)
    assets = dict((clean(x.get("asset_id")), x) for x in (recon.get("records") or []))
    vm_names = _vm_name_index(state)

    for row in plan:
        asset = assets.get(clean(row.get("asset_id"))) or {}

        history_conflict = clean(asset.get("historical_identity_conflict"))
        if history_conflict:
            row["decision"] = "BLOCKED"
            row["action"] = "CONFLICT"
            _append_reason(row, "IDENTITY_HISTORY_CONFLICT:{0}".format(history_conflict))
            continue

        if not v2._looks_like_vm_asset(asset):
            continue

        matches = _unique_vm_matches(asset, row, vm_names)
        existing_device = row.get("existing_device_id")

        if len(matches) == 1:
            vm = matches[0]
            vm_id = vm.get("id")
            if existing_device:
                row["decision"] = "BLOCKED"
                row["action"] = "CONFLICT"
                row["match_state"] = "CROSS_PIPELINE_CONFLICT"
                row["match_reason"] = "Device físico existe, mas identidade VMware corresponde à VM ID {0}".format(vm_id)
                _append_reason(row, "PHYSICAL_DEVICE_CONFLICT_WITH_HYPERVISOR_VM:{0}".format(vm_id))
            else:
                row["suppressed_reasons"] = list(row.get("reasons") or [])
                row["decision"] = "DELEGATED"
                row["action"] = "NOOP"
                row["match_state"] = "EXTERNAL_MANAGED"
                row["match_reason"] = "Identidade VMware + nome único correspondem à VM ID {0}".format(vm_id)
                row["reasons"] = ["OWNED_BY_HYPERVISOR_VM_NAME:{0}".format(vm_id)]
                row["interfaces"] = []
                row["ip_intents"] = []
            continue

        if len(matches) > 1:
            row["decision"] = "REVIEW" if row.get("decision") != "BLOCKED" else row.get("decision")
            _append_reason(row, "HYPERVISOR_VM_NAME_AMBIGUOUS")
            continue

        if existing_device:
            row["decision"] = "BLOCKED"
            row["action"] = "CONFLICT"
            row["match_state"] = "CROSS_PIPELINE_CONFLICT"
            row["match_reason"] = "Device físico existe para asset com identidade VMware sem VM correlacionada"
            _append_reason(row, "PHYSICAL_DEVICE_WITH_VMWARE_IDENTITY_NO_VM_MATCH")
        elif row.get("decision") != "BLOCKED":
            row["decision"] = "REVIEW"
            _append_reason(row, "VIRTUAL_MACHINE_CANDIDATE_NO_VM_MATCH")

    return plan, prereq


def main(argv=None):
    old_state = v2.netbox_state
    old_build = v2.build_plan
    old_version = v2.PLANNER_VERSION
    try:
        v2.netbox_state = netbox_state
        v2.build_plan = build_plan
        v2.PLANNER_VERSION = PLANNER_VERSION
        return v2.main(argv)
    finally:
        v2.netbox_state = old_state
        v2.build_plan = old_build
        v2.PLANNER_VERSION = old_version


if __name__ == "__main__":
    sys.exit(main())
