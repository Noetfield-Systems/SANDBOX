#!/usr/bin/env python3
"""
DX-6 — State-surface index dashboard for onboarding  (catalog build B4 · DX-6)

Renders ONE self-contained, brand-neutral, theme-aware static HTML index of the
governance automation surface, for onboarding a new operator/agent. It reads three
on-disk sources (all read-only):

  * data/github_automation_registry_v1.json ...... motors[] + agent_lanes[] (the surface map)
  * receipts/p0pgr/phase2_scorecard_v1.json ...... dispatch mode / executions / counters
  * newest receipts/p0pgr/evidence/evidence-*.json  loop census value-class counts + freshness

What it shows: every registered motor and agent lane, the lanes they occupy, and the
loop census value-class counts (GUARD / META / NONE / REVENUE). Freshness badges age
each source against the render date; empty/missing fields render an explicit UNPOPULATED
badge (EMPTY-SINK / STUB) and are NEVER shown as 0/blank that reads all-clear.

Deliverable guards (Lock 10 / B4):
  * output written only to a local out/ path with a visible "DO NOT PUSH" banner.
  * autonomy fields (autonomous_promote, ...) render LOCKED / proof-gated, never "available".
  * no autonomy or guaranteed-outcome claim; computed rollups carry a SYNTHETIC/ADVISORY watermark.

Red-capable proof (data-driven, see test_dx6_state_surface_index.py): the rendered motor-row
count is pinned to the registry motor count, and an empty census sink must render UNPOPULATED
(not 0). Mutating the registry (drop/add a motor) or the census (blank the counts) flips those
assertions — the test is not green-by-construction.

    python3 dx6_state_surface_index.py            # render out/state_surface_index.html
    python3 dx6_state_surface_index.py --out X     # custom output path
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
TEMPLATE_PATH = HERE / "index_template.html"
OUT_DIR = HERE / "out"                                  # Lock 10: local out/, never a hosting path
OUT_HTML = OUT_DIR / "state_surface_index.html"

BANNER_TEXT = "DO NOT PUSH — not for public hosting (onboarding index, read-only advisory snapshot)"
FOOTER_NOTE = (
    "This page is a read-only index of the automation registry and receipts as they existed "
    "on disk at render time. It is a map for onboarding, not a health verdict. It makes no "
    "autonomy promise and no guaranteed-outcome claim; freshness and UNPOPULATED badges mark "
    "where a source is stale or did not carry a field."
)
STALE_DAYS = 3          # a source older than this renders STALE
VALUE_CLASSES = ["GUARD", "META", "NONE", "REVENUE"]     # census value-classes, fixed order


# ----- repo layout / loaders -------------------------------------------------

def _repo_root() -> Path:
    # sg-sandbox root: catalog/builds/DX-6 -> up 3.
    return HERE.parents[2]


def default_sources() -> dict:
    root = _repo_root()
    return {
        "registry": root / "data" / "github_automation_registry_v1.json",
        "scorecard": root / "receipts" / "p0pgr" / "phase2_scorecard_v1.json",
        "evidence_dir": root / "receipts" / "p0pgr" / "evidence",
    }


def newest_evidence(evidence_dir: Path) -> Path | None:
    cands = sorted(evidence_dir.glob("evidence-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return cands[0] if cands else None


def load_inputs(sources: dict | None = None) -> dict:
    """Load the three inputs. Missing files degrade to empty dicts so the page renders
    UNPOPULATED rather than crashing — an onboarding index must survive an empty sink."""
    src = sources or default_sources()
    registry = _read_json(src["registry"])
    scorecard = _read_json(src["scorecard"])
    ev_path = newest_evidence(Path(src["evidence_dir"])) if src.get("evidence_dir") else None
    evidence = _read_json(ev_path) if ev_path else {}
    return {"registry": registry, "scorecard": scorecard, "evidence": evidence,
            "evidence_file": ev_path.name if ev_path else None}


def _read_json(path) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, TypeError, ValueError):
        return {}


# ----- helpers ---------------------------------------------------------------

def _e(s) -> str:
    return html.escape(str(s), quote=True)


def _parse_stamp(s: str | None) -> datetime | None:
    if not s:
        return None
    txt = str(s).strip()
    # ISO with trailing Z
    try:
        return datetime.fromisoformat(txt.replace("Z", "+00:00"))
    except ValueError:
        pass
    # compact stamp embedded in a filename, e.g. workflow-census-20260706T093358Z.json
    m = re.search(r"(\d{8})T(\d{6})Z", txt)
    if m:
        try:
            return datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    m = re.search(r"(\d{8})", txt)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y%m%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def freshness_badge(stamp: str | None, now: datetime) -> tuple[str, str, str]:
    """Return (label, css_class, age_text). Missing/unparseable -> UNPOPULATED."""
    dt = _parse_stamp(stamp)
    if dt is None:
        return ("UNPOPULATED", "unpop", "—")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    age = now - dt
    days = age.total_seconds() / 86400.0
    age_text = f"{int(days)}d" if days >= 1 else f"{int(age.total_seconds()//3600)}h"
    cls = "stale" if days > STALE_DAYS else "fresh"
    return ("STALE" if cls == "stale" else "FRESH", cls, age_text)


# ----- section builders ------------------------------------------------------

def _source_rows(inp: dict, now: datetime) -> str:
    reg = inp["registry"]
    sc = inp["scorecard"]
    ev = inp["evidence"]
    rows = []
    for label, stamp in [
        ("automation registry", reg.get("saved_at")),
        ("dispatch scorecard", sc.get("updated_at")),
        ("evidence bundle", ev.get("generated_at")),
        ("census file", (ev.get("census") or {}).get("file")),
    ]:
        lbl, cls, age = freshness_badge(stamp, now)
        stamp_txt = _e(stamp) if stamp else '<span class="badge unpop">UNPOPULATED</span>'
        rows.append(
            f'<tr><td>{_e(label)}</td><td>{stamp_txt}</td><td>{_e(age)}</td>'
            f'<td><span class="badge {cls}">{lbl}</span></td></tr>'
        )
    return "\n        ".join(rows)


def _census_cards(ev: dict) -> tuple[str, str, dict]:
    """Return (cards_html, reconciliation_note, meta). Empty/missing counts -> UNPOPULATED card."""
    census = ev.get("census") or {}
    counts = census.get("counts") or {}
    meta = {
        "audit_status": census.get("audit_status"),
        "file": census.get("file"),
        "flag_count": census.get("flag_count"),
        "loop_count": census.get("loop_count"),
        "counts": counts,
    }
    if not counts:
        # EMPTY-SINK: render an explicit UNPOPULATED card, never four zero cards.
        card = ('<div class="cc unpop"><span class="cc-num">UNPOPULATED</span>'
                '<span class="cc-lbl">census value-classes — no counts in source</span></div>')
        return card, "Census counts absent from the newest evidence bundle (EMPTY-SINK).", meta

    cards = []
    for vc in VALUE_CLASSES:
        if vc in counts:
            cards.append(
                f'<div class="cc {vc.lower()}"><span class="cc-num">{int(counts[vc])}</span>'
                f'<span class="cc-lbl">{_e(vc)}</span></div>'
            )
        else:
            cards.append(
                f'<div class="cc unpop"><span class="cc-num">UNPOPULATED</span>'
                f'<span class="cc-lbl">{_e(vc)} — not in source</span></div>'
            )
    # any value-classes present beyond the known set
    for vc in counts:
        if vc not in VALUE_CLASSES:
            cards.append(
                f'<div class="cc meta"><span class="cc-num">{int(counts[vc])}</span>'
                f'<span class="cc-lbl">{_e(vc)}</span></div>'
            )

    summed = sum(int(v) for v in counts.values())
    loop_count = meta["loop_count"]
    if loop_count is None:
        recon = f"Value-class counts sum to {summed}; declared loop_count is UNPOPULATED."
    elif int(loop_count) == summed:
        recon = f"Value-class counts sum to {summed}, matching declared loop_count {int(loop_count)}."
    else:
        recon = (f"MISMATCH — value-class counts sum to {summed} but declared loop_count is "
                 f"{int(loop_count)} (possible STALE / partial census).")
    return "\n      ".join(cards), recon, meta


def _autonomy_badge(motor: dict) -> str:
    """Autonomy is ALWAYS gated: any autonomy field renders LOCKED / proof-gated, never 'available'."""
    keys = [k for k in ("autonomous_promote", "autonomy", "auto_deploy") if motor.get(k)]
    if keys:
        cond = _e(motor.get("autonomous_promote") or motor.get("autonomy") or motor.get("auto_deploy"))
        return f'<span class="badge locked" title="{cond}">LOCKED / proof-gated</span>'
    return '<span class="badge locked">LOCKED</span>'


def _motor_rows(reg: dict) -> str:
    motors = reg.get("motors") or []
    if not motors:
        return ('<tr><td colspan="8"><span class="badge unpop">UNPOPULATED</span> '
                'no motors registered in source</td></tr>')
    rows = []
    for m in motors:
        status = (m.get("status") or "").upper()
        if status == "SUPERSEDED":
            state = '<span class="badge superseded">SUPERSEDED</span>'
        elif status:
            state = f'<span class="badge">{_e(status)}</span>'
        else:
            state = '<span class="badge fresh">ACTIVE</span>'
        owns = m.get("owns") or []
        owns_txt = ", ".join(_e(o) for o in owns) if owns else '<span class="badge unpop">UNPOPULATED</span>'
        lane = m.get("lane") or '<span class="badge unpop">UNPOPULATED</span>'
        cadence = m.get("cadence") or '<span class="badge unpop">UNPOPULATED</span>'
        rows.append(
            f'<tr data-motor-row="{_e(m.get("motor_id",""))}">'
            f'<td><code>{_e(m.get("motor_id","?"))}</code></td>'
            f'<td>{_e(m.get("kind","?"))}</td>'
            f'<td>{_e(m.get("repo","?"))}</td>'
            f'<td>{lane}</td>'
            f'<td><code>{cadence}</code></td>'
            f'<td>{owns_txt}</td>'
            f'<td>{_autonomy_badge(m)}</td>'
            f'<td>{state}</td></tr>'
        )
    return "\n        ".join(rows)


def _agent_rows(reg: dict) -> str:
    agents = reg.get("agent_lanes") or []
    if not agents:
        return ('<tr><td colspan="5"><span class="badge unpop">UNPOPULATED</span> '
                'no agent lanes in source</td></tr>')
    rows = []
    for a in agents:
        owns = a.get("owns") or []
        owns_txt = ", ".join(_e(o) for o in owns) if owns else '<span class="badge unpop">UNPOPULATED</span>'
        rows.append(
            f'<tr data-agent-row="{_e(a.get("agent_id",""))}">'
            f'<td><code>{_e(a.get("agent_id","?"))}</code></td>'
            f'<td>{_e(a.get("kind","?"))}</td>'
            f'<td>{_e(a.get("repo","?"))}</td>'
            f'<td>{_e(a.get("lane","?"))}</td>'
            f'<td>{owns_txt}</td></tr>'
        )
    return "\n        ".join(rows)


def _motor_lanes(reg: dict) -> list[str]:
    return sorted({m.get("lane") for m in (reg.get("motors") or []) if m.get("lane")})


def _scorecard_block(sc: dict) -> str:
    if not sc:
        return '<p><span class="badge unpop">UNPOPULATED</span> no scorecard on disk.</p>'
    queue = sc.get("queue_order") or []
    execs = sc.get("executions") or []
    counters = sc.get("counters") or {}
    chips = "".join(f'<span class="lane-chip">{_e(q)}</span>' for q in queue) or \
        '<span class="badge unpop">UNPOPULATED</span>'
    exec_rows = []
    for x in execs:
        qs = (x.get("quality_state") or "UNPOPULATED")
        qcls = {"PASS": "fresh", "PARTIAL": "stale", "FAIL": "red"}.get(qs, "unpop")
        exec_rows.append(
            f'<tr><td><code>{_e(x.get("move_id","?"))}</code></td>'
            f'<td>{_e(x.get("what","?"))}</td>'
            f'<td><span class="badge {qcls}">{_e(qs)}</span></td></tr>'
        )
    exec_tbl = ("\n          ".join(exec_rows)
                or '<tr><td colspan="3"><span class="badge unpop">UNPOPULATED</span></td></tr>')
    ctr_txt = " &middot; ".join(
        f"{_e(k)}: {_e(v)}" for k, v in counters.items()
    ) if counters else '<span class="badge unpop">UNPOPULATED</span>'
    return f"""<p class="note">Ranked queue:</p><div>{chips}</div>
    <div class="tbl-scroll"><table class="tbl"><thead><tr><th>Move</th><th>What</th><th>Quality</th></tr></thead>
      <tbody>{exec_tbl}</tbody></table></div>
    <p class="note">Counters &middot; {ctr_txt}</p>"""


# ----- render ----------------------------------------------------------------

def render(inp: dict, now: datetime | None = None, template: str | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    if template is None:
        template = TEMPLATE_PATH.read_text(encoding="utf-8")
    reg = inp["registry"]
    sc = inp["scorecard"]
    ev = inp["evidence"]

    motors = reg.get("motors") or []
    agents = reg.get("agent_lanes") or []
    lanes = _motor_lanes(reg)
    cards, recon, cmeta = _census_cards(ev)

    audit = cmeta["audit_status"]
    audit_status = audit if audit else "UNPOPULATED"
    audit_class = {"RED": "red", "GREEN": "fresh", "AMBER": "stale"}.get(str(audit).upper(), "unpop")
    cfresh_lbl, cfresh_cls, _cage = freshness_badge(cmeta["file"], now)
    sfresh_lbl, sfresh_cls, _sage = freshness_badge(sc.get("updated_at"), now)

    loop_count = cmeta["loop_count"]
    repl = {
        "__BANNER_TEXT__": _e(BANNER_TEXT),
        "__MOTOR_COUNT__": str(len(motors)) if motors else "0",
        "__AGENT_COUNT__": str(len(agents)) if agents else "0",
        "__LANE_COUNT__": str(len(lanes)) if lanes else "0",
        "__LOOP_COUNT__": str(int(loop_count)) if loop_count is not None else "—",
        "__SOURCE_ROWS__": _source_rows(inp, now),
        "__AUDIT_STATUS__": _e(audit_status),
        "__AUDIT_CLASS__": audit_class,
        "__CENSUS_FILE__": _e(cmeta["file"] or "UNPOPULATED"),
        "__CENSUS_FRESH__": cfresh_lbl,
        "__CENSUS_FRESH_CLASS__": cfresh_cls,
        "__FLAG_COUNT__": _e(cmeta["flag_count"]) if cmeta["flag_count"] is not None else "UNPOPULATED",
        "__CENSUS_CARDS__": cards,
        "__CENSUS_RECON__": _e(recon),
        "__MOTOR_ROWS__": _motor_rows(reg),
        "__AGENT_ROWS__": _agent_rows(reg),
        "__OPERATING_MODE__": _e(sc.get("operating_mode", "UNPOPULATED")),
        "__SCORECARD_FRESH__": sfresh_lbl,
        "__SCORECARD_FRESH_CLASS__": sfresh_cls,
        "__SCORECARD_BLOCK__": _scorecard_block(sc),
        "__FOOTER_NOTE__": _e(FOOTER_NOTE),
        "__GENERATED_AT__": _e(now.strftime("%Y-%m-%d %H:%MZ")),
        "__REGISTRY_VERSION__": _e(reg.get("version", "UNPOPULATED")),
    }
    out = template
    for k, v in repl.items():
        out = out.replace(k, v)
    return out


def build(out_path: Path = OUT_HTML, sources: dict | None = None, now: datetime | None = None) -> Path:
    inp = load_inputs(sources)
    html_out = render(inp, now=now)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)      # Lock 10: local out/ only
    out_path.write_text(html_out, encoding="utf-8")
    return out_path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=OUT_HTML)
    args = ap.parse_args(argv)
    inp = load_inputs()
    out = build(args.out)
    n_motors = len(inp["registry"].get("motors") or [])
    n_agents = len(inp["registry"].get("agent_lanes") or [])
    census = (inp["evidence"].get("census") or {}).get("counts") or {}
    print(f"DX-6 rendered -> {out}")
    print(f"  motors={n_motors}  agent_lanes={n_agents}  census_value_classes={census or 'UNPOPULATED'}")
    print(f"  evidence_file={inp['evidence_file'] or 'UNPOPULATED (empty sink)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
