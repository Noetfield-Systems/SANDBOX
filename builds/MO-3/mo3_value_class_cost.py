#!/usr/bin/env python3
"""
MO-3 — Value-class cost attribution table  (catalog build B3 · MO-3, designed move M06)

Static, READ-ONLY report. Joins two ground-truth artifacts:

  * data/workflow_census_value_class_rules_v1.json
      - by_task_cell : task_cell -> {value_class, receipt_target}   (the RULES)
      - standing_audit_rules : "META cost > GUARD+REVENUE cost -> audit_status RED"
                               "REVENUE lane may never be empty -> RED"
  * receipts/p0pgr/evidence/evidence-*.json  (NEWEST by mtime)
      - census.counts : value_class -> loop count            (the observed CENSUS)

In this system "cost" is the operational loop footprint carried by each value_class
(the census counts). The audit rule literally compares "META cost" against
"GUARD+REVENUE cost" using those counts. This report attributes that cost by
value_class: it groups the rules' task_cells under each value_class (the JOIN),
attaches the newest census count to each class, and re-evaluates the two
standing cost rules.

Verdict vocab: CHECK_OK / CHECK_REJECTED — never a bare governance PASS. The report
is advisory (origin=sandbox-advisory, authority=none). It EXITS NONZERO when a
standing cost rule is violated (this is not an always-exit-0 stub): with the real
census (META=22 > GUARD+REVENUE=8) it emits CHECK_REJECTED, exactly mirroring the
census's own audit_status=RED. Never writes to either ground-truth artifact.

    python3 mo3_value_class_cost.py [--rules PATH] [--evidence PATH] [--json]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                             cwd=Path(__file__).resolve().parent,
                             text=True, capture_output=True, check=True)
        return Path(out.stdout.strip())
    except Exception:
        return Path(__file__).resolve().parents[3]


REPO = _repo_root()
DEFAULT_RULES = REPO / "data" / "workflow_census_value_class_rules_v1.json"
EVIDENCE_DIR = REPO / "receipts" / "p0pgr" / "evidence"


def newest_evidence(evidence_dir: Path = EVIDENCE_DIR) -> Path:
    """The newest census evidence bundle (by mtime), matching how the census picks
    'the latest'. Raises if none present rather than silently reporting on nothing."""
    cands = sorted(evidence_dir.glob("evidence-*.json"),
                   key=lambda p: (p.stat().st_mtime, p.name))
    if not cands:
        raise FileNotFoundError(f"no evidence-*.json under {evidence_dir}")
    return cands[-1]


def group_task_cells(rules: dict) -> dict[str, list[str]]:
    """JOIN: group each rules.by_task_cell entry under its declared value_class.
    This is the grouping a rule mutation must move a task_cell between."""
    groups: dict[str, list[str]] = {vc: [] for vc in rules.get("value_classes", [])}
    for cell, spec in (rules.get("by_task_cell") or {}).items():
        vc = spec.get("value_class")
        groups.setdefault(vc, []).append(cell)
    return {vc: sorted(cells) for vc, cells in groups.items()}


def attribute(rules: dict, evidence: dict) -> dict:
    """Build the value-class cost attribution table and evaluate the standing
    cost rules. 'cost' == census loop count carried by the class."""
    groups = group_task_cells(rules)
    census = (evidence.get("census") or {})
    counts = dict(census.get("counts") or {})
    declared = list(rules.get("value_classes", []))

    # Join integrity: every value_class the census attributes cost to must be a
    # declared value_class in the rules — otherwise cost is attributed to a class
    # the rulebook does not recognize (unattributable cost).
    unknown_census_classes = sorted(c for c in counts if c not in declared)

    total_cost = sum(counts.values())
    rows = []
    for vc in declared:
        cost = int(counts.get(vc, 0))
        rows.append({
            "value_class": vc,
            "cost_loops": cost,
            "cost_share_pct": round(100.0 * cost / total_cost, 1) if total_cost else 0.0,
            "rule_cell_count": len(groups.get(vc, [])),
            "rule_task_cells": groups.get(vc, []),
        })

    meta_cost = int(counts.get("META", 0))
    guard_cost = int(counts.get("GUARD", 0))
    revenue_cost = int(counts.get("REVENUE", 0))

    violations = []
    # standing_audit_rules[1]: "META cost > GUARD+REVENUE cost -> audit_status RED"
    if meta_cost > guard_cost + revenue_cost:
        violations.append({
            "rule": "META cost > GUARD+REVENUE cost -> RED",
            "detail": f"META={meta_cost} > GUARD+REVENUE={guard_cost + revenue_cost} "
                      f"(system grooming itself)",
        })
    # standing_audit_rules[3]: "REVENUE lane may never be empty -> RED"
    if revenue_cost == 0:
        violations.append({
            "rule": "REVENUE lane empty -> RED",
            "detail": "zero REVENUE loops in census",
        })
    if unknown_census_classes:
        violations.append({
            "rule": "census cost attributed to undeclared value_class",
            "detail": f"classes not in rules.value_classes: {unknown_census_classes}",
        })

    verdict = "CHECK_OK" if not violations else "CHECK_REJECTED"
    return {
        "origin": "sandbox-advisory", "authority": "none", "pass_claimed": False,
        "verdict": verdict,
        "evidence_census_file": census.get("file"),
        "census_audit_status": census.get("audit_status"),
        "total_cost_loops": total_cost,
        "table": rows,
        "cost_rule_violations": violations,
        "cost_usd_month_menu": rules.get("cost_usd_month", {}),
    }


def render(res: dict, evidence_path: Path) -> str:
    lines = []
    lines.append(f"MO-3 VALUE-CLASS COST ATTRIBUTION: {res['verdict']}  "
                 f"(total cost {res['total_cost_loops']} loops; "
                 f"census audit_status={res['census_audit_status']})")
    lines.append(f"  evidence: {evidence_path.name}  census_file={res['evidence_census_file']}")
    lines.append(f"  {'value_class':<10} {'cost':>5} {'share':>7} {'#cells':>7}  task_cells")
    for r in res["table"]:
        cells = ", ".join(r["rule_task_cells"]) or "(none)"
        lines.append(f"  {r['value_class']:<10} {r['cost_loops']:>5} "
                     f"{r['cost_share_pct']:>6.1f}% {r['rule_cell_count']:>7}  {cells}")
    if res["cost_rule_violations"]:
        lines.append("  cost-rule violations (CHECK_REJECTED):")
        for v in res["cost_rule_violations"]:
            lines.append(f"    [{v['rule']}] {v['detail']}")
    else:
        lines.append("  all standing cost rules satisfied")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    ap.add_argument("--evidence", type=Path, default=None,
                    help="explicit evidence bundle; default = newest evidence-*.json")
    ap.add_argument("--json", action="store_true", help="emit the report as JSON")
    args = ap.parse_args(argv)

    ev_path = args.evidence if args.evidence is not None else newest_evidence()
    rules = json.loads(args.rules.read_text(encoding="utf-8"))
    evidence = json.loads(ev_path.read_text(encoding="utf-8"))
    res = attribute(rules, evidence)

    if args.json:
        print(json.dumps(res, indent=2, sort_keys=True))
    else:
        print(render(res, ev_path))
    return 0 if res["verdict"] == "CHECK_OK" else 1


if __name__ == "__main__":
    sys.exit(main())
