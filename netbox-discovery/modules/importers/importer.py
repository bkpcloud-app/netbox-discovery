#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import argparse
import csv
import datetime
import fcntl
import glob
import ipaddress
import json
import os
import re
import subprocess
import sys
import urllib.parse
from collections import Counter, defaultdict

BASE = os.environ.get("NETBOX_DISCOVERY_BASE", "/opt/netbox-discovery")
REPORTS = os.path.join(BASE, "reports")
LOCK_FILE = "/var/lock/netbox-discovery-import.lock"
IMPORTER_VERSION = "4.1-product"
HERE = os.path.dirname(os.path.abspath(__file__))


def clean(v):
    return "" if v is None else str(v).strip()


def norm(v):
    return re.sub(r"\s+", " ", clean(v)).strip().lower()


def norm_serial(v):
    return re.sub(r"[^A-Za-z0-9]", "", clean(v)).upper()


def slugify(v):
    s = clean(v).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:100] or "item"


def norm_ip(v):
    s = clean(v)
    if not s:
        return ""
    try:
        return str(ipaddress.ip_interface(s).ip)
    except Exception:
        try:
            return str(ipaddress.ip_address(s.split("/")[0]))
        except Exception:
            return ""


def latest(pattern):
    files = glob.glob(pattern)
    return max(files, key=os.path.getmtime) if files else ""


def nested_id(v):
    if isinstance(v, dict):
        return v.get("id")
    if isinstance(v, int):
        return v
    return None


def nested_name(v):
    if isinstance(v, dict):
        return clean(v.get("name") or v.get("display") or v.get("model"))
    return clean(v)


def query(nb, endpoint, **params):
    params = dict((k, v) for k, v in params.items() if v is not None and v != "")
    params.setdefault("limit", 1000)
    suffix = urllib.parse.urlencode(params)
    path = endpoint
    if suffix:
        path += ("&" if "?" in path else "?") + suffix
    return nb.get_all(path)


def choose_exact(rows, value, label, name_field="name"):
    found = [x for x in rows if norm(x.get(name_field)) == norm(value)]
    if len(found) == 1:
        return found[0]
    if len(found) > 1:
        raise RuntimeError("{0} duplicado no NetBox: {1}".format(label, value))
    return None


def load_networks(site):
    path = os.path.join(BASE, "config", "sites", site, "networks.conf")
    if not os.path.isfile(path):
        raise RuntimeError("Arquivo de redes não encontrado: {0}".format(path))
    networks = []
    with open(path, "r") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            try:
                networks.append(ipaddress.ip_network(line, strict=False))
            except Exception:
                raise RuntimeError("Rede inválida em {0}: {1}".format(path, line))
    if not networks:
        raise RuntimeError("Nenhuma rede configurada para o site {0}".format(site))
    return networks


def address_for_ip(ip, networks):
    obj = ipaddress.ip_address(ip)
    matches = [n for n in networks if obj in n]
    if len(matches) != 1:
        raise RuntimeError("IP {0} pertence a {1} redes configuradas; esperado exatamente 1".format(ip, len(matches)))
    return "{0}/{1}".format(ip, matches[0].prefixlen)


def get_device_id_from_ip(ipr):
    ao = ipr.get("assigned_object") or {}
    if isinstance(ao, dict):
        dev = ao.get("device") or {}
        if isinstance(dev, dict) and dev.get("id"):
            return dev.get("id")
        if ipr.get("assigned_object_type") == "dcim.device" and ao.get("id"):
            return ao.get("id")
    return None


def assigned_object_id(ipr):
    ao = ipr.get("assigned_object") or {}
    if isinstance(ao, dict) and ao.get("id"):
        return ao.get("id")
    return ipr.get("assigned_object_id")


