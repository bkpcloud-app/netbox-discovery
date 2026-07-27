#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import ipaddress
import json
import os
from collections import Counter, defaultdict

from lib.config import load_config
from modules.hypervisor.config import clean, enabled_sources, load_hypervisor_config, public_source
from modules.hypervisor.collectors import collect_source
from modules.hypervisor import engine as base
from modules.hypervisor import engine_v2 as v2
from modules.hypervisor.resolver import context_key, resolve_host, resolve_vm

ENGINE_VERSION = "3.0-product"
REPORTS = base.REPORTS
NetBox = v2.NetBox


def utc_now():
    return base.utc_now()


def _network_objects(values):
    rows = []
    for value in values or []:
        try:
            rows.append(ipaddress.ip_network(clean(value), strict=False))
        except Exception:
            pass
    return rows


def _default_context(cfg):
    return {
        "tenant_group": clean(cfg.get("tenant_group")),
        "tenant": clean(cfg.get("tenant")),
        "site": clean((cfg.get("discovery") or {}).get("site")),
        "network": "",
    }


def _mapping_networks(source):
    return _network_objects([x.get("network") for x in (source.get("mappings") or [])])


def _normalize_record(row, networks):
    item = dict(row)
    item["interfaces"] = base.normalize_interfaces(item.get("interfaces"), networks)
    return item


def _context_networks(source, ctx, default_networks):
    mode = clean(source.get("inventory_mode") or "single_site").lower()
    if mode == "single_site":
        return [str(x) for x in default_networks]
    values = []
    for mapping in source.get("mappings") or []:
        tenant = clean(mapping.get("tenant")) or clean(ctx.get("tenant"))
        site = clean(mapping.get("site"))
        if tenant == clean(ctx.get("tenant")) and site == clean(ctx.get("site")):
            network = clean(mapping.get("network"))
            if network and network not in values:
                values.append(network)
    return values


def _bucket_source(raw, source, cfg, default_networks):
    mode = clean(source.get("inventory_mode") or "single_site").lower()
    default = _default_context(cfg)
    normalize_networks = default_networks if mode == "single_site" else _mapping_networks(source)

    if mode == "single_site":
        # Preserve the old scope behaviour for upgraded sources. Newly configured
        # 1.10 single-site sources use scope=all explicitly.
        scoped = base.scope_inventory(raw, source, default_networks)
        hosts = scoped.get("hosts") or []
        vms = scoped.get("vms") or []
    else:
        hosts = [_normalize_record(x, normalize_networks) for x in (raw.get("hosts") or [])]
        vms = [_normalize_record(x, normalize_networks) for x in (raw.get("vms") or [])]

    buckets = defaultdict(lambda: {"hosts": [], "vms": [], "clusters": []})
    contexts = {}
    host_contexts = {}
    unresolved = []

    for host in hosts:
        ctx = resolve_host(host, source, default["tenant"], default["site"], default["tenant_group"])
        if not ctx:
            unresolved.append({
                "object_type": "HOST", "source_id": source.get("id"),
                "desired_name": clean(host.get("name")), "serial": base.host_identity_serial(host),
                "reason": "rede de gerenciamento do host sem mapeamento Tenant/Site",
            })
            continue
        key = context_key(ctx)
        contexts[key] = ctx
        host_contexts[(clean(source.get("id")).casefold(), clean(host.get("name")).casefold())] = ctx
        buckets[key]["hosts"].append(host)

    for vm in vms:
        ctx = resolve_vm(vm, source, host_contexts, default["tenant"], default["site"], default["tenant_group"])
        if not ctx:
            unresolved.append({
                "object_type": "VM", "source_id": source.get("id"),
                "desired_name": clean(vm.get("name")), "serial": clean(vm.get("serial") or vm.get("uuid")),
                "reason": "VM sem host/rede resolvidos para Tenant/Site",
            })
            continue
        key = context_key(ctx)
        contexts[key] = ctx
        buckets[key]["vms"].append(vm)

    raw_clusters = raw.get("clusters") or []
    for key, bucket in buckets.items():
        wanted = set(base.norm(x.get("cluster")) for x in bucket["hosts"] + bucket["vms"] if clean(x.get("cluster")))
        bucket["clusters"] = [dict(x) for x in raw_clusters if base.norm(x.get("name")) in wanted]

    out = {}
    for key, bucket in buckets.items():
        ctx = contexts[key]
        out[key] = {
            "context": ctx,
            "networks": _context_networks(source, ctx, default_networks),
            "result": {
                "stage": "HYPERVISOR_DISCOVERY", "provider": raw.get("provider"),
                "source_id": source.get("id"), "endpoint": raw.get("endpoint"),
                "manager": raw.get("manager") or {}, "scope_mode": mode,
                "hosts": bucket["hosts"], "vms": bucket["vms"], "clusters": bucket["clusters"],
                "errors": [], "netbox_write": False,
            },
        }
    return out, unresolved


