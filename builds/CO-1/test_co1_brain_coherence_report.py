#!/usr/bin/env python3
"""
TH for CO-1 — the Brain Coherence Report deliverable's own proof.

Red-capable by construction: the positive fixture is the REAL rendered on-disk report
(built from the 7 brain-audit diagnostic categories + the real template); the negative
fixture is that SAME artifact with ONE field flipped into an overclaim ("100% guaranteed
certified"). The repo language_gate (surface=public) is the judge.

  * the report renders the 7 real diagnostic categories, a 0-5 rubric, and the Lock-10 banner.
  * Tier-3 / Tier-4 are rendered LOCKED / proof-gated, never "available".
  * no autonomy / guaranteed-outcome claims in the clean report.
  * POSITIVE — the real rendered report does NOT FAIL the gate -> CHECK_OK.
  * NEGATIVE — a MINIMAL MUTATION (inject one overclaim) FAILs the gate -> CHECK_REJECTED.
  * minimality — negative differs from positive by exactly the injected phrase (no strawman).
  * the gate is not relaxed: the judge that passes the clean report is the one that FAILs the mutant.
  * dogfood writes no receipt into the tracked language_gate/receipts dir (scan/decide only).
"""
from __future__ import annotations
import html as _htmllib, importlib.util, json, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("co1", HERE / "co1_brain_coherence_report.py")
co1 = importlib.util.module_from_spec(spec); spec.loader.exec_module(co1)

FINDINGS = json.loads((HERE / "sample_findings.json").read_text())
EXPECTED_CATEGORY_IDS = {
    "stack_fragmentation", "definition_drift", "agent_theater", "missing_receipts",
    "dead_workflows", "founder_overload", "missing_decision_spine",
}
OVERCLAIM_INJECTION = "100% guaranteed certified"


def _real_report() -> str:
    # build the REAL on-disk artifact (local out/, Lock 10) and read it back.
    out = co1.build()
    assert out.is_file()
    return out.read_text(encoding="utf-8")


def _visible_text(html: str) -> str:
    """Reader-visible prose: drop <style>/<script> blocks and tags. Used so CSS values
    like height:100% or the word 'unavailable' don't masquerade as marketing claims."""
    html = re.sub(r"<style.*?</style>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<[^>]+>", " ", html)
    return _htmllib.unescape(html)


def test_report_has_seven_categories_rubric_and_lock10_banner():
    html = _real_report()
    ids = {c["id"] for c in FINDINGS["categories"]}
    assert ids == EXPECTED_CATEGORY_IDS, f"category set drifted from brain-audit-v1: {ids}"
    for c in FINDINGS["categories"]:
        assert c["name"] in html, f"missing rendered section for {c['name']}"
    assert "DO NOT PUSH" in html, "Lock 10 banner missing"
    assert "Scoring rubric" in html and "0-5" in html, "rubric missing"
    # rubric shows all six levels 0..5
    for lvl in FINDINGS["rubric"]["levels"]:
        assert lvl["label"] in html


def test_tier3_and_tier4_are_locked_never_available():
    html = _real_report()
    text = _visible_text(html).lower()
    # the two advanced tiers must be gated, not offered
    assert html.count("LOCKED") >= 2, "Tier-3/Tier-4 must render LOCKED"
    assert "proof-gated" in html
    # no tier may be presented as generically 'available' (word-boundary; 'unavailable' is fine)
    assert not re.search(r"\bavailable\b", text), "no tier may be labelled available"


def test_no_autonomy_or_guarantee_claims_in_clean_report():
    text = _visible_text(_real_report()).lower()
    for banned in ("guarantee", "guaranteed", "fully autonomous", "runs itself",
                   "100% guaranteed", "certified", "zero-drift proven", "guaranteed outcome"):
        assert banned not in text, f"clean report must not claim {banned!r}"


def test_positive_real_report_passes_gate():
    res = co1.run_language_gate(_real_report(), surface="public")
    assert res["gate_decision"] != "FAIL", res
    assert res["verdict"] == "CHECK_OK", res


def test_negative_minimal_mutation_overclaim_fails_gate():
    clean = _real_report()
    assert "Diagnosis only" in clean, "anchor for the single-field flip is gone"
    mutant = clean.replace("Diagnosis only", OVERCLAIM_INJECTION, 1)   # flip ONE field
    assert mutant != clean
    res = co1.run_language_gate(mutant, surface="public")
    assert res["gate_decision"] == "FAIL", res
    assert res["verdict"] == "CHECK_REJECTED", res
    kinds = {b["type"] for b in res["blockers"]}
    assert "OVERCLAIM" in kinds, res


def test_mutation_is_minimal_and_gate_is_not_relaxed():
    clean = _real_report()
    mutant = clean.replace("Diagnosis only", OVERCLAIM_INJECTION, 1)
    # minimality: reversing the single injection reproduces the clean artifact byte-for-byte
    assert mutant.replace(OVERCLAIM_INJECTION, "Diagnosis only", 1) == clean
    # same judge, opposite verdicts -> passing the clean report is not green-by-construction
    assert co1.run_language_gate(clean)["verdict"] == "CHECK_OK"
    assert co1.run_language_gate(mutant)["verdict"] == "CHECK_REJECTED"


def test_dogfood_writes_no_receipt_into_tracked_gate_dir():
    receipts = co1._repo_root() / "language_gate" / "receipts"
    before = {p.name for p in receipts.glob("*")} if receipts.exists() else set()
    co1.run_language_gate(_real_report(), surface="public")
    after = {p.name for p in receipts.glob("*")} if receipts.exists() else set()
    assert before == after, "dogfood must not write a receipt into the tracked gate dir"


TESTS = [
    test_report_has_seven_categories_rubric_and_lock10_banner,
    test_tier3_and_tier4_are_locked_never_available,
    test_no_autonomy_or_guarantee_claims_in_clean_report,
    test_positive_real_report_passes_gate,
    test_negative_minimal_mutation_overclaim_fails_gate,
    test_mutation_is_minimal_and_gate_is_not_relaxed,
    test_dogfood_writes_no_receipt_into_tracked_gate_dir,
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
    import sys
    sys.exit(_main())
