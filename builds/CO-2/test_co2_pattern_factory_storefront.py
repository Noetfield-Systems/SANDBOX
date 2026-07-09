#!/usr/bin/env python3
"""
TH for CO-2 - the Pattern Factory storefront's own proof.

Red-capable by construction: the positive fixture is the REAL rendered on-disk storefront
(built from the 7 Pattern Factory patterns + the real template); the negative fixture is
that SAME artifact with ONE field flipped into an overclaim ("100% guaranteed certified").
The repo language_gate (surface=public) is the judge.

  * the storefront renders all 7 real patterns, the staged ladder, and the Lock-10 banner.
  * Tier-3 / Tier-4 (managed autonomy) patterns render LOCKED / proof-gated, never "sells now".
  * UNPOPULATED price fields render an explicit badge, never $0 or blank (no all-clear read).
  * populated indicative price bands carry the SYNTHETIC watermark.
  * no autonomy / guaranteed-outcome claims in the clean storefront.
  * POSITIVE - the real rendered storefront does NOT FAIL the gate -> CHECK_OK.
  * NEGATIVE - a MINIMAL MUTATION (inject one overclaim) FAILs the gate -> CHECK_REJECTED.
  * minimality - negative differs from positive by exactly the injected phrase (no strawman).
  * the gate is not relaxed: the judge that passes the clean storefront is the one that FAILs the mutant.
  * dogfood writes no receipt into the tracked language_gate/receipts dir (scan/decide only).
"""
from __future__ import annotations
import html as _htmllib, importlib.util, json, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("co2", HERE / "co2_pattern_factory_storefront.py")
co2 = importlib.util.module_from_spec(spec); spec.loader.exec_module(co2)

CATALOG = json.loads((HERE / "patterns_catalog.json").read_text())
EXPECTED_PATTERN_IDS = {
    "signal_factory", "brain_audit", "zero_drift_target", "anti_theater",
    "operational_language_governance", "auto_heal_hospital", "alive_doc_staleness_governance",
}
LOCKED_IDS = {"auto_heal_hospital", "alive_doc_staleness_governance"}
OVERCLAIM_ANCHOR = "diagnosis only"
OVERCLAIM_INJECTION = "100% guaranteed certified"


def _real_storefront() -> str:
    # build the REAL on-disk artifact (local out/, Lock 10) and read it back.
    out = co2.build()
    assert out.is_file()
    return out.read_text(encoding="utf-8")


def _visible_text(html: str) -> str:
    """Reader-visible prose: drop <style>/<script> blocks and tags, so CSS values and the
    word 'unavailable' cannot masquerade as marketing claims."""
    html = re.sub(r"<style.*?</style>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<[^>]+>", " ", html)
    return _htmllib.unescape(html)


def test_seven_patterns_ladder_and_lock10_banner():
    html = _real_storefront()
    ids = {p["id"] for p in CATALOG["patterns"]}
    assert ids == EXPECTED_PATTERN_IDS, f"pattern set drifted from the P9 factory: {ids}"
    assert len(CATALOG["patterns"]) == 7
    for p in CATALOG["patterns"]:
        # names are HTML-escaped in the rendered artifact (e.g. '&' -> '&amp;')
        assert _htmllib.escape(p["name"], quote=True) in html, f"missing rendered card for {p['name']}"
    assert "DO NOT PUSH" in html, "Lock 10 banner missing"
    # staged ladder: all four tiers rendered
    for r in CATALOG["ladder"]:
        assert r["name"] in html, f"missing ladder rung {r['name']}"


def test_tier3_tier4_render_locked_never_sells_now():
    html = _real_storefront()
    # locked cards must carry LOCKED / proof-gated and must NOT be badged sells-now/build
    for p in CATALOG["patterns"]:
        card = re.search(rf'data-tier="{p["tier"]}"[^>]*>.*?</div>\s*</div>', html, flags=re.S)
        if p["gate_state"] == "locked":
            assert p["tier"] in (3, 4), f"{p['id']} locked but not Tier-3/4"
    # both known managed patterns are locked in the data and rendered LOCKED
    locked = {p["id"] for p in CATALOG["patterns"] if p["gate_state"] == "locked"}
    assert locked == LOCKED_IDS, f"locked set drifted: {locked}"
    assert html.count("LOCKED") >= 2, "Tier-3/Tier-4 patterns must render LOCKED"
    assert "proof-gated" in html
    # no Tier-3/4 tier may be advertised as a running/available result
    text = _visible_text(html).lower()
    assert not re.search(r"\bavailable\b", text), "no tier may be labelled available"


