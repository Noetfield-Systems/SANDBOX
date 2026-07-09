#!/usr/bin/env python3
"""
DX-5 — "Wording-debt rollup" over the language_gate_review sidecars  (catalog build B4 · DX-5)

A read-only developer-experience rollup. It globs the language_gate_review sidecars that
sit next to the SG-Canonical-Library documents:

    SG-Canonical-Library/**/*.language_gate_review.json   (92 sidecars at build time)

For each sidecar it tallies the wording-debt review reasons — the language_gate's own
findings — into a fixed set of canonical reason buckets, derives a per-file decision,
and renders ONE self-contained, brand-neutral, theme-aware HTML table (to a LOCAL out/
dir) of files ranked by wording-debt (most debt first).

Reason buckets (canonical, stable):
  * AGENT_REVIEW           — agent_review[].type (long/Title-Case sentences to rewrite)
  * UNDEFINED_TERM         — dictionary_warnings[] of type UNDEFINED_TERM
  * ALIAS_RETIRED          — dictionary_warnings[] of type ALIAS_RETIRED
  * SYNONYM_DRIFT          — dictionary_warnings[] of type SYNONYM_DRIFT
  * PLAIN_ENGLISH          — proposed_agent_actions[] of type PLAIN_ENGLISH
  * REGEX_REWRITE          — one per proposed_regex_rewrites[] entry
  * LATENT_UNDEFINED_TERM  — one per latent_undefined_terms[] entry

Per-file decision:
  * the sidecar's own rewrite_policy string if present (e.g. SIDECAR_PREVIEW_ONLY)
  * else "CLEAN"  when the file has debt keys but zero debt items
  * else "REVIEW" when there is any wording-debt
  * "UNPOPULATED" when the sidecar carries none of the known debt keys (empty sink / stub)

Commercial / deliverable locks (Lock 10):
  * the generated HTML carries a visible "DO NOT PUSH — not for public hosting" banner and
    is written only to a local out/ path (never a public-hosting / CF / Vercel path).
  * counts are REAL (tallied from the on-disk sidecars, read-only); they are NOT synthetic.
    Empty / clean / unpopulated states render as explicit CLEAN / UNPOPULATED badges,
    never as a bare 0 that reads all-clear.
  * no autonomy, no guaranteed-outcome claim — this is an advisory rollup of existing findings.

    python3 dx5_wording_debt_rollup.py                # tally the real sidecars -> out/wording_debt_rollup.html
    python3 dx5_wording_debt_rollup.py --print-top 10 # also print the top-N table to stdout
"""
from __future__ import annotations

import argparse
import glob
import html
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE_PATH = HERE / "report_template.html"
OUT_DIR = HERE / "out"                                   # Lock 10: local out/, never a hosting path
OUT_HTML = OUT_DIR / "wording_debt_rollup.html"

BANNER_TEXT = "DO NOT PUSH — not for public hosting (internal wording-debt rollup, advisory)"
FOOTER_NOTE = (
    "Advisory rollup. Each count is tallied read-only from the language_gate_review sidecars "
    "that already sit next to the library documents; nothing here is a synthetic or guaranteed "
    "claim. CLEAN means the sidecar carries debt keys but zero open items; UNPOPULATED means the "
    "sidecar carries none of the known debt keys (treat as empty-sink / stub, not as all-clear)."
)

# Canonical reason buckets, in stable display order.
REASON_ORDER = [
    "AGENT_REVIEW",
    "UNDEFINED_TERM",
    "ALIAS_RETIRED",
    "SYNONYM_DRIFT",
    "PLAIN_ENGLISH",
    "REGEX_REWRITE",
    "LATENT_UNDEFINED_TERM",
]

# Keys in a sidecar that carry wording-debt signal. If NONE are present the sidecar is
# treated as UNPOPULATED (empty-sink / stub), distinct from CLEAN.
DEBT_KEYS = (
    "agent_review",
    "dictionary_warnings",
    "proposed_agent_actions",
    "proposed_regex_rewrites",
    "latent_undefined_terms",
)

