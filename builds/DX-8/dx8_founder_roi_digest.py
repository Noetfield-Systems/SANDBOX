#!/usr/bin/env python3
"""
DX-8 — Weekly Founder ROI Digest  (catalog build B4 · DX-8 · R5 rung deliverable)

A deterministic weekly digest that reads three REAL P0-PGR receipts and renders a
founder-facing md + HTML summary (to a LOCAL out/ dir):

    receipts/p0pgr/phase2_queue_v1.json        (ranked ROI queue + held items)
    receipts/p0pgr/phase2_scorecard_v1.json    (executions + running counters)
    receipts/p0pgr/P0PGR-EXEC-M03-20260708T1330Z.json  (executed candidate detail)

It surfaces, in order:
  * ranked moves            — the ROI-ranked queue (rank, move, score, rationale)
  * executed candidates     — what actually ran this cycle + quality_state + cost
  * findings needing founder eyes  — the M03 founder-eyes findings
  * held items              — HOLD_CLOUD_UNSAFE / SELF items (not silently dropped)
  * running counters        — cost / send / deploy counters, with a NO-SEND / NO-DEPLOY
                              invariant that is ASSERTED and rendered (all zero -> HOLD).

B4 deliverable guards baked in:
  * Lock 10 — every generated HTML carries a visible "DO NOT PUSH — not for public
    hosting" banner and is written only to a local out/ path (never a hosting path).
  * Theme-aware, brand-neutral, self-contained (inline CSS/JS).
  * Source-freshness badges (FRESH / STALE / UNKNOWN) — never render a null/absent
    field as a blank 0 that reads all-clear. Absent counters render UNPOPULATED, and
    the invariant becomes UNKNOWN (not OK). Present-and-zero renders "0 OK".
  * Derived aggregates are watermarked "DERIVED — advisory, not a guaranteed claim".
  * No autonomy / guaranteed-outcome claims — this is an advisory digest, authority=none.

Determinism: no wall-clock is read. "as_of" defaults to the latest source timestamp,
so the same inputs always render byte-identical output. --as-of overrides it (used to
exercise the STALE badge without mutating the inputs).

    python3 dx8_founder_roi_digest.py            # render out/founder_roi_digest.{md,html}
    python3 dx8_founder_roi_digest.py --as-of 2026-07-20T00:00:00Z   # force STALE badges
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE_PATH = HERE / "digest_template.html"
OUT_DIR = HERE / "out"                                  # Lock 10: local out/ only
OUT_HTML = OUT_DIR / "founder_roi_digest.html"
OUT_MD = OUT_DIR / "founder_roi_digest.md"

BANNER_TEXT = "DO NOT PUSH — not for public hosting (advisory founder digest, sandbox receipts)"
WATERMARK = "DERIVED — advisory, not a guaranteed claim"
WEEKLY_STALENESS_DAYS = 7                               # weekly digest: sources older than a week -> STALE

# Counters that MUST be zero under the Phase-2 no-live contract (asserted + rendered).
ZERO_INVARIANT_COUNTERS = [
    "external_sends", "forms_submitted", "deploys", "merges",
    "authority_changes", "estimated_cost_usd",
]


def _repo_root() -> Path:
    # sg-sandbox root: catalog/builds/DX-8 -> up 3.
    return HERE.parents[2]


def _receipts_dir() -> Path:
    return _repo_root() / "receipts" / "p0pgr"


DEFAULT_QUEUE = _receipts_dir() / "phase2_queue_v1.json"
DEFAULT_SCORECARD = _receipts_dir() / "phase2_scorecard_v1.json"
DEFAULT_EXEC = _receipts_dir() / "P0PGR-EXEC-M03-20260708T1330Z.json"


# ---------------------------------------------------------------------------- utils
def _e(s) -> str:
    return html.escape(str(s), quote=True)


def _parse_ts(s: str | None) -> datetime | None:
    if not s or not isinstance(s, str):
        return None
    txt = s.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(txt)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _freshness(ts: datetime | None, as_of: datetime, max_age_days: int = WEEKLY_STALENESS_DAYS) -> dict:
    if ts is None:
        return {"badge": "UNKNOWN", "age_days": None}
    age = (as_of - ts).total_seconds() / 86400.0
    badge = "STALE" if age > max_age_days else "FRESH"
    return {"badge": badge, "age_days": round(age, 2)}


# ---------------------------------------------------------------------------- model
def build_model(queue: dict, scorecard: dict, exec_receipt: dict, as_of: str | None = None) -> dict:
    """Pure transform: three loaded receipts -> a deterministic digest model."""
    q_ts = _parse_ts(queue.get("generated_at"))
    s_ts = _parse_ts(scorecard.get("updated_at"))
    e_ts = _parse_ts(exec_receipt.get("executed_at"))

    # deterministic as_of: latest source timestamp unless overridden
    if as_of is not None:
        as_of_dt = _parse_ts(as_of) or datetime.now(timezone.utc)
    else:
        candidates = [t for t in (q_ts, s_ts, e_ts) if t is not None]
        as_of_dt = max(candidates) if candidates else datetime.now(timezone.utc)

    sources = [
        {"name": "phase2_queue", "path": "receipts/p0pgr/phase2_queue_v1.json",
         "timestamp": queue.get("generated_at"), **_freshness(q_ts, as_of_dt)},
        {"name": "phase2_scorecard", "path": "receipts/p0pgr/phase2_scorecard_v1.json",
         "timestamp": scorecard.get("updated_at"), **_freshness(s_ts, as_of_dt)},
        {"name": "exec_M03", "path": "receipts/p0pgr/P0PGR-EXEC-M03-20260708T1330Z.json",
         "timestamp": exec_receipt.get("executed_at"), **_freshness(e_ts, as_of_dt)},
    ]

    ranked = []
    for i, mv in enumerate(queue.get("ranked_queue", []), start=1):
        ranked.append({
            "rank": i,
            "move_id": mv.get("move_id"),
            "packet_id": mv.get("packet_id"),
            "score": mv.get("phase2_score"),
            "commercial": bool(mv.get("value_class_commercial")),
            "route_decision": mv.get("route_decision"),
            "rationale": mv.get("rationale", ""),
        })

    executed = []
    for ex in scorecard.get("executions", []):
        executed.append({
            "move_id": ex.get("move_id"),
            "what": ex.get("what", ""),
            "quality_state": ex.get("quality_state"),
            "cost_usd": ex.get("cost_usd"),
            "receipt": ex.get("receipt"),
            "findings": ex.get("findings", []),
        })

    findings = [
        {"id": f.get("id"), "class": f.get("class"),
         "detail": f.get("detail", ""), "next_pointer": f.get("next_pointer", "")}
        for f in exec_receipt.get("findings_requiring_founder_eyes", [])
    ]
    candidate_packets = list(scorecard.get("new_candidate_packets_from_findings", []))

    held = [
        {"move_id": h.get("move_id"), "packet_id": h.get("packet_id"),
         "status": h.get("status"), "reason": h.get("reason", "")}
        for h in queue.get("held_items", [])
    ]

    raw_counters = scorecard.get("counters", {})
    counters, invariant_ok, invariant_breaches, invariant_unknown = _counter_status(raw_counters)

    next_in_queue = scorecard.get("next_in_queue", {})

    return {
        "as_of": as_of_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "operating_mode": queue.get("operating_mode") or scorecard.get("operating_mode", ""),
        "weights": queue.get("weights", {}),
        "sources": sources,
        "ranked_moves": ranked,
        "queue_order": [f"{r['move_id']}:{r['score']}" for r in ranked],
        "executed": executed,
        "findings": findings,
        "candidate_packets": candidate_packets,
        "held": held,
        "counters": counters,
        "invariant_ok": invariant_ok,
        "invariant_breaches": invariant_breaches,
        "invariant_unknown": invariant_unknown,
        "next_in_queue": next_in_queue,
    }


def _counter_status(raw: dict):
    """Render every counter with an explicit status badge.

    Zero-invariant counters: present-and-zero -> OK; present-and-nonzero -> BREACH;
    absent -> UNPOPULATED (invariant UNKNOWN, never silently read as an all-clear 0).
    """
    rows = []
    breaches, unknown = [], []
    zero_set = set(ZERO_INVARIANT_COUNTERS)
    # preserve source order, then any zero-invariant keys that were absent
    keys = list(raw.keys())
    for k in ZERO_INVARIANT_COUNTERS:
        if k not in raw and k not in keys:
            keys.append(k)
    for k in keys:
        present = k in raw
        val = raw.get(k)
        if k in zero_set:
            if not present:
                badge = "UNPOPULATED"
                unknown.append(k)
            elif val in (0, 0.0):
                badge = "OK"
            else:
                badge = "BREACH"
                breaches.append(k)
        else:
            badge = "INFO" if present else "UNPOPULATED"
            if not present:
                unknown.append(k)
        rows.append({"name": k, "value": (val if present else None),
                     "present": present, "invariant": k in zero_set, "badge": badge})
    invariant_ok = (not breaches) and (not unknown)
    return rows, invariant_ok, breaches, unknown


def assert_invariants(model: dict) -> None:
    """Fail loudly if the no-send / no-deploy contract is not provably held.

    Requires every zero-invariant counter to be present AND exactly zero. An absent
    (UNPOPULATED) counter is NOT treated as zero — it fails the assertion.
    """
    if model["invariant_breaches"]:
        raise AssertionError(f"NO-SEND/NO-DEPLOY invariant BREACHED: {model['invariant_breaches']}")
    if model["invariant_unknown"]:
        raise AssertionError(f"counters UNPOPULATED (cannot assert all-zero): {model['invariant_unknown']}")
    assert model["invariant_ok"] is True


# ---------------------------------------------------------------------------- render: markdown
def render_markdown(model: dict) -> str:
    L = []
    L.append(f"<!-- {BANNER_TEXT} -->")
    L.append("# Weekly Founder ROI Digest — DX-8")
    L.append("")
    L.append(f"> **{BANNER_TEXT}**")
    L.append("")
    L.append(f"- **As of:** {model['as_of']}  ·  origin=sandbox-advisory · authority=none · pass_claimed=false")
    L.append(f"- **Operating mode:** {model['operating_mode']}")
    L.append(f"- _{WATERMARK} — figures are read from repo receipts; this digest asserts, it does not promise._")
    L.append("")

    L.append("## Source freshness")
    L.append("")
    L.append("| Source | Timestamp | Age (days) | Badge |")
    L.append("|---|---|---|---|")
    for s in model["sources"]:
        age = "—" if s["age_days"] is None else s["age_days"]
        L.append(f"| `{s['path']}` | {s['timestamp']} | {age} | {s['badge']} |")
    L.append("")

    L.append("## Running counters — NO-SEND / NO-DEPLOY invariant")
    L.append("")
    inv = "HELD (all zero)" if model["invariant_ok"] else "**BREACH / UNKNOWN**"
    L.append(f"**Invariant status: {inv}**")
    if model["invariant_breaches"]:
        L.append(f"- BREACH: {', '.join(model['invariant_breaches'])}")
    if model["invariant_unknown"]:
        L.append(f"- UNPOPULATED (not all-clear): {', '.join(model['invariant_unknown'])}")
    L.append("")
    L.append("| Counter | Value | Status |")
    L.append("|---|---|---|")
    for c in model["counters"]:
        v = "UNPOPULATED" if not c["present"] else c["value"]
        L.append(f"| {c['name']} | {v} | {c['badge']} |")
    L.append("")

    L.append("## Ranked moves (ROI queue)")
    L.append("")
    L.append(f"_Weights: {json.dumps(model['weights'])}_")
    L.append("")
    L.append("| # | Move | Packet | Score | Commercial | Route | Rationale |")
    L.append("|---|---|---|---|---|---|---|")
    for r in model["ranked_moves"]:
        L.append(f"| {r['rank']} | {r['move_id']} | {r['packet_id']} | {r['score']} | "
                 f"{'yes' if r['commercial'] else 'no'} | {r['route_decision']} | {r['rationale']} |")
    L.append("")

    L.append("## Executed candidates")
    L.append("")
    for ex in model["executed"]:
        L.append(f"- **{ex['move_id']}** — {ex['what']}  ·  quality: `{ex['quality_state']}`  ·  cost: ${ex['cost_usd']}")
        for f in ex.get("findings", []):
            L.append(f"    - {f}")
        if ex.get("receipt"):
            L.append(f"    - receipt: `{ex['receipt']}`")
    L.append("")

    L.append("## Findings needing founder eyes")
    L.append("")
    if not model["findings"]:
        L.append("_None recorded._")
    for f in model["findings"]:
        L.append(f"- **{f['id']} [{f['class']}]** — {f['detail']}")
        if f["next_pointer"]:
            L.append(f"    - next: {f['next_pointer']}")
    if model["candidate_packets"]:
        L.append("")
        L.append("**Candidate follow-up packets:**")
        for p in model["candidate_packets"]:
            L.append(f"- {p}")
    L.append("")

    L.append("## Held items")
    L.append("")
    if not model["held"]:
        L.append("_None held._")
    for h in model["held"]:
        L.append(f"- **{h['move_id']}** ({h['packet_id']}) — `{h['status']}` — {h['reason']}")
    L.append("")

    nxt = model["next_in_queue"]
    if nxt:
        L.append("## Next in queue")
        L.append("")
        L.append(f"- **{nxt.get('move_id')}** ({nxt.get('packet_id')}) — {nxt.get('what','')}")
        if nxt.get("gates"):
            L.append(f"    - gates: {nxt['gates']}")
        L.append("")

    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------- render: html
def _badge_span(badge: str) -> str:
    cls = {
        "FRESH": "b-ok", "OK": "b-ok", "HELD": "b-ok",
        "STALE": "b-warn", "INFO": "b-info", "UNKNOWN": "b-warn",
        "UNPOPULATED": "b-warn", "BREACH": "b-bad",
    }.get(badge, "b-info")
    return f'<span class="badge {cls}">{_e(badge)}</span>'


def _sources_rows(model: dict) -> str:
    out = []
    for s in model["sources"]:
        age = "—" if s["age_days"] is None else s["age_days"]
        out.append(f"<tr><td><code>{_e(s['path'])}</code></td><td>{_e(s['timestamp'])}</td>"
                   f"<td>{_e(age)}</td><td>{_badge_span(s['badge'])}</td></tr>")
    return "\n".join(out)


def _counter_rows(model: dict) -> str:
    out = []
    for c in model["counters"]:
        v = "UNPOPULATED" if not c["present"] else c["value"]
        inv = "invariant" if c["invariant"] else ""
        out.append(f'<tr class="{inv}"><td>{_e(c["name"])}</td><td>{_e(v)}</td>'
                   f"<td>{_badge_span(c['badge'])}</td></tr>")
    return "\n".join(out)


def _ranked_rows(model: dict) -> str:
    out = []
    for r in model["ranked_moves"]:
        comm = '<span class="badge b-info">commercial</span>' if r["commercial"] else ""
        out.append(
            f"<tr><td>{r['rank']}</td><td><b>{_e(r['move_id'])}</b></td><td>{_e(r['packet_id'])}</td>"
            f"<td>{_e(r['score'])}</td><td>{comm}</td><td>{_e(r['route_decision'])}</td>"
            f"<td>{_e(r['rationale'])}</td></tr>"
        )
    return "\n".join(out)


def _executed_html(model: dict) -> str:
    out = []
    for ex in model["executed"]:
        qs = _e(ex["quality_state"])
        fl = "".join(f"<li>{_e(x)}</li>" for x in ex.get("findings", []))
        rec = f'<div class="muted">receipt: <code>{_e(ex["receipt"])}</code></div>' if ex.get("receipt") else ""
        out.append(
            f'<div class="card"><div class="card-h"><b>{_e(ex["move_id"])}</b>'
            f'<span class="pill">{qs}</span><span class="pill">cost ${_e(ex["cost_usd"])}</span></div>'
            f'<div>{_e(ex["what"])}</div>'
            f'{("<ul>" + fl + "</ul>") if fl else ""}{rec}</div>'
        )
    return "\n".join(out)


def _findings_html(model: dict) -> str:
    if not model["findings"]:
        return '<p class="muted">None recorded.</p>'
    out = []
    for f in model["findings"]:
        nxt = f'<div class="muted">next: {_e(f["next_pointer"])}</div>' if f["next_pointer"] else ""
        out.append(
            f'<div class="card"><div class="card-h"><b>{_e(f["id"])}</b>'
            f'<span class="badge b-warn">{_e(f["class"])}</span></div>'
            f'<div>{_e(f["detail"])}</div>{nxt}</div>'
        )
    if model["candidate_packets"]:
        items = "".join(f"<li>{_e(p)}</li>" for p in model["candidate_packets"])
        out.append(f'<div class="card"><b>Candidate follow-up packets</b><ul>{items}</ul></div>')
    return "\n".join(out)


def _held_html(model: dict) -> str:
    if not model["held"]:
        return '<p class="muted">None held.</p>'
    out = []
    for h in model["held"]:
        out.append(
            f'<div class="card"><div class="card-h"><b>{_e(h["move_id"])}</b>'
            f'<span class="badge b-warn">{_e(h["status"])}</span>'
            f'<span class="muted">{_e(h["packet_id"])}</span></div>'
            f'<div>{_e(h["reason"])}</div></div>'
        )
    return "\n".join(out)


def render_html(model: dict, template: str | None = None) -> str:
    if template is None:
        template = TEMPLATE_PATH.read_text(encoding="utf-8")
    nxt = model["next_in_queue"]
    next_html = ""
    if nxt:
        gates = f'<div class="muted">gates: {_e(nxt.get("gates",""))}</div>' if nxt.get("gates") else ""
        next_html = (f'<div class="card"><div class="card-h"><b>{_e(nxt.get("move_id"))}</b>'
                     f'<span class="muted">{_e(nxt.get("packet_id"))}</span></div>'
                     f'<div>{_e(nxt.get("what",""))}</div>{gates}</div>')

    inv_ok = model["invariant_ok"]
    inv_class = "b-ok" if inv_ok else "b-bad"
    inv_label = "HELD — all send/deploy/cost counters zero" if inv_ok else "BREACH / UNKNOWN — see counters"
    inv_note = ""
    if model["invariant_breaches"]:
        inv_note += f'<div class="muted">BREACH: {_e(", ".join(model["invariant_breaches"]))}</div>'
    if model["invariant_unknown"]:
        inv_note += f'<div class="muted">UNPOPULATED (not all-clear): {_e(", ".join(model["invariant_unknown"]))}</div>'

    repl = {
        "__BANNER_TEXT__": _e(BANNER_TEXT),
        "__WATERMARK__": _e(WATERMARK),
        "__AS_OF__": _e(model["as_of"]),
        "__OPERATING_MODE__": _e(model["operating_mode"]),
        "__WEIGHTS__": _e(json.dumps(model["weights"])),
        "__SOURCE_ROWS__": _sources_rows(model),
        "__INV_CLASS__": inv_class,
        "__INV_LABEL__": _e(inv_label),
        "__INV_NOTE__": inv_note,
        "__COUNTER_ROWS__": _counter_rows(model),
        "__RANKED_ROWS__": _ranked_rows(model),
        "__EXECUTED__": _executed_html(model),
        "__FINDINGS__": _findings_html(model),
        "__HELD__": _held_html(model),
        "__NEXT__": next_html,
    }
    out = template
    for k, v in repl.items():
        out = out.replace(k, v)
    return out


# ---------------------------------------------------------------------------- build
def load_sources(queue_path=DEFAULT_QUEUE, scorecard_path=DEFAULT_SCORECARD, exec_path=DEFAULT_EXEC):
    return (
        json.loads(Path(queue_path).read_text(encoding="utf-8")),
        json.loads(Path(scorecard_path).read_text(encoding="utf-8")),
        json.loads(Path(exec_path).read_text(encoding="utf-8")),
    )


def build(out_dir: Path = OUT_DIR, as_of: str | None = None, enforce: bool = True) -> dict:
    queue, scorecard, exec_receipt = load_sources()
    model = build_model(queue, scorecard, exec_receipt, as_of=as_of)
    if enforce:
        assert_invariants(model)                        # assert the send/deploy zero contract
    out_dir.mkdir(parents=True, exist_ok=True)          # Lock 10: local out/ only
    (out_dir / "founder_roi_digest.md").write_text(render_markdown(model), encoding="utf-8")
    (out_dir / "founder_roi_digest.html").write_text(render_html(model), encoding="utf-8")
    return model


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    ap.add_argument("--as-of", type=str, default=None, help="override as_of (ISO8601) to exercise STALE badges")
    ap.add_argument("--no-enforce", action="store_true", help="render even if the zero-invariant is breached")
    args = ap.parse_args(argv)

    model = build(args.out_dir, as_of=args.as_of, enforce=not args.no_enforce)
    print(f"DX-8 rendered -> {args.out_dir / 'founder_roi_digest.md'}")
    print(f"DX-8 rendered -> {args.out_dir / 'founder_roi_digest.html'}")
    print(f"  as_of={model['as_of']}  ranked={len(model['ranked_moves'])}  "
          f"executed={len(model['executed'])}  findings={len(model['findings'])}  held={len(model['held'])}")
    print(f"  NO-SEND/NO-DEPLOY invariant: {'HELD (all zero)' if model['invariant_ok'] else 'BREACH/UNKNOWN'}")
    return 0 if model["invariant_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
