#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import json
import os
import re
import tempfile

CONFIG_DIR = "/etc/netbox-discovery"
CONFIG_FILE = os.path.join(CONFIG_DIR, "hypervisors.json")
CONFIG_VERSION = 1


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


def validate_source(source):
    if not isinstance(source, dict):
        raise RuntimeError("Source de hypervisor inválido")
    sid = clean(source.get("id"))
    stype = clean(source.get("type")).lower()
    endpoint = clean(source.get("endpoint"))
    if not sid:
        raise RuntimeError("Source sem id")
    if stype not in ("vmware", "proxmox", "hyperv"):
        raise RuntimeError("Tipo de hypervisor inválido em {0}: {1}".format(sid, stype))
    if not endpoint:
        raise RuntimeError("Source {0} sem endpoint".format(sid))
    if not clean(source.get("username")):
        raise RuntimeError("Source {0} sem username".format(sid))
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
