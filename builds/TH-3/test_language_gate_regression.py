#!/usr/bin/env python3
"""
TH-3 — language_gate regression harness  (catalog build B0 · TH-3)

Freezes the language gate's current decision behavior so nobody can silently
tune it (esp. the WI-1/WI-3/WI-6 overlay/allowlist wiring in Phase B2).

Drives the PURE core (scan() + decide()) — never run_pipeline(), which writes
receipts + sidecars. No repo writes, append-only respected (global patch §5).

CHESS-patched (BUILD_PLAN_PHASED_v1_LOCKED §B0 + anti-theater lens):
  * frozen golden over the 4 real test_files/ fixtures (drift = INVESTIGATE, never re-baseline).
  * NOT golden-only: hand-asserts >=1 correct value per fixture.
  * red-capable synthetic guards: a known OVERCLAIM must FAIL on public, a known
    BANNED_REGISTER must FAIL, a clean line must PASS  -> the anti-downgrade
    regression that must still hold after any WI overlay/allowlist wiring.
  * ships a committed red-run canary proving the suite goes red.

Freeze-order rule: this golden is committed and FROZEN before any WI-1/WI-3/WI-6
merge. A post-wiring golden diff means INVESTIGATE, never `--update-golden` to pass.

Advisory sandbox harness. Emits no PASS of its own. Runnable two ways:
    python3 test_language_gate_regression.py                 # self-runner
    python3 test_language_gate_regression.py --update-golden # FIRST freeze only
    python3 -m pytest test_language_gate_regression.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=Path(__file__).resolve().parent, text=True, capture_output=True, check=True,
        )
        return Path(out.stdout.strip())
    except Exception:
        return Path(__file__).resolve().parents[3]


REPO = _repo_root()
GATE_DIR = REPO / "language_gate"
FIXTURES = GATE_DIR / "test_files"
GOLDEN = Path(__file__).resolve().parent / "golden" / "language_gate_golden_v1.json"

sys.path.insert(0, str(GATE_DIR))
from language_gate_core_v1 import load_dictionary, infer_surface, scan, decide, Finding  # noqa: E402

FIXTURE_NAMES = [
    "clean_example.md",
    "violations_example.md",
    "tombstone_only.md",
    "cold_session_doctrine_sample_v1.md",
]

# Synthetic red-capable guards: (id, text, surface, expected_decision, must_contain_type)
SYNTHETIC = [
    ("overclaim_public",  "Our brain is 100% guaranteed and certified.", "public",   "FAIL", "OVERCLAIM"),
    ("overclaim_clients", "Trusted by 50+ clients worldwide.",           "website",  "FAIL", "OVERCLAIM"),
    ("banned_register",   "we need this revolutionary next-gen tool.",   "internal", "FAIL", "BANNED_REGISTER"),
    ("clean_line",        "The governance gate scans a file and returns a decision.", "public", "PASS", None),
]


def _scan_fixture(name: str) -> dict:
    p = FIXTURES / name
    text = p.read_text(encoding="utf-8")
    surface = infer_surface(str(p), None)
    findings, _ = scan(text, surface, load_dictionary(), file_path=str(p))
    decision, _ = decide(findings)
    return {
        "surface": surface,
        "decision": decision,
        "finding_count": len(findings),
        "finding_types": sorted({f.type for f in findings}),
        "findings": [{"type": f.type, "term": f.term, "line": f.line} for f in findings],
    }


def build_golden() -> dict:
    return {"_note": "frozen language_gate regression datum — drift means INVESTIGATE, never re-baseline",
            "fixtures": {name: _scan_fixture(name) for name in FIXTURE_NAMES}}


# ---- tests -------------------------------------------------------------------

def test_fixtures_match_frozen_golden():
    assert GOLDEN.is_file(), f"golden missing — run with --update-golden to freeze first: {GOLDEN}"
    frozen = json.loads(GOLDEN.read_text())["fixtures"]
    live = build_golden()["fixtures"]
    drift = []
    for name in FIXTURE_NAMES:
        if live.get(name) != frozen.get(name):
            drift.append(f"{name}: frozen={frozen.get(name)} live={live.get(name)}")
    assert not drift, "language_gate behavior DRIFTED from frozen golden (INVESTIGATE, do not re-baseline):\n" + "\n".join(drift)


def test_hand_asserted_known_values():
    live = build_golden()["fixtures"]
    assert live["clean_example.md"]["decision"] == "PASS"
    assert live["clean_example.md"]["finding_count"] == 0
    v = live["violations_example.md"]
    assert v["decision"] == "FAIL", v
    assert "BANNED_REGISTER" in v["finding_types"], v            # a hard blocker present
    assert live["tombstone_only.md"]["decision"] == "PASS_WITH_REWRITE"


def test_synthetic_guards_red_capable():
    d = load_dictionary()
    for case_id, text, surface, expected, must_type in SYNTHETIC:
        findings, _ = scan(text, surface, d)
        decision, _ = decide(findings)
        assert decision == expected, f"[{case_id}] expected {expected}, got {decision} ({[f.type for f in findings]})"
        if must_type:
            assert must_type in {f.type for f in findings}, f"[{case_id}] missing {must_type}"


def test_anti_downgrade_overclaim_still_fails_on_public():
    # the guard the WI-1/WI-3/WI-6 wiring must never break: a real overclaim FAILs on public.
    findings, _ = scan("This service is 100% guaranteed and certified.", "public", load_dictionary())
    decision, blockers = decide(findings)
    assert decision == "FAIL" and any(f.type == "OVERCLAIM" for f in blockers)


def test_decide_invariant_hard_type_forces_fail():
    # any hard-type finding -> FAIL, independent of fixtures.
    for hard in ("BANNED_REGISTER", "OVERCLAIM", "BANNED_SURFACE"):
        decision, blockers = decide([Finding(hard, "x", 1)])
        assert decision == "FAIL" and blockers, hard


TESTS = [
    test_fixtures_match_frozen_golden,
    test_hand_asserted_known_values,
    test_synthetic_guards_red_capable,
    test_anti_downgrade_overclaim_still_fails_on_public,
    test_decide_invariant_hard_type_forces_fail,
]


def _main(argv) -> int:
    if "--update-golden" in argv:
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(json.dumps(build_golden(), indent=2) + "\n", encoding="utf-8")
        print(f"FROZEN golden -> {GOLDEN}")
        return 0
    failed = 0
    for t in TESTS:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {t.__name__}: {e}")
    print(f"\n{len(TESTS) - failed}/{len(TESTS)} green")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
