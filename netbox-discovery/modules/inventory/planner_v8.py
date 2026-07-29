#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, "..", ".."))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.inventory import planner_v2 as v2
from modules.inventory import planner_v4 as v4
from modules.inventory import planner_v7 as v7
from modules.inventory import printer_identity

PLANNER_VERSION = "4.8-product"
ORIG_V7_BUILD_PLAN = v7.build_plan
GENERIC_PRINTER_MODELS = {"generic printer"}
GENERIC_MANUFACTURERS = {"", "generic", "unidentified", "unknown"}


def clean(value):
    return "" if value is None else str(value).strip()


def norm(value):
    return v2.base.norm(value)


def _device_type_parts(device):
    dtype = device.get("device_type") or {}
    if not isinstance(dtype, dict):
        return "", ""
    manufacturer = v2.base.flatten_name(dtype.get("manufacturer"))
    model = clean(dtype.get("model") or dtype.get("display") or dtype.get("name"))
    return manufacturer, model


def _interfaces_are_product_owned(state, device_id):
    interfaces = v4._device_interfaces(state, device_id)
    if not interfaces:
        return False, "Device sem interface criada pelo produto"
    for interface in interfaces:
        if clean(interface.get("description")) != v4.PRODUCT_INTERFACE_DESCRIPTION:
            return False, "Device possui interface não criada pelo produto"
        if interface.get("cable") or interface.get("mark_connected"):
            return False, "Device possui cabo/conexão manual"
    return True, ""


def _printer_upgrade(row, device, state):
    if clean(device.get("description")) != v4.PRODUCT_DEVICE_DESCRIPTION:
        return None, "Device não foi criado pelo netbox-discovery"
    if not v4._device_scope_is_empty(device):
        return None, "Device possui vínculo manual de rack/location/cluster"
    related = v4._device_has_related_objects(state, device.get("id"))
    if related:
        return None, "Device possui objetos relacionados: {0}".format(", ".join(related))
    interfaces_ok, interface_error = _interfaces_are_product_owned(state, device.get("id"))
    if not interfaces_ok:
        return None, interface_error

    live_role = v2.base.flatten_name(device.get("role"))
    if norm(live_role) != norm("PRINTER"):
        return None, "Role live não é PRINTER: {0}".format(live_role)

    current_manufacturer, current_model = _device_type_parts(device)
    target_manufacturer = clean(row.get("manufacturer"))
    target_model = clean(row.get("model"))

    if norm(current_model) not in GENERIC_PRINTER_MODELS:
        return None, "Device Type atual não é Generic Printer"
    if norm(current_manufacturer) not in GENERIC_MANUFACTURERS and norm(current_manufacturer) != norm(target_manufacturer):
        return None, "Fabricante live específico diverge: {0}".format(current_manufacturer)
    if not printer_identity.is_specific_manufacturer(target_manufacturer):
        return None, "Fabricante alvo ainda é genérico"
    if not target_model:
        target_model = "Generic Printer"
    if norm(current_manufacturer) == norm(target_manufacturer) and norm(current_model) == norm(target_model):
        return None, "Device Type já está correto"

    precision = "MODEL" if printer_identity.is_specific_model(target_model) else "MANUFACTURER"
    return {
        "mode": "UPGRADE_PRODUCT_GENERIC_PRINTER",
        "device_id": device.get("id"),
        "expected_device_description": v4.PRODUCT_DEVICE_DESCRIPTION,
        "expected_role": "PRINTER",
        "expected_current_manufacturer": current_manufacturer,
        "expected_current_model": current_model,
        "target_manufacturer": target_manufacturer,
        "target_model": target_model,
        "precision": precision,
    }, ""


def build_plan(recon, classification, state):
    plan, prereq = ORIG_V7_BUILD_PLAN(recon, classification, state)
    by_id = dict((item.get("id"), item) for item in (state.get("devices") or []) if item.get("id"))

    for row in plan:
        if clean(row.get("decision")) != "READY" or not row.get("existing_device_id"):
            continue
        if clean(row.get("role")) != "PRINTER" or clean(row.get("target_role")) != "PRINTER":
            continue
        if clean(row.get("confidence")) != "HIGH":
            continue

        device = by_id.get(row.get("existing_device_id"))
        if not device:
            continue
        upgrade, error = _printer_upgrade(row, device, state)
        if not upgrade:
            continue

        safe_diffs = list(row.get("safe_diffs") or [])
        marker = "device_type:UPGRADE_GENERIC:{0}|{1}".format(
            upgrade["target_manufacturer"], upgrade["target_model"])
        if marker not in safe_diffs:
            safe_diffs.append(marker)
        row["safe_diffs"] = safe_diffs
        row["device_type_upgrade"] = upgrade
        row["action"] = "UPDATE_SAFE"

    return plan, prereq


def main(argv=None):
    old_build = v7.build_plan
    old_version = v7.PLANNER_VERSION
    try:
        v7.build_plan = build_plan
        v7.PLANNER_VERSION = PLANNER_VERSION
        return v7.main(argv)
    finally:
        v7.PLANNER_VERSION = old_version
        v7.build_plan = old_build


if __name__ == "__main__":
    sys.exit(main())
