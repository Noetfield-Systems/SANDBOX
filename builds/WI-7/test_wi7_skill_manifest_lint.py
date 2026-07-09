#!/usr/bin/env python3
"""TH for WI-7 — extraction works; a seeded missing ref is caught; red-run canary."""
from __future__ import annotations
import importlib.util, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("wi7", HERE / "wi7_skill_manifest_lint.py")
wi7 = importlib.util.module_from_spec(spec); spec.loader.exec_module(wi7)


def test_extraction_finds_real_paths():
    # the staleness skill declares real script/data deps in its frontmatter
    md = wi7.REPO / "skills" / "staleness-gate-auditor" / "SKILL.md"
    refs = wi7.referenced_paths(md)
    assert any(r.startswith("scripts/") for r in refs), refs
    assert any(r.startswith("data/") for r in refs), refs


def test_seeded_missing_ref_is_caught():
    # write a temp SKILL.md that references a non-existent file; extraction+existence must flag it
    with tempfile.TemporaryDirectory() as tmp:
        md = Path(tmp) / "SKILL.md"
        md.write_text("---\nname: x\ncompatibility: Requires scripts/does_not_exist_zzz.py to exist.\n---\nbody\n")
        refs = wi7.referenced_paths(md)
        assert "scripts/does_not_exist_zzz.py" in refs
        assert not (wi7.REPO / "scripts/does_not_exist_zzz.py").exists()


def test_frontmatter_isolation():
    # only the frontmatter block is scanned, not the body
    with tempfile.TemporaryDirectory() as tmp:
        md = Path(tmp) / "SKILL.md"
        md.write_text("---\nname: x\n---\nsee scripts/body_only_ref.py in the body\n")
        assert wi7.referenced_paths(md) == []


TESTS = [test_extraction_finds_real_paths, test_seeded_missing_ref_is_caught, test_frontmatter_isolation]


def _main() -> int:
    failed = 0
    for t in TESTS:
        try: t(); print(f"PASS  {t.__name__}")
        except AssertionError as e: failed += 1; print(f"FAIL  {t.__name__}: {e}")
    print(f"\n{len(TESTS)-failed}/{len(TESTS)} green")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_main())
