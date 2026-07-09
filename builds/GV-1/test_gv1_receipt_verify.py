#!/usr/bin/env python3
"""
TH for GV-1 — the trust spine's own proof.

  * real M03 -> CHECK_REJECTED citing the 3 missing required fields + PARTIAL + bare-$0 + round timestamp.
  * a MINIMAL MUTATION of M03 (add the 3 missing fields, PASS, accounting_note, non-round ts) -> CHECK_OK.
  * removing one required field from the conformant flips it back to CHECK_REJECTED (no schema relaxation).
  * running the verifier never edits the subject receipt (sha unchanged).
  * verdict vocab is CHECK_OK/CHECK_REJECTED, never PASS.
  * reconcile: auditor agrees with M03's own PARTIAL self-label (no false disagreement).
"""
from __future__ import annotations
import copy, hashlib, importlib.util, json, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("gv1", HERE / "gv1_receipt_verify.py")
gv1 = importlib.util.module_from_spec(spec); spec.loader.exec_module(gv1)
M03 = json.loads(gv1.DEFAULT_RECEIPT.read_text())


def _conformant() -> dict:
    r = copy.deepcopy(M03)
    r["recorded_at"] = "2026-07-08T13:30:47Z"
    r["executed_at"] = "2026-07-08T13:30:47Z"            # non-round
    r["evidence_artifacts"] = [{"claim": "6 GTM routes fetched", "artifact_path": "receipts/p0pgr/artifacts/M03/routes.json"}]
    r["founder_authorization_ref"] = "receipts/p0pgr/founder/FOUNDER-UNLOCK-PHASE2-CLOUD-ONLY-20260708.json"
    r["quality_state"] = "PASS"
    r["cost"] = dict(r["cost"]); r["cost"]["accounting_note"] = "session-cost (LLM-authored analysis); no metered API spend"
    return r


def test_real_M03_is_rejected_for_the_right_reasons():
    res = gv1.verify(M03)
    assert res["verdict"] == "CHECK_REJECTED", res
    blob = " ".join(res["schema_errors"] + res["provenance_reasons"])
    for needle in ("recorded_at", "evidence_artifacts", "founder_authorization_ref", "PARTIAL", "bare $0", "round :00"):
        assert needle in blob, f"missing citation {needle!r} in: {blob}"


def test_minimally_mutated_conformant_is_accepted():
    res = gv1.verify(_conformant())
    assert res["verdict"] == "CHECK_OK", res


def test_no_schema_relaxation_removing_required_flips_back():
    good = _conformant()
    for field in ("founder_authorization_ref", "recorded_at", "evidence_artifacts"):
        bad = copy.deepcopy(good); del bad[field]
        assert gv1.verify(bad)["verdict"] == "CHECK_REJECTED", f"removing {field} should re-reject"


def test_running_verifier_never_edits_subject():
    before = hashlib.sha256(gv1.DEFAULT_RECEIPT.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory() as tmp:
        rc = subprocess.run([sys.executable, str(HERE / "gv1_receipt_verify.py"),
                             "--emit-verdict-dir", tmp], text=True, capture_output=True)
        assert rc.returncode == 1, "real M03 should exit 1 (rejected)"
        assert (Path(tmp) / f"verdict-{gv1.DEFAULT_RECEIPT.stem}.json").is_file(), "verdict not written to scratch"
    after = hashlib.sha256(gv1.DEFAULT_RECEIPT.read_bytes()).hexdigest()
    assert before == after, "subject receipt was modified!"


def test_never_emits_pass():
    for r in (M03, _conformant()):
        assert gv1.verify(r)["verdict"] in ("CHECK_OK", "CHECK_REJECTED")


def test_reconcile_agrees_with_partial_self_label():
    # M03 says quality_state=PARTIAL; auditor rejects -> both non-PASS, no false disagreement
    assert gv1.verify(M03)["reconcile"]["auditor_disagrees_with_receipt"] is False
    # conformant says PASS; auditor CHECK_OK -> agree
    assert gv1.verify(_conformant())["reconcile"]["auditor_disagrees_with_receipt"] is False


TESTS = [test_real_M03_is_rejected_for_the_right_reasons, test_minimally_mutated_conformant_is_accepted,
         test_no_schema_relaxation_removing_required_flips_back, test_running_verifier_never_edits_subject,
         test_never_emits_pass, test_reconcile_agrees_with_partial_self_label]


def _main() -> int:
    failed = 0
    for t in TESTS:
        try: t(); print(f"PASS  {t.__name__}")
        except AssertionError as e: failed += 1; print(f"FAIL  {t.__name__}: {e}")
    print(f"\n{len(TESTS)-failed}/{len(TESTS)} green")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_main())
