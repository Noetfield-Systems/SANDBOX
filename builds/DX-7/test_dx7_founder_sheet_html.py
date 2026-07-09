#!/usr/bin/env python3
"""
TH for DX-7 — the DLM founder-sheet HTML renderer's own proof.

The sheet dict is produced by running the real DLM pipeline ONCE with all writes
redirected to a temp dir (TH-2 pattern). The HTML renderer is judged against the
MODULE's own render_founder_sheet_md for the SAME dict: same sections, same counts.

Red-capable two ways:
  * DATA-DRIVEN — a minimal mutation of the sheet dict (drop one advisor cluster)
    changes the rendered cluster count; the parity assertion discriminates real vs
    mutated input (test_mutated_dict_is_detected).
  * DOGFOOD — the clean HTML does NOT FAIL the repo language_gate (surface=public);
    a minimal overclaim injection ("100% guaranteed") FAILs it -> CHECK_REJECTED.

Isolation guards:
  * generate_sheet() writes nothing into the tracked decision_language_machine_v1 tree.
  * the gate dogfood writes no receipt into the tracked language_gate/receipts dir.

    python3 test_dx7_founder_sheet_html.py       # self-runner
    pytest -q test_dx7_founder_sheet_html.py
"""
from __future__ import annotations

import html as _htmllib
import importlib.util
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("dx7", HERE / "dx7_founder_sheet_html.py")
dx7 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dx7)

dx7._ensure_paths()
from dlm_founder_sheet_v1 import render_founder_sheet_md  # noqa: E402  (the module we must match)

OVERCLAIM_INJECTION = "100% guaranteed outcome"
HINTS_ANCHOR = "Recommended picks are hints only"

_SHEET_CACHE: dict = {}


def _sheet() -> dict:
    if "s" not in _SHEET_CACHE:
        _SHEET_CACHE["s"] = dx7.generate_sheet()
    return _SHEET_CACHE["s"]


def _visible_text(html: str) -> str:
    html = re.sub(r"<style.*?</style>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<[^>]+>", " ", html)
    return _htmllib.unescape(html)


def _synthetic_sheet() -> dict:
    """Hand-built dict in the SAME shape, exercising the empty-field (UNPOPULATED) paths."""
    return {
        "schema": "decision_language_machine_founder_sheet_v1",
        "summary": {
            "total_items": 3, "advisor_clusters": 1, "advisor_items": 1,
            "founder_fact_items": 0, "machine_validatable": 0, "deferred": 2,
        },
        "advisor_clusters": [
            {
                "cluster_id": "CL-EMPTY", "name": "Cluster with no options",
                "plain_english": "Does this render an explicit empty badge?",
                "controls": "founder", "if_unanswered": "hold",
                "member_ids": [], "options": [], "note": "hints only",
            }
        ],
        "founder_facts": [],
        "machine_queue_ids": [],
        "deferred_ids": ["X-1", "X-2"],
    }


# ------------------------------------------------------------------ parity
def test_html_renders_same_summary_counts_as_md():
    sheet = _sheet()
    md = render_founder_sheet_md(sheet)
    html = dx7.render_founder_sheet_html(sheet)
    s = sheet["summary"]
    for val in (s["total_items"], s["advisor_clusters"], s["founder_fact_items"],
                s["machine_validatable"], s["deferred"]):
        assert str(val) in md, f"{val} missing from md (sanity)"
        assert str(val) in html, f"summary count {val} missing from html"


def test_html_contains_every_cluster_fact_and_machine_id():
    sheet = _sheet()
    html = dx7.render_founder_sheet_html(sheet)
    md = render_founder_sheet_md(sheet)
    for c in sheet["advisor_clusters"]:
        assert c["cluster_id"] in md and c["cluster_id"] in html, f"cluster id {c['cluster_id']}"
        assert c["name"] in html, f"cluster name {c['name']}"
        assert c["plain_english"] in html, "cluster plain_english"
        for m in c["member_ids"]:
            assert m in html, f"member id {m} missing from html"
    for f in sheet["founder_facts"]:
        assert f["id"] in html, f"founder fact {f['id']} missing"
        assert f["plain_english"] in html
    for q in sheet["machine_queue_ids"][:20]:
        assert q in html, f"machine queue id {q} missing (md preview shows first 20)"


def test_cluster_section_count_matches_summary():
    sheet = _sheet()
    html = dx7.render_founder_sheet_html(sheet)
    n = html.count('<section class="cluster">')
    assert n == sheet["summary"]["advisor_clusters"], \
        f"rendered {n} cluster sections vs summary {sheet['summary']['advisor_clusters']}"
    # same number of numbered headings as the md renderer emits (## i. [id])
    md = render_founder_sheet_md(sheet)
    md_clusters = len(re.findall(r"^## \d+\. \[", md, flags=re.M))
    assert md_clusters == n, f"md has {md_clusters} cluster headings, html has {n}"


# ------------------------------------------- empty-sink vs clean (B4 guard)
def test_empty_fields_render_unpopulated_badge_not_blank():
    html = dx7.render_founder_sheet_html(_synthetic_sheet())
    # empty options, empty members, empty facts, empty machine-queue -> explicit badge
    assert html.count("UNPOPULATED") >= 4, "empty fields must render an explicit UNPOPULATED badge"
    # the counts that ARE zero must still be shown as numbers, not hidden
    assert re.search(r'class="mval">0<', html), "a genuine 0 metric must still render"


