#!/usr/bin/env python3
"""
BR-1 — DLM -> P0-PGR packet bridge  (catalog build B3 · BR-1).

Fuses the two flagship brains: turns a DLM apply_map into P0-PGR DRAFT packets.
The founder-authority brakes (from BUILD_PLAN_PHASED_v1_LOCKED §B3 + the CHESS pass):

  * consumes ONLY a GV-6-PASSED apply_map. If GV-6 (the fence validator) returns
    CHECK_REJECTED (e.g. the default partial_batch=True map that silently drops
    unvalidated items), BR-1 REFUSES and emits ZERO packets. It never bridges a
    leaky apply_map, and never re-calls build_apply_map or edits the fence.
  * bridges ONLY MACHINE_VALIDATABLE items + ADVISOR items present in picks
    (validated). EXCLUDES every FOUNDER_FACT and every unvalidated advisor item.
  * every emitted packet hardcodes status=DRAFT and dispatch_now=false regardless
    of the apply_map status; never AUTO_DISPATCH_APPROVED, never a cron.
  * emits a machine_closed_without_founder manifest (the excluded items) for founder eyes.

Advisory: packets are DRAFT proposals, origin=sandbox-advisory, never a governance PASS.
"""
from __future__ import annotations

import importlib.util
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
_gv6_spec = importlib.util.spec_from_file_location(
    "gv6", REPO / "catalog" / "builds" / "GV-6" / "gv6_apply_map_fence_verify.py")
gv6 = importlib.util.module_from_spec(_gv6_spec)
_gv6_spec.loader.exec_module(gv6)

# hardcoded DRAFT brakes — applied to EVERY packet, independent of apply_map status
DRAFT_BRAKES = {
    "status": "DRAFT",
    "dispatch_now": False,
    "dispatch_mode": "shadow",
    "authority_scope": "observe",
}


def _make_draft_packet(item: dict) -> dict:
    return {
        "id": f"BR1-DRAFT-{item.get('id')}",
        **DRAFT_BRAKES,
        "origin": "sandbox-advisory",
        "authority": "none",
        "source_item_id": item.get("id"),
        "classification": item.get("classification"),
        "classification_reason": item.get("classification_reason") or item.get("classification"),
        "task": item.get("plain_english") or (item.get("item") or {}).get("raw_text") or "",
        "evidence_refs": [],
        "provenance": "DLM apply_map -> BR-1 bridge (GV-6 CHECK_OK required)",
    }


def bridge(apply_map: dict, processed: list[dict], unvalidated_universe: set[str]) -> dict:
    """Return {refused, gv6_verdict, packets, machine_closed_manifest}. Refuses a non-CHECK_OK apply_map."""
    gv6_res = gv6.verify(apply_map, unvalidated_universe)
    if gv6_res["verdict"] != "CHECK_OK":
        return {
            "refused": True,
            "gv6_verdict": gv6_res["verdict"],
            "refusal_reason": gv6_res.get("violations", []),
            "packets": [],
            "machine_closed_manifest": {},
        }

    pick_ids = gv6._pick_ids(apply_map)
    by_id = {p.get("id"): p for p in processed}
    bridgeable, excluded = [], []
    for iid, p in by_id.items():
        cls = p.get("classification")
        if cls == "MACHINE_VALIDATABLE" or (cls == "ADVISOR_REVIEW" and iid in pick_ids):
            bridgeable.append(iid)
        else:                                   # FOUNDER_FACT, unvalidated ADVISOR, DEFER
            excluded.append(iid)

    packets = [_make_draft_packet(by_id[i]) for i in bridgeable]
    manifest = {
        "note": "excluded from the bridge; founder eyes required before ANY dispatch",
        "founder_fact_ids": sorted(i for i in by_id if by_id[i].get("classification") == "FOUNDER_FACT"),
        "machine_closed_without_founder": sorted(
            set(str(x) for x in excluded)
            | {str(x) for x in (apply_map.get("machine_closed_without_founder") or [])}
        ),
    }
    return {"refused": False, "gv6_verdict": "CHECK_OK", "packets": packets, "machine_closed_manifest": manifest}


if __name__ == "__main__":
    import json
    ap = json.loads(Path(sys.argv[1]).read_text())
    pr = json.loads(Path(sys.argv[2]).read_text())
    uni = gv6.advisor_founder_ids(pr)
    out = bridge(ap, pr, uni)
    print(json.dumps({k: (v if k != "packets" else f"{len(v)} DRAFT packets") for k, v in out.items()}, indent=2))
    sys.exit(0 if not out["refused"] else 1)
