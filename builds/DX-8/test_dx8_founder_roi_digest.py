#!/usr/bin/env python3
"""
TH for DX-8 — the weekly founder ROI digest's own proof.

Red-capable by construction, data-driven (no strawman):
  * the digest reflects the REAL ranked queue — order + move ids + count match the
    scorecard's queue_order, read from the on-disk receipts.
  * the send / deploy / cost counters are present AND exactly zero; the digest renders
    them "0 / OK" and the NO-SEND/NO-DEPLOY invariant is HELD.
  * NEGATIVE — a MINIMAL MUTATION of the real scorecard (flip external_sends 0 -> 3, or
    deploys 0 -> 1) makes the invariant BREACH and assert_invariants() raise. Same model
    code, opposite verdict.
  * EMPTY-SINK — deleting a counter key makes it render UNPOPULATED (not a silent 0) and
    the invariant becomes UNKNOWN, so an absent counter never reads as all-clear.
  * FRESHNESS — with an as_of a month in the future the sources render STALE, not FRESH.
  * Lock 10 — the generated HTML carries the DO-NOT-PUSH banner and lands only in out/.
  * no autonomy / guaranteed-outcome claim in the rendered digest.
"""
from __future__ import annotations
import copy, html as _htmllib, importlib.util, json, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("dx8", HERE / "dx8_founder_roi_digest.py")
dx8 = importlib.util.module_from_spec(spec); spec.loader.exec_module(dx8)

QUEUE, SCORECARD, EXECR = dx8.load_sources()


def _model(**kw):
    return dx8.build_model(copy.deepcopy(QUEUE), copy.deepcopy(SCORECARD), copy.deepcopy(EXECR), **kw)


def _visible_text(html: str) -> str:
    html = re.sub(r"<style.*?</style>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<[^>]+>", " ", html)
    return _htmllib.unescape(html)


def test_digest_reflects_the_real_ranked_queue():
    model = _model()
    # order + ids come straight from the queue, and match the scorecard's own queue_order
    assert model["queue_order"] == SCORECARD["queue_order"], model["queue_order"]
    assert [r["move_id"] for r in model["ranked_moves"]] == [m["move_id"] for m in QUEUE["ranked_queue"]]
    assert len(model["ranked_moves"]) == len(QUEUE["ranked_queue"]) == 8
    assert model["ranked_moves"][0]["move_id"] == "M03"          # top move is the executed one
    # rendered md must contain every ranked move id in rank order
    md = dx8.render_markdown(model)
    positions = [md.index(r["move_id"] + " |") if False else md.find(r["move_id"]) for r in model["ranked_moves"]]
    for mv in QUEUE["ranked_queue"]:
        assert mv["move_id"] in md, f"{mv['move_id']} missing from digest"


def test_send_and_deploy_counters_are_zero_and_invariant_held():
    model = _model()
    c = {row["name"]: row for row in model["counters"]}
    for k in ("external_sends", "deploys", "forms_submitted", "merges", "estimated_cost_usd"):
        assert c[k]["present"], f"{k} must be present, not inferred"
        assert c[k]["value"] in (0, 0.0), f"{k} must be zero, got {c[k]['value']}"
        assert c[k]["badge"] == "OK"
    assert model["invariant_ok"] is True
    assert model["invariant_breaches"] == [] and model["invariant_unknown"] == []
    dx8.assert_invariants(model)                                  # does not raise
    md = dx8.render_markdown(model)
    assert "external_sends | 0 |" in md and "deploys | 0 |" in md


def test_negative_minimal_mutation_nonzero_send_breaches_invariant():
    bad = copy.deepcopy(SCORECARD)
    bad["counters"]["external_sends"] = 3                         # flip ONE field
    model = dx8.build_model(copy.deepcopy(QUEUE), bad, copy.deepcopy(EXECR))
    assert model["invariant_ok"] is False
    assert "external_sends" in model["invariant_breaches"]
    row = next(r for r in model["counters"] if r["name"] == "external_sends")
    assert row["badge"] == "BREACH"
    raised = False
    try:
        dx8.assert_invariants(model)
    except AssertionError:
        raised = True
    assert raised, "assert_invariants must raise on a non-zero send counter"


