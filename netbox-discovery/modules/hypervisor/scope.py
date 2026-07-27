#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import argparse

from modules.hypervisor.config import clean, load_hypervisor_config, save_hypervisor_config

VALID_MODES = ("site_networks", "all")


def describe(mode):
    if mode == "site_networks":
        return "hosts pela rede de gerenciamento do Site; VMs nesses hosts ou com IP do Site"
    return "todos os hosts/VMs visíveis pela source, independentemente do Site"


def show(cfg):
    rows = cfg.get("sources") or []
    print("===== HYPERVISOR SCOPE =====")
    print("Sources configuradas: {0}".format(len(rows)))
    for pos, source in enumerate(rows, 1):
        mode = clean(source.get("scope_mode") or "site_networks").lower()
        if mode not in VALID_MODES:
            mode = "site_networks"
        print("  {0}. {1} | {2} | scope={3}".format(pos, source.get("id"), source.get("endpoint"), mode))
    print("NetBox write: NÃO")


def set_scope(cfg, mode):
    if mode not in VALID_MODES:
        raise RuntimeError("Scope inválido: {0}".format(mode))
    rows = cfg.get("sources") or []
    if not rows:
        raise RuntimeError("Nenhuma source configurada")

    changed = 0
    print("===== HYPERVISOR SCOPE UPDATE =====")
    print("Novo scope: {0}".format(mode))
    print("Política: {0}".format(describe(mode)))
    for source in rows:
        old = clean(source.get("scope_mode") or "site_networks").lower()
        if old not in VALID_MODES:
            old = "site_networks"
        source["scope_mode"] = mode
        if old != mode:
            changed += 1
        print("  {0}: {1} -> {2}".format(source.get("id"), old, mode))

    save_hypervisor_config(cfg)
    print("Sources alteradas: {0}".format(changed))
    print("Credenciais/endpoints: PRESERVADOS")
    print("NetBox write: NÃO")
    print("Próximo passo seguro: netbox-discovery hypervisor run")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Gerencia o escopo das sources Hypervisor")
    sub = ap.add_subparsers(dest="action")
    sub.add_parser("status")
    setter = sub.add_parser("set")
    setter.add_argument("mode", choices=VALID_MODES)
    args = ap.parse_args(argv)

    cfg = load_hypervisor_config(required=True)
    if args.action in (None, "status"):
        show(cfg)
        return 0
    if args.action == "set":
        set_scope(cfg, args.mode)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
