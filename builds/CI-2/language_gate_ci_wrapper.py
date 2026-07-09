#!/usr/bin/env python3
"""CI-2 language-gate wrapper: run the language gate over a PR changed-file list, REPORT-ONLY.

Ground:
  - .githooks/pre-commit           (how the gate is invoked over changed files)
  - language_gate/language_gate_pipeline_v1.py  (the gate pipeline)

Report-only contract (mirrors the CI job that calls it):
  * runs the pipeline with write=False (no --write), skip_agent=True, strict_undefined=False
    (i.e. the CLI equivalent of `--json --soft-undefined --skip-agent`).
  * --soft-undefined => UNDEFINED_TERM is WARN, never a hard fail.
  * writes NOTHING into the tracked repo: the pipeline's receipts are redirected to an
    ephemeral --receipts-dir (default: a fresh tempdir) so no receipt/sidecar lands in
    language_gate/receipts or next to the scanned files.
  * NON-BLOCKING: the process exits 0 regardless of findings. Findings are returned in the
    JSON payload and rendered to the (optional) job-summary markdown. Nothing here fails a build
    or merges anything.

Same changed-file filter as the pre-commit hook: only *.md, *.mdc, *.txt, *.json;
skip language_gate/receipts/* and node_modules/*.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
GATE_DIR = REPO_ROOT / "language_gate"
sys.path.insert(0, str(GATE_DIR))

GATE_EXTS = (".md", ".mdc", ".txt", ".json")


def _eligible(rel: str) -> bool:
    if not rel.endswith(GATE_EXTS):
        return False
    if rel.startswith("language_gate/receipts/") or "/language_gate/receipts/" in rel:
        return False
    if rel.startswith("node_modules/") or "/node_modules/" in rel:
        return False
    return True


def run_over_files(
    files: list[str],
    *,
    surface: str = "auto",
    soft_undefined: bool = True,
    receipts_dir: Path | None = None,
    repo_root: Path = REPO_ROOT,
) -> dict:
    """Run the gate pipeline report-only over the given (repo-relative or absolute) files."""
    # Import here so an override of RECEIPTS_DIR sticks for the pipeline's write_receipt.
    import language_gate_core_v1 as core  # noqa: E402
    from language_gate_pipeline_v1 import run_pipeline  # noqa: E402

    if receipts_dir is None:
        receipts_dir = Path(tempfile.mkdtemp(prefix="ci2_gate_receipts_"))
    receipts_dir.mkdir(parents=True, exist_ok=True)
    # Redirect ALL pipeline receipt writes to an ephemeral dir -> zero repo pollution.
    core.RECEIPTS_DIR = receipts_dir

    results: list[dict] = []
    considered = 0
    for raw in files:
        rel = raw.strip()
        if not rel:
            continue
        # normalise to a repo-relative string for the eligibility filter
        rel_for_filter = rel
        p = Path(rel)
        if p.is_absolute():
            try:
                rel_for_filter = str(p.relative_to(repo_root))
            except ValueError:
                rel_for_filter = p.name
        if not _eligible(rel_for_filter):
            continue
        considered += 1
        abspath = p if p.is_absolute() else (repo_root / rel)
        if not abspath.is_file():
            results.append({"file": rel, "status": "MISSING", "decision": None, "findings": []})
            continue
        res = run_pipeline(
            abspath,
            surface=surface,
            write=False,          # REPORT-ONLY: never mutate the scanned file
            skip_agent=True,      # no agent rewrite / no sidecar write
            strict_undefined=not soft_undefined,
        )
        blockers = res.get("blockers", [])
        findings = res.get("findings", [])
        decision = res["decision"]
        flagged = decision == "FAIL" or bool(blockers) or bool(findings)
        results.append(
            {
                "file": rel,
                "status": "SCANNED",
                "decision": decision,
                "surface": res.get("surface"),
                "flagged": flagged,
                "blocking_count": len(blockers),
                "findings_count": len(findings),
                "findings": findings,
            }
        )

    any_fail = any(r.get("decision") == "FAIL" for r in results)
    any_flag = any(r.get("flagged") for r in results)
    return {
        "mode": "report-only",
        "soft_undefined": soft_undefined,
        "blocking": False,
        "files_considered": considered,
        "files_scanned": sum(1 for r in results if r["status"] == "SCANNED"),
        "any_fail": any_fail,
        "any_flagged": any_flag,
        "results": results,
    }


def render_summary(report: dict) -> str:
    lines = ["## language-gate-ci (report-only, non-blocking)", ""]
    lines.append(f"- files scanned: **{report['files_scanned']}**")
    lines.append(f"- soft-undefined: `{report['soft_undefined']}` (UNDEFINED_TERM => WARN)")
    lines.append(f"- any FAIL: **{report['any_fail']}**  |  any flagged: **{report['any_flagged']}**")
    lines.append("")
    if not report["results"]:
        lines.append("_No eligible changed files (*.md, *.mdc, *.txt, *.json)._")
        return "\n".join(lines) + "\n"
    lines.append("| file | decision | blocking | findings |")
    lines.append("| --- | --- | --- | --- |")
    for r in report["results"]:
        if r["status"] != "SCANNED":
            lines.append(f"| `{r['file']}` | {r['status']} | - | - |")
            continue
        lines.append(
            f"| `{r['file']}` | {r['decision']} | {r['blocking_count']} | {r['findings_count']} |"
        )
    lines.append("")
    lines.append("_Advisory only: this job never blocks a merge and writes nothing to the repo._")
    return "\n".join(lines) + "\n"


def _load_files(args) -> list[str]:
    files: list[str] = list(args.files)
    if args.files_from:
        text = Path(args.files_from).read_text(encoding="utf-8")
        files.extend(line for line in text.splitlines())
    return files


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("files", nargs="*", help="changed files (repo-relative or absolute)")
    ap.add_argument("--files-from", help="path to a newline-delimited changed-file list")
    ap.add_argument("--surface", default="auto")
    ap.add_argument(
        "--soft-undefined",
        action="store_true",
        default=True,
        help="treat UNDEFINED_TERM as WARN (default on for CI report-only)",
    )
    ap.add_argument("--strict-undefined", dest="soft_undefined", action="store_false")
    ap.add_argument("--receipts-dir", help="ephemeral dir for pipeline receipts (default: tempdir)")
    ap.add_argument("--json", action="store_true", help="print the JSON report to stdout")
    ap.add_argument("--summary-out", help="append a markdown summary to this path (e.g. GITHUB_STEP_SUMMARY)")
    args = ap.parse_args(argv)

    files = _load_files(args)
    receipts_dir = Path(args.receipts_dir) if args.receipts_dir else None
    report = run_over_files(
        files,
        surface=args.surface,
        soft_undefined=args.soft_undefined,
        receipts_dir=receipts_dir,
    )

    if args.summary_out:
        with open(args.summary_out, "a", encoding="utf-8") as fh:
            fh.write(render_summary(report))

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(render_summary(report))

    # NON-BLOCKING: always exit 0. Findings are reported, never enforced.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
