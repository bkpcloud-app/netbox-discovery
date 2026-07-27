#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import argparse
import getpass
import ipaddress
import os
import sys

BASE = os.environ.get("NETBOX_DISCOVERY_BASE", "/opt/netbox-discovery")
CONFIG_FILE = os.path.join(BASE, "config.yml")
LOCKED_NETBOX_URL = "https://inventory.bkpcloud.app.br:8080"


def clean(v):
    return "" if v is None else str(v).strip()


def parse_simple_yaml(path):
    data = {}
    section = None
    if not os.path.isfile(path):
        return data
    with open(path, "r") as f:
        for raw in f:
            if not raw.strip() or raw.lstrip().startswith("#"):
                continue
            indent = len(raw) - len(raw.lstrip())
            line = raw.strip()
            if indent == 0 and line.endswith(":"):
                section = line[:-1].strip()
                data[section] = {}
                continue
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if v.lower() == "true":
                v = True
            elif v.lower() == "false":
                v = False
            if indent > 0 and section:
                data.setdefault(section, {})[k] = v
            else:
                data[k] = v
                section = None
    return data


def read_lines(path):
    if not os.path.isfile(path):
        return []
    out = []
    with open(path, "r") as f:
        for raw in f:
            line = raw.strip()
            if line and not line.startswith("#"):
                out.append(line)
    return out


def yn(prompt, default=True):
    suffix = " [S/n]: " if default else " [s/N]: "
    ans = input(prompt + suffix).strip().lower()
    if not ans:
        return default
    return ans in ("s", "sim", "y", "yes")


def ask(prompt, default="", required=False):
    suffix = ""
    if default:
        suffix = " [{0}]".format(default)
    while True:
        val = input(prompt + suffix + ": ").strip()
        if not val:
            val = default
        if val or not required:
            return val
        print("Valor obrigatório.")


def validate_network(value):
    return str(ipaddress.ip_network(value, strict=False))


def capture_list(title, validator=None, existing=None, at_least_one=False):
    existing = list(existing or [])
    if existing:
        print("{0} atuais: {1}".format(title, ", ".join(existing)))
        if yn("Manter os valores atuais de {0}?".format(title), True):
            return existing
    values = []
    print("Informe {0}, um por vez. ENTER encerra.".format(title))
    while True:
        val = input("> ").strip()
        if not val:
            if at_least_one and not values:
                print("Informe pelo menos um valor.")
                continue
            break
        try:
            if validator:
                val = validator(val)
            if val not in values:
                values.append(val)
        except Exception as exc:
            print("Inválido: {0}".format(exc))
    return values


def write_lines(path, rows, mode=0o640):
    parent = os.path.dirname(path)
    if not os.path.isdir(parent):
        os.makedirs(parent)
    with open(path, "w") as f:
        for row in rows:
            f.write(clean(row) + "\n")
    os.chmod(path, mode)


def yaml_bool(v):
    return "true" if bool(v) else "false"


def write_config(values):
    site = values["site"]
    site_dir = os.path.join(BASE, "config", "sites", site)
    if not os.path.isdir(site_dir):
        os.makedirs(site_dir)
    network_file = os.path.join(site_dir, "networks.conf")
    exclusions_file = os.path.join(site_dir, "exclusions.conf")
    communities_file = os.path.join(site_dir, "snmp-communities.conf")

    write_lines(network_file, values["networks"])
    write_lines(exclusions_file, values["exclusions"])
    write_lines(communities_file, values["communities"], 0o600)

    text = """netbox:\n  url: {url}\n  token: {token}\n  verify_ssl: {verify_ssl}\n\ntenant: {tenant}\ntenant_group: {tenant_group}\n\ndiscovery:\n  site: {site}\n  networks_file: {network_file}\n  exclusions_file: {exclusions_file}\n  communities_file: {communities_file}\n\npaths:\n  reports: {base}/reports\n  logs: {base}/logs\n  cache: {base}/cache\n  backups: {base}/backups\n\nautomation:\n  enabled: {auto_enabled}\n  apply: {auto_apply}\n  schedule: {schedule}\n""".format(
        url=values["url"].rstrip("/"),
        token=values["token"],
        verify_ssl=yaml_bool(values["verify_ssl"]),
        tenant=values["tenant"],
        tenant_group=clean(values.get("tenant_group")),
        site=site,
        network_file=network_file,
        exclusions_file=exclusions_file,
        communities_file=communities_file,
        base=BASE,
        auto_enabled=yaml_bool(values["automation_enabled"]),
        auto_apply=yaml_bool(values["automation_apply"]),
        schedule=values["schedule"],
    )
    with open(CONFIG_FILE, "w") as f:
        f.write(text)
    os.chmod(CONFIG_FILE, 0o600)


