#!/usr/bin/env python3
"""
MO-7 — Stale-Law Sweep over ACTIVE agent read surfaces  (catalog build B3 · MO-7)

Static, READ-ONLY detector. Grounds:
  * data/stale_law_guard_patterns_v1.json  — the stale-law regexes (Vercel/vercel_deploy/
    NOOS-for-Vercel/Mac-only-24-7/legacy vercel workflow), each declaring
    applies_to_status. Only patterns whose applies_to_status includes "ACTIVE" are swept.
  * data/agent_read_surfaces_v1.json       — the read-surface registry. The swept set is
    every must_read entry with status=="ACTIVE" that resolves inside THIS repo and exists
    on disk, honoring the registry's own exclude_globs.

Invariant: no ACTIVE read surface may contain a stale-law string. A hit means an agent's
live authority surface still carries retired routing/deploy law. Exit NONZERO on any hit.

Scoping (NOT relaxation):
  * PATTERN_SOURCE (data/stale_law_guard_patterns_v1.json) is the detector's OWN rule
    table — it necessarily contains the forbidden strings as regex/replacement/message
    metadata and would self-match by construction. It is excluded as the pattern source,
    the same way a linter does not lint its own rule table. This is printed transparently.
  * A pattern that declares scan_workflow_globs is a workflow-file rule; it is applied
    ONLY to surfaces whose path matches those globs (never as a broad substring sweep).

CRITICAL positive control: a hardcoded synthetic surface known to contain a stale-law
string is swept every run and MUST be detected. If it is NOT detected the tool aborts
NONZERO — so a zero-hit real result can never be a broken-regex false-clean.

Verdict vocab: CHECK_OK / CHECK_REJECTED (never a bare governance PASS).

    python3 mo7_stale_law_sweep.py [--patterns PATH] [--surfaces PATH]
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                             cwd=Path(__file__).resolve().parent, text=True,
                             capture_output=True, check=True)
        return Path(out.stdout.strip())
    except Exception:
        return Path(__file__).resolve().parents[3]


REPO = _repo_root()
DEFAULT_PATTERNS = REPO / "data" / "stale_law_guard_patterns_v1.json"
DEFAULT_SURFACES = REPO / "data" / "agent_read_surfaces_v1.json"

# The detector's own rule table — excluded as the pattern source (self-match by construction).
PATTERN_SOURCE_REL = "data/stale_law_guard_patterns_v1.json"

# Hardcoded known-bad synthetic surface. It MUST be detected on every run, otherwise the
# regexes are broken and any zero-hit real result is untrustworthy.
POSITIVE_CONTROL_NAME = "__positive_control__"
POSITIVE_CONTROL_TEXT = (
    "Deploy target: Vercel (owner vercel_deploy). NOOS for Vercel routing.\n"
    "Runs Mac-only ... 24/7 on the founder laptop.\n"
)


def _glob_match(path: str, glob: str) -> bool:
    """fnmatch, but a leading '**/' also matches a repo-root-relative path with no prefix
    (fnmatch does not treat '**' as a recursive segment)."""
    if fnmatch.fnmatch(path, glob):
        return True
    if glob.startswith("**/") and fnmatch.fnmatch(path, glob[3:]):
        return True
    return False


def load_patterns(patterns_path: Path) -> list[dict]:
    doc = json.loads(patterns_path.read_text(encoding="utf-8"))
    out = []
    for p in doc.get("patterns", []) or []:
        if "ACTIVE" not in (p.get("applies_to_status") or []):
            continue
        out.append({
            "id": p["id"],
            "severity": p.get("severity", "WARN"),
            "regex": p["regex"],
            "rx": re.compile(p["regex"]),
            "workflow_globs": p.get("scan_workflow_globs") or [],
        })
    if not out:
        raise SystemExit("MO-7 ABORT: no ACTIVE-applicable stale-law patterns loaded")
    return out


def active_surfaces(surfaces_path: Path) -> list[tuple[str, Path]]:
    """ACTIVE must_read entries that resolve inside THIS repo and exist on disk,
    honoring exclude_globs and excluding the pattern-source file."""
    doc = json.loads(surfaces_path.read_text(encoding="utf-8"))
    exclude = doc.get("exclude_globs", []) or []
    seen: set[str] = set()
    out: list[tuple[str, Path]] = []
    for lane in (doc.get("lanes") or {}).values():
        for m in lane.get("must_read", []) or []:
            if m.get("status") != "ACTIVE":
                continue
            rel = m.get("path", "")
            if not rel or rel.startswith("~"):
                continue                                   # cross-repo / home-relative
            repo = m.get("repo")
            if repo and repo not in ("sina-governance-ssot",):
                continue                                   # different repo
            if rel == PATTERN_SOURCE_REL:
                continue                                   # detector's own rule table
            if any(_glob_match(rel, g) for g in exclude):
                continue
            if rel in seen:
                continue
            fp = (surfaces_path.parent.parent / rel)
            if not fp.is_file():
                continue                                   # missing / not present here
            seen.add(rel)
            out.append((rel, fp))
    return sorted(out)


def _pattern_applies(pat: dict, surface_name: str) -> bool:
    """Workflow-glob patterns apply only to matching workflow-file surfaces."""
    if pat["workflow_globs"]:
        return any(_glob_match(surface_name, g) for g in pat["workflow_globs"])
    return True


def sweep(surfaces: list[tuple[str, str]], patterns: list[dict]) -> list[dict]:
    """surfaces: list of (name, text). Returns list of hit dicts."""
    hits: list[dict] = []
    for name, text in surfaces:
        for pat in patterns:
            if not _pattern_applies(pat, name):
                continue
            for mt in pat["rx"].finditer(text):
                line = text.count("\n", 0, mt.start()) + 1
                hits.append({
                    "surface": name,
                    "pattern_id": pat["id"],
                    "severity": pat["severity"],
                    "line": line,
                    "match": mt.group(0),
                })
    return hits


def _positive_control_ok(patterns: list[dict]) -> bool:
    """The synthetic known-bad surface must yield >=1 hit, else regexes are broken."""
    return len(sweep([(POSITIVE_CONTROL_NAME, POSITIVE_CONTROL_TEXT)], patterns)) > 0


def run(patterns_path: Path, surfaces_path: Path) -> dict:
    patterns = load_patterns(patterns_path)
    pc_ok = _positive_control_ok(patterns)
    surfs = active_surfaces(surfaces_path)
    loaded = [(name, fp.read_text(encoding="utf-8", errors="replace")) for name, fp in surfs]
    hits = sweep(loaded, patterns)
    verdict = "CHECK_OK" if (pc_ok and not hits) else "CHECK_REJECTED"
    return {
        "origin": "sandbox-advisory", "authority": "none", "pass_claimed": False,
        "verdict": verdict,
        "positive_control_detected": pc_ok,
        "active_pattern_ids": [p["id"] for p in patterns],
        "surfaces_swept": len(surfs),
        "pattern_source_excluded": PATTERN_SOURCE_REL,
        "hit_count": len(hits),
        "hits": hits,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--patterns", type=Path, default=DEFAULT_PATTERNS)
    ap.add_argument("--surfaces", type=Path, default=DEFAULT_SURFACES)
    args = ap.parse_args(argv)

    res = run(args.patterns, args.surfaces)

    if not res["positive_control_detected"]:
        print("MO-7 STALE_LAW_SWEEP: CHECK_REJECTED (positive control NOT detected — "
              "regexes are broken; zero-hit results are untrustworthy)")
        return 1

    print(f"MO-7 STALE_LAW_SWEEP: {res['verdict']}  "
          f"({res['surfaces_swept']} ACTIVE surfaces, {len(res['active_pattern_ids'])} patterns, "
          f"positive-control OK)")
    print(f"  pattern source excluded (self-match by construction): {res['pattern_source_excluded']}")
    for h in res["hits"]:
        print(f"  [HIT] {h['surface']}:{h['line']}  [{h['pattern_id']}/{h['severity']}]  {h['match']!r}")
    if not res["hits"]:
        print("  no stale-law strings on any ACTIVE read surface")
    return 0 if res["verdict"] == "CHECK_OK" else 1


if __name__ == "__main__":
    sys.exit(main())
