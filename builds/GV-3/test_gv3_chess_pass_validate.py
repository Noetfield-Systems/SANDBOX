#!/usr/bin/env python3
"""
TH for GV-3 — proves the CHESS pass validator has teeth.

  * canonical sample pass -> valid (no errors).
  * our own locked build-plan chess_pass -> valid (real generated data).
  * action=BLOCK -> rejected (both enum + forbidden-label checks).
  * missing required field -> rejected.
  * extra field (additionalProperties:false) -> rejected.
  * wrong type -> rejected.
  * manifest-check reports the real dangling TOOLS/ refs.
  * red-run canary.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("gv3", HERE / "gv3_chess_pass_validate.py")
gv3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gv3)

SAMPLE = json.loads(gv3.SAMPLE_PATH.read_text())


def test_sample_pass_is_valid():
    assert gv3.validate_pass(SAMPLE) == [], gv3.validate_pass(SAMPLE)


def test_our_locked_plan_chess_pass_is_valid():
    src = HERE.parents[1] / "planning" / "chess_forecast_full.json"   # catalog/planning/
    cp = json.loads(src.read_text())["synth"]["chess_pass"]
    assert gv3.validate_pass(cp) == [], gv3.validate_pass(cp)


def test_block_action_rejected():
    bad = copy.deepcopy(SAMPLE); bad["action"] = "BLOCK"
    errs = gv3.validate_pass(bad)
    assert any("forbidden label 'BLOCK'" in e for e in errs), errs
    assert any("not in allowed" in e for e in errs), errs   # enum catches it too


def test_missing_required_rejected():
    bad = copy.deepcopy(SAMPLE); del bad["action"]
    assert any("missing required field 'action'" in e for e in gv3.validate_pass(bad))


def test_extra_field_rejected():
    bad = copy.deepcopy(SAMPLE); bad["sneaky"] = 1
    assert any("unexpected field 'sneaky'" in e for e in gv3.validate_pass(bad))


def test_wrong_type_rejected():
    bad = copy.deepcopy(SAMPLE); bad["protected_assets"] = "should-be-a-list"
    assert any("expected array" in e for e in gv3.validate_pass(bad))


def test_manifest_check_surfaces_dangling_tools_refs():
    missing = gv3.manifest_dangling()
    assert "TOOLS/chess_pass_cli.py" in missing, missing
    assert "TOOLS/README.md" in missing, missing


TESTS = [
    test_sample_pass_is_valid,
    test_our_locked_plan_chess_pass_is_valid,
    test_block_action_rejected,
    test_missing_required_rejected,
    test_extra_field_rejected,
    test_wrong_type_rejected,
    test_manifest_check_surfaces_dangling_tools_refs,
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
