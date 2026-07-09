#!/usr/bin/env python3
"""
CO-4a — TrustField overclaim enforcement (OFFLINE ONLY)  ·  catalog build B4 · CO-4a

A block-pattern lint engine + a dry-run REGULATORY_COPY_RISK report over a CHECKED-IN,
SYNTHETIC fixture copy of sample web text (sample_web_copy_fixture.json). It is grounded in:

  * language_gate/trustfield_dictionary_overlay_index_v1.json — the CONFLICT_PHRASE and
    REGULATORY_COPY_RISK entries (loaded read-only; these classes are NEVER allowlisted).
  * language_gate/language_gate_core_v1.py — OVERCLAIM_PATTERNS (imported verbatim) and the
    public-surface block_private posture (dictionary.private_only -> BANNED_SURFACE).

CO-4a is OFFLINE ONLY. It does NOT open or scan the live TrustField-Technologies repo and
does NOT fetch trustfield.ca. The only text it lints is the in-repo synthetic fixture.
CO-4b (live wiring) is out of scope and founder-gated.

The engine authors NO RPAA / FINTRAC / MSB / MSP / PSP status assertions. It only reports,
per fixture line, whether the copy would trip a block pattern, and of which risk class.
Every offending span is REDACTED in the rendered report, so the report itself carries no
raw overclaim string (that is why the report dogfoods clean through the language_gate).

Red-capable two ways:
  1. data-driven — a fixture line with an MSP/PSP self-claim is flagged; a clean line is not.
     Mutating a clean line into a self-claim flips its flagged status (see the test).
  2. dogfood — the rendered HTML does NOT FAIL the repo language_gate (public surface);
     injecting '100% guaranteed' into the HTML makes the same gate FAIL.

    python3 co4a_overclaim_lint_report.py               # lint fixture, render out/, dogfood the HTML
    python3 co4a_overclaim_lint_report.py --no-gate      # render only
"""
from __future__ import annotations

import argparse
import html
import importlib.util
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE_PATH = HERE / "report_template.html"
FIXTURE_PATH = HERE / "sample_web_copy_fixture.json"
OUT_DIR = HERE / "out"                                   # Lock 10: local out/, never a hosting path
OUT_HTML = OUT_DIR / "co4a_overclaim_lint_report.html"

LOCK10_BANNER = "DO NOT PUSH — not for public hosting (CO-4a offline lint, synthetic fixture)"
LINT_BANNER = "lint result, not a legal/compliance determination; publishing is founder-gated"
SYNTHETIC_WM = "SYNTHETIC — not a guaranteed claim"
LINT_ANCHOR = "lint-only advisory"                       # stable anchor for the dogfood mutation

# ---------------------------------------------------------------------------
# grounding: import OVERCLAIM_PATTERNS + gate helpers from the repo language_gate core
# ---------------------------------------------------------------------------

def _repo_root() -> Path:
    # sg-sandbox root: catalog/builds/CO-4a -> up 3.
    return HERE.parents[2]


def _load_gate():
    core = _repo_root() / "language_gate" / "language_gate_core_v1.py"
    if "language_gate_core_v1" in sys.modules:
        return sys.modules["language_gate_core_v1"]
    spec = importlib.util.spec_from_file_location("language_gate_core_v1", core)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(core.parent))
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


OVERLAY_PATH = None  # set on first engine build


# ---------------------------------------------------------------------------
# block-pattern engine
# ---------------------------------------------------------------------------
# REGULATORY_COPY_RISK regex bank — grounded in the overlay's REGULATORY_COPY_RISK
# subclasses ("MSP self-identification", "payment processing self-claim",
# "retired entity alias (partial)"). Only matches FIRST-PARTY self-claims ("we are ...",
# "we process ..."), never third-party/disclaiming copy ("your partner holds the funds").
REG_RISK_PATTERNS = [
    ("MSP_SELF_ID", r"\bwe(?:'re|\s+are)\s+(?:a|an|the|a\s+licensed|an\s+authorized|a\s+registered)?\s*(?:msp|msb|money[ -]services?[ -]business)\b", "first-party MSP/MSB self-identification"),
    ("MSP_SELF_ID", r"\bregistered\s+(?:as\s+)?(?:an?\s+)?(?:msp|msb|money[ -]services?[ -]business)\b", "claims MSP/MSB registration status"),
    ("PSP_SELF_CLAIM", r"\bwe\s+process\s+payments\b", "first-party payment-processing self-claim"),
    ("PSP_SELF_CLAIM", r"\bwe\s+are\s+a\s+(?:psp|payment\s+(?:service\s+)?provider|payment\s+processor)\b", "first-party PSP self-identification"),
    ("PSP_SELF_CLAIM", r"\bwe\s+(?:handle|settle|clear|move|hold|custody)\s+(?:the\s+|client\s+|customer\s+)?(?:funds|money|payments?|settlements?|transactions?)\b", "claims first-party control of funds/settlement"),
    ("ENTITY_ALIAS", r"\bTrustField\s+Technologies\b", "retired/entity alias — regulatory/entity confusion"),
]


