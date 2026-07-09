#!/usr/bin/env python3
"""
TH for DX-1 - the P0-PGR read-only status dashboard's own proof.

Red-capable by construction (data-driven, discriminates real vs mutated input):
  * the rendered HTML reflects the REAL ranked-queue order from phase2_queue_v1.json,
    in the exact receipt order (M03 > M05 > M04 > M02 > M06 > M07 > M01 > M09);
  * an attestation field that was never populated (packets_confirmed_accepted_by_founder = 0)
    renders an explicit UNPOPULATED badge - NOT a clean/all-clear 0;
  * a safety-invariant 0 (p0_leakage_count = 0) DOES render CLEAN - so the badge system
    actually discriminates 'measured good zero' from 'empty sink';
  * MUTATION teeth: reversing two rows in the queue input flips the rendered row order
    (proves the order is read from data, not hardcoded); populating the attestation field
    flips UNPOPULATED -> POPULATED (proves the badge is data-driven);
  * STALE freshness: with a render time well after the receipts' timestamps, the sources
    flag STALE, not FRESH;
  * autonomy rungs R4/R5 render LOCKED / proof-gated, never 'available'.
"""
from __future__ import annotations
import copy
import importlib.util
import re
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("dx1", HERE / "dx1_p0pgr_status_dashboard.py")
dx1 = importlib.util.module_from_spec(spec); spec.loader.exec_module(dx1)

REAL = dx1.load_inputs()
EXPECTED_ORDER = ["M03", "M05", "M04", "M02", "M06", "M07", "M01", "M09"]
# a render time deliberately after the 2026-07-08 receipts so freshness resolves STALE
NOW_LATE = datetime(2026, 7, 10, 0, 0, tzinfo=timezone.utc)


def _rendered(data=None, now=NOW_LATE) -> str:
    return dx1.render(data or REAL, now=now)


def _row_order(html: str) -> list[str]:
    return re.findall(r'<tr data-move="([^"]+)"', html)


def test_queue_order_matches_real_receipt_order():
    order = dx1.queue_order(REAL)
    assert order == EXPECTED_ORDER, f"receipt order drifted: {order}"
    html = _rendered()
    assert _row_order(html) == EXPECTED_ORDER, "rendered rows must match the real ROI queue order"


def test_mutating_queue_input_changes_rendered_order():
    # swap the top two ranked moves in a COPY of the input; the rendered order must follow.
    mutated = copy.deepcopy(REAL)
    rq = mutated["queue"]["ranked_queue"]
    rq[0], rq[1] = rq[1], rq[0]
    html = _rendered(mutated)
    got = _row_order(html)
    assert got[:2] == [EXPECTED_ORDER[1], EXPECTED_ORDER[0]], got
    assert got != EXPECTED_ORDER, "order must be read from data, not hardcoded"


def test_empty_attestation_field_renders_UNPOPULATED_not_clean_zero():
    # packets_confirmed_accepted_by_founder is 0 in the real receipt: an attestation gap,
    # not a clean zero. It must carry the UNPOPULATED badge on its own card.
    assert REAL["phase1"]["packets_confirmed_accepted_by_founder"] == 0
    html = _rendered()
    m = re.search(
        r'data-field="packets_confirmed_accepted_by_founder".*?</div>\s*</div>',
        html, flags=re.S)
    assert m, "founder-confirmation card missing"
    card = m.group(0)
    assert "UNPOPULATED" in card, "empty attestation field must render UNPOPULATED"
    assert "CLEAN" not in card and ">0<" not in card, "must NOT read as a clean 0/all-clear"


def test_populating_attestation_field_flips_badge():
    mutated = copy.deepcopy(REAL)
    mutated["phase1"]["packets_confirmed_accepted_by_founder"] = 10
    html = _rendered(mutated)
    m = re.search(
        r'data-field="packets_confirmed_accepted_by_founder".*?</div>\s*</div>',
        html, flags=re.S)
    card = m.group(0)
    assert "UNPOPULATED" not in card and "POPULATED" in card, "populated field must drop UNPOPULATED"


def test_safety_invariant_zero_reads_CLEAN_not_unpopulated():
    # the badge system must discriminate: a measured invariant 0 is CLEAN, not UNPOPULATED.
    assert REAL["phase2"]["counters"]["p0_leakage_count"] == 0
    html = _rendered()
    m = re.search(r'data-field="p0_leakage_count".*?</div>\s*</div>', html, flags=re.S)
    card = m.group(0)
    assert "CLEAN" in card, "a measured invariant 0 must read CLEAN"
    assert "UNPOPULATED" not in card, "invariant 0 must NOT be flagged UNPOPULATED"


def test_sources_flag_STALE_after_window():
    html = _rendered(now=NOW_LATE)
    assert "STALE" in html, "receipts older than the window must flag STALE"
    # and the freshness helper itself discriminates
    fresh = dx1.freshness(REAL["phase1"]["updated_at"],
                          datetime(2026, 7, 8, 14, 0, tzinfo=timezone.utc))
    assert fresh["kind"] == "FRESH"
    stale = dx1.freshness(REAL["phase1"]["updated_at"], NOW_LATE)
    assert stale["kind"] == "STALE"


def test_no_timestamp_source_flagged_not_silently_fresh():
    # the ladder markdown has no machine timestamp; it must be flagged, never shown FRESH.
    html = _rendered()
    assert "NO TIMESTAMP" in html


def test_ladder_rungs_parsed_with_states():
    rungs = REAL["ladder"]
    ids = [r["id"] for r in rungs]
    assert ids == ["R1", "R2", "R3", "R4", "R5"], ids
    by = {r["id"]: r for r in rungs}
    assert by["R1"]["state"] == "DONE" and by["R1"]["current"]
    assert by["R2"]["state"] == "BUILT"
    for rid in ("R3", "R4", "R5"):
        assert by[rid]["state"] == "LOCKED", f"{rid} founder-unlock rung must be LOCKED"


def test_autonomy_rungs_locked_never_available():
    html = _rendered()
    text = re.sub(r"<style.*?</style>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text).lower()
    assert html.count("LOCKED") >= 3, "R3/R4/R5 must render LOCKED"
    assert "proof-gated" in html
    assert not re.search(r"\bavailable\b", text), "no rung may be labelled available"


def test_lock10_banner_and_local_out_path():
    html = _rendered()
    assert "DO NOT PUSH" in html, "Lock 10 banner missing"
    # build writes only into a local out/ dir
    assert dx1.OUT_HTML.parent.name == "out"


TESTS = [
    test_queue_order_matches_real_receipt_order,
    test_mutating_queue_input_changes_rendered_order,
    test_empty_attestation_field_renders_UNPOPULATED_not_clean_zero,
    test_populating_attestation_field_flips_badge,
    test_safety_invariant_zero_reads_CLEAN_not_unpopulated,
    test_sources_flag_STALE_after_window,
    test_no_timestamp_source_flagged_not_silently_fresh,
    test_ladder_rungs_parsed_with_states,
    test_autonomy_rungs_locked_never_available,
    test_lock10_banner_and_local_out_path,
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
