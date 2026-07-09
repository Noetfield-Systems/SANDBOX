#!/usr/bin/env python3
"""
CI-5 - forbidden-marker PR grep gate (REPORT-ONLY).

Scans a given list of files for the forbidden active-config marker named in
.github/copilot-instructions.md and prints a machine-readable JSON report
(default) or a Markdown summary. Exits NONZERO when the marker is found in any
scanned file, exit 0 when clean.

Report-only by construction:
  * reads files only; performs NO writes, NO network, NO git mutations.
  * never sets a receipt, never mutates Supabase, never blocks a merge itself.
    The workflow that calls it is responsible for staying non-blocking
    (continue-on-error) so a hit is surfaced, not enforced.

The forbidden marker is assembled from fragments below so that THIS source file
does not itself contain the literal marker string (which would make the gate
flag its own scanner). Override with --marker or FORBIDDEN_MARKER if the ground
truth in copilot-instructions.md ever changes.

Usage:
  scan_forbidden_marker_v1.py [FILE ...]
  scan_forbidden_marker_v1.py --files-from LIST.txt
  scan_forbidden_marker_v1.py --files-from LIST.txt --md   # Markdown summary
Exit: 0 = clean, 1 = marker found, 2 = usage error.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Ground truth: .github/copilot-instructions.md names the forbidden
# active-config marker. Assembled from fragments so this scanner source does
# not embed the literal string it hunts for.
_MARKER_FRAGMENTS = ("kazemnezhadsina144", "dot")
DEFAULT_MARKER = "-".join(_MARKER_FRAGMENTS)


def resolve_marker(cli_marker: str | None) -> str:
    if cli_marker:
        return cli_marker
    return os.environ.get("FORBIDDEN_MARKER", DEFAULT_MARKER)


def scan_file(path: Path, marker: str) -> dict:
    """Return a per-file result. Never raises on unreadable/binary content."""
    entry: dict = {"file": str(path), "hits": [], "status": "clean"}
    if not path.exists():
        entry["status"] = "missing"
        return entry
    if path.is_dir():
        entry["status"] = "skipped_dir"
        return entry
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:  # pragma: no cover - defensive
        entry["status"] = "unreadable"
        entry["error"] = str(exc)
        return entry
    for lineno, line in enumerate(text.splitlines(), start=1):
        if marker in line:
            entry["hits"].append({"line": lineno, "text": line.strip()[:200]})
    if entry["hits"]:
        entry["status"] = "flagged"
    return entry


def build_report(files: list[str], marker: str) -> dict:
    results = [scan_file(Path(f), marker) for f in files]
    flagged = [r for r in results if r["status"] == "flagged"]
    hit_count = sum(len(r["hits"]) for r in flagged)
    return {
        "tool": "ci5-forbidden-marker-scan",
        "mode": "report-only",
        "marker": marker,
        "ground_truth": ".github/copilot-instructions.md",
        "scanned_count": len(results),
        "files_with_hits": [r["file"] for r in flagged],
        "hit_count": hit_count,
        "clean": hit_count == 0,
        "results": results,
    }


def render_markdown(report: dict) -> str:
    lines = ["## Forbidden active-config marker scan (report-only)", ""]
    lines.append(f"- marker: `{report['marker']}`")
    lines.append(f"- files scanned: {report['scanned_count']}")
    lines.append(f"- total hits: {report['hit_count']}")
    if report["clean"]:
        lines.append("")
        lines.append("Result: **CLEAN** - no forbidden marker in the scanned files.")
        return "\n".join(lines) + "\n"
    lines.append("")
    lines.append("Result: **FLAGGED** (advisory / non-blocking)")
    lines.append("")
    lines.append("| file | line | text |")
    lines.append("| --- | --- | --- |")
    for r in report["results"]:
        if r["status"] != "flagged":
            continue
        for h in r["hits"]:
            snippet = h["text"].replace("|", "\\|")
            lines.append(f"| `{r['file']}` | {h['line']} | `{snippet}` |")
    return "\n".join(lines) + "\n"


def collect_files(args: argparse.Namespace) -> list[str]:
    files: list[str] = list(args.files)
    if args.files_from:
        listing = Path(args.files_from).read_text(encoding="utf-8", errors="replace")
        files.extend(f.strip() for f in listing.splitlines() if f.strip())
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Report-only forbidden-marker scanner.")
    parser.add_argument("files", nargs="*", help="Files to scan.")
    parser.add_argument("--files-from", help="Read newline-delimited file list from this path.")
    parser.add_argument("--marker", help="Override the forbidden marker string.")
    fmt = parser.add_mutually_exclusive_group()
    fmt.add_argument("--json", action="store_true", help="Emit JSON report (default).")
    fmt.add_argument("--md", "--summary", action="store_true", dest="md",
                     help="Emit a Markdown summary (for a CI job summary).")
    args = parser.parse_args(argv)

    marker = resolve_marker(args.marker)
    files = collect_files(args)
    report = build_report(files, marker)

    if args.md:
        sys.stdout.write(render_markdown(report))
    else:
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")

    return 0 if report["clean"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