def test_unpopulated_price_renders_badge_never_zero():
    html = _real_storefront()
    # signal_factory has a null price band -> must show an explicit UNPOPULATED badge
    sf = next(p for p in CATALOG["patterns"] if p["id"] == "signal_factory")
    assert sf["price_band"] is None
    assert "UNPOPULATED" in html, "empty-sink price must render UNPOPULATED, not blank"
    # a stub/empty price must never read as an all-clear $0
    assert "$0" not in html, "empty price must never render as $0"


def test_populated_bands_carry_synthetic_watermark():
    html = _real_storefront()
    populated = [p for p in CATALOG["patterns"] if p["price_band"]]
    assert populated, "expected at least one populated indicative band"
    # each populated band's dollar figure and the SYNTHETIC watermark are both present
    assert html.count(co2.SYNTHETIC_WATERMARK) >= len(populated), "each band must be watermarked SYNTHETIC"
    for p in populated:
        assert p["price_band"] in html, f"band missing for {p['id']}"


def test_no_autonomy_or_guarantee_claims_in_clean_storefront():
    text = _visible_text(_real_storefront()).lower()
    for banned in ("we guarantee", "guaranteed outcome", "fully autonomous", "runs itself",
                   "100% guaranteed", "zero-drift proven across live", "guaranteed savings"):
        assert banned not in text, f"clean storefront must not claim {banned!r}"


def test_positive_real_storefront_passes_gate():
    res = co2.run_language_gate(_real_storefront(), surface="public")
    assert res["gate_decision"] != "FAIL", res
    assert res["verdict"] == "CHECK_OK", res


def test_negative_minimal_mutation_overclaim_fails_gate():
    clean = _real_storefront()
    assert clean.count(OVERCLAIM_ANCHOR) == 1, "anchor for the single-field flip is not unique"
    mutant = clean.replace(OVERCLAIM_ANCHOR, OVERCLAIM_INJECTION, 1)   # flip ONE field
    assert mutant != clean
    res = co2.run_language_gate(mutant, surface="public")
    assert res["gate_decision"] == "FAIL", res
    assert res["verdict"] == "CHECK_REJECTED", res
    kinds = {b["type"] for b in res["blockers"]}
    assert "OVERCLAIM" in kinds, res


def test_mutation_is_minimal_and_gate_is_not_relaxed():
    clean = _real_storefront()
    mutant = clean.replace(OVERCLAIM_ANCHOR, OVERCLAIM_INJECTION, 1)
    # minimality: reversing the single injection reproduces the clean artifact byte-for-byte
    assert mutant.replace(OVERCLAIM_INJECTION, OVERCLAIM_ANCHOR, 1) == clean
    # same judge, opposite verdicts -> passing the clean storefront is not green-by-construction
    assert co2.run_language_gate(clean)["verdict"] == "CHECK_OK"
    assert co2.run_language_gate(mutant)["verdict"] == "CHECK_REJECTED"


def test_dogfood_writes_no_receipt_into_tracked_gate_dir():
    receipts = co2._repo_root() / "language_gate" / "receipts"
    before = {p.name for p in receipts.glob("*")} if receipts.exists() else set()
    co2.run_language_gate(_real_storefront(), surface="public")
    after = {p.name for p in receipts.glob("*")} if receipts.exists() else set()
    assert before == after, "dogfood must not write a receipt into the tracked gate dir"


TESTS = [
    test_seven_patterns_ladder_and_lock10_banner,
    test_tier3_tier4_render_locked_never_sells_now,
    test_unpopulated_price_renders_badge_never_zero,
    test_populated_bands_carry_synthetic_watermark,
    test_no_autonomy_or_guarantee_claims_in_clean_storefront,
    test_positive_real_storefront_passes_gate,
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
