#!/usr/bin/env python3
"""
TH for WI-2 — the library-scan runner's own proof.

  * REAL violations_example.md -> rolls up FAIL, carrying its real finding types
    (BANNED_REGISTER present) — the runner detects a real violation, doesn't stamp a verdict.
  * a MINIMAL MUTATION of that same real file (delete only the banned-register lines)
    -> no longer FAIL. Proves FAIL is caused by the on-disk violation content, not hardcoded.
  * REAL clean_example.md -> PASS (positive accepted, no relaxation of anything).
  * every emitted row matches the canonical sample details.json key shape (superset OK,
    never a subset — a missing roll-up key must fail this).
  * running the runner writes only build-dir scratch and never a tracked receipt.
  * decision vocab is the gate's own (PASS/WARN/PASS_WITH_REWRITE/FAIL) — never a bare governance PASS.
"""
from __future__ import annotations
import copy, importlib.util, json, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("wi2", HERE / "wi2_library_scan.py")
wi2 = importlib.util.module_from_spec(spec); spec.loader.exec_module(wi2)

CORPUS_DIR = wi2.GATE_DIR / "test_files"
VIOLATIONS = CORPUS_DIR / "violations_example.md"
CLEAN = CORPUS_DIR / "clean_example.md"

_core = wi2._load_core()
_dict = _core.load_dictionary()


def _row_for(path: Path) -> dict:
    return wi2.scan_file(_core, _dict, path)


def _decide_text(text: str, path: Path) -> str:
    surface = _core.infer_surface(str(path))
    findings, _ = _core.scan(text, surface, _dict, file_path=str(path))
    return _core.decide(findings)[0]


def _sample_row_keys() -> set:
    sample = json.loads(wi2.SAMPLE_DETAILS.read_text())
    keys = set(sample[0].keys())
    assert keys == set(wi2.SAMPLE_ROW_KEYS), f"sample drifted from expected key set: {keys}"
    return keys


def test_real_violations_file_rolls_up_FAIL_with_its_finding_types():
    row = _row_for(VIOLATIONS)
    assert row["decision"] == "FAIL", row
    assert "BANNED_REGISTER" in row["finding_types"], row
    assert row["findings_count"] >= 1


def test_minimal_mutation_of_real_file_flips_off_FAIL():
    # Take the REAL on-disk artifact; delete ONLY the two banned-register lines.
    text = VIOLATIONS.read_text(encoding="utf-8")
    kept = [
        ln for ln in text.splitlines()
        if "revolutionary" not in ln.lower()          # BANNED: revolutionary / game-changing
        and "we need" not in ln.lower()               # BANNED: we need
    ]
    mutated = "\n".join(kept) + "\n"
    assert _decide_text(text, VIOLATIONS) == "FAIL", "real file must start FAIL"
    assert _decide_text(mutated, VIOLATIONS) != "FAIL", (
        "removing the banned-register lines must clear FAIL — FAIL is content-driven, not hardcoded"
    )


def test_real_clean_file_is_PASS():
    assert _row_for(CLEAN)["decision"] == "PASS", _row_for(CLEAN)


def test_emitted_rows_match_sample_key_shape():
    sample_keys = _sample_row_keys()
    rows = wi2.scan_corpus([str(CORPUS_DIR / "*")])
    assert rows, "corpus scan produced no rows"
    assert wi2.matches_sample_shape(rows)
    for row in rows:
        assert sample_keys.issubset(row.keys()), f"row missing sample keys: {row}"


def test_no_schema_relaxation_dropping_a_rollup_key_fails_the_shape_check():
    rows = wi2.scan_corpus([str(CORPUS_DIR / "*")])
    crippled = copy.deepcopy(rows)
    del crippled[0]["findings_count"]  # drop a required roll-up field
    assert wi2.matches_sample_shape(crippled) is False, (
        "shape check must reject a row missing a sample roll-up key"
    )


def test_runner_writes_only_scratch_never_tracked_receipt():
    receipts_dir = wi2.GATE_DIR / "receipts"
    before = {p.name for p in receipts_dir.glob("*")}
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "details.json"
        rc = subprocess.run(
            [sys.executable, str(HERE / "wi2_library_scan.py"), "--out", str(out)],
            text=True, capture_output=True,
        )
        assert rc.returncode == 0, rc.stderr
        assert out.is_file(), "details not written to scratch --out"
        rows = json.loads(out.read_text())
        assert any(r["decision"] == "FAIL" for r in rows), "expected >=1 FAIL in corpus"
    after = {p.name for p in receipts_dir.glob("*")}
    assert before == after, "runner mutated the tracked receipts/ dir!"


def test_decision_vocab_is_gate_native_never_bare_pass():
    rows = wi2.scan_corpus([str(CORPUS_DIR / "*")])
    allowed = {"PASS", "WARN", "PASS_WITH_REWRITE", "FAIL"}
    for r in rows:
        assert r["decision"] in allowed, r


TESTS = [
    test_real_violations_file_rolls_up_FAIL_with_its_finding_types,
    test_minimal_mutation_of_real_file_flips_off_FAIL,
    test_real_clean_file_is_PASS,
    test_emitted_rows_match_sample_key_shape,
    test_no_schema_relaxation_dropping_a_rollup_key_fails_the_shape_check,
    test_runner_writes_only_scratch_never_tracked_receipt,
    test_decision_vocab_is_gate_native_never_bare_pass,
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
    sys.exit(_main())
