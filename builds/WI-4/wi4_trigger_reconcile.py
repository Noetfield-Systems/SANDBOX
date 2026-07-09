#!/usr/bin/env python3
"""
WI-4 — Founder-Trigger Retirement Reconciler  (catalog build B2 · WI-4)

Static, READ-ONLY reconciler over the two P0-FOUNDATION-SPINE registries:
  * data/machine-process-loops-v1.json         — machine loops, each declaring
    `retires_trigger_ids` (references to founder triggers a loop claims to retire)
  * data/founder-trigger-retirement-registry-v1.json — the retirement registry,
    whose `triggers[].trigger_id` are the ONLY definitions of trigger_ids
    (the loops file carries references, not definitions — both are read to confirm
    where trigger_ids are defined).

Invariant: every `retires_trigger_ids` value declared by a loop MUST resolve to a
defined trigger_id. A referenced id with no definition is a DANGLING reference — a
loop claiming to retire a founder trigger the registry never lists. Dangling refs
mean earned-autonomy accounting is wired to phantom triggers.

Verdict vocab: CHECK_OK / CHECK_REJECTED. Never a bare governance PASS. Exits
NONZERO on any dangling reference (this is not an always-exit-0 stub). Reads only;
never writes to the ground-truth registries.

    python3 wi4_trigger_reconcile.py [--loops PATH] [--registry PATH]
"""
from __future__ import annotations

import argparse
import json
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
DATA = REPO / "SG-Canonical-Library" / "noetfield-library" / "P0-FOUNDATION-SPINE" / "data"
DEFAULT_LOOPS = DATA / "machine-process-loops-v1.json"
DEFAULT_REGISTRY = DATA / "founder-trigger-retirement-registry-v1.json"


def defined_trigger_ids(registry: dict, loops: dict) -> set[str]:
    """Where trigger_ids are DEFINED. Read both files; today only the registry's
    triggers[].trigger_id define ids, but include any trigger_id the loops file
    might carry so the reconciler stays honest if the schema grows."""
    ids: set[str] = set()
    for t in registry.get("triggers", []) or []:
        tid = t.get("trigger_id")
        if isinstance(tid, str) and tid:
            ids.add(tid)
    for lp in loops.get("loops", []) or []:
        tid = lp.get("trigger_id")
        if isinstance(tid, str) and tid:
            ids.add(tid)
    return ids


def referenced_edges(loops: dict) -> list[tuple]:
    """Every (loop_id, retires_trigger_id) reference declared by the loops file."""
    edges: list[tuple] = []
    for lp in loops.get("loops", []) or []:
        lid = lp.get("loop_id")
        for ref in lp.get("retires_trigger_ids", []) or []:
            edges.append((lid, ref))
    return edges


def reconcile(loops: dict, registry: dict) -> dict:
    defined = defined_trigger_ids(registry, loops)
    edges = referenced_edges(loops)
    dangling = [{"loop_id": lid, "retires_trigger_id": ref}
                for (lid, ref) in edges if ref not in defined]
    verdict = "CHECK_OK" if not dangling else "CHECK_REJECTED"
    return {
        "origin": "sandbox-advisory", "authority": "none", "pass_claimed": False,
        "verdict": verdict,
        "defined_trigger_ids": sorted(defined),
        "referenced_count": len(edges),
        "dangling_count": len(dangling),
        "dangling_references": dangling,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--loops", type=Path, default=DEFAULT_LOOPS)
    ap.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    args = ap.parse_args(argv)

    loops = json.loads(args.loops.read_text(encoding="utf-8"))
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    res = reconcile(loops, registry)

    print(f"WI-4 TRIGGER_RECONCILE: {res['verdict']}  "
          f"({res['referenced_count']} refs, {len(res['defined_trigger_ids'])} defined)")
    for d in res["dangling_references"]:
        print(f"  [dangling] loop {d['loop_id']} retires_trigger_id {d['retires_trigger_id']!r} "
              f"-> no matching trigger_id in registry")
    if not res["dangling_references"]:
        print("  all retires_trigger_ids resolve to defined trigger_ids")
    return 0 if res["verdict"] == "CHECK_OK" else 1


if __name__ == "__main__":
    sys.exit(main())
