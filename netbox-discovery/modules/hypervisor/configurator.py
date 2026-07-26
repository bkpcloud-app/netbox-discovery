#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import getpass
import os
import subprocess
import sys

BASE = os.environ.get("NETBOX_DISCOVERY_BASE", "/opt/netbox-discovery")
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.hypervisor.collectors import check_source
from modules.hypervisor.config import clean, load_hypervisor_config, save_hypervisor_config, slugify


def ask(prompt, default="", required=False):
    suffix = " [{0}]".format(default) if clean(default) else ""
    while True:
        value = input(prompt + suffix + ": ").strip()
        if not value:
            value = clean(default)
        if value or not required:
            return value
        print("Valor obrigatório.")


def yn(prompt, default=True):
    suffix = " [S/n]: " if default else " [s/N]: "
    value = input(prompt + suffix).strip().lower()
    if not value:
        return default
    return value in ("s", "sim", "y", "yes")


def secret(prompt, current=""):
    label = prompt + (" (ENTER preserva o atual)" if current else "") + ": "
    value = getpass.getpass(label).strip()
    if not value:
        value = current
    if not value:
        raise RuntimeError("Segredo/senha é obrigatório")
    return value


def type_choice(default=""):
    mapping = {"1": "vmware", "2": "proxmox", "3": "hyperv"}
    reverse = dict((v, k) for k, v in mapping.items())
    print("Plataforma:")
    print("  1 - VMware vCenter/ESXi")
    print("  2 - Proxmox VE")
    print("  3 - Microsoft Hyper-V")
    while True:
        value = input("Escolha{0}: ".format(" [{0}]".format(reverse.get(default)) if default else "")).strip()
        if not value and default:
            return default
        if value in mapping:
            return mapping[value]
        print("Opção inválida.")


def default_source_id(stype, endpoint):
    host = clean(endpoint).replace("https://", "").replace("http://", "").split("/")[0]
    return slugify("{0}-{1}".format(stype, host))


def edit_source(current=None):
    current = dict(current or {})
    stype = type_choice(clean(current.get("type")).lower())
    if stype in ("vmware", "hyperv"):
        subprocess.check_call([os.path.join(BASE, "bin", "netbox-discovery"), "hypervisor", "_ensure-deps", stype])
    endpoint = ask("IP/FQDN do hypervisor/manager", current.get("endpoint", ""), True)
    sid = ask("ID da source", current.get("id") or default_source_id(stype, endpoint), True)
    username = ask("Usuário", current.get("username", ""), True)
    source = {
        "id": sid,
        "type": stype,
        "endpoint": endpoint,
        "username": username,
        "secret": current.get("secret", ""),
        "enabled": True,
        "scope_mode": "site_networks" if yn("Limitar hosts/VMs às redes configuradas deste Site?", clean(current.get("scope_mode") or "site_networks") != "all") else "all",
    }

    if stype == "vmware":
        source["port"] = int(ask("Porta VMware", current.get("port", 443), True))
        source["verify_ssl"] = yn("Validar certificado SSL do VMware?", bool(current.get("verify_ssl", False)))
        source["secret"] = secret("Senha VMware", current.get("secret", ""))
    elif stype == "proxmox":
        current_auth = clean(current.get("auth") or "token")
        token_default = current_auth == "token"
        use_token = yn("Usar API Token do Proxmox?", token_default)
        source["auth"] = "token" if use_token else "password"
        source["port"] = int(ask("Porta Proxmox", current.get("port", 8006), True))
        source["verify_ssl"] = yn("Validar certificado SSL do Proxmox?", bool(current.get("verify_ssl", False)))
        if use_token:
            source["token_id"] = ask("Token ID", current.get("token_id", ""), True)
            source["secret"] = secret("Token Secret", current.get("secret", ""))
        else:
            source["secret"] = secret("Senha Proxmox", current.get("secret", ""))
    else:
        scheme_default = clean(current.get("scheme") or "https")
        use_https = yn("Usar WinRM HTTPS?", scheme_default != "http")
        source["scheme"] = "https" if use_https else "http"
        source["port"] = int(ask("Porta WinRM", current.get("port", 5986 if use_https else 5985), True))
        source["transport"] = "ntlm"
        print("Transporte WinRM: NTLM")
        source["verify_ssl"] = yn("Validar certificado SSL do WinRM?", bool(current.get("verify_ssl", False))) if use_https else False
        source["secret"] = secret("Senha Hyper-V", current.get("secret", ""))

    print("\n===== TESTE DA SOURCE =====")
    result = check_source(source)
    print("CONEXÃO: OK")
    print("Produto: {0}".format(result.get("product", "")))
    print("Versão: {0}".format(result.get("version", "")))
    return source


