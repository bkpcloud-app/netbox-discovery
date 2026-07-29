#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import builtins
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from modules.importers import importer as base
from modules.importers import importer_v7 as v7
from modules.importers import importer_v8 as v8

IMPORTER_VERSION = "5.7-product"
BASE = v7.BASE
REPORTS = v7.REPORTS
PRODUCT_DEVICE_DESCRIPTION = "Criado pelo netbox-discovery"
PRODUCT_INTERFACE_DESCRIPTION = "Gerenciamento criado pelo netbox-discovery"
RELATED_ENDPOINTS = (
    "dcim/inventory-items/", "dcim/console-ports/", "dcim/console-server-ports/",
    "dcim/power-ports/", "dcim/power-outlets/", "dcim/front-ports/",
    "dcim/rear-ports/", "dcim/device-bays/", "dcim/module-bays/",
)
ORIG_SAFE_PATCH = base.safe_patch_for_existing
ORIG_PREFLIGHT_READY = base.preflight_ready


def clean(value):
    return "" if value is None else str(value).strip()


def norm(value):
    return base.norm(value)


def _device_type_parts(device):
    dtype = device.get("device_type") or {}
    if not isinstance(dtype, dict):
        return "", ""
    manufacturer = base.nested_name(dtype.get("manufacturer"))
    model = clean(dtype.get("model") or dtype.get("display") or dtype.get("name"))
    return manufacturer, model


def _validate_upgrade_snapshot(row, current):
    upgrade = row.get("device_type_upgrade") or {}
    if clean(upgrade.get("mode")) != "UPGRADE_PRODUCT_GENERIC_PRINTER":
        return ""
    if current is None:
        return "Device alvo do upgrade não existe"
    if current.get("id") != upgrade.get("device_id"):
        return "Device alvo mudou: live={0}; esperado={1}".format(
            current.get("id"), upgrade.get("device_id"))
    if clean(current.get("description")) != clean(upgrade.get("expected_device_description")):
        return "Device não possui ownership do netbox-discovery"
    live_role = base.nested_name(current.get("role"))
    if norm(live_role) != norm(upgrade.get("expected_role")):
        return "Role live mudou: {0}".format(live_role)
    live_manufacturer, live_model = _device_type_parts(current)
    if norm(live_manufacturer) != norm(upgrade.get("expected_current_manufacturer")):
        return "Fabricante live mudou: {0}".format(live_manufacturer)
    if norm(live_model) != norm(upgrade.get("expected_current_model")):
        return "Modelo live mudou: {0}".format(live_model)
    return ""


def preflight_ready(ready, indexes, tenant):
    errors = list(ORIG_PREFLIGHT_READY(ready, indexes, tenant))
    for row in ready:
        upgrade = row.get("device_type_upgrade") or {}
        if not upgrade:
            continue
        current = indexes.get("by_id", {}).get(row.get("existing_device_id"))
        error = _validate_upgrade_snapshot(row, current)
        if error:
            label = clean(row.get("desired_name")) or clean(row.get("asset_id"))
            errors.append("{0}: printer upgrade bloqueado: {1}".format(label, error))
    return errors


def _validate_upgrade_live(nb, row, current):
    error = _validate_upgrade_snapshot(row, current)
    if error:
        raise RuntimeError(error)

    device_id = current.get("id")
    for field in ("rack", "location", "cluster", "virtual_chassis", "device_bay"):
        if base.nested_id(current.get(field)):
            raise RuntimeError("Device ganhou vínculo manual: {0}".format(field))

    interfaces = base.query(nb, "dcim/interfaces/", device_id=device_id, limit=1000)
    if not interfaces:
        raise RuntimeError("Device sem interface criada pelo produto")
    for interface in interfaces:
        if clean(interface.get("description")) != PRODUCT_INTERFACE_DESCRIPTION:
            raise RuntimeError("Device possui interface não criada pelo produto")
        if interface.get("cable") or interface.get("mark_connected"):
            raise RuntimeError("Device possui cabo/conexão manual")

    for endpoint in RELATED_ENDPOINTS:
        if base.query(nb, endpoint, device_id=device_id, limit=1):
            raise RuntimeError("Device possui objeto relacionado em {0}".format(endpoint))


def safe_patch_for_existing(row, current, catalog):
    payload = ORIG_SAFE_PATCH(row, current, catalog)
    upgrade = row.get("device_type_upgrade") or {}
    if clean(upgrade.get("mode")) != "UPGRADE_PRODUCT_GENERIC_PRINTER":
        return payload

    # Revalidate every ownership gate before creating catalog entries or
    # changing the Device Type. No name, role, IP, interface or serial is
    # replaced by this path.
    _validate_upgrade_live(catalog.nb, row, current)
    target_manufacturer = clean(upgrade.get("target_manufacturer"))
    target_model = clean(upgrade.get("target_model"))
    dtype = catalog.ensure_device_type(target_manufacturer, target_model)
    if not dtype.get("id"):
        raise RuntimeError("Device Type alvo sem ID: {0}/{1}".format(
            target_manufacturer, target_model))
    payload["device_type"] = dtype["id"]
    return payload


def refresh_plan():
    planner = os.path.join(BASE, "modules", "inventory", "planner_v8.py")
    if not os.path.isfile(planner):
        raise RuntimeError("Planner V8 não encontrado: {0}".format(planner))
    base.subprocess.check_call([sys.executable, planner])
    path = v7.v4._latest(os.path.join(REPORTS, "*-plan-*.json"))
    if not path:
        raise RuntimeError("PLAN V8 não gerou JSON")
    return path


def main(argv=None):
    old_refresh = v7.refresh_plan
    old_version = v8.IMPORTER_VERSION
    old_safe_patch = base.safe_patch_for_existing
    old_preflight = base.preflight_ready
    old_print = builtins.print

    def release_print(*args, **kwargs):
        if args and str(args[0]) == "===== IMPORT FINALIZE 1.10.18 =====":
            args = ("===== IMPORT FINALIZE 1.10.19 =====",) + tuple(args[1:])
        return old_print(*args, **kwargs)

    try:
        v7.refresh_plan = refresh_plan
        v8.IMPORTER_VERSION = IMPORTER_VERSION
        base.safe_patch_for_existing = safe_patch_for_existing
        base.preflight_ready = preflight_ready
        builtins.print = release_print
        return v8.main(argv)
    finally:
        builtins.print = old_print
        base.preflight_ready = old_preflight
        base.safe_patch_for_existing = old_safe_patch
        v8.IMPORTER_VERSION = old_version
        v7.refresh_plan = old_refresh


if __name__ == "__main__":
    sys.exit(main())
