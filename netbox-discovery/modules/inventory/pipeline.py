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
PIPELINE_VERSION = "2.4-product"


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
        ip = clean(row.get("ip"))
        if ip:
            out[ip] = row
    return out


def _format_list(values):
    return ", ".join(clean(x) for x in (values or []) if clean(x)) or "-"


def _print_class_evidence(row, class_row):
    print("  Asset class: {0}".format(clean(row.get("asset_class")) or clean(class_row.get("asset_class")) or "-"))
    print("  SNMP: name={0} object_id={1} mgmt_mac={2}".format(
        clean(class_row.get("snmp_name")) or "-", clean(class_row.get("snmp_object_id")) or "-",
        clean(class_row.get("management_mac")) or "-",
    ))
    if clean(class_row.get("storage_unit_id")) or clean(class_row.get("storage_unit_product")):
        print("  Storage FA-MIB: id={0} product={1} serial={2} type={3}".format(
            clean(class_row.get("storage_unit_id")) or "-",
            clean(class_row.get("storage_unit_product")) or "-",
            clean(class_row.get("serial")) or "-",
            clean(class_row.get("storage_unit_type")) or "-",
        ))
    if clean(class_row.get("identity_history_source")):
        print("  Anti-flap: identidade forte preservada de {0}".format(clean(class_row.get("identity_history_source"))))
    if clean(class_row.get("historical_vmware_mac")):
        print("  VMware MAC histórico: {0}".format(clean(class_row.get("historical_vmware_mac"))))
    print("  Evidência CLASSIFY: {0}".format(_format_list(class_row.get("evidence"))))


def print_plan_diagnostics(plan_path, classification_path):
    plan = _load_json(plan_path)
    classification = _load_json(classification_path)
    by_ip = _classification_by_ip(classification)
    records = plan.get("records") or []

    ready_create = [
        row for row in records
        if row.get("decision") == "READY" and row.get("action") == "CREATE"
    ]
    ready_update = [
        row for row in records
        if row.get("decision") == "READY" and row.get("action") == "UPDATE_SAFE"
    ]
    delegated = [row for row in records if row.get("decision") == "DELEGATED"]
    pending = [
        row for row in records
        if row.get("decision") in ("REVIEW", "BLOCKED")
    ]

    print("===== NETWORK PLAN DIAGNÓSTICO =====")
    print("Planner: {0}".format(clean(plan.get("planner_version")) or "-"))
    print("READY/CREATE: {0}".format(len(ready_create)))
    print("READY/UPDATE_SAFE: {0}".format(len(ready_update)))
    print("DELEGATED/HYPERVISOR: {0}".format(len(delegated)))
    print("REVIEW: {0}".format(sum(1 for x in pending if x.get("decision") == "REVIEW")))
    print("BLOCKED: {0}".format(sum(1 for x in pending if x.get("decision") == "BLOCKED")))
    print("NetBox write: NÃO")

    if delegated:
        print("===== NETWORK DELEGADOS AO HYPERVISOR =====")
        for pos, row in enumerate(delegated, 1):
            print("[{0}/{1}] DELEGATED | {2} | {3} | {4}".format(
                pos, len(delegated), clean(row.get("primary_ip")) or "-",
                clean(row.get("desired_name")) or "-", clean(row.get("match_reason")) or "-",
            ))

    if ready_create:
        print("===== NETWORK NOVOS OBJETOS READY =====")
        for pos, row in enumerate(ready_create, 1):
            ip = clean(row.get("primary_ip"))
            class_row = by_ip.get(ip) or {}
            print("[{0}/{1}] READY | {2} | {3} | role={4} | confidence={5}".format(
                pos, len(ready_create), ip or "-", clean(row.get("desired_name")) or "-",
                clean(row.get("role")) or "-", clean(row.get("confidence")) or "-",
            ))
            print("  Fabricante/Modelo: {0} / {1}".format(
                clean(row.get("manufacturer")) or "-", clean(row.get("model")) or "-"
            ))
            _print_class_evidence(row, class_row)

    if ready_update:
        print("===== NETWORK AJUSTES READY =====")
        for pos, row in enumerate(ready_update, 1):
            print("[{0}/{1}] READY | {2} | {3} | UPDATE_SAFE".format(
                pos, len(ready_update), clean(row.get("primary_ip")) or "-",
                clean(row.get("desired_name")) or "-",
            ))
            print("  Ajustes: {0}".format(_format_list(row.get("safe_diffs"))))

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
        ip = clean(row.get("primary_ip"))
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
            clean(row.get("manufacturer")) or "-", clean(row.get("model")) or "-",
            clean(row.get("serial")) or "-",
        ))
        _print_class_evidence(row, class_row)


def main(argv=None):
    ap = argparse.ArgumentParser(description="netbox-discovery inventory pipeline (CLASSIFY -> RECONCILE -> PLAN)")
    ap.add_argument("--input", default="", help="Discovery JSON; default is latest discovery report")
    ap.add_argument("--output-dir", default=REPORTS)
    args = ap.parse_args(argv)

    classifier = os.path.join(HERE, "classifier_v4.py")
    reconciler = os.path.join(HERE, "reconciler_v3.py")
    planner = os.path.join(HERE, "planner_v3.py")

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
    print("CLASSIFY V4: OK")
    print("RECONCILE V3: OK")
    print("PLAN V3: OK")
    print("NetBox write: NÃO")
    return 0


if __name__ == "__main__":
    sys.exit(main())