class Catalog(object):
    def __init__(self, nb, apply_mode, report):
        self.nb = nb
        self.apply_mode = apply_mode
        self.report = report
        self.roles = query(nb, "dcim/device-roles/")
        self.manufacturers = query(nb, "dcim/manufacturers/")
        self.types = query(nb, "dcim/device-types/")
        self.platforms = query(nb, "dcim/platforms/")

    def _report(self, object_type, action, name, object_id=None, detail=""):
        self.report.append({
            "phase": "CATALOG", "object_type": object_type, "action": action,
            "name": name, "object_id": object_id or "", "detail": detail,
        })

    def ensure_role(self, name):
        obj = choose_exact(self.roles, name, "Role")
        if obj:
            return obj
        slug = slugify(name)
        collisions = [x for x in self.roles if norm(x.get("slug")) == norm(slug)]
        if collisions:
            raise RuntimeError("Slug de Role em uso: {0}".format(slug))
        if not self.apply_mode:
            self._report("DEVICE_ROLE", "WOULD_CREATE", name, detail=slug)
            return {"id": "PLANNED:ROLE:" + slug, "name": name, "slug": slug, "_planned": True}
        obj = self.nb.post("dcim/device-roles/", {
            "name": name, "slug": slug, "color": "607d8b", "vm_role": False,
        })
        self.roles.append(obj)
        self._report("DEVICE_ROLE", "CREATED", name, obj.get("id"), slug)
        return obj

    def ensure_manufacturer(self, name):
        obj = choose_exact(self.manufacturers, name, "Manufacturer")
        if obj:
            return obj
        slug = slugify(name)
        collisions = [x for x in self.manufacturers if norm(x.get("slug")) == norm(slug)]
        if collisions:
            raise RuntimeError("Slug de Manufacturer em uso: {0}".format(slug))
        if not self.apply_mode:
            self._report("MANUFACTURER", "WOULD_CREATE", name, detail=slug)
            return {"id": "PLANNED:MANUFACTURER:" + slug, "name": name, "slug": slug, "_planned": True}
        obj = self.nb.post("dcim/manufacturers/", {"name": name, "slug": slug})
        self.manufacturers.append(obj)
        self._report("MANUFACTURER", "CREATED", name, obj.get("id"), slug)
        return obj

    def ensure_platform(self, name):
        if not clean(name):
            return None
        obj = choose_exact(self.platforms, name, "Platform")
        if obj:
            return obj
        slug = slugify(name)
        collisions = [x for x in self.platforms if norm(x.get("slug")) == norm(slug)]
        if collisions:
            raise RuntimeError("Slug de Platform em uso: {0}".format(slug))
        if not self.apply_mode:
            self._report("PLATFORM", "WOULD_CREATE", name, detail=slug)
            return {"id": "PLANNED:PLATFORM:" + slug, "name": name, "slug": slug, "_planned": True}
        obj = self.nb.post("dcim/platforms/", {"name": name, "slug": slug})
        self.platforms.append(obj)
        self._report("PLATFORM", "CREATED", name, obj.get("id"), slug)
        return obj

    def ensure_device_type(self, manufacturer_name, model):
        manufacturer = self.ensure_manufacturer(manufacturer_name)
        for x in self.types:
            raw_m = x.get("manufacturer")
            m = nested_name(raw_m)
            if isinstance(raw_m, int):
                found_m = [z for z in self.manufacturers if z.get("id") == raw_m]
                m = clean(found_m[0].get("name")) if found_m else clean(raw_m)
            if norm(m) == norm(manufacturer_name) and norm(x.get("model")) == norm(model):
                return x
        slug_base = slugify(manufacturer_name + "-" + model)
        slug = slug_base
        taken = dict((norm(x.get("slug")), x) for x in self.types if clean(x.get("slug")))
        if norm(slug) in taken:
            collision = taken[norm(slug)]
            raw_cm = collision.get("manufacturer")
            collision_m = nested_name(raw_cm)
            if isinstance(raw_cm, int):
                found_cm = [z for z in self.manufacturers if z.get("id") == raw_cm]
                collision_m = clean(found_cm[0].get("name")) if found_cm else clean(raw_cm)
            raise RuntimeError("Slug de Device Type em uso por {0}: {1}".format(collision_m, slug))
        if not self.apply_mode:
            self._report("DEVICE_TYPE", "WOULD_CREATE", model, detail=manufacturer_name + " / " + slug)
            return {"id": "PLANNED:TYPE:" + slug, "model": model, "slug": slug, "manufacturer": manufacturer, "_planned": True}
        if not manufacturer.get("id"):
            raise RuntimeError("Manufacturer sem ID para Device Type: {0}".format(manufacturer_name))
        obj = self.nb.post("dcim/device-types/", {
            "manufacturer": manufacturer["id"], "model": model, "slug": slug,
            "u_height": 0, "is_full_depth": False,
        })
        self.types.append(obj)
        self._report("DEVICE_TYPE", "CREATED", model, obj.get("id"), manufacturer_name + " / " + slug)
        return obj


