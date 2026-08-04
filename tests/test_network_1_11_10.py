#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.auditors import auditor_v11
from modules.importers import importer_v12
from modules.product import runner


def _printer_row():
    return {
        "asset_id": "SERIAL:ZDEJB07KA24BRWA",
        "existing_device_id": 480,
        "desired_name": "imp-ba01",
        "effective_name": "imp-ba01",
        "decision": "READY",
        "action": "UPDATE_SAFE",
        "confidence": "HIGH",
        "identity_policy": "UPGRADE_PRODUCT_GENERIC_TYPE",
        "manufacturer": "Samsung",
        "model": "SL-M4020ND",
        "serial": "ZDEJB07KA24BRWA",
        "ips": ["10.2.2.80"],
        "primary_ip": "10.2.2.80",
        "safe_diffs": ["device_type:SET:Samsung|SL-M4020ND"],
        "interfaces": [],
        "ip_intents": [],
    }


def test_01_component_versions():
    assert importer_v12.IMPORTER_VERSION == "6.1-product"
    assert auditor_v11.AUDITOR_VERSION == "6.9-product"
    assert runner.RUNNER_VERSION == "3.3-product"
    assert runner.COMPONENTS["importer"] == "importer_v12.py"
    assert runner.COMPONENTS["auditor"] == "auditor_v11.py"


def test_02_duplicate_module_aliases_are_explicit():
    assert importer_v12.package_base is not importer_v12.v2.base
    assert auditor_v11.package_base is not auditor_v11.v2.base


def test_03_importer_propagates_planner_and_patch_to_real_alias():
    original = importer_v12.v11.main
    observed = {}

    def fake_main(argv):
        observed["argv"] = list(argv)
        modules = (
            importer_v12.v11, importer_v12.v11.v10, importer_v12.v11.v9,
            importer_v12.v11.v8, importer_v12.v11.v7, importer_v12.v11.v6,
            importer_v12.v11.v5, importer_v12.v11.v4, importer_v12.v11.v3,
            importer_v12.v11.v2, importer_v12.package_base, importer_v12.v2.base,
        )
        for module in modules:
            if hasattr(module, "refresh_plan"):
                assert module.refresh_plan is importer_v12.refresh_plan
        assert importer_v12.package_base.safe_patch_for_existing is importer_v12.v11.safe_patch_for_existing
        assert importer_v12.v2.base.safe_patch_for_existing is importer_v12.v11.safe_patch_for_existing
        assert importer_v12.v11.IMPORTER_VERSION == "6.1-product"
        return 0

    importer_v12.v11.main = fake_main
    try:
        assert importer_v12.main(["--no-refresh-plan"]) == 0
    finally:
        importer_v12.v11.main = original
    assert observed["argv"] == ["--no-refresh-plan"]


def test_04_importer_uses_real_sys_argv_when_argv_is_none():
    original_main = importer_v12.v11.main
    original_argv = list(sys.argv)
    captured = []

    def fake_main(argv):
        captured.extend(argv)
        return 0

    importer_v12.v11.main = fake_main
    sys.argv = ["importer_v12.py", "--no-refresh-plan"]
    try:
        assert importer_v12.main(None) == 0
    finally:
        sys.argv = original_argv
        importer_v12.v11.main = original_main
    assert captured == ["--no-refresh-plan"]


def test_05_auditor_propagates_planner_and_stable_idempotency():
    original = auditor_v11.v10.main

    def fake_main(argv):
        modules = (
            auditor_v11.v10, auditor_v11.v10.v9, auditor_v11.v10.v8,
            auditor_v11.v10.v7, auditor_v11.v10.v6, auditor_v11.v10.v5,
            auditor_v11.v10.v4, auditor_v11.v10.v3, auditor_v11.v10.v2,
            auditor_v11.package_base, auditor_v11.v2.base,
        )
        for module in modules:
            if hasattr(module, "generate_fresh_plan"):
                assert module.generate_fresh_plan is auditor_v11.generate_fresh_plan
        assert auditor_v11.package_base.audit_idempotency is auditor_v11.v10.audit_idempotency
        assert auditor_v11.v2.base.audit_idempotency is auditor_v11.v10.audit_idempotency
        assert auditor_v11.v2.base.compare_expected_inventory is auditor_v11.v10.compare_expected_inventory
        return 0

    auditor_v11.v10.main = fake_main
    try:
        assert auditor_v11.main([]) == 0
    finally:
        auditor_v11.v10.main = original


def test_06_stable_idempotency_ignores_preserved_name():
    original = {
        "asset_id": "SERIAL:1V683V1",
        "desired_name": "VM-BA02",
        "primary_ip": "10.2.1.22",
        "serial": "1V683V1",
        "decision": "READY",
        "action": "NOOP",
        "ip_intents": [],
    }
    fresh = dict(original)
    fresh["desired_name"] = "OUTRO-NOME-PRESERVADO"
    checks = []
    auditor_v11.v10.audit_idempotency([original], {"records": [fresh]}, checks)
    assert any(row.get("code") == "IDEMPOTENCY_NOOP" for row in checks)
    assert not any(row.get("severity") == "FAIL" for row in checks)


