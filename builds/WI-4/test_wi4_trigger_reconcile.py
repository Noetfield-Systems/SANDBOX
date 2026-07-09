#!/usr/bin/env python3
"""
TH for WI-4 — the trigger reconciler's own proof (RED-before-GREEN).

  * REAL registries -> CHECK_REJECTED: 7 real dangling refs reported as a finding
    (loops declare retires_trigger_ids the registry never defines). No relaxation.
  * a MINIMAL MUTATION of the real registry (define every referenced trigger_id)
    reconciles clean -> CHECK_OK  (proves the checker is not always-fail).
  * seeding one dangling ref into that clean copy flips it back -> CHECK_REJECTED
    (RED-before-GREEN: green passes, the seed makes it red, seed id is cited).
  * removing a needed definition from the clean copy re-rejects (no relaxation).
  * running the reconciler leaves BOTH ground-truth files byte-identical (read-only).
  * verdict vocab is CHECK_OK/CHECK_REJECTED, never PASS.
"""
from __future__ import annotations
import copy, hashlib, importlib.util, json, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("wi4", HERE / "wi4_trigger_reconcile.py")
wi4 = importlib.util.module_from_spec(spec); spec.loader.exec_module(wi4)

LOOPS = json.loads(wi4.DEFAULT_LOOPS.read_text())
REGISTRY = json.loads(wi4.DEFAULT_REGISTRY.read_text())

REAL_DANGLING = {
    "FT-FOUNDER-TIER-ROUTING", "FT-FOUNDER-MISSION-PICK", "FT-FOUNDER-VALIDATOR-CHECK",
    "FT-DUP-IMPL-FOUNDER", "FT-FOUNDER-RECEIPT-READ", "FT-FOUNDER-CI-TRIAGE",
    "FT-FOUNDER-UNCERTAINTY",
}


def _clean_registry() -> dict:
    """MINIMAL MUTATION of the real registry: add a trigger definition for every
    id the loops file references but the registry currently omits. Nothing else
    changes; the checker is untouched."""
    reg = copy.deepcopy(REGISTRY)
    defined = {t["trigger_id"] for t in reg["triggers"]}
    for lid, ref in wi4.referenced_edges(LOOPS):
        if ref not in defined:
            reg["triggers"].append({"trigger_id": ref, "status": "active",
                                    "current_blocker": "(defined for reconcile fixture)"})
            defined.add(ref)
    return reg


def test_real_registries_report_dangling_as_finding():
    res = wi4.reconcile(LOOPS, REGISTRY)
    assert res["verdict"] == "CHECK_REJECTED", res
    got = {d["retires_trigger_id"] for d in res["dangling_references"]}
    assert got == REAL_DANGLING, f"real dangling set mismatch: {got}"
    # each dangling ref is attributed to the loop that declared it
    for d in res["dangling_references"]:
        assert d["loop_id"], d


def test_minimally_mutated_clean_registry_reconciles():
    res = wi4.reconcile(LOOPS, _clean_registry())
    assert res["verdict"] == "CHECK_OK", res
    assert res["dangling_count"] == 0, res


def test_seeded_dangling_flips_clean_to_rejected():
    # GREEN baseline: clean pair passes.
    assert wi4.reconcile(LOOPS, _clean_registry())["verdict"] == "CHECK_OK"
    # Seed ONE dangling ref into an in-memory loops copy -> RED.
    loops = copy.deepcopy(LOOPS)
    loops["loops"][0]["retires_trigger_ids"].append("FT-SEEDED-PHANTOM")
    res = wi4.reconcile(loops, _clean_registry())
    assert res["verdict"] == "CHECK_REJECTED", res
    assert any(d["retires_trigger_id"] == "FT-SEEDED-PHANTOM"
               for d in res["dangling_references"]), res


def test_no_relaxation_removing_a_definition_reflips():
    clean = _clean_registry()
    # FT-MERGE-T0-T1 is referenced by LP-MERGE; drop its definition -> must re-reject.
    clean["triggers"] = [t for t in clean["triggers"] if t["trigger_id"] != "FT-MERGE-T0-T1"]
    res = wi4.reconcile(LOOPS, clean)
    assert res["verdict"] == "CHECK_REJECTED", res
    assert any(d["retires_trigger_id"] == "FT-MERGE-T0-T1" for d in res["dangling_references"])


def test_reconciler_is_read_only():
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in (wi4.DEFAULT_LOOPS, wi4.DEFAULT_REGISTRY)}
    rc = subprocess.run([sys.executable, str(HERE / "wi4_trigger_reconcile.py")],
                        text=True, capture_output=True)
    assert rc.returncode == 1, f"real registries should exit 1 (rejected): {rc.stdout}{rc.stderr}"
    after = {p: hashlib.sha256(p.read_bytes()).hexdigest()
             for p in (wi4.DEFAULT_LOOPS, wi4.DEFAULT_REGISTRY)}
    assert before == after, "reconciler modified a ground-truth registry!"


def test_never_emits_pass():
    for reg in (REGISTRY, _clean_registry()):
        assert wi4.reconcile(LOOPS, reg)["verdict"] in ("CHECK_OK", "CHECK_REJECTED")


TESTS = [test_real_registries_report_dangling_as_finding,
         test_minimally_mutated_clean_registry_reconciles,
         test_seeded_dangling_flips_clean_to_rejected,
         test_no_relaxation_removing_a_definition_reflips,
         test_reconciler_is_read_only,
         test_never_emits_pass]


def _main() -> int:
    failed = 0
    for t in TESTS:
        try: t(); print(f"PASS  {t.__name__}")
        except AssertionError as e: failed += 1; print(f"FAIL  {t.__name__}: {e}")
    print(f"\n{len(TESTS)-failed}/{len(TESTS)} green")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_main())
