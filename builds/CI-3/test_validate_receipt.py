#!/usr/bin/env python3
"""
TH for CI-3 — proves the extracted validator + the workflow's CI guards.

Validator (report-only, red-capable):
  * the real example cycle receipt validates against the loop-state schema -> CHECK_OK.
  * a MINIMAL MUTATION (delete one required top-level field, `cost`) -> CHECK_REJECTED
    citing the missing field.
  * a nested mutation (bad enum for `state`) -> CHECK_REJECTED.
  * validating never edits the receipt or the schema (sha256 unchanged).

CI guards on the proposal workflow YAML:
  * permissions: contents: read ONLY (no write scopes anywhere).
  * on: pull_request ONLY (never pull_request_target / push / schedule).
  * NO secrets: / env: credential references at all.
  * the validation step is NON-BLOCKING (continue-on-error: true).
And on the composite action.yml:
  * it invokes the validator in report mode (--json), never a --write-* flag.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import yaml  # optional; tests fall back to text parsing under HOME=temp
except Exception:  # pragma: no cover
    yaml = None

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]  # CI-3 -> builds -> catalog -> sg-sandbox
RECEIPT = REPO / "receipts" / "p0pgr" / "P0PGR-CYCLE-20260708T131048Z.json"
SCHEMA = REPO / "p0-pgr" / "P0_PROMPT_LOOP_STATE_SCHEMA_v1.json"
WORKFLOW = HERE / "ci-3-validate-receipt.yml"
ACTION = HERE / "action.yml"

spec = importlib.util.spec_from_file_location("vr", HERE / "validate_receipt.py")
vr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vr)


# ---- validator ---------------------------------------------------------------

def test_real_receipt_is_conformant():
    res = vr.validate(RECEIPT, SCHEMA)
    assert res["verdict"] == "CHECK_OK", res


def test_minimal_mutation_missing_required_is_rejected():
    receipt = json.loads(RECEIPT.read_text())
    del receipt["cost"]  # `cost` is a required top-level field
    errs = vr.schema_errors(receipt, json.loads(SCHEMA.read_text()))
    blob = " ".join(errs)
    assert errs, "removing required `cost` must be flagged"
    assert "missing required field 'cost'" in blob, blob


def test_nested_bad_enum_is_rejected():
    receipt = json.loads(RECEIPT.read_text())
    receipt["state"] = "TOTALLY_NOT_A_STATE"
    errs = vr.schema_errors(receipt, json.loads(SCHEMA.read_text()))
    assert any("state" in e and "not in allowed" in e for e in errs), errs


def test_validation_never_edits_inputs():
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (RECEIPT, SCHEMA)}
    with tempfile.TemporaryDirectory() as _:
        rc = subprocess.run(
            [sys.executable, str(HERE / "validate_receipt.py"),
             "--receipt", str(RECEIPT), "--schema", str(SCHEMA), "--json"],
            text=True, capture_output=True)
        assert rc.returncode == 0, rc.stderr
    after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (RECEIPT, SCHEMA)}
    assert before == after, "validator mutated an input file"


# ---- CI guards ---------------------------------------------------------------
# Guard assertions run on the raw YAML text (dependency-free so they pass even
# under HOME=temp where PyYAML may be hidden). When PyYAML is importable we also
# cross-check the parsed structure.

def _code_lines() -> list[str]:
    """Workflow lines with trailing '# ...' comments stripped, blanks/comment-only dropped."""
    out = []
    for raw in WORKFLOW.read_text().splitlines():
        line = re.sub(r"\s+#.*$", "", raw)  # strip inline comments (keeps '#' inside quotes rare here)
        if line.strip() and not line.lstrip().startswith("#"):
            out.append(line)
    return out


def test_guard_permissions_contents_read_only():
    lines = _code_lines()
    assert any(re.fullmatch(r"permissions:", l.strip()) for l in lines)
    assert any(re.fullmatch(r"contents:\s*read", l.strip()) for l in lines), "must grant contents: read"
    # no write scope anywhere in real (non-comment) config
    assert not any("write" in l for l in lines), "no write permission scope allowed"
    if yaml:
        wf = yaml.safe_load(WORKFLOW.read_text())
        assert wf.get("permissions") == {"contents": "read"}, wf.get("permissions")


def test_guard_on_pull_request_only():
    lines = _code_lines()
    assert any(re.fullmatch(r"on:", l.strip()) for l in lines), "must have an on: block"
    assert any(re.fullmatch(r"pull_request:?", l.strip()) for l in lines), "must trigger on pull_request"
    for forbidden in ("pull_request_target", "push:", "schedule:", "workflow_dispatch"):
        assert not any(forbidden in l for l in lines), f"forbidden trigger {forbidden!r} present"
    if yaml:
        wf = yaml.safe_load(WORKFLOW.read_text())
        on = wf.get("on", wf.get(True))  # bare `on:` parses to key True
        triggers = set(on.keys()) if isinstance(on, dict) else {on}
        assert triggers == {"pull_request"}, triggers


def test_guard_no_secrets_or_env_credentials():
    lines = _code_lines()
    joined = "\n".join(lines)
    assert "secrets." not in joined and not any(l.strip().startswith("secrets:") for l in lines)
    assert not any(re.fullmatch(r"env:", l.strip()) for l in lines), "no env: credential block allowed"
    for token in ("CF_", "SUPABASE", "GITHUB_TOKEN", "ACCESS_TOKEN", "API_KEY"):
        assert token not in joined, f"credential-like ref {token!r} present"


def test_guard_validation_step_is_non_blocking():
    lines = _code_lines()
    assert any("./catalog/builds/CI-3" in l for l in lines), "must call the CI-3 composite action"
    assert any(re.fullmatch(r"continue-on-error:\s*true", l.strip()) for l in lines), \
        "validation step must be non-blocking"
    if yaml:
        wf = yaml.safe_load(WORKFLOW.read_text())
        steps = wf["jobs"]["validate-receipt"]["steps"]
        val = [s for s in steps if str(s.get("uses", "")).startswith("./catalog/builds/CI-3")]
        assert val and val[0].get("continue-on-error") is True


def test_action_runs_report_only():
    text = ACTION.read_text()
    assert "--json" in text, "composite action must call the validator in report mode"
    for bad in ("--write-supabase", "--write-receipt", "--fail-on-block-merge"):
        assert bad not in text, f"report-only violated: {bad}"
    assert "secrets." not in text and "env:" not in text


TESTS = [
    test_real_receipt_is_conformant,
    test_minimal_mutation_missing_required_is_rejected,
    test_nested_bad_enum_is_rejected,
    test_validation_never_edits_inputs,
    test_guard_permissions_contents_read_only,
    test_guard_on_pull_request_only,
    test_guard_no_secrets_or_env_credentials,
    test_guard_validation_step_is_non_blocking,
    test_action_runs_report_only,
]


def _main() -> int:
    failed = 0
    for t in TESTS:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {t.__name__}: {e}")
    print(f"\n{len(TESTS) - failed}/{len(TESTS)} green")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_main())