def test_netbox():
    sys.path.insert(0, BASE)
    from lib.netbox import NetBox
    nb = NetBox()
    result = nb.get("status/")
    if not isinstance(result, dict):
        raise RuntimeError("Resposta inesperada da API")
    print("NETBOX: OK")


def current_defaults():
    cfg = parse_simple_yaml(CONFIG_FILE)
    disc = cfg.get("discovery") or {}
    site = clean(disc.get("site"))
    site_dir = os.path.join(BASE, "config", "sites", site) if site else ""
    return {
        "url": LOCKED_NETBOX_URL,
        "token": clean((cfg.get("netbox") or {}).get("token")),
        "verify_ssl": bool((cfg.get("netbox") or {}).get("verify_ssl", True)),
        "tenant": clean(cfg.get("tenant")),
        "tenant_group": clean(cfg.get("tenant_group")),
        "site": site,
        "networks": read_lines(os.path.join(site_dir, "networks.conf")) if site_dir else [],
        "exclusions": read_lines(os.path.join(site_dir, "exclusions.conf")) if site_dir else [],
        "communities": read_lines(os.path.join(site_dir, "snmp-communities.conf")) if site_dir else [],
        "automation_enabled": bool((cfg.get("automation") or {}).get("enabled", False)),
        "automation_apply": bool((cfg.get("automation") or {}).get("apply", False)),
        "schedule": clean((cfg.get("automation") or {}).get("schedule")) or "daily",
    }


def interactive_configure():
    cur = current_defaults()
    print("===== NETBOX-DISCOVERY CONFIGURAÇÃO =====")
    tenant = ask("Cliente/Tenant", cur["tenant"], True)
    group_default = cur["tenant_group"] if tenant == cur["tenant"] else ""
    tenant_group = ask("Tenant Group (opcional)", group_default, False)
    site = ask("Site", cur["site"], True)
    url = LOCKED_NETBOX_URL
    print("NetBox fixo: {0}".format(url))
    token_prompt = "Token do NetBox (ENTER preserva o atual)" if cur["token"] else "Token do NetBox"
    token = getpass.getpass(token_prompt + ": ").strip()
    if not token:
        token = cur["token"]
    if not token:
        raise RuntimeError("Token do NetBox é obrigatório")
    verify_ssl = yn("Validar certificado SSL?", cur["verify_ssl"])

    same_site = site == cur["site"]
    networks = capture_list("redes CIDR", validate_network, cur["networks"] if same_site else [], True)
    exclusions = capture_list("exclusões (IP/CIDR)", None, cur["exclusions"] if same_site else [], False)

    snmp_default = bool(cur["communities"]) if same_site else False
    snmp_enabled = yn("Habilitar SNMP?", snmp_default)
    communities = []
    if snmp_enabled:
        communities = capture_list("comunidades SNMP", None, cur["communities"] if same_site else [], True)

    automation_enabled = yn("Habilitar execução automática?", cur["automation_enabled"])
    automation_apply = False
    schedule = cur["schedule"] or "daily"
    if automation_enabled:
        schedule = ask("Agenda systemd OnCalendar", schedule, True)
        automation_apply = yn("Permitir IMPORT automático (escrita no NetBox)?", cur["automation_apply"])

    values = {
        "tenant": tenant, "tenant_group": tenant_group, "site": site, "url": url, "token": token,
        "verify_ssl": verify_ssl, "networks": networks, "exclusions": exclusions,
        "communities": communities, "automation_enabled": automation_enabled,
        "automation_apply": automation_apply, "schedule": schedule,
    }

    print("\n===== RESUMO =====")
    print("Tenant: {0}".format(tenant))
    print("Tenant Group: {0}".format(tenant_group or "SEM GRUPO"))
    print("Site: {0}".format(site))
    print("NetBox: {0}".format(url))
    print("SSL verify: {0}".format("SIM" if verify_ssl else "NÃO"))
    print("Redes: {0}".format(", ".join(networks)))
    print("Exclusões: {0}".format(len(exclusions)))
    print("SNMP: {0}".format("SIM ({0} comunidade(s))".format(len(communities)) if communities else "NÃO"))
    print("Automação: {0}".format("SIM" if automation_enabled else "NÃO"))
    if automation_enabled:
        print("Agenda: {0}".format(schedule))
        print("IMPORT automático: {0}".format("SIM" if automation_apply else "NÃO"))
    print("Discovery NÃO será iniciado por este assistente.")

    if not yn("Salvar esta configuração?", True):
        print("Cancelado. Nada alterado.")
        return 1
    write_config(values)
    print("CONFIGURAÇÃO: SALVA")
    if yn("Testar conexão com o NetBox agora?", True):
        test_netbox()
    print("Nenhuma varredura foi iniciada.")
    return 0


