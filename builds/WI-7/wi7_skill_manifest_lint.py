#!/usr/bin/env python3
"""
WI-7 — Skill-manifest self-linter  (catalog build B0 · WI-7)

Each skills/*/SKILL.md frontmatter names the repo files the skill wraps/requires
(e.g. "Wraps scripts/agent_read_staleness_engine_v1.py", "Requires
data/agent_read_surfaces_v1.json"). This checks every such referenced path
actually exists — catching a skill that points at a moved or deleted file.

Extracts repo-relative path tokens from each SKILL.md frontmatter (the block
between the first two --- markers) and verifies existence under the repo root.

Read-only. Exits 1 if any referenced path is missing (RED), 0 when all resolve.

    python3 wi7_skill_manifest_lint.py
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                             cwd=Path(__file__).resolve().parent, text=True, capture_output=True, check=True)
        return Path(out.stdout.strip())
    except Exception:
        return Path(__file__).resolve().parents[3]


REPO = _repo_root()
TOP_DIRS = ("scripts", "data", "gates", "verifier", "desktop-app", "language_gate",
            "skills", "SG-Canonical-Library", "receipts", "ssot", "workers")
# a repo-relative path starting with a known top dir, ending at whitespace/comma/paren/quote
PATH_RE = re.compile(r"\b(?:" + "|".join(TOP_DIRS) + r")/[A-Za-z0-9._/\-]+")


def frontmatter(text: str) -> str:
    parts = text.split("---")
    return parts[1] if text.lstrip().startswith("---") and len(parts) >= 3 else ""


def referenced_paths(skill_md: Path) -> list[str]:
    fm = frontmatter(skill_md.read_text(encoding="utf-8"))
    seen, out = set(), []
    for m in PATH_RE.finditer(fm):
        p = m.group(0).rstrip(".,);:")
        if p not in seen:
            seen.add(p); out.append(p)
    return out


def find_missing() -> list[dict]:
    missing: list[dict] = []
    for skill_md in sorted(REPO.glob("skills/*/SKILL.md")):
        for ref in referenced_paths(skill_md):
            if not (REPO / ref).exists():
                missing.append({"skill": skill_md.parent.name, "ref": ref})
    return missing


def main(argv=None) -> int:
    missing = find_missing()
    if missing:
        print("WI-7 SKILL_MANIFEST: MISSING referenced files:")
        for m in missing:
            print(f"  - [{m['skill']}] {m['ref']} (referenced in SKILL.md, absent on disk)")
        return 1
    print("WI-7 SKILL_MANIFEST: CHECK_OK (all referenced files exist)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
