#!/usr/bin/env python3
"""
CO-1 — "Brain Coherence Report" Tier-1 deliverable renderer  (catalog build B4 · CO-1)

The sellable-NOW Tier-1 client deliverable from the Pattern Factory brain-audit line
(SG-Canonical-Library/.../P9-PATTERN-FACTORY/brain-audit-v1.md + brain-as-a-service.md).
It renders ONE self-contained, brand-neutral, theme-aware HTML report — one scored
section per diagnostic category (the ~7 from brain-audit-v1: stack fragmentation,
definition drift, agent theater, missing receipts, dead workflows, founder overload,
missing decision-spine) plus a 0-5 scoring rubric — filled from a synthetic
sample-findings JSON.

Commercial locks baked in:
  * Lock 10 — the generated HTML carries a visible "DO NOT PUSH" banner and is written
    only to a local out/ path (never a public-hosting path).
  * Tier-3 / Tier-4 autonomy tiers are rendered LOCKED / proof-gated, never "available".
  * No autonomy or guaranteed-outcome claims — Tier-1 is diagnosis only.

Dogfood: run_language_gate() runs the repo language_gate (scan/decide, surface="public")
over the rendered HTML. The report is built so the gate does NOT return FAIL; an injected
overclaim (e.g. "100% guaranteed") is what makes the gate FAIL. That is the red-capable
proof — see test_co1_brain_coherence_report.py.

    python3 co1_brain_coherence_report.py                 # render out/brain_coherence_report.html + gate it
    python3 co1_brain_coherence_report.py --no-gate       # render only
"""
from __future__ import annotations

import argparse
import html
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE_PATH = HERE / "report_template.html"
FINDINGS_PATH = HERE / "sample_findings.json"
OUT_DIR = HERE / "out"                                   # Lock 10: local out/, never a hosting path
OUT_HTML = OUT_DIR / "brain_coherence_report.html"

BANNER_TEXT = "DO NOT PUSH — not for public hosting (Tier-1 diagnosis deliverable, sample data)"
FOOTER_NOTE = (
    "This report describes what was observed in the client's current stack on the date shown. "
    "It is a diagnosis. It makes no autonomy promise and no outcome promise. Build and managed-operation "
    "work are separate, later engagements with their own scope."
)

SCORE_VAR = {0: "var(--s0)", 1: "var(--s1)", 2: "var(--s2)", 3: "var(--s3)", 4: "var(--s4)", 5: "var(--s5)"}
OVERALL_LABELS = {0: "absent", 1: "fragmented", 2: "gaps", 3: "partial", 4: "mostly coherent", 5: "coherent"}


def _repo_root() -> Path:
    # sg-sandbox root: catalog/builds/CO-1 -> up 3.
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
    language_gate/receipts dir. Verdict vocab is advisory: CHECK_OK when the gate does not FAIL,
    CHECK_REJECTED when it FAILs.
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


def _category_section(cat: dict) -> str:
    score = int(cat["score"])
    color = SCORE_VAR[score]
    pct = int(score / 5 * 100)
    ev = "".join(f"<li>{_e(x)}</li>" for x in cat.get("evidence", []))
    return f"""  <section class="cat">
    <div class="cat-head">
      <h2>{_e(cat['name'])}</h2>
      <span class="pill" style="background:{color}">{score} / 5 &middot; {_e(OVERALL_LABELS[score])}</span>
    </div>
    <div class="bar"><span style="width:{pct}%; background:{color}"></span></div>
    <p class="observed">{_e(cat['observed'])}</p>
    <div class="evidence"><b>Observed evidence:</b><ul>{ev}</ul></div>
    <div class="step"><b>Recommended first step:</b> {_e(cat['recommended_step'])}</div>
  </section>
"""


def _rubric_rows(rubric: dict) -> str:
    rows = []
    for lvl in rubric["levels"]:
        s = int(lvl["score"])
        rows.append(
            f'<tr><td><span class="dot" style="background:{SCORE_VAR[s]}"></span>{s}</td>'
            f"<td>{_e(lvl['label'])}</td><td>{_e(lvl['meaning'])}</td></tr>"
        )
    return "\n      ".join(rows)


def render(findings: dict, template: str | None = None) -> str:
    if template is None:
        template = TEMPLATE_PATH.read_text(encoding="utf-8")
    cats = findings["categories"]
    scores = [int(c["score"]) for c in cats]
    overall = round(sum(scores) / len(scores)) if scores else 0
    sections = "".join(_category_section(c) for c in cats)

    repl = {
        "__BANNER_TEXT__": _e(BANNER_TEXT),
        "__TIER_LINE__": _e(findings.get("tier", "Tier-1 (diagnosis only)")
                            + " — diagnosis of the current stack. No autonomy or outcome promise."),
        "__CLIENT_LABEL__": _e(findings.get("client_label", "SAMPLE CLIENT")),
        "__ENGAGEMENT_DATE__": _e(findings.get("engagement_date", "")),
        "__SCOPE_NOTE__": _e(findings.get("scope_note", "")),
        "__OVERALL_SCORE__": str(overall),
        "__OVERALL_COLOR__": SCORE_VAR[overall],
        "__OVERALL_LABEL__": _e(OVERALL_LABELS[overall]),
        "__CATEGORY_SECTIONS__": sections,
        "__RUBRIC_SCALE__": _e(findings["rubric"]["scale"]),
        "__RUBRIC_ROWS__": _rubric_rows(findings["rubric"]),
        "__RUBRIC_FORMULA__": _e(findings["rubric"]["overall_formula"]),
        "__FOOTER_NOTE__": _e(FOOTER_NOTE),
    }
    out = template
    for k, v in repl.items():
        out = out.replace(k, v)
    return out


def build(out_path: Path = OUT_HTML) -> Path:
    findings = json.loads(FINDINGS_PATH.read_text(encoding="utf-8"))
    html_out = render(findings)
    out_path.parent.mkdir(parents=True, exist_ok=True)   # Lock 10: local out/ only
    out_path.write_text(html_out, encoding="utf-8")
    return out_path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=OUT_HTML)
    ap.add_argument("--no-gate", action="store_true", help="render only; skip the language-gate dogfood")
    args = ap.parse_args(argv)

    out = build(args.out)
    print(f"CO-1 rendered -> {out}")

    if args.no_gate:
        return 0

    result = run_language_gate(out.read_text(encoding="utf-8"), surface="public")
    print(f"CO-1 language_gate dogfood: gate_decision={result['gate_decision']}  verdict={result['verdict']}")
    for b in result["blockers"]:
        print(f"  [BLOCK] {b['type']}: {b['term']!r} (line {b['line']})")
    # advisory only: exit 1 iff the gate FAILed (report carried an overclaim/banned register)
    return 0 if result["verdict"] == "CHECK_OK" else 1


if __name__ == "__main__":
    sys.exit(main())
