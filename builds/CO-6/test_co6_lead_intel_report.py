#!/usr/bin/env python3
"""
TH for CO-6 — the Gateway Lead-Intelligence Dashboard's own proof.

Two independent red-capable teeth:

  (A) DATA-DRIVEN — the rendered priority_tag breakdown counts MUST equal an independent
      Counter over the mock rows. Mutating any row's priority_tag (real -> mutated input)
      changes the independent count and breaks the assertion. Not green-by-construction.

  (B) DOGFOOD — the repo language_gate (surface=public) is the judge over the rendered HTML.
      POSITIVE: the real dashboard does NOT FAIL -> CHECK_OK.
      NEGATIVE: a MINIMAL single-field mutation injecting an overclaim ("100% guaranteed
      certified") FAILs the gate -> CHECK_REJECTED. Reversing the injection reproduces the
      clean artifact byte-for-byte; the gate is never relaxed.

Also proves the B4 deliverable guards: MOCK-DATA watermark + DO-NOT-PUSH banner present;
null/empty fields render an explicit UNPOPULATED bucket (never a silent 0/'low'); DEFERRED
items render LOCKED, never "available"; dogfood writes no receipt into the tracked gate dir.
"""
from __future__ import annotations
import html as _htmllib, importlib.util, json, re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("co6", HERE / "co6_lead_intel_report.py")
co6 = importlib.util.module_from_spec(spec); spec.loader.exec_module(co6)

MOCK = json.loads((HERE / "mock_leads.json").read_text())
ROWS = MOCK["rows"]
OVERCLAIM_INJECTION = "100% guaranteed certified"


def _real_dashboard() -> str:
    out = co6.build()
    assert out.is_file()
    return out.read_text(encoding="utf-8")


def _visible_text(html: str) -> str:
    html = re.sub(r"<style.*?</style>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<[^>]+>", " ", html)
    return _htmllib.unescape(html)


def _independent_counts() -> Counter:
    """Count priority_tag the way the reader would expect, WITHOUT calling co6.breakdown —
    a null/empty/unknown tag is UNPOPULATED, otherwise the canonical bucket."""
    c = Counter()
    for r in ROWS:
        raw = r.get("priority_tag")
        if raw is None or str(raw).strip().lower() not in ("high", "medium", "low"):
            c["UNPOPULATED"] += 1
        else:
            c[str(raw).strip().lower()] += 1
    return c


# ---------- (A) data-driven: breakdown counts match the mock rows ----------

def test_breakdown_counts_match_mock_rows():
    exp = _independent_counts()
    bd = co6.breakdown(ROWS)
    assert bd["counts"]["high"] == exp["high"], bd
    assert bd["counts"]["medium"] == exp["medium"], bd
    assert bd["counts"]["low"] == exp["low"], bd
    assert bd["unpopulated"] == exp["UNPOPULATED"], bd
    assert bd["populated_total"] == exp["high"] + exp["medium"] + exp["low"]
    assert bd["grand_total"] == len(ROWS)
    # every row is accounted for exactly once (no silent drop)
    assert bd["counts"]["high"] + bd["counts"]["medium"] + bd["counts"]["low"] + bd["unpopulated"] == len(ROWS)


def test_rendered_counts_appear_in_html_and_discriminate_mutation():
    html = _real_dashboard()
    exp = _independent_counts()
    # the priority cards render each count; assert the exact numbers are present
    for k in ("high", "medium", "low"):
        assert re.search(rf'>{exp[k]}</div>\s*<div class="k">', html), f"count for {k} not rendered"
    # RED-CAPABLE: mutate one row's priority_tag and the independent count must move,
    # which would break test_breakdown_counts_match_mock_rows against the on-disk data.
    mutated_rows = [dict(r) for r in ROWS]
    # flip the first 'high' row to 'low'
    for r in mutated_rows:
        if r.get("priority_tag") == "high":
            r["priority_tag"] = "low"; break
    mbd = co6.breakdown(mutated_rows)
    assert mbd["counts"]["high"] == exp["high"] - 1, "mutation did not change the high count"
    assert mbd["counts"]["low"] == exp["low"] + 1, "mutation did not change the low count"
    assert mbd != co6.breakdown(ROWS), "breakdown does not discriminate real vs mutated input"


