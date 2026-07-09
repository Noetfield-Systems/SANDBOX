#!/usr/bin/env python3
"""
WI-2 — In-gate read-only library scan runner  (catalog build B2 · WI-2)

The language gate ships scan()/decide() in language_gate_core_v1.py and a canonical
per-file details roll-up at
    language_gate/receipts/SG-Canonical-Library.library_scan.056cec9f66a064c7.details.json
but nothing globs a corpus and reproduces that details.json. This runner does exactly
that: it globs a set of files, runs scan()+decide() over each, and emits an array in the
SAME per-file schema the sample uses (file / surface / decision / findings_count /
regex_would_change / agent_would_change / agent_actions).

Read-only: it never writes a tracked receipt. Output goes to this build dir (scratch).
It reproduces the sample's roll-up fields; it does NOT relax any gate decision — a file
with a real violation (BANNED_REGISTER / OVERCLAIM / …) rolls up FAIL, a clean file PASS.

The core only exposes scan()+decide() (regex + decision); there is no agent-rewrite
stage on this surface, so agent_would_change is False and agent_actions is 0 for every
row. That is reported honestly, never faked to match the sample's agent values.

    python3 wi2_library_scan.py [--corpus GLOB ...] [--out PATH]
"""
from __future__ import annotations

import argparse
import glob as globmod
import importlib.util
import json
import os
import sys
from pathlib import Path


def _repo_root() -> Path:
    # catalog/builds/WI-2/wi2_library_scan.py  ->  repo root is parents[3]
    return Path(__file__).resolve().parents[3]


REPO = _repo_root()
GATE_DIR = REPO / "language_gate"
DEFAULT_CORPUS = str(GATE_DIR / "test_files" / "*")
SAMPLE_DETAILS = (
    GATE_DIR / "receipts" / "SG-Canonical-Library.library_scan.056cec9f66a064c7.details.json"
)

# The exact per-file key shape the canonical sample details.json uses.
SAMPLE_ROW_KEYS = frozenset(
    {
        "file",
        "surface",
        "decision",
        "findings_count",
        "regex_would_change",
        "agent_would_change",
        "agent_actions",
    }
)


def _load_core():
    spec = importlib.util.spec_from_file_location(
        "language_gate_core_v1", GATE_DIR / "language_gate_core_v1.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # dataclasses in the core need the module registered
    spec.loader.exec_module(mod)
    return mod


def _rel(path: Path) -> str:
    try:
        return os.path.relpath(path, REPO)
    except ValueError:
        return str(path)


def scan_file(core, dictionary, path: Path) -> dict:
    """Scan one file with scan()+decide(); return a sample-shaped roll-up row.

    Extends the sample schema with `finding_types` (a sorted, de-duplicated list of
    the finding types that drove the decision) so a violating file shows *why* it
    rolled up FAIL. This is additive — all sample keys are still present.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    surface = core.infer_surface(str(path))
    findings, rewritten = core.scan(text, surface, dictionary, file_path=str(path))
    decision, _blockers = core.decide(findings)
    return {
        # --- sample-schema roll-up fields (must match SAMPLE_ROW_KEYS) ---
        "file": _rel(path),
        "surface": surface,
        "decision": decision,
        "findings_count": len(findings),
        "regex_would_change": rewritten != text,
        # core exposes no agent stage on this surface — reported honestly, not faked.
        "agent_would_change": False,
        "agent_actions": 0,
        # --- additive: per-file finding taxonomy (why the row decided as it did) ---
        "finding_types": sorted({f.type for f in findings}),
    }


def scan_corpus(patterns: list[str]) -> list[dict]:
    core = _load_core()
    dictionary = core.load_dictionary()
    paths: list[Path] = []
    seen: set[str] = set()
    for pat in patterns:
        for hit in sorted(globmod.glob(pat)):
            p = Path(hit)
            if p.is_file() and str(p) not in seen:
                seen.add(str(p))
                paths.append(p)
    return [scan_file(core, dictionary, p) for p in paths]


def matches_sample_shape(rows: list[dict]) -> bool:
    """True iff every emitted row carries the sample's full key set (superset OK)."""
    return all(SAMPLE_ROW_KEYS.issubset(row.keys()) for row in rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", nargs="+", default=[DEFAULT_CORPUS],
                    help="glob(s) of files to scan (default: language_gate/test_files/*)")
    ap.add_argument("--out", type=Path,
                    default=Path(__file__).resolve().parent / "library_scan.details.json",
                    help="where to write the details roll-up (build-dir scratch, never a tracked receipt)")
    args = ap.parse_args(argv)

    rows = scan_corpus(args.corpus)
    # Write to build-dir scratch only. Never RECEIPTS_DIR.
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")

    fails = [r for r in rows if r["decision"] == "FAIL"]
    print(f"WI-2 LIBRARY_SCAN: {len(rows)} files scanned  ({len(fails)} FAIL)")
    for r in rows:
        types = ",".join(r["finding_types"]) or "-"
        print(f"  {r['decision']:<18} {r['file']}  [{types}]")
    print(f"  shape matches sample: {matches_sample_shape(rows)}")
    print(f"  details written -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
