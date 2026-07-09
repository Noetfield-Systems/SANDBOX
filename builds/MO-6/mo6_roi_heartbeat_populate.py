#!/usr/bin/env python3
"""
MO-6 — ROI Heartbeat Populator  (catalog build B3 · MO-6)

Ground: scripts/write_roi_heartbeat_v1.py emits a `roi-heartbeat-receipt-v1`
whose metrics (and top-level `blocker_count`) are ALL hardcoded to the string
"unknown" — a no-fabrication placeholder awaiting live TrustField cost_event /
Signal Factory data.

This populator fills ONLY what is derivable from LOCAL receipts/census JSON,
strictly append-only and offline:

  * blocker_count  -> DERIVED by hand-counting the open blockers in the LATEST
    agent-read-staleness receipt on disk (blockers[] entries whose
    severity == "BLOCKER"). The staleness motor already recomputes this every
    tick; we re-derive from its blockers[] array rather than trusting any stored
    scalar, so the number is grounded in local artifact content.

  * every other metric (cost_per_signal_cad, free_tier_ceiling_max_pct,
    trap_battery_pass_pct, fixture_agreement_pct, pattern_exports_per_week,
    receipt_chain_verifier) requires LIVE Supabase cost_event / Signal Factory
    fixtures that this offline populator MUST NOT read. Per the no-fabrication
    contract these STAY the string "unknown" — never fabricated to 0.

NO live calls: reads only local JSON under receipts/. NEVER opens Supabase,
cost_event, or any network source. NEVER overwrites a prior heartbeat or any
tracked receipt: writes a fresh timestamped file into the MO-6 build dir only.

Verdict vocab: CHECK_OK / CHECK_REJECTED (advisory), never a bare governance
PASS. The `verify` subcommand is a no-fabrication DETECTOR that exits NONZERO
when a metric that is NOT locally derivable has been fabricated to a concrete
value instead of staying "unknown".

    python3 mo6_roi_heartbeat_populate.py populate [--receipts DIR] [--out DIR]
    python3 mo6_roi_heartbeat_populate.py verify   <heartbeat.json>
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

UNKNOWN = "unknown"

# Metrics that require LIVE cost_event / Signal Factory sources this offline
# populator is forbidden to read. They MUST remain "unknown" (no fabrication).
NON_LOCALLY_DERIVABLE = (
    "cost_per_signal_cad",
    "free_tier_ceiling_max_pct",
    "trap_battery_pass_pct",
    "fixture_agreement_pct",
    "pattern_exports_per_week",
    "receipt_chain_verifier",
)


def _repo_root() -> Path:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=Path(__file__).resolve().parent,
            text=True, capture_output=True, check=True,
        )
        return Path(out.stdout.strip())
    except Exception:
        return Path(__file__).resolve().parents[3]


REPO = _repo_root()
DEFAULT_RECEIPTS = REPO / "receipts"
DEFAULT_OUT = Path(__file__).resolve().parent  # MO-6 build dir — never receipts/


def _staleness_receipts(receipts_dir: Path) -> list[Path]:
    return sorted(receipts_dir.glob("agent-read-staleness-*.json"))


def latest_staleness_receipt(receipts_dir: Path) -> Path | None:
    """Newest agent-read-staleness receipt by its self-reported `at` timestamp
    (falling back to filename order)."""
    files = _staleness_receipts(receipts_dir)
    if not files:
        return None

    def _key(p: Path):
        try:
            return (json.loads(p.read_text(encoding="utf-8")).get("at", ""), p.name)
        except Exception:
            return ("", p.name)

    return max(files, key=_key)


def count_open_blockers(receipt: dict) -> int:
    """Hand-count blockers[] entries whose severity == 'BLOCKER'. Derived from
    array content, not from any stored scalar."""
    return sum(
        1 for b in (receipt.get("blockers") or [])
        if isinstance(b, dict) and b.get("severity") == "BLOCKER"
    )


def derive_blocker_count(receipts_dir: Path):
    """int when a local staleness receipt exists; otherwise UNKNOWN — an
    underivable metric is NEVER fabricated to 0."""
    latest = latest_staleness_receipt(receipts_dir)
    if latest is None:
        return UNKNOWN
    receipt = json.loads(latest.read_text(encoding="utf-8"))
    return count_open_blockers(receipt)


def build_heartbeat(receipts_dir: Path = DEFAULT_RECEIPTS, ts: str | None = None) -> dict:
    ts = ts or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bc = derive_blocker_count(receipts_dir)
    latest = latest_staleness_receipt(receipts_dir)
    return {
        "schema": "roi-heartbeat-receipt-v1",
        "receipt_id": f"mo6-roi-heartbeat-{ts}",
        "recorded_at": ts,
        "origin": "sandbox-advisory",
        "authority": "none",
        "pass_claimed": False,
        "metrics": {
            # LIVE-only metrics stay "unknown" — no fabrication.
            "cost_per_signal_cad": UNKNOWN,
            "free_tier_ceiling_max_pct": UNKNOWN,
            "trap_battery_pass_pct": UNKNOWN,
            "fixture_agreement_pct": UNKNOWN,
            "pattern_exports_per_week": UNKNOWN,
            "receipt_chain_verifier": UNKNOWN,
        },
        # DERIVED from local staleness receipt content.
        "blocker_count": bc,
        "derivation": {
            "blocker_count": {
                "method": "count blockers[] with severity=='BLOCKER' in latest agent-read-staleness receipt",
                "source": (str(latest.relative_to(REPO)) if latest else None),
                "locally_derivable": latest is not None,
            }
        },
        "no_fabrication_contract": (
            "metrics requiring live cost_event / Signal Factory data remain 'unknown'; "
            "only blocker_count is derived from local receipts"
        ),
        "source": "LOCAL receipts/agent-read-staleness-*.json (offline; no Supabase)",
    }


def no_fabrication_violations(hb: dict) -> list[str]:
    """DETECTOR: return the ways `hb` breaks the no-fabrication contract.
    Empty list == clean (CHECK_OK). Non-empty == CHECK_REJECTED."""
    v: list[str] = []
    metrics = hb.get("metrics", {})
    for name in NON_LOCALLY_DERIVABLE:
        val = metrics.get(name, "<absent>")
        if val != UNKNOWN:
            v.append(
                f"metric {name!r} was fabricated to {val!r} — not locally derivable, "
                f"must stay {UNKNOWN!r}"
            )
    bc = hb.get("blocker_count", "<absent>")
    if not (bc == UNKNOWN or (isinstance(bc, int) and not isinstance(bc, bool) and bc >= 0)):
        v.append(f"blocker_count {bc!r} is neither {UNKNOWN!r} nor a non-negative int")
    return v


def write_heartbeat(hb: dict, out_dir: Path = DEFAULT_OUT) -> Path:
    """Append-only write of a fresh timestamped heartbeat. REFUSES to overwrite
    an existing file, and refuses to write into the tracked receipts/ tree."""
    out_dir = out_dir.resolve()
    if out_dir == DEFAULT_RECEIPTS.resolve() or DEFAULT_RECEIPTS.resolve() in out_dir.parents:
        raise RuntimeError(f"refusing to write into tracked receipts tree: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{hb['receipt_id']}.json"
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing heartbeat: {path}")
    path.write_text(json.dumps(hb, indent=2) + "\n", encoding="utf-8")
    return path


def _cmd_populate(args) -> int:
    hb = build_heartbeat(args.receipts)
    violations = no_fabrication_violations(hb)
    if violations:  # self-check: our own builder must never fabricate.
        print("MO-6 ROI_HEARTBEAT: CHECK_REJECTED (self-check found fabrication)")
        for m in violations:
            print(f"  [fabricated] {m}")
        return 1
    path = write_heartbeat(hb, args.out)
    print(f"MO-6 ROI_HEARTBEAT: CHECK_OK  blocker_count={hb['blocker_count']!r}")
    print(f"  wrote {path}")
    return 0


def _cmd_verify(args) -> int:
    hb = json.loads(Path(args.path).read_text(encoding="utf-8"))
    violations = no_fabrication_violations(hb)
    verdict = "CHECK_OK" if not violations else "CHECK_REJECTED"
    print(f"MO-6 NO_FABRICATION_VERIFY: {verdict}")
    for m in violations:
        print(f"  [fabricated] {m}")
    if not violations:
        print("  all non-derivable metrics correctly held at 'unknown'")
    return 0 if not violations else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_pop = sub.add_parser("populate", help="derive + write a fresh heartbeat")
    p_pop.add_argument("--receipts", type=Path, default=DEFAULT_RECEIPTS)
    p_pop.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p_pop.set_defaults(func=_cmd_populate)

    p_ver = sub.add_parser("verify", help="detect fabricated metrics in a heartbeat")
    p_ver.add_argument("path")
    p_ver.set_defaults(func=_cmd_verify)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
