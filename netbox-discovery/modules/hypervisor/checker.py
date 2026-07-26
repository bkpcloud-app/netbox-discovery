#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import sys

BASE = os.environ.get("NETBOX_DISCOVERY_BASE", "/opt/netbox-discovery")
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from lib.config import LOCKED_NETBOX_URL, load_config
from lib.netbox import NetBox
from modules.hypervisor.collectors import check_source
from modules.hypervisor.config import enabled_sources, load_hypervisor_config


def main():
    cfg = load_config()
    hv = load_hypervisor_config(required=True)
    sources = enabled_sources(hv)
    if not sources:
        raise RuntimeError("Nenhum hypervisor habilitado")
    print("===== NETBOX-DISCOVERY HYPERVISOR CHECK =====")
    print("NetBox fixo: {0}".format(LOCKED_NETBOX_URL))
    nb = NetBox()
    status = nb.get("status/")
    if not isinstance(status, dict):
        raise RuntimeError("NetBox retornou status inválido")
    print("NETBOX: OK")
    print("Tenant/Site: {0}/{1}".format(cfg.get("tenant", ""), (cfg.get("discovery") or {}).get("site", "")))
    errors = []
    for source in sources:
        try:
            result = check_source(source)
            print("{0}: OK | {1} | {2}".format(source.get("id"), result.get("product", ""), result.get("version", "")))
        except Exception as exc:
            errors.append((source.get("id"), str(exc)))
            print("{0}: ERRO | {1}".format(source.get("id"), exc))
    if errors:
        raise RuntimeError("{0} source(s) com erro".format(len(errors)))
    print("HYPERVISOR CHECK: OK")
    print("NetBox write: NÃO")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("ERRO: {0}".format(exc), file=sys.stderr)
        sys.exit(1)
