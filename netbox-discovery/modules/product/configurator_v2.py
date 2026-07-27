#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import re
import subprocess
import sys
import unicodedata
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("NETBOX_DISCOVERY_BASE", os.path.abspath(os.path.join(HERE, "..", "..")))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
if BASE not in sys.path:
    sys.path.insert(0, BASE)

import configurator as base

ORIG_WRITE_CONFIG = base.write_config

# Relações de tenancy explicitamente conhecidas do produto. Não há fallback
# genérico para grupo: tenants não mapeados são criados sem Tenant Group.
KNOWN_TENANT_GROUPS = {
    "MIZU": "POLIMIX",
}


def clean(value):
    return "" if value is None else str(value).strip()


def slugify(value):
    text = unicodedata.normalize("NFKD", clean(value)).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    if not text:
        raise RuntimeError("não foi possível gerar slug para: {0}".format(value))
    return text[:100]


def sync_scheduler(enabled, schedule):
    if os.geteuid() != 0:
        raise RuntimeError("configuração do scheduler exige root")
    unit = "netbox-discovery.timer"
    dropin = "/etc/systemd/system/netbox-discovery.timer.d"
    if enabled:
        if not os.path.isdir(dropin):
            os.makedirs(dropin)
        with open(os.path.join(dropin, "schedule.conf"), "w") as handle:
            handle.write("[Timer]\nOnCalendar=\nOnCalendar={0}\n".format(schedule or "daily"))
        subprocess.check_call(["systemctl", "daemon-reload"])
        subprocess.check_call(["systemctl", "enable", "--now", unit])
    else:
        subprocess.call(["systemctl", "disable", "--now", unit])


def write_config(values):
    ORIG_WRITE_CONFIG(values)
    sync_scheduler(bool(values.get("automation_enabled")), values.get("schedule") or "daily")


def _query_name(nb, endpoint, name):
    response = nb.get(endpoint + "?name=" + urllib.parse.quote(name) + "&limit=100")
    rows = response.get("results", []) if isinstance(response, dict) else []
    exact = [row for row in rows if clean(row.get("name")).casefold() == clean(name).casefold()]
    if len(exact) > 1:
        raise RuntimeError("mais de um objeto NetBox com o mesmo nome: {0}".format(name))
    return exact[0] if exact else None


def _related_id(value):
    if isinstance(value, dict):
        return value.get("id")
    return value


def _tenant_group_for(tenant, cfg):
    configured = clean(cfg.get("tenant_group"))
    env_group = clean(os.environ.get("NETBOX_DISCOVERY_TENANT_GROUP"))
    if env_group:
        return env_group
    if configured:
        return configured
    return KNOWN_TENANT_GROUPS.get(clean(tenant).upper(), "")


def _persist_tenant_group(group_name):
    if not group_name or not os.path.isfile(base.CONFIG_FILE):
        return
    rows = open(base.CONFIG_FILE, "r").read().splitlines()
    found = False
    out = []
    inserted = False
    for row in rows:
        if row.startswith("tenant_group:"):
            out.append("tenant_group: {0}".format(group_name))
            found = True
            continue
        out.append(row)
        if not inserted and row.startswith("tenant:"):
            out.append("tenant_group: {0}".format(group_name))
            inserted = True
    if not found and not inserted:
        out.append("tenant_group: {0}".format(group_name))
    temp = base.CONFIG_FILE + ".tmp"
    with open(temp, "w") as handle:
        handle.write("\n".join(out) + "\n")
    os.chmod(temp, 0o600)
    os.replace(temp, base.CONFIG_FILE)


def ensure_netbox_structure():
    cfg = base.parse_simple_yaml(base.CONFIG_FILE)
    tenant_name = clean(cfg.get("tenant"))
    site_name = clean((cfg.get("discovery") or {}).get("site"))
    if not tenant_name or not site_name:
        raise RuntimeError("tenant/site ausentes após salvar configuração")

    from lib.netbox import NetBox
    nb = NetBox()
    group_name = _tenant_group_for(tenant_name, cfg)
    group = None

    print("===== ESTRUTURA BASE NETBOX =====")

    if group_name:
        group = _query_name(nb, "tenancy/tenant-groups/", group_name)
        if group is None:
            group = nb.post("tenancy/tenant-groups/", {
                "name": group_name,
                "slug": slugify(group_name),
            })
            print("Tenant Group {0}: CRIADO ID={1}".format(group_name, group.get("id")))
        else:
            print("Tenant Group {0}: OK ID={1}".format(group_name, group.get("id")))
        _persist_tenant_group(group_name)

    tenant = _query_name(nb, "tenancy/tenants/", tenant_name)
    if tenant is None:
        payload = {"name": tenant_name, "slug": slugify(tenant_name)}
        if group:
            payload["group"] = group["id"]
        tenant = nb.post("tenancy/tenants/", payload)
        print("Tenant {0}: CRIADO ID={1}".format(tenant_name, tenant.get("id")))
    else:
        if group:
            current_group = _related_id(tenant.get("group"))
            if current_group is None:
                tenant = nb.patch("tenancy/tenants/{0}/".format(tenant["id"]), {"group": group["id"]})
            elif current_group != group["id"]:
                raise RuntimeError(
                    "CONFLITO: Tenant {0} já pertence ao Tenant Group ID={1}; esperado {2} ID={3}".format(
                        tenant_name, current_group, group_name, group["id"]
                    )
                )
        print("Tenant {0}: OK ID={1}".format(tenant_name, tenant.get("id")))

    site = _query_name(nb, "dcim/sites/", site_name)
    if site is None:
        site = nb.post("dcim/sites/", {
            "name": site_name,
            "slug": slugify(site_name),
            "status": "active",
            "tenant": tenant["id"],
        })
        print("Site {0}: CRIADO ID={1}".format(site_name, site.get("id")))
    else:
        current_tenant = _related_id(site.get("tenant"))
        if current_tenant is None:
            site = nb.patch("dcim/sites/{0}/".format(site["id"]), {"tenant": tenant["id"]})
        elif current_tenant != tenant["id"]:
            raise RuntimeError(
                "CONFLITO: Site {0} já pertence ao Tenant ID={1}; esperado {2} ID={3}".format(
                    site_name, current_tenant, tenant_name, tenant["id"]
                )
            )
        print("Site {0}: OK ID={1}".format(site_name, site.get("id")))

    print("ESTRUTURA BASE: OK")
    return {"group": group, "tenant": tenant, "site": site}


def main(argv=None):
    old = base.write_config
    try:
        base.write_config = write_config
        result = base.main(argv)
        if result != 0:
            return result
        ensure_netbox_structure()
        print("INIT: CONFIG + ESTRUTURA NETBOX PRONTOS")
        return 0
    finally:
        base.write_config = old


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("ERRO: {0}".format(exc), file=sys.stderr)
        sys.exit(1)
