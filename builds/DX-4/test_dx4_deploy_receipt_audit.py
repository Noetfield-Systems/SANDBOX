#!/usr/bin/env python3
"""
TH for DX-4 — the deploy-receipt auditor's own proof.

  * REAL step10a watched-deploy receipt (content_identity_confirmed=false) -> FAIL,
    with the exact rollback_hint pinned to its recorded pre_live_version_id.
  * a MINIMAL MUTATION of the real receipt (flip content_identity_confirmed -> true) -> PASS.
  * flipping it back to false re-FAILs (no relaxation of the success predicate).
  * a deploy receipt with a nonzero deploy_exit_code -> FAIL even if identity is confirmed.
  * a receipt with no deploy_exit_code -> BLOCKED (nothing to roll back).
  * running the auditor never edits the subject receipt (sha unchanged); verdict -> scratch.
  * verdict vocab is PASS/FAIL/BLOCKED, never a bare governance PASS with authority.
"""
from __future__ import annotations
import copy, hashlib, importlib.util, json, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("dx4", HERE / "dx4_deploy_receipt_audit.py")
dx4 = importlib.util.module_from_spec(spec); spec.loader.exec_module(dx4)
REAL = json.loads(dx4.DEFAULT_RECEIPT.read_text())
PRE_VERSION = REAL["pre_live_version_id"]  # 628ebc37-... — from the real on-disk artifact


def _confirmed() -> dict:
    """Minimal mutation of the REAL receipt: flip the one identity field true."""
    r = copy.deepcopy(REAL)
    assert r["content_identity_confirmed"] is False, "fixture assumption: real receipt is unconfirmed"
    r["content_identity_confirmed"] = True
    return r


def test_real_step10a_is_FAIL_for_content_identity():
    res = dx4.classify(REAL)
    assert res["classification"] == "FAIL", res
    assert res["predicate"]["identity_ok"] is False, res
    assert res["predicate"]["deploy_exit_code"] == 0, res  # exit was 0; identity is why it fails
    blob = " ".join(res["reasons"]).lower()
    assert "content identity not confirmed" in blob, blob


def test_real_step10a_rollback_hint_is_exact():
    res = dx4.classify(REAL)
    assert res["rollback_hint"] == (
        f"wrangler versions deploy {PRE_VERSION} --name sourcea-brain-chat-v1"
    ), res["rollback_hint"]


def test_minimally_mutated_confirmed_is_PASS():
    res = dx4.classify(_confirmed())
    assert res["classification"] == "PASS", res
    assert res["predicate"]["deploy_success"] is True, res
    assert res["rollback_hint"] is None, res  # nothing to roll back on PASS


def test_flip_back_re_fails_no_relaxation():
    good = _confirmed()
    bad = copy.deepcopy(good); bad["content_identity_confirmed"] = False
    assert dx4.classify(bad)["classification"] == "FAIL", "flipping identity false must re-FAIL"


def test_nonzero_exit_is_FAIL_even_when_identity_confirmed():
    r = _confirmed(); r["deploy_exit_code"] = 137
    res = dx4.classify(r)
    assert res["classification"] == "FAIL", res
    assert any("nonzero" in x for x in res["reasons"]), res
    assert res["rollback_hint"].endswith("--name sourcea-brain-chat-v1"), res


def test_no_exit_code_is_BLOCKED():
    r = copy.deepcopy(REAL); del r["deploy_exit_code"]
    res = dx4.classify(r)
    assert res["classification"] == "BLOCKED", res
    assert res["rollback_hint"] is None, res


def test_running_auditor_never_edits_subject():
    before = hashlib.sha256(dx4.DEFAULT_RECEIPT.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory() as tmp:
        rc = subprocess.run([sys.executable, str(HERE / "dx4_deploy_receipt_audit.py"),
                             "--emit-verdict-dir", tmp], text=True, capture_output=True)
        assert rc.returncode == 1, f"real step10a should exit 1 (FAIL): {rc.stdout}{rc.stderr}"
        assert (Path(tmp) / f"verdict-{dx4.DEFAULT_RECEIPT.stem}.json").is_file(), "verdict not written to scratch"
    after = hashlib.sha256(dx4.DEFAULT_RECEIPT.read_bytes()).hexdigest()
    assert before == after, "subject receipt was modified!"


def test_advisory_stamp_and_no_bare_pass():
    for r in (REAL, _confirmed()):
        res = dx4.classify(r)
        assert res["origin"] == "sandbox-advisory" and res["authority"] == "none", res
        assert res["classification"] in ("PASS", "FAIL", "BLOCKED")


TESTS = [test_real_step10a_is_FAIL_for_content_identity, test_real_step10a_rollback_hint_is_exact,
         test_minimally_mutated_confirmed_is_PASS, test_flip_back_re_fails_no_relaxation,
         test_nonzero_exit_is_FAIL_even_when_identity_confirmed, test_no_exit_code_is_BLOCKED,
         test_running_auditor_never_edits_subject, test_advisory_stamp_and_no_bare_pass]


def _main() -> int:
    failed = 0
    for t in TESTS:
        try: t(); print(f"PASS  {t.__name__}")
        except AssertionError as e: failed += 1; print(f"FAIL  {t.__name__}: {e}")
    print(f"\n{len(TESTS)-failed}/{len(TESTS)} green")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_main())