def _duplicate_identities(contexts):
    identity = defaultdict(list)
    for ctx in contexts:
        for result in ctx.get("results") or []:
            for host in result.get("hosts") or []:
                key = base.norm_serial(base.host_identity_serial(host))
                if key:
                    identity[("HOST", key)].append((result.get("source_id"), host.get("name"), ctx.get("tenant"), ctx.get("site")))
            for vm in result.get("vms") or []:
                key = base.norm_serial(vm.get("serial")) or base.norm(vm.get("uuid"))
                if key:
                    identity[("VM", key)].append((result.get("source_id"), vm.get("name"), ctx.get("tenant"), ctx.get("site")))
    duplicates = []
    for (kind, key), refs in identity.items():
        unique = set(tuple(clean(x) for x in ref) for ref in refs)
        if len(unique) > 1:
            duplicates.append({"kind": kind, "identity": key, "refs": list(sorted(unique))})
    return duplicates


def collect_all():
    cfg = load_config()
    hv_cfg = load_hypervisor_config(required=True)
    default_networks = base.load_site_networks(cfg)
    sources = enabled_sources(hv_cfg)
    if not sources:
        raise RuntimeError("Nenhum hypervisor habilitado. Execute: netbox-discovery hypervisor configure")

    grouped = defaultdict(lambda: {"context": None, "networks": [], "results": []})
    unresolved = []
    errors = []
    print("===== HYPERVISOR DISCOVER V3 =====")
    print("Sources habilitados: {0}".format(len(sources)))
    print("Resolver: Tenant/Site por source + rede de gerenciamento do host")
    print("NetBox write: NÃO")

    for pos, source in enumerate(sources, 1):
        label = "{0} ({1}, {2})".format(source.get("id"), source.get("type"), source.get("inventory_mode", "single_site"))
        print("[{0}/{1}] Coletando {2}...".format(pos, len(sources), label))
        try:
            raw = collect_source(source)
            buckets, missing = _bucket_source(raw, source, cfg, default_networks)
            unresolved.extend(missing)
            for key, data in buckets.items():
                grouped[key]["context"] = data["context"]
                for network in data.get("networks") or []:
                    if network not in grouped[key]["networks"]:
                        grouped[key]["networks"].append(network)
                grouped[key]["results"].append(data["result"])
            mapped_hosts = sum(len(x["result"].get("hosts") or []) for x in buckets.values())
            mapped_vms = sum(len(x["result"].get("vms") or []) for x in buckets.values())
            print("  OK: hosts mapeados {0}/{1} | VMs mapeadas {2}/{3} | não resolvidos {4}".format(
                mapped_hosts, len(raw.get("hosts") or []), mapped_vms, len(raw.get("vms") or []), len(missing)
            ))
        except Exception as exc:
            errors.append({"source_id": source.get("id"), "error": str(exc)})
            print("  ERRO: {0}".format(exc))

    if errors:
        raise RuntimeError("Falha em {0} source(s) de hypervisor; nenhuma escrita foi iniciada".format(len(errors)))

    contexts = []
    for key in sorted(grouped):
        data = grouped[key]
        ctx = data["context"]
        contexts.append({
            "stage": "HYPERVISOR_DISCOVERY_CONTEXT",
            "engine_version": ENGINE_VERSION,
            "generated_at": utc_now(),
            "tenant_group": clean(ctx.get("tenant_group")),
            "tenant": clean(ctx.get("tenant")),
            "site": clean(ctx.get("site")),
            "networks": list(data.get("networks") or []),
            "results": data.get("results") or [],
            "duplicate_identities": [],
            "netbox_write": False,
        })
    duplicates = _duplicate_identities(contexts)
    for ctx in contexts:
        ctx["duplicate_identities"] = duplicates

    out = {
        "stage": "HYPERVISOR_DISCOVERY_MULTI_CONTEXT",
        "engine_version": ENGINE_VERSION,
        "generated_at": utc_now(),
        "tenant": clean(cfg.get("tenant")),
        "site": clean((cfg.get("discovery") or {}).get("site")),
        "sources": [public_source(x) for x in sources],
        "contexts": contexts,
        "unresolved": unresolved,
        "duplicate_identities": duplicates,
        "netbox_write": False,
    }
    base.ensure_reports_dir()
    path = os.path.join(REPORTS, "MULTI-hypervisor-discovery-{0}.json".format(base.utc_stamp()))
    with open(path, "w") as handle:
        json.dump(out, handle, indent=2, sort_keys=True)

    print("HYPERVISOR CONTEXTOS RESOLVIDOS: {0}".format(len(contexts)))
    for ctx in contexts:
        hosts, vms, clusters = base.flatten_discovery(ctx)
        print("  {0}/{1}: hosts={2} VMs={3} clusters={4} redes={5}".format(
            ctx.get("tenant"), ctx.get("site"), len(hosts), len(vms), len(clusters), len(ctx.get("networks") or [])
        ))
    print("NÃO RESOLVIDOS: {0}".format(len(unresolved)))
    print("JSON: {0}".format(path))
    return out, path