# ------------------------------------------------- Lock 10 + watermark + no-claims
def test_lock10_banner_and_synthetic_watermark():
    html = dx7.render_founder_sheet_html(_sheet())
    assert "DO NOT PUSH" in html, "Lock 10 banner missing"
    assert "SYNTHETIC" in html and "not a guaranteed claim" in html, "synthetic watermark missing"


def test_no_autonomy_or_guarantee_claims_in_clean_html():
    text = _visible_text(dx7.render_founder_sheet_html(_sheet())).lower()
    for banned in ("100% guaranteed", "fully autonomous", "runs itself",
                   "certified", "guaranteed outcome", "zero-drift proven"):
        assert banned not in text, f"clean html must not claim {banned!r}"


# ---------------------------------------------------- gate dogfood (red-capable)
def test_positive_real_html_passes_gate():
    html = dx7.render_founder_sheet_html(_sheet())
    res = dx7.run_language_gate(html, surface="public")
    assert res["gate_decision"] != "FAIL", res
    assert res["verdict"] == "CHECK_OK", res


def test_negative_minimal_mutation_overclaim_fails_gate():
    clean = dx7.render_founder_sheet_html(_sheet())
    assert HINTS_ANCHOR in clean, "anchor for the single-field flip is gone"
    mutant = clean.replace(HINTS_ANCHOR, OVERCLAIM_INJECTION, 1)   # flip ONE field
    assert mutant != clean
    res = dx7.run_language_gate(mutant, surface="public")
    assert res["gate_decision"] == "FAIL", res
    assert res["verdict"] == "CHECK_REJECTED", res
    assert "OVERCLAIM" in {b["type"] for b in res["blockers"]}, res


def test_mutation_is_minimal_and_gate_is_not_relaxed():
    clean = dx7.render_founder_sheet_html(_sheet())
    mutant = clean.replace(HINTS_ANCHOR, OVERCLAIM_INJECTION, 1)
    # minimality: reversing the injection reproduces the clean artifact byte-for-byte
    assert mutant.replace(OVERCLAIM_INJECTION, HINTS_ANCHOR, 1) == clean
    assert dx7.run_language_gate(clean)["verdict"] == "CHECK_OK"
    assert dx7.run_language_gate(mutant)["verdict"] == "CHECK_REJECTED"


# ------------------------------------------------- data-driven discrimination
def test_mutated_dict_is_detected():
    """Dropping one advisor cluster from the dict must change the rendered section count —
    the renderer tracks the data, it is not a fixed template."""
    sheet = _sheet()
    n_full = dx7.render_founder_sheet_html(sheet).count('<section class="cluster">')
    assert sheet["advisor_clusters"], "fixture must have at least one cluster"
    mutated = dict(sheet)
    mutated["advisor_clusters"] = sheet["advisor_clusters"][:-1]  # drop one
    n_mut = dx7.render_founder_sheet_html(mutated).count('<section class="cluster">')
    assert n_mut == n_full - 1, f"renderer did not track the dropped cluster: {n_full} -> {n_mut}"


# --------------------------------------------------------------- isolation
def test_generate_sheet_writes_nothing_into_tracked_dlm_dir():
    dlm = dx7._repo_root() / "decision_language_machine_v1"
    out_dir, rec_dir = dlm / "output", dlm / "receipts"
    before_out = {p.name for p in out_dir.glob("*")} if out_dir.exists() else set()
    before_rec = {p.name for p in rec_dir.glob("*")} if rec_dir.exists() else set()
    dx7.generate_sheet()
    after_out = {p.name for p in out_dir.glob("*")} if out_dir.exists() else set()
    after_rec = {p.name for p in rec_dir.glob("*")} if rec_dir.exists() else set()
    assert before_out == after_out, "pipeline wrote into tracked DLM output/ — temp redirect failed"
    assert before_rec == after_rec, "pipeline wrote into tracked DLM receipts/ — temp redirect failed"


def test_dogfood_writes_no_receipt_into_tracked_gate_dir():
    receipts = dx7._repo_root() / "language_gate" / "receipts"
    before = {p.name for p in receipts.glob("*")} if receipts.exists() else set()
    dx7.run_language_gate(dx7.render_founder_sheet_html(_sheet()), surface="public")
    after = {p.name for p in receipts.glob("*")} if receipts.exists() else set()
    assert before == after, "dogfood must not write a receipt into the tracked gate dir"


TESTS = [
    test_html_renders_same_summary_counts_as_md,
    test_html_contains_every_cluster_fact_and_machine_id,
    test_cluster_section_count_matches_summary,
    test_empty_fields_render_unpopulated_badge_not_blank,
    test_lock10_banner_and_synthetic_watermark,
    test_no_autonomy_or_guarantee_claims_in_clean_html,
    test_positive_real_html_passes_gate,
    test_negative_minimal_mutation_overclaim_fails_gate,
    test_mutation_is_minimal_and_gate_is_not_relaxed,
    test_mutated_dict_is_detected,
    test_generate_sheet_writes_nothing_into_tracked_dlm_dir,
    test_dogfood_writes_no_receipt_into_tracked_gate_dir,
]


def _main() -> int:
    failed = 0
    for t in TESTS:
        try:
            t(); print(f"PASS  {t.__name__}")
        except AssertionError as e:
            failed += 1; print(f"FAIL  {t.__name__}: {e}")
    print(f"\n{len(TESTS)-failed}/{len(TESTS)} green")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_main())