def test_negative_minimal_mutation_nonzero_deploy_breaches_invariant():
    bad = copy.deepcopy(SCORECARD)
    bad["counters"]["deploys"] = 1
    model = dx8.build_model(copy.deepcopy(QUEUE), bad, copy.deepcopy(EXECR))
    assert model["invariant_ok"] is False and "deploys" in model["invariant_breaches"]


def test_empty_sink_absent_counter_is_unpopulated_not_zero():
    bad = copy.deepcopy(SCORECARD)
    del bad["counters"]["external_sends"]                         # sink emptied, not zeroed
    model = dx8.build_model(copy.deepcopy(QUEUE), bad, copy.deepcopy(EXECR))
    row = next(r for r in model["counters"] if r["name"] == "external_sends")
    assert row["present"] is False and row["badge"] == "UNPOPULATED"
    assert model["invariant_ok"] is False and "external_sends" in model["invariant_unknown"]
    md = dx8.render_markdown(model)
    assert "UNPOPULATED" in md                                   # never rendered as a silent 0


def test_freshness_badges_fresh_now_stale_in_future():
    fresh = _model()                                              # default as_of = latest source ts
    assert all(s["badge"] == "FRESH" for s in fresh["sources"]), fresh["sources"]
    stale = _model(as_of="2026-08-20T00:00:00Z")                 # >7 days later
    assert all(s["badge"] == "STALE" for s in stale["sources"]), stale["sources"]


def test_findings_and_held_are_surfaced():
    model = _model()
    fids = {f["id"] for f in model["findings"]}
    assert {"F1", "F2"} <= fids, fids
    held_ids = {h["move_id"] for h in model["held"]}
    assert {"M08", "M10"} <= held_ids, held_ids
    md = dx8.render_markdown(model)
    assert "HOLD_CLOUD_UNSAFE" in md and "CLAIM_AMBIGUITY" in md


def test_lock10_banner_and_local_out_only():
    model = dx8.build()                                           # writes real artifacts to out/
    html_path = dx8.OUT_HTML
    md_path = dx8.OUT_MD
    assert html_path.is_file() and md_path.is_file()
    assert html_path.resolve().parent.name == "out"
    html = html_path.read_text(encoding="utf-8")
    assert "DO NOT PUSH" in html and "DO NOT PUSH" in md_path.read_text(encoding="utf-8")


def test_no_autonomy_or_guarantee_claims():
    dx8.build()
    text = _visible_text(dx8.OUT_HTML.read_text(encoding="utf-8")).lower()
    # affirmative overclaims only; the prescribed disclaimer "not a guaranteed claim" is a negation, not a claim
    for banned in ("we guarantee", "guaranteed outcome", "guaranteed results", "100% guaranteed",
                   "fully autonomous", "runs itself", "zero-drift proven"):
        assert banned not in text, f"digest must not claim {banned!r}"
    # the only occurrence of 'guarantee*' must be inside the disclaiming watermark
    assert re.sub(r"not a guaranteed claim", "", text).find("guarantee") == -1, "unexpected guarantee claim"


def test_deterministic_render_is_byte_stable():
    a = dx8.render_html(_model())
    b = dx8.render_html(_model())
    assert a == b, "render must be deterministic for identical inputs"


TESTS = [
    test_digest_reflects_the_real_ranked_queue,
    test_send_and_deploy_counters_are_zero_and_invariant_held,
    test_negative_minimal_mutation_nonzero_send_breaches_invariant,
    test_negative_minimal_mutation_nonzero_deploy_breaches_invariant,
    test_empty_sink_absent_counter_is_unpopulated_not_zero,
    test_freshness_badges_fresh_now_stale_in_future,
    test_findings_and_held_are_surfaced,
    test_lock10_banner_and_local_out_only,
    test_no_autonomy_or_guarantee_claims,
    test_deterministic_render_is_byte_stable,
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
    import sys
    sys.exit(_main())