def live_state(nb, tenant_name, site_name):
    tenant = choose_exact(query(nb, "tenancy/tenants/", name=tenant_name), tenant_name, "Tenant")
    site = choose_exact(query(nb, "dcim/sites/", name=site_name), site_name, "Site")
    if not tenant:
        raise RuntimeError("Tenant não encontrado: {0}".format(tenant_name))
    if not site:
        raise RuntimeError("Site não encontrado: {0}".format(site_name))
    devices = query(nb, "dcim/devices/", tenant_id=tenant["id"], site_id=site["id"])
    # IP uniqueness in NetBox global table is not tenant-scoped. Read the
    # complete global table so an existing unowned/foreign address is reused
    # or blocked instead of being POSTed as a duplicate.
    ips = query(nb, "ipam/ip-addresses/")
    ips = [x for x in ips if not x.get("vrf")]
    return tenant, site, devices, ips


def build_indexes(devices, ips):
    by_id = dict((x.get("id"), x) for x in devices if x.get("id") is not None)
    by_name = defaultdict(list)
    by_serial = defaultdict(list)
    ip_devices = defaultdict(set)
    ip_objects = defaultdict(list)
    for d in devices:
        if clean(d.get("name")):
            by_name[norm(d.get("name"))].append(d)
        if norm_serial(d.get("serial")):
            by_serial[norm_serial(d.get("serial"))].append(d)
        for k in ("primary_ip4", "primary_ip", "oob_ip"):
            v = d.get(k) or {}
            ip = norm_ip(v.get("address") if isinstance(v, dict) else v)
            if ip:
                ip_devices[ip].add(d.get("id"))
    for x in ips:
        ip = norm_ip(x.get("address"))
        if not ip:
            continue
        ip_objects[ip].append(x)
        did = get_device_id_from_ip(x)
        if did:
            ip_devices[ip].add(did)
    return {
        "by_id": by_id, "by_name": by_name, "by_serial": by_serial,
        "ip_devices": ip_devices, "ip_objects": ip_objects,
    }


def rematch_record(row, indexes):
    candidates = set()
    strong = set()
    serial = norm_serial(row.get("serial"))
    if serial:
        ids = set(x.get("id") for x in indexes["by_serial"].get(serial, []))
        candidates.update(ids)
        strong.update(ids)
    for ip in row.get("ips") or []:
        ids = set(indexes["ip_devices"].get(norm_ip(ip), set()))
        candidates.update(ids)
        strong.update(ids)
    name_ids = set(x.get("id") for x in indexes["by_name"].get(norm(row.get("desired_name")), []))
    candidates.update(name_ids)
    if len(strong) > 1:
        return None, "CONFLICT", "serial/IP apontam para devices diferentes"
    if len(strong) == 1:
        did = list(strong)[0]
        if did not in indexes["by_id"]:
            return None, "CONFLICT", "IP aponta para device fora do tenant/site"
        if name_ids and did not in name_ids:
            return None, "CONFLICT", "nome aponta para outro device"
        return indexes["by_id"].get(did), "MATCHED", "strong"
    if len(candidates) == 1:
        did = list(candidates)[0]
        return indexes["by_id"].get(did), "MATCHED", "name"
    if len(candidates) > 1:
        return None, "CONFLICT", "nome ambíguo"
    return None, "NEW", "sem correspondência"


