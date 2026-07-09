#!/usr/bin/env python3
"""
MO-5 — Batch Outbox Linter  (catalog build B3 · MO-5)

Static, READ-ONLY batch runner over the P0-PGR dispatch outbox. It imports the
ground per-packet linter (scripts/p0pgr_packet_lint_v1.py) and runs it over every
packet in receipts/p0pgr/outbox/*.json, then collects the per-packet verdicts into
ONE summary.

Why this exists: the ground linter is governed by RUNTIME_CONTINUITY_LAW_v1 — a
malformed packet must never freeze the lane, so `p0pgr_packet_lint_v1.py` ALWAYS
exits 0 (its per-packet verdict is PASS or REPAIR_CANDIDATE, never an exit code).
That is correct for the live lane but useless for a pre-flight batch gate: nothing
fails CI. MO-5 is the gate. It reuses the exact same lint logic (no fork, no
relaxation) but turns the collected verdicts into a batch decision with TEETH:

  * batch verdict CHECK_OK   -> every outbox packet lints clean (PASS)  -> exit 0
  * batch verdict CHECK_REJECTED -> at least one packet is a REPAIR_CANDIDATE
                                    (a lint violation) -> exit 1

Verdict vocab is CHECK_OK / CHECK_REJECTED — never a bare governance PASS. The
per-packet `lint_verdict` field is the ground linter's own classification
(PASS/REPAIR_CANDIDATE), reported verbatim, not a governance stamp of ours.

Read-only: the outbox packets and the ground linter are only read; the summary is
printed to stdout and, if --out is given, written into this build dir only.

    python3 mo5_outbox_lint.py [--outbox DIR] [--out SUMMARY.json]

Honest reporting: run over the REAL outbox, MO-5 exits according to the real
verdicts. It does not pretend the outbox is clean and it does not manufacture a
violation — it reports whatever the ground linter finds, packet by packet.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=Path(__file__).resolve().parent, text=True,
            capture_output=True, check=True,
        )
        return Path(out.stdout.strip())
    except Exception:
        return Path(__file__).resolve().parents[3]


REPO = _repo_root()
GROUND_LINTER = REPO / "scripts" / "p0pgr_packet_lint_v1.py"
DEFAULT_OUTBOX = REPO / "receipts" / "p0pgr" / "outbox"


def _load_ground_linter():
    """Import the REAL per-packet linter as a module — no fork, no re-implementation.
    The batch verdict must be derived from the exact same lint_packet() the lane uses,
    otherwise a green batch would prove nothing about the live linter."""
    spec = importlib.util.spec_from_file_location("p0pgr_packet_lint_v1", GROUND_LINTER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def lint_outbox(outbox_dir: Path, ground=None) -> dict:
    ground = ground or _load_ground_linter()
    packets = sorted(Path(outbox_dir).glob("*.json"))

    results: list[dict] = []
    violations: list[dict] = []
    for path in packets:
        packet = json.loads(path.read_text(encoding="utf-8"))
        res = ground.lint_packet(packet)
        row = {
            "packet_file": path.name,
            "packet_id": res.get("packet_id", "UNKNOWN"),
            "lint_verdict": res.get("verdict"),          # ground linter's own vocab
            "degraded_mode": res.get("degraded_mode", False),
            "reasons": res.get("reasons", []),
        }
        results.append(row)
        if res.get("verdict") != "PASS":
            violations.append({
                "packet_file": path.name,
                "packet_id": row["packet_id"],
                "lint_verdict": row["lint_verdict"],
                "reasons": row["reasons"],
            })

    verdict = "CHECK_OK" if not violations else "CHECK_REJECTED"
    return {
        "schema": "mo5-outbox-lint-summary-v1",
        "origin": "sandbox-advisory",
        "authority": "none",
        "pass_claimed": False,
        "verdict": verdict,
        "outbox_dir": str(outbox_dir),
        "ground_linter": str(GROUND_LINTER),
        "packet_count": len(packets),
        "clean_count": len(packets) - len(violations),
        "violation_count": len(violations),
        "results": results,
        "violations": violations,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--outbox", type=Path, default=DEFAULT_OUTBOX,
                    help="directory of *.json packets (default: real outbox)")
    ap.add_argument("--out", type=Path, default=None,
                    help="optional path to write the summary JSON (build dir only)")
    args = ap.parse_args(argv)

    if not GROUND_LINTER.is_file():
        print(f"MO-5 ERROR: ground linter not found at {GROUND_LINTER}", file=sys.stderr)
        return 2

    summary = lint_outbox(args.outbox)

    print(f"MO-5 OUTBOX_LINT: {summary['verdict']}  "
          f"({summary['clean_count']}/{summary['packet_count']} clean, "
          f"{summary['violation_count']} violation(s))")
    for row in summary["results"]:
        mark = "ok " if row["lint_verdict"] == "PASS" else "XX "
        print(f"  [{mark}] {row['packet_file']:<28} {row['lint_verdict']}")
        for reason in row["reasons"]:
            print(f"         - {reason}")
    if summary["violation_count"] == 0:
        print("  all outbox packets lint clean")

    if args.out is not None:
        args.out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"  summary -> {args.out}")

    # TEETH: unlike the always-exit-0 ground linter, the batch gate fails on any
    # real lint violation. CHECK_OK -> 0, CHECK_REJECTED -> 1.
    return 0 if summary["verdict"] == "CHECK_OK" else 1


if __name__ == "__main__":
    sys.exit(main())
