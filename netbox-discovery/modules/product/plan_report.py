#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function

import argparse
import glob
import json
import os
import sys
from collections import Counter

BASE = os.environ.get("NETBOX_DISCOVERY_BASE", "/opt/netbox-discovery")
REPORTS = os.path.join(BASE, "reports")


def clean(value):
    return "" if value is None else str(value).strip()


def load_json(path):
    try:
        with open(path, "r") as handle:
            value = json.load(handle)
            return value if isinstance(value, dict) else {}
    except Exception as exc:
        raise RuntimeError("não foi possível ler {0}: {1}".format(path, exc))


def configured_site():
    sys.path.insert(0, BASE)
    from lib.config import load_config
    cfg = load_config()
    site = clean((cfg.get("discovery") or {}).get("site"))
    if not site:
        raise RuntimeError("site não definido em config.yml")
    return site


def latest_path(pattern):
    rows = glob.glob(os.path.join(REPORTS, pattern))
    if not rows:
        return ""
    return max(rows, key=lambda path: (os.path.getmtime(path), path))


def latest_context(site):
    plan_path = latest_path("{0}-plan-*.json".format(site))
    if not plan_path:
        raise RuntimeError("nenhum PLAN encontrado para o site {0}".format(site))
    run_path = latest_path("{0}-run-*.json".format(site))
    return plan_path, load_json(plan_path), run_path, load_json(run_path) if run_path else {}


def row_decision(row):
    return clean(row.get("decision") or row.get("status") or row.get("plan_decision")).upper() or "UNKNOWN"


def row_action(row):
    return clean(row.get("action") or row.get("planned_action")).upper() or "NONE"


def row_name(row):
    return clean(
        row.get("effective_name")
        or row.get("desired_name")
        or row.get("observed_name")
        or row.get("hostname")
        or row.get("asset_id")
    ) or "SEM-NOME"


def row_ip(row):
    value = clean(row.get("primary_ip") or row.get("ip"))
    if value:
        return value.split("/", 1)[0]
    ips = row.get("ips") or []
    if ips:
        return clean(ips[0]).split("/", 1)[0]
    return "SEM-IP"


def row_role(row):
    return clean(row.get("target_role") or row.get("role") or row.get("asset_class")) or "SEM-ROLE"


def flatten_reasons(row):
    values = []
    for key in ("reasons", "review_recommendations", "serial_conflict"):
        raw = row.get(key)
        if isinstance(raw, list):
            for item in raw:
                text = clean(item)
                if text and text not in values:
                    values.append(text)
        elif clean(raw):
            text = clean(raw)
            if text not in values:
                values.append(text)
    if not values:
        for key in ("identity_policy", "match_reason", "delegation_status"):
            text = clean(row.get(key))
            if text and text not in values:
                values.append(text)
    return values or ["SEM_MOTIVO_INFORMADO"]


def effective_write_guard(records):
    guards = [row.get("write_guard") for row in records if isinstance(row.get("write_guard"), dict)]
    if not guards:
        return {}
    return dict(guards[0])


def build_payload(site, plan_path, plan, run_path, run):
    records = [row for row in (plan.get("records") or []) if isinstance(row, dict)]
    decisions = Counter(row_decision(row) for row in records)
    actions = Counter(row_action(row) for row in records)
    by_decision_action = {}
    reasons = {}
    for decision in sorted(decisions):
        selected = [row for row in records if row_decision(row) == decision]
        by_decision_action[decision] = dict(Counter(row_action(row) for row in selected))
        reason_counter = Counter()
        for row in selected:
            for reason in flatten_reasons(row):
                reason_counter[reason] += 1
        reasons[decision] = dict(reason_counter)
    return {
        "site": site,
        "plan_path": plan_path,
        "run_path": run_path,
        "run_id": clean(run.get("run_id")),
        "run_status": clean(run.get("status")),
        "apply_requested": bool(run.get("apply_requested", False)),
        "netbox_write": bool(run.get("netbox_write", False)),
        "record_count": len(records),
        "decision_summary": dict(decisions),
        "action_summary": dict(actions),
        "actions_by_decision": by_decision_action,
        "reasons_by_decision": reasons,
        "write_guard": effective_write_guard(records),
        "records": records,
    }


def print_counter(title, values):
    print(title)
    if not values:
        print("  nenhum")
        return
    for key, total in sorted(values.items(), key=lambda item: (-item[1], item[0])):
        print("  {0}: {1}".format(key, total))


