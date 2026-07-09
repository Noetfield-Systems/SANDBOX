#!/usr/bin/env python3
"""
TH-6 — Prompt-Forge deterministic snapshot harness  (catalog build B0 · TH-6)

Freezes the deterministic (--no-llm) output of the Prompt-Forge pipeline for the
built-in --demo input, so a change that alters the deterministic transform gets
caught. The one volatile field (created_at) is stripped before snapshotting;
used_llm is asserted false (proves the deterministic path, no network/LLM).

Runs with HOME on a temp dir; --receipt is never passed, so nothing is written
to ~/.sina. Read-only.

    python3 test_prompt_forge_snapshot.py                 # self-runner
    python3 test_prompt_forge_snapshot.py --update-golden # first freeze only
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def _repo_root() -> Path:
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                             cwd=Path(__file__).resolve().parent, text=True, capture_output=True, check=True)
        return Path(out.stdout.strip())
    except Exception:
        return Path(__file__).resolve().parents[3]


REPO = _repo_root()
FORGE = REPO / "SG-Canonical-Library" / "noetfield-library" / "P5-LINE-ENGINE" / "reference-code" / "prompt_forge_pipeline_v1.py"
GOLDEN = Path(__file__).resolve().parent / "golden" / "prompt_forge_demo_golden_v1.json"
VOLATILE = {"created_at"}


def run_forge() -> dict:
    with tempfile.TemporaryDirectory() as home:
        proc = subprocess.run(
            [sys.executable, str(FORGE), "--demo", "--no-llm", "--json"],
            text=True, capture_output=True, env={"HOME": home, "PATH": __import__("os").environ.get("PATH", "")},
        )
        assert proc.returncode == 0, f"forge failed: {proc.stderr}\n{proc.stdout}"
        return json.loads(proc.stdout)


def normalize(d: dict) -> dict:
    return {k: v for k, v in d.items() if k not in VOLATILE}


def test_output_matches_frozen_golden():
    assert GOLDEN.is_file(), f"golden missing — run --update-golden to freeze: {GOLDEN}"
    frozen = json.loads(GOLDEN.read_text())
    live = normalize(run_forge())
    assert live == frozen, "prompt_forge deterministic output DRIFTED from golden (INVESTIGATE, do not re-baseline)"


def test_hand_asserted_invariants():
    d = run_forge()
    assert d.get("used_llm") is False, "must be the deterministic path"
    assert d.get("pipeline") == "prompt_forge"
    codes = {f.get("code") for f in d.get("findings", [])}
    assert "rebuild_risk" in codes, f"demo should surface rebuild_risk finding: {codes}"
    assert d.get("facts", {}).get("already_done"), "demo facts.already_done should be non-empty"


def test_determinism_two_runs_agree():
    assert normalize(run_forge()) == normalize(run_forge()), "two --no-llm runs must be identical"


TESTS = [test_output_matches_frozen_golden, test_hand_asserted_invariants, test_determinism_two_runs_agree]


def _main(argv) -> int:
    if "--update-golden" in argv:
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(json.dumps(normalize(run_forge()), indent=2) + "\n", encoding="utf-8")
        print(f"FROZEN golden -> {GOLDEN}")
        return 0
    failed = 0
    for t in TESTS:
        try: t(); print(f"PASS  {t.__name__}")
        except AssertionError as e: failed += 1; print(f"FAIL  {t.__name__}: {e}")
    print(f"\n{len(TESTS)-failed}/{len(TESTS)} green")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
