#!/usr/bin/env python3
"""
TH for MO-7 — the stale-law sweep's own proof (RED-before-GREEN).

  * REAL ACTIVE surfaces -> CHECK_OK, zero hits (clean), AND positive control detected —
    so the clean result is trustworthy, not a broken-regex false-clean.
  * POSITIVE CONTROL: the hardcoded synthetic stale-law surface is ALWAYS detected
    (guards a zero-hit real result). If it silently stopped matching, the tool would
    reject — proven here directly.
  * NEGATIVE FIXTURE by MINIMAL MUTATION of a REAL on-disk surface: inject one stale-law
    token ("Vercel") into a byte-for-byte copy of the real AGENTS.md text -> the sweep
    FLAGS it, cites the surface + pattern_id, exits nonzero (RED). The unmutated original
    is clean (GREEN). This is the seeded-hit RED-before-GREEN with no strawman.
  * broken-regex simulation: if the positive control fails to match, run() returns
    CHECK_REJECTED — a zero-hit can never be reported clean when the regexes are dead.
  * running the sweep leaves the two ground-truth files byte-identical (read-only).
  * verdict vocab is CHECK_OK/CHECK_REJECTED, never PASS.
"""
from __future__ import annotations
import copy, hashlib, importlib.util, json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("mo7", HERE / "mo7_stale_law_sweep.py")
mo7 = importlib.util.module_from_spec(spec); spec.loader.exec_module(mo7)

PATTERNS = mo7.load_patterns(mo7.DEFAULT_PATTERNS)
REAL_SURFACES = mo7.active_surfaces(mo7.DEFAULT_SURFACES)
# a real on-disk ACTIVE surface used for the minimal-mutation negative fixture
AGENTS = next((name, fp) for name, fp in REAL_SURFACES if name == "AGENTS.md")


def test_real_active_surfaces_are_clean_and_control_holds():
    res = mo7.run(mo7.DEFAULT_PATTERNS, mo7.DEFAULT_SURFACES)
    assert res["positive_control_detected"] is True, res
    assert res["hit_count"] == 0, res["hits"]
    assert res["verdict"] == "CHECK_OK", res
    assert res["surfaces_swept"] >= 20, res           # real registry, not a strawman of 1


def test_positive_control_is_detected():
    hits = mo7.sweep([(mo7.POSITIVE_CONTROL_NAME, mo7.POSITIVE_CONTROL_TEXT)], PATTERNS)
    assert hits, "positive control must be detected — otherwise regexes are broken"
    ids = {h["pattern_id"] for h in hits}
    # the synthetic surface trips multiple ACTIVE patterns
    assert "deploy_vercel_word" in ids, ids


def test_minimal_mutation_of_real_surface_is_flagged():
    name, fp = AGENTS
    original = fp.read_text(encoding="utf-8")
    # GREEN: the real surface, unmutated, is clean.
    assert mo7.sweep([(name, original)], PATTERNS) == []
    # MINIMAL MUTATION: append one stale-law token to a copy of the real bytes.
    mutated = original + "\nDeploy owner: Vercel\n"
    hits = mo7.sweep([(name, mutated)], PATTERNS)
    assert hits, "injected stale-law token must be flagged"
    assert any(h["pattern_id"] == "deploy_vercel_word" and h["surface"] == name for h in hits), hits


def test_broken_regex_cannot_report_clean():
    # Simulate dead regexes: none of them match anything. run() must NOT return CHECK_OK.
    dead = [dict(p, rx=__import__("re").compile(r"(?!x)x")) for p in copy.deepcopy(PATTERNS)]
    for p in dead:
        p["rx"] = __import__("re").compile(r"\Zzznevermatch")
    assert mo7._positive_control_ok(dead) is False
    # and the sweep of a genuinely-bad surface with dead regexes finds nothing (proves
    # the positive-control gate is the only thing standing between us and a false-clean)
    assert mo7.sweep([(mo7.POSITIVE_CONTROL_NAME, mo7.POSITIVE_CONTROL_TEXT)], dead) == []


def test_workflow_glob_pattern_is_gated():
    # vercel_workflow_file (regex "vercel", scan_workflow_globs) must NOT fire on a
    # non-workflow surface even though the text contains "vercel".
    wf = [p for p in PATTERNS if p["workflow_globs"]]
    assert wf, "expected a workflow-glob pattern in the ground truth"
    hits = mo7.sweep([("data/some_data.json", "vercel vercel vercel")], [wf[0]])
    assert hits == [], "workflow-glob pattern should not sweep arbitrary surfaces"
    # but it DOES fire on a matching workflow path
    hits2 = mo7.sweep([(".github/workflows/deploy-vercel.yml", "uses vercel")], [wf[0]])
    assert hits2, "workflow-glob pattern must fire on a matching workflow surface"


def test_sweep_is_read_only():
    watched = [mo7.DEFAULT_PATTERNS, mo7.DEFAULT_SURFACES]
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in watched}
    rc = subprocess.run([sys.executable, str(HERE / "mo7_stale_law_sweep.py")],
                        text=True, capture_output=True)
    assert rc.returncode == 0, f"real surfaces are clean -> expected exit 0: {rc.stdout}{rc.stderr}"
    after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in watched}
    assert before == after, "sweep modified a ground-truth file!"


def test_never_emits_pass():
    res = mo7.run(mo7.DEFAULT_PATTERNS, mo7.DEFAULT_SURFACES)
    assert res["verdict"] in ("CHECK_OK", "CHECK_REJECTED")
    assert res["pass_claimed"] is False


TESTS = [test_real_active_surfaces_are_clean_and_control_holds,
         test_positive_control_is_detected,
         test_minimal_mutation_of_real_surface_is_flagged,
         test_broken_regex_cannot_report_clean,
         test_workflow_glob_pattern_is_gated,
         test_sweep_is_read_only,
         test_never_emits_pass]


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