def print_write_guard(guard):
    if not guard:
        print("WRITE GUARD: NÃO INFORMADO")
        return
    print("WRITE GUARD: {0} | elegíveis={1} | base={2} | mudanças={3}%".format(
        guard.get("status", "?"),
        guard.get("eligible_total", 0),
        guard.get("live_devices", 0),
        guard.get("change_percent", 0),
    ))
    if "percent_enforced" in guard:
        print("WRITE GUARD POLÍTICA: {0} | percentual={1} | base mínima={2}".format(
            guard.get("policy", "?"),
            "ATIVO" if guard.get("percent_enforced") else "ADIADO",
            guard.get("percent_min_base", (guard.get("limits") or {}).get("PERCENT_MIN_BASE", "?")),
        ))
    violations = guard.get("violations") or []
    if violations:
        print("WRITE GUARD VIOLAÇÕES: {0}".format(" | ".join(str(value) for value in violations)))


def print_summary(payload):
    print("===== PLAN SUMMARY =====")
    print("Site: {0}".format(payload["site"]))
    print("Run ID: {0}".format(payload["run_id"] or "NÃO VINCULADO"))
    print("Run status: {0}".format(payload["run_status"] or "SEM RUN"))
    print("NetBox write: {0}".format("SIM" if payload["netbox_write"] else "NÃO"))
    print("PLAN: {0}".format(payload["plan_path"]))
    print("Registros: {0}".format(payload["record_count"]))
    print_write_guard(payload.get("write_guard") or {})
    print_counter("Decisões:", payload["decision_summary"])
    print_counter("Ações em todos os registros:", payload["action_summary"])

    for decision in ("READY", "BLOCKED", "REVIEW", "DELEGATED"):
        total = payload["decision_summary"].get(decision, 0)
        if not total:
            continue
        print("")
        print("===== {0}: {1} =====".format(decision, total))
        print_counter("Ações:", payload["actions_by_decision"].get(decision, {}))
        if decision in ("BLOCKED", "REVIEW"):
            print_counter("Motivos:", payload["reasons_by_decision"].get(decision, {}))

    if payload["decision_summary"].get("BLOCKED", 0) or payload["decision_summary"].get("REVIEW", 0):
        print("")
        print("Detalhes nativos:")
        print("  netbox-discovery plan blocked")
        print("  netbox-discovery plan review")
    print("")
    print("Este comando é somente leitura. Nenhuma alteração foi feita no NetBox.")


def print_details(payload, decision, limit):
    selected = [row for row in payload["records"] if decision == "ALL" or row_decision(row) == decision]
    print("===== PLAN {0}: {1} =====".format(decision, len(selected)))
    print("Site: {0}".format(payload["site"]))
    print("Run ID: {0}".format(payload["run_id"] or "NÃO VINCULADO"))
    print("NetBox write: {0}".format("SIM" if payload["netbox_write"] else "NÃO"))
    print_write_guard(payload.get("write_guard") or {})
    shown = selected if limit <= 0 else selected[:limit]
    for index, row in enumerate(shown, 1):
        print("")
        print("[{0}] {1} | {2} | {3}".format(index, row_ip(row), row_name(row), row_role(row)))
        print("    DECISION={0} ACTION={1}".format(row_decision(row), row_action(row)))
        print("    MOTIVOS: {0}".format(" | ".join(flatten_reasons(row))))
        diffs = [clean(value) for value in (row.get("safe_diffs") or []) if clean(value)]
        if diffs:
            print("    DIFFS: {0}".format(" | ".join(diffs)))
    if len(shown) < len(selected):
        print("")
        print("Exibidos {0} de {1}. Use --limit 0 para mostrar todos.".format(len(shown), len(selected)))
    print("")
    print("Este comando é somente leitura. Nenhuma alteração foi feita no NetBox.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Relatório nativo do último PLAN")
    parser.add_argument(
        "view",
        nargs="?",
        default="summary",
        choices=("summary", "blocked", "review", "ready", "delegated", "all"),
    )
    parser.add_argument("--limit", type=int, default=100, help="limite de linhas; 0 mostra todas")
    parser.add_argument("--json", action="store_true", help="retorna relatório estruturado em JSON")
    args = parser.parse_args(argv)

    site = configured_site()
    plan_path, plan, run_path, run = latest_context(site)
    payload = build_payload(site, plan_path, plan, run_path, run)
    if args.json:
        output = dict(payload)
        if args.view != "all":
            decision = args.view.upper()
            if args.view == "summary":
                output.pop("records", None)
            else:
                output["records"] = [row for row in payload["records"] if row_decision(row) == decision]
        print(json.dumps(output, indent=2, sort_keys=True, ensure_ascii=False))
        return 0
    if args.view == "summary":
        print_summary(payload)
    else:
        print_details(payload, args.view.upper(), args.limit)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("ERRO: {0}".format(exc), file=sys.stderr)
        sys.exit(1)
