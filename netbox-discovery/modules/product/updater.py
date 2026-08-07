#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import argparse
import datetime
import fcntl
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

BASE = os.environ.get("NETBOX_DISCOVERY_BASE", "/opt/netbox-discovery")
REPO_URL = "https://github.com/bkpcloud-app/netbox-discovery.git"
CHANNEL = "stable"
REMOTE_VERSION_URL = "https://raw.githubusercontent.com/bkpcloud-app/netbox-discovery/stable/VERSION"
LOCK_FILE = "/var/lock/netbox-discovery-global.lock"
STATE_DIR = "/var/lib/netbox-discovery"
STATE_FILE = os.path.join(STATE_DIR, "update-state.json")
BACKUP_DIR = os.path.join(STATE_DIR, "update-backups")
BACKUP_ITEMS = ("VERSION", "workflow.yml", "config.yml", "bin", "lib", "modules", "config", "systemd")


def now():
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def read_text(path):
    with open(path, "r") as handle:
        return handle.read().strip()


def version_key(value):
    value = str(value or "").strip()
    if not re.match(r"^[0-9]+\.[0-9]+\.[0-9]+$", value):
        raise RuntimeError("VERSION estável inválida: {0}".format(value))
    return tuple(int(x) for x in value.split("."))


def installed_version():
    return read_text(os.path.join(BASE, "VERSION"))


def remote_version():
    # raw.githubusercontent.com pode manter VERSION em cache por alguns minutos
    # logo após um merge. O parâmetro único e os headers no-cache impedem o
    # updater de concluir incorretamente que a versão instalada ainda é a atual.
    url = REMOTE_VERSION_URL + "?cache_bust={0}".format(int(time.time() * 1000))
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "netbox-discovery-updater/1.9",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        return response.read().decode("utf-8").strip()


def load_state():
    try:
        with open(STATE_FILE, "r") as handle:
            data = json.load(handle)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_state(data):
    if not os.path.isdir(STATE_DIR):
        os.makedirs(STATE_DIR)
    temp = STATE_FILE + ".tmp"
    with open(temp, "w") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, STATE_FILE)


def cleanup_retention():
    if os.path.isdir(BACKUP_DIR):
        rows = sorted(
            [os.path.join(BACKUP_DIR, x) for x in os.listdir(BACKUP_DIR)],
            key=lambda p: os.path.getmtime(p), reverse=True,
        )
        for path in rows[5:]:
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
    reports = os.path.join(BASE, "reports")
    cutoff = datetime.datetime.utcnow().timestamp() - (30 * 86400)
    if os.path.isdir(reports):
        for name in os.listdir(reports):
            path = os.path.join(reports, name)
            try:
                if os.path.isfile(path) and os.path.getmtime(path) < cutoff:
                    os.unlink(path)
            except Exception:
                pass


