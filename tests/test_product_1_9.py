#!/usr/bin/env python3
import hashlib
import os
import shutil
import sys
import tempfile
import types

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(ROOT, "netbox-discovery")
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "modules", "inventory"))
sys.path.insert(0, os.path.join(BASE, "modules", "importers"))

import classifier_v2
import reconciler_v2
import planner_v2
import importer_v2
from modules.product import updater
from modules.product import configurator_v2
from modules.hypervisor import deps_vmware
from modules.hypervisor import configurator as hypervisor_configurator


def service(port):
    return {"port": port, "protocol": "tcp", "service": "unknown", "scripts": {}}


def test_management_mac():
    row = {"ip":"10.1.1.50","mac":"00:11:22:33:44:55","snmp_ip_addresses":[{"address":"10.1.1.50","ifindex":"7"}],"snmp_interface_macs":[{"index":"1","mac":"00:AA:AA:AA:AA:AA"},{"index":"7","mac":"00:BB:BB:BB:BB:BB"}]}
    mac, source = classifier_v2.derive_management_mac(row)
    assert mac == "00:BB:BB:BB:BB:BB" and source == "snmp-ip-ifindex"


def test_secondary_mac_not_identity():
    row = {"serial":"","management_mac":"00:11:22:33:44:55","secondary_macs":["00:66:77:88:99:AA"],"snmp_lldp_chassis_id":""}
    serial, macs, chassis = reconciler_v2.identity_sets(row)
    assert serial == "" and macs == {"00:11:22:33:44:55"}
    assert "00:66:77:88:99:AA" not in macs


def test_topdata_rules():
    base = {"mac":"00:18:E2:01:02:03","snmp_interface_macs":[],"open_services":[service(3570)]}
    role, score, _ = classifier_v2.classify_role(base, "")
    assert role == "ACCESS_CONTROL" and score >= 85
    base["open_services"] = [service(51000)]
    role, score, _ = classifier_v2.classify_role(base, "")
    assert role == "TIME_ATTENDANCE" and score >= 85
    base["open_services"] = []
    role, _, _ = classifier_v2.classify_role(base, "")
    assert role not in ("ACCESS_CONTROL", "TIME_ATTENDANCE", "TURNSTILE")


def test_printer_vendor_normalization():
    assert classifier_v2.normalize_manufacturer("KYOCERA Document Solutions") == "Kyocera"
    assert classifier_v2.normalize_manufacturer("HP Inc.") == "HP"
    assert classifier_v2.normalize_manufacturer("Zebra Technologies") == "Zebra Technologies"


def test_plan_mac_match():
    asset = {"serial":"","macs":["00:11:22:33:44:55"],"ips":["10.1.1.99"],"oob_ips":[]}
    indexes = {"serials":{},"mac_to_devices":{"00:11:22:33:44:55":{9}},"ip_to_devices":{},"names":{},"by_id":{9:{"id":9,"name":"PRINTER01"}}}
    did, state, reason, votes = planner_v2.match_asset(asset, indexes, desired_name="PRINTER01")
    assert did == 9 and state == "MATCHED" and "MAC" in reason


def test_import_refreshes_planner_v2():
    called=[]; old_check=importer_v2.base.subprocess.check_call; old_latest=importer_v2.base.latest
    try:
        importer_v2.base.subprocess.check_call=lambda cmd: called.append(cmd)
        importer_v2.base.latest=lambda pattern:"/tmp/fake-plan-v2.json"
        path=importer_v2.refresh_plan()
        assert path=="/tmp/fake-plan-v2.json" and called and called[0][1].endswith("planner_v2.py")
    finally:
        importer_v2.base.subprocess.check_call=old_check; importer_v2.base.latest=old_latest


def test_explicit_tenant_group_policy():
    old_env=os.environ.pop("NETBOX_DISCOVERY_TENANT_GROUP",None)
    try:
        assert configurator_v2._tenant_group_for({})==""
        assert configurator_v2._tenant_group_for({"tenant":"MIZU"})==""
        assert configurator_v2._tenant_group_for({"tenant_group":"POLIMIX"})=="POLIMIX"
        assert configurator_v2.slugify("São Paulo DCM")=="sao-paulo-dcm"
    finally:
        if old_env is not None: os.environ["NETBOX_DISCOVERY_TENANT_GROUP"]=old_env


def test_vmware_dependency_set_is_minimal():
    assert deps_vmware.PACKAGES==["six==1.16.0","pyvmomi==7.0.3"]
    expected=hashlib.sha256(b"vmware=1\nhyperv=0\nsix==1.16.0\npyvmomi==7.0.3\n").hexdigest()
    assert deps_vmware.fingerprint()==expected


def test_hypervisor_collector_is_loaded_after_vendor():
    assert "modules.hypervisor.collectors" not in sys.modules
    tmp=tempfile.mkdtemp(prefix="nd-test-"); vendor=os.path.join(tmp,"vendor"); os.makedirs(vendor)
    old_base=hypervisor_configurator.BASE; fake=types.ModuleType("modules.hypervisor.collectors"); fake.check_source=lambda source:{"product":"fake","version":"1"}
    try:
        hypervisor_configurator.BASE=tmp; sys.modules["modules.hypervisor.collectors"]=fake
        result=hypervisor_configurator.check_source_ready({"type":"vmware"})
        assert result["product"]=="fake" and vendor in sys.path
    finally:
        hypervisor_configurator.BASE=old_base; sys.modules.pop("modules.hypervisor.collectors",None)
        while vendor in sys.path: sys.path.remove(vendor)
        shutil.rmtree(tmp)


def test_hypervisor_plan_issues_are_visible():
    from modules.hypervisor import runner
    plan={"records":[
        {"decision":"READY","object_type":"VM","desired_name":"OK","action":"CREATE","reason":"ok"},
        {"decision":"REVIEW","object_type":"VM","desired_name":"VM-DUP","action":"CREATE","reason":"IP duplicado"},
        {"decision":"BLOCKED","object_type":"HOST","desired_name":"ESX01","action":"NOOP","reason":"conflito"},
    ]}
    lines=runner.plan_issue_lines(plan)
    text="\n".join(lines)
    assert "VM-DUP" in text and "IP duplicado" in text
    assert "ESX01" in text and "conflito" in text
    assert "OK" not in text
    assert "PENDÊNCIAS TOTAIS: 2" in text


def test_versions():
    root_version=open(os.path.join(ROOT,"VERSION"),"r").read().strip()
    package_version=open(os.path.join(BASE,"VERSION"),"r").read().strip()
    assert root_version==package_version=="1.9.5"
    assert updater.version_key("1.9.5")>updater.version_key("1.9.4")


def main():
    tests=[test_management_mac,test_secondary_mac_not_identity,test_topdata_rules,test_printer_vendor_normalization,test_plan_mac_match,test_import_refreshes_planner_v2,test_explicit_tenant_group_policy,test_vmware_dependency_set_is_minimal,test_hypervisor_collector_is_loaded_after_vendor,test_hypervisor_plan_issues_are_visible,test_versions]
    for test in tests:
        test(); print("PASS",test.__name__)
    print("ALL TESTS PASSED")


if __name__=="__main__": main()
