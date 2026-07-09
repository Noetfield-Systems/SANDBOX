#!/usr/bin/env python3
"""
MO-4 — Repair-Candidate Re-Linter  (catalog build B3 · MO-4)

Static, READ-ONLY re-verifier layered on the ground packet linter
(scripts/p0pgr_packet_lint_v1.py). It answers one question the raw linter does
not: "given a filed repair candidate (or a packet), does the referenced packet
STILL lint the same way today, and did anything actually get repaired?"

For each repair candidate it:
  1) resolves the packet the candidate refers to (its recorded ``packet_path`` if
     that file exists on disk today, else ``<corpus>/<packet_id>.json``);
  2) re-runs the ground linter against that packet NOW (the "after" reasons);
  3) diffs the "after" reasons against the reasons recorded in the candidate at
     filing time (the "before" reasons) — resolved / still_present / newly_introduced.

Verdict vocab: CHECK_OK / CHECK_REJECTED (never a bare governance PASS).
  * a packet that re-lints clean  -> CHECK_OK   (no violation; repair confirmed)
  * a packet with a real violation -> CHECK_REJECTED, citing the exact reason(s)
  * a candidate whose referenced packet cannot be resolved -> CHECK_REJECTED
    (UNRESOLVED_PACKET: the repair cannot be re-verified — reported, not hidden)

Exits NONZERO whenever any assessed item is CHECK_REJECTED (this is a real
detector, not an always-exit-0 stub). Reads only; never writes or mutates any
packet, repair candidate, or receipt.

    python3 mo4_repair_relint.py [--candidates DIR] [--corpus DIR] [--packet FILE]
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
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                             cwd=Path(__file__).resolve().parent, text=True,
                             capture_output=True, check=True)
        return Path(out.stdout.strip())
    except Exception:
        return Path(__file__).resolve().parents[3]


REPO = _repo_root()
GROUND_LINTER = REPO / "scripts" / "p0pgr_packet_lint_v1.py"
DEFAULT_CANDIDATES = REPO / "receipts" / "p0pgr" / "repair_candidates"
DEFAULT_CORPUS = REPO / "receipts" / "p0pgr" / "outbox"


def load_linter(path: Path = GROUND_LINTER):
    """Import the ground linter module by path (no relaxation, no reimplementation
    — MO-4 re-runs the SAME lint_packet the runtime files repair candidates with)."""
    spec = importlib.util.spec_from_file_location("p0pgr_lint_ground", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def relint(packet: dict, linter=None) -> dict:
    """Re-run the ground linter over one packet dict. Returns its native result."""
    linter = linter or load_linter()
    return linter.lint_packet(packet)


def diff_reasons(before, after) -> dict:
    """before = reasons recorded on the repair candidate at filing time.
    after  = reasons the linter emits for the referenced packet NOW.
    Order-independent set diff, but keeps stable sorted output."""
    b, a = set(before or []), set(after or [])
    return {
        "resolved": sorted(b - a),          # were flagged, now gone (repaired)
        "still_present": sorted(b & a),     # flagged then and now (not repaired)
        "newly_introduced": sorted(a - b),  # new violations not seen at filing
    }


def resolve_packet(candidate: dict, corpus_dir: Path) -> Path | None:
    """Find the packet a repair candidate refers to. The recorded packet_path wins
    if it still exists on disk; otherwise fall back to <corpus>/<packet_id>.json."""
    pp = candidate.get("packet_path")
    if isinstance(pp, str) and pp:
        p = Path(pp)
        if p.is_file():
            return p
    pid = candidate.get("packet_id")
    if isinstance(pid, str) and pid:
        cand = corpus_dir / f"{pid}.json"
        if cand.is_file():
            return cand
    return None


def assess_candidate(candidate: dict, corpus_dir: Path, linter=None) -> dict:
    """Re-verify one repair candidate. CHECK_OK only if its referenced packet
    both resolves AND re-lints clean today."""
    linter = linter or load_linter()
    packet_path = resolve_packet(candidate, corpus_dir)
    before = candidate.get("reasons", []) or []
    base = {
        "origin": "sandbox-advisory", "authority": "none", "pass_claimed": False,
        "packet_id": candidate.get("packet_id", "UNKNOWN"),
        "cycle_id": candidate.get("cycle_id"),
        "before_reasons": sorted(before),
    }
    if packet_path is None:
        return {**base, "status": "UNRESOLVED_PACKET", "verdict": "CHECK_REJECTED",
                "resolved_packet_path": None, "after_reasons": None,
                "reason_diff": None,
                "note": "referenced packet not found on disk (recorded packet_path "
                        "missing and no <corpus>/<packet_id>.json); repair cannot be re-verified"}
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    res = relint(packet, linter)
    after = res["reasons"]
    verdict = "CHECK_OK" if not after else "CHECK_REJECTED"
    return {**base, "status": "RESOLVED", "verdict": verdict,
            "resolved_packet_path": str(packet_path),
            "linter_verdict": res["verdict"], "degraded_mode": res.get("degraded_mode"),
            "after_reasons": sorted(after),
            "reason_diff": diff_reasons(before, after)}


def assess_packet(packet: dict, linter=None) -> dict:
    """Re-lint a raw packet (no repair-candidate context). Red-capable core:
    a clean packet -> CHECK_OK; a packet with a real violation -> CHECK_REJECTED."""
    res = relint(packet, linter or load_linter())
    reasons = res["reasons"]
    return {
        "origin": "sandbox-advisory", "authority": "none", "pass_claimed": False,
        "packet_id": packet.get("id", "UNKNOWN"),
        "verdict": "CHECK_OK" if not reasons else "CHECK_REJECTED",
        "linter_verdict": res["verdict"], "degraded_mode": res.get("degraded_mode"),
        "reasons": sorted(reasons),
    }


def run(candidates_dir: Path, corpus_dir: Path, linter=None) -> dict:
    linter = linter or load_linter()
    cand_reports, pkt_reports = [], []
    for cf in sorted(candidates_dir.glob("*.json")) if candidates_dir.is_dir() else []:
        try:
            candidate = json.loads(cf.read_text(encoding="utf-8"))
        except Exception as e:  # pragma: no cover - defensive
            cand_reports.append({"packet_id": cf.name, "status": "UNREADABLE",
                                 "verdict": "CHECK_REJECTED", "note": str(e)})
            continue
        cand_reports.append(assess_candidate(candidate, corpus_dir, linter))
    for pf in sorted(corpus_dir.glob("*.json")) if corpus_dir.is_dir() else []:
        packet = json.loads(pf.read_text(encoding="utf-8"))
        pkt_reports.append(assess_packet(packet, linter))
    rejected = ([c for c in cand_reports if c["verdict"] == "CHECK_REJECTED"]
                + [p for p in pkt_reports if p["verdict"] == "CHECK_REJECTED"])
    return {
        "origin": "sandbox-advisory", "authority": "none", "pass_claimed": False,
        "tool": "mo4-repair-relint-v1",
        "verdict": "CHECK_OK" if not rejected else "CHECK_REJECTED",
        "candidate_reports": cand_reports,
        "packet_reports": pkt_reports,
        "rejected_count": len(rejected),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    ap.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    ap.add_argument("--packet", type=Path, default=None,
                    help="re-lint a single packet file and exit")
    args = ap.parse_args(argv)
    linter = load_linter()

    if args.packet is not None:
        packet = json.loads(args.packet.read_text(encoding="utf-8"))
        rep = assess_packet(packet, linter)
        print(json.dumps(rep, indent=2))
        return 0 if rep["verdict"] == "CHECK_OK" else 1

    out = run(args.candidates, args.corpus, linter)
    print(f"MO-4 REPAIR_RELINT: {out['verdict']}  "
          f"({len(out['candidate_reports'])} candidates, "
          f"{len(out['packet_reports'])} packets, "
          f"{out['rejected_count']} rejected)")
    for c in out["candidate_reports"]:
        line = f"  [candidate] {c['packet_id']} {c['verdict']} status={c.get('status')}"
        if c.get("reason_diff"):
            d = c["reason_diff"]
            line += (f" resolved={len(d['resolved'])}"
                     f" still={len(d['still_present'])}"
                     f" new={len(d['newly_introduced'])}")
        print(line)
    for p in out["packet_reports"]:
        if p["verdict"] != "CHECK_OK":
            print(f"  [packet] {p['packet_id']} {p['verdict']} reasons={p['reasons']}")
    return 0 if out["verdict"] == "CHECK_OK" else 1


if __name__ == "__main__":
    sys.exit(main())