class FakeNetBox(object):
    def __init__(self):
        self.tenant = {"id": 1, "name": "MIZU"}
        self.site = {"id": 2, "name": "FBA"}
        self.manufacturers = [
            {"id": 10, "name": "Unidentified", "slug": "unidentified"},
        ]
        self.types = [
            {
                "id": 20,
                "manufacturer": self.manufacturers[0],
                "model": "Generic Printer",
                "slug": "unidentified-generic-printer",
            },
        ]
        self.device = {
            "id": 480,
            "name": "imp-ba01",
            "serial": "ZDEJB07KA24BRWA",
            "description": "Criado pelo netbox-discovery",
            "tenant": self.tenant,
            "site": self.site,
            "role": {"id": 5, "name": "PRINTER"},
            "device_type": self.types[0],
        }
        self.next_id = 100

    def get_all(self, path):
        endpoint = path.split("?", 1)[0]
        if endpoint == "tenancy/tenants/":
            return [self.tenant]
        if endpoint == "dcim/sites/":
            return [self.site]
        if endpoint == "dcim/device-roles/":
            return []
        if endpoint == "dcim/manufacturers/":
            return list(self.manufacturers)
        if endpoint == "dcim/device-types/":
            return list(self.types)
        if endpoint == "dcim/platforms/":
            return []
        if endpoint == "ipam/ip-addresses/":
            return []
        raise AssertionError("endpoint inesperado: " + endpoint)

    def get(self, path):
        if path == "dcim/devices/480/":
            return dict(self.device)
        raise AssertionError("GET inesperado: " + path)

    def post(self, path, payload):
        self.next_id += 1
        if path == "dcim/manufacturers/":
            row = {"id": self.next_id, "name": payload["name"], "slug": payload["slug"]}
            self.manufacturers.append(row)
            return row
        if path == "dcim/device-types/":
            manufacturer = [row for row in self.manufacturers if row["id"] == payload["manufacturer"]][0]
            row = {
                "id": self.next_id,
                "manufacturer": manufacturer,
                "model": payload["model"],
                "slug": payload["slug"],
            }
            self.types.append(row)
            return row
        raise AssertionError("POST inesperado: " + path)

    def patch(self, path, payload):
        if path == "dcim/devices/480/":
            target_id = payload.get("device_type")
            target = [row for row in self.types if row["id"] == target_id][0]
            self.device["device_type"] = target
            return dict(self.device)
        raise AssertionError("PATCH inesperado: " + path)


def test_07_device_type_is_written_and_read_back():
    tmp = tempfile.mkdtemp(prefix="nbd-1110-")
    original_reports = importer_v12.REPORTS
    original_netbox = importer_v12.NetBox
    fake = FakeNetBox()
    plan_path = os.path.join(tmp, "FBA-plan.json")
    with open(plan_path, "w") as handle:
        json.dump({
            "stage": "PLAN",
            "client": "MIZU",
            "site": "FBA",
            "records": [_printer_row()],
            "netbox_write": False,
        }, handle)
    importer_v12.REPORTS = tmp
    importer_v12.NetBox = lambda: fake
    try:
        report = importer_v12.apply_and_verify_device_types(plan_path)
        data = json.load(open(report, "r"))
    finally:
        importer_v12.NetBox = original_netbox
        importer_v12.REPORTS = original_reports
        shutil.rmtree(tmp)
    assert data["status"] == "PASS"
    assert data["updated"] == 1
    assert data["verified"] == 1
    manufacturer, model = importer_v12.v11._current_device_type(fake.device)
    assert manufacturer == "Samsung"
    assert model == "SL-M4020ND"


def test_08_safe_patch_reaches_device_type_only_diff():
    class Catalog(object):
        def ensure_device_type(self, manufacturer, model):
            assert manufacturer == "Samsung"
            assert model == "SL-M4020ND"
            return {"id": 77}

        def ensure_role(self, name):
            return {"id": 5}

        def ensure_platform(self, name):
            return {"id": 6}

    current = FakeNetBox().device
    payload = importer_v12.v11.safe_patch_for_existing(_printer_row(), current, Catalog())
    assert payload == {"device_type": 77}


def test_09_cli_and_runner_use_new_components():
    cli = open(os.path.join(BASE, "bin", "netbox-discovery"), "r").read()
    assert 'importer_v12.py' in cli
    assert 'auditor_v11.py' in cli
    assert 'IMPORT V12: OK' in cli
    assert 'AUDIT V11: OK' in cli
    assert 'importer_v11.py' not in runner.COMPONENTS.values()
    assert 'auditor_v10.py' not in runner.COMPONENTS.values()


def test_10_direct_entrypoints():
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    paths = (
        os.path.join(BASE, "modules", "importers", "importer_v12.py"),
        os.path.join(BASE, "modules", "auditors", "auditor_v11.py"),
    )
    for path in paths:
        assert subprocess.call([sys.executable, path, "--help"], cwd="/", env=env) == 0


def main():
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    assert len(tests) >= 10, len(tests)
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.11.10 IMPORT/AUDIT IDEMPOTENCY TESTS PASSED: {0}".format(len(tests)))


if __name__ == "__main__":
    main()