def get_interface(nb, device_id, name):
    if not isinstance(device_id, int):
        return None
    rows = query(nb, "dcim/interfaces/", device_id=device_id)
    exact = [x for x in rows if norm(x.get("name")) == norm(name)]
    if len(exact) > 1:
        raise RuntimeError("Interface duplicada: device {0} / {1}".format(device_id, name))
    return exact[0] if exact else None


def ensure_interface(nb, apply_mode, device, spec, report):
    name = clean(spec.get("name")) or "MGMT"
    current = get_interface(nb, device["id"], name)
    if current:
        report.append({"phase": "INTERFACE", "object_type": "INTERFACE", "action": "PRESERVED", "name": name, "object_id": current.get("id"), "detail": clean(device.get("name"))})
        return current
    if not apply_mode:
        report.append({"phase": "INTERFACE", "object_type": "INTERFACE", "action": "WOULD_CREATE", "name": name, "object_id": "", "detail": clean(device.get("name"))})
        return {"id": "PLANNED:INTERFACE:{0}:{1}".format(device.get("id"), name), "name": name, "device": {"id": device.get("id")}, "_planned": True}
    payload = {
        "device": device["id"], "name": name, "type": "other", "enabled": True,
        "mgmt_only": bool(spec.get("mgmt_only")),
        "description": "Gerenciamento criado pelo netbox-discovery",
    }
    obj = nb.post("dcim/interfaces/", payload)
    report.append({"phase": "INTERFACE", "object_type": "INTERFACE", "action": "CREATED", "name": name, "object_id": obj.get("id"), "detail": clean(device.get("name"))})
    return obj


def ensure_ip(nb, apply_mode, tenant, device, interface, spec, ip_index, networks, report):
    ip = norm_ip(spec.get("ip"))
    if not ip:
        raise RuntimeError("Intent de IP inválido para {0}".format(clean(device.get("name"))))
    objects = ip_index.get(ip, [])
    if len(objects) > 1:
        raise RuntimeError("IP duplicado no NetBox: {0}".format(ip))
    existing = objects[0] if objects else None
    if existing:
        existing_tenant_id = nested_id(existing.get("tenant"))
        if existing_tenant_id and existing_tenant_id != tenant.get("id"):
            raise RuntimeError("IP {0} pertence a outro tenant ID {1}".format(ip, existing_tenant_id))
        assigned_dev = get_device_id_from_ip(existing)
        if assigned_dev and assigned_dev != device.get("id"):
            raise RuntimeError("IP {0} pertence a outro device ID {1}".format(ip, assigned_dev))
        aoid = assigned_object_id(existing)
        if aoid and interface.get("id") and aoid != interface.get("id"):
            raise RuntimeError("IP {0} já está atribuído a outro objeto ID {1}".format(ip, aoid))
        if not aoid:
            if not apply_mode:
                report.append({"phase": "IP", "object_type": "IP_ADDRESS", "action": "WOULD_ASSIGN", "name": ip, "object_id": existing.get("id"), "detail": clean(device.get("name"))})
                return existing
            if not interface.get("id"):
                raise RuntimeError("Interface sem ID para atribuir IP {0}".format(ip))
            payload = {
                "assigned_object_type": "dcim.interface",
                "assigned_object_id": interface["id"],
            }
            if not existing_tenant_id:
                payload["tenant"] = tenant["id"]
            existing = nb.patch("ipam/ip-addresses/{0}/".format(existing["id"]), payload)
            report.append({"phase": "IP", "object_type": "IP_ADDRESS", "action": "ASSIGNED", "name": ip, "object_id": existing.get("id"), "detail": clean(device.get("name"))})
        else:
            report.append({"phase": "IP", "object_type": "IP_ADDRESS", "action": "PRESERVED", "name": ip, "object_id": existing.get("id"), "detail": clean(device.get("name"))})
        return existing

    address = clean(spec.get("address"))
    if not address or "/" not in address:
        address = address_for_ip(ip, networks)
    if not apply_mode:
        report.append({"phase": "IP", "object_type": "IP_ADDRESS", "action": "WOULD_CREATE", "name": address, "object_id": "", "detail": clean(device.get("name"))})
        return {"id": "PLANNED:IP:" + address, "address": address, "_planned": True}
    if not interface.get("id"):
        raise RuntimeError("Interface sem ID para criar IP {0}".format(ip))
    obj = nb.post("ipam/ip-addresses/", {
        "address": address,
        "status": "active",
        "tenant": tenant["id"],
        "assigned_object_type": "dcim.interface",
        "assigned_object_id": interface["id"],
        "description": "Importado pelo netbox-discovery",
    })
    ip_index[ip].append(obj)
    report.append({"phase": "IP", "object_type": "IP_ADDRESS", "action": "CREATED", "name": address, "object_id": obj.get("id"), "detail": clean(device.get("name"))})
    return obj


