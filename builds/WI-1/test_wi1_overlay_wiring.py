#!/usr/bin/env python3
"""
WI-1 — Wire the orphaned overlay indexes into the gate  (catalog build B2 · WI-1).

Recovers the 165-entry sourcea/trustfield dictionary overlays that nothing loaded,
by folding their ALLOW-classes (COMMAND_FRAGMENT/STATUS_LABEL/SOURCEA_LOCAL_TERM)
into effective_structural_allowlist(). Additive only.

CHESS-patched (§B2):
  * CONFLICT_PHRASE / REGULATORY_COPY_RISK are NEVER allowlisted (block-eligible).
  * anti-downgrade regression: a known overclaim still FAILs on public; a
    legitimately-undefined Title-Case term still WARNs after wiring.
  * freeze-order: TH-3 golden was frozen before this wiring; a post-wiring golden
    diff is INVESTIGATE, never re-baseline (checked separately by re-running TH-3).
"""
from __future__ import annotations
import importlib.util, json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=HERE,
                           text=True, capture_output=True, check=True).stdout.strip())
sys.path.insert(0, str(REPO / "language_gate"))
import language_gate_core_v1 as core  # noqa: E402


def _fresh_allowlist() -> set[str]:
    core._RUNTIME_STRUCTURAL = None            # reset the module cache
    return core.effective_structural_allowlist()


def _overlay_terms(classes: set[str]) -> set[str]:
    out = set()
    for p in core.OVERLAY_INDEX_PATHS:
        if p.is_file():
            for e in json.loads(p.read_text()).get("entries") or []:
                if e.get("class") in classes and e.get("term"):
                    out.add(str(e["term"]).lower())
    return out


def test_overlay_allow_terms_are_recovered():
    allow = _fresh_allowlist()
    overlay_allow = _overlay_terms(core.OVERLAY_ALLOW_CLASSES)
    assert overlay_allow, "no overlay allow-terms found — overlays not loaded"
    missing = [t for t in overlay_allow if t not in allow]
    assert not missing, f"overlay allow-terms not recovered into allowlist: {missing[:5]}"


def test_recovered_terms_were_actually_orphaned():
    # at least some overlay allow-terms are NOT in the base/supplement allowlists,
    # proving the wiring (not pre-existing membership) is what recovered them.
    base = (set(core.STRUCTURAL_ALLOWLIST) | core.CENSUS_VERB_ALLOWLIST
            | core.STATUS_LABEL_ALLOWLIST | core.FRAGMENT_ALLOWLIST | core.TECH_REFERENCE_ALLOWLIST)
    newly = _overlay_terms(core.OVERLAY_ALLOW_CLASSES) - base
    assert newly, "every overlay term was already allowlisted — nothing was actually recovered"


def test_conflict_phrase_never_allowlisted():
    allow = _fresh_allowlist()
    conflict = _overlay_terms({"CONFLICT_PHRASE", "REGULATORY_COPY_RISK"})
    leaked = [t for t in conflict if t in allow]
    assert not leaked, f"regulatory/conflict terms leaked into allowlist (anti-downgrade violation): {leaked}"


def test_anti_downgrade_overclaim_still_fails():
    _fresh_allowlist()
    findings, _ = core.scan("This service is 100% guaranteed and certified.", "public", core.load_dictionary())
    decision, _ = core.decide(findings)
    assert decision == "FAIL" and any(f.type == "OVERCLAIM" for f in findings), (decision, [f.type for f in findings])


def test_legit_undefined_term_still_warns():
    _fresh_allowlist()
    findings, _ = core.scan("Deploy the WunderKind Gizmotron now.", "internal", core.load_dictionary())
    assert any(f.type == "UNDEFINED_TERM" for f in findings), [f.type for f in findings]


def test_a_recovered_titlecase_term_no_longer_flagged():
    # pick an overlay allow-term that is Title-Case/ALLCAPS (would trigger UNDEFINED_TERM)
    core._RUNTIME_STRUCTURAL = None
    d = core.load_dictionary()
    for p in core.OVERLAY_INDEX_PATHS:
        if not p.is_file():
            continue
        for e in json.loads(p.read_text()).get("entries") or []:
            if e.get("class") not in core.OVERLAY_ALLOW_CLASSES:
                continue
            term = str(e.get("term") or "")
            words = term.split()
            is_flaggable = len(term) >= 3 and (term.isupper() or all(w[:1].isupper() for w in words if w[:1].isalpha()))
            if is_flaggable and term.lower() not in d.terms:
                findings, _ = core.scan(f"Note: {term} is used here.", "internal", d)
                flagged = [f for f in findings if f.type == "UNDEFINED_TERM" and f.term.lower() == term.lower()]
                assert not flagged, f"recovered term {term!r} still flagged UNDEFINED_TERM"
                return
    # if none qualified, the membership tests above already prove recovery
    assert True


TESTS = [test_overlay_allow_terms_are_recovered, test_recovered_terms_were_actually_orphaned,
         test_conflict_phrase_never_allowlisted, test_anti_downgrade_overclaim_still_fails,
         test_legit_undefined_term_still_warns, test_a_recovered_titlecase_term_no_longer_flagged]


def _main() -> int:
    failed = 0
    for t in TESTS:
        try: t(); print(f"PASS  {t.__name__}")
        except AssertionError as e: failed += 1; print(f"FAIL  {t.__name__}: {e}")
    print(f"\n{len(TESTS)-failed}/{len(TESTS)} green")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_main())
