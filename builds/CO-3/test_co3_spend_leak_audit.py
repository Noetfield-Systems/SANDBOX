#!/usr/bin/env python3
"""
Test for CO-3 — the AI Spend Leak Audit deliverable's own proof.

Red-capable on TWO independent axes:

  (A) DATA-DRIVEN — a hand-computed known-leak fixture must yield the exact expected
      leak_rate, AND a minimal mutation of one leak flag must change that number.
      The judge (compute_metrics) is never relaxed: same function, discriminating outputs.

  (B) DOGFOOD — the REAL rendered on-disk report does NOT FAIL the repo language_gate
      (surface=public) -> CHECK_OK; a MINIMAL MUTATION of that same artifact (flip one
      field 'Diagnosis only' -> '100% guaranteed certified') makes the gate FAIL -> CHECK_REJECTED.

Also proves the B4 commercial guards: real-log firewall, Lock-10 banner + local-out path,
SYNTHETIC watermark on every leak_rate, Tier-3/Tier-4 LOCKED, UNPOPULATED handling,
no-receipt-written dogfood.
"""
from __future__ import annotations
import copy, html as _htmllib, importlib.util, json, re
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("co3", HERE / "co3_spend_leak_audit.py")
co3 = importlib.util.module_from_spec(spec); spec.loader.exec_module(co3)

FIXTURE = json.loads((HERE / "synthetic_token_log.json").read_text())
OVERCLAIM_INJECTION = "100% guaranteed certified"

# Hand-computed ground truth over synthetic_token_log.json:
#   leaks (above_policy AND not roi_signal): t-003 150 + t-005 250 + t-007 100 = 500
#   total = 120+200+150+80+250+100+100 = 1000  ->  leak_rate = 50.00%
EXPECTED_LEAK_RATE = 50.00
EXPECTED_TOTAL = 1000.00
EXPECTED_LEAKED = 500.00


def _real_report() -> str:
    out = co3.build()               # build the REAL on-disk artifact (local out/, Lock 10)
    assert out.is_file()
    assert out.parent.name == "out", "Lock 10: report must be written into a local out/ dir"
    return out.read_text(encoding="utf-8")


def _visible_text(html: str) -> str:
    html = re.sub(r"<style.*?</style>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<[^>]+>", " ", html)
    return _htmllib.unescape(html)


# ---------------------------------------------------------------- (A) data-driven
def test_known_leak_fixture_yields_expected_leak_rate():
    m = co3.compute_metrics(FIXTURE)
    assert m["total_spend"] == EXPECTED_TOTAL
    assert m["leaked_spend"] == EXPECTED_LEAKED
    assert m["leak_rate"] == EXPECTED_LEAK_RATE, m


def test_mutating_one_leak_flag_changes_the_rate():
    """Discriminates real vs mutated input with the SAME compute function (not relaxed).
    Give t-003 an ROI signal: it stops being a leak, leaked drops 150 -> 350, rate -> 35.0%."""
    mutant = copy.deepcopy(FIXTURE)
    hit = [e for e in mutant["entries"] if e["task_id"] == "t-003"][0]
    assert hit["above_policy"] is True and hit["roi_signal"] is False
    hit["roi_signal"] = True                      # single-field flip
    m = co3.compute_metrics(mutant)
    assert m["leaked_spend"] == 350.00
    assert m["leak_rate"] == 35.00, m
    assert m["leak_rate"] != EXPECTED_LEAK_RATE   # the metric actually moved


def test_leak_definition_matches_ssot():
    """SSOT: cost leak = above policy AND no measured ROI signal. Neither alone is a leak."""
    assert co3._is_leak({"above_policy": True, "roi_signal": False}) is True
    assert co3._is_leak({"above_policy": True, "roi_signal": None}) is True   # null == no signal
    assert co3._is_leak({"above_policy": True, "roi_signal": True}) is False  # justified premium
    assert co3._is_leak({"above_policy": False, "roi_signal": False}) is False


def test_per_tier_leak_rates_present_and_watermarked():
    m = co3.compute_metrics(FIXTURE)
    tiers = {t["tier"]: t for t in m["tiers"]}
    assert tiers["premium"]["leak_rate"] == round(400 / 600 * 100, 2)   # 66.67
    assert tiers["commodity"]["leak_rate"] == 25.00
    html = _real_report()
    # every leak_rate on the page carries the savings watermark
    assert html.count(co3.LEAK_WATERMARK) >= 1 + len(m["tiers"]), "each leak_rate must be watermarked"


# ---------------------------------------------------------------- real-log firewall
def test_refuses_a_non_synthetic_log():
    real = copy.deepcopy(FIXTURE); real["data_class"] = "PRODUCTION"; real["synthetic"] = False
    with pytest.raises(co3.RealTokenLogRefused):
        co3.assert_synthetic(real)
    # dropping the marker entirely is also refused
    with pytest.raises(co3.RealTokenLogRefused):
        co3.assert_synthetic({"entries": []})


def test_fixture_on_disk_is_marked_synthetic():
    assert FIXTURE["data_class"] == "SYNTHETIC" and FIXTURE["synthetic"] is True


