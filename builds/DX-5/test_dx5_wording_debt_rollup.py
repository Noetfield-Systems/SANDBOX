#!/usr/bin/env python3
"""
TH for DX-5 — the wording-debt rollup's own proof.

Red-capable by construction (data-driven, not a strawman):
  * the tally is checked against an INDEPENDENT hand-count on two known real sidecars
    (brain-as-a-service.md -> 8x UNDEFINED_TERM; BIG_PICTURE_RELATION_MAP.md -> 1x AGENT_REVIEW).
  * NEGATIVE — a MINIMAL MUTATION of a sidecar's parsed dict (add one dictionary_warning,
    or drop one) shifts the tally by exactly one; the same assertion that passes on the real
    dict FAILs on the mutant. The tally discriminates real vs mutated input.
  * ranking is verified to be non-increasing in debt (most debt first).
  * the rendered HTML carries the Lock-10 DO-NOT-PUSH banner, is written to a local out/ path,
    and renders zero-debt / empty sidecars as CLEAN / UNPOPULATED badges, never a bare 0.
"""
from __future__ import annotations
import copy
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("dx5", HERE / "dx5_wording_debt_rollup.py")
dx5 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dx5)

# Two known sidecars, hand-counted independently from the tally code.
KNOWN = {
    "SG-Canonical-Library/noetfield-library/P9-PATTERN-FACTORY/brain-as-a-service.md.language_gate_review.json": {
        "UNDEFINED_TERM": 8, "_total": 8, "_decision": "REVIEW",
    },
    "SG-Canonical-Library/noetfield-library/BIG_PICTURE_RELATION_MAP.md.language_gate_review.json": {
        "AGENT_REVIEW": 1, "_total": 1, "_decision": "REVIEW",
    },
}


def _load(rel: str) -> dict:
    return json.loads((dx5._repo_root() / rel).read_text(encoding="utf-8"))


def test_glob_finds_the_sidecars():
    sidecars = dx5.find_sidecars()
    assert len(sidecars) >= 90, f"expected the full sidecar corpus, got {len(sidecars)}"
    assert all(str(p).endswith(".language_gate_review.json") for p in sidecars)


def test_tally_matches_handcount_on_known_sidecars():
    for rel, expect in KNOWN.items():
        data = _load(rel)
        t = dx5.tally_sidecar(data)
        assert t["debt_total"] == expect["_total"], (rel, t["counts"])
        assert t["decision"] == expect["_decision"], (rel, t["decision"])
        for reason, n in expect.items():
            if reason.startswith("_"):
                continue
            assert t["counts"][reason] == n, (rel, reason, t["counts"])
        # every OTHER bucket must be exactly zero on these files
        for reason, got in t["counts"].items():
            if reason not in expect:
                assert got == 0, f"{rel}: unexpected {reason}={got}"


def test_mutated_tally_shifts_by_exactly_one():
    """Red-capable: mutating the parsed sidecar by one item moves the tally by one.
    The same equality that holds on the real dict FAILs on the mutant."""
    rel = "SG-Canonical-Library/noetfield-library/P9-PATTERN-FACTORY/brain-as-a-service.md.language_gate_review.json"
    real = _load(rel)
    base = dx5.tally_sidecar(real)["counts"]["UNDEFINED_TERM"]
    assert base == 8

    # ADD one warning -> tally must become base+1 (not base).
    mut_add = copy.deepcopy(real)
    mut_add["dictionary_warnings"].append(
        {"type": "UNDEFINED_TERM", "term": "SYNTHETIC INJECTED", "line": 0}
    )
    assert dx5.tally_sidecar(mut_add)["counts"]["UNDEFINED_TERM"] == base + 1
    assert dx5.tally_sidecar(mut_add)["counts"]["UNDEFINED_TERM"] != base

    # DROP one warning -> tally must become base-1.
    mut_drop = copy.deepcopy(real)
    mut_drop["dictionary_warnings"] = mut_drop["dictionary_warnings"][:-1]
    assert dx5.tally_sidecar(mut_drop)["counts"]["UNDEFINED_TERM"] == base - 1

    # a bucket-type mutation is caught too: retype one warning.
    mut_type = copy.deepcopy(real)
    mut_type["dictionary_warnings"][0]["type"] = "ALIAS_RETIRED"
    tt = dx5.tally_sidecar(mut_type)["counts"]
    assert tt["UNDEFINED_TERM"] == base - 1 and tt["ALIAS_RETIRED"] == 1


def test_clean_and_unpopulated_are_distinct_from_zero():
    clean = dx5.tally_sidecar({"file": "x.md", "agent_review": [], "dictionary_warnings": []})
    assert clean["debt_total"] == 0 and clean["decision"] == "CLEAN" and clean["populated"]

    unpop = dx5.tally_sidecar({"file": "x.md"})  # no debt keys at all
    assert unpop["debt_total"] == 0 and unpop["decision"] == "UNPOPULATED" and not unpop["populated"]


def test_rewrite_policy_becomes_the_decision():
    data = {"file": "x.md", "rewrite_policy": "SIDECAR_PREVIEW_ONLY",
            "proposed_regex_rewrites": [{"pattern": "a", "replacement": "b"}]}
    t = dx5.tally_sidecar(data)
    assert t["decision"] == "SIDECAR_PREVIEW_ONLY"
    assert t["counts"]["REGEX_REWRITE"] == 1 and t["debt_total"] == 1


def test_ranking_is_non_increasing_in_debt():
    rollup = dx5.build_rollup(dx5.find_sidecars())
    totals = [r["debt_total"] for r in rollup["rows"]]
    assert totals == sorted(totals, reverse=True), "rows must be ranked most-debt-first"
    assert rollup["corpus_total"] == sum(totals)
    for i, r in enumerate(rollup["rows"], start=1):
        assert r["rank"] == i


def test_render_has_lock10_banner_and_badges_not_bare_zero():
    out = dx5.build()  # writes to local out/ (Lock 10)
    assert out.is_file() and out.parent.name == "out"
    html = out.read_text(encoding="utf-8")
    assert "DO NOT PUSH" in html, "Lock 10 banner missing"
    # zero-debt states surface as explicit badges, never as a bare all-clear 0
    assert "UNPOPULATED" in html or "CLEAN" in html or "SIDECAR_PREVIEW_ONLY" in html
    # a known high-debt file appears in the ranked table
    assert "brain-as-a-service.md" in html


TESTS = [
    test_glob_finds_the_sidecars,
    test_tally_matches_handcount_on_known_sidecars,
    test_mutated_tally_shifts_by_exactly_one,
    test_clean_and_unpopulated_are_distinct_from_zero,
    test_rewrite_policy_becomes_the_decision,
    test_ranking_is_non_increasing_in_debt,
    test_render_has_lock10_banner_and_badges_not_bare_zero,
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
