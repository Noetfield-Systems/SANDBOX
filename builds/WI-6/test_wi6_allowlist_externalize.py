#!/usr/bin/env python3
"""
WI-6 — externalize the six language_gate allowlists to JSON  (catalog build B2 · WI-6).

Proves ADDITIVE-PARITY: the externalized allowlists_v1.json, loaded via
core.load_allowlist(), is BYTE-IDENTICAL (== as a set) to each hardcoded Python
constant; the constants remain the source-of-truth fallback and are never deleted.

RED-CAPABLE by MINIMAL MUTATION of the real on-disk artifact:
  * positive: the REAL allowlists_v1.json -> CHECK_OK, all six sets parity-clean.
  * negative: drop ONE element from a real set (minimal mutation) -> CHECK_REJECTED.
  * negative: add ONE bogus element to a real set -> CHECK_REJECTED.
  No strawman, no relaxation: parity is checked against the untouched constants.

Freeze-order guard: re-runs TH-3's frozen golden and asserts NO drift (5/5). The
edit is purely additive (a loader + a JSON mirror), so behavior must not change.

    python3 test_wi6_allowlist_externalize.py          # self-runner
    python3 -m pytest test_wi6_allowlist_externalize.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=HERE,
                           text=True, capture_output=True, check=True).stdout.strip())
sys.path.insert(0, str(REPO / "language_gate"))
sys.path.insert(0, str(HERE))

import language_gate_core_v1 as core  # noqa: E402
import wi6_allowlist_externalize as tool  # noqa: E402

REAL_JSON = HERE / "allowlists_v1.json"
TH3_TEST = REPO / "catalog" / "builds" / "TH-3" / "test_language_gate_regression.py"

NAMES = tool.ALLOWLIST_NAMES


def _reset_runtime_caches() -> None:
    # spec: reset the runtime caches before checking parity
    core._RUNTIME_STRUCTURAL = None
    core._RUNTIME_ENTITY = None


def _mutated_json(mutate) -> Path:
    """Copy the REAL json, apply `mutate(doc)` (minimal), write to a temp file."""
    doc = json.loads(REAL_JSON.read_text(encoding="utf-8"))
    mutate(doc)
    tmp = Path(tempfile.mkdtemp()) / "allowlists_v1.mutated.json"
    tmp.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return tmp


# ---- tests -------------------------------------------------------------------

def test_real_json_is_byte_identical_to_constants():
    _reset_runtime_caches()
    verdict, reasons, detail = tool.verify_parity(REAL_JSON)
    assert verdict == "CHECK_OK", reasons
    for name in NAMES:
        assert detail["sets"][name]["parity"] is True, (name, detail["sets"][name])


def test_loader_prefers_json_and_matches_each_constant():
    _reset_runtime_caches()
    for name in NAMES:
        loaded = core.load_allowlist(name, json_path=REAL_JSON)
        assert loaded == set(getattr(core, name)), name


def test_loader_falls_back_to_constants_when_json_absent():
    absent = HERE / "does_not_exist_allowlists.json"
    assert not absent.exists()
    for name in NAMES:
        assert core.load_allowlist(name, json_path=absent) == set(getattr(core, name)), name


def test_constants_remain_present_source_of_truth():
    # the Python constants must never be deleted — they are the fallback.
    expected = {"STRUCTURAL_ALLOWLIST": 66, "STATUS_LABEL_ALLOWLIST": 105,
                "FRAGMENT_ALLOWLIST": 65, "TECH_REFERENCE_ALLOWLIST": 53,
                "CENSUS_VERB_ALLOWLIST": 98, "ENTITY_ALLOWLIST": 19}
    for name, n in expected.items():
        s = getattr(core, name)
        assert isinstance(s, set) and len(s) == n, (name, len(s))


def test_negative_drop_one_element_is_rejected():
    # MINIMAL MUTATION of the real artifact: remove exactly one member.
    def mutate(doc):
        doc["allowlists"]["STRUCTURAL_ALLOWLIST"].pop()
    tmp = _mutated_json(mutate)
    verdict, reasons, detail = tool.verify_parity(tmp)
    assert verdict == "CHECK_REJECTED", "dropping one member must NOT parity-pass"
    assert detail["sets"]["STRUCTURAL_ALLOWLIST"]["parity"] is False
    assert detail["sets"]["STRUCTURAL_ALLOWLIST"]["missing_from_json"], detail


def test_negative_add_one_bogus_element_is_rejected():
    # MINIMAL MUTATION: add exactly one term not in the constant.
    def mutate(doc):
        doc["allowlists"]["ENTITY_ALLOWLIST"].append("wi6-bogus-not-in-constant")
    tmp = _mutated_json(mutate)
    verdict, reasons, detail = tool.verify_parity(tmp)
    assert verdict == "CHECK_REJECTED", "an extra JSON term must NOT parity-pass"
    assert "wi6-bogus-not-in-constant" in detail["sets"]["ENTITY_ALLOWLIST"]["extra_in_json"]


def test_negative_missing_key_is_rejected():
    def mutate(doc):
        del doc["allowlists"]["CENSUS_VERB_ALLOWLIST"]
    tmp = _mutated_json(mutate)
    verdict, reasons, _ = tool.verify_parity(tmp)
    assert verdict == "CHECK_REJECTED"
    assert any("CENSUS_VERB_ALLOWLIST" in r for r in reasons), reasons


def test_freeze_order_th3_golden_does_not_drift():
    # after the additive edit, TH-3's frozen golden must still be 5/5 (no drift).
    r = subprocess.run([sys.executable, str(TH3_TEST)], text=True, capture_output=True)
    assert "5/5 green" in r.stdout, f"TH-3 golden DRIFTED (INVESTIGATE, never re-baseline):\n{r.stdout}\n{r.stderr}"
    assert r.returncode == 0, r.stdout


TESTS = [
    test_real_json_is_byte_identical_to_constants,
    test_loader_prefers_json_and_matches_each_constant,
    test_loader_falls_back_to_constants_when_json_absent,
    test_constants_remain_present_source_of_truth,
    test_negative_drop_one_element_is_rejected,
    test_negative_add_one_bogus_element_is_rejected,
    test_negative_missing_key_is_rejected,
    test_freeze_order_th3_golden_does_not_drift,
]


def _main() -> int:
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
    sys.exit(_main())
