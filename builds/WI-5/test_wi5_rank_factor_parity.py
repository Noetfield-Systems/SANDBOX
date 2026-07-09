#!/usr/bin/env python3
"""
TH for WI-5 — proof the externalized rank-factor table is at parity with the module.

  * the on-disk phase2_rank_factors.json recomputes to the SAME ranking + SAME per-move
    scores as the live in-module WEIGHTS/FACTORS constants -> CHECK_OK.
  * the transported constants are verbatim (WEIGHTS + every FACTORS[mid] deep-equal).
  * RED-CAPABLE: a MINIMAL MUTATION of one factor value in a copy of the JSON changes
    the ranking and/or a score, and the verifier CHECK_REJECTs it (the test discriminates).
  * mutating a single WEIGHT verbatim-check also re-rejects (no relaxation).
  * verify() never runs the ranker main(): no queue file is written (no side effects).
  * verdict vocab is CHECK_OK/CHECK_REJECTED, never PASS.
  * running the tool leaves the source module byte-identical (append-only).
"""
from __future__ import annotations
import copy, hashlib, importlib.util, json, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("wi5", HERE / "wi5_rank_factor_parity.py")
wi5 = importlib.util.module_from_spec(spec); spec.loader.exec_module(wi5)

DATA = json.loads((HERE / "phase2_rank_factors.json").read_text())


def _write_tmp(data: dict) -> Path:
    tmp = Path(tempfile.mkdtemp()) / "mutated.json"
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    return tmp


def test_real_json_is_at_parity_with_module():
    res = wi5.verify(HERE / "phase2_rank_factors.json")
    assert res["verdict"] == "CHECK_OK", res
    assert res["parity_reasons"] == [], res
    assert res["ranking_from_json"] == res["ranking_from_module"]
    assert res["scores_from_json"] == res["scores_from_module"]


def test_transported_constants_are_verbatim():
    mod_w, mod_f = wi5.load_module_constants()
    assert DATA["weights"] == mod_w
    assert DATA["factors"] == mod_f


def test_minimal_factor_mutation_changes_ranking_and_is_rejected():
    # M09 is the lowest-ranked move (direct_revenue=0.1). Bump it to 1.0 -> it
    # jumps up the order AND its score changes: the check MUST catch this.
    mutated = copy.deepcopy(DATA)
    before = mutated["factors"]["M09"]["direct_revenue"]
    mutated["factors"]["M09"]["direct_revenue"] = 1.0
    assert before != 1.0
    res = wi5.verify(_write_tmp(mutated))
    assert res["verdict"] == "CHECK_REJECTED", res
    # discrimination proof: the JSON-derived ranking/score actually diverged
    assert res["ranking_from_json"] != res["ranking_from_module"] \
        or res["scores_from_json"] != res["scores_from_module"]
    assert res["scores_from_json"]["M09"] != res["scores_from_module"]["M09"]


def test_minimal_weight_mutation_is_rejected():
    mutated = copy.deepcopy(DATA)
    mutated["weights"]["direct_revenue"] = mutated["weights"]["direct_revenue"] + 1
    res = wi5.verify(_write_tmp(mutated))
    assert res["verdict"] == "CHECK_REJECTED", res
    assert any("WEIGHTS" in r for r in res["parity_reasons"]), res


def test_verify_writes_no_queue_side_effect():
    # the module would write receipts/p0pgr/phase2_queue_v1.json if main() ran;
    # verify() must not. Assert the tool exit-0 path emits no such file mtime change.
    queue = wi5.REPO / "receipts" / "p0pgr" / "phase2_queue_v1.json"
    before = queue.stat().st_mtime_ns if queue.exists() else None
    wi5.verify(HERE / "phase2_rank_factors.json")
    after = queue.stat().st_mtime_ns if queue.exists() else None
    assert before == after, "verify() must not touch the ranker's queue output"


def test_never_emits_pass():
    for dp in (HERE / "phase2_rank_factors.json",):
        assert wi5.verify(dp)["verdict"] in ("CHECK_OK", "CHECK_REJECTED")


def test_running_tool_never_edits_source_module():
    before = hashlib.sha256(wi5.SOURCE_MODULE.read_bytes()).hexdigest()
    rc = subprocess.run([sys.executable, str(HERE / "wi5_rank_factor_parity.py")],
                        text=True, capture_output=True)
    assert rc.returncode == 0, rc.stderr
    after = hashlib.sha256(wi5.SOURCE_MODULE.read_bytes()).hexdigest()
    assert before == after, "source module was modified!"


TESTS = [test_real_json_is_at_parity_with_module, test_transported_constants_are_verbatim,
         test_minimal_factor_mutation_changes_ranking_and_is_rejected,
         test_minimal_weight_mutation_is_rejected, test_verify_writes_no_queue_side_effect,
         test_never_emits_pass, test_running_tool_never_edits_source_module]


def _main() -> int:
    failed = 0
    for t in TESTS:
        try: t(); print(f"PASS  {t.__name__}")
        except AssertionError as e: failed += 1; print(f"FAIL  {t.__name__}: {e}")
    print(f"\n{len(TESTS)-failed}/{len(TESTS)} green")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_main())
