#!/usr/bin/env python3
"""
TH for CO-5 — the Signal Factory receipt verifier's own proof.

Red-capable by data-driven discrimination (real vs mutated input):
  * the conformant fixture -> CHECK_OK.
  * author == subject -> CHECK_REJECTED citing the independence rule.
  * any score pushed out of 0..5 -> CHECK_REJECTED citing out-of-bounds.
  * a bad enum / missing required field -> CHECK_REJECTED (schema never relaxed).
  * risk_score that stops matching scores.risk -> CHECK_REJECTED.
  * running the verifier never edits the subject receipt (sha unchanged).
  * verdict vocab is CHECK_OK / CHECK_REJECTED, never PASS.
"""
from __future__ import annotations
import copy, hashlib, importlib.util, json, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("co5", HERE / "co5_signal_receipt_verify.py")
co5 = importlib.util.module_from_spec(spec); spec.loader.exec_module(co5)

CONFORMANT = json.loads((HERE / "fixtures" / "receipt_conformant.json").read_text())


def test_conformant_receipt_is_check_ok():
    res = co5.verify(CONFORMANT)
    assert res["verdict"] == "CHECK_OK", res
    assert not res["schema_errors"] and not res["contract_reasons"], res


def test_author_equals_subject_is_rejected():
    bad = copy.deepcopy(CONFORMANT)
    bad["subject"] = bad["author"]
    res = co5.verify(bad)
    assert res["verdict"] == "CHECK_REJECTED", res
    assert any("author == subject" in r for r in res["contract_reasons"]), res


def test_author_equals_subject_bundled_fixture():
    r = json.loads((HERE / "fixtures" / "receipt_author_equals_subject.json").read_text())
    assert co5.verify(r)["verdict"] == "CHECK_REJECTED"


def test_out_of_bounds_score_is_rejected():
    for dim in ("trust", "risk", "automation_value", "commercial_value"):
        for bad_val in (6, 7, -1, 99):
            bad = copy.deepcopy(CONFORMANT)
            bad["scores"] = dict(bad["scores"]); bad["scores"][dim] = bad_val
            if dim == "risk":
                bad["risk_score"] = bad_val  # keep mirror so the failure is purely the bound
            res = co5.verify(bad)
            assert res["verdict"] == "CHECK_REJECTED", (dim, bad_val, res)


def test_out_of_bounds_bundled_fixture():
    r = json.loads((HERE / "fixtures" / "receipt_score_out_of_bounds.json").read_text())
    assert co5.verify(r)["verdict"] == "CHECK_REJECTED"


def test_bad_enum_and_missing_required_rejected_no_relaxation():
    bad_enum = copy.deepcopy(CONFORMANT); bad_enum["classification"] = "not_a_class"
    assert co5.verify(bad_enum)["verdict"] == "CHECK_REJECTED"
    for field in ("signal_id", "author", "subject", "scores", "result", "status"):
        miss = copy.deepcopy(CONFORMANT); del miss[field]
        assert co5.verify(miss)["verdict"] == "CHECK_REJECTED", f"removing {field} should reject"


def test_risk_score_mismatch_rejected():
    bad = copy.deepcopy(CONFORMANT)
    bad["risk_score"] = (CONFORMANT["scores"]["risk"] + 1) % 6
    res = co5.verify(bad)
    assert res["verdict"] == "CHECK_REJECTED", res
    assert any("risk_score" in r for r in res["contract_reasons"]), res


def test_verifier_never_edits_subject_and_writes_to_scratch():
    subj = HERE / "fixtures" / "receipt_conformant.json"
    before = hashlib.sha256(subj.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory() as tmp:
        rc = subprocess.run(
            [sys.executable, str(HERE / "co5_signal_receipt_verify.py"),
             "--receipt", str(subj), "--emit-verdict-dir", tmp],
            text=True, capture_output=True,
        )
        assert rc.returncode == 0, rc.stderr  # conformant -> exit 0
        assert (Path(tmp) / f"verdict-{subj.stem}.json").is_file(), "verdict not written to scratch"
    after = hashlib.sha256(subj.read_bytes()).hexdigest()
    assert before == after, "subject receipt was modified!"


def test_never_emits_pass():
    for r in (CONFORMANT, {"scores": {}}):
        assert co5.verify(r)["verdict"] in ("CHECK_OK", "CHECK_REJECTED")


TESTS = [
    test_conformant_receipt_is_check_ok,
    test_author_equals_subject_is_rejected,
    test_author_equals_subject_bundled_fixture,
    test_out_of_bounds_score_is_rejected,
    test_out_of_bounds_bundled_fixture,
    test_bad_enum_and_missing_required_rejected_no_relaxation,
    test_risk_score_mismatch_rejected,
    test_verifier_never_edits_subject_and_writes_to_scratch,
    test_never_emits_pass,
]


def _main() -> int:
    failed = 0
    for t in TESTS:
        try:
            t(); print(f"PASS  {t.__name__}")
        except AssertionError as e:
            failed += 1; print(f"FAIL  {t.__name__}: {e}")
    print(f"\n{len(TESTS)-failed}/{len(TESTS)} green")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_main())
