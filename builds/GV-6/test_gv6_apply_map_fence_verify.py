#!/usr/bin/env python3
"""
TH for GV-6 — the apply-map fence validator's own proof.

Runs the DLM pipeline ONCE in-process with OUTPUT_DIR/RECEIPTS_DIR monkeypatched to a
TEMP dir (exact pattern from catalog/builds/TH-2), so NOTHING is written into the tracked
decision_language_machine_v1/output|receipts (append-only, Lock 5). The persisted
apply_map.json + sibling processed.json produced there are the REAL on-disk artifacts
every fixture is a minimal mutation of. No strawman is authored from scratch; no schema
is relaxed to pass.

  * REAL default partial_batch=True apply_map (no picks) -> CHECK_REJECTED: its 51
    unvalidated ADVISOR/FOUNDER items are dropped silently (fence leak, founder-gated).
    This is current behavior leaking — GV-6 FLAGS it, it does not patch the fence.
  * a MINIMAL MUTATION of that real map (add the one accountability field
    deferred_unvalidated = the dropped ids) -> CHECK_OK. One field, no schema relaxation.
  * from that conformant map, moving ONE machine_closed id into picks -> CHECK_REJECTED (a).
  * from that conformant map, adding ONE auto-submit field (auto_submit) -> CHECK_REJECTED (b).
  * removing the accountability field re-flips to CHECK_REJECTED -> invariant (c) is never relaxed.
  * GV-6 never re-calls build_apply_map and never emits PASS (vocab CHECK_OK/CHECK_REJECTED).
"""
from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def _repo_root() -> Path:
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                             cwd=Path(__file__).resolve().parent, text=True, capture_output=True, check=True)
        return Path(out.stdout.strip())
    except Exception:
        return Path(__file__).resolve().parents[3]


REPO = _repo_root()
HERE = Path(__file__).resolve().parent
DLM_DIR = REPO / "decision_language_machine_v1"
FIXTURE = DLM_DIR / "test_fixtures" / "form_official_80_open_v1.json"

# make DLM + language_gate importable in-process (TH-2 pattern)
for p in (str(DLM_DIR), str(REPO / "language_gate")):
    if p not in sys.path:
        sys.path.insert(0, p)

spec = importlib.util.spec_from_file_location("gv6", HERE / "gv6_apply_map_fence_verify.py")
gv6 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gv6)


def _real_run() -> tuple[dict, set[str]]:
    """Run the DLM pipeline once with all writes redirected to a temp dir; return the
    persisted apply_map (default partial_batch=True, no picks) + its advisor/founder universe.
    ZERO writes to the tracked DLM output/receipts dirs."""
    import dlm_core_v1 as core
    import dlm_pipeline_v1 as pipe
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "output"
        rec = Path(tmp) / "receipts"
        core.OUTPUT_DIR = out           # write_run_manifest / write_stage_receipt
        core.RECEIPTS_DIR = rec
        pipe.OUTPUT_DIR = out           # run_pipeline writes apply_map/processed directly
        summary = pipe.run_pipeline(FIXTURE)   # partial_batch default True, no validated picks
        apply_map = json.loads(Path(out, f"{summary['run_id']}.apply_map.json").read_text())
        processed = json.loads(Path(summary["processed"]).read_text())
    return apply_map, gv6.advisor_founder_ids(processed)


REAL_MAP, UNIVERSE = _real_run()


def _conformant() -> dict:
    """Minimal mutation of the REAL map: add the single accountability field the fence
    is missing (deferred_unvalidated = the ids it dropped). Nothing else changes."""
    m = copy.deepcopy(REAL_MAP)
    dropped = sorted(UNIVERSE - gv6._pick_ids(m))
    m["deferred_unvalidated"] = dropped
    return m


def test_real_default_partial_batch_map_is_flagged_for_silent_drop():
    # Sanity: the real artifact really is the leaky default (unvalidated items exist, none accounted)
    assert UNIVERSE, "fixture should classify ADVISOR/FOUNDER items"
    assert REAL_MAP.get("target_form") == "FORM_OFFICIAL"
    assert "deferred_unvalidated" not in REAL_MAP, "real map has no accountability list — that is the leak"
    res = gv6.verify(REAL_MAP, UNIVERSE)
    assert res["verdict"] == "CHECK_REJECTED", res
    assert res["founder_gated_finding"] is True, "silent drop must be a founder-gated finding"
    assert set(res["fence_leaks"]) == UNIVERSE, "every unvalidated item should be flagged as leaked"
    assert any(v.startswith("(c)") for v in res["violations"])