class Finding:
    __slots__ = ("risk_class", "subclass", "match", "start", "end", "reason", "source")

    def __init__(self, risk_class, subclass, match, start, end, reason, source):
        self.risk_class = risk_class
        self.subclass = subclass
        self.match = match
        self.start = start
        self.end = end
        self.reason = reason
        self.source = source

    def as_dict(self):
        return {
            "risk_class": self.risk_class, "subclass": self.subclass,
            "match": self.match, "start": self.start, "end": self.end,
            "reason": self.reason, "source": self.source,
        }


def load_conflict_phrases(overlay_path: Path) -> list[tuple[str, str]]:
    """Load CONFLICT_PHRASE literal terms from the trustfield overlay index (read-only)."""
    data = json.loads(overlay_path.read_text(encoding="utf-8"))
    out = []
    for e in data.get("entries") or []:
        if e.get("class") == "CONFLICT_PHRASE" and e.get("term"):
            out.append((str(e["term"]), str(e.get("id", ""))))
    return out


def build_engine(overlay_path: Path | None = None):
    """Assemble the block-pattern bank: overlay CONFLICT_PHRASE literals + REGULATORY_COPY_RISK
    regexes + language_gate OVERCLAIM_PATTERNS + public-surface private_only (block_private)."""
    global OVERLAY_PATH
    OVERLAY_PATH = overlay_path or (_repo_root() / "language_gate" / "trustfield_dictionary_overlay_index_v1.json")
    gate = _load_gate()

    patterns = []  # (compiled, risk_class, subclass, reason, source)

    for term, oid in load_conflict_phrases(OVERLAY_PATH):
        patterns.append((
            re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE),
            "CONFLICT_PHRASE", oid or "CONFLICT_PHRASE",
            "overlay CONFLICT_PHRASE — regulatory/entity confusion, human review before rewrite",
            "trustfield_overlay",
        ))

    for subclass, pat, reason in REG_RISK_PATTERNS:
        patterns.append((re.compile(pat, re.IGNORECASE), "REGULATORY_COPY_RISK", subclass, reason, "co4a_reg_risk_bank"))

    for pat_str, reason in gate.OVERCLAIM_PATTERNS:
        patterns.append((re.compile(pat_str, re.IGNORECASE), "OVERCLAIM", "OVERCLAIM", reason, "language_gate_core"))

    # block_private posture: on the public surface the gate blocks PRIVATE_ONLY terms.
    private_terms = set()
    block_private = bool(gate.SURFACE_POLICY["public"]["block_private"])
    if block_private:
        try:
            private_terms = set(gate.load_dictionary().private_only)
        except Exception:
            private_terms = set()
    for term in sorted(private_terms):
        if not term:
            continue
        patterns.append((
            re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE),
            "BANNED_SURFACE", "PRIVATE_ONLY",
            "PRIVATE_ONLY term on public surface (block_private)",
            "language_gate_core",
        ))

    return {"patterns": patterns, "block_private": block_private, "overlay_path": str(OVERLAY_PATH)}


def scan_line(text: str, engine) -> list[Finding]:
    findings: list[Finding] = []
    for pat, risk_class, subclass, reason, source in engine["patterns"]:
        for m in pat.finditer(text):
            findings.append(Finding(risk_class, subclass, m.group(0), m.start(), m.end(), reason, source))
    findings.sort(key=lambda f: (f.start, f.end))
    return findings


def _merge_spans(findings: list[Finding]) -> list[tuple[int, int]]:
    spans = sorted((f.start, f.end) for f in findings)
    merged: list[list[int]] = []
    for s, e in spans:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return [(s, e) for s, e in merged]


def redact_line(text: str, findings: list[Finding]) -> str:
    """Replace every offending span with a lowercase kebab risk tag so the rendered report
    carries NO raw overclaim string (keeps the report itself clean through the language_gate)."""
    if not findings:
        return text
    tag_at = {}
    for f in findings:
        tag_at.setdefault(f.start, f.subclass.lower().replace("_", "-"))
    out, cursor = [], 0
    for s, e in _merge_spans(findings):
        out.append(text[cursor:s])
        out.append(f"[flagged: {tag_at.get(s, 'risk')}]")
        cursor = e
    out.append(text[cursor:])
    return "".join(out)


def lint_fixture(fixture: dict, engine) -> dict:
    lines = fixture.get("lines") or []
    results = []
    for ln in lines:
        findings = scan_line(ln.get("text", ""), engine)
        results.append({
            "id": ln.get("id"),
            "text": ln.get("text", ""),
            "redacted": redact_line(ln.get("text", ""), findings),
            "flagged": bool(findings),
            "classes": sorted({f.risk_class for f in findings}),
            "findings": [f.as_dict() for f in findings],
            "expect_flagged": ln.get("expect_flagged"),
        })
    flagged = [r for r in results if r["flagged"]]
    return {
        "results": results,
        "total": len(results),
        "flagged": len(flagged),
        "clean": len(results) - len(flagged),
        "populated": len(results) > 0,
    }


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------

