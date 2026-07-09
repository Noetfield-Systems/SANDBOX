#!/usr/bin/env python3
"""
TH-4 — Skill eval-suite validator  (catalog build B0 · TH-4)

The 3 in-repo audit skills (registry-motor-validator, receipt-ledger-auditor,
staleness-gate-auditor) shipped with NO evals/ (only pr-conflict-resolver had them).
This adds an authored eval suite for each (agent-graded negative scenarios, same
schema as skills/pr-conflict-resolver/evals/evals.json) plus this validator that
keeps each suite well-formed and tied to a real skill + its wrapped scripts.

It does NOT run the wrapped scripts (they read fixed repo paths and some write
receipts — running them with synthetic inputs would pollute the repo). The
scenarios are agent-graded fixtures; a full lift-vs-baseline run is an LLM-grader
follow-up (see pr-conflict-resolver/evals/benchmark.*).

Read-only. Exits 1 on any malformed suite / missing skill / missing wrapped script.

    python3 run_evals.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                             cwd=Path(__file__).resolve().parent, text=True, capture_output=True, check=True)
        return Path(out.stdout.strip())
    except Exception:
        return Path(__file__).resolve().parents[3]


REPO = _repo_root()
EVALS_DIR = Path(__file__).resolve().parent / "evals"

# each suite must target a real skill whose wrapped scripts exist
WRAPPED_SCRIPTS = {
    "registry-motor-validator": ["scripts/validate_parallel_automation_governance_v1.py",
                                 "scripts/audit_automation_surface_v1.py"],
    "receipt-ledger-auditor": ["scripts/audit_receipt_ledger_v1.py"],
    "staleness-gate-auditor": ["scripts/agent_read_staleness_engine_v1.py"],
}


def validate_suite(path: Path) -> list[str]:
    errs: list[str] = []
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return [f"{path.name}: not valid JSON ({e})"]
    name = d.get("skill_name")
    if not isinstance(name, str) or not name:
        errs.append(f"{path.name}: missing skill_name")
    if name and not (REPO / "skills" / name / "SKILL.md").is_file():
        errs.append(f"{path.name}: skill '{name}' has no skills/{name}/SKILL.md")
    for scr in WRAPPED_SCRIPTS.get(name, []):
        if not (REPO / scr).is_file():
            errs.append(f"{path.name}: wrapped script missing: {scr}")
    evals = d.get("evals")
    if not isinstance(evals, list) or not evals:
        errs.append(f"{path.name}: 'evals' must be a non-empty list")
        return errs
    ids = set()
    for i, ev in enumerate(evals):
        for field in ("id", "prompt", "expected_output", "expectations"):
            if field not in ev:
                errs.append(f"{path.name}[eval {i}]: missing '{field}'")
        if not isinstance(ev.get("expectations"), list) or not ev.get("expectations"):
            errs.append(f"{path.name}[eval {i}]: 'expectations' must be a non-empty list")
        if ev.get("id") in ids:
            errs.append(f"{path.name}: duplicate eval id {ev.get('id')}")
        ids.add(ev.get("id"))
    return errs


def validate_all() -> list[str]:
    suites = sorted(EVALS_DIR.glob("*.evals.json"))
    if not suites:
        return [f"no eval suites found under {EVALS_DIR}"]
    errs = []
    for s in suites:
        errs += validate_suite(s)
    # every skill lacking evals/ must now have an authored suite
    covered = {json.loads(s.read_text()).get("skill_name") for s in suites}
    for need in WRAPPED_SCRIPTS:
        if need not in covered:
            errs.append(f"missing eval suite for skill '{need}'")
    return errs


def main(argv=None) -> int:
    errs = validate_all()
    if errs:
        print("TH-4 EVAL_SUITES: INVALID:")
        for e in errs:
            print(f"  - {e}")
        return 1
    n = len(list(EVALS_DIR.glob("*.evals.json")))
    print(f"TH-4 EVAL_SUITES: CHECK_OK ({n} suites well-formed, skills + wrapped scripts present)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
