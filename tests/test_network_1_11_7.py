#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from modules.discovery import network_v4
from modules.inventory import classifier_v8 as classifier
from modules.inventory import planner_v9 as planner


def test_01_samsung_sec_is_hostname_like():
    assert network_v4._printer_model_is_hostname("SEC30CDA7FFE27C", "SEC30CDA7FFE27C", "Samsung")


def test_02_kyocera_model_equal_name_is_valid():
    assert not network_v4._printer_model_is_hostname("ECOSYS M3655idn", "ECOSYS M3655idn", "Kyocera")


def test_03_pantum_model_equal_name_is_valid():
    assert not network_v4._printer_model_is_hostname("BM5100FDW", "BM5100FDW", "Pantum")


def test_04_brother_brn_is_hostname_like():
    assert network_v4._printer_model_is_hostname("BRN3C2AF4536FDE", "BRN3C2AF4536FDE", "Brother")


def test_05_hp_npi_is_hostname_like():
    assert network_v4._printer_model_is_hostname("NPIA1B2C3", "NPIA1B2C3", "HP")


def test_06_xerox_xrx_is_hostname_like():
    assert network_v4._printer_model_is_hostname("XRX001122AABBCC", "XRX001122AABBCC", "Xerox")


def test_07_epson_generated_name_is_hostname_like():
    assert network_v4._printer_model_is_hostname("EPSONA1B2C3", "EPSONA1B2C3", "Epson")


def test_08_canon_generated_name_is_hostname_like():
    assert network_v4._printer_model_is_hostname("CANONA1B2C3", "CANONA1B2C3", "Canon")


def _printer_entity(manufacturer_text, name, serial):
    original_walk = network_v4.base._snmp_walk
    original_context = network_v4.base.snmp_command_context

    def fake_context(snmp):
        return "-v2c", "public"

    def fake_walk(ip, version, community, root, timeout=8):
        if root == network_v4.PRT_GENERAL_ROOT:
            return [
                (root + ".16.1", "STRING", name),
                (root + ".17.1", "STRING", serial),
            ]
        if root == network_v4.HR_DEVICE_DESCR:
            return [(root + ".1", "STRING", manufacturer_text)]
        return []

    try:
        network_v4.base.snmp_command_context = fake_context
        network_v4.base._snmp_walk = fake_walk
        return network_v4._printer_entity("10.0.0.10", {"available": True})
    finally:
        network_v4.base._snmp_walk = original_walk
        network_v4.base.snmp_command_context = original_context


def test_09_samsung_entity_drops_generated_hostname_model():
    row = _printer_entity("Samsung SEC30CDA7FFE27C", "SEC30CDA7FFE27C", "ZDEJBQAJ20003SL")
    assert row["manufacturer"] == "Samsung"
    assert row["model"] == ""
    assert row["serial"] == "ZDEJBQAJ20003SL"


def test_10_kyocera_entity_retains_real_model():
    row = _printer_entity("Kyocera ECOSYS M3655idn", "ECOSYS M3655idn", "R4P1Y94076")
    assert row["manufacturer"] == "Kyocera"
    assert row["model"] == "ECOSYS M3655idn"


def test_11_pantum_entity_retains_real_model():
    row = _printer_entity("Pantum BM5100FDW", "BM5100FDW", "PANTUM12345")
    assert row["manufacturer"] == "Pantum"
    assert row["model"] == "BM5100FDW"


def _printer_out(manufacturer, model, observed):
    return {
        "role": "PRINTER",
        "manufacturer": manufacturer,
        "model": model,
        "observed_name": observed,
        "identity_provenance": {"model": "printer-mib"},
    }


def test_12_classifier_rejects_samsung_generated_model():
    out = _printer_out("Samsung", "SEC30CDA7FFE27C", "SEC30CDA7FFE27C")
    classifier._sanitize_printer_model({"snmp_name": "SEC30CDA7FFE27C"}, out)
    assert out["model"] == ""
    assert out["model_rejection"]["reason"] == "printer-hostname-not-model"


def test_13_classifier_keeps_kyocera_model_equal_name():
    out = _printer_out("Kyocera", "ECOSYS M3655idn", "ECOSYS M3655idn")
    classifier._sanitize_printer_model({"snmp_name": "ECOSYS M3655idn"}, out)
    assert out["model"] == "ECOSYS M3655idn"
    assert "model_rejection" not in out


def test_14_classifier_keeps_pantum_model_equal_name():
    out = _printer_out("Pantum", "BM5100FDW", "BM5100FDW")
    classifier._sanitize_printer_model({"snmp_name": "BM5100FDW"}, out)
    assert out["model"] == "BM5100FDW"


def test_15_generic_printer_placeholder_is_generic():
    assert planner._generic_model("Printer-MIB managed printer")


def _printer_update(model, diffs, provenance="printer-mib"):
    row = {
        "role": "PRINTER",
        "model": model,
        "decision": "READY",
        "action": "UPDATE_SAFE",
        "safe_diffs": list(diffs),
        "reasons": ["PRODUCT_GENERIC_DEVICE_TYPE_UPGRADE"],
        "existing_device_id": 10,
    }
    class_row = {
        "role": "PRINTER",
        "model": model,
        "identity_provenance": {"model": provenance},
    }
    return row, class_row


