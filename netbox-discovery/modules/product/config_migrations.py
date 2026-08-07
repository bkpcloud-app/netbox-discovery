#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import argparse
import os
import sys

DEFAULT_BASE = os.environ.get("NETBOX_DISCOVERY_BASE", "/opt/netbox-discovery")
DEFAULT_CONFIG = os.path.join(DEFAULT_BASE, "config.yml")
LEGACY_NETBOX_URL = "https://inventory.bkpcloud.app.br:8080"
CURRENT_NETBOX_URL = "https://inventory.bkpcloud.app.br"


def _clean(value):
    return "" if value is None else str(value).strip()


def _atomic_write(path, text):
    mode = 0o600
    try:
        mode = os.stat(path).st_mode & 0o777
    except OSError:
        pass
    tmp = path + ".migration.tmp"
    with open(tmp, "w") as handle:
        handle.write(text.rstrip() + "\n")
    os.chmod(tmp, mode or 0o600)
    os.replace(tmp, path)


def _top_level_section(lines, name):
    exact = name + ":"
    malformed = []
    for index, row in enumerate(lines):
        stripped = row.strip()
        indent = len(row) - len(row.lstrip())
        if indent != 0 or not stripped or stripped.startswith("#"):
            continue
        if stripped == exact:
            end = len(lines)
            for cursor in range(index + 1, len(lines)):
                candidate = lines[cursor]
                candidate_stripped = candidate.strip()
                candidate_indent = len(candidate) - len(candidate.lstrip())
                if candidate_indent == 0 and candidate_stripped and not candidate_stripped.startswith("#"):
                    end = cursor
                    break
            return index, end
        if stripped.startswith(name + ":"):
            malformed.append((index + 1, stripped))
    if malformed:
        line, value = malformed[0]
        raise RuntimeError("seção {0} inválida na linha {1}: {2}".format(name, line, value))
    return None, None


def ensure_network_automation(path):
    """Add missing Network automation defaults without changing existing values.

    Existing customer configuration, credentials and comments are preserved.
    A legacy configuration without the automation section is migrated to the
    safest product default: disabled scheduler, no automatic APPLY and daily
    schedule.
    """
    if not os.path.isfile(path):
        raise RuntimeError("config.yml não existe: {0}".format(path))

    original = open(path, "r").read()
    lines = original.splitlines()
    start, end = _top_level_section(lines, "automation")
    changed = False

    defaults = (
        ("enabled", "false"),
        ("apply", "false"),
        ("schedule", "daily"),
    )

    if start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend([
            "automation:",
            "  enabled: false",
            "  apply: false",
            "  schedule: daily",
        ])
        changed = True
    else:
        present = set()
        for row in lines[start + 1:end]:
            stripped = row.strip()
            indent = len(row) - len(row.lstrip())
            if indent <= 0 or not stripped or stripped.startswith("#") or ":" not in stripped:
                continue
            key = _clean(stripped.split(":", 1)[0])
            if key:
                present.add(key)

        additions = ["  {0}: {1}".format(key, value) for key, value in defaults if key not in present]
        if additions:
            insert_at = end
            while insert_at > start + 1 and not lines[insert_at - 1].strip():
                insert_at -= 1
            lines[insert_at:insert_at] = additions
            changed = True

    if changed:
        _atomic_write(path, "\n".join(lines))
    return changed


def _yaml_scalar(value):
    value = _clean(value)
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1], value[0]
    return value, ""


def migrate_netbox_url(path):
    """Migrate only the product's exact legacy public NetBox URL.

    This is deliberately not a generic port rewrite. Customer-specific URLs,
    other :8080 endpoints, credentials and all unrelated configuration remain
    untouched. Existing quote style is preserved.
    """
    if not os.path.isfile(path):
        raise RuntimeError("config.yml não existe: {0}".format(path))

    original = open(path, "r").read()
    lines = original.splitlines()
    start, end = _top_level_section(lines, "netbox")
    if start is None:
        return False

    for index in range(start + 1, end):
        row = lines[index]
        stripped = row.strip()
        indent = len(row) - len(row.lstrip())
        if indent <= 0 or not stripped or stripped.startswith("#") or ":" not in row:
            continue

        key_text, value_text = row.split(":", 1)
        if _clean(key_text) != "url":
            continue

        scalar, quote = _yaml_scalar(value_text)
        if scalar != LEGACY_NETBOX_URL:
            return False

        spacing = value_text[:len(value_text) - len(value_text.lstrip())]
        replacement = CURRENT_NETBOX_URL
        if quote:
            replacement = quote + replacement + quote
        lines[index] = key_text + ":" + spacing + replacement
        _atomic_write(path, "\n".join(lines))
        return True

    return False


def main(argv=None):
    parser = argparse.ArgumentParser(description="Migrações seguras do config.yml")
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--ensure-network-automation", action="store_true")
    parser.add_argument("--migrate-netbox-url", action="store_true")
    args = parser.parse_args(argv)

    if not args.ensure_network_automation and not args.migrate_netbox_url:
        parser.error("informe ao menos uma migração")

    config_path = os.path.abspath(args.config)

    if args.ensure_network_automation:
        changed = ensure_network_automation(config_path)
        if changed:
            print("CONFIG MIGRATION: automation adicionada/completada com segurança")
        else:
            print("CONFIG MIGRATION: automation já completa")

    if args.migrate_netbox_url:
        changed = migrate_netbox_url(config_path)
        if changed:
            print("CONFIG MIGRATION: NetBox URL migrada para HTTPS/443")
        else:
            print("CONFIG MIGRATION: NetBox URL sem alteração")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("ERRO: {0}".format(exc), file=sys.stderr)
        sys.exit(1)
