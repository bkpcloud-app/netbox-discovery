#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import ipaddress
import json
import os
import re
import tempfile

CONFIG_DIR = "/etc/netbox-discovery"
CONFIG_FILE = os.path.join(CONFIG_DIR, "hypervisors.json")
CONFIG_VERSION = 2
INVENTORY_MODES = ("single_site", "multi_site", "multi_tenant")


def clean(value):
    return "" if value is None else str(value).strip()


def slugify(value):
    value = clean(value).lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value[:64] or "hypervisor"


def default_config():
    return {
        "version": CONFIG_VERSION,
        "automation": {
            "enabled": False,
            "apply": False,
            "schedule": "daily",
        },
        "sources": [],
    }


def load_hypervisor_config(path=CONFIG_FILE, required=False):
    if not os.path.isfile(path):
        if required:
            raise RuntimeError(
                "Configuração de hypervisor não encontrada: {0}. "
                "Execute: netbox-discovery hypervisor configure".format(path)
            )
        return default_config()

    st = os.stat(path)
    mode = st.st_mode & 0o777
    if mode & 0o077:
        raise RuntimeError(
            "Permissão insegura em {0}: {1:o}. Esperado 600.".format(path, mode)
        )
    if os.geteuid() == 0 and st.st_uid != 0:
        raise RuntimeError("Proprietário inseguro em {0}: esperado root".format(path))

    with open(path, "r") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        raise RuntimeError("Configuração de hypervisor inválida")

    data.setdefault("version", CONFIG_VERSION)
    data.setdefault("automation", {})
    data["automation"].setdefault("enabled", False)
    data["automation"].setdefault("apply", False)
    data["automation"].setdefault("schedule", "daily")
    data.setdefault("sources", [])

    if not isinstance(data["sources"], list):
        raise RuntimeError("hypervisors.json: sources deve ser uma lista")

    seen = set()
    for source in data["sources"]:
        # Backward compatibility: pre-1.10 sources remain single-site until edited.
        source.setdefault("inventory_mode", "single_site")
        source.setdefault("mappings", [])
        validate_source(source)
        sid = clean(source.get("id")).lower()
        if sid in seen:
            raise RuntimeError("Source ID duplicado: {0}".format(source.get("id")))
        seen.add(sid)

    return data


def save_hypervisor_config(data, path=CONFIG_FILE):
    parent = os.path.dirname(path) or "."
    if not os.path.isdir(parent):
        os.makedirs(parent)
    data = dict(data or {})
    data["version"] = CONFIG_VERSION
    data.setdefault("automation", {})
    data.setdefault("sources", [])

    for source in data["sources"]:
        validate_source(source)

    fd, temp_path = tempfile.mkstemp(prefix="hypervisors-", suffix=".json", dir=parent)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_path, 0o600)
        try:
            os.chown(temp_path, 0, 0)
        except PermissionError:
            pass
        os.replace(temp_path, path)
        os.chmod(path, 0o600)
    except Exception:
        try:
            os.unlink(temp_path)
        except Exception:
            pass
        raise


def _validate_mapping(source, mapping):
    sid = clean(source.get("id"))
    mode = clean(source.get("inventory_mode") or "single_site").lower()
    if not isinstance(mapping, dict):
        raise RuntimeError("Source {0}: mapping inválido".format(sid))
    network = clean(mapping.get("network"))
    try:
        ipaddress.ip_network(network, strict=False)
    except Exception:
        raise RuntimeError("Source {0}: rede de mapping inválida: {1}".format(sid, network))
    if not clean(mapping.get("site")):
        raise RuntimeError("Source {0}: mapping {1} sem Site".format(sid, network))
    if mode == "multi_tenant" and not clean(mapping.get("tenant")):
        raise RuntimeError("Source {0}: mapping {1} sem Tenant".format(sid, network))


def validate_source(source):
    if not isinstance(source, dict):
        raise RuntimeError("Source de hypervisor inválido")
    sid = clean(source.get("id"))
    stype = clean(source.get("type")).lower()
    endpoint = clean(source.get("endpoint"))
    mode = clean(source.get("inventory_mode") or "single_site").lower()
    if not sid:
        raise RuntimeError("Source sem id")
    if stype not in ("vmware", "proxmox", "hyperv"):
        raise RuntimeError("Tipo de hypervisor inválido em {0}: {1}".format(sid, stype))
    if mode not in INVENTORY_MODES:
        raise RuntimeError("Source {0}: inventory_mode inválido: {1}".format(sid, mode))
    if not endpoint:
        raise RuntimeError("Source {0} sem endpoint".format(sid))
    if not clean(source.get("username")):
        raise RuntimeError("Source {0} sem username".format(sid))
    mappings = source.get("mappings") or []
    if not isinstance(mappings, list):
        raise RuntimeError("Source {0}: mappings deve ser lista".format(sid))
    seen_networks = set()
    for mapping in mappings:
        _validate_mapping(source, mapping)
        key = clean(mapping.get("network"))
        if key in seen_networks:
            raise RuntimeError("Source {0}: mapping duplicado para {1}".format(sid, key))
        seen_networks.add(key)
    if mode != "single_site" and not mappings:
        raise RuntimeError("Source {0}: modo {1} exige ao menos um mapping".format(sid, mode))
    if stype == "proxmox":
        auth = clean(source.get("auth") or "token").lower()
        if auth not in ("token", "password"):
            raise RuntimeError("Source {0}: auth Proxmox inválido".format(sid))
        if auth == "token" and not clean(source.get("token_id")):
            raise RuntimeError("Source {0}: token_id obrigatório".format(sid))
    if stype == "hyperv" and clean(source.get("transport") or "ntlm").lower() != "ntlm":
        raise RuntimeError("Source {0}: nesta versão o Hyper-V suporta WinRM/NTLM".format(sid))
    if not clean(source.get("secret")):
        raise RuntimeError("Source {0} sem segredo".format(sid))


def public_source(source):
    out = dict(source or {})
    if "secret" in out:
        out["secret"] = "***"
    return out


def enabled_sources(data):
    return [s for s in (data.get("sources") or []) if bool(s.get("enabled", True))]


def get_source(data, source_id):
    wanted = clean(source_id).lower()
    rows = [s for s in (data.get("sources") or []) if clean(s.get("id")).lower() == wanted]
    if len(rows) == 1:
        return rows[0]
    if not rows:
        raise RuntimeError("Source não encontrado: {0}".format(source_id))
    raise RuntimeError("Source duplicado: {0}".format(source_id))