def test_unpopulated_is_explicit_not_folded_into_low():
    # a null priority_tag must NOT be silently counted as 'low' or 0 — it is its own bucket.
    assert any(r.get("priority_tag") is None for r in ROWS), "fixture lost its UNPOPULATED row"
    bd = co6.breakdown(ROWS)
    assert bd["unpopulated"] >= 1
    html = _real_dashboard()
    assert "UNPOPULATED" in html, "UNPOPULATED badge/bucket missing from render"
    # populated denominator excludes UNPOPULATED
    assert bd["populated_total"] == len(ROWS) - bd["unpopulated"]


# ---------- B4 deliverable guards ----------

def test_mock_watermark_and_donotpush_banner_present():
    html = _real_dashboard()
    assert "DO NOT PUSH" in html, "Lock 10 DO-NOT-PUSH banner missing"
    assert "MOCK DATA" in html, "MOCK-DATA watermark missing"
    assert "SYNTHETIC — not a guaranteed claim" in html, "synthetic metric watermark missing"


def test_deferred_items_locked_never_available():
    html = _real_dashboard()
    text = _visible_text(html).lower()
    assert html.count("LOCKED") >= 2, "DEFERRED items must render LOCKED"
    assert "proof-gated" in html
    assert not re.search(r"\bavailable\b", text), "no capability may be labelled available"


def test_no_pii_only_placeholder_contacts():
    # every non-null mock contact is an obvious .invalid placeholder — no real address shape.
    for r in ROWS:
        c = r.get("contact")
        if c:
            assert c.endswith(".invalid"), f"mock contact looks real: {c}"


# ---------- (B) dogfood: language_gate over the rendered HTML ----------

def test_positive_real_dashboard_passes_gate():
    res = co6.run_language_gate(_real_dashboard(), surface="public")
    assert res["gate_decision"] != "FAIL", res
    assert res["verdict"] == "CHECK_OK", res


def test_negative_minimal_mutation_overclaim_fails_gate():
    clean = _real_dashboard()
    assert "not a guaranteed claim" in clean, "anchor for the single-field flip is gone"
    mutant = clean.replace("not a guaranteed claim", OVERCLAIM_INJECTION, 1)   # flip ONE field
    assert mutant != clean
    res = co6.run_language_gate(mutant, surface="public")
    assert res["gate_decision"] == "FAIL", res
    assert res["verdict"] == "CHECK_REJECTED", res
    assert "OVERCLAIM" in {b["type"] for b in res["blockers"]}, res


def test_mutation_is_minimal_and_gate_is_not_relaxed():
    clean = _real_dashboard()
    mutant = clean.replace("not a guaranteed claim", OVERCLAIM_INJECTION, 1)
    # minimality: reversing the single injection reproduces the clean artifact byte-for-byte
    assert mutant.replace(OVERCLAIM_INJECTION, "not a guaranteed claim", 1) == clean
    assert co6.run_language_gate(clean)["verdict"] == "CHECK_OK"
    assert co6.run_language_gate(mutant)["verdict"] == "CHECK_REJECTED"


def test_dogfood_writes_no_receipt_into_tracked_gate_dir():
    receipts = co6._repo_root() / "language_gate" / "receipts"
    before = {p.name for p in receipts.glob("*")} if receipts.exists() else set()
    co6.run_language_gate(_real_dashboard(), surface="public")
    after = {p.name for p in receipts.glob("*")} if receipts.exists() else set()
    assert before == after, "dogfood must not write a receipt into the tracked gate dir"


TESTS = [
    test_breakdown_counts_match_mock_rows,
    test_rendered_counts_appear_in_html_and_discriminate_mutation,
    test_unpopulated_is_explicit_not_folded_into_low,
    test_mock_watermark_and_donotpush_banner_present,
    test_deferred_items_locked_never_available,
    test_no_pii_only_placeholder_contacts,
    test_positive_real_dashboard_passes_gate,
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
