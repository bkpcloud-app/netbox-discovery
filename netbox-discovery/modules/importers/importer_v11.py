#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, "..", ".."))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.importers import importer as base_importer
from modules.importers import importer_v2 as v2
from modules.importers import importer_v3 as v3
from modules.importers import importer_v4 as v4
from modules.importers import importer_v5 as v5
from modules.importers import importer_v6 as v6
from modules.importers import importer_v7 as v7
from modules.importers import importer_v8 as v8
from modules.importers import importer_v9 as v9
from modules.importers import importer_v10 as v10

IMPORTER_VERSION = "6.0-product"
ORIG_SAFE_PATCH = v10.safe_patch_for_existing
PRODUCT_DEVICE_DESCRIPTION = "Criado pelo netbox-discovery"


def clean(value):
    return "" if value is None else str(value).strip()


def norm(value):
    return re.sub(r"\s+", " ", clean(value)).strip().casefold()


def nested_name(value):
    if isinstance(value, dict):
        return clean(value.get("name") or value.get("display") or value.get("model"))
    return clean(value)


def _device_type_diff(row):
    values = []
    for diff in row.get("safe_diffs") or []:
        text = clean(diff)
        prefix = "device_type:SET:"
        if not text.startswith(prefix):
            continue
        payload = text[len(prefix):]
        if "|" not in payload:
            raise RuntimeError("device_type safe diff inválido")
        manufacturer, model = payload.split("|", 1)
        values.append((clean(manufacturer), clean(model)))
    if len(values) > 1:
        raise RuntimeError("mais de um device_type safe diff")
    return values[0] if values else ("", "")


def _current_device_type(current):
    dtype = current.get("device_type") or {}
    if not isinstance(dtype, dict):
        return "", ""
    return nested_name(dtype.get("manufacturer")), clean(
        dtype.get("model") or dtype.get("display") or dtype.get("name")
    )


def _ensure_device_type_patch(payload, row, current, catalog):
    manufacturer, model = _device_type_diff(row)
    if not manufacturer and not model:
        return payload
    if not manufacturer or not model:
        raise RuntimeError("Device Type de destino incompleto")
    if clean(row.get("manufacturer")) != manufacturer or clean(row.get("model")) != model:
        raise RuntimeError("Device Type do PLAN diverge do safe diff")
    if clean(row.get("decision")) != "READY" or clean(row.get("action")) != "UPDATE_SAFE":
        raise RuntimeError("device_type patch exige READY/UPDATE_SAFE")
    if clean(current.get("description")) != PRODUCT_DEVICE_DESCRIPTION:
        raise RuntimeError("device_type patch exige Device criado pelo netbox-discovery")
    if clean(row.get("confidence")) != "HIGH":
        raise RuntimeError("device_type patch exige confiança HIGH")
    if clean(row.get("identity_policy")) != "UPGRADE_PRODUCT_GENERIC_TYPE":
        raise RuntimeError("device_type patch exige política de upgrade genérico")

    live_manufacturer, live_model = _current_device_type(current)
    if norm(live_manufacturer) == norm(manufacturer) and norm(live_model) == norm(model):
        payload.pop("device_type", None)
        return payload
    if not v9._generic_model(live_model):
        raise RuntimeError("Device Type atual deixou de ser genérico: {0}/{1}".format(
            live_manufacturer, live_model))
    if v9._generic_model(model):
        raise RuntimeError("Device Type de destino continua genérico: {0}".format(model))

    target = catalog.ensure_device_type(manufacturer, model)
    if not target or not target.get("id"):
        raise RuntimeError("Device Type de destino sem ID: {0}/{1}".format(manufacturer, model))
    payload["device_type"] = target["id"]
    return payload


def safe_patch_for_existing(row, current, catalog):
    payload = ORIG_SAFE_PATCH(row, current, catalog)
    _ensure_device_type_patch(payload, row, current, catalog)
    if "name" in payload:
        raise RuntimeError("política 1.11 proíbe alteração automática de nome")
    return payload


def refresh_plan():
    planner = os.path.join(BASE, "modules", "inventory", "planner_v10.py")
    if not os.path.isfile(planner):
        raise RuntimeError("Planner V10 não encontrado: {0}".format(planner))
    v4.base.subprocess.check_call([sys.executable, planner])
    path = v4._latest(os.path.join(v4.REPORTS, "*-plan-*.json"))
    if not path:
        raise RuntimeError("PLAN V10 não gerou JSON")
    return path


def main(argv=None):
    old_safe = v10.safe_patch_for_existing
    old_refresh = v10.refresh_plan
    modules = (base_importer, v2, v3, v4, v5, v6, v7, v8, v9, v10)
    old_versions = [getattr(module, "IMPORTER_VERSION", "") for module in modules]
    try:
        v10.safe_patch_for_existing = safe_patch_for_existing
        v10.refresh_plan = refresh_plan
        for module in modules:
            module.IMPORTER_VERSION = IMPORTER_VERSION
        return v10.main(argv)
    finally:
        v10.safe_patch_for_existing = old_safe
        v10.refresh_plan = old_refresh
        for module, value in zip(modules, old_versions):
            module.IMPORTER_VERSION = value


if __name__ == "__main__":
    raise SystemExit(main())