def show_sources(cfg):
    sources = cfg.get("sources") or []
    print("\nSources configuradas: {0}".format(len(sources)))
    for pos, row in enumerate(sources, 1):
        print("  {0}. {1} | {2} | {3} | scope={4} | {5}".format(
            pos,
            row.get("id"),
            row.get("type"),
            row.get("endpoint"),
            row.get("scope_mode", "site_networks"),
            "ENABLED" if row.get("enabled", True) else "DISABLED",
        ))


def choose_existing(cfg):
    sources = cfg.get("sources") or []
    if not sources:
        raise RuntimeError("Nenhuma source configurada")
    show_sources(cfg)
    while True:
        value = input("Número da source: ").strip()
        try:
            idx = int(value) - 1
            if 0 <= idx < len(sources):
                return idx, sources[idx]
        except Exception:
            pass
        print("Opção inválida.")


def configure_automation(cfg):
    auto = cfg.setdefault("automation", {})
    enabled = yn("Habilitar scheduler independente de hypervisor?", bool(auto.get("enabled", False)))
    auto["enabled"] = enabled
    if enabled:
        auto["schedule"] = ask("Agenda systemd OnCalendar", auto.get("schedule") or "daily", True)
        auto["apply"] = yn("Permitir escrita automática (--apply)?", bool(auto.get("apply", False)))
    else:
        auto.setdefault("schedule", "daily")
        auto["apply"] = False
    save_hypervisor_config(cfg)
    print("AUTOMAÇÃO HYPERVISOR: SALVA")
    print("Para ativar/desativar o timer no systemd use:")
    print("  netbox-discovery hypervisor scheduler enable")
    print("  netbox-discovery hypervisor scheduler disable")


def main():
    cfg = load_hypervisor_config(required=False)
    print("===== NETBOX-DISCOVERY HYPERVISOR CONFIGURE =====")
    show_sources(cfg)
    if not cfg.get("sources"):
        print("\nNenhuma source ainda. Vamos cadastrar a primeira.")
        source = edit_source()
        cfg["sources"] = [source]
        save_hypervisor_config(cfg)
        print("SOURCE SALVA: {0}".format(source.get("id")))
        return 0

    print("\nAção:")
    print("  1 - Adicionar source")
    print("  2 - Editar source")
    print("  3 - Remover source")
    print("  4 - Configurar automação")
    print("  5 - Sair")
    action = input("Escolha: ").strip()
    if action == "1":
        source = edit_source()
        if any(clean(x.get("id")).lower() == clean(source.get("id")).lower() for x in cfg.get("sources") or []):
            raise RuntimeError("Source ID já existe: {0}".format(source.get("id")))
        cfg.setdefault("sources", []).append(source)
        save_hypervisor_config(cfg)
        print("SOURCE SALVA: {0}".format(source.get("id")))
    elif action == "2":
        idx, current = choose_existing(cfg)
        source = edit_source(current)
        for pos, item in enumerate(cfg.get("sources") or []):
            if pos != idx and clean(item.get("id")).lower() == clean(source.get("id")).lower():
                raise RuntimeError("Source ID já existe: {0}".format(source.get("id")))
        cfg["sources"][idx] = source
        save_hypervisor_config(cfg)
        print("SOURCE ATUALIZADA: {0}".format(source.get("id")))
    elif action == "3":
        idx, current = choose_existing(cfg)
        if yn("Remover source {0}?".format(current.get("id")), False):
            cfg["sources"].pop(idx)
            save_hypervisor_config(cfg)
            print("SOURCE REMOVIDA")
        else:
            print("Cancelado.")
    elif action == "4":
        configure_automation(cfg)
    elif action == "5" or not action:
        return 0
    else:
        raise RuntimeError("Opção inválida")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("ERRO: {0}".format(exc), file=sys.stderr)
        sys.exit(1)
