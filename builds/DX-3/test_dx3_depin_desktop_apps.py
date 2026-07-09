#!/usr/bin/env python3
"""
TH for DX-3 — proves the 3 desktop audit apps are de-pinned.

Each generate.py used to hardcode REPO=/Users/.../sina-governance-SSOT, so it only
worked on the founder's machine and read the WRONG repo from a worktree. After DX-3
each resolves the repo root automatically.

Proves:
  * each app's module-level REPO resolves to THIS worktree (git toplevel), not the pin.
  * REPO is a real repo root (has data/ + scripts/).
  * SG_REPO_ROOT env override wins (portable).
  * the legacy path is preserved as a last-resort fallback (anti-downgrade: capability kept).
  * the .app bundles are NOT deleted.
  * red-run canary: a still-pinned REPO fails the 'reads this worktree' assertion.

Importing generate.py evaluates REPO at module top level but does NOT run main()
(guarded by __main__), so no wrapped validator/subprocess side effects fire.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKTREE = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=HERE,
                               text=True, capture_output=True, check=True).stdout.strip())
LEGACY_PIN = Path("/Users/sinakazemnezhad/Desktop/Noetfield-Systems/sina-governance-SSOT")

APPS = [
    "Registry-Motor-Validator.app",
    "Receipt-Ledger-Auditor.app",
    "Staleness-Gate-Auditor.app",
]


def _gen_path(app: str) -> Path:
    return WORKTREE / "desktop-app" / app / "Contents" / "Resources" / "generate.py"


def _load(app: str):
    spec = importlib.util.spec_from_file_location(f"gen_{app.replace('-', '_').replace('.', '_')}", _gen_path(app))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_all_three_resolve_to_this_worktree():
    for app in APPS:
        m = _load(app)
        assert m.REPO == WORKTREE, f"{app}: REPO={m.REPO} expected worktree {WORKTREE}"
        assert m.REPO != LEGACY_PIN, f"{app}: still pinned to the hardcoded path"


def test_repo_is_a_real_root():
    for app in APPS:
        m = _load(app)
        assert (m.REPO / "data").is_dir() and (m.REPO / "scripts").is_dir(), f"{app}: REPO not a repo root"


def test_env_override_wins():
    m = _load(APPS[0])
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp); (root / "data").mkdir(); (root / "scripts").mkdir()
        os.environ["SG_REPO_ROOT"] = str(root)
        try:
            assert m._resolve_repo() == root, "SG_REPO_ROOT override should win"
        finally:
            os.environ.pop("SG_REPO_ROOT", None)


def test_legacy_fallback_preserved():
    # anti-downgrade: the old path must still exist as a last-resort fallback (capability kept).
    for app in APPS:
        src = _gen_path(app).read_text(encoding="utf-8")
        assert str(LEGACY_PIN) in src, f"{app}: legacy fallback removed (anti-downgrade violation)"


def test_app_bundles_not_deleted():
    for app in APPS:
        assert _gen_path(app).is_file(), f"{app}: bundle/generate.py missing"


TESTS = [
    test_all_three_resolve_to_this_worktree,
    test_repo_is_a_real_root,
    test_env_override_wins,
    test_legacy_fallback_preserved,
    test_app_bundles_not_deleted,
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
