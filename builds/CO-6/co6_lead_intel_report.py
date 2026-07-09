#!/usr/bin/env python3
"""
CO-6 — Gateway Lead-Intelligence Dashboard renderer  (catalog build B4 · CO-6)

Renders ONE self-contained, brand-neutral, theme-aware HTML dashboard that shows the
`priority_tag` breakdown (high / medium / low) over MOCK `gateway_leads` rows.

Ground:
  SG-Canonical-Library/.../P10-PRODUCT-LAYERS/SINA_GATEWAY_BLUEPRINT_LOCKED_v1.md
    §4 — deterministic priority_tag rule (high / medium / low)
    §5 — gateway_leads table schema
    §7 — v1 scope vs DEFERRED (learned scoring / admin dashboard are DEFERRED)

Data is MOCK ONLY — synthetic rows from mock_leads.json. No real leads, no PII. Every
row is an obvious placeholder. The dashboard carries:
  * Lock 10 — a visible "DO NOT PUSH — not for public hosting" banner; the HTML is written
    only to a local out/ path, never a hosting/CF/Railway/Vercel path.
  * a MOCK-DATA watermark, and every computed metric is watermarked
    "SYNTHETIC — not a guaranteed claim".
  * EMPTY-SINK / UNPOPULATED handling — a row whose priority_tag is null/empty is counted
    into an explicit UNPOPULATED bucket (NOT silently folded into 'low'/0), and null contact
    fields render an explicit UNPOPULATED badge.
  * the two DEFERRED items (learned scoring, autonomous routing) render LOCKED / proof-gated,
    never "available"; no autonomy or guaranteed-outcome claim.

Dogfood: run_language_gate() runs the repo language_gate (scan/decide, surface="public") over
the rendered HTML. The clean dashboard does NOT FAIL the gate; an injected overclaim
("100% guaranteed") is what makes the gate FAIL — the red-capable proof.

    python3 co6_lead_intel_report.py                 # render out/gateway_lead_intel.html + gate it
    python3 co6_lead_intel_report.py --no-gate       # render only
"""
from __future__ import annotations

import argparse
import html
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE_PATH = HERE / "report_template.html"
MOCK_PATH = HERE / "mock_leads.json"
OUT_DIR = HERE / "out"                                   # Lock 10: local out/, never a hosting path
OUT_HTML = OUT_DIR / "gateway_lead_intel.html"

BANNER_TEXT = "DO NOT PUSH — not for public hosting (CO-6 mock lead-intel dashboard, synthetic data)"
WATERMARK_TEXT = "MOCK DATA — synthetic gateway_leads rows, NOT real leads / NOT PII. SYNTHETIC — not a guaranteed claim."
SUBTITLE = ("Priority-tag distribution over mock gateway_leads rows. Rule-based tags per blueprint §4; "
            "schema per §5. Diagnosis of a mock capture set only — no autonomy or outcome promise.")
FOOTER_NOTE = (
    "This dashboard visualises SYNTHETIC gateway_leads rows only. Counts describe the mock dataset shown, "
    "nothing more. No row is a real person; no metric is a guaranteed claim. Learned/weighted scoring and any "
    "autonomous routing stay locked until real rows exist and their proof conditions are met (blueprint §4, §7)."
)

# Canonical priority buckets (blueprint §4). UNPOPULATED is a synthetic-freshness bucket for
# rows the tagger has not yet stamped — kept OUT of the populated shares so a stub never reads clean.
PRIORITY_ORDER = ["high", "medium", "low"]
PRIORITY_VAR = {"high": "var(--high)", "medium": "var(--medium)", "low": "var(--low)"}
UNPOPULATED = "UNPOPULATED"


def _repo_root() -> Path:
    # sg-sandbox root: catalog/builds/CO-6 -> up 3.
    return HERE.parents[2]


