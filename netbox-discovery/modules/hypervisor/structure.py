#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import re
import unicodedata
import urllib.parse

from lib.netbox import NetBox


def clean(value):
    return "" if value is None else str(value).strip()


def slugify(value):
    text = unicodedata.normalize("NFKD", clean(value)).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    if not text:
        raise RuntimeError("não foi possível gerar slug para: {0}".format(value))
    return text[:100]


def related_id(value):
    return value.get("id") if isinstance(value, dict) else value


def query_name(nb, endpoint, name):
    response = nb.get(endpoint + "?name=" + urllib.parse.quote(clean(name)) + "&limit=100")
    rows = response.get("results", []) if isinstance(response, dict) else []
    exact = [row for row in rows if clean(row.get("name")).casefold() == clean(name).casefold()]
    if len(exact) > 1:
        raise RuntimeError("mais de um objeto NetBox com o mesmo nome: {0}".format(name))
    return exact[0] if exact else None


def ensure_structure(tenant, site, tenant_group="", nb=None, verbose=True):
    tenant = clean(tenant)
    site = clean(site)
    tenant_group = clean(tenant_group)
    if not tenant or not site:
        raise RuntimeError("tenant/site obrigatórios para provisionar estrutura")
    nb = nb or NetBox()
    group = None

    if tenant_group:
        group = query_name(nb, "tenancy/tenant-groups/", tenant_group)
        if group is None:
            group = nb.post("tenancy/tenant-groups/", {"name": tenant_group, "slug": slugify(tenant_group)})
            if verbose:
                print("Tenant Group {0}: CRIADO ID={1}".format(tenant_group, group.get("id")))
        elif verbose:
            print("Tenant Group {0}: OK ID={1}".format(tenant_group, group.get("id")))

    tenant_obj = query_name(nb, "tenancy/tenants/", tenant)
    if tenant_obj is None:
        payload = {"name": tenant, "slug": slugify(tenant)}
        if group:
            payload["group"] = group["id"]
        tenant_obj = nb.post("tenancy/tenants/", payload)
        if verbose:
            print("Tenant {0}: CRIADO ID={1}".format(tenant, tenant_obj.get("id")))
    else:
        if group:
            current_group = related_id(tenant_obj.get("group"))
            if current_group is None:
                tenant_obj = nb.patch("tenancy/tenants/{0}/".format(tenant_obj["id"]), {"group": group["id"]})
            elif current_group != group["id"]:
                raise RuntimeError("CONFLITO: Tenant {0} pertence a outro Tenant Group".format(tenant))
        if verbose:
            print("Tenant {0}: OK ID={1}".format(tenant, tenant_obj.get("id")))

    site_obj = query_name(nb, "dcim/sites/", site)
    if site_obj is None:
        site_obj = nb.post("dcim/sites/", {
            "name": site,
            "slug": slugify(site),
            "status": "active",
            "tenant": tenant_obj["id"],
        })
        if verbose:
            print("Site {0}: CRIADO ID={1}".format(site, site_obj.get("id")))
    else:
        current_tenant = related_id(site_obj.get("tenant"))
        if current_tenant is None:
            site_obj = nb.patch("dcim/sites/{0}/".format(site_obj["id"]), {"tenant": tenant_obj["id"]})
        elif current_tenant != tenant_obj["id"]:
            raise RuntimeError("CONFLITO: Site {0} pertence a outro Tenant".format(site))
        if verbose:
            print("Site {0}: OK ID={1}".format(site, site_obj.get("id")))

    return {"group": group, "tenant": tenant_obj, "site": site_obj}
