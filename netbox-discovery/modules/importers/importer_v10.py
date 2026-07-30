#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import builtins
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, "..", ".."))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.importers import importer_v4 as v4
from modules.importers import importer_v7 as v7
from modules.importers import importer_v8 as v8
from modules.importers import importer_v9 as v9

IMPORTER_VERSION = "5.9-product"
REPORTS = v4.REPORTS
ORIG_SAFE_PATCH = v9.safe_patch_for_existing
PRODUCT_DEVICE_DESCRIPTION = "Criado pelo netbox-discovery"
WINDOWS_ROLES = {
    "SERVER-WINDOWS", "WORKSTATION-WINDOWS",
    "WINDOWS_SERVER", "WINDOWS_WORKSTATION",
}
WINDOWS_EVIDENCE_SOURCES = (
    "smb-os-discovery", "smb-system-info", "service-cpe",
    "os-cpe", "os-fingerprint", "os-class",
)


def clean(value):
    return "" if value is None else str(value).strip()


def norm(value):
    return re.sub(r"\s+", " ", clean(value)).strip().casefold()


def nested_name(value):
    if isinstance(value, dict):
        return clean(value.get("name") or value.get("display") or value.get("model"))
    return clean(value)


def _role_diff(row):
    values = []
    prefix = "role:SET:"
    for diff in row.get("safe_diffs") or []:
        value = clean(diff)
        if value.startswith(prefix):
            values.append(clean(value[len(prefix):]))
    if len(values) > 1:
        raise RuntimeError("mais de um role safe diff")
    return values[0] if values else ""


def _apply_windows_role_patch(payload, row, current, catalog):
    target = _role_diff(row)
    if not target:
        return payload
    if target not in ("SERVER-WINDOWS", "WORKSTATION-WINDOWS"):
        raise RuntimeError("correção automática de role não autorizada: {0}".format(target))
    if clean(row.get("target_role")) != target:
        raise RuntimeError("role safe diff diverge do PLAN")
    if clean(row.get("identity_policy")) != "WINDOWS_ROLE_CORRECTION_EXPLICIT_OS":
        raise RuntimeError("correção de role exige política Windows explícita")
    if clean(current.get("description")) != PRODUCT_DEVICE_DESCRIPTION:
        raise RuntimeError("correção de role exige Device criado pelo netbox-discovery")
    if clean(row.get("confidence")) != "HIGH":
        raise RuntimeError("correção de role exige confiança HIGH")
    source = clean(row.get("windows_evidence_source"))
    if not any(token in source for token in WINDOWS_EVIDENCE_SOURCES):
        raise RuntimeError("correção de role exige SMB/CPE/fingerprint forte")
    current_role = nested_name(current.get("role"))
    if current_role not in WINDOWS_ROLES:
        raise RuntimeError("role atual não pertence à família Windows protegida: {0}".format(current_role))
    if norm(current_role) == norm(target):
        return payload
    role = catalog.ensure_role(target)
    if not role or not role.get("id"):
        raise RuntimeError("role Windows sem ID: {0}".format(target))
    payload["role"] = role["id"]
    return payload


def _validate_serial_patch(payload, row):
    if "serial" not in payload:
        return payload
    if row.get("serial_conflict"):
        raise RuntimeError("serial conflitante não pode ser gravado")
    confidence = clean(row.get("serial_confidence"))
    if confidence not in ("HIGH", "MEDIUM"):
        raise RuntimeError("serial exige evidência HIGH ou MEDIUM")
    if clean(payload.get("serial")) != clean(row.get("serial")):
        raise RuntimeError("serial do payload diverge do PLAN")
    return payload


def safe_patch_for_existing(row, current, catalog):
    payload = ORIG_SAFE_PATCH(row, current, catalog)
    if "name" in payload:
        raise RuntimeError("política 1.11 proíbe alteração automática do nome de Device existente")
    if row.get("name_write_allowed") is False and "name" in payload:
        raise RuntimeError("PLAN marcou nome como administrado pelo NetBox")
    _validate_serial_patch(payload, row)
    _apply_windows_role_patch(payload, row, current, catalog)
    return payload


def refresh_plan():
    planner = os.path.join(BASE, "modules", "inventory", "planner_v9.py")
    if not os.path.isfile(planner):
        raise RuntimeError("Planner V9 não encontrado: {0}".format(planner))
    v4.base.subprocess.check_call([sys.executable, planner])
    path = v4._latest(os.path.join(REPORTS, "*-plan-*.json"))
    if not path:
        raise RuntimeError("PLAN V9 não gerou JSON")
    return path


def main(argv=None):
    old_refresh = v7.refresh_plan
    old_version = v8.IMPORTER_VERSION
    old_patch_v4 = v4.base.safe_patch_for_existing
    old_patch_v9 = v9.safe_patch_for_existing
    old_print = builtins.print

    def release_print(*args, **kwargs):
        if args and str(args[0]) in (
            "===== IMPORT FINALIZE 1.10.18 =====",
            "===== IMPORT FINALIZE 1.10.19 =====",
            "===== IMPORT FINALIZE 1.11.0 =====",
            "===== IMPORT FINALIZE 1.11.1 =====",
        ):
            args = ("===== IMPORT FINALIZE 1.11.2 =====",) + tuple(args[1:])
        return old_print(*args, **kwargs)

    try:
        v7.refresh_plan = refresh_plan
        v8.IMPORTER_VERSION = IMPORTER_VERSION
        v4.base.safe_patch_for_existing = safe_patch_for_existing
        v9.safe_patch_for_existing = safe_patch_for_existing
        builtins.print = release_print
        return v9.main(argv)
    finally:
        builtins.print = old_print
        v9.safe_patch_for_existing = old_patch_v9
        v4.base.safe_patch_for_existing = old_patch_v4
        v8.IMPORTER_VERSION = old_version
        v7.refresh_plan = old_refresh


if __name__ == "__main__":
    sys.exit(main())
