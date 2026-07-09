#!/usr/bin/env python3
"""
TH for CO-4a — the offline overclaim lint engine's own proof.

Red-capable two independent ways:
  * data-driven — the engine flags every self-claim fixture line and NO clean line; mutating a
    clean line into an MSP/PSP self-claim flips its flagged status (real vs mutated input).
  * dogfood — the REAL rendered report does NOT FAIL the repo language_gate (public surface);
    a MINIMAL MUTATION injecting '100% guaranteed' into that same artifact FAILs the same gate.

Also asserts: offending spans are redacted (no raw overclaim string in the report), the Lock-10
banner + lint banner are present, the report authors no MSB/MSP/PSP status assertion, and the
dogfood writes no receipt into the tracked language_gate/receipts dir.
"""
from __future__ import annotations
import html as _htmllib, importlib.util, json, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("co4a", HERE / "co4a_overclaim_lint_report.py")
co4a = importlib.util.module_from_spec(spec); spec.loader.exec_module(co4a)

FIXTURE = json.loads((HERE / "sample_web_copy_fixture.json").read_text())
RAW_TRIGGERS = ["we are an MSP", "we process payments", "100% guaranteed",
                "certified", "200+ clients", "TrustField Technologies"]


def _engine():
    return co4a.build_engine()


def _real_report() -> str:
    out = co4a.build()
    assert out.is_file()
    return out.read_text(encoding="utf-8")


def _visible_text(html: str) -> str:
    html = re.sub(r"<style.*?</style>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<[^>]+>", " ", html)
    return _htmllib.unescape(html)


def test_engine_flags_selfclaims_and_leaves_clean_lines_alone():
    eng = _engine()
    lint = co4a.lint_fixture(FIXTURE, eng)
    by_id = {r["id"]: r for r in lint["results"]}
    # every fixture line matches its authored expectation — this is the discriminating assertion
    for r in lint["results"]:
        assert r["flagged"] == r["expect_flagged"], f"{r['id']} flagged={r['flagged']} expected {r['expect_flagged']}"
    # explicit red-capable anchor: an MSP/PSP self-claim line IS flagged; a clean line is NOT
    assert by_id["R1"]["flagged"] and "REGULATORY_COPY_RISK" in by_id["R1"]["classes"]
    assert by_id["R2"]["flagged"] and "REGULATORY_COPY_RISK" in by_id["R2"]["classes"]
    assert by_id["C1"]["flagged"] is False
    assert by_id["C3"]["flagged"] is False
    assert lint["flagged"] == 5 and lint["clean"] == 4


def test_mutating_a_clean_line_into_a_selfclaim_flips_the_flag():
    """Real vs mutated input: the exact same engine that passes the clean line flags its mutation."""
    eng = _engine()
    clean = next(l for l in FIXTURE["lines"] if l["id"] == "C1")
    assert co4a.scan_line(clean["text"], eng) == [] or not co4a.scan_line(clean["text"], eng)
    mutant = clean["text"] + " We are an MSP that processes payments."
    findings = co4a.scan_line(mutant, eng)
    assert findings, "mutated clean line must now be flagged"
    classes = {f.risk_class for f in findings}
    assert "REGULATORY_COPY_RISK" in classes or "CONFLICT_PHRASE" in classes


def test_offending_spans_are_redacted_no_raw_trigger_in_report():
    html = _real_report()
    for bad in RAW_TRIGGERS:
        assert bad not in html, f"raw overclaim string leaked into report: {bad!r}"
    assert "[flagged:" in html, "redaction tags missing from flagged rows"


def test_report_has_lock10_and_lint_banners_and_no_status_assertion():
    html = _real_report()
    assert "DO NOT PUSH" in html, "Lock 10 banner missing"
    assert co4a.LINT_BANNER in html, "lint/compliance banner missing"
    assert co4a.SYNTHETIC_WM in html, "synthetic watermark missing"
    text = _visible_text(html).lower()
    # authors NO RPAA/FINTRAC/MSB status assertion about the entity
    for forbidden in ("trustfield is an msb", "trustfield is a registered",
                      "we are an msp", "we are registered", "rpaa compliant"):
        assert forbidden not in text, f"report must not assert status: {forbidden!r}"


def test_positive_real_report_passes_gate():
    res = co4a.run_language_gate(_real_report(), surface="public")
    assert res["gate_decision"] != "FAIL", res
    assert res["verdict"] == "CHECK_OK", res


def test_negative_minimal_mutation_overclaim_fails_gate():
    clean = _real_report()
    assert co4a.LINT_ANCHOR in clean, "anchor for the single-field flip is gone"
    mutant = clean.replace(co4a.LINT_ANCHOR, "100% guaranteed certified", 1)
    assert mutant != clean
    res = co4a.run_language_gate(mutant, surface="public")
    assert res["gate_decision"] == "FAIL", res
    assert res["verdict"] == "CHECK_REJECTED", res
    assert "OVERCLAIM" in {b["type"] for b in res["blockers"]}, res


def test_mutation_is_minimal_and_gate_is_not_relaxed():
    clean = _real_report()
    mutant = clean.replace(co4a.LINT_ANCHOR, "100% guaranteed certified", 1)
    # reversing the single injection reproduces the clean artifact byte-for-byte
    assert mutant.replace("100% guaranteed certified", co4a.LINT_ANCHOR, 1) == clean
    assert co4a.run_language_gate(clean)["verdict"] == "CHECK_OK"
    assert co4a.run_language_gate(mutant)["verdict"] == "CHECK_REJECTED"


def test_dogfood_writes_no_receipt_into_tracked_gate_dir():
    receipts = co4a._repo_root() / "language_gate" / "receipts"
    before = {p.name for p in receipts.glob("*")} if receipts.exists() else set()
    co4a.run_language_gate(_real_report(), surface="public")
    after = {p.name for p in receipts.glob("*")} if receipts.exists() else set()
    assert before == after, "dogfood must not write a receipt into the tracked gate dir"


TESTS = [
    test_engine_flags_selfclaims_and_leaves_clean_lines_alone,
    test_mutating_a_clean_line_into_a_selfclaim_flips_the_flag,
    test_offending_spans_are_redacted_no_raw_trigger_in_report,
    test_report_has_lock10_and_lint_banners_and_no_status_assertion,
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
