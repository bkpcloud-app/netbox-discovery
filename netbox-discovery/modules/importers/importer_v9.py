#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import builtins
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from modules.importers import importer_v4 as v4
from modules.importers import importer_v7 as v7
from modules.importers import importer_v8 as v8

IMPORTER_VERSION = "5.7-product"
BASE = v4.BASE
REPORTS = v4.REPORTS
PRODUCT_DEVICE_DESCRIPTION = "Criado pelo netbox-discovery"
ORIG_SAFE_PATCH = v4.base.safe_patch_for_existing


def clean(value):
    return "" if value is None else str(value).strip()


def norm(value):
    return re.sub(r"\s+", " ", clean(value)).strip().casefold()


def nested_name(value):
    if isinstance(value, dict):
        return clean(value.get("name") or value.get("display") or value.get("model"))
    return clean(value)


def _generic_model(value):
    low = norm(value)
    if not low:
        return True
    markers = (
        "generic ", "unknown server", "generic unknown", "unknown dell server",
        "generic printer", "generic wireless", "generic network", "industrial device",
        "industrial switch", "generic storage",
    )
    return any(low == marker.strip() or low.startswith(marker) for marker in markers)


def _device_type_diff(row):
    found = []
    for diff in row.get("safe_diffs") or []:
        prefix = "device_type:SET:"
        if not clean(diff).startswith(prefix):
            continue
        value = clean(diff)[len(prefix):]
        if "|" not in value:
            raise RuntimeError("device_type safe diff inválido")
        manufacturer, model = value.split("|", 1)
        found.append((clean(manufacturer), clean(model)))
    if len(found) > 1:
        raise RuntimeError("mais de um device_type safe diff")
    return found[0] if found else ("", "")


def safe_patch_for_existing(row, current, catalog):
    payload = ORIG_SAFE_PATCH(row, current, catalog)
    manufacturer, model = _device_type_diff(row)
    if not manufacturer and not model:
        return payload

    if clean(current.get("description")) != PRODUCT_DEVICE_DESCRIPTION:
        raise RuntimeError("upgrade de Device Type exige Device criado pelo netbox-discovery")
    if clean(row.get("confidence")) != "HIGH":
        raise RuntimeError("upgrade de Device Type exige confiança HIGH")
    if clean(row.get("manufacturer")) != manufacturer or clean(row.get("model")) != model:
        raise RuntimeError("device_type safe diff diverge do PLAN")
    if not manufacturer or not model or _generic_model(model):
        raise RuntimeError("Device Type de destino não é identidade exata")

    dtype = current.get("device_type") or {}
    current_model = clean(dtype.get("model") if isinstance(dtype, dict) else "")
    if not _generic_model(current_model):
        raise RuntimeError("Device Type atual deixou de ser genérico: {0}".format(current_model))

    target = catalog.ensure_device_type(manufacturer, model)
    if not target or not target.get("id"):
        raise RuntimeError("Device Type exato sem ID: {0}/{1}".format(manufacturer, model))
    payload["device_type"] = target["id"]
    return payload


def refresh_plan():
    planner = os.path.join(BASE, "modules", "inventory", "planner_v8.py")
    if not os.path.isfile(planner):
        raise RuntimeError("Planner V8 não encontrado: {0}".format(planner))
    v4.base.subprocess.check_call([sys.executable, planner])
    path = v4._latest(os.path.join(REPORTS, "*-plan-*.json"))
    if not path:
        raise RuntimeError("PLAN V8 não gerou JSON")
    return path


def main(argv=None):
    old_refresh = v7.refresh_plan
    old_version = v8.IMPORTER_VERSION
    old_patch = v4.base.safe_patch_for_existing
    old_print = builtins.print

    def release_print(*args, **kwargs):
        if args and str(args[0]) == "===== IMPORT FINALIZE 1.10.18 =====":
            args = ("===== IMPORT FINALIZE 1.10.19 =====",) + tuple(args[1:])
        return old_print(*args, **kwargs)

    try:
        v7.refresh_plan = refresh_plan
        v8.IMPORTER_VERSION = IMPORTER_VERSION
        v4.base.safe_patch_for_existing = safe_patch_for_existing
        builtins.print = release_print
        return v8.main(argv)
    finally:
        builtins.print = old_print
        v4.base.safe_patch_for_existing = old_patch
        v8.IMPORTER_VERSION = old_version
        v7.refresh_plan = old_refresh


if __name__ == "__main__":
    sys.exit(main())