def preflight_ready(ready, indexes, tenant):
    """Validate every READY asset against the complete live global IP table.

    This runs before the first write. It prevents a late IP conflict from
    leaving a half-applied batch merely because an address was outside the
    target tenant's IP query.
    """
    errors = []
    for row in ready:
        label = clean(row.get("desired_name")) or clean(row.get("asset_id"))
        current, state, reason = rematch_record(row, indexes)
        if state == "CONFLICT":
            errors.append("{0}: {1}".format(label, reason))
            continue
        target_id = current.get("id") if current else None
        for spec in row.get("interfaces") or []:
            ip = norm_ip(spec.get("ip"))
            objects = indexes["ip_objects"].get(ip, [])
            if len(objects) > 1:
                errors.append("{0}: IP duplicado no global table: {1}".format(label, ip))
                continue
            if not objects:
                continue
            obj = objects[0]
            obj_tenant = nested_id(obj.get("tenant"))
            if obj_tenant and obj_tenant != tenant.get("id"):
                errors.append("{0}: IP {1} pertence a outro tenant ID {2}".format(label, ip, obj_tenant))
                continue
            assigned_dev = get_device_id_from_ip(obj)
            assigned_type = clean(obj.get("assigned_object_type"))
            if assigned_dev:
                if not target_id or assigned_dev != target_id:
                    errors.append("{0}: IP {1} pertence ao Device ID {2}".format(label, ip, assigned_dev))
            elif assigned_type:
                errors.append("{0}: IP {1} pertence a objeto {2}".format(label, ip, assigned_type))
    return errors


def safe_patch_for_existing(row, current, catalog):
    payload = {}
    cur_serial = clean(current.get("serial"))
    serial = clean(row.get("serial"))
    if serial and not cur_serial:
        payload["serial"] = serial
    role_name = clean(row.get("target_role"))
    if role_name and not nested_id(current.get("role")):
        role = catalog.ensure_role(role_name)
        if role.get("id"):
            payload["role"] = role["id"]
    platform_name = clean(row.get("platform"))
    if platform_name and not nested_id(current.get("platform")):
        platform = catalog.ensure_platform(platform_name)
        if platform and platform.get("id"):
            payload["platform"] = platform["id"]
    return payload


def create_device(nb, apply_mode, row, tenant, site, catalog, report):
    role = catalog.ensure_role(clean(row.get("target_role")))
    dtype = catalog.ensure_device_type(clean(row.get("manufacturer")), clean(row.get("model")))
    platform = catalog.ensure_platform(clean(row.get("platform"))) if clean(row.get("platform")) else None
    payload = {
        "name": clean(row.get("desired_name")),
        "device_type": dtype.get("id"),
        "role": role.get("id"),
        "tenant": tenant.get("id"),
        "site": site.get("id"),
        "status": "active",
        "description": "Criado pelo netbox-discovery",
    }
    if clean(row.get("serial")):
        payload["serial"] = clean(row.get("serial"))
    if platform and platform.get("id"):
        payload["platform"] = platform.get("id")
    if not apply_mode:
        report.append({"phase": "DEVICE", "object_type": "DEVICE", "action": "WOULD_CREATE", "name": payload["name"], "object_id": "", "detail": clean(row.get("asset_id"))})
        return {"id": "PLANNED:DEVICE:" + payload["name"], "name": payload["name"], "serial": payload.get("serial", ""), "_planned": True}
    missing = [k for k in ("name", "device_type", "role", "tenant", "site") if not payload.get(k)]
    if missing:
        raise RuntimeError("Pré-requisito sem ID para criar {0}: {1}".format(payload["name"], ", ".join(missing)))
    obj = nb.post("dcim/devices/", payload)
    report.append({"phase": "DEVICE", "object_type": "DEVICE", "action": "CREATED", "name": payload["name"], "object_id": obj.get("id"), "detail": clean(row.get("asset_id"))})
    return obj