def test_16_generic_device_type_diff_is_suppressed():
    row, class_row = _printer_update(
        "Printer-MIB managed printer",
        ["serial:SET:ABC12345", "device_type:SET:Samsung|Printer-MIB managed printer"],
        "rejected-hostname-like-model",
    )
    planner._suppress_untrusted_printer_device_type(row, class_row, {"id": 10})
    assert row["safe_diffs"] == ["serial:SET:ABC12345"]
    assert row["action"] == "UPDATE_SAFE"


def test_17_serial_only_update_remains_update_safe():
    row, class_row = _printer_update("", ["serial:SET:ABC12345"], "")
    planner._suppress_untrusted_printer_device_type(row, class_row, {"id": 10})
    assert row["action"] == "UPDATE_SAFE"
    assert row["safe_diffs"] == ["serial:SET:ABC12345"]


def test_18_generic_only_update_becomes_noop():
    row, class_row = _printer_update(
        "Generic Printer",
        ["device_type:SET:Samsung|Generic Printer"],
        "generic",
    )
    planner._suppress_untrusted_printer_device_type(row, class_row, {"id": 10})
    assert row["action"] == "NOOP"
    assert row["safe_diffs"] == []


def test_19_specific_kyocera_type_diff_is_preserved():
    row, class_row = _printer_update(
        "ECOSYS M3655idn",
        ["device_type:SET:Kyocera|ECOSYS M3655idn"],
    )
    planner._suppress_untrusted_printer_device_type(row, class_row, {"id": 10})
    assert row["safe_diffs"] == ["device_type:SET:Kyocera|ECOSYS M3655idn"]


def test_20_specific_pantum_type_diff_is_preserved():
    row, class_row = _printer_update("BM5100FDW", ["device_type:SET:Pantum|BM5100FDW"])
    planner._suppress_untrusted_printer_device_type(row, class_row, {"id": 10})
    assert row["safe_diffs"] == ["device_type:SET:Pantum|BM5100FDW"]


def test_21_specific_samsung_sl_type_diff_is_preserved():
    row, class_row = _printer_update("SL-M4020ND", ["device_type:SET:Samsung|SL-M4020ND"])
    planner._suppress_untrusted_printer_device_type(row, class_row, {"id": 10})
    assert row["safe_diffs"] == ["device_type:SET:Samsung|SL-M4020ND"]


def test_22_new_printer_without_specific_model_is_review():
    row = {
        "role": "PRINTER", "model": "Generic Printer", "decision": "READY", "action": "CREATE",
        "interfaces": [{"name": "MGMT"}], "ip_intents": [{"action": "ENSURE"}], "reasons": [],
    }
    class_row = {"role": "PRINTER", "model": "Generic Printer", "identity_provenance": {"model": "generic"}}
    planner._suppress_untrusted_printer_device_type(row, class_row, None)
    assert row["decision"] == "REVIEW"
    assert row["action"] == "NOOP"


def test_23_new_printer_with_specific_model_is_not_downgraded():
    row = {
        "role": "PRINTER", "model": "DCP-L5502DN", "decision": "READY", "action": "CREATE",
        "interfaces": [{"name": "MGMT"}], "ip_intents": [{"action": "ENSURE"}], "reasons": [],
    }
    class_row = {"role": "PRINTER", "model": "DCP-L5502DN", "identity_provenance": {"model": "printer-mib"}}
    planner._suppress_untrusted_printer_device_type(row, class_row, None)
    assert row["decision"] == "READY"
    assert row["action"] == "CREATE"


def _physical_row(uid, role="INDUSTRIAL_COMMUNICATION"):
    return {
        "role": role,
        "asset_class": "PHYSICAL_DEVICE",
        "decision": "READY",
        "action": "CREATE",
        "discovery_uid": uid,
        "interfaces": [{"name": "MGMT"}],
        "ip_intents": [{"action": "ENSURE"}],
        "reasons": [],
    }


def test_24_new_physical_weak_identity_is_review():
    row = _physical_row("WEAK:7275627C14CBD9FC")
    planner._new_physical_identity_policy(row, {"discovery_uid": row["discovery_uid"]}, None)
    assert row["decision"] == "REVIEW"
    assert row["action"] == "NOOP"


def test_25_new_physical_management_mac_remains_ready():
    row = _physical_row("MGMT-MAC:00:11:22:33:44:55", "WIRELESS_AP")
    planner._new_physical_identity_policy(row, {"discovery_uid": row["discovery_uid"]}, None)
    assert row["decision"] == "READY"


def test_26_new_physical_serial_remains_ready():
    row = _physical_row("SERIAL:brother:U64189C8N703205", "PRINTER")
    planner._new_physical_identity_policy(row, {"discovery_uid": row["discovery_uid"]}, None)
    assert row["decision"] == "READY"