def backup_current(version):
    if not os.path.isdir(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    stamp = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    destination = os.path.join(BACKUP_DIR, "{0}-{1}".format(stamp, version))
    os.makedirs(destination)
    for item in BACKUP_ITEMS:
        source = os.path.join(BASE, item)
        if not os.path.exists(source):
            continue
        target = os.path.join(destination, item)
        if os.path.isdir(source):
            shutil.copytree(source, target, symlinks=True)
        else:
            shutil.copy2(source, target)
    return destination


def restore_backup(path):
    for item in BACKUP_ITEMS:
        source = os.path.join(path, item)
        target = os.path.join(BASE, item)
        if os.path.isdir(target) and not os.path.islink(target):
            shutil.rmtree(target)
        elif os.path.lexists(target):
            os.unlink(target)
        if not os.path.exists(source):
            continue
        if os.path.isdir(source):
            shutil.copytree(source, target, symlinks=True)
        else:
            shutil.copy2(source, target)
    cli = os.path.join(BASE, "bin", "netbox-discovery")
    if os.path.isfile(cli):
        os.chmod(cli, 0o750)
        subprocess.call(["ln", "-sfn", cli, "/usr/local/bin/netbox-discovery"])
    systemd_dir = os.path.join(BASE, "systemd")
    if os.path.isdir(systemd_dir):
        for name in os.listdir(systemd_dir):
            if name.endswith((".service", ".timer")):
                shutil.copy2(os.path.join(systemd_dir, name), os.path.join("/etc/systemd/system", name))
        subprocess.call(["systemctl", "daemon-reload"])


def candidate_selftest(repo_root):
    product = os.path.join(repo_root, "netbox-discovery")
    script = os.path.join(product, "modules", "product", "selftest.py")
    subprocess.check_call([sys.executable, script, "--base", product, "--package-root", repo_root])


def installed_selftest():
    script = os.path.join(BASE, "modules", "product", "selftest.py")
    subprocess.check_call([sys.executable, script, "--base", BASE])
    if os.path.isfile(os.path.join(BASE, "config.yml")):
        subprocess.check_call([os.path.join(BASE, "bin", "netbox-discovery"), "check"])


def status():
    state = load_state()
    current = "?"
    try:
        current = installed_version()
    except Exception:
        pass
    print("===== NETBOX-DISCOVERY UPDATE STATUS =====")
    print("Canal: {0}".format(CHANNEL))
    print("Versão instalada: {0}".format(current))
    print("Última verificação: {0}".format(state.get("last_check", "NUNCA")))
    print("Último status: {0}".format(state.get("last_status", "SEM HISTÓRICO")))
    print("Última versão disponível: {0}".format(state.get("available_version", "?")))
    print("Versão em quarentena: {0}".format(state.get("failed_version", "")))
    print("Último rollback: {0}".format(state.get("last_rollback", "")))
    return 0


def check_only():
    current = installed_version()
    available = remote_version()
    version_key(current)
    version_key(available)
    state = load_state()
    state.update({"last_check": now(), "available_version": available, "installed_version": current})
    save_state(state)
    print("Instalada: {0}".format(current))
    print("Disponível: {0}".format(available))
    print("Update: {0}".format("SIM" if version_key(available) > version_key(current) else "NÃO"))
    return 0


def perform_update(retry_failed=False):
    if os.geteuid() != 0:
        raise RuntimeError("update exige root")

    current = installed_version()
    available = remote_version()
    version_key(current)
    version_key(available)
    state = load_state()
    state.update({"last_check": now(), "available_version": available, "installed_version": current})
    save_state(state)

    if version_key(available) < version_key(current):
        print("DOWNGRADE BLOQUEADO: instalada={0} disponível={1}".format(current, available))
        return 0
    if available == current:
        state["last_status"] = "UP_TO_DATE"
        save_state(state)
        cleanup_retention()
        print("ATUALIZADO: {0}".format(current))
        return 0
    if state.get("failed_version") == available and not retry_failed:
        print("VERSÃO EM QUARENTENA: {0}. Use --retry para tentar manualmente.".format(available))
        return 0

    lock = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        print("UPDATE ADIADO: Network/Hypervisor/Update em execução.")
        return 0
    lock.write("update:{0}".format(os.getpid()))
    lock.flush()

    backup = ""
    temp_root = tempfile.mkdtemp(prefix="netbox-discovery-update-")
    repo = os.path.join(temp_root, "repo")
    try:
        subprocess.check_call(["git", "clone", "--depth", "1", "--branch", CHANNEL, REPO_URL, repo])
        root_version = read_text(os.path.join(repo, "VERSION"))
        package_version = read_text(os.path.join(repo, "netbox-discovery", "VERSION"))
        if root_version != available or package_version != available:
            raise RuntimeError("VERSION divergente no pacote stable")
        candidate_selftest(repo)
        backup = backup_current(current)
        subprocess.check_call(["bash", os.path.join(repo, "bootstrap.sh")])
        installed_selftest()
        state.update({
            "last_status": "UPDATED", "last_update": now(),
            "previous_version": current, "installed_version": available,
            "failed_version": "", "last_error": "", "last_rollback": "",
        })
        save_state(state)
        cleanup_retention()
        print("UPDATE OK: {0} -> {1}".format(current, available))
        return 0
    except Exception as exc:
        rollback_status = "NOT_REQUIRED"
        if backup:
            try:
                restore_backup(backup)
                installed_selftest()
                rollback_status = "OK"
            except Exception as rollback_exc:
                rollback_status = "FAILED: {0}".format(rollback_exc)
        state.update({
            "last_status": "FAILED", "failed_version": available,
            "last_error": str(exc), "last_rollback": rollback_status,
        })
        save_state(state)
        print("UPDATE FALHOU: {0}".format(exc), file=sys.stderr)
        print("ROLLBACK: {0}".format(rollback_status), file=sys.stderr)
        return 1
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description="netbox-discovery stable auto updater")
    ap.add_argument("action", nargs="?", default="status", choices=("status", "check", "run", "scheduled"))
    ap.add_argument("--retry", action="store_true", help="tenta novamente versão em quarentena")
    args = ap.parse_args(argv)
    if args.action == "status":
        return status()
    if args.action == "check":
        return check_only()
    return perform_update(retry_failed=args.retry)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("ERRO: {0}".format(exc), file=sys.stderr)
        sys.exit(1)
