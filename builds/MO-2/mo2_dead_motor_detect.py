#!/usr/bin/env python3
"""
MO-2 — Dead-Motor Detector  (catalog build B3 · MO-2)

Static, READ-ONLY detector over the workflow-census extensions registry:
  * data/workflow_census_extensions_v1.json — declares one motor per entry, each
    carrying a `receipt_glob`: the on-disk location its receipts are supposed to
    land at (a filesystem glob, resolved relative to the repo root — the same root
    that receipts/ and decision_language_machine_v1/receipts/ live under).

Invariant: a live motor leaves receipts. For each motor's `receipt_glob`, count
matching files on disk. A motor whose glob matches ZERO receipts is DEAD — it has
declared a receipt location but deposited nothing there (either the loop never ran,
or it emits no on-disk artifact at all, e.g. a prose "receipt via Telegram").

Verdict vocab: CHECK_OK / CHECK_REJECTED. Never a bare governance PASS. Exits
NONZERO when any motor is dead (this is not an always-exit-0 stub). Reads only;
never writes to the census or any receipt directory.

    python3 mo2_dead_motor_detect.py [--census PATH] [--root PATH]
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# catalog/builds/MO-2/ -> repo root (sg-sandbox) is parents[2]
REPO = HERE.parents[2]
DEFAULT_CENSUS = REPO / "data" / "workflow_census_extensions_v1.json"


def iter_motors(census: dict):
    """Yield (loop_id, receipt_glob) for every census entry that declares a
    receipt_glob. Walks every top-level list in the census (cloudflare_workers,
    railway_services, github_workflows, traffic_probes, ...) so no motor family
    is silently skipped; entries without a receipt_glob (e.g. traffic probes that
    use receipt_target) are not motors-with-receipts and are excluded."""
    for value in census.values():
        if not isinstance(value, list):
            continue
        for entry in value:
            if isinstance(entry, dict) and "receipt_glob" in entry:
                lid = entry.get("loop_id") or entry.get("name") or "(unnamed)"
                yield lid, entry["receipt_glob"]


def glob_matches(receipt_glob: str, root: Path) -> list[str]:
    """Resolve receipt_glob relative to root and return matching paths. A glob
    that is prose (spaces / not a real path) or points at a location nothing was
    written to simply yields []."""
    pattern = str(root / receipt_glob)
    return sorted(glob.glob(pattern, recursive=True))


def detect(census: dict, root: Path) -> dict:
    motors = []
    dead = []
    for lid, rg in iter_motors(census):
        matches = glob_matches(rg, root)
        rec = {"loop_id": lid, "receipt_glob": rg, "match_count": len(matches)}
        motors.append(rec)
        if len(matches) == 0:
            dead.append(rec)
    verdict = "CHECK_OK" if not dead else "CHECK_REJECTED"
    return {
        "origin": "sandbox-advisory", "authority": "none", "pass_claimed": False,
        "verdict": verdict,
        "motor_count": len(motors),
        "alive_count": len(motors) - len(dead),
        "dead_count": len(dead),
        "dead_motors": dead,
        "motors": motors,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--census", type=Path, default=DEFAULT_CENSUS)
    ap.add_argument("--root", type=Path, default=REPO)
    args = ap.parse_args(argv)

    census = json.loads(args.census.read_text(encoding="utf-8"))
    res = detect(census, args.root)

    print(f"MO-2 DEAD_MOTOR_DETECT: {res['verdict']}  "
          f"({res['dead_count']} dead / {res['motor_count']} motors with receipt_glob)")
    for d in res["dead_motors"]:
        print(f"  [dead] {d['loop_id']} — glob {d['receipt_glob']!r} matched 0 receipts")
    for m in res["motors"]:
        if m["match_count"] > 0:
            print(f"  [alive] {m['loop_id']} — glob {m['receipt_glob']!r} matched {m['match_count']}")
    return 0 if res["verdict"] == "CHECK_OK" else 1


if __name__ == "__main__":
    sys.exit(main())