def _windows_row(uid):
    return {
        "role": "WINDOWS_WORKSTATION", "target_role": "WINDOWS_WORKSTATION",
        "manufacturer": "Unidentified", "model": "Unknown Server", "confidence": "HIGH",
        "decision": "READY", "action": "CREATE", "safe_diffs": [], "reasons": [],
        "match_state": "NEW", "discovery_uid": uid,
        "interfaces": [{"name": "MGMT"}], "ip_intents": [{"action": "ENSURE"}],
    }


def _windows_class(uid):
    return {
        "role": "WINDOWS_WORKSTATION", "confidence": "HIGH", "windows_product": "Windows 11",
        "windows_evidence_source": "smb-os-discovery", "windows_evidence_rank": 110,
        "discovery_uid": uid, "serial": "", "serial_confidence": "NONE",
    }


def test_27_new_windows_weak_identity_remains_review():
    row = _windows_row("WEAK:8D5A7F409E09E87E")
    planner._windows_plan_policy(row, _windows_class(row["discovery_uid"]), None)
    assert row["decision"] == "REVIEW"


def test_28_new_windows_management_mac_remains_ready():
    row = _windows_row("MGMT-MAC:00:11:22:33:44:55")
    planner._windows_plan_policy(row, _windows_class(row["discovery_uid"]), None)
    assert row["decision"] == "READY"


def test_29_review_only_generic_prerequisite_is_removed():
    plan = [{
        "decision": "REVIEW", "action": "NOOP", "role": "PRINTER", "target_role": "PRINTER",
        "manufacturer": "Samsung", "model": "Printer-MIB managed printer", "safe_diffs": [],
    }]
    prereq = {
        "roles": [{"name": "PRINTER", "slug": "printer"}],
        "manufacturers": [{"name": "Samsung", "slug": "samsung"}],
        "platforms": [],
        "device_types": [{"manufacturer": "Samsung", "model": "Printer-MIB managed printer", "slug": "bad"}],
    }
    planner._prune_prerequisites_to_ready_actions(plan, prereq)
    assert prereq["device_types"] == []
    assert prereq["manufacturers"] == []


def test_30_ready_create_specific_prerequisites_are_retained():
    plan = [{
        "decision": "READY", "action": "CREATE", "role": "PRINTER", "target_role": "PRINTER",
        "manufacturer": "Brother", "model": "DCP-L5502DN", "platform": "", "safe_diffs": [],
    }]
    prereq = {
        "roles": [{"name": "PRINTER", "slug": "printer"}],
        "manufacturers": [{"name": "Brother", "slug": "brother"}],
        "platforms": [],
        "device_types": [{"manufacturer": "Brother", "model": "DCP-L5502DN", "slug": "brother-dcp"}],
    }
    planner._prune_prerequisites_to_ready_actions(plan, prereq)
    assert len(prereq["roles"]) == 1
    assert len(prereq["manufacturers"]) == 1
    assert len(prereq["device_types"]) == 1


def test_31_serial_only_update_needs_no_catalog_prerequisite():
    plan = [{
        "decision": "READY", "action": "UPDATE_SAFE", "safe_diffs": ["serial:SET:ABC12345"],
    }]
    prereq = {
        "roles": [{"name": "PRINTER"}], "manufacturers": [{"name": "Samsung"}],
        "platforms": [], "device_types": [{"manufacturer": "Samsung", "model": "Generic Printer"}],
    }
    planner._prune_prerequisites_to_ready_actions(plan, prereq)
    assert all(prereq[key] == [] for key in prereq)


def test_32_device_type_update_retains_exact_catalog_prerequisite():
    plan = [{
        "decision": "READY", "action": "UPDATE_SAFE",
        "safe_diffs": ["device_type:SET:Kyocera|ECOSYS M3655idn"],
    }]
    prereq = {
        "roles": [], "manufacturers": [{"name": "Kyocera"}], "platforms": [],
        "device_types": [{"manufacturer": "Kyocera", "model": "ECOSYS M3655idn"}],
    }
    planner._prune_prerequisites_to_ready_actions(plan, prereq)
    assert len(prereq["manufacturers"]) == 1
    assert len(prereq["device_types"]) == 1


def test_33_brother_serial_is_accepted():
    serial, reason = classifier._validate_serial("U64189M8N960565", [])
    assert serial == "U64189M8N960565" and reason == ""


def test_34_real_mac_is_rejected_as_serial():
    serial, reason = classifier._validate_serial("64:18:98:96:05:65", [])
    assert serial == "" and reason == "mac-address"


def test_35_known_placeholder_is_rejected():
    serial, reason = classifier._validate_serial("123456789012", [])
    assert serial == "" and reason == "known-placeholder"


def test_36_duplicate_serial_rejections_are_collapsed():
    out = {"serial_rejections": [
        {"value": "ABC12345", "source": "printer-mib", "reason": "known-placeholder"},
        {"value": "ABC12345", "source": "printer-mib-candidate", "reason": "known-placeholder"},
    ]}
    classifier._dedupe_serial_rejections(out)
    assert len(out["serial_rejections"]) == 1


def main():
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    assert len(tests) >= 30, len(tests)
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.11.7 30-POINT AUDIT TESTS PASSED: {0}".format(len(tests)))


if __name__ == "__main__":
    main()
