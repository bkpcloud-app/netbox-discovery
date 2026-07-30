#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import argparse
import glob
import json
import os
import subprocess
import sys
from collections import Counter

BASE = os.environ.get("NETBOX_DISCOVERY_BASE", "/opt/netbox-discovery")
REPORTS = os.path.join(BASE, "reports")
HERE = os.path.dirname(os.path.abspath(__file__))
PIPELINE_VERSION = "3.0-product"


def latest(pattern):
    files = glob.glob(pattern)
    return max(files, key=os.path.getmtime) if files else ""


def clean(value):
    return "" if value is None else str(value).strip()


def _load_json(path):
    with open(path, "r") as handle:
        return json.load(handle)


def _classification_by_ip(classification):
    out = {}
    for row in classification.get("records") or []:
        ip = clean(row.get("ip")).split("/", 1)[0]
        if ip:
            out[ip] = row
    return out


def _format_list(values):
    return ", ".join(clean(x) for x in (values or []) if clean(x)) or "-"


def _print_identity(row, class_row):
    print("  Nome efetivo/observado: {0} / {1}".format(
        clean(row.get("effective_name") or row.get("desired_name")) or "-",
        clean(row.get("observed_name") or class_row.get("observed_name")) or "-",
    ))
    print("  Autoridade do nome: {0} | origem observada={1}".format(
        clean(row.get("name_authority")) or "-",
        clean(row.get("observed_name_source") or class_row.get("observed_name_source")) or "-",
    ))
    print("  Natureza: {0} | origem={1}".format(
        clean(row.get("asset_nature") or class_row.get("asset_nature")) or "-",
        clean(row.get("asset_nature_source") or class_row.get("asset_nature_source")) or "-",
    ))
    print("  Discovery UID: {0}".format(
        clean(row.get("discovery_uid") or class_row.get("discovery_uid")) or "-"
    ))
    provenance = row.get("identity_provenance") or class_row.get("identity_provenance") or {}
    if provenance:
        parts = ["{0}={1}".format(key, clean(value)) for key, value in sorted(provenance.items()) if clean(value)]
        if parts:
            print("  Proveniência: {0}".format(", ".join(parts)))


def _print_class_evidence(row, class_row):
    print("  Asset class: {0}".format(clean(row.get("asset_class")) or clean(class_row.get("asset_class")) or "-"))
    print("  SNMP: name={0} object_id={1} mgmt_mac={2}".format(
        clean(class_row.get("snmp_name")) or "-", clean(class_row.get("snmp_object_id")) or "-",
        clean(class_row.get("management_mac")) or "-",
    ))
    if class_row.get("printer_mib_detected"):
        print("  Printer-MIB: name={0} serial={1}".format(
            clean(class_row.get("printer_mib_name")) or "-",
            clean(class_row.get("printer_mib_serial")) or "-",
        ))
    if clean(class_row.get("storage_unit_id")) or clean(class_row.get("storage_unit_product")):
        print("  Storage FA-MIB: id={0} product={1} serial={2} type={3}".format(
            clean(class_row.get("storage_unit_id")) or "-",
            clean(class_row.get("storage_unit_product")) or "-",
            clean(class_row.get("serial")) or "-",
            clean(class_row.get("storage_unit_type")) or "-",
        ))
    if clean(class_row.get("identity_source")):
        print("  Fonte principal de identidade: {0}".format(clean(class_row.get("identity_source"))))
    facts = class_row.get("protocol_facts") or {}
    if facts:
        parts = ["{0}={1}".format(key, clean(value)) for key, value in sorted(facts.items()) if clean(value)]
        if parts:
            print("  Dados do protocolo: {0}".format(", ".join(parts)))
    if clean(class_row.get("md32xx_pair_key")):
        print("  Storage MD32xx pair: {0}".format(clean(class_row.get("md32xx_pair_key"))))
    if clean(class_row.get("identity_history_source")):
        print("  Anti-flap: identidade forte preservada de {0}".format(clean(class_row.get("identity_history_source"))))
    if clean(class_row.get("historical_vmware_mac")):
        print("  VMware MAC histórico: {0}".format(clean(class_row.get("historical_vmware_mac"))))
    print("  Evidência CLASSIFY: {0}".format(_format_list(class_row.get("evidence"))))
    recommendations = row.get("review_recommendations") or class_row.get("review_recommendations") or []
    if recommendations:
        print("  Próxima evidência sugerida: {0}".format(_format_list(recommendations)))


