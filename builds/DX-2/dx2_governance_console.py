#!/usr/bin/env python3
"""
DX-2 — Unified Governance Console  (catalog build B4 · DX-2)

Composes the FOUR desktop auditors into ONE parent HTML console:
  1. Receipt Ledger Auditor        (Receipt-Ledger-Auditor.app  -> audit_receipt_ledger_v1.py)
  2. Registry / Motor Validator    (Registry-Motor-Validator.app -> validate_parallel_automation_governance_v1.py
                                     + audit_automation_surface_v1.py)
  3. Staleness Gate Auditor        (Staleness-Gate-Auditor.app  -> agent_read_staleness_engine_v1.py)
  4. PR-Conflict-Resolver Report   (PR-Conflict-Resolver-Report.app -> static report.html)

The first three are grounded in the DX-3 de-pinned generators under
desktop-app/*/Contents/Resources/generate.py (they resolve the repo root via DX-3's
_resolve_repo(), no hardcoded machine path).

CRITICAL — receipt safety:
  The Registry / Motor Validator's underlying audit_automation_surface_v1.py WRITES a
  receipt into the repo's tracked receipts/ dir on EVERY run. Running the generators live
  would therefore mutate a tracked directory (append-only / NO-LIVE lock) and is also a
  live repo call. So this console does NOT execute the generators. It composes READ-ONLY,
  embedded SNAPSHOTS (auditor_snapshots.json) instead — deterministic and side-effect-free.
  build() writes exactly one file, into the local out/ dir, and nothing else.

B4 deliverable guards baked in:
  * Lock 10 — the generated HTML carries a visible "DO NOT PUSH" banner and is written
    only to a local out/ path (never a public-hosting path).
  * Theme-aware (light/dark), brand-neutral, self-contained (inline CSS, no external assets).
  * Tier-3 / Tier-4 autonomy tiers render LOCKED / proof-gated, never "available".
  * EMPTY-SINK / STUB / STALE are distinguished from CLEAN: null/empty stats render an explicit
    UNPOPULATED badge and a source-freshness (SYNTHETIC / STALE) badge — never a green 0/blank.
  * Synthetic snapshot metrics are watermarked 'SYNTHETIC — not a guaranteed claim'.

Dogfood: run_language_gate() runs the repo language_gate (scan/decide, surface="public")
over the rendered HTML. The clean console does NOT FAIL; an injected overclaim ("100%
guaranteed") is what makes the gate FAIL. That is the red-capable proof — see the test.

    python3 dx2_governance_console.py               # render out/governance_console.html + gate it
    python3 dx2_governance_console.py --no-gate      # render only
"""
from __future__ import annotations

import argparse
import html
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE_PATH = HERE / "console_template.html"
SNAPSHOTS_PATH = HERE / "auditor_snapshots.json"
OUT_DIR = HERE / "out"                                   # Lock 10: local out/, never a hosting path
OUT_HTML = OUT_DIR / "governance_console.html"

BANNER_TEXT = "DO NOT PUSH — not for public hosting (local desktop console, synthetic snapshot data)"
SYNTH_WATERMARK = "SYNTHETIC — not a guaranteed claim"
FOOTER_NOTE = (
    "This console is a read-only view. It reports what four auditors observed in the snapshot shown; "
    "it runs no gate, mutates no repo, and makes no autonomy or outcome promise. Real gate runs "
    "(which write their own receipts) are separate, operator-triggered actions outside this console."
)

STATUS_BADGE = {
    "clean": ("ok", "CLEAN"),
    "findings": ("bad", "FINDINGS"),
    "unpopulated": ("unpop", "UNPOPULATED"),
}
FRESHNESS_BADGE = {
    "synthetic": ("synth", "SYNTHETIC snapshot"),
    "stale": ("warn", "STALE — source counts not captured"),
    "live": ("ok", "LIVE"),
}
TIER_STATE_BADGE = {
    "shown": ("ok", "SHOWN"),
    "locked": ("lock", "LOCKED · proof-gated"),
}


def _repo_root() -> Path:
    # sg-sandbox root: catalog/builds/DX-2 -> up 3.
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


def _badge(kind: str, text: str) -> str:
    return f'<span class="badge {kind}">{_e(text)}</span>'