def _load_gate():
    """Import scan/decide/load_dictionary from the repo language_gate core (no receipt written)."""
    core = _repo_root() / "language_gate" / "language_gate_core_v1.py"
    if "language_gate_core_v1" in sys.modules:
        return sys.modules["language_gate_core_v1"]
    spec = importlib.util.spec_from_file_location("language_gate_core_v1", core)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(core.parent))
    sys.modules[spec.name] = mod          # register before exec so @dataclass can introspect
    spec.loader.exec_module(mod)
    return mod


def run_language_gate(text: str, surface: str = "public") -> dict:
    """Advisory dogfood: scan text on the given surface and decide. Returns decision + blockers.

    Uses scan/decide directly (not the pipeline) so NO receipt is written into the tracked
    language_gate/receipts dir. CHECK_OK when the gate does not FAIL, CHECK_REJECTED when it FAILs.
    """
    gate = _load_gate()
    dictionary = gate.load_dictionary()
    findings, _ = gate.scan(text, surface, dictionary, file_path=None)
    decision, blockers = gate.decide(findings)
    return {
        "origin": "sandbox-advisory",
        "authority": "none",
        "gate_decision": decision,
        "verdict": "CHECK_REJECTED" if decision == "FAIL" else "CHECK_OK",
        "blockers": [
            {"type": b.type, "term": b.term, "line": b.line, "reason": getattr(b, "reason", None)}
            for b in blockers
        ],
    }


def _e(s) -> str:
    return html.escape(str(s), quote=True)


def _norm_tag(row: dict) -> str:
    """Normalise a row's priority_tag into a canonical bucket or UNPOPULATED.

    A null / empty / whitespace / unrecognised tag is NOT coerced to 'low' — it lands in the
    explicit UNPOPULATED bucket so a stub/empty-sink row never masquerades as a clean 'low'."""
    raw = row.get("priority_tag")
    if raw is None:
        return UNPOPULATED
    v = str(raw).strip().lower()
    if v in PRIORITY_ORDER:
        return v
    return UNPOPULATED


def breakdown(rows: list[dict]) -> dict:
    """Compute the priority_tag breakdown over the given rows.

    Returns counts per canonical bucket, the UNPOPULATED count, the populated total (denominator
    for shares — excludes UNPOPULATED), and the grand total. This is the single source of truth the
    HTML and the test both read."""
    counts = Counter(_norm_tag(r) for r in rows)
    populated = sum(counts[k] for k in PRIORITY_ORDER)
    return {
        "counts": {k: counts.get(k, 0) for k in PRIORITY_ORDER},
        "unpopulated": counts.get(UNPOPULATED, 0),
        "populated_total": populated,
        "grand_total": len(rows),
    }


def _priority_cards(bd: dict) -> str:
    cards = []
    for k in PRIORITY_ORDER:
        n = bd["counts"][k]
        pop = bd["populated_total"]
        pct = round(n / pop * 100) if pop else 0
        cards.append(
            f'<div class="card"><div class="n" style="color:{PRIORITY_VAR[k]}">{n}</div>'
            f'<div class="k"><span class="dot" style="background:{PRIORITY_VAR[k]}"></span>{_e(k)}</div>'
            f'<div class="p">{pct}% of populated</div></div>'
        )
    cards.append(
        f'<div class="card"><div class="n" style="color:var(--unpop)">{bd["unpopulated"]}</div>'
        f'<div class="k"><span class="dot" style="background:var(--unpop)"></span>unpopulated</div>'
        f'<div class="p">tag not yet stamped</div></div>'
    )
    return "".join(cards)


def _breakdown_rows(bd: dict) -> str:
    rows = []
    pop = bd["populated_total"]
    for k in PRIORITY_ORDER:
        n = bd["counts"][k]
        pct = round(n / pop * 100) if pop else 0
        rows.append(
            f'<tr><td><span class="dot" style="background:{PRIORITY_VAR[k]}"></span>{_e(k)}</td>'
            f"<td>{n}</td><td>{pct}%</td>"
            f'<td><div class="bar"><span style="width:{pct}%; background:{PRIORITY_VAR[k]}"></span></div></td></tr>'
        )
    # UNPOPULATED row — explicit, badged, and excluded from the share denominator.
    rows.append(
        f'<tr><td><span class="badge-unpop">{UNPOPULATED}</span></td>'
        f'<td>{bd["unpopulated"]}</td><td>&mdash;</td>'
        f'<td><span class="gate-note">excluded from shares (source-freshness)</span></td></tr>'
    )
    return "\n      ".join(rows)


