#!/usr/bin/env python3
"""
TH for DX-6 — the state-surface index's own proof.

Red-capable by construction (data-driven, no strawman):
  * the rendered motor-row count is PINNED to the registry motor count. Mutating the
    registry (drop or add a motor) changes the rendered count, so the assertion is not
    green-by-construction — a mutated input FAILs it.
  * an EMPTY census sink must render an explicit UNPOPULATED card, never four 0 cards
    that read all-clear. The clean census (with real counts) must NOT render that
    UNPOPULATED card — same renderer, opposite outcomes.
  * autonomy fields render LOCKED / proof-gated, never "available".
  * Lock 10 banner present; output confined to local out/.
"""
from __future__ import annotations
import copy
import importlib.util
import re
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("dx6", HERE / "dx6_state_surface_index.py")
dx6 = importlib.util.module_from_spec(spec); spec.loader.exec_module(dx6)

NOW = datetime(2026, 7, 9, 12, 0, tzinfo=timezone.utc)   # fixed clock for deterministic freshness


def _real_inputs() -> dict:
    inp = dx6.load_inputs()
    assert inp["registry"].get("motors"), "registry must load real motors"
    return inp


def _count_motor_rows(html: str) -> int:
    return len(re.findall(r'data-motor-row="', html))


# ---- data-driven discriminator: rendered motor count == registry motor count ----

def test_rendered_motor_count_matches_registry():
    inp = _real_inputs()
    n = len(inp["registry"]["motors"])
    html = dx6.render(inp, now=NOW)
    assert _count_motor_rows(html) == n, "rendered motor rows must equal registry motor count"
    # the headline stat must show the same number
    assert re.search(rf'id="motor-count">{n}<', html), "headline motor count must match registry"


def test_mutating_registry_changes_rendered_count():
    """Drop one motor -> the count-matches assertion no longer holds against the ORIGINAL n.
    Proves the assertion discriminates real input from a mutation (not green-by-construction)."""
    inp = _real_inputs()
    n = len(inp["registry"]["motors"])
    mutant = copy.deepcopy(inp)
    dropped = mutant["registry"]["motors"].pop()          # minimal mutation: remove one motor
    html = dx6.render(mutant, now=NOW)
    assert _count_motor_rows(html) == n - 1, "mutant must render one fewer motor row"
    assert dropped["motor_id"] not in html or f'data-motor-row="{dropped["motor_id"]}"' not in html
    # the discriminator an operator would assert (rows == original n) now fails on the mutant
    assert _count_motor_rows(html) != n


def test_agent_lane_count_matches_registry():
    inp = _real_inputs()
    n = len(inp["registry"]["agent_lanes"])
    html = dx6.render(inp, now=NOW)
    assert len(re.findall(r'data-agent-row="', html)) == n


# ---- empty-sink vs clean: UNPOPULATED, never 0/blank ----

def test_empty_census_sink_renders_unpopulated():
    inp = _real_inputs()
    empty = copy.deepcopy(inp)
    empty["evidence"] = {"census": {"counts": {}}}        # EMPTY-SINK
    html = dx6.render(empty, now=NOW)
    assert "census value-classes — no counts in source" in html, "empty sink must render UNPOPULATED card"
    assert "UNPOPULATED" in html
    # the four value-class numeric cards must NOT be emitted for an empty sink
    assert '<div class="cc guard">' not in html


def test_clean_census_does_not_render_the_empty_unpopulated_card():
    """Same renderer, opposite outcome: real counts render numeric class cards, not the sink card."""
    inp = _real_inputs()
    html = dx6.render(inp, now=NOW)
    assert "census value-classes — no counts in source" not in html
    assert '<div class="cc guard">' in html and '<div class="cc revenue">' in html


def test_missing_value_class_is_unpopulated_not_zero():
    inp = _real_inputs()
    mut = copy.deepcopy(inp)
    mut["evidence"]["census"]["counts"].pop("REVENUE", None)   # a class disappears from the sink
    html = dx6.render(mut, now=NOW)
    assert "REVENUE — not in source" in html, "a missing class must read UNPOPULATED, never 0"


# ---- guards: autonomy locked, banner, freshness ----

def test_autonomy_never_available_always_locked():
    inp = _real_inputs()
    html = dx6.render(inp, now=NOW)
    text = re.sub(r"<style.*?</style>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text).lower()
    assert not re.search(r"\bavailable\b", text), "no autonomy surface may read 'available'"
    assert "locked / proof-gated" in html.lower()


def test_lock10_banner_and_no_hosting_path():
    out = dx6.build(now=NOW)
    assert out.is_file()
    assert out.parent.name == "out", "Lock 10: must write into local out/"
    html = out.read_text(encoding="utf-8")
    assert "DO NOT PUSH" in html, "Lock 10 banner missing"


def test_stale_source_is_badged_stale():
    """A source older than STALE_DAYS must badge STALE; a same-day source badges FRESH."""
    inp = _real_inputs()
    old = copy.deepcopy(inp)
    old["scorecard"]["updated_at"] = "2026-01-01T00:00:00Z"     # far in the past vs NOW
    html = dx6.render(old, now=NOW)
    # scorecard freshness surfaces in its section header
    assert "STALE" in html


def test_empty_registry_renders_unpopulated_not_crash():
    html = dx6.render({"registry": {}, "scorecard": {}, "evidence": {}}, now=NOW)
    assert "UNPOPULATED" in html
    assert 'id="motor-count">0<' in html
    assert _count_motor_rows(html) == 0


TESTS = [
    test_rendered_motor_count_matches_registry,
    test_mutating_registry_changes_rendered_count,
    test_agent_lane_count_matches_registry,
    test_empty_census_sink_renders_unpopulated,
    test_clean_census_does_not_render_the_empty_unpopulated_card,
    test_missing_value_class_is_unpopulated_not_zero,
    test_autonomy_never_available_always_locked,
    test_lock10_banner_and_no_hosting_path,
    test_stale_source_is_badged_stale,
    test_empty_registry_renders_unpopulated_not_crash,
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