def _stat_html(stat: dict) -> str:
    """Render one stat tile. A null/empty value renders UNPOPULATED, never 0/blank."""
    val = stat.get("value", None)
    lbl = _e(stat.get("label", ""))
    if val is None or val == "":
        return (f'<div class="stat"><div class="num unpop">UNPOPULATED</div>'
                f'<div class="lbl">{lbl}</div></div>')
    return f'<div class="stat"><div class="num">{_e(val)}</div><div class="lbl">{lbl}</div></div>'


def _auditor_card(a: dict) -> str:
    st_kind, st_text = STATUS_BADGE.get(a.get("status"), ("unpop", "UNKNOWN"))
    fr_kind, fr_text = FRESHNESS_BADGE.get(a.get("freshness"), ("unpop", "UNKNOWN FRESHNESS"))
    stats = "".join(_stat_html(s) for s in a.get("stats", []))
    receipt_note = ""
    if a.get("writes_receipt_when_run"):
        receipt_note = (' <span class="badge warn">writes a receipt when run '
                        '— snapshotted, not executed</span>')
    return f"""    <div class="card" data-auditor-id="{_e(a['id'])}">
      <h2>{_e(a['title'])} {_badge(st_kind, st_text)} {_badge(fr_kind, fr_text)}</h2>
      <div class="src">{_e(a.get('source_generator',''))}<br>run: {_e(a.get('source_script',''))} &middot; repo root via {_e(a.get('grounds_repo_root_via',''))}{receipt_note}</div>
      <div class="stat-row">{stats}</div>
      <div class="detail">{_e(a.get('detail',''))}</div>
    </div>
"""


def _tier_row(t: dict) -> str:
    kind, text = TIER_STATE_BADGE.get(t.get("state"), ("lock", "LOCKED"))
    return (f'    <div class="tier-row"><span class="tname">{_e(t["tier"])}</span>'
            f'{_badge(kind, text)}<span>{_e(t["name"])}</span>'
            f'<span class="tnote">— {_e(t["note"])}</span></div>\n')


def render(snap: dict, template: str | None = None) -> str:
    if template is None:
        template = TEMPLATE_PATH.read_text(encoding="utf-8")
    cards = "".join(_auditor_card(a) for a in snap["auditors"])
    tiers = "".join(_tier_row(t) for t in snap["autonomy_tiers"])
    repl = {
        "__BANNER_TEXT__": _e(BANNER_TEXT),
        "__CONSOLE_TITLE__": _e(snap.get("console_title", "Unified Governance Console")),
        "__SUBTITLE__": _e(snap.get("subtitle", "")),
        "__SYNTH_WATERMARK__": _e(SYNTH_WATERMARK),
        "__CAPTURED__": _e(snap.get("captured", "")),
        "__AUDITOR_CARDS__": cards,
        "__TIER_ROWS__": tiers,
        "__SNAPSHOT_NOTE__": _e(snap.get("snapshot_note", "")),
        "__FOOTER_NOTE__": _e(FOOTER_NOTE),
    }
    out = template
    for k, v in repl.items():
        out = out.replace(k, v)
    return out


def build(out_path: Path = OUT_HTML) -> Path:
    snap = json.loads(SNAPSHOTS_PATH.read_text(encoding="utf-8"))
    html_out = render(snap)
    out_path.parent.mkdir(parents=True, exist_ok=True)   # Lock 10: local out/ only
    out_path.write_text(html_out, encoding="utf-8")
    return out_path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=OUT_HTML)
    ap.add_argument("--no-gate", action="store_true", help="render only; skip the language-gate dogfood")
    args = ap.parse_args(argv)

    out = build(args.out)
    print(f"DX-2 rendered -> {out}")

    if args.no_gate:
        return 0

    result = run_language_gate(out.read_text(encoding="utf-8"), surface="public")
    print(f"DX-2 language_gate dogfood: gate_decision={result['gate_decision']}  verdict={result['verdict']}")
    for b in result["blockers"]:
        print(f"  [BLOCK] {b['type']}: {b['term']!r} (line {b['line']})")
    # advisory only: exit 1 iff the gate FAILed (console carried an overclaim/banned register)
    return 0 if result["verdict"] == "CHECK_OK" else 1


if __name__ == "__main__":
    sys.exit(main())