def _print_delegated(rows):
    if not rows:
        return
    print("===== NETWORK VMS NO INVENTÁRIO CENTRALIZADO =====")
    for pos, row in enumerate(rows, 1):
        target = row.get("delegated_target") or {}
        print("[{0}/{1}] DELEGATED_VM/PASS | {2} | observado={3}".format(
            pos, len(rows), clean(row.get("primary_ip")) or "-",
            clean(row.get("observed_name") or row.get("desired_name")) or "-",
        ))
        if target:
            print("  VM: {0} (ID {1})".format(clean(target.get("vm_name")) or "-", target.get("vm_id") or "-"))
            print("  Interface: {0} (ID {1}) | MAC={2}".format(
                clean(target.get("interface_name")) or "-", target.get("interface_id") or "-",
                _format_list(target.get("interface_macs")),
            ))
            print("  Cluster/Host físico/Site: {0} / {1} / {2}".format(
                clean(target.get("cluster")) or "-", clean(target.get("physical_host")) or "-",
                clean(target.get("site")) or "-",
            ))
            print("  Origem autoritativa: vCenter central | correlação={0}".format(
                clean(target.get("source")) or "-"
            ))
        else:
            print("  Detalhe da VM não resolvido; criação física continua suprimida.")


def print_plan_diagnostics(plan_path, classification_path):
    plan = _load_json(plan_path)
    classification = _load_json(classification_path)
    by_ip = _classification_by_ip(classification)
    records = plan.get("records") or []

    ready_create = [row for row in records if row.get("decision") == "READY" and row.get("action") == "CREATE"]
    ready_update = [row for row in records if row.get("decision") == "READY" and row.get("action") == "UPDATE_SAFE"]
    ready_repair = [row for row in records if row.get("decision") == "READY" and row.get("action") == "REPAIR_SAFE_VM_DUPLICATE"]
    delegated = [row for row in records if row.get("decision") == "DELEGATED"]
    pending = [row for row in records if row.get("decision") in ("REVIEW", "BLOCKED")]

    guard = next((row.get("write_guard") for row in records if row.get("write_guard")), {}) or {}

    print("===== NETWORK PLAN DIAGNÓSTICO =====")
    print("Planner: {0}".format(clean(plan.get("planner_version")) or "-"))
    print("READY/CREATE: {0}".format(len(ready_create)))
    print("READY/UPDATE_SAFE: {0}".format(len(ready_update)))
    print("READY/REPAIR_SAFE: {0}".format(len(ready_repair)))
    print("DELEGATED/VM CENTRAL: {0}".format(len(delegated)))
    print("REVIEW: {0}".format(sum(1 for x in pending if x.get("decision") == "REVIEW")))
    print("BLOCKED: {0}".format(sum(1 for x in pending if x.get("decision") == "BLOCKED")))
    if guard:
        print("WRITE GUARD: {0} | mudanças={1} ({2}%) | violações={3}".format(
            clean(guard.get("status")) or "-", guard.get("eligible_total", 0),
            guard.get("change_percent", 0), _format_list(guard.get("violations")),
        ))
    print("NetBox write: NÃO")

    _print_delegated(delegated)

    if ready_create:
        print("===== NETWORK NOVOS OBJETOS READY =====")
        for pos, row in enumerate(ready_create, 1):
            ip = clean(row.get("primary_ip")).split("/", 1)[0]
            class_row = by_ip.get(ip) or {}
            print("[{0}/{1}] READY | {2} | {3} | role={4} | confidence={5}".format(
                pos, len(ready_create), ip or "-", clean(row.get("desired_name")) or "-",
                clean(row.get("role")) or "-", clean(row.get("confidence")) or "-",
            ))
            print("  Fabricante/Modelo: {0} / {1}".format(
                clean(row.get("manufacturer")) or "-", clean(row.get("model")) or "-"
            ))
            if clean(row.get("identity_policy")):
                print("  Política de identidade: {0}".format(clean(row.get("identity_policy"))))
            print("  IPs: {0}".format(_format_list(row.get("ips"))))
            _print_identity(row, class_row)
            _print_class_evidence(row, class_row)

    if ready_update:
        print("===== NETWORK AJUSTES READY =====")
        for pos, row in enumerate(ready_update, 1):
            ip = clean(row.get("primary_ip")).split("/", 1)[0]
            class_row = by_ip.get(ip) or {}
            print("[{0}/{1}] READY | {2} | {3} | UPDATE_SAFE".format(
                pos, len(ready_update), ip or "-", clean(row.get("desired_name")) or "-",
            ))
            print("  Ajustes: {0}".format(_format_list(row.get("safe_diffs"))))
            print("  Nome existente protegido: SIM")
            if clean(row.get("identity_policy")):
                print("  Política de identidade: {0}".format(clean(row.get("identity_policy"))))
            _print_identity(row, class_row)

    if ready_repair:
        print("===== NETWORK REPAROS SEGUROS READY =====")
        for pos, row in enumerate(ready_repair, 1):
            repair = row.get("repair") or {}
            print("[{0}/{1}] READY/REPAIR_SAFE | {2} | Device ID {3} -> VM ID {4}".format(
                pos, len(ready_repair), clean(row.get("desired_name")) or "-",
                repair.get("device_id") or "-", repair.get("vm_id") or "-",
            ))
            print("  IP: {0} -> VM interface {1}".format(
                clean(repair.get("ip_address")) or "-", clean(repair.get("vm_interface_name")) or "-"
            ))
            print("  Proteção: VM única e ownership integral do produto")

    reason_counts = Counter()
    for row in pending:
        for reason in row.get("reasons") or []:
            reason_counts[clean(reason)] += 1

    print("===== NETWORK PENDÊNCIAS POR MOTIVO =====")
    if not reason_counts:
        print("Nenhuma pendência.")
    else:
        for reason, count in sorted(reason_counts.items(), key=lambda item: (-item[1], item[0])):
            print("{0}: {1}".format(reason or "SEM_MOTIVO", count))

    print("===== NETWORK PENDÊNCIAS DETALHADAS =====")
    if not pending:
        print("Nenhuma pendência REVIEW/BLOCKED.")
        return

    for pos, row in enumerate(pending, 1):
        ip = clean(row.get("primary_ip")).split("/", 1)[0]
        class_row = by_ip.get(ip) or {}
        print("[{0}/{1}] {2} | {3} | {4} | role={5} | confidence={6} score={7}".format(
            pos, len(pending), clean(row.get("decision")) or "-", ip or "-",
            clean(row.get("desired_name")) or "-", clean(row.get("role")) or "-",
            clean(row.get("confidence")) or "-", clean(row.get("classification_score")) or "-",
        ))
        print("  Motivos: {0}".format(_format_list(row.get("reasons"))))
        print("  Match: {0} | {1}".format(
            clean(row.get("match_state")) or "-", clean(row.get("match_reason")) or "-"
        ))
        print("  Fabricante/Modelo/Serial: {0} / {1} / {2}".format(
            clean(row.get("manufacturer")) or "-", clean(row.get("model")) or "-", clean(row.get("serial")) or "-",
        ))
        parent = row.get("oob_parent_candidate") or {}
        if parent:
            print("  Pai OOB provável: {0} (Device ID {1}) por service-tag {2}".format(
                clean(parent.get("device_name")) or "-", parent.get("device_id") or "-",
                clean(parent.get("serial")) or "-",
            ))
        _print_identity(row, class_row)
        _print_class_evidence(row, class_row)


