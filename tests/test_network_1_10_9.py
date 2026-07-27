#!/usr/bin/env python3
import io
import json
import os
import shutil
import sys
import tempfile
from contextlib import redirect_stdout

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
sys.path.insert(0, BASE)

from modules.inventory import pipeline


def _write(path, data):
    with open(path, "w") as handle:
        json.dump(data, handle)


def test_network_plan_diagnostics_lists_ready_review_blocked_and_evidence():
    root = tempfile.mkdtemp(prefix="netbox-network-diag-")
    try:
        classification = os.path.join(root, "DCM-classification.json")
        plan = os.path.join(root, "DCM-plan.json")
        _write(classification, {
            "records": [
                {
                    "ip": "10.1.1.31",
                    "snmp_name": "SW-DCM-SERVERS",
                    "snmp_object_id": "1.3.6.1.4.1.11",
                    "management_mac": "00:11:22:33:44:55",
                    "evidence": ["Managed switch fingerprint", "manufacturer:entity-mib"],
                },
                {
                    "ip": "10.1.1.20",
                    "snmp_name": "vcsa",
                    "snmp_object_id": "",
                    "management_mac": "00:50:56:AA:BB:CC",
                    "evidence": ["VMware service/TLS fingerprint without ESXi proof"],
                },
            ]
        })
        _write(plan, {
            "planner_version": "4.0-product",
            "records": [
                {
                    "decision": "READY", "action": "CREATE",
                    "primary_ip": "10.1.1.31", "desired_name": "SW-DCM-SERVERS",
                    "role": "NETWORK_SWITCH", "confidence": "HIGH",
                    "manufacturer": "HPE Aruba", "model": "Generic Network Switch",
                },
                {
                    "decision": "REVIEW", "action": "CREATE",
                    "primary_ip": "10.1.1.20", "desired_name": "vcsa",
                    "role": "VMWARE_APPLIANCE", "confidence": "MEDIUM",
                    "classification_score": 82,
                    "manufacturer": "VMware", "model": "",
                    "serial": "", "match_state": "NEW", "match_reason": "Sem correspondência",
                    "reasons": ["CONFIDENCE_MEDIUM", "IP_ASSIGNED_TO_EXTERNAL_OBJECT:10.1.1.20:virtualization.vminterface"],
                },
                {
                    "decision": "BLOCKED", "action": "CONFLICT",
                    "primary_ip": "10.1.1.50", "desired_name": "SW-SAN-AE1",
                    "role": "LINUX_HOST", "confidence": "HIGH",
                    "classification_score": 85,
                    "manufacturer": "Generic", "model": "Unknown Server",
                    "serial": "", "match_state": "CONFLICT",
                    "match_reason": "SERIAL/MAC/IP apontam para devices diferentes",
                    "reasons": ["IDENTITY_CONFLICT", "SERIAL/MAC/IP apontam para devices diferentes"],
                },
            ]
        })

        buf = io.StringIO()
        with redirect_stdout(buf):
            pipeline.print_plan_diagnostics(plan, classification)
        out = buf.getvalue()

        assert "===== NETWORK PLAN DIAGNÓSTICO =====" in out
        assert "READY/CREATE: 1" in out
        assert "REVIEW: 1" in out
        assert "BLOCKED: 1" in out
        assert "===== NETWORK PENDÊNCIAS POR MOTIVO =====" in out
        assert "CONFIDENCE_MEDIUM: 1" in out
        assert "IP_ASSIGNED_TO_EXTERNAL_OBJECT:10.1.1.20:virtualization.vminterface: 1" in out
        assert "SW-DCM-SERVERS" in out
        assert "vcsa" in out
        assert "SW-SAN-AE1" in out
        assert "Evidência CLASSIFY: VMware service/TLS fingerprint without ESXi proof" in out
        assert "NetBox write: NÃO" in out
    finally:
        shutil.rmtree(root)


def main():
    tests = [test_network_plan_diagnostics_lists_ready_review_blocked_and_evidence]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL 1.10.9 NETWORK DIAGNOSTIC TESTS PASSED")


if __name__ == "__main__":
    main()