# ---------------------------------------------------------------- UNPOPULATED / empty-sink
def test_null_cost_renders_unpopulated_not_zero():
    stub = copy.deepcopy(FIXTURE)
    stub["entries"].append({"task_id": "t-stub", "model_tier": "premium",
                            "cost_usd": None, "above_policy": True, "roi_signal": False})
    m = co3.compute_metrics(stub)
    assert m["unpopulated_count"] == 1
    assert m["total_spend"] == EXPECTED_TOTAL, "null cost must be excluded from the math, not read as 0"
    html = co3.render(stub, m)
    assert "UNPOPULATED" in html and "t-stub" in html


# ---------------------------------------------------------------- Lock 10 / tiers / claims
def test_lock10_banner_and_source_freshness_badge():
    html = _real_report()
    assert "DO NOT PUSH" in html, "Lock 10 banner missing"
    assert "DATA SOURCE:" in html and "synthetic, not live" in html, "source-freshness badge missing"


def test_tier3_and_tier4_are_locked_never_available():
    html = _real_report()
    text = _visible_text(html).lower()
    assert html.count("LOCKED") >= 2, "Tier-3/Tier-4 must render LOCKED"
    assert "proof-gated" in html
    assert not re.search(r"\bavailable\b", text), "no tier may be labelled available"


def test_no_savings_or_autonomy_claims_in_clean_report():
    report = _real_report()
    text = _visible_text(report).lower()
    # No AFFIRMATIVE overclaim/autonomy phrasing. (The word 'guaranteed' appears ONLY inside the
    # negated disclaimer watermark 'not a guaranteed-savings claim', which is a disclaimer, not a claim.)
    for banned in ("guaranteed savings", "fully autonomous", "runs itself",
                   "100% guaranteed", "certified", "guaranteed outcome", "we guarantee"):
        assert banned not in text, f"clean report must not claim {banned!r}"
    # Strong check: the real judge finds no hard blocker (OVERCLAIM/BANNED_REGISTER/BANNED_SURFACE).
    res = co3.run_language_gate(report, surface="public")
    assert not any(b["type"] in {"OVERCLAIM", "BANNED_REGISTER", "BANNED_SURFACE"}
                   for b in res["blockers"]), res


# ---------------------------------------------------------------- (B) dogfood
def test_positive_real_report_passes_gate():
    res = co3.run_language_gate(_real_report(), surface="public")
    assert res["gate_decision"] != "FAIL", res
    assert res["verdict"] == "CHECK_OK", res


def test_negative_minimal_mutation_overclaim_fails_gate():
    clean = _real_report()
    assert "Diagnosis only" in clean, "anchor for the single-field flip is gone"
    mutant = clean.replace("Diagnosis only", OVERCLAIM_INJECTION, 1)   # flip ONE field
    assert mutant != clean
    res = co3.run_language_gate(mutant, surface="public")
    assert res["gate_decision"] == "FAIL", res
    assert res["verdict"] == "CHECK_REJECTED", res
    assert "OVERCLAIM" in {b["type"] for b in res["blockers"]}, res


def test_mutation_is_minimal_and_gate_not_relaxed():
    clean = _real_report()
    mutant = clean.replace("Diagnosis only", OVERCLAIM_INJECTION, 1)
    assert mutant.replace(OVERCLAIM_INJECTION, "Diagnosis only", 1) == clean   # reversible -> minimal
    assert co3.run_language_gate(clean)["verdict"] == "CHECK_OK"
    assert co3.run_language_gate(mutant)["verdict"] == "CHECK_REJECTED"


def test_dogfood_writes_no_receipt_into_tracked_gate_dir():
    receipts = co3._repo_root() / "language_gate" / "receipts"
    before = {p.name for p in receipts.glob("*")} if receipts.exists() else set()
    co3.run_language_gate(_real_report(), surface="public")
    after = {p.name for p in receipts.glob("*")} if receipts.exists() else set()
    assert before == after, "dogfood must not write a receipt into the tracked gate dir"


TESTS = [
    test_known_leak_fixture_yields_expected_leak_rate,
    test_mutating_one_leak_flag_changes_the_rate,
    test_leak_definition_matches_ssot,
    test_per_tier_leak_rates_present_and_watermarked,
    test_refuses_a_non_synthetic_log,
    test_fixture_on_disk_is_marked_synthetic,
    test_null_cost_renders_unpopulated_not_zero,
    test_lock10_banner_and_source_freshness_badge,
    test_tier3_and_tier4_are_locked_never_available,
    test_no_savings_or_autonomy_claims_in_clean_report,
    test_positive_real_report_passes_gate,
    test_negative_minimal_mutation_overclaim_fails_gate,
    test_mutation_is_minimal_and_gate_not_relaxed,
    test_dogfood_writes_no_receipt_into_tracked_gate_dir,
]


def _main() -> int:
    failed = 0
    for t in TESTS:
        try:
            t(); print(f"PASS  {t.__name__}")
        except AssertionError as e:
            failed += 1; print(f"FAIL  {t.__name__}: {e}")
        except Exception as e:                       # pytest.raises helpers etc.
            failed += 1; print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(TESTS)-failed}/{len(TESTS)} green")
    return 1 if failed else 0


if __name__ == "__main__":
    import sys
    sys.exit(_main())
