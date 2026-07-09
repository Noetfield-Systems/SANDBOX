#!/usr/bin/env python3
"""
TH-1 — Promotion-gate "refusal teeth" harness  (catalog build B0 · TH-1)

Locks the load-bearing deploy trust boundary: proves gates/promotion_gate.py
REFUSES a non-PASS verifier receipt for the SPECIFIC cause, and APPROVES a
conformant one — before anyone tunes the gate.

CHESS-patched (BUILD_PLAN_PHASED_v1_LOCKED §B0):
  * asserts the specific refusal-cause STRING, never returncode==2 alone
    (exit 2 is overloaded across 4+ paths in the gate).
  * ships a conformant-PASS positive control that must reach APPROVED_DRY_RUN exit 0.
  * every negative fixture is a MINIMAL MUTATION of the conformant receipt (flip one field).
  * runs flagless, CF tokens unset, HOME on a temp dir — never passes
    --deploy-command/--confirm-each-time/--semi-auto-window/--autonomous-deploy
    (a deploy flag would let main() reach a live `wrangler deploy`). run_gate()
    hard-raises if a forbidden flag is ever requested.

Advisory sandbox harness. Emits no PASS of its own. Runnable two ways:
    python3 test_promotion_gate_refusal_teeth.py     # self-contained runner
    python3 -m pytest test_promotion_gate_refusal_teeth.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def _repo_root() -> Path:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=Path(__file__).resolve().parent, text=True, capture_output=True, check=True,
        )
        return Path(out.stdout.strip())
    except Exception:
        return Path(__file__).resolve().parents[3]


REPO = _repo_root()
GATE = REPO / "gates" / "promotion_gate.py"

# A fully conformant verifier receipt: every refusal_reasons() check passes.
BASE_RECEIPT = {
    "receipt_id": "rcpt-conformant-0001",
    "artifact_type": "knowledge_bundle",
    "status": "PASS",
    "result": "PASS",
    "pass_claimed": True,
    "edge_execution_proven": True,
    "secondary_account_proven": True,
    "cf_account_id": "b7282b4a5c17b84d62e3ef8866b878f8",
    "candidate_ref": "abc123",
    "candidate_path": "cloud/workers/sourcea-brain-chat-v1/src/knowledge-bundle.json",
    "candidate_sha256": "deadbeefcafe",
    "candidate_validation_failures": [],
    "failures": [],
}

# The expected-* args must MATCH the conformant receipt so the ONLY thing that
# can flip the verdict is the single mutated field.
COMMON_ARGS = [
    "--expected-candidate-ref", "abc123",
    "--expected-candidate-path", "cloud/workers/sourcea-brain-chat-v1/src/knowledge-bundle.json",
    "--expected-candidate-sha256", "deadbeefcafe",
    "--expected-cf-account-id", "b7282b4a5c17b84d62e3ef8866b878f8",
]

FORBIDDEN_FLAGS = (
    "--deploy-command", "--execute-deploy", "--confirm-each-time",
    "--semi-auto-window", "--autonomous-deploy", "--post-promote-command",
)

# (case_id, mutation dict applied to BASE_RECEIPT, expected exact reason substring)
MUTATIONS = [
    ("status_fail",            {"status": "FAIL"},                 "receipt status is 'FAIL', not 'PASS'"),
    ("result_fail",            {"result": "FAIL"},                 "receipt result is 'FAIL', not 'PASS'"),
    ("pass_claimed_false",     {"pass_claimed": False},            "receipt pass_claimed is not true"),
    ("edge_not_proven",        {"edge_execution_proven": False},   "edge execution is not proven"),
    ("secondary_not_proven",   {"secondary_account_proven": False},"secondary account is not proven"),
    ("cf_account_mismatch",    {"cf_account_id": "0d0b967bMAIN"},  "cf_account_id does not match expected secondary account"),
    ("sha_mismatch",           {"candidate_sha256": "0000"},       "candidate_sha256 does not match expected candidate sha256"),
    ("has_failures",           {"failures": ["boom"]},             "receipt has failures"),
]


def run_gate(receipt: dict, extra_args=()):
    """Invoke the gate offline against a local receipt. Returns (exit_code, stdout+stderr).

    Hard safety guard: refuses to add any deploy/execute flag, and forces
    HOME onto a throwaway dir so ~/.sina CF tokens can never load.
    """
    for a in extra_args:
        if a in FORBIDDEN_FLAGS:
            raise AssertionError(f"TH-1 harness must never pass a deploy flag: {a}")
    with tempfile.TemporaryDirectory() as tmp:
        rc_path = Path(tmp) / "receipt.json"
        rc_path.write_text(json.dumps(receipt), encoding="utf-8")
        home = Path(tmp) / "home"
        home.mkdir()
        env = dict(os.environ)
        env["HOME"] = str(home)                 # no ~/.sina/secrets/cloudflare-tokens.env here
        env.pop("CF_MAIN_TOKEN", None)
        env.pop("CF_VERIFIER_TOKEN", None)
        env.pop("CLOUDFLARE_API_TOKEN", None)
        proc = subprocess.run(
            [sys.executable, str(GATE), "--receipt-url", rc_path.as_uri(), *COMMON_ARGS, *extra_args],
            text=True, capture_output=True, env=env,
        )
        return proc.returncode, proc.stdout + proc.stderr


def _mutate(**over):
    r = dict(BASE_RECEIPT)
    r.update(over)
    return r


# ---- tests -------------------------------------------------------------------

def test_positive_control_conformant_is_approved_dry_run():
    code, out = run_gate(BASE_RECEIPT)
    assert code == 0, f"conformant receipt should be approved (exit 0), got {code}\n{out}"
    assert "APPROVED_DRY_RUN" in out, out
    assert "deploy_executed: false" in out, out


def test_refusal_teeth_specific_cause():
    for case_id, over, expected_reason in MUTATIONS:
        code, out = run_gate(_mutate(**over))
        assert code == 2, f"[{case_id}] expected REFUSED exit 2, got {code}\n{out}"
        assert "PROMOTION_GATE: REFUSED" in out, f"[{case_id}] no REFUSED banner\n{out}"
        assert "deploy_executed: false" in out, f"[{case_id}] gate must not deploy\n{out}"
        # the teeth: the SPECIFIC cause, not just the exit code
        assert expected_reason in out, f"[{case_id}] missing cause {expected_reason!r}\n{out}"


def test_reasons_are_cause_specific_not_just_exit_code():
    # two different single-field faults must yield DIFFERENT reason lines,
    # proving we assert on causes rather than the overloaded exit code 2.
    _, a = run_gate(_mutate(status="FAIL"))
    _, b = run_gate(_mutate(pass_claimed=False))
    ra = [l for l in a.splitlines() if l.startswith("- ")]
    rb = [l for l in b.splitlines() if l.startswith("- ")]
    assert ra and rb and ra != rb, f"reason lines should differ per cause:\nA={ra}\nB={rb}"


def test_harness_hard_refuses_deploy_flags():
    # the harness itself must be unable to reach a live deploy path.
    for flag in FORBIDDEN_FLAGS:
        try:
            run_gate(BASE_RECEIPT, extra_args=[flag, "x"])
        except AssertionError:
            continue
        raise AssertionError(f"run_gate accepted forbidden flag {flag}")


TESTS = [
    test_positive_control_conformant_is_approved_dry_run,
    test_refusal_teeth_specific_cause,
    test_reasons_are_cause_specific_not_just_exit_code,
    test_harness_hard_refuses_deploy_flags,
]


def _main() -> int:
    assert GATE.is_file(), f"gate not found: {GATE}"
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