LIBRARY_GLOB = "SG-Canonical-Library/**/*.language_gate_review.json"


def _repo_root() -> Path:
    # sg-sandbox root: catalog/builds/DX-5 -> up 3.
    return HERE.parents[2]


def find_sidecars(root: Path | None = None) -> list[Path]:
    """Glob the language_gate_review sidecars under the canonical library (read-only)."""
    base = root if root is not None else _repo_root()
    return sorted(Path(p) for p in glob.glob(str(base / LIBRARY_GLOB), recursive=True))


def _new_counts() -> dict[str, int]:
    return {r: 0 for r in REASON_ORDER}


def tally_sidecar(data: dict) -> dict:
    """Tally one sidecar's wording-debt into canonical reason buckets + a decision.

    Pure function of the parsed JSON — no I/O — so the test can drive it with a
    hand-built dict and with a mutated dict (red-capable).
    """
    counts = _new_counts()

    for item in data.get("agent_review") or []:
        t = item.get("type", "AGENT_REVIEW") if isinstance(item, dict) else "AGENT_REVIEW"
        counts[t] = counts.get(t, 0) + 1

    for item in data.get("dictionary_warnings") or []:
        t = item.get("type", "UNDEFINED_TERM") if isinstance(item, dict) else "UNDEFINED_TERM"
        counts[t] = counts.get(t, 0) + 1

    for item in data.get("proposed_agent_actions") or []:
        t = item.get("type", "PLAIN_ENGLISH") if isinstance(item, dict) else "PLAIN_ENGLISH"
        counts[t] = counts.get(t, 0) + 1

    counts["REGEX_REWRITE"] += len(data.get("proposed_regex_rewrites") or [])
    counts["LATENT_UNDEFINED_TERM"] += len(data.get("latent_undefined_terms") or [])

    debt_total = sum(counts.values())
    populated = any(k in data for k in DEBT_KEYS)

    if not populated:
        decision = "UNPOPULATED"
    elif data.get("rewrite_policy"):
        decision = str(data["rewrite_policy"])
    elif debt_total == 0:
        decision = "CLEAN"
    else:
        decision = "REVIEW"

    return {
        "counts": counts,
        "debt_total": debt_total,
        "decision": decision,
        "populated": populated,
    }


def _short_name(sidecar_path: str, data: dict) -> str:
    """Human file label: the reviewed document path if the sidecar records it, else the
    sidecar basename with the .language_gate_review.json suffix stripped."""
    f = data.get("file")
    if isinstance(f, str) and f:
        return f
    name = Path(sidecar_path).name
    return name.replace(".language_gate_review.json", "")


def build_rollup(sidecars: list[Path]) -> dict:
    """Read every sidecar and produce a rank-ordered rollup (most wording-debt first)."""
    rows = []
    corpus = _new_counts()
    decision_totals: dict[str, int] = {}
    for p in sidecars:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        t = tally_sidecar(data)
        rows.append({
            "sidecar": str(p),
            "name": _short_name(str(p), data),
            "counts": t["counts"],
            "debt_total": t["debt_total"],
            "decision": t["decision"],
            "populated": t["populated"],
        })
        for r in REASON_ORDER:
            corpus[r] += t["counts"][r]
        decision_totals[t["decision"]] = decision_totals.get(t["decision"], 0) + 1

    # Rank: highest debt first; ties broken by name for determinism.
    rows.sort(key=lambda r: (-r["debt_total"], r["name"]))
    for i, r in enumerate(rows, start=1):
        r["rank"] = i

    return {
        "rows": rows,
        "file_count": len(rows),
        "corpus_counts": corpus,
        "corpus_total": sum(corpus.values()),
        "decision_totals": decision_totals,
    }


# ------------------------------- rendering ---------------------------------------------

def _e(s) -> str:
    return html.escape(str(s), quote=True)


_DECISION_CLASS = {
    "REVIEW": "d-review",
    "CLEAN": "d-clean",
    "UNPOPULATED": "d-unpop",
}