def _row_table(rows: list[dict]) -> str:
    out = []
    for r in rows:
        tag = _norm_tag(r)
        if tag == UNPOPULATED:
            tag_cell = f'<span class="tag tag-unpop">{UNPOPULATED}</span>'
        else:
            tag_cell = f'<span class="tag tag-{tag}">{_e(tag)}</span>'
        contact = r.get("contact")
        if contact is None or str(contact).strip() == "":
            contact_cell = '<span class="badge-unpop">UNPOPULATED</span>'
        else:
            contact_cell = _e(contact)
        out.append(
            "<tr>"
            f"<td>{_e(r.get('id',''))}</td>"
            f"<td>{_e(r.get('identity',''))}</td>"
            f"<td>{_e(r.get('intent',''))}</td>"
            f"<td>{_e(r.get('urgency',''))}</td>"
            f"<td>{_e(r.get('venture_route',''))}</td>"
            f"<td>{contact_cell}</td>"
            f"<td>{tag_cell}</td>"
            "</tr>"
        )
    return "\n        ".join(out)


def render(mock: dict, template: str | None = None) -> str:
    if template is None:
        template = TEMPLATE_PATH.read_text(encoding="utf-8")
    rows = mock["rows"]
    bd = breakdown(rows)
    pop_note = (
        f"Populated rows: {bd['populated_total']} of {bd['grand_total']} "
        f"({bd['unpopulated']} UNPOPULATED, excluded from shares). Shares are of populated rows only. "
        "SYNTHETIC — not a guaranteed claim."
    )
    repl = {
        "__BANNER_TEXT__": _e(BANNER_TEXT),
        "__WATERMARK_TEXT__": _e(WATERMARK_TEXT),
        "__SUBTITLE__": _e(SUBTITLE),
        "__TOTAL_ROWS__": str(bd["grand_total"]),
        "__PRIORITY_CARDS__": _priority_cards(bd),
        "__BREAKDOWN_ROWS__": _breakdown_rows(bd),
        "__POPULATED_NOTE__": _e(pop_note),
        "__ROW_TABLE__": _row_table(rows),
        "__FOOTER_NOTE__": _e(FOOTER_NOTE),
    }
    out = template
    for k, v in repl.items():
        out = out.replace(k, v)
    return out


def build(out_path: Path = OUT_HTML) -> Path:
    mock = json.loads(MOCK_PATH.read_text(encoding="utf-8"))
    html_out = render(mock)
    out_path.parent.mkdir(parents=True, exist_ok=True)   # Lock 10: local out/ only
    out_path.write_text(html_out, encoding="utf-8")
    return out_path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=OUT_HTML)
    ap.add_argument("--no-gate", action="store_true", help="render only; skip the language-gate dogfood")
    args = ap.parse_args(argv)

    out = build(args.out)
    print(f"CO-6 rendered -> {out}")

    mock = json.loads(MOCK_PATH.read_text(encoding="utf-8"))
    bd = breakdown(mock["rows"])
    print(f"CO-6 breakdown: high={bd['counts']['high']} medium={bd['counts']['medium']} "
          f"low={bd['counts']['low']} unpopulated={bd['unpopulated']} (of {bd['grand_total']} mock rows)")

    if args.no_gate:
        return 0

    result = run_language_gate(out.read_text(encoding="utf-8"), surface="public")
    print(f"CO-6 language_gate dogfood: gate_decision={result['gate_decision']}  verdict={result['verdict']}")
    for b in result["blockers"]:
        print(f"  [BLOCK] {b['type']}: {b['term']!r} (line {b['line']})")
    return 0 if result["verdict"] == "CHECK_OK" else 1


if __name__ == "__main__":
    sys.exit(main())
