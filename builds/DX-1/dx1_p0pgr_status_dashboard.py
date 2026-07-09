#!/usr/bin/env python3
"""
DX-1 - P0-PGR read-only status dashboard renderer  (catalog build B4 . DX-1)

Reads the on-disk P0-PGR receipts (source of truth, READ-ONLY):
  * receipts/p0pgr/phase1_scorecard_v1.json   (Phase-1 shadow-campaign scorecard)
  * receipts/p0pgr/phase2_scorecard_v1.json   (Phase-2 cloud-only ROI scorecard)
  * receipts/p0pgr/phase2_queue_v1.json       (ranked queue receipt)
  * p0-pgr/P0_PGR_CLOUD_ACTIVATION_LADDER_v1.md (R1-R5 ladder)

and renders ONE self-contained, theme-aware, brand-neutral static HTML dashboard to a
LOCAL out/ dir showing: the ROI-ranked Phase-2 queue (in the REAL receipt order),
gate/invariant states, and the R1-R5 cloud-activation ladder with per-rung state.

Freshness / honesty locks baked in (B4 deliverable guards):
  * Lock 10 - the HTML is written only to a local out/ path and carries a visible
    "DO NOT PUSH - not for public hosting" banner. Never a hosting path.
  * Source-freshness badges: any source older than STALE_HOURS of the render time is
    flagged STALE; the dashboard never presents stale data as live.
  * EMPTY-SINK / STUB vs CLEAN: attestation fields that were never populated render an
    explicit UNPOPULATED badge - never a clean/all-clear "0" or blank. Safety-invariant
    counters render CLEAN only when a real 0 was measured.
  * Autonomy rungs (R4/R5) render LOCKED / proof-gated, never "available".

    python3 dx1_p0pgr_status_dashboard.py            # render out/p0pgr_status_dashboard.html
    python3 dx1_p0pgr_status_dashboard.py --print-queue-order
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE_PATH = HERE / "dashboard_template.html"
OUT_DIR = HERE / "out"                                     # Lock 10: local out/, never a hosting path
OUT_HTML = OUT_DIR / "p0pgr_status_dashboard.html"

BANNER_TEXT = "DO NOT PUSH - not for public hosting (internal read-only P0-PGR status snapshot)"
STALE_HOURS = 24
FOOTER_NOTE = (
    "Read-only snapshot rendered from on-disk P0-PGR receipts. It reflects the receipts as they were "
    "on the render date - it is an observation, not a live control surface and not a guarantee of runtime "
    "state. UNPOPULATED and STALE badges mark fields that were never filled or whose source is older than "
    f"{STALE_HOURS}h; those are NOT clean zeros. No autonomy is claimed: rungs R4-R5 are LOCKED / proof-gated."
)

# --- source locations (relative to sg-sandbox repo root) ---
SRC_PHASE1 = "receipts/p0pgr/phase1_scorecard_v1.json"
SRC_PHASE2 = "receipts/p0pgr/phase2_scorecard_v1.json"
SRC_QUEUE = "receipts/p0pgr/phase2_queue_v1.json"
SRC_LADDER = "p0-pgr/P0_PGR_CLOUD_ACTIVATION_LADDER_v1.md"

# Safety invariants: a measured 0 here is genuinely CLEAN (good).
INVARIANT_FIELDS = {
    "p0_leakage_count": "P0 leakage",
    "hard_block_count": "Hard blocks",
    "runtime_freeze_count": "Runtime freezes",
    "unauthorized_execution_count": "Unauthorized executions",
}
# Attestation fields: a 0/empty here means "never populated / no receipt yet",
# NOT a clean zero -> must render UNPOPULATED.
ATTESTATION_FIELDS = {
    "packets_confirmed_accepted_by_founder": "Founder-confirmed accepts",
}


def _repo_root() -> Path:
    # catalog/builds/DX-1 -> up 3 == sg-sandbox root
    return HERE.parents[2]


def _e(s) -> str:
    return html.escape(str(s), quote=True)


# --------------------------------------------------------------------------- load
def load_inputs(repo_root: Path | None = None) -> dict:
    root = repo_root or _repo_root()
    p1 = json.loads((root / SRC_PHASE1).read_text(encoding="utf-8"))
    p2 = json.loads((root / SRC_PHASE2).read_text(encoding="utf-8"))
    q = json.loads((root / SRC_QUEUE).read_text(encoding="utf-8"))
    ladder_txt = (root / SRC_LADDER).read_text(encoding="utf-8")
    return {
        "phase1": p1,
        "phase2": p2,
        "queue": q,
        "ladder_text": ladder_txt,
        "ladder": parse_ladder(ladder_txt),
        "sources": [
            (SRC_PHASE1, p1.get("updated_at")),
            (SRC_PHASE2, p2.get("updated_at")),
            (SRC_QUEUE, q.get("generated_at")),
            (SRC_LADDER, None),   # markdown has no machine timestamp
        ],
    }


def parse_ladder(text: str) -> list[dict]:
    """Extract R1..R5 rungs and their declared state from the ladder markdown headings.

    A heading looks like:  '### R2 - Cloud manual trigger (BUILT, awaiting founder push + first run)'
    State is derived from the parenthetical keywords; founder-unlock rungs are LOCKED.
    """
    current = None
    m = re.search(r"Current rung:\s*(R\d)", text)
    if m:
        current = m.group(1)
    rungs = []
    for hm in re.finditer(r"^###\s*(R\d)\s*[-—]\s*(.+)$", text, flags=re.M):
        rid = hm.group(1)
        rest = hm.group(2).strip()
        paren = ""
        pm = re.search(r"\(([^)]*)\)", rest)
        if pm:
            paren = pm.group(1)
        title = re.sub(r"\s*\([^)]*\)\s*$", "", rest).strip()
        low = (rest + " " + paren).lower()
        if "founder unlock" in low:
            state = "LOCKED"
        elif "done" in low:
            state = "DONE"
        elif "built" in low:
            state = "BUILT"
        else:
            state = "PENDING"
        rungs.append({
            "id": rid, "title": title, "detail": paren,
            "state": state, "current": (rid == current),
        })
    return rungs


# ----------------------------------------------------------------- freshness / stub
def freshness(updated_at: str | None, now: datetime, stale_hours: int = STALE_HOURS) -> dict:
    """Classify a source timestamp. Returns kind in {FRESH, STALE, UNKNOWN} + age hours."""
    if not updated_at:
        return {"kind": "UNKNOWN", "age_hours": None, "updated_at": None}
    try:
        ts = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
    except ValueError:
        return {"kind": "UNKNOWN", "age_hours": None, "updated_at": updated_at}
    age = (now - ts).total_seconds() / 3600.0
    return {
        "kind": "STALE" if age > stale_hours else "FRESH",
        "age_hours": round(age, 1),
        "updated_at": updated_at,
    }


def is_unpopulated(value) -> bool:
    """A value is UNPOPULATED (stub / empty sink) when it is null, empty text, empty
    container, or a zero standing in for 'no receipt yet'."""
    return value in (None, "", 0) or value == [] or value == {}


def classify_metric(field: str, value) -> dict:
    """Classify a scorecard metric into a render badge.

    INVARIANT + value==0            -> CLEAN (b-ok)      : a measured, good zero.
    ATTESTATION + unpopulated       -> UNPOPULATED (b-unpop): never filled; NOT clean.
    otherwise                       -> VALUE (b-warn if unpopulated-ish else neutral)
    """
    if field in ATTESTATION_FIELDS:
        if is_unpopulated(value):
            return {"badge": "UNPOPULATED", "cls": "b-unpop",
                    "note": "no founder-confirmation receipt yet - not a clean 0"}
        return {"badge": "POPULATED", "cls": "b-ok", "note": ""}
    if field in INVARIANT_FIELDS:
        if value == 0:
            return {"badge": "CLEAN", "cls": "b-ok", "note": "measured 0"}
        return {"badge": "BREACH", "cls": "b-stale", "note": "non-zero invariant"}
    # generic
    if is_unpopulated(value):
        return {"badge": "UNPOPULATED", "cls": "b-unpop", "note": "empty / stub"}
    return {"badge": "OK", "cls": "b-ok", "note": ""}


# --------------------------------------------------------------------------- render
def _queue_rows(queue: dict) -> str:
    rows = []
    for i, item in enumerate(queue.get("ranked_queue", []), start=1):
        commercial = ' <span class="commercial">$ commercial</span>' if item.get("value_class_commercial") else ""
        rows.append(
            f'<tr data-move="{_e(item["move_id"])}">'
            f'<td class="rank">{i}</td>'
            f'<td class="mv">{_e(item["move_id"])}{commercial}</td>'
            f'<td>{_e(item.get("packet_id",""))}</td>'
            f'<td class="score">{_e(item.get("phase2_score",""))}</td>'
            f'<td>{_e(item.get("route_decision",""))}</td>'
            f'<td>{_e(item.get("rationale",""))}</td>'
            f'</tr>'
        )
    return "\n      ".join(rows)


def _held_rows(queue: dict) -> str:
    out = []
    for h in queue.get("held_items", []):
        badge = "b-locked" if h.get("status", "").startswith("HOLD") else "b-warn"
        out.append(
            f'<li><span class="grow"><b>{_e(h["move_id"])}</b> '
            f'{_e(h.get("packet_id",""))} &mdash; {_e(h.get("reason",""))}</span>'
            f'<span class="badge {badge}">{_e(h.get("status",""))}</span></li>'
        )
    return "".join(out)


def _gate_cards(data: dict, now: datetime) -> str:
    """Render safety invariants (from phase2 counters) + attestation fields (from phase1)."""
    phase1 = data["phase1"]
    counters = data["phase2"].get("counters", {})
    cards = []
    # attestation fields (phase1) - these are the UNPOPULATED-capable ones
    for field, label in ATTESTATION_FIELDS.items():
        val = phase1.get(field)
        c = classify_metric(field, val)
        shown = "&mdash;" if is_unpopulated(val) else _e(val)
        cards.append(
            f'<div class="card" data-field="{_e(field)}">'
            f'<div class="k"><span>{_e(label)}</span><span class="badge {c["cls"]}">{c["badge"]}</span></div>'
            f'<div class="v">{shown}</div>'
            f'<div class="note">{_e(c["note"])}</div></div>'
        )
    # safety invariants (phase2 counters)
    for field, label in INVARIANT_FIELDS.items():
        val = counters.get(field, phase1.get(field))
        c = classify_metric(field, val)
        cards.append(
            f'<div class="card" data-field="{_e(field)}">'
            f'<div class="k"><span>{_e(label)}</span><span class="badge {c["cls"]}">{c["badge"]}</span></div>'
            f'<div class="v">{_e(val)}</div>'
            f'<div class="note">{_e(c["note"])}</div></div>'
        )
    return "".join(cards)


def _gate_checklist(queue: dict) -> str:
    cand = queue.get("first_execution_candidate", {})
    gates = cand.get("gates_required", [])
    out = []
    for g in gates:
        out.append(f'<li><span class="grow">{_e(g)}</span><span class="badge b-ok">REQUIRED</span></li>')
    return "".join(out)


def _source_badges(data: dict, now: datetime) -> str:
    out = []
    for path, ts in data["sources"]:
        f = freshness(ts, now)
        if f["kind"] == "STALE":
            cls, label = "b-stale", f"STALE ({f['age_hours']}h old)"
        elif f["kind"] == "FRESH":
            cls, label = "b-ok", f"FRESH ({f['age_hours']}h)"
        else:
            cls, label = "b-unpop", "NO TIMESTAMP"
        out.append(
            f'<div class="src"><div><span class="badge {cls}">{_e(label)}</span></div>'
            f'<div class="path">{_e(path)}</div></div>'
        )
    return "".join(out)


def _ladder_rows(rungs: list[dict]) -> str:
    badge_cls = {"DONE": "b-done", "BUILT": "b-built", "LOCKED": "b-locked", "PENDING": "b-warn"}
    badge_txt = {"DONE": "DONE", "BUILT": "BUILT", "LOCKED": "LOCKED . proof-gated", "PENDING": "PENDING"}
    out = []
    for r in rungs:
        cur = ' <span class="current">&larr; current rung</span>' if r["current"] else ""
        cls = badge_cls.get(r["state"], "b-warn")
        txt = badge_txt.get(r["state"], r["state"])
        detail = f'<div class="gate-note">{_e(r["detail"])}</div>' if r["detail"] else ""
        out.append(
            f'<li data-rung="{_e(r["id"])}"><span class="rung-body">'
            f'<span class="rname">{_e(r["id"])} &mdash; {_e(r["title"])}</span>{cur}{detail}</span>'
            f'<span class="badge {cls}">{_e(txt)}</span></li>'
        )
    return "".join(out)


def render(data: dict, now: datetime | None = None, template: str | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    if template is None:
        template = TEMPLATE_PATH.read_text(encoding="utf-8")
    queue = data["queue"]
    p2 = data["phase2"]
    cand = queue.get("first_execution_candidate", {})
    next_label = f'{cand.get("move_id","?")} / {cand.get("packet_id","?")}'
    repl = {
        "__BANNER_TEXT__": _e(BANNER_TEXT),
        "__SUBTITLE__": _e(
            f'Operating mode: {p2.get("operating_mode","?")} . campaign '
            f'{data["phase1"].get("campaign","?")} . rendered {now.strftime("%Y-%m-%dT%H:%MZ")}'),
        "__STALE_HOURS__": str(STALE_HOURS),
        "__SOURCE_BADGES__": _source_badges(data, now),
        "__QUEUE_CAPTION__": _e(
            f'{len(queue.get("ranked_queue", []))} ranked moves, ROI weights '
            f'{json.dumps(queue.get("weights", {}))}. Order below is the exact receipt order '
            f'(highest phase2_score first).'),
        "__QUEUE_ROWS__": _queue_rows(queue),
        "__HELD_ROWS__": _held_rows(queue),
        "__GATE_CARDS__": _gate_cards(data, now),
        "__NEXT_CANDIDATE__": _e(next_label),
        "__GATE_CHECKLIST__": _gate_checklist(queue),
        "__LADDER_CAPTION__": _e(
            "Ordered path from session-driven to self-running. R4-R5 (autonomy) stay LOCKED / "
            "proof-gated - shown for context, never presented as unlocked or offered."),
        "__LADDER_ROWS__": _ladder_rows(data["ladder"]),
        "__FOOTER_NOTE__": _e(FOOTER_NOTE),
    }
    out = template
    for k, v in repl.items():
        out = out.replace(k, v)
    return out


def build(out_path: Path = OUT_HTML, now: datetime | None = None,
          repo_root: Path | None = None) -> Path:
    data = load_inputs(repo_root)
    html_out = render(data, now=now)
    out_path.parent.mkdir(parents=True, exist_ok=True)     # Lock 10: local out/ only
    out_path.write_text(html_out, encoding="utf-8")
    return out_path


def queue_order(data: dict | None = None) -> list[str]:
    data = data or load_inputs()
    return [i["move_id"] for i in data["queue"].get("ranked_queue", [])]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=OUT_HTML)
    ap.add_argument("--print-queue-order", action="store_true")
    args = ap.parse_args(argv)

    data = load_inputs()
    if args.print_queue_order:
        print(" > ".join(queue_order(data)))
        return 0
    out = build(args.out)
    print(f"DX-1 rendered -> {out}")
    print(f"queue order: {' > '.join(queue_order(data))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
