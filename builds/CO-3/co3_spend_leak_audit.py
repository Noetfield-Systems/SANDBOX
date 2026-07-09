#!/usr/bin/env python3
"""
CO-3 — Tier-1 "AI Spend Leak Audit" scanner + report renderer  (catalog build B4 · CO-3)

The sellable-NOW Tier-1 deliverable from the Agentic Cost Governance line
(SG-Canonical-Library/.../P10-PRODUCT-LAYERS/agentic-cost-governance-SSOT.md).
It reads a SYNTHETIC token-log fixture (hardcoded, in this build dir), computes the
ROI metrics defined in that SSOT (§3 ROI METRICS) — headlined by **leak_rate**
("% spend above policy") where a cost leak is, per the SSOT vocabulary, "spend above
policy baseline WITHOUT a measured ROI signal" — and renders ONE self-contained,
brand-neutral, theme-aware HTML report into a local out/ dir.

Commercial locks baked in (B4):
  * Lock 10 — the generated HTML carries a visible "DO NOT PUSH" banner and is written
    only to a local out/ path (never a public-hosting path).
  * SYNTHETIC watermark — EVERY leak_rate (overall + per-tier) is rendered with the
    watermark 'SYNTHETIC — not a guaranteed-savings claim; customer receipt required'.
    Every other computed metric carries 'SYNTHETIC — not a guaranteed claim'.
  * Real-log firewall — the loader REFUSES to ingest anything not explicitly marked
    SYNTHETIC (data_class=="SYNTHETIC" and synthetic==true). No real token log is ever read.
  * Tier-3 (Firewall Pilot) / Tier-4 (ROI Router Advisory) render LOCKED / proof-gated,
    never "available". No autonomy or guaranteed-savings claim anywhere.
  * UNPOPULATED / source-freshness — null/blank cost fields render an explicit UNPOPULATED
    badge and are excluded from the math; they are never silently read as $0 (all-clear).

Dogfood: run_language_gate() runs the repo language_gate (scan/decide, surface="public")
over the rendered HTML. The report is built so the gate does NOT return FAIL; an injected
overclaim (e.g. "100% guaranteed") is what makes the gate FAIL — the red-capable proof.

    python3 co3_spend_leak_audit.py                 # render out/spend_leak_audit_report.html + gate it
    python3 co3_spend_leak_audit.py --no-gate       # render only
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
FIXTURE_PATH = HERE / "synthetic_token_log.json"        # hardcoded synthetic fixture — the ONLY log we read
OUT_DIR = HERE / "out"                                   # Lock 10: local out/, never a hosting path
OUT_HTML = OUT_DIR / "spend_leak_audit_report.html"

BANNER_TEXT = "DO NOT PUSH — not for public hosting (Tier-1 spend-leak audit, SYNTHETIC data)"
LEAK_WATERMARK = "SYNTHETIC — not a guaranteed-savings claim; customer receipt required"
METRIC_WATERMARK = "SYNTHETIC — not a guaranteed claim"
FOOTER_NOTE = (
    "This report describes spend observed in a SYNTHETIC token log on the date shown. It is a Tier-1 "
    "diagnosis of where spend sits above policy without a measured ROI signal. It is not a savings "
    "promise: every figure is synthetic and any real figure requires the customer's own spend ledger "
    "and receipt. The customer holds the data; enforcement (Tier-3 firewall) is a separate, later, "
    "receipt-gated engagement."
)


# --------------------------------------------------------------------------- gate dogfood
def _repo_root() -> Path:
    # sg-sandbox root: catalog/builds/CO-3 -> up 3.
    return HERE.parents[2]


def _load_gate():
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


# --------------------------------------------------------------------------- data + metrics
class RealTokenLogRefused(RuntimeError):
    """Raised when the input is not explicitly marked SYNTHETIC. CO-3 never ingests a real log."""


def assert_synthetic(log: dict) -> None:
    """Real-log firewall. Refuse anything not explicitly, doubly marked synthetic."""
    if log.get("data_class") != "SYNTHETIC" or log.get("synthetic") is not True:
        raise RealTokenLogRefused(
            "CO-3 refuses to ingest this token log: it is not marked SYNTHETIC "
            '(require data_class=="SYNTHETIC" and synthetic==true). '
            "This tool computes SYNTHETIC illustrations only; real spend requires the customer's ledger."
        )


def load_log(path: Path = FIXTURE_PATH) -> dict:
    log = json.loads(path.read_text(encoding="utf-8"))
    assert_synthetic(log)                # hard gate before any figure is computed
    return log


def _is_populated_cost(entry: dict) -> bool:
    c = entry.get("cost_usd", None)
    return isinstance(c, (int, float)) and not isinstance(c, bool)


def _is_leak(entry: dict) -> bool:
    """SSOT cost leak: spend above policy baseline WITHOUT a measured ROI signal.
    A null/false roi_signal is treated conservatively as 'no measured ROI signal'."""
    return bool(entry.get("above_policy")) and (entry.get("roi_signal") is not True)


def compute_metrics(log: dict) -> dict:
    entries = log.get("entries", [])
    populated = [e for e in entries if _is_populated_cost(e)]
    unpopulated = [e for e in entries if not _is_populated_cost(e)]

    total = sum(e["cost_usd"] for e in populated)
    leaked = sum(e["cost_usd"] for e in populated if _is_leak(e))
    leak_rate = (leaked / total * 100.0) if total else None

    def _tier(tier: str) -> dict:
        rows = [e for e in populated if e.get("model_tier") == tier]
        t = sum(e["cost_usd"] for e in rows)
        lk = sum(e["cost_usd"] for e in rows if _is_leak(e))
        return {
            "tier": tier,
            "total_spend": round(t, 2),
            "leaked_spend": round(lk, 2),
            "leak_rate": round(lk / t * 100.0, 2) if t else None,
            "count": len(rows),
        }

    tiers = [_tier("premium"), _tier("commodity")]

    successful = [e for e in populated if e.get("success") is True]
    within_policy = [e for e in populated if not e.get("above_policy")]
    premium = [e for e in populated if e.get("model_tier") == "premium"]
    premium_justified = [e for e in premium if e.get("roi_signal") is True]

    leak_targets = sorted(
        (e for e in populated if _is_leak(e)), key=lambda e: e["cost_usd"], reverse=True
    )[:5]

    return {
        "total_spend": round(total, 2),
        "leaked_spend": round(leaked, 2),
        "leak_rate": round(leak_rate, 2) if leak_rate is not None else None,          # SSOT headline
        "cost_per_successful_task": round(total / len(successful), 2) if successful else None,
        "policy_compliance_pct": round(len(within_policy) / len(populated) * 100.0, 2) if populated else None,
        "premium_justification_pct": round(len(premium_justified) / len(premium) * 100.0, 2) if premium else None,
        "entry_count": len(entries),
        "populated_count": len(populated),
        "unpopulated_count": len(unpopulated),
        "unpopulated": unpopulated,
        "tiers": tiers,
        "leak_targets": leak_targets,
    }


# --------------------------------------------------------------------------- render
def _e(s) -> str:
    return html.escape(str(s), quote=True)


def _fmt_usd(v) -> str:
    return f"${v:,.2f}" if isinstance(v, (int, float)) and not isinstance(v, bool) else "UNPOPULATED"


def _fmt_pct(v) -> str:
    return f"{v:.2f}%" if isinstance(v, (int, float)) and not isinstance(v, bool) else "UNPOPULATED"


def _leak_class(rate) -> str:
    if not isinstance(rate, (int, float)) or isinstance(rate, bool):
        return "unpop"
    if rate >= 40:
        return "hi"
    if rate >= 15:
        return "mid"
    return "lo"


def _tier_rows(m: dict) -> str:
    out = []
    for t in m["tiers"]:
        rate = t["leak_rate"]
        badge = _fmt_pct(rate)
        cls = _leak_class(rate)
        out.append(
            f'<tr><td>{_e(t["tier"])}</td>'
            f'<td>{_e(t["count"])}</td>'
            f'<td>{_fmt_usd(t["total_spend"])}</td>'
            f'<td>{_fmt_usd(t["leaked_spend"])}</td>'
            f'<td><span class="leak {cls}">{badge}</span>'
            f'<div class="wm">{_e(LEAK_WATERMARK)}</div></td></tr>'
        )
    return "\n      ".join(out)


def _leak_target_rows(m: dict) -> str:
    if not m["leak_targets"]:
        return '<tr><td colspan="5" class="muted">No leaking routes in this synthetic log.</td></tr>'
    out = []
    for e in m["leak_targets"]:
        out.append(
            f'<tr><td><code>{_e(e.get("task_id"))}</code></td>'
            f'<td>{_e(e.get("model_tier"))}</td>'
            f'<td>{_e(e.get("task_class"))}</td>'
            f'<td>{_fmt_usd(e.get("cost_usd"))}</td>'
            f'<td>above policy &middot; no ROI signal</td></tr>'
        )
    return "\n      ".join(out)


def _unpopulated_block(m: dict) -> str:
    if not m["unpopulated"]:
        return ('<p class="muted">No UNPOPULATED / empty-sink rows in this log — '
                'every entry carries a populated cost field.</p>')
    rows = "".join(
        f'<li><code>{_e(e.get("task_id", "?"))}</code> — '
        f'<span class="leak unpop">UNPOPULATED cost</span> '
        '(excluded from every figure; never read as $0)</li>'
        for e in m["unpopulated"]
    )
    return (f'<p class="muted">{m["unpopulated_count"]} of {m["entry_count"]} rows have a null/blank '
            f'cost and are shown as UNPOPULATED, not as clean $0:</p><ul class="unpop-list">{rows}</ul>')


def render(log: dict, metrics: dict | None = None, template: str | None = None) -> str:
    if template is None:
        template = TEMPLATE_PATH.read_text(encoding="utf-8")
    m = metrics if metrics is not None else compute_metrics(log)

    repl = {
        "__BANNER_TEXT__": _e(BANNER_TEXT),
        "__TIER_LINE__": _e("Tier-1 AI Spend Leak Audit — a diagnosis of where agentic spend sits "
                            "above policy without a measured ROI signal. SYNTHETIC data; no savings promise."),
        "__CLIENT_LABEL__": _e(log.get("source_label", "SYNTHETIC FIXTURE")),
        "__GENERATED_AT__": _e(log.get("generated_at", "")),
        "__SOURCE_BADGE__": _e(f'DATA SOURCE: {log.get("source_label", "SYNTHETIC")} '
                               f'(generated {log.get("generated_at", "unknown")}) — synthetic, not live'),
        "__POLICY_REF__": _e(log.get("policy_pack_ref", "")),
        "__LEAK_RATE__": _fmt_pct(m["leak_rate"]),
        "__LEAK_CLASS__": _leak_class(m["leak_rate"]),
        "__LEAK_WATERMARK__": _e(LEAK_WATERMARK),
        "__TOTAL_SPEND__": _fmt_usd(m["total_spend"]),
        "__LEAKED_SPEND__": _fmt_usd(m["leaked_spend"]),
        "__METRIC_WATERMARK__": _e(METRIC_WATERMARK),
        "__COST_PER_TASK__": _fmt_usd(m["cost_per_successful_task"]),
        "__POLICY_COMPLIANCE__": _fmt_pct(m["policy_compliance_pct"]),
        "__PREMIUM_JUSTIFICATION__": _fmt_pct(m["premium_justification_pct"]),
        "__ENTRY_COUNT__": str(m["entry_count"]),
        "__POPULATED_COUNT__": str(m["populated_count"]),
        "__TIER_ROWS__": _tier_rows(m),
        "__LEAK_TARGET_ROWS__": _leak_target_rows(m),
        "__UNPOPULATED_BLOCK__": _unpopulated_block(m),
        "__FOOTER_NOTE__": _e(FOOTER_NOTE),
    }
    out = template
    for k, v in repl.items():
        out = out.replace(k, v)
    return out


def build(out_path: Path = OUT_HTML) -> Path:
    log = load_log()
    html_out = render(log)
    out_path.parent.mkdir(parents=True, exist_ok=True)   # Lock 10: local out/ only
    out_path.write_text(html_out, encoding="utf-8")
    return out_path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=OUT_HTML)
    ap.add_argument("--no-gate", action="store_true", help="render only; skip the language-gate dogfood")
    args = ap.parse_args(argv)

    log = load_log()
    m = compute_metrics(log)
    print(f"CO-3 leak_rate = {_fmt_pct(m['leak_rate'])}  ({_fmt_usd(m['leaked_spend'])} of {_fmt_usd(m['total_spend'])})")
    print(f"          watermark: {LEAK_WATERMARK}")

    out = build(args.out)
    print(f"CO-3 rendered -> {out}")

    if args.no_gate:
        return 0

    result = run_language_gate(out.read_text(encoding="utf-8"), surface="public")
    print(f"CO-3 language_gate dogfood: gate_decision={result['gate_decision']}  verdict={result['verdict']}")
    for b in result["blockers"]:
        print(f"  [BLOCK] {b['type']}: {b['term']!r} (line {b['line']})")
    return 0 if result["verdict"] == "CHECK_OK" else 1


if __name__ == "__main__":
    sys.exit(main())
