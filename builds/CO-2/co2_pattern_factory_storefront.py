#!/usr/bin/env python3
"""
CO-2 - Pattern Factory storefront renderer  (catalog build B4 - CO-2)

Renders ONE self-contained, brand-neutral, theme-aware HTML storefront: one card per
Pattern Factory pattern (the ~7 from P9-PATTERN-FACTORY) with its commercial tier + an
indicative price band, plus the staged engagement ladder. Grounded in:
  * P9-PATTERN-FACTORY/pattern-factory-index.md  (the pattern set)
  * P10-PRODUCT-LAYERS/brain-as-a-service.md      (staged Tier-1..4 ladder)
  * P10-PRODUCT-LAYERS/agentic-cost-governance-service.md   (Tier-1 diagnostic bands)
  * P10-PRODUCT-LAYERS/operational-language-governance-audit.md (Tier-1 diagnostic bands)

Commercial locks baked in:
  * Lock 10 - the generated HTML carries a visible "DO NOT PUSH" banner and is written
    only to a local out/ path (never a public-hosting path).
  * Tier-3 / Tier-4 patterns render LOCKED / proof-gated, never "sells now" and never a
    running result. No autonomy or guaranteed-outcome claims.
  * EMPTY / STUB / UNPOPULATED pricing renders an explicit UNPOPULATED badge, never $0.
  * Every computed/indicative price band is watermarked 'SYNTHETIC - not a guaranteed claim'.

Dogfood: run_language_gate() runs the repo language_gate (scan/decide, surface="public")
over the rendered HTML. The storefront is built so the gate does NOT return FAIL; an
injected overclaim (e.g. "100% guaranteed certified") is what makes the gate FAIL. That is
the red-capable proof - see test_co2_pattern_factory_storefront.py.

    python3 co2_pattern_factory_storefront.py                 # render out/pattern_factory_storefront.html + gate it
    python3 co2_pattern_factory_storefront.py --no-gate        # render only
"""
from __future__ import annotations

import argparse
import html
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE_PATH = HERE / "storefront_template.html"
CATALOG_PATH = HERE / "patterns_catalog.json"
OUT_DIR = HERE / "out"                                   # Lock 10: local out/, never a hosting path
OUT_HTML = OUT_DIR / "pattern_factory_storefront.html"

BANNER_TEXT = "DO NOT PUSH - not for public hosting (Pattern Factory storefront, synthetic pricing)"
FOOTER_NOTE = (
    "This storefront lists Pattern Factory patterns and the staged engagement ladder. Diagnosis tiers "
    "sell now; the managed autonomy tiers stay LOCKED and proof-gated until SourceA runs 24/7 with receipts. "
    "It makes no autonomy promise and no outcome promise. Price bands are synthetic indicative ranges for "
    "layout only, not quotes."
)

SYNTHETIC_WATERMARK = "SYNTHETIC - not a guaranteed claim"

# gate_state -> (badge css class, badge label). Tier-3/4 == locked, never a "sells now" badge.
GATE_BADGE = {
    "sells_now": ("b-sell", "SELLS NOW"),
    "bounded_build": ("b-build", "BOUNDED BUILD"),
    "locked": ("b-lock", "LOCKED / proof-gated"),
}


def _repo_root() -> Path:
    # sg-sandbox root: catalog/builds/CO-2 -> up 3.
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


def _price_block(pat: dict) -> str:
    """Render the price row. UNPOPULATED (null band) -> explicit badge, never $0.
    A populated band -> band + SYNTHETIC watermark. Locked tier -> gated, no figure sold."""
    band = pat.get("price_band")
    note = pat.get("price_note", "")
    locked = pat.get("gate_state") == "locked"

    if band is None:
        # empty-sink / stub: never render as 0 or blank (reads all-clear); flag it.
        label = "UNPOPULATED" if not locked else "LOCKED - no figure offered"
        price_cls = "unpop" if not locked else "locked"
        tag = '<span class="unpop-tag">UNPOPULATED</span>' if not locked else ""
        row = (
            f'<div class="price-row"><span class="price {price_cls}">{_e(label)}</span>{tag}</div>'
        )
    else:
        # populated indicative band -> always carry the SYNTHETIC watermark
        row = (
            f'<div class="price-row"><span class="price">{_e(band)}</span>'
            f'<span class="synth-tag">{_e(SYNTHETIC_WATERMARK)}</span></div>'
        )
    src = pat.get("price_source")
    src_html = f'<div class="src">band source: {_e(src)}</div>' if src else ""
    note_html = f'<p class="price-note">{_e(note)}</p>' if note else ""
    return row + note_html + src_html


