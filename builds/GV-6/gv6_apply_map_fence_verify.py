#!/usr/bin/env python3
"""
GV-6 — DLM apply-map fence validator  (catalog build B1 · GV-6)

The Decision Language Machine's apply-map stage (decision_language_machine_v1/
dlm_apply_map_v1.py::build_apply_map) is the FENCE between validated picks and an
OFFICIAL form submit. That fence is founder-gated. GV-6 is a DETECTOR: it validates
a PERSISTED apply_map.json (it NEVER re-calls build_apply_map at verify time, and it
NEVER edits the fence) and FLAGS leaks. Verdict vocab is CHECK_OK / CHECK_REJECTED —
never a bare governance PASS.

It reads the persisted apply_map by data only and IGNORES any self-emitted stage
"decision" field (a DLM stage decision:PASS is not a gate verdict). Invariants:

  (a) machine_closed_without_founder never intersects picks
      — a machine-auto-closed id must never also be a founder-applied pick.
  (b) if target_form == FORM_OFFICIAL: status in {READY, EMPTY, BLOCKED_UNVALIDATED}
      and there is NO submit / auto_submit / dispatch_now field
      — the fence never auto-submits an OFFICIAL form.
  (c) every ADVISOR_REVIEW / FOUNDER_FACT item id (from the run's sibling
      processed.json) is in picks OR an explicit deferred_unvalidated list.
      A dropped-silently unvalidated item is a FENCE LEAK and is FLAGGED
      (founder-gated finding — GV-6 flags it, it does NOT patch the fence).

    python3 gv6_apply_map_fence_verify.py [--apply-map PATH] [--processed PATH] [--emit-verdict-dir DIR]

If --processed is omitted it is derived from the run id in the apply_map filename
({run_id}.apply_map.json -> {run_id}.processed.json in the same dir).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

OFFICIAL_OK_STATUS = {"READY", "EMPTY", "BLOCKED_UNVALIDATED"}
SUBMIT_KEYS = ("submit", "auto_submit", "dispatch_now")
UNVALIDATED_CLASSES = {"ADVISOR_REVIEW", "FOUNDER_FACT"}


def _repo_root() -> Path:
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                             cwd=Path(__file__).resolve().parent, text=True, capture_output=True, check=True)
        return Path(out.stdout.strip())
    except Exception:
        return Path(__file__).resolve().parents[3]


REPO = _repo_root()
DLM_OUTPUT = REPO / "decision_language_machine_v1" / "output"


def _pick_ids(apply_map: dict) -> set[str]:
    picks = apply_map.get("picks")
    ids: set[str] = set()
    if isinstance(picks, list):
        for row in picks:
            if isinstance(row, dict) and "id" in row:
                ids.add(str(row["id"]))
    elif isinstance(picks, dict):
        ids = {str(k) for k in picks}
    return ids


def advisor_founder_ids(processed: list[dict]) -> set[str]:
    return {str(p["id"]) for p in processed
            if isinstance(p, dict) and p.get("classification") in UNVALIDATED_CLASSES}


def verify(apply_map: dict, unvalidated_universe: set[str] | None) -> dict:
    """Validate a persisted apply_map by data only. Never re-calls build_apply_map."""
    violations: list[str] = []
    fence_leaks: list[str] = []

    pick_ids = _pick_ids(apply_map)
    machine_closed = set(str(x) for x in apply_map.get("machine_closed_without_founder", []) or [])
    status = apply_map.get("status")
    target_form = apply_map.get("target_form")

    # (a) machine_closed_without_founder never intersects picks
    overlap = sorted(machine_closed & pick_ids)
    if overlap:
        violations.append(
            f"(a) machine_closed_without_founder intersects picks: {overlap} "
            "— a machine-auto-closed id is also a founder-applied pick")

    # (b) OFFICIAL form: status gated + no auto-submit field
    if target_form == "FORM_OFFICIAL":
        if status not in OFFICIAL_OK_STATUS:
            violations.append(
                f"(b) FORM_OFFICIAL status {status!r} not in {sorted(OFFICIAL_OK_STATUS)} "
                "— fence must not report an applied/submitted state for an OFFICIAL form")
        present = [k for k in SUBMIT_KEYS if k in apply_map]
        if present:
            violations.append(
                f"(b) FORM_OFFICIAL apply_map carries auto-submit field(s) {present} "
                "— the fence never auto-submits; submit is downstream and founder-gated")

    # (c) no ADVISOR/FOUNDER item silently dropped (fence leak). BLOCKED_UNVALIDATED is an
    #     explicit block (missing_ids names them) — not a silent drop.
    if unvalidated_universe is not None and status != "BLOCKED_UNVALIDATED":
        deferred_unvalidated = set(str(x) for x in apply_map.get("deferred_unvalidated", []) or [])
        accounted = pick_ids | deferred_unvalidated
        dropped = sorted(unvalidated_universe - accounted)
        if dropped:
            fence_leaks = dropped
            violations.append(
                f"(c) {len(dropped)} unvalidated ADVISOR/FOUNDER item(s) dropped silently "
                f"(neither in picks nor an explicit deferred_unvalidated list): {dropped[:5]}"
                f"{' …' if len(dropped) > 5 else ''} — FENCE LEAK")

    verdict = "CHECK_OK" if not violations else "CHECK_REJECTED"
    return {
        "origin": "sandbox-advisory",
        "authority": "none",
        "verdict": verdict,
        "pass_claimed": False,
        "target_form": target_form,
        "status": status,
        "checked": {
            "a_machine_closed_vs_picks": not overlap,
            "b_official_form_gate": target_form != "FORM_OFFICIAL" or not any(
                v.startswith("(b)") for v in violations),
            "c_no_silent_unvalidated_drop": (unvalidated_universe is None) or not fence_leaks,
        },
        "violations": violations,
        "fence_leaks": fence_leaks,
        # A fence leak is a founder-gated finding: GV-6 FLAGS it, it does NOT patch the
        # founder-gated fence in dlm_apply_map_v1.py.
        "founder_gated_finding": bool(fence_leaks),
        "note": ("advisory only — GV-6 detects & flags fence leaks; it never edits the "
                 "founder-gated DLM apply-map fence and never emits a bare PASS"),
    }


def _sibling_processed(apply_map_path: Path) -> Path | None:
    name = apply_map_path.name
    if name.endswith(".apply_map.json"):
        cand = apply_map_path.with_name(name.replace(".apply_map.json", ".processed.json"))
        if cand.exists():
            return cand
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply-map", type=Path, required=True)
    ap.add_argument("--processed", type=Path, default=None,
                    help="sibling processed.json; auto-derived from run id if omitted")
    ap.add_argument("--emit-verdict-dir", type=Path,
                    default=Path(__file__).resolve().parent / "verdicts")
    args = ap.parse_args(argv)

    apply_map = json.loads(args.apply_map.read_text(encoding="utf-8"))
    proc_path = args.processed or _sibling_processed(args.apply_map)
    universe = None
    if proc_path and proc_path.exists():
        universe = advisor_founder_ids(json.loads(proc_path.read_text(encoding="utf-8")))

    result = verify(apply_map, universe)
    result["subject_apply_map"] = str(args.apply_map)
    result["subject_processed"] = str(proc_path) if proc_path else None

    args.emit_verdict_dir.mkdir(parents=True, exist_ok=True)
    vp = args.emit_verdict_dir / f"verdict-{args.apply_map.stem}.json"
    vp.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")  # verdict to SCRATCH, never the subject

    print(f"GV-6 APPLY_MAP_FENCE: {result['verdict']}  ({args.apply_map.name})")
    if universe is None:
        print("  [warn] no processed.json — invariant (c) fence-leak check SKIPPED")
    for v in result["violations"]:
        print(f"  [violation] {v}")
    if result["founder_gated_finding"]:
        print("  FOUNDER_GATED_FINDING: fence leak detected — flag for founder; GV-6 does not patch the fence")
    print(f"  verdict written -> {vp}")
    return 0 if result["verdict"] == "CHECK_OK" else 1


if __name__ == "__main__":
    sys.exit(main())
