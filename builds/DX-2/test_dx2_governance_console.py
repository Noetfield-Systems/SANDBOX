#!/usr/bin/env python3
"""
TH for DX-2 — the Unified Governance Console's own proof.

Red-capable by construction: the positive fixture is the REAL rendered on-disk console
(built from the 4 auditor snapshots + the real template); the negative fixture is that
SAME artifact with ONE phrase flipped into an overclaim ("100% guaranteed certified
autonomous"). The repo language_gate (surface=public) is the judge.

  * all FOUR auditor sections render (receipt ledger, registry/motor, staleness, PR-conflict).
  * building the console writes NO receipt into any tracked receipts/ dir (the underlying
    audit_automation_surface_v1.py would, so the console snapshots instead of running it).
  * Lock 10 banner present; console written only to local out/.
  * Tier-3 / Tier-4 render LOCKED / proof-gated, never "available".
  * EMPTY-SINK / STALE distinguished from CLEAN: null stats render UNPOPULATED, not 0/blank.
  * synthetic metrics are watermarked 'SYNTHETIC — not a guaranteed claim'.
  * POSITIVE — the real rendered console does NOT FAIL the gate -> CHECK_OK.
  * NEGATIVE — a MINIMAL MUTATION (inject one overclaim) FAILs the gate -> CHECK_REJECTED.
  * minimality — negative differs from positive by exactly the injected phrase (no strawman).
  * the gate is not relaxed: the judge that passes the clean console is the one that FAILs the mutant.
  * dogfood writes no receipt into the tracked language_gate/receipts dir (scan/decide only).
"""
from __future__ import annotations
import html as _htmllib, importlib.util, json, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("dx2", HERE / "dx2_governance_console.py")
dx2 = importlib.util.module_from_spec(spec); spec.loader.exec_module(dx2)

SNAP = json.loads((HERE / "auditor_snapshots.json").read_text())
EXPECTED_AUDITOR_IDS = {"receipt_ledger", "registry_motor", "staleness_gate", "pr_conflict"}
OVERCLAIM_ANCHOR = "read-only view"
OVERCLAIM_INJECTION = "100% guaranteed certified autonomous"

# tracked receipt dirs that must NOT gain a file because of a console build.
TRACKED_RECEIPT_DIRS = [
    dx2._repo_root() / "language_gate" / "receipts",
    dx2._repo_root().parent / "sina-governance-SSOT" / "receipts",
]


def _real_console() -> str:
    out = dx2.build()
    assert out.is_file()
    return out.read_text(encoding="utf-8")


def _visible_text(html: str) -> str:
    html = re.sub(r"<style.*?</style>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<[^>]+>", " ", html)
    return _htmllib.unescape(html)


def _receipt_snapshot() -> dict:
    snap = {}
    for d in TRACKED_RECEIPT_DIRS:
        snap[str(d)] = {p.name for p in d.glob("*")} if d.exists() else set()
    return snap


def test_all_four_auditor_sections_render():
    html = _real_console()
    ids = {a["id"] for a in SNAP["auditors"]}
    assert ids == EXPECTED_AUDITOR_IDS, f"auditor set drifted: {ids}"
    for a in SNAP["auditors"]:
        assert a["title"] in html, f"missing rendered section for {a['title']}"
        assert f'data-auditor-id="{a["id"]}"' in html, f"missing card marker for {a['id']}"
    # exactly four auditor cards
    assert html.count('data-auditor-id=') == 4


def test_build_writes_no_receipt_into_any_tracked_dir():
    before = _receipt_snapshot()
    dx2.build()
    after = _receipt_snapshot()
    assert before == after, f"console build mutated a tracked receipts dir: {before} != {after}"


def test_console_writes_only_into_local_out_dir():
    out = dx2.build()
    assert out.parent == HERE / "out", "Lock 10: console must be written into local out/"
    assert "public" not in str(out).lower().replace("public surface", "")  # no hosting path token


def test_lock10_banner_present():
    html = _real_console()
    assert "DO NOT PUSH" in html, "Lock 10 banner missing"


def test_tier3_and_tier4_are_locked_never_available():
    html = _real_console()
    text = _visible_text(html).lower()
    assert html.count("LOCKED") >= 2, "Tier-3/Tier-4 must render LOCKED"
    assert "proof-gated" in html
    # no autonomy tier may be presented as generically 'available' (word-boundary)
    assert not re.search(r"\bavailable\b", text), "no tier may be labelled available"


def test_empty_sink_renders_unpopulated_not_zero():
    html = _real_console()
    # the PR-conflict snapshot has three null stats -> must show UNPOPULATED, never a green 0.
    pr = next(a for a in SNAP["auditors"] if a["id"] == "pr_conflict")
    assert all(s["value"] is None for s in pr["stats"]), "fixture drift: pr_conflict stats not null"
    assert "UNPOPULATED" in html
    assert "STALE" in html, "stale source must carry a freshness badge"


def test_synthetic_watermark_present():
    html = _real_console()
    assert "SYNTHETIC — not a guaranteed claim" in html, "synthetic metrics must be watermarked"


def test_positive_real_console_passes_gate():
    res = dx2.run_language_gate(_real_console(), surface="public")
    assert res["gate_decision"] != "FAIL", res
    assert res["verdict"] == "CHECK_OK", res


def test_negative_minimal_mutation_overclaim_fails_gate():
    clean = _real_console()
    assert OVERCLAIM_ANCHOR in clean, "anchor for the single-field flip is gone"
    mutant = clean.replace(OVERCLAIM_ANCHOR, OVERCLAIM_INJECTION, 1)
    assert mutant != clean
    res = dx2.run_language_gate(mutant, surface="public")
    assert res["gate_decision"] == "FAIL", res
    assert res["verdict"] == "CHECK_REJECTED", res
    kinds = {b["type"] for b in res["blockers"]}
    assert "OVERCLAIM" in kinds, res


def test_mutation_is_minimal_and_gate_is_not_relaxed():
    clean = _real_console()
    mutant = clean.replace(OVERCLAIM_ANCHOR, OVERCLAIM_INJECTION, 1)
    # minimality: reversing the single injection reproduces the clean artifact byte-for-byte
    assert mutant.replace(OVERCLAIM_INJECTION, OVERCLAIM_ANCHOR, 1) == clean
    # same judge, opposite verdicts -> passing the clean console is not green-by-construction
    assert dx2.run_language_gate(clean)["verdict"] == "CHECK_OK"
    assert dx2.run_language_gate(mutant)["verdict"] == "CHECK_REJECTED"


def test_dogfood_writes_no_receipt_into_tracked_gate_dir():
    receipts = dx2._repo_root() / "language_gate" / "receipts"
    before = {p.name for p in receipts.glob("*")} if receipts.exists() else set()
    dx2.run_language_gate(_real_console(), surface="public")
    after = {p.name for p in receipts.glob("*")} if receipts.exists() else set()
    assert before == after, "dogfood must not write a receipt into the tracked gate dir"


TESTS = [
    test_all_four_auditor_sections_render,
    test_build_writes_no_receipt_into_any_tracked_dir,
    test_console_writes_only_into_local_out_dir,
    test_lock10_banner_present,
    test_tier3_and_tier4_are_locked_never_available,
    test_empty_sink_renders_unpopulated_not_zero,
    test_synthetic_watermark_present,
    test_positive_real_console_passes_gate,
    test_negative_minimal_mutation_overclaim_fails_gate,
    test_mutation_is_minimal_and_gate_is_not_relaxed,
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
    import sys
    sys.exit(_main())