def noninteractive(args):
    cur = current_defaults()
    tenant = args.tenant or cur["tenant"]
    tenant_changed = bool(args.tenant) and clean(args.tenant) != cur["tenant"]
    if args.tenant_group is not None:
        tenant_group = clean(args.tenant_group)
    elif tenant_changed:
        tenant_group = ""
    else:
        tenant_group = cur["tenant_group"]
    values = {
        "tenant": tenant,
        "tenant_group": tenant_group,
        "site": args.site or cur["site"],
        "url": LOCKED_NETBOX_URL,
        "token": args.netbox_token or cur["token"],
        "verify_ssl": cur["verify_ssl"] if args.verify_ssl is None else args.verify_ssl,
        "networks": args.network or cur["networks"],
        "exclusions": args.exclude if args.exclude is not None else cur["exclusions"],
        "communities": args.community if args.community is not None else cur["communities"],
        "automation_enabled": cur["automation_enabled"] if args.automation is None else args.automation,
        "automation_apply": cur["automation_apply"] if args.auto_apply is None else args.auto_apply,
        "schedule": args.schedule or cur["schedule"] or "daily",
    }
    if args.netbox_url and args.netbox_url.rstrip("/").lower() != LOCKED_NETBOX_URL.rstrip("/").lower():
        raise RuntimeError("--netbox-url não permitido. Endpoint fixo: {0}".format(LOCKED_NETBOX_URL))
    for key in ("tenant", "site", "url", "token"):
        if not clean(values[key]):
            raise RuntimeError("Campo obrigatório ausente: {0}".format(key))
    if not values["networks"]:
        raise RuntimeError("Informe pelo menos uma --network")
    values["networks"] = [validate_network(x) for x in values["networks"]]
    write_config(values)
    if not args.skip_test:
        test_netbox()
    print("CONFIGURAÇÃO: SALVA")
    print("Nenhuma varredura foi iniciada.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Assistente de configuração do netbox-discovery")
    ap.add_argument("--non-interactive", action="store_true")
    ap.add_argument("--tenant")
    ap.add_argument("--tenant-group", default=None, help="Tenant Group opcional; string vazia remove o grupo da configuração")
    ap.add_argument("--site")
    ap.add_argument("--netbox-url", help="compatibilidade: deve corresponder ao endpoint fixo BKPCLOUD")
    ap.add_argument("--netbox-token")
    ap.add_argument("--network", action="append")
    ap.add_argument("--exclude", action="append")
    ap.add_argument("--community", action="append")
    ap.add_argument("--schedule")
    ap.add_argument("--skip-test", action="store_true")
    ssl = ap.add_mutually_exclusive_group()
    ssl.add_argument("--verify-ssl", dest="verify_ssl", action="store_true")
    ssl.add_argument("--no-verify-ssl", dest="verify_ssl", action="store_false")
    ap.set_defaults(verify_ssl=None)
    auto = ap.add_mutually_exclusive_group()
    auto.add_argument("--automation", dest="automation", action="store_true")
    auto.add_argument("--no-automation", dest="automation", action="store_false")
    ap.set_defaults(automation=None)
    apply = ap.add_mutually_exclusive_group()
    apply.add_argument("--auto-apply", dest="auto_apply", action="store_true")
    apply.add_argument("--no-auto-apply", dest="auto_apply", action="store_false")
    ap.set_defaults(auto_apply=None)
    args = ap.parse_args(argv)
    if args.non_interactive:
        return noninteractive(args)
    return interactive_configure()


if __name__ == "__main__":
    sys.exit(main())
