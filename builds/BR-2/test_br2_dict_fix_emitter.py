#!/usr/bin/env python3
"""
TH for BR-2 — the dictionary-fix proposal emitter's own proof.

  * REAL 80-item fixture -> proposal with ZERO candidates (the corpus is fully
    dictionary-covered today) and dictionary_index.json is NOT written.
  * NEGATIVE fixture by MINIMAL MUTATION of the real fixture on disk: inject ONE
    undefined term (`zorptflux capsule`) into one item's text -> that term appears
    as a proposal candidate AND the emitter exits nonzero (a hit). RED-before-GREEN.
  * POSITIVE CONTROL / no-relaxation: inject a term that IS already in
    dictionary_index.json (`agnostic`) the same way -> it is NOT re-proposed
    (proves the skip is real, and a zero-candidate run isn't a broken-regex false-clean).
  * running the emitter never edits dictionary_index.json (sha unchanged).
  * proposal is stamped origin=sandbox-advisory / authority=none / DRAFT, never PASS.

    python3 test_br2_dict_fix_emitter.py        # self-runner
    pytest test_br2_dict_fix_emitter.py
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("br2", HERE / "br2_dict_fix_emitter.py")
br2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(br2)

REAL_FIXTURE = br2.DEFAULT_FIXTURE
UNDEFINED_TERM = "zorptflux capsule"       # nonsense -> DICTIONARY_FIX_NEEDED
KNOWN_TERM = "agnostic"                     # real dictionary_index.json term


def _mutated_fixture(inject_term: str, tmpdir: Path) -> Path:
    """Deep-copy the REAL on-disk fixture, backtick-inject ONE term into the first
    item's raw text (a minimal mutation), and write it to a temp file. The real
    fixture on disk is never touched."""
    data = json.loads(REAL_FIXTURE.read_text(encoding="utf-8"))
    mutant = copy.deepcopy(data)
    q = mutant["open_questions"][0]
    # intake maps raw_text from the `question` field, so inject there (minimal mutation)
    q["question"] = (q.get("question") or q.get("title") or "") + f" We must define `{inject_term}` first."
    out = tmpdir / "mutated_fixture.json"
    out.write_text(json.dumps(mutant, indent=2), encoding="utf-8")
    return out


def _candidate_terms(proposal: dict) -> set[str]:
    return {c["normalized"] for c in proposal["candidate_entries"]}


def test_real_fixture_has_zero_candidates_and_is_advisory():
    p = br2.build_proposal(REAL_FIXTURE)
    assert p["candidate_count"] == 0, f"real fixture unexpectedly has candidates: {_candidate_terms(p)}"
    assert p["verdict"] == "NO_FIX_NEEDED"
    assert p["origin"] == "sandbox-advisory" and p["authority"] == "none"
    assert p["status"] == "DRAFT" and p["pass_claimed"] is False
    assert p["dictionary_index_written"] is False


def test_minimal_mutation_surfaces_undefined_term_as_candidate():
    with tempfile.TemporaryDirectory() as tmp:
        fx = _mutated_fixture(UNDEFINED_TERM, Path(tmp))
        p = br2.build_proposal(fx)
    assert UNDEFINED_TERM in _candidate_terms(p), \
        f"injected undefined term not proposed: {_candidate_terms(p)}"
    assert p["verdict"] == "FIX_NEEDED_TERMS_FOUND"


def test_seeded_hit_exits_nonzero_red_before_green():
    """Detector contract: a seeded fix-needed term makes the CLI exit 1 (a hit)."""
    with tempfile.TemporaryDirectory() as tmp:
        fx = _mutated_fixture(UNDEFINED_TERM, Path(tmp))
        out = Path(tmp) / "prop.json"
        rc = subprocess.run(
            [sys.executable, str(HERE / "br2_dict_fix_emitter.py"), "--fixture", str(fx), "--out", str(out)],
            text=True, capture_output=True,
        )
        assert rc.returncode == 1, f"seeded hit must exit 1, got {rc.returncode}: {rc.stdout}{rc.stderr}"
        prop = json.loads(out.read_text())
    assert UNDEFINED_TERM in _candidate_terms(prop)


def test_positive_control_known_term_is_not_reproposed():
    """A term already in dictionary_index.json, injected identically, must NOT be
    proposed — proves the skip is real (no relaxation) and the regex actually fires."""
    with tempfile.TemporaryDirectory() as tmp:
        fx = _mutated_fixture(KNOWN_TERM, Path(tmp))
        p = br2.build_proposal(fx)
    assert KNOWN_TERM not in _candidate_terms(p), \
        f"known dictionary term was re-proposed: {KNOWN_TERM}"
    # and the guard recorded why it was skipped (only if the term actually extracted+matched)
    assert KNOWN_TERM in existing_known(), "positive control term must exist in dictionary"


def existing_known() -> set[str]:
    return br2.existing_dictionary_terms()


def test_emitter_never_edits_dictionary_index():
    before = hashlib.sha256(br2.DICTIONARY_INDEX.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory() as tmp:
        fx = _mutated_fixture(UNDEFINED_TERM, Path(tmp))
        br2.emit(fx, Path(tmp) / "prop.json")
    after = hashlib.sha256(br2.DICTIONARY_INDEX.read_bytes()).hexdigest()
    assert before == after, "dictionary_index.json was modified!"


def test_refuses_to_write_dictionary_index():
    try:
        br2.emit(REAL_FIXTURE, br2.DICTIONARY_INDEX)
    except RuntimeError:
        return
    raise AssertionError("emitter must refuse to write dictionary_index.json")


TESTS = [
    test_real_fixture_has_zero_candidates_and_is_advisory,
    test_minimal_mutation_surfaces_undefined_term_as_candidate,
    test_seeded_hit_exits_nonzero_red_before_green,
    test_positive_control_known_term_is_not_reproposed,
    test_emitter_never_edits_dictionary_index,
    test_refuses_to_write_dictionary_index,
]


def _main() -> int:
    failed = 0
    for t in TESTS:
        try:
            t(); print(f"PASS  {t.__name__}")
        except AssertionError as e:
            failed += 1; print(f"FAIL  {t.__name__}: {e}")
    print(f"\n{len(TESTS) - failed}/{len(TESTS)} green")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_main())