def test_minimally_mutated_conformant_is_accepted():
    res = gv6.verify(_conformant(), UNIVERSE)
    assert res["verdict"] == "CHECK_OK", res
    assert res["fence_leaks"] == []
    assert res["founder_gated_finding"] is False


def test_machine_closed_intersecting_picks_is_rejected():
    # (a): move ONE machine_closed id into picks — a real minimal mutation of the conformant map.
    m = _conformant()
    mc = m.get("machine_closed_without_founder") or []
    assert mc, "real map should have machine_closed ids to mutate"
    leaked_id = mc[0]
    m["picks"] = list(m.get("picks") or []) + [{"id": leaked_id, "pick": "A"}]
    res = gv6.verify(m, UNIVERSE)
    assert res["verdict"] == "CHECK_REJECTED", res
    assert any(v.startswith("(a)") and leaked_id in v for v in res["violations"]), res["violations"]


def test_official_form_autosubmit_field_is_rejected():
    # (b): add ONE auto-submit field to the conformant OFFICIAL map.
    m = _conformant()
    m["auto_submit"] = True
    res = gv6.verify(m, UNIVERSE)
    assert res["verdict"] == "CHECK_REJECTED", res
    assert any(v.startswith("(b)") and "auto_submit" in v for v in res["violations"]), res["violations"]


def test_no_relaxation_removing_accountability_reflips():
    # invariant (c) is never relaxed: strip the one field that made it conformant -> reject again.
    good = _conformant()
    bad = copy.deepcopy(good)
    del bad["deferred_unvalidated"]
    assert gv6.verify(bad, UNIVERSE)["verdict"] == "CHECK_REJECTED"


def test_never_recalls_build_apply_map_and_never_emits_pass():
    # data-only verifier: it must not import/call build_apply_map, and vocab is CHECK_OK/CHECK_REJECTED.
    src = (HERE / "gv6_apply_map_fence_verify.py").read_text()
    assert "build_apply_map(" not in src, "GV-6 must NOT call build_apply_map at verify time"
    assert "import dlm_apply_map" not in src and "from dlm_apply_map" not in src, \
        "GV-6 must not import the fence module — it validates the persisted artifact by data only"
    for m in (REAL_MAP, _conformant()):
        assert gv6.verify(m, UNIVERSE)["verdict"] in ("CHECK_OK", "CHECK_REJECTED")


def test_running_tool_writes_verdict_to_scratch_never_edits_subject():
    import hashlib
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        am = tmp / "run0.apply_map.json"
        pr = tmp / "run0.processed.json"
        am.write_text(json.dumps(REAL_MAP, indent=2))
        # minimal processed shaped so the sibling-derivation path exercises invariant (c)
        pr.write_text(json.dumps([{"id": i, "classification": "ADVISOR_REVIEW"} for i in sorted(UNIVERSE)]))
        before = hashlib.sha256(am.read_bytes()).hexdigest()
        vdir = tmp / "verdicts"
        rc = subprocess.run([sys.executable, str(HERE / "gv6_apply_map_fence_verify.py"),
                             "--apply-map", str(am), "--emit-verdict-dir", str(vdir)],
                            text=True, capture_output=True)
        assert rc.returncode == 1, f"real leaky map should exit 1 (rejected); out={rc.stdout}{rc.stderr}"
        assert (vdir / "verdict-run0.apply_map.json").is_file(), "verdict not written to scratch"
        after = hashlib.sha256(am.read_bytes()).hexdigest()
        assert before == after, "subject apply_map was modified!"


TESTS = [
    test_real_default_partial_batch_map_is_flagged_for_silent_drop,
    test_minimally_mutated_conformant_is_accepted,
    test_machine_closed_intersecting_picks_is_rejected,
    test_official_form_autosubmit_field_is_rejected,
    test_no_relaxation_removing_accountability_reflips,
    test_never_recalls_build_apply_map_and_never_emits_pass,
    test_running_tool_writes_verdict_to_scratch_never_edits_subject,
]


def _main() -> int:
    failed = 0
    for t in TESTS:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {t.__name__}: {e}")
    print(f"\n{len(TESTS)-failed}/{len(TESTS)} green")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_main())
