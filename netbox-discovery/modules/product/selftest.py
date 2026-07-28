#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import argparse
import json
import os
import py_compile
import subprocess
import sys

DEFAULT_BASE = os.environ.get("NETBOX_DISCOVERY_BASE", "/opt/netbox-discovery")


def _check_release_docs(package_root, version, errors):
    if not package_root or not version:
        return
    expected = [
        ("README.md", "**Versão atual:** {0}".format(version)),
        ("docs/MANUAL.md", "**Versão:** {0}".format(version)),
        ("docs/COMANDOS-RAPIDOS.md", "# netbox-discovery {0}".format(version)),
        ("docs/HOMOLOGACAO.md", "# netbox-discovery {0}".format(version)),
        ("RELEASE-NOTES.md", "## V{0}".format(version)),
        ("SECURITY.md", "**Versão da política:** {0}".format(version)),
    ]
    for rel, marker in expected:
        path = os.path.join(package_root, rel)
        if not os.path.isfile(path):
            errors.append("documentação obrigatória ausente: {0}".format(rel))
            continue
        try:
            text = open(path, "r").read()
        except Exception as exc:
            errors.append("documentação ilegível {0}: {1}".format(rel, exc))
            continue
        if marker not in text:
            errors.append("documentação fora da versão {0}: {1} (esperado marcador: {2})".format(version, rel, marker))


def check(base, package_root=""):
    errors = []
    required = [
        "VERSION", "bin/netbox-discovery", "lib/config.py", "lib/netbox.py",
        "modules/discovery/network.py", "modules/discovery/network_v2.py", "modules/discovery/network_v3.py",
        "modules/inventory/classifier.py", "modules/inventory/classifier_v2.py",
        "modules/inventory/classifier_v3.py", "modules/inventory/classifier_v4.py", "modules/inventory/classifier_v5.py",
        "modules/inventory/reconciler_v2.py", "modules/inventory/reconciler_v3.py",
        "modules/inventory/reconciler_v4.py", "modules/inventory/reconciler_v5.py",
        "modules/inventory/planner_v2.py", "modules/inventory/planner_v3.py", "modules/inventory/planner_v4.py",
        "modules/inventory/pipeline.py", "modules/importers/importer_v2.py",
        "modules/importers/importer_v3.py", "modules/importers/importer_v4.py",
        "modules/auditors/auditor_v2.py", "modules/auditors/auditor_v3.py", "modules/auditors/auditor_v4.py",
        "modules/product/configurator_v2.py", "modules/product/runner.py", "modules/product/updater.py",
        "modules/product/health.py", "modules/product/selftest.py",
        "modules/hypervisor/configurator_v2.py", "modules/hypervisor/deps_vmware.py",
        "modules/hypervisor/engine_v2.py", "modules/hypervisor/engine_v3.py",
        "modules/hypervisor/resolver.py", "modules/hypervisor/structure.py",
        "modules/hypervisor/runner.py", "systemd/netbox-discovery-update.service",
        "systemd/netbox-discovery-update.timer",
    ]
    for rel in required:
        if not os.path.isfile(os.path.join(base, rel)):
            errors.append("arquivo ausente: " + rel)

    version = ""
    try:
        version = open(os.path.join(base, "VERSION"), "r").read().strip()
    except Exception as exc:
        errors.append("VERSION ilegível: {0}".format(exc))
    if not version:
        errors.append("VERSION vazia")

    if package_root:
        root_version = ""
        try:
            root_version = open(os.path.join(package_root, "VERSION"), "r").read().strip()
        except Exception as exc:
            errors.append("VERSION raiz ilegível: {0}".format(exc))
        if root_version and version and root_version != version:
            errors.append("VERSION divergente: raiz={0} pacote={1}".format(root_version, version))
        _check_release_docs(package_root, version, errors)

    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in ("vendor", "reports", "logs", "cache", "backups", "__pycache__")]
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(root, name)
            try:
                py_compile.compile(path, doraise=True)
            except Exception as exc:
                errors.append("py_compile {0}: {1}".format(path, exc))

    shell_files = [os.path.join(base, "bin", "netbox-discovery")]
    if package_root:
        shell_files.extend([
            os.path.join(package_root, "bootstrap.sh"),
            os.path.join(package_root, "install.sh"),
            os.path.join(package_root, "install-from-github.sh"),
        ])
    for path in shell_files:
        if os.path.isfile(path):
            result = subprocess.call(["bash", "-n", path])
            if result != 0:
                errors.append("bash -n falhou: " + path)

    return version, errors


def main(argv=None):
    ap = argparse.ArgumentParser(description="netbox-discovery self-test sem dependência de config.yml")
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--package-root", default="")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    version, errors = check(os.path.abspath(args.base), os.path.abspath(args.package_root) if args.package_root else "")
    result = {"status": "PASS" if not errors else "FAIL", "version": version, "errors": errors}
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print("===== NETBOX-DISCOVERY SELF-TEST =====")
        print("Versão: {0}".format(version or "?"))
        print("Status: {0}".format(result["status"]))
        for error in errors:
            print("ERRO: {0}".format(error))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
