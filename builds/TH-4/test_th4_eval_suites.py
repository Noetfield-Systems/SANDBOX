#!/usr/bin/env python3
"""TH for TH-4 — the 3 authored suites validate; malformed/missing caught; red-run canary."""
from __future__ import annotations
import importlib.util, json, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("th4", HERE / "run_evals.py")
th4 = importlib.util.module_from_spec(spec); spec.loader.exec_module(th4)


def test_real_suites_valid():
    assert th4.validate_all() == [], th4.validate_all()


def test_all_three_skills_covered():
    covered = {json.loads(s.read_text())["skill_name"] for s in th4.EVALS_DIR.glob("*.evals.json")}
    for need in th4.WRAPPED_SCRIPTS:
        assert need in covered, f"missing suite for {need}"


def test_malformed_suite_caught():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "x.evals.json"
        p.write_text(json.dumps({"skill_name": "registry-motor-validator",
                                 "evals": [{"id": 1, "prompt": "p", "expected_output": "o"}]}))  # missing expectations
        errs = th4.validate_suite(p)
        assert any("missing 'expectations'" in e for e in errs), errs


def test_missing_skill_caught():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "x.evals.json"
        p.write_text(json.dumps({"skill_name": "no-such-skill-zzz",
                                 "evals": [{"id": 1, "prompt": "p", "expected_output": "o", "expectations": ["e"]}]}))
        errs = th4.validate_suite(p)
        assert any("has no skills/" in e for e in errs), errs


TESTS = [test_real_suites_valid, test_all_three_skills_covered, test_malformed_suite_caught, test_missing_skill_caught]


def _main() -> int:
    failed = 0
    for t in TESTS:
        try: t(); print(f"PASS  {t.__name__}")
        except AssertionError as e: failed += 1; print(f"FAIL  {t.__name__}: {e}")
    print(f"\n{len(TESTS)-failed}/{len(TESTS)} green")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_main())
