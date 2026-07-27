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

ENGINE_VERSION = "3.1-product"
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


def _vm_snapshot(discovery):
    rows = {}
    for ctx in discovery.get("contexts") or []:
        for result in ctx.get("results") or []:
            source_id = clean(result.get("source_id"))
            for vm in result.get("vms") or []:
                serial = base.norm_serial(vm.get("serial")) or base.norm_serial(vm.get("uuid"))
                if serial:
                    key = (source_id.casefold(), "serial", serial)
                else:
                    key = (source_id.casefold(), "name_host", base.norm(vm.get("name")), base.norm(vm.get("host_name")))
                rows[key] = {
                    "object_type": "VM",
                    "source_id": source_id,
                    "desired_name": clean(vm.get("name")),
                    "serial": clean(vm.get("serial") or vm.get("uuid")),
                    "host_name": clean(vm.get("host_name")),
                    "tenant": clean(ctx.get("tenant")),
                    "site": clean(ctx.get("site")),
                }
    return rows


def _inventory_changes(previous, current, previous_path=""):
    before = _vm_snapshot(previous or {})
    after = _vm_snapshot(current or {})
    removed = [before[key] for key in sorted(set(before) - set(after))]
    added = [after[key] for key in sorted(set(after) - set(before))]
    return {
        "previous_report": previous_path,
        "vms_removed": removed,
        "vms_added": added,
        "delete_automatic": False,
    }


def _latest_previous_discovery():
    try:
        names = [name for name in os.listdir(REPORTS) if name.startswith("MULTI-hypervisor-discovery-") and name.endswith(".json")]
    except OSError:
        return "", None
    for name in sorted(names, reverse=True):
        path = os.path.join(REPORTS, name)
        try:
            with open(path, "r") as handle:
                doc = json.load(handle)
            if doc.get("stage") == "HYPERVISOR_DISCOVERY_MULTI_CONTEXT":
                return path, doc
        except Exception:
            continue
    return "", None


