#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import argparse
import os
import sys

DEFAULT_BASE = os.environ.get("NETBOX_DISCOVERY_BASE", "/opt/netbox-discovery")
DEFAULT_CONFIG = os.path.join(DEFAULT_BASE, "config.yml")


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


def main(argv=None):
    parser = argparse.ArgumentParser(description="Migrações seguras do config.yml")
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--ensure-network-automation", action="store_true")
    args = parser.parse_args(argv)

    if not args.ensure_network_automation:
        parser.error("informe --ensure-network-automation")

    changed = ensure_network_automation(os.path.abspath(args.config))
    if changed:
        print("CONFIG MIGRATION: automation adicionada/completada com segurança")
    else:
        print("CONFIG MIGRATION: automation já completa")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("ERRO: {0}".format(exc), file=sys.stderr)
        sys.exit(1)
