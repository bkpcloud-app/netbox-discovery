#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile

BASE = os.environ.get("NETBOX_DISCOVERY_BASE", "/opt/netbox-discovery")
VENDOR = os.path.join(BASE, "vendor")
PACKAGES = ["six==1.16.0", "pyvmomi==7.0.3"]


def fingerprint():
    lines = ["vmware=1", "hyperv=0"] + PACKAGES
    raw = "".join(x + "\n" for x in lines).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def valid_vendor(path):
    env = os.environ.copy()
    env["PYTHONPATH"] = path + (":" + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return subprocess.call(
        [sys.executable, "-c", "import pyVmomi, six; print('VMWARE DEPS: OK')"],
        env=env,
    ) == 0


def main():
    if os.geteuid() != 0:
        raise RuntimeError("instalação de dependências VMware exige root")

    marker = os.path.join(VENDOR, ".requirements.sha256")
    wanted = fingerprint()
    try:
        current = open(marker, "r").read().strip()
    except Exception:
        current = ""

    if current == wanted and valid_vendor(VENDOR):
        print("VMWARE DEPS: OK")
        return 0

    if subprocess.call([sys.executable, "-m", "pip", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
        raise RuntimeError("python3-pip não está disponível")

    parent = BASE if os.path.isdir(BASE) else "/tmp"
    temp = tempfile.mkdtemp(prefix="vendor.vmware.tmp.", dir=parent)
    old = VENDOR + ".old"
    try:
        print("Preparando dependências VMware isoladas...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install",
            "--disable-pip-version-check", "--no-cache-dir",
            "--target", temp,
        ] + PACKAGES)

        if not valid_vendor(temp):
            raise RuntimeError("validação do pyVmomi falhou")

        with open(os.path.join(temp, ".requirements.sha256"), "w") as handle:
            handle.write(wanted + "\n")

        if os.path.isdir(old):
            shutil.rmtree(old)
        if os.path.isdir(VENDOR):
            os.rename(VENDOR, old)
        try:
            os.rename(temp, VENDOR)
            temp = ""
        except Exception:
            if os.path.isdir(old) and not os.path.isdir(VENDOR):
                os.rename(old, VENDOR)
            raise
        if os.path.isdir(old):
            shutil.rmtree(old)

        print("VMWARE DEPS: OK")
        return 0
    finally:
        if temp and os.path.isdir(temp):
            shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("ERRO: {0}".format(exc), file=sys.stderr)
        sys.exit(1)