def collect_all():
    cfg = load_config()
    hv_cfg = load_hypervisor_config(required=True)
    default_networks = base.load_site_networks(cfg)
    sources = enabled_sources(hv_cfg)
    if not sources:
        raise RuntimeError("Nenhum hypervisor habilitado. Execute: netbox-discovery hypervisor configure")

    previous_path, previous_doc = _latest_previous_discovery()
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
        "inventory_changes": {},
        "netbox_write": False,
    }
    out["inventory_changes"] = _inventory_changes(previous_doc, out, previous_path) if previous_doc else {
        "previous_report": "", "vms_removed": [], "vms_added": [], "delete_automatic": False,
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
    changes = out.get("inventory_changes") or {}
    removed = changes.get("vms_removed") or []
    added = changes.get("vms_added") or []
    if previous_doc:
        print("===== HYPERVISOR INVENTORY CHANGE =====")
        print("VMs adicionadas desde a coleta anterior: {0}".format(len(added)))
        print("VMs ausentes desde a coleta anterior: {0}".format(len(removed)))
        for item in removed:
            print("  REMOVED/REVIEW: {0}/{1} | {2} | source={3}".format(item.get("tenant"), item.get("site"), item.get("desired_name"), item.get("source_id")))
        print("DELETE automático: NÃO")
    print("JSON: {0}".format(path))
    return out, path


def _annotate_context(plan, ctx):
    for row in plan.get("records") or []:
        row["target_tenant_group"] = clean(ctx.get("tenant_group"))
        row["target_tenant"] = clean(ctx.get("tenant"))
        row["target_site"] = clean(ctx.get("site"))
        row["context_key"] = "{0}/{1}".format(row["target_tenant"], row["target_site"])
    return plan


def _target_contexts(plan, nb):
    names = set((clean(row.get("target_tenant")), clean(row.get("target_site"))) for row in plan.get("records") or [] if clean(row.get("target_tenant")) and clean(row.get("target_site")))
    tenants = base.query(nb, "tenancy/tenants/", limit=5000)
    sites = base.query(nb, "dcim/sites/", limit=5000)
    tenant_by_name = defaultdict(list)
    site_by_name = defaultdict(list)
    for obj in tenants:
        tenant_by_name[base.norm(obj.get("name"))].append(obj)
    for obj in sites:
        site_by_name[base.norm(obj.get("name"))].append(obj)
    out = {}
    for tenant_name, site_name in names:
        th = tenant_by_name.get(base.norm(tenant_name), [])
        sh = site_by_name.get(base.norm(site_name), [])
        if len(th) == 1 and len(sh) == 1:
            out[(tenant_name, site_name)] = {"tenant": th[0], "site": sh[0]}
    return out


def _binding_owner_candidates(row, ips, macs, expected_type):
    owners = set()
    for spec in row.get("interfaces") or []:
        ip = base.norm_ip(spec.get("ip"))
        if ip:
            matches = [x for x in ips if base.norm_ip(x.get("address")) == ip]
            if len(matches) == 1 and clean(matches[0].get("assigned_object_type")) == expected_type:
                owner = base.ip_owner_id(matches[0])
                if owner:
                    owners.add(owner)
        mac = base.norm_mac(spec.get("mac"))
        if mac:
            matches = [x for x in macs if base.norm_mac(base.mac_value(x)) == mac]
            if len(matches) == 1 and clean(matches[0].get("assigned_object_type")) == expected_type:
                owner = base.mac_owner_id(matches[0])
                if owner:
                    owners.add(owner)
    return owners


def _strong_global_match(row, objects_by_id, serial_index, ips, macs):
    serial = base.norm_serial(row.get("serial"))
    serial_ids = set(x.get("id") for x in serial_index.get(serial, []) if x.get("id")) if serial else set()
    expected_type = "dcim.interface" if row.get("object_type") == "HOST" else "virtualization.vminterface"
    binding_ids = _binding_owner_candidates(row, ips, macs, expected_type)
    if len(serial_ids) > 1 or len(binding_ids) > 1:
        return None, "identidade global ambígua"
    all_ids = set(serial_ids) | set(binding_ids)
    if len(all_ids) > 1:
        return None, "serial e IP/MAC apontam para objetos globais diferentes"
    if len(all_ids) == 1:
        return objects_by_id.get(list(all_ids)[0]), "serial/IP/MAC global"
    return None, "sem identidade global forte"


def _tenant_id(obj):
    return base.nested_id((obj or {}).get("tenant"))


def _site_id(obj):
    return base.nested_id((obj or {}).get("site"))


def _scope_site_id(obj):
    scope = (obj or {}).get("scope") or {}
    if isinstance(scope, dict):
        return scope.get("id")
    return None


def _related_ip_tenant_mismatch(row, object_id, ips, target_tenant_id):
    expected_type = "dcim.interface" if row.get("object_type") == "HOST" else "virtualization.vminterface"
    for iprow in ips:
        if clean(iprow.get("assigned_object_type")) != expected_type:
            continue
        if base.ip_owner_id(iprow) != object_id:
            continue
        tenant_id = base.nested_id(iprow.get("tenant"))
        if tenant_id and tenant_id != target_tenant_id:
            return True
    return False


def _mark_reclassify(row, obj, target, match_reason):
    row["decision"] = "READY"
    row["action"] = "RECLASSIFY_SAFE"
    row["existing_id"] = obj.get("id")
    row["migration_match"] = match_reason
    row["migration_source_tenant"] = base.nested_name(obj.get("tenant"))
    row["migration_source_site"] = base.nested_name(obj.get("site")) or base.nested_name(obj.get("scope"))
    row["reason"] = "mesma identidade já existe fora do contexto alvo; reclassificação segura para {0}/{1}".format(target["tenant"].get("name"), target["site"].get("name"))


def _plan_reclassifications(plan, nb):
    targets = _target_contexts(plan, nb)
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

    for row in plan.get("records") or []:
        key = (clean(row.get("target_tenant")), clean(row.get("target_site")))
        target = targets.get(key)
        if not target:
            continue
        tenant_id = target["tenant"].get("id")
        site_id = target["site"].get("id")
        kind = row.get("object_type")

        if kind in ("HOST", "VM") and row.get("action") in ("CREATE", "UPDATE_SAFE"):
            obj, match_reason = _strong_global_match(row, device_by_id if kind == "HOST" else vm_by_id, device_serials if kind == "HOST" else vm_serials, ips, macs)
            if not obj:
                if match_reason != "sem identidade global forte":
                    row["decision"] = "REVIEW"
                    row["reason"] = (clean(row.get("reason")) + "; " if clean(row.get("reason")) else "") + match_reason
                continue
            wrong_context = _tenant_id(obj) not in (None, tenant_id)
            if kind == "HOST":
                wrong_context = wrong_context or _site_id(obj) not in (None, site_id)
            elif not base.nested_id(obj.get("cluster")) and not base.nested_id(obj.get("device")):
                wrong_context = wrong_context or _site_id(obj) not in (None, site_id)
            wrong_context = wrong_context or _related_ip_tenant_mismatch(row, obj.get("id"), ips, tenant_id)
            if wrong_context:
                _mark_reclassify(row, obj, target, match_reason)
            continue

        if kind == "CLUSTER" and row.get("action") == "CREATE":
            candidates = [x for x in clusters if base.norm(x.get("name")) == base.norm(row.get("name"))]
            if len(candidates) == 1:
                obj = candidates[0]
                wrong_context = _tenant_id(obj) not in (None, tenant_id) or _scope_site_id(obj) not in (None, site_id)
                if wrong_context:
                    _mark_reclassify(row, obj, target, "nome/tipo de cluster único")
            continue

        if kind == "PREFIX":
            candidates = [x for x in prefixes if clean(x.get("prefix")) == clean(row.get("prefix"))]
            if len(candidates) == 1:
                obj = candidates[0]
                wrong_context = _tenant_id(obj) not in (None, tenant_id) or _scope_site_id(obj) not in (None, site_id)
                if wrong_context and (_tenant_id(obj) is not None or _scope_site_id(obj) is not None or "netbox-discovery" in clean(obj.get("description")).lower()):
                    _mark_reclassify(row, obj, target, "prefixo exato único")
    return plan


def _recount(plan):
    records = plan.get("records") or []
    plan["decision_summary"] = dict(Counter(x.get("decision") for x in records))
    plan["action_summary"] = dict(Counter(x.get("action") for x in records))
    plan["ready_action_summary"] = dict(Counter(x.get("action") for x in records if x.get("decision") == "READY"))
    return plan


def _append_inventory_change_reviews(records, discovery):
    changes = discovery.get("inventory_changes") or {}
    for item in changes.get("vms_removed") or []:
        records.append({
            "object_type": "VM",
            "asset_id": "REMOVED:{0}:{1}:{2}".format(item.get("source_id"), item.get("serial") or item.get("desired_name"), item.get("host_name")),
            "source_id": item.get("source_id"),
            "desired_name": item.get("desired_name"),
            "serial": item.get("serial"),
            "host_name": item.get("host_name"),
            "decision": "REVIEW",
            "action": "NOOP",
            "reason": "VM presente no snapshot anterior e ausente da coleta atual; remoção automática proibida",
            "target_tenant": item.get("tenant"),
            "target_site": item.get("site"),
            "context_key": "{0}/{1}".format(item.get("tenant"), item.get("site")),
            "inventory_change": "REMOVED",
        })
    return records


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

    _append_inventory_change_reviews(records, discovery)
    plan = {
        "stage": "HYPERVISOR_PLAN_MULTI_CONTEXT", "engine_version": ENGINE_VERSION,
        "generated_at": utc_now(), "records": records, "context_plans": context_paths,
        "inventory_changes": discovery.get("inventory_changes") or {},
        "netbox_write": False,
    }
    _plan_reclassifications(plan, nb)
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
    print("Ações totais: CREATE={0} UPDATE_SAFE={1} RECLASSIFY_SAFE={2} NOOP={3}".format(actions.get("CREATE", 0), actions.get("UPDATE_SAFE", 0), actions.get("RECLASSIFY_SAFE", 0), actions.get("NOOP", 0)))
    print("ELEGÍVEIS PARA ESCRITA (READY): {0}".format(decisions.get("READY", 0)))
    print("  READY/CREATE: {0}".format(ready_actions.get("CREATE", 0)))
    print("  READY/UPDATE_SAFE: {0}".format(ready_actions.get("UPDATE_SAFE", 0)))
    print("  READY/RECLASSIFY_SAFE: {0}".format(ready_actions.get("RECLASSIFY_SAFE", 0)))
    print("  READY/NOOP: {0}".format(ready_actions.get("NOOP", 0)))
    print("NetBox write: NÃO")
    print("JSON: {0}".format(path))
    return plan, path


def _context_plan(combined_plan, ctx):
    key = "{0}/{1}".format(clean(ctx.get("tenant")), clean(ctx.get("site")))
    rows = [x for x in combined_plan.get("records") or [] if x.get("context_key") == key]
    return {"stage": "HYPERVISOR_PLAN", "records": rows, "netbox_write": False}


def _target_objects(nb, ctx):
    tenants = base.query(nb, "tenancy/tenants/", name=ctx.get("tenant"), limit=100)
    sites = base.query(nb, "dcim/sites/", name=ctx.get("site"), limit=100)
    tenant = base.choose_exact(tenants, ctx.get("tenant"), "Tenant")
    site = base.choose_exact(sites, ctx.get("site"), "Site")
    if not tenant or not site:
        raise RuntimeError("RECLASSIFY: Tenant/Site alvo não encontrado: {0}/{1}".format(ctx.get("tenant"), ctx.get("site")))
    return tenant, site


def _patch_owned_ip_tenant(nb, object_type, object_id, tenant_id, events):
    expected_type = "dcim.interface" if object_type == "HOST" else "virtualization.vminterface"
    for iprow in base.query(nb, "ipam/ip-addresses/", limit=30000):
        if iprow.get("vrf") or clean(iprow.get("assigned_object_type")) != expected_type:
            continue
        if base.ip_owner_id(iprow) != object_id:
            continue
        current_tenant = base.nested_id(iprow.get("tenant"))
        if current_tenant == tenant_id:
            continue
        obj = nb.patch("ipam/ip-addresses/{0}/".format(iprow["id"]), {"tenant": tenant_id})
        events.append({
            "phase": "RECLASSIFY", "object_type": "IP_ADDRESS", "action": "RECLASSIFIED_SAFE",
            "name": clean(obj.get("address")) if isinstance(obj, dict) else clean(iprow.get("address")),
            "object_id": iprow.get("id"), "detail": "tenant={0}".format(tenant_id),
        })


def _apply_reclassifications(ctx, subplan, nb):
    rows = [x for x in subplan.get("records") or [] if x.get("decision") == "READY" and x.get("action") == "RECLASSIFY_SAFE"]
    if not rows:
        return []
    tenant, site = _target_objects(nb, ctx)
    tenant_id = tenant["id"]
    site_id = site["id"]
    events = []
    order = {"PREFIX": 0, "CLUSTER": 1, "HOST": 2, "VM": 3}
    for row in sorted(rows, key=lambda x: order.get(x.get("object_type"), 9)):
        object_id = row.get("existing_id")
        if not object_id:
            raise RuntimeError("RECLASSIFY sem existing_id: {0}".format(row.get("asset_id")))
        kind = row.get("object_type")
        if kind == "PREFIX":
            endpoint = "ipam/prefixes/{0}/".format(object_id)
            payload = {"tenant": tenant_id, "scope_type": "dcim.site", "scope_id": site_id}
        elif kind == "CLUSTER":
            endpoint = "virtualization/clusters/{0}/".format(object_id)
            payload = {"tenant": tenant_id, "scope_type": "dcim.site", "scope_id": site_id}
        elif kind == "HOST":
            endpoint = "dcim/devices/{0}/".format(object_id)
            payload = {"tenant": tenant_id, "site": site_id}
        elif kind == "VM":
            endpoint = "virtualization/virtual-machines/{0}/".format(object_id)
            payload = {"tenant": tenant_id}
            source = row.get("source") or {}
            if not clean(source.get("cluster")) and not clean(source.get("host_name")):
                payload["site"] = site_id
        else:
            continue
        nb.patch(endpoint, payload)
        events.append({
            "phase": "RECLASSIFY", "object_type": kind, "action": "RECLASSIFIED_SAFE",
            "name": row.get("desired_name") or row.get("name") or row.get("prefix") or row.get("asset_id"),
            "object_id": object_id, "detail": "{0}/{1}".format(ctx.get("tenant"), ctx.get("site")),
        })
        if kind in ("HOST", "VM"):
            _patch_owned_ip_tenant(nb, kind, object_id, tenant_id, events)
    return events


def apply_plan(discovery, plan, nb=None):
    nb = nb or NetBox()
    paths = []
    migration_events = []
    print("===== HYPERVISOR IMPORT MULTI-CONTEXT =====")
    for ctx in discovery.get("contexts") or []:
        subplan = _context_plan(plan, ctx)
        ready = [x for x in subplan["records"] if x.get("decision") == "READY"]
        if not ready:
            print("{0}/{1}: sem objetos READY".format(ctx.get("tenant"), ctx.get("site")))
            continue
        migrations = [x for x in ready if x.get("action") == "RECLASSIFY_SAFE"]
        if migrations:
            print("===== RECLASSIFY {0}/{1} | READY={2} =====".format(ctx.get("tenant"), ctx.get("site"), len(migrations)))
            migration_events.extend(_apply_reclassifications(ctx, subplan, nb))
        print("===== APPLY {0}/{1} | READY={2} =====".format(ctx.get("tenant"), ctx.get("site"), len(ready)))
        paths.append(v2.apply_plan(ctx, subplan, nb=nb))
    base.ensure_reports_dir()
    path = os.path.join(REPORTS, "MULTI-hypervisor-import-{0}.json".format(base.utc_stamp()))
    with open(path, "w") as handle:
        json.dump({
            "stage": "HYPERVISOR_IMPORT_MULTI_CONTEXT", "engine_version": ENGINE_VERSION,
            "generated_at": utc_now(), "context_imports": paths,
            "reclassification_events": migration_events,
            "netbox_write": bool(paths or migration_events),
        }, handle, indent=2, sort_keys=True)
    print("HYPERVISOR IMPORT MULTI-CONTEXT: contextos escritos={0} | reclassificações={1}".format(len(paths), len(migration_events)))
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