def _pattern_card(pat: dict) -> str:
    gate_state = pat["gate_state"]
    badge_cls, badge_label = GATE_BADGE[gate_state]
    gate_reason = pat.get("gate_reason")
    reason_html = f'<p class="price-note">{_e(gate_reason)}</p>' if gate_reason else ""
    return f"""    <div class="card" data-gate="{_e(gate_state)}" data-tier="{pat['tier']}">
      <div class="card-head">
        <h2>{_e(pat['name'])}</h2>
        <span class="badge {badge_cls}">{_e(badge_label)}</span>
      </div>
      <div class="tier-label">{_e(pat['tier_label'])}</div>
      <p class="what">{_e(pat['what'])}</p>
      <p class="pain"><b>Buyer pain:</b> {_e(pat['buyer_pain'])}</p>
      <p class="commercial"><b>Offer:</b> {_e(pat['commercial'])}</p>
      {_price_block(pat)}
      {reason_html}
      <p class="proof"><b>Proof / guardrail:</b> {_e(pat['proof'])}</p>
      <div class="src">source: {_e(pat['source'])}</div>
    </div>
"""


def _ladder_rung(rung: dict) -> str:
    return (
        f'<div class="rung" data-gate="{_e(rung["gate_state"])}">'
        f'<div class="tl">Tier {rung["tier"]} &middot; {_e(rung["name"])}</div>'
        f'<div class="tn">{_e(rung["note"])}</div></div>'
    )


def render(catalog: dict, template: str | None = None) -> str:
    if template is None:
        template = TEMPLATE_PATH.read_text(encoding="utf-8")
    rungs = "\n    ".join(_ladder_rung(r) for r in catalog["ladder"])
    cards = "".join(_pattern_card(p) for p in catalog["patterns"])
    repl = {
        "__BANNER_TEXT__": _e(BANNER_TEXT),
        "__STOREFRONT__": _e(catalog["storefront"]),
        "__SUBTITLE__": _e(catalog["subtitle"]),
        "__LADDER_RUNGS__": rungs,
        "__PATTERN_CARDS__": cards,
        "__PRICE_DISCLAIMER__": _e(catalog["price_disclaimer"]),
        "__FOOTER_NOTE__": _e(FOOTER_NOTE),
    }
    out = template
    for k, v in repl.items():
        out = out.replace(k, v)
    return out


def build(out_path: Path = OUT_HTML) -> Path:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    html_out = render(catalog)
    out_path.parent.mkdir(parents=True, exist_ok=True)   # Lock 10: local out/ only
    out_path.write_text(html_out, encoding="utf-8")
    return out_path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=OUT_HTML)
    ap.add_argument("--no-gate", action="store_true", help="render only; skip the language-gate dogfood")
    args = ap.parse_args(argv)

    out = build(args.out)
    print(f"CO-2 rendered -> {out}")

    if args.no_gate:
        return 0

    result = run_language_gate(out.read_text(encoding="utf-8"), surface="public")
    print(f"CO-2 language_gate dogfood: gate_decision={result['gate_decision']}  verdict={result['verdict']}")
    for b in result["blockers"]:
        print(f"  [BLOCK] {b['type']}: {b['term']!r} (line {b['line']})")
    # advisory only: exit 1 iff the gate FAILed (storefront carried an overclaim/banned register)
    return 0 if result["verdict"] == "CHECK_OK" else 1


if __name__ == "__main__":
    sys.exit(main())
