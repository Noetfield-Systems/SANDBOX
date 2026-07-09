#!/usr/bin/env python3
"""
TH for GV-4 — proves the registry cross-consistency linter has teeth.

  * real registries -> CHECK_OK, exit 0 (GREEN), zero dangling refs.
  * a seeded bad reference (one field, injected in memory) -> caught by name.
  * CLI exit codes: real -> 0; tampered temp file -> 1.
  * red-run canary: a linter that always returns [] would pass the good case
    but FAIL the seeded-bad case -> proves not always-exit-0 theater.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("gv4", HERE / "gv4_registry_xref_lint.py")
gv4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gv4)

REG = json.loads(gv4.DEFAULT_REGISTRY.read_text())
INV = json.loads(gv4.DEFAULT_INVENTORY.read_text())


def test_real_registries_are_consistent():
    dangling = gv4.find_dangling(REG, INV)
    assert dangling == [], f"real registries have dangling refs: {dangling}"


def test_seeded_bad_ref_is_caught():
    reg = copy.deepcopy(REG)
    reg["motors"][0].setdefault("conflicts_with", []).append("motor_that_does_not_exist_v9")
    dangling = gv4.find_dangling(reg, INV)
    ids = {d["id"] for d in dangling}
    assert "motor_that_does_not_exist_v9" in ids, f"seeded bad ref not caught: {dangling}"


def test_seeded_bad_allowed_motor_is_caught():
    reg = copy.deepcopy(REG)
    reg["duplication_forbidden"][0]["allowed_motors"].append("ghost_agent_v0")
    dangling = gv4.find_dangling(reg, INV)
    assert any(d["id"] == "ghost_agent_v0" for d in dangling), dangling


def _run_cli(reg_obj, inv_obj) -> int:
    with tempfile.TemporaryDirectory() as tmp:
        rp = Path(tmp) / "reg.json"; rp.write_text(json.dumps(reg_obj))
        ip = Path(tmp) / "inv.json"; ip.write_text(json.dumps(inv_obj))
        proc = subprocess.run(
            [sys.executable, str(HERE / "gv4_registry_xref_lint.py"),
             "--registry", str(rp), "--inventory", str(ip)],
            text=True, capture_output=True,
        )
        return proc.returncode


def test_cli_exit_codes():
    assert _run_cli(REG, INV) == 0, "CLI should exit 0 on consistent registries"
    bad = copy.deepcopy(REG)
    bad["motors"][0].setdefault("conflicts_with", []).append("nope_v0")
    assert _run_cli(bad, INV) == 1, "CLI should exit 1 on a dangling ref"


TESTS = [
    test_real_registries_are_consistent,
    test_seeded_bad_ref_is_caught,
    test_seeded_bad_allowed_motor_is_caught,
    test_cli_exit_codes,
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