def _e(s) -> str:
    return html.escape(str(s), quote=True)


CLASS_LABEL = {
    "CONFLICT_PHRASE": "Conflict phrase",
    "REGULATORY_COPY_RISK": "Regulatory copy risk",
    "OVERCLAIM": "Overclaim",
    "BANNED_SURFACE": "Private-only on public surface",
}


def _row(r: dict) -> str:
    if r["flagged"]:
        badge = '<span class="badge flag">FLAGGED</span>'
        classes = " ".join(f'<span class="chip">{_e(CLASS_LABEL.get(c, c))}</span>' for c in r["classes"])
        subs = ", ".join(_e(f["subclass"]) for f in r["findings"])
        reasons = "".join(f"<li>{_e(f['reason'])} <span class=\"src\">[{_e(f['source'])}]</span></li>" for f in r["findings"])
        detail = f'<div class="detail"><b>Redacted copy:</b> <code>{_e(r["redacted"])}</code><ul class="reasons">{reasons}</ul></div>'
    else:
        badge = '<span class="badge clean">CLEAN</span>'
        classes = '<span class="chip none">no block pattern matched</span>'
        subs = "&mdash;"
        detail = f'<div class="detail"><b>Copy:</b> <code>{_e(r["text"])}</code></div>'
    return f"""      <tr>
        <td class="id">{_e(r['id'])}</td>
        <td>{badge}</td>
        <td>{classes}</td>
        <td class="subs">{subs}</td>
      </tr>
      <tr class="detailrow"><td></td><td colspan="3">{detail}</td></tr>"""


def render(lint: dict, fixture: dict, engine: dict, template: str | None = None) -> str:
    if template is None:
        template = TEMPLATE_PATH.read_text(encoding="utf-8")

    if lint["populated"]:
        total_cell = f'<span class="num">{lint["total"]}</span>'
        flagged_cell = f'<span class="num flag">{lint["flagged"]}</span>'
        clean_cell = f'<span class="num clean">{lint["clean"]}</span>'
        rows = "\n".join(_row(r) for r in lint["results"])
    else:
        # EMPTY-SINK: never render 0/blank as all-clear
        total_cell = flagged_cell = clean_cell = '<span class="badge unpop">UNPOPULATED</span>'
        rows = '<tr><td colspan="4" class="unpoprow"><span class="badge unpop">UNPOPULATED</span> fixture contained no lines — no lint could run (not a clean result)</td></tr>'

    repl = {
        "__LOCK10_BANNER__": _e(LOCK10_BANNER),
        "__LINT_BANNER__": _e(LINT_BANNER),
        "__SYNTHETIC_WM__": _e(SYNTHETIC_WM),
        "__LINT_ANCHOR__": _e(LINT_ANCHOR),
        "__FIXTURE_SOURCE__": _e(fixture.get("source", "unknown")),
        "__FIXTURE_STATUS__": _e(fixture.get("status", "unknown")),
        "__FIXTURE_NOTE__": _e(fixture.get("note", "")),
        "__OVERLAY_PATH__": _e(engine.get("overlay_path", "")),
        "__BLOCK_PRIVATE__": _e("ON (public surface)" if engine.get("block_private") else "off"),
        "__PATTERN_COUNT__": str(len(engine.get("patterns", []))),
        "__TOTAL_CELL__": total_cell,
        "__FLAGGED_CELL__": flagged_cell,
        "__CLEAN_CELL__": clean_cell,
        "__ROWS__": rows,
    }
    out = template
    for k, v in repl.items():
        out = out.replace(k, v)
    return out


def build(out_path: Path = OUT_HTML) -> Path:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    engine = build_engine()
    lint = lint_fixture(fixture, engine)
    html_out = render(lint, fixture, engine)
    out_path.parent.mkdir(parents=True, exist_ok=True)   # Lock 10: local out/ only
    out_path.write_text(html_out, encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# dogfood: run the repo language_gate over the RENDERED report (no receipt written)
# ---------------------------------------------------------------------------

def run_language_gate(text: str, surface: str = "public") -> dict:
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=OUT_HTML)
    ap.add_argument("--no-gate", action="store_true", help="render only; skip the language-gate dogfood")
    args = ap.parse_args(argv)

    out = build(args.out)
    print(f"CO-4a rendered -> {out}")

    if args.no_gate:
        return 0

    result = run_language_gate(out.read_text(encoding="utf-8"), surface="public")
    print(f"CO-4a language_gate dogfood: gate_decision={result['gate_decision']}  verdict={result['verdict']}")
    for b in result["blockers"]:
        print(f"  [BLOCK] {b['type']}: {b['term']!r} (line {b['line']})")
    return 0 if result["verdict"] == "CHECK_OK" else 1


if __name__ == "__main__":
    sys.exit(main())
