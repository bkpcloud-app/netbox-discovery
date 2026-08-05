#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import argparse
import json
import os
import py_compile
import re
import subprocess
import sys

DEFAULT_BASE = os.environ.get("NETBOX_DISCOVERY_BASE", "/opt/netbox-discovery")


def _check_release_docs(package_root, version, errors):
    if not package_root or not version:
        return

    expected_files = [
        "README.md",
        "docs/MANUAL.md",
        "docs/COMANDOS-RAPIDOS.md",
        "docs/HOMOLOGACAO.md",
        "RELEASE-NOTES.md",
        "SECURITY.md",
    ]
    texts = {}
    for rel in expected_files:
        path = os.path.join(package_root, rel)
        if not os.path.isfile(path):
            errors.append("documentação obrigatória ausente: {0}".format(rel))
            continue
        try:
            texts[rel] = open(path, "r").read()
        except Exception as exc:
            errors.append("documentação ilegível {0}: {1}".format(rel, exc))

    parts = version.split(".")
    patch_release = len(parts) == 3 and parts[2] != "0"
    patch_path = os.path.join(package_root, "docs", "PATCH-{0}.md".format(version))

    if patch_release and os.path.isfile(patch_path):
        try:
            patch_text = open(patch_path, "r").read()
        except Exception as exc:
            errors.append("nota de patch ilegível: {0}".format(exc))
            return
        marker = "# netbox-discovery {0}".format(version)
        if marker not in patch_text:
            errors.append("nota de patch fora da versão {0}".format(version))
        family = "{0}.{1}.".format(parts[0], parts[1])
        for rel, text in texts.items():
            if family not in text:
                errors.append("documentação fora da família {0}: {1}".format(family, rel))
        return

    expected = [
        ("README.md", "**Versão atual:** {0}"),
        ("docs/MANUAL.md", "**Versão:** {0}"),
        ("docs/COMANDOS-RAPIDOS.md", "# netbox-discovery {0}"),
        ("docs/HOMOLOGACAO.md", "# netbox-discovery {0}"),
        ("RELEASE-NOTES.md", "## V{0}"),
        ("SECURITY.md", "**Versão da política:** {0}"),
    ]
    for rel, marker_template in expected:
        text = texts.get(rel)
        if text is None:
            continue
        marker = marker_template.format(version)
        if marker not in text:
            errors.append("documentação fora da versão {0}: {1} (esperado: {2})".format(version, rel, marker))


def _check_direct_entrypoint(label, path, errors):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    try:
        process = subprocess.Popen(
            [sys.executable, path, "--help"],
            cwd="/",
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = process.communicate()
    except Exception as exc:
        errors.append("entrypoint {0} não executou: {1}".format(label, exc))
        return
    if process.returncode != 0:
        detail = (stderr or stdout or b"").decode("utf-8", "replace").strip()
        errors.append("entrypoint {0} falhou diretamente: {1}".format(label, detail[:500]))


def _check_effective_components(base, errors):
    code = (
        "import sys; sys.path.insert(0, {0}); "
        "from modules.discovery import network_v6 as d; "
        "from modules.inventory import planner_v11 as p; "
        "from modules.importers import importer_v12 as i; "
        "from modules.auditors import auditor_v11 as a; "
        "assert d.DISCOVERY_WRAPPER_VERSION == '4.6-product'; "
        "assert p.PLANNER_VERSION == '5.3-product'; "
        "assert i.IMPORTER_VERSION == '6.1-product'; "
        "assert a.AUDITOR_VERSION == '6.9-product'"
    ).format(repr(base))
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    try:
        process = subprocess.Popen(
            [sys.executable, "-c", code], cwd="/", env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        stdout, stderr = process.communicate()
    except Exception as exc:
        errors.append("contrato de componentes não executou: {0}".format(exc))
        return
    if process.returncode != 0:
        detail = (stderr or stdout or b"").decode("utf-8", "replace").strip()
        errors.append("contrato de componentes falhou: {0}".format(detail[:500]))


def check(base, package_root=""):
    errors = []
    required = [
        "VERSION", "bin/netbox-discovery", "lib/config.py", "lib/netbox.py",
        "modules/discovery/network.py", "modules/discovery/network_v2.py", "modules/discovery/network_v3.py",
        "modules/discovery/network_v4.py", "modules/discovery/network_v5.py", "modules/discovery/network_v6.py",
        "modules/inventory/classifier.py", "modules/inventory/classifier_v2.py",
        "modules/inventory/classifier_v3.py", "modules/inventory/classifier_v4.py",
        "modules/inventory/classifier_v5.py", "modules/inventory/classifier_v6.py",
        "modules/inventory/classifier_v7.py", "modules/inventory/classifier_v8.py",
        "modules/inventory/reconciler_v2.py", "modules/inventory/reconciler_v3.py",
        "modules/inventory/reconciler_v4.py", "modules/inventory/reconciler_v5.py",
        "modules/inventory/planner_v2.py", "modules/inventory/planner_v3.py",
        "modules/inventory/planner_v4.py", "modules/inventory/planner_v5.py",
        "modules/inventory/planner_v6.py", "modules/inventory/planner_v7.py",
        "modules/inventory/planner_v8.py", "modules/inventory/planner_v9.py",
        "modules/inventory/planner_v9_core.py", "modules/inventory/planner_v10.py",
        "modules/inventory/planner_v11.py", "modules/inventory/pipeline.py",
        "modules/importers/importer_v2.py", "modules/importers/importer_v3.py",
        "modules/importers/importer_v4.py", "modules/importers/importer_v5.py",
        "modules/importers/importer_v6.py", "modules/importers/importer_v7.py",
        "modules/importers/importer_v8.py", "modules/importers/importer_v9.py",
        "modules/importers/importer_v10.py", "modules/importers/importer_v11.py",
        "modules/importers/importer_v12.py",
        "modules/auditors/auditor_v2.py", "modules/auditors/auditor_v3.py",
        "modules/auditors/auditor_v4.py", "modules/auditors/auditor_v5.py",
        "modules/auditors/auditor_v6.py", "modules/auditors/auditor_v7.py",
        "modules/auditors/auditor_v8.py", "modules/auditors/auditor_v9.py",
        "modules/auditors/auditor_v10.py", "modules/auditors/auditor_v11.py",
        "modules/product/configurator_v2.py", "modules/product/runner.py", "modules/product/updater.py",
        "modules/product/health.py", "modules/product/selftest.py", "modules/product/identity.py",
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
        dirs[:] = [name for name in dirs if name not in ("vendor", "reports", "logs", "cache", "backups", "__pycache__")]
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

    entrypoints = (
        ("planner_v11.py", os.path.join(base, "modules", "inventory", "planner_v11.py")),
        ("importer_v12.py", os.path.join(base, "modules", "importers", "importer_v12.py")),
        ("auditor_v11.py", os.path.join(base, "modules", "auditors", "auditor_v11.py")),
    )
    for label, path in entrypoints:
        if os.path.isfile(path):
            _check_direct_entrypoint(label, path, errors)
    _check_effective_components(base, errors)

    return version, errors


def main(argv=None):
    parser = argparse.ArgumentParser(description="netbox-discovery self-test sem dependência de config.yml")
    parser.add_argument("--base", default=DEFAULT_BASE)
    parser.add_argument("--package-root", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

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
