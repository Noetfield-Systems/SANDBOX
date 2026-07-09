#!/usr/bin/env python3
"""
WI-3 — NOETFIELD product-dictionary overlay  (catalog build B2 · WI-3).

Clears the open UNDEFINED_TERM backlog on the P9/P10 sidecars by authoring a
NOETFIELD product overlay (all terms are status labels or product/entity terms
already DEFINED in canon — point-to-canon, none CONFLICT_PHRASE) and wiring its
allow-classes into the gate. Additive (rides WI-1's overlay mechanism).

Guards: CONFLICT_PHRASE/REGULATORY never allowlisted; anti-downgrade holds;
TH-3 frozen golden must not drift.
"""
from __future__ import annotations
import importlib.util, json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=HERE,
                           text=True, capture_output=True, check=True).stdout.strip())
sys.path.insert(0, str(REPO / "language_gate"))
import language_gate_core_v1 as core  # noqa: E402

OVERLAY = REPO / "language_gate" / "noetfield_product_dictionary_overlay_index_v1.json"
# the 15 terms the P9/P10 sidecars flagged UNDEFINED_TERM
BACKLOG = ["DETECT", "DIAGNOSE", "PROPOSE", "PROJECTED", "FAIL/PASS",
           "Brain Coherence Report", "Managed Deterministic Brain", "BaaS HOLD",
           "Sellable NOW", "Brain Architecture", "System Architect",
           "Native Pattern Thinker", "Grade-its-own-homework", "Noetfield", "TrustField Inc"]


def _fresh():
    core._RUNTIME_STRUCTURAL = None
    return core.effective_structural_allowlist()


def test_overlay_authored_and_loaded():
    assert OVERLAY.is_file(), "NOETFIELD overlay not authored"
    d = json.loads(OVERLAY.read_text())
    assert len(d["entries"]) == 15, len(d["entries"])
    assert OVERLAY in core.OVERLAY_INDEX_PATHS, "overlay not wired into OVERLAY_INDEX_PATHS"
    assert "NOETFIELD_PRODUCT_TERM" in core.OVERLAY_ALLOW_CLASSES, "allow-class not registered"


def test_all_backlog_terms_recovered_into_allowlist():
    allow = _fresh()
    missing = [t for t in BACKLOG if t.lower() not in allow]
    assert not missing, f"backlog terms not cleared: {missing}"


def test_overlay_contains_no_conflict_or_regulatory_class():
    d = json.loads(OVERLAY.read_text())
    bad = [e["term"] for e in d["entries"] if e.get("class") in core.OVERLAY_NEVER_ALLOWLIST]
    assert not bad, f"overlay must not carry block-classes: {bad}"


def test_dry_scan_backlog_terms_no_longer_flagged():
    _fresh()
    d = core.load_dictionary()
    for term in ["Brain Coherence Report", "Managed Deterministic Brain", "Native Pattern Thinker"]:
        findings, _ = core.scan(f"The {term} is delivered.", "internal", d)
        flagged = [f for f in findings if f.type == "UNDEFINED_TERM" and f.term.lower() == term.lower()]
        assert not flagged, f"{term!r} still flagged UNDEFINED_TERM after wiring"


def test_anti_downgrade_overclaim_still_fails():
    _fresh()
    findings, _ = core.scan("This service is 100% guaranteed and certified.", "public", core.load_dictionary())
    decision, _ = core.decide(findings)
    assert decision == "FAIL" and any(f.type == "OVERCLAIM" for f in findings)


def test_th3_frozen_golden_no_drift():
    r = subprocess.run([sys.executable, str(REPO / "catalog/builds/TH-3/test_language_gate_regression.py")],
                       text=True, capture_output=True)
    assert r.returncode == 0 and "5/5 green" in r.stdout, f"TH-3 golden drifted:\n{r.stdout}"


TESTS = [test_overlay_authored_and_loaded, test_all_backlog_terms_recovered_into_allowlist,
         test_overlay_contains_no_conflict_or_regulatory_class, test_dry_scan_backlog_terms_no_longer_flagged,
         test_anti_downgrade_overclaim_still_fails, test_th3_frozen_golden_no_drift]


def _main() -> int:
    failed = 0
    for t in TESTS:
        try: t(); print(f"PASS  {t.__name__}")
        except AssertionError as e: failed += 1; print(f"FAIL  {t.__name__}: {e}")
    print(f"\n{len(TESTS)-failed}/{len(TESTS)} green")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_main())
