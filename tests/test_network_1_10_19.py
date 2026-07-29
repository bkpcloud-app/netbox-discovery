#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.discovery import network_v4
from modules.inventory import classifier_v6, planner_v8
from modules.importers import importer_v9


def test_printer_model_patterns():
    assert network_v4._printer_manufacturer("KYOCERA ECOSYS M2040dn") == "Kyocera"
    assert network_v4._printer_model("KYOCERA ECOSYS M2040dn", "Kyocera") == "ECOSYS M2040dn"
    assert network_v4._printer_manufacturer("Pantum BM5100FDW") == "Pantum"
    assert network_v4._printer_model("Pantum BM5100FDW", "Pantum") == "BM5100FDW"


def test_classifier_moxa_nport_exact_oid():
    row = {
        "role": "WEB_APPLIANCE", "manufacturer": "", "model": "",
        "classification_score": 52, "confidence": "LOW", "asset_class": "HOST_OR_APPLIANCE",
        "evidence": [],
    }
    classifier_v6._apply_moxa_nport(row, {
        "snmp_object_id": classifier_v6.MOXA_NPORT_5210_OID,
        "snmp_name": "NP5210_4618",
    })
    assert row["role"] == "INDUSTRIAL_COMMUNICATION"
    assert row["manufacturer"] == "Moxa"
    assert row["model"] == "NPort 5210"
    assert row["confidence"] == "HIGH"


def test_collision_safe_names_require_strong_physical_identity():
    plan = [
        {
            "asset_id": "a", "decision": "BLOCKED", "action": "CREATE",
            "desired_name": "SW-BA17", "confidence": "HIGH", "existing_device_id": None,
            "reasons": ["DUPLICATE_DESIRED_NAME", "RECONCILE_REVIEW_CANDIDATE"],
        },
        {
            "asset_id": "b", "decision": "BLOCKED", "action": "CREATE",
            "desired_name": "SW-BA17", "confidence": "HIGH", "existing_device_id": None,
            "reasons": ["DUPLICATE_DESIRED_NAME", "RECONCILE_REVIEW_CANDIDATE"],
        },
    ]
    assets = {
        "a": {"asset_class": "PHYSICAL_DEVICE", "serial": "TW37LB43JZ", "macs": ["88:25:10:92:68:83"]},
        "b": {"asset_class": "PHYSICAL_DEVICE", "serial": "TW37KPC2C1", "macs": ["0C:97:5F:E1:DD:13"]},
    }
    planner_v8._resolve_strong_name_collisions(plan, assets, {"devices": []})
    assert plan[0]["decision"] == "READY"
    assert plan[1]["decision"] == "READY"
    assert plan[0]["desired_name"] == "SW-BA17-LB43JZ"
    assert plan[1]["desired_name"] == "SW-BA17-KPC2C1"
    assert plan[0]["desired_name"] != plan[1]["desired_name"]


def test_product_generic_type_upgrade_is_safe_update():
    row = {
        "decision": "REVIEW", "action": "NOOP", "confidence": "HIGH",
        "match_reason": "MAC+IP", "manufacturer": "Kyocera", "model": "ECOSYS M2040dn",
        "reasons": ["DEVICE_TYPE_DRIFT:Unidentified/Generic Printer->Kyocera/ECOSYS M2040dn"],
        "safe_diffs": [],
    }
    current = {
        "description": planner_v8.PRODUCT_DEVICE_DESCRIPTION,
        "device_type": {"model": "Generic Printer", "manufacturer": {"name": "Unidentified"}},
        "role": {"name": "PRINTER"}, "platform": None, "name": "IMP-01",
    }
    assert planner_v8._safe_generic_type_upgrade(row, current) is True
    assert row["decision"] == "READY"
    assert row["action"] == "UPDATE_SAFE"
    assert "device_type:SET:Kyocera|ECOSYS M2040dn" in row["safe_diffs"]


def test_importer_revalidates_generic_type_before_patch():
    class Catalog(object):
        def ensure_device_type(self, manufacturer, model):
            assert manufacturer == "Kyocera"
            assert model == "ECOSYS M2040dn"
            return {"id": 901}
        def ensure_role(self, name):
            return {"id": 1}
        def ensure_platform(self, name):
            return {"id": 2}

    row = {
        "confidence": "HIGH", "manufacturer": "Kyocera", "model": "ECOSYS M2040dn",
        "safe_diffs": ["device_type:SET:Kyocera|ECOSYS M2040dn"],
        "serial": "", "target_role": "PRINTER", "platform": "",
    }
    current = {
        "description": importer_v9.PRODUCT_DEVICE_DESCRIPTION,
        "device_type": {"model": "Generic Printer"},
        "serial": "", "role": {"id": 1}, "platform": None,
    }
    patch = importer_v9.safe_patch_for_existing(row, current, Catalog())
    assert patch["device_type"] == 901


def test_live_manufacturer_alias_removes_false_drift():
    row = {
        "manufacturer": "Dell", "model": "PowerEdge R650",
        "reasons": ["DEVICE_TYPE_DRIFT:Dell Inc./PowerEdge R650->Dell/PowerEdge R650"],
    }
    current = {
        "device_type": {"manufacturer": {"name": "Dell Inc."}, "model": "PowerEdge R650"},
        "role": {"name": "HYPERVISOR"}, "platform": {"name": "VMware ESXi"}, "name": "VM-01",
    }
    planner_v8._apply_manufacturer_alias(row, current)
    assert row["manufacturer"] == "Dell Inc."
    assert not row["reasons"]


def main():
    tests = [
        test_printer_model_patterns,
        test_classifier_moxa_nport_exact_oid,
        test_collision_safe_names_require_strong_physical_identity,
        test_product_generic_type_upgrade_is_safe_update,
        test_importer_revalidates_generic_type_before_patch,
        test_live_manufacturer_alias_removes_false_drift,
    ]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.10.19 IDENTITY QUALITY TESTS PASSED")


if __name__ == "__main__":
    main()