def main(argv=None):
    ap = argparse.ArgumentParser(description="netbox-discovery inventory pipeline (CLASSIFY -> RECONCILE -> PLAN)")
    ap.add_argument("--input", default="", help="Discovery JSON; default is latest discovery report")
    ap.add_argument("--output-dir", default=REPORTS)
    args = ap.parse_args(argv)

    classifier = os.path.join(HERE, "classifier_v7.py")
    reconciler = os.path.join(HERE, "reconciler_v5.py")
    planner = os.path.join(HERE, "planner_v9.py")

    cmd = [sys.executable, classifier, "--output-dir", args.output_dir]
    if args.input:
        cmd.extend(["--input", args.input])
    subprocess.check_call(cmd)

    classification = latest(os.path.join(args.output_dir, "*-classification-*.json"))
    if not classification:
        raise RuntimeError("CLASSIFY terminou sem gerar JSON")
    subprocess.check_call([sys.executable, reconciler, "--input", classification, "--output-dir", args.output_dir])

    reconciliation = latest(os.path.join(args.output_dir, "*-reconciliation-*.json"))
    if not reconciliation:
        raise RuntimeError("RECONCILE terminou sem gerar JSON")
    subprocess.check_call([
        sys.executable, planner,
        "--input", reconciliation,
        "--classification", classification,
        "--output-dir", args.output_dir,
    ])

    plan = latest(os.path.join(args.output_dir, "*-plan-*.json"))
    if not plan:
        raise RuntimeError("PLAN terminou sem gerar JSON")
    print_plan_diagnostics(plan, classification)

    print("===== INVENTORY PIPELINE =====")
    print("Pipeline version: {0}".format(PIPELINE_VERSION))
    print("CLASSIFY V7: OK")
    print("RECONCILE V5: OK")
    print("PLAN V9: OK")
    print("NetBox write: NÃO")
    return 0


if __name__ == "__main__":
    sys.exit(main())