def _annotate_context(plan, ctx):
    for row in plan.get("records") or []:
        row["target_tenant_group"] = clean(ctx.get("tenant_group"))
        row["target_tenant"] = clean(ctx.get("tenant"))
        row["target_site"] = clean(ctx.get("site"))
        row["context_key"] = "{0}/{1}".format(row["target_tenant"], row["target_site"])
    return plan


def _global_identity_guard(plan, nb):
    devices = base.query(nb, "dcim/devices/", limit=20000)
    vms = base.query(nb, "virtualization/virtual-machines/", limit=20000)
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

    for row in plan.get("records") or []:
        if row.get("decision") != "READY" or row.get("action") != "CREATE":
            continue
        serial = base.norm_serial(row.get("serial"))
        if not serial:
            continue
        hits = device_serials.get(serial, []) if row.get("object_type") == "HOST" else vm_serials.get(serial, []) if row.get("object_type") == "VM" else []
        if hits:
            obj = hits[0]
            row["decision"] = "REVIEW"
            row["reason"] = "identidade já existe no NetBox fora do contexto alvo (ID={0}, nome={1}); requer reclassificação/migração, não duplicar".format(obj.get("id"), clean(obj.get("name")))
    return plan


def _recount(plan):
    records = plan.get("records") or []
    plan["decision_summary"] = dict(Counter(x.get("decision") for x in records))
    plan["action_summary"] = dict(Counter(x.get("action") for x in records))
    plan["ready_action_summary"] = dict(Counter(x.get("action") for x in records if x.get("decision") == "READY"))
    return plan


def build_plan(discovery, nb=None):
    nb = nb or NetBox()
    records = []
    context_paths = []
    for ctx in discovery.get("contexts") or []:
        print("===== CONTEXTO {0}/{1} =====".format(ctx.get("tenant"), ctx.get("site")))
        try:
            subplan, path = v2.build_plan(ctx, nb=nb)
            _annotate_context(subplan, ctx)
            records.extend(subplan.get("records") or [])
            context_paths.append(path)
        except Exception as exc:
            hosts, vms, _ = base.flatten_discovery(ctx)
            for item, object_type in [(x, "HOST") for x in hosts] + [(x, "VM") for x in vms]:
                records.append({
                    "object_type": object_type,
                    "asset_id": "CTXERR:{0}:{1}:{2}".format(ctx.get("tenant"), ctx.get("site"), clean(item.get("name"))),
                    "desired_name": clean(item.get("name")), "serial": clean(item.get("serial") or item.get("uuid")),
                    "decision": "REVIEW", "action": "NOOP",
                    "reason": "contexto Tenant/Site indisponível no NetBox: {0}".format(exc),
                    "target_tenant_group": clean(ctx.get("tenant_group")), "target_tenant": clean(ctx.get("tenant")), "target_site": clean(ctx.get("site")),
                    "context_key": "{0}/{1}".format(ctx.get("tenant"), ctx.get("site")),
                })

    for item in discovery.get("unresolved") or []:
        records.append({
            "object_type": item.get("object_type"),
            "asset_id": "UNRESOLVED:{0}:{1}:{2}".format(item.get("source_id"), item.get("object_type"), item.get("serial") or item.get("desired_name")),
            "source_id": item.get("source_id"), "desired_name": item.get("desired_name"), "serial": item.get("serial"),
            "decision": "REVIEW", "action": "NOOP", "reason": item.get("reason"),
            "target_tenant": "", "target_site": "", "context_key": "UNRESOLVED",
        })

    plan = {
        "stage": "HYPERVISOR_PLAN_MULTI_CONTEXT", "engine_version": ENGINE_VERSION,
        "generated_at": utc_now(), "records": records, "context_plans": context_paths,
        "netbox_write": False,
    }
    _global_identity_guard(plan, nb)
    _recount(plan)
    base.ensure_reports_dir()
    path = os.path.join(REPORTS, "MULTI-hypervisor-plan-{0}.json".format(base.utc_stamp()))
    with open(path, "w") as handle:
        json.dump(plan, handle, indent=2, sort_keys=True)

    decisions = plan["decision_summary"]
    actions = plan["action_summary"]
    ready_actions = plan["ready_action_summary"]
    print("===== HYPERVISOR PLAN MULTI-CONTEXT =====")
    print("Objetos planejados: {0}".format(len(records)))
    print("READY: {0} REVIEW: {1} BLOCKED: {2}".format(decisions.get("READY", 0), decisions.get("REVIEW", 0), decisions.get("BLOCKED", 0)))
    print("Ações totais: CREATE={0} UPDATE_SAFE={1} NOOP={2}".format(actions.get("CREATE", 0), actions.get("UPDATE_SAFE", 0), actions.get("NOOP", 0)))
    print("ELEGÍVEIS PARA ESCRITA (READY): {0}".format(decisions.get("READY", 0)))
    print("  READY/CREATE: {0}".format(ready_actions.get("CREATE", 0)))
    print("  READY/UPDATE_SAFE: {0}".format(ready_actions.get("UPDATE_SAFE", 0)))
    print("  READY/NOOP: {0}".format(ready_actions.get("NOOP", 0)))
    print("NetBox write: NÃO")
    print("JSON: {0}".format(path))
    return plan, path


