#!/usr/bin/env python3
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TESTS = os.path.join(ROOT, "tests")
BASE = os.path.join(ROOT, "netbox-discovery")
sys.path.insert(0, TESTS)
sys.path.insert(0, BASE)

import test_product_1_9 as legacy
from modules.product import updater


def test_release_version():
    root_version = open(os.path.join(ROOT, "VERSION"), "r").read().strip()
    package_version = open(os.path.join(BASE, "VERSION"), "r").read().strip()
    assert root_version == package_version == "1.10.13"
    assert updater.version_key("1.10.13") > updater.version_key("1.10.12")


def main():
    tests = [
        legacy.test_management_mac,
        legacy.test_secondary_mac_not_identity,
        legacy.test_topdata_rules,
        legacy.test_printer_vendor_normalization,
        legacy.test_plan_mac_match,
        legacy.test_import_refreshes_planner_v2,
        legacy.test_explicit_tenant_group_policy,
        legacy.test_vmware_dependency_set_is_minimal,
        legacy.test_hypervisor_collector_is_loaded_after_vendor,
        legacy.test_hypervisor_plan_issues_are_visible,
        legacy.test_hypervisor_secondary_bridge_ip_is_not_authoritative,
        legacy.test_hypervisor_apply_and_audit_force_v2_planner_and_client,
        legacy.test_hypervisor_audit_details_are_visible,
        test_release_version,
    ]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL LEGACY + RELEASE REGRESSIONS PASSED")


if __name__ == "__main__":
    main()