def refresh_plan():
    planner = os.path.join(BASE, "modules", "inventory", "planner.py")
    if not os.path.isfile(planner):
        raise RuntimeError("Planner não encontrado: {0}".format(planner))
    subprocess.check_call([sys.executable, planner])
    path = latest(os.path.join(REPORTS, "*-plan-*.json"))
    if not path:
        raise RuntimeError("PLAN não gerou JSON")
    return path


def write_reports(site, source_plan, apply_mode, records, errors, summary):
    stamp = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    base = os.path.join(REPORTS, "{0}-import-{1}".format(site, stamp))
    jpath, cpath = base + ".json", base + ".csv"
    out = {
        "stage": "IMPORT", "importer_version": IMPORTER_VERSION,
        "mode": "APPLY" if apply_mode else "DRY-RUN",
        "source_plan": source_plan, "site": site,
        "summary": dict(summary), "errors": errors, "records": records,
        "netbox_write": bool(apply_mode),
    }
    with open(jpath, "w") as f:
        json.dump(out, f, indent=2, sort_keys=True)
    fields = ["phase", "object_type", "action", "name", "object_id", "detail"]
    with open(cpath, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in records:
            w.writerow(dict((k, r.get(k, "")) for k in fields))
    return jpath, cpath


def main(argv=None):
    ap = argparse.ArgumentParser(description="netbox-discovery IMPORT idempotente")
    ap.add_argument("--apply", action="store_true", help="Executa escrita real no NetBox")
    ap.add_argument("--plan", default="", help="PLAN JSON específico")
    ap.add_argument("--no-refresh-plan", action="store_true", help="Não recalcula PLAN antes da execução")
    args = ap.parse_args(argv)

    lock = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        raise RuntimeError("IMPORT já está em execução")
    lock.write(str(os.getpid()))
    lock.flush()

    sys.path.insert(0, BASE)
    from lib.netbox import NetBox

    if args.plan:
        source_plan = args.plan
    elif args.no_refresh_plan:
        source_plan = latest(os.path.join(REPORTS, "*-plan-*.json"))
    else:
        source_plan = refresh_plan()
    if not source_plan or not os.path.isfile(source_plan):
        raise RuntimeError("PLAN JSON não encontrado")

    with open(source_plan, "r") as f:
        plan = json.load(f)
    if clean(plan.get("stage")) != "PLAN":
        raise RuntimeError("Arquivo não é um PLAN válido: {0}".format(source_plan))
    if plan.get("netbox_write") is not False:
        raise RuntimeError("PLAN sem proteção netbox_write=False")

    client = clean(plan.get("client"))
    site_name = clean(plan.get("site"))
    if not client or not site_name:
        raise RuntimeError("PLAN sem client/site")

    records = plan.get("records") or []
    ready = [x for x in records if clean(x.get("decision")) == "READY"]
    skipped_review = len([x for x in records if clean(x.get("decision")) == "REVIEW"])
    skipped_blocked = len([x for x in records if clean(x.get("decision")) == "BLOCKED"])

    print("===== IMPORT =====")
    print("Modo: {0}".format("APPLY - ESCRITA REAL" if args.apply else "DRY-RUN - SEM ESCRITA"))
    print("PLAN: {0}".format(source_plan))
    print("READY: {0}".format(len(ready)))
    print("REVIEW ignorados: {0}".format(skipped_review))
    print("BLOCKED ignorados: {0}".format(skipped_blocked))

    nb = NetBox()
    tenant, site, devices, ips = live_state(nb, client, site_name)
    indexes = build_indexes(devices, ips)
    networks = load_networks(site_name)
    event_rows = []
    errors = []
    summary = Counter()

    if args.apply:
        preflight_errors = preflight_ready(ready, indexes, tenant)
        if preflight_errors:
            print("PREFLIGHT: BLOQUEADO - nenhuma nova escrita foi iniciada")
            for msg in preflight_errors[:20]:
                print(" - {0}".format(msg))
            if len(preflight_errors) > 20:
                print(" - ... +{0} conflito(s)".format(len(preflight_errors) - 20))
            raise RuntimeError("PREFLIGHT encontrou {0} conflito(s) em READY".format(len(preflight_errors)))
        print("PREFLIGHT: OK")

    catalog = Catalog(nb, args.apply, event_rows)

    for pos, row in enumerate(ready, 1):
        label = clean(row.get("desired_name")) or clean(row.get("asset_id"))
        try:
            current, state, reason = rematch_record(row, indexes)
            if state == "CONFLICT":
                summary["runtime_blocked"] += 1
                event_rows.append({"phase": "ASSET", "object_type": "ASSET", "action": "RUNTIME_BLOCKED", "name": label, "object_id": "", "detail": reason})
                continue

            if current is None:
                device = create_device(nb, args.apply, row, tenant, site, catalog, event_rows)
                if args.apply:
                    devices.append(device)
                    indexes = build_indexes(devices, ips)
                    current = device
                else:
                    current = device
                summary["devices_create"] += 1
            else:
                patch = safe_patch_for_existing(row, current, catalog)
                if patch:
                    if args.apply:
                        current = nb.patch("dcim/devices/{0}/".format(current["id"]), patch)
                        indexes["by_id"][current["id"]] = current
                        event_rows.append({"phase": "DEVICE", "object_type": "DEVICE", "action": "UPDATED_SAFE", "name": clean(current.get("name")), "object_id": current.get("id"), "detail": json.dumps(patch, sort_keys=True)})
                    else:
                        event_rows.append({"phase": "DEVICE", "object_type": "DEVICE", "action": "WOULD_UPDATE_SAFE", "name": clean(current.get("name")), "object_id": current.get("id"), "detail": json.dumps(patch, sort_keys=True)})
                    summary["devices_update_safe"] += 1
                else:
                    event_rows.append({"phase": "DEVICE", "object_type": "DEVICE", "action": "PRESERVED", "name": clean(current.get("name")), "object_id": current.get("id") or "", "detail": reason})
                    summary["devices_preserved"] += 1

            if args.apply and not current.get("id"):
                raise RuntimeError("Device sem ID após criação/match: {0}".format(label))

            primary_ip_obj = None
            oob_ip_obj = None
            for spec in row.get("interfaces") or []:
                ip = norm_ip(spec.get("ip"))
                existing_ip_rows = indexes["ip_objects"].get(ip, [])
                if len(existing_ip_rows) > 1:
                    raise RuntimeError("IP duplicado no NetBox: {0}".format(ip))
                existing_ip = existing_ip_rows[0] if existing_ip_rows else None

                # Preserve an existing binding when the IP is already attached to
                # an interface of this same Device. Do not create an extra MGMT
                # interface just to force our preferred interface name.
                if existing_ip and clean(existing_ip.get("assigned_object_type")) == "dcim.interface":
                    assigned_dev = get_device_id_from_ip(existing_ip)
                    if assigned_dev == current.get("id"):
                        interface = existing_ip.get("assigned_object") or {}
                        event_rows.append({
                            "phase": "INTERFACE", "object_type": "INTERFACE",
                            "action": "PRESERVED", "name": clean(interface.get("name")),
                            "object_id": interface.get("id") or "",
                            "detail": clean(current.get("name")),
                        })
                        ip_obj = existing_ip
                        event_rows.append({
                            "phase": "IP", "object_type": "IP_ADDRESS",
                            "action": "PRESERVED", "name": clean(existing_ip.get("address")),
                            "object_id": existing_ip.get("id") or "",
                            "detail": clean(current.get("name")),
                        })
                    else:
                        raise RuntimeError(
                            "IP {0} pertence ao Device ID {1}, não ao Device atual {2}".format(
                                ip, assigned_dev, current.get("id")
                            )
                        )
                elif existing_ip and clean(existing_ip.get("assigned_object_type")):
                    raise RuntimeError(
                        "IP {0} já pertence a objeto {1}; importação física bloqueada".format(
                            ip, clean(existing_ip.get("assigned_object_type"))
                        )
                    )
                else:
                    interface = ensure_interface(nb, args.apply, current, spec, event_rows)
                    ip_obj = ensure_ip(
                        nb, args.apply, tenant, current, interface, spec,
                        indexes["ip_objects"], networks, event_rows
                    )

                if spec.get("primary"):
                    primary_ip_obj = ip_obj
                if clean(spec.get("kind")) == "OOB" or bool(spec.get("mgmt_only")):
                    oob_ip_obj = ip_obj

            if current.get("id") and primary_ip_obj and primary_ip_obj.get("id"):
                cur_primary_id = nested_id(current.get("primary_ip4")) or nested_id(current.get("primary_ip"))
                if not cur_primary_id:
                    if args.apply:
                        current = nb.patch("dcim/devices/{0}/".format(current["id"]), {"primary_ip4": primary_ip_obj["id"]})
                        event_rows.append({"phase": "DEVICE", "object_type": "PRIMARY_IP4", "action": "SET", "name": label, "object_id": primary_ip_obj.get("id"), "detail": norm_ip(primary_ip_obj.get("address"))})
                    else:
                        event_rows.append({"phase": "DEVICE", "object_type": "PRIMARY_IP4", "action": "WOULD_SET", "name": label, "object_id": primary_ip_obj.get("id") or "", "detail": norm_ip(primary_ip_obj.get("address"))})

            if current.get("id") and oob_ip_obj and oob_ip_obj.get("id") and not nested_id(current.get("oob_ip")):
                if args.apply:
                    nb.patch("dcim/devices/{0}/".format(current["id"]), {"oob_ip": oob_ip_obj["id"]})
                    event_rows.append({"phase": "DEVICE", "object_type": "OOB_IP", "action": "SET", "name": label, "object_id": oob_ip_obj.get("id"), "detail": norm_ip(oob_ip_obj.get("address"))})
                else:
                    event_rows.append({"phase": "DEVICE", "object_type": "OOB_IP", "action": "WOULD_SET", "name": label, "object_id": oob_ip_obj.get("id") or "", "detail": norm_ip(oob_ip_obj.get("address"))})

            summary["assets_processed"] += 1
            if pos % 25 == 0 or pos == len(ready):
                print("Processados: {0}/{1}".format(pos, len(ready)))

        except Exception as exc:
            errors.append({"asset_id": clean(row.get("asset_id")), "name": label, "error": str(exc)})
            summary["errors"] += 1
            event_rows.append({"phase": "ASSET", "object_type": "ASSET", "action": "ERROR", "name": label, "object_id": "", "detail": str(exc)})
            # Stop on first error in APPLY to avoid multiplying an unexpected condition.
            if args.apply:
                jpath, cpath = write_reports(site_name, source_plan, args.apply, event_rows, errors, summary)
                print("ERRO em {0}: {1}".format(label, exc))
                print("JSON: {0}".format(jpath))
                print("CSV:  {0}".format(cpath))
                raise

    jpath, cpath = write_reports(site_name, source_plan, args.apply, event_rows, errors, summary)
    print("===== IMPORT RESULTADO =====")
    print("Assets READY processados: {0}".format(summary.get("assets_processed", 0)))
    print("Runtime blocked: {0}".format(summary.get("runtime_blocked", 0)))
    print("Erros: {0}".format(summary.get("errors", 0)))
    print("JSON: {0}".format(jpath))
    print("CSV:  {0}".format(cpath))
    print("NetBox write: {0}".format("SIM" if args.apply else "NÃO"))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