def _context_plan(combined_plan, ctx):
    key = "{0}/{1}".format(clean(ctx.get("tenant")), clean(ctx.get("site")))
    rows = [x for x in combined_plan.get("records") or [] if x.get("context_key") == key]
    return {"stage": "HYPERVISOR_PLAN", "records": rows, "netbox_write": False}


def apply_plan(discovery, plan, nb=None):
    nb = nb or NetBox()
    paths = []
    print("===== HYPERVISOR IMPORT MULTI-CONTEXT =====")
    for ctx in discovery.get("contexts") or []:
        subplan = _context_plan(plan, ctx)
        ready = [x for x in subplan["records"] if x.get("decision") == "READY"]
        if not ready:
            print("{0}/{1}: sem objetos READY".format(ctx.get("tenant"), ctx.get("site")))
            continue
        print("===== APPLY {0}/{1} | READY={2} =====".format(ctx.get("tenant"), ctx.get("site"), len(ready)))
        paths.append(v2.apply_plan(ctx, subplan, nb=nb))
    base.ensure_reports_dir()
    path = os.path.join(REPORTS, "MULTI-hypervisor-import-{0}.json".format(base.utc_stamp()))
    with open(path, "w") as handle:
        json.dump({
            "stage": "HYPERVISOR_IMPORT_MULTI_CONTEXT", "engine_version": ENGINE_VERSION,
            "generated_at": utc_now(), "context_imports": paths, "netbox_write": bool(paths),
        }, handle, indent=2, sort_keys=True)
    print("HYPERVISOR IMPORT MULTI-CONTEXT: contextos escritos={0}".format(len(paths)))
    print("JSON: {0}".format(path))
    return path


def audit(discovery, original_plan, nb=None):
    nb = nb or NetBox()
    rows = []
    worst = "PASS"
    for ctx in discovery.get("contexts") or []:
        subplan = _context_plan(original_plan, ctx)
        if not [x for x in subplan["records"] if x.get("decision") == "READY"]:
            continue
        status, path = v2.audit(ctx, subplan, nb=nb)
        rows.append({"tenant": ctx.get("tenant"), "site": ctx.get("site"), "status": status, "audit": path})
        if status == "FAIL":
            worst = "FAIL"
        elif status == "WARN" and worst != "FAIL":
            worst = "WARN"
    base.ensure_reports_dir()
    path = os.path.join(REPORTS, "MULTI-hypervisor-audit-{0}.json".format(base.utc_stamp()))
    with open(path, "w") as handle:
        json.dump({
            "stage": "HYPERVISOR_AUDIT_MULTI_CONTEXT", "engine_version": ENGINE_VERSION,
            "generated_at": utc_now(), "status": worst, "contexts": rows, "netbox_write": False,
        }, handle, indent=2, sort_keys=True)
    print("===== HYPERVISOR AUDIT MULTI-CONTEXT =====")
    print("Status: {0}".format(worst))
    print("Contextos auditados: {0}".format(len(rows)))
    print("JSON: {0}".format(path))
    return worst, path
