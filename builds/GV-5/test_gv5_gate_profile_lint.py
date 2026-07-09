#!/usr/bin/env python3
"""TH for GV-5 — real registry clean; seeded bad rows caught; red-run canary."""
from __future__ import annotations
import copy, importlib.util, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("gv5", HERE / "gv5_gate_profile_lint.py")
gv5 = importlib.util.module_from_spec(spec); spec.loader.exec_module(gv5)
REG = json.loads(gv5.DEFAULT_REGISTRY.read_text())


def test_real_registry_clean():
    assert gv5.lint_registry(REG) == [], gv5.lint_registry(REG)


def test_missing_deploy_root_caught():
    r = copy.deepcopy(REG); r["sandboxes"][0].pop("deploy_root", None)
    assert any("deploy_root missing" in x for x in gv5.lint_registry(r))


def test_unknown_gate_profile_key_caught():
    r = copy.deepcopy(REG); r["sandboxes"][0].setdefault("gate_profile", {})["typoo_key"] = True
    assert any("unknown key 'typoo_key'" in x for x in gv5.lint_registry(r))


def test_wrong_type_caught():
    r = copy.deepcopy(REG); r["sandboxes"][0].setdefault("gate_profile", {})["deploy_command"] = 123
    assert any("deploy_command should be a string" in x for x in gv5.lint_registry(r))


TESTS = [test_real_registry_clean, test_missing_deploy_root_caught,
         test_unknown_gate_profile_key_caught, test_wrong_type_caught]


def _main() -> int:
    failed = 0
    for t in TESTS:
        try: t(); print(f"PASS  {t.__name__}")
        except AssertionError as e: failed += 1; print(f"FAIL  {t.__name__}: {e}")
    print(f"\n{len(TESTS)-failed}/{len(TESTS)} green")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_main())