def _decision_badge(decision: str) -> str:
    cls = _DECISION_CLASS.get(decision, "d-policy")
    return f'<span class="badge {cls}">{_e(decision)}</span>'


def _debt_cell(row: dict) -> str:
    """The debt-total cell — never a bare 0. Zero shows CLEAN/UNPOPULATED, not all-clear."""
    if not row["populated"]:
        return '<span class="badge d-unpop">UNPOPULATED</span>'
    if row["debt_total"] == 0:
        return '<span class="badge d-clean">CLEAN &middot; 0</span>'
    return f'<b class="debt-n">{row["debt_total"]}</b>'


def _reason_chips(counts: dict) -> str:
    chips = []
    for r in REASON_ORDER:
        n = counts.get(r, 0)
        if n:
            chips.append(f'<span class="chip">{_e(r)}<i>{n}</i></span>')
    return "".join(chips) if chips else '<span class="chip chip-none">none</span>'


def _table_rows(rows: list[dict]) -> str:
    out = []
    for r in rows:
        out.append(
            "<tr>"
            f'<td class="rank">{r["rank"]}</td>'
            f'<td class="file"><code>{_e(r["name"])}</code></td>'
            f'<td class="debt">{_debt_cell(r)}</td>'
            f'<td class="reasons">{_reason_chips(r["counts"])}</td>'
            f'<td class="decision">{_decision_badge(r["decision"])}</td>'
            "</tr>"
        )
    return "\n      ".join(out)


def _corpus_summary(rollup: dict) -> str:
    parts = [f'<span class="chip">{_e(r)}<i>{rollup["corpus_counts"][r]}</i></span>'
             for r in REASON_ORDER if rollup["corpus_counts"][r]]
    dt = rollup["decision_totals"]
    dparts = [f'<span class="chip">{_e(k)}<i>{v}</i></span>'
              for k, v in sorted(dt.items(), key=lambda kv: (-kv[1], kv[0]))]
    return (
        f'<div class="sum-line"><span class="sum-label">Reasons</span>{"".join(parts)}</div>'
        f'<div class="sum-line"><span class="sum-label">Decisions</span>{"".join(dparts)}</div>'
    )


def render(rollup: dict, template: str | None = None) -> str:
    if template is None:
        template = TEMPLATE_PATH.read_text(encoding="utf-8")
    repl = {
        "__BANNER_TEXT__": _e(BANNER_TEXT),
        "__FILE_COUNT__": str(rollup["file_count"]),
        "__CORPUS_TOTAL__": str(rollup["corpus_total"]),
        "__CORPUS_SUMMARY__": _corpus_summary(rollup),
        "__TABLE_ROWS__": _table_rows(rollup["rows"]),
        "__FOOTER_NOTE__": _e(FOOTER_NOTE),
    }
    out = template
    for k, v in repl.items():
        out = out.replace(k, v)
    return out


def build(out_path: Path = OUT_HTML, root: Path | None = None) -> Path:
    rollup = build_rollup(find_sidecars(root))
    html_out = render(rollup)
    out_path.parent.mkdir(parents=True, exist_ok=True)   # Lock 10: local out/ only
    out_path.write_text(html_out, encoding="utf-8")
    return out_path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=OUT_HTML)
    ap.add_argument("--print-top", type=int, default=0, metavar="N",
                    help="also print the top-N ranked files to stdout")
    args = ap.parse_args(argv)

    sidecars = find_sidecars()
    rollup = build_rollup(sidecars)
    out = build(args.out)
    print(f"DX-5 tallied {rollup['file_count']} sidecars "
          f"({rollup['corpus_total']} debt items) -> {out}")

    if args.print_top:
        print(f"\nTop {args.print_top} by wording-debt:")
        print(f"  {'rank':>4}  {'debt':>4}  {'decision':<18}  file")
        for r in rollup["rows"][:args.print_top]:
            print(f"  {r['rank']:>4}  {r['debt_total']:>4}  {r['decision']:<18}  {r['name']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
