#!/usr/bin/env python3
"""
TH for MO-3 — the value-class cost attribution report's own proof (RED-before-GREEN).

  * REAL rules+census -> the join maps a KNOWN task_cell to its declared value_class:
    gateway_lead_capture is REVENUE per the rules AND lands in the REVENUE group.
  * a MINIMAL MUTATION of the real rules (flip gateway_lead_capture REVENUE->GUARD)
    moves that task_cell out of the REVENUE group into GUARD — mutating the rule
    changes the grouping (the exact red-capable requirement). No relaxation.
  * REAL census (META=22 > GUARD+REVENUE=8) trips the standing cost rule ->
    CHECK_REJECTED, mirroring the census's own audit_status=RED (the checker has teeth).
  * POSITIVE-CONTROL census (balanced counts) -> CHECK_OK: proves the checker is not
    always-fail (a zero-hit is reachable, so CHECK_REJECTED is not a stuck verdict).
  * seeding an empty REVENUE lane into a balanced census re-trips CHECK_REJECTED.
  * running the report leaves BOTH ground-truth files byte-identical (read-only).
  * verdict vocab is CHECK_OK/CHECK_REJECTED, never PASS.
"""
from __future__ import annotations
import copy, hashlib, importlib.util, json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("mo3", HERE / "mo3_value_class_cost.py")
mo3 = importlib.util.module_from_spec(spec); spec.loader.exec_module(mo3)

RULES = json.loads(mo3.DEFAULT_RULES.read_text())
EVIDENCE_PATH = mo3.newest_evidence()
EVIDENCE = json.loads(EVIDENCE_PATH.read_text())

# The one exact mapping we anchor the join on (declared in the real rules file).
ANCHOR_CELL = "gateway_lead_capture"
ANCHOR_CLASS = "REVENUE"


def _balanced_evidence() -> dict:
    """POSITIVE-CONTROL: a minimally-mutated census where META does NOT dominate and
    REVENUE is non-empty, so every standing cost rule is satisfied -> CHECK_OK."""
    ev = copy.deepcopy(EVIDENCE)
    ev["census"]["counts"] = {"GUARD": 10, "META": 5, "NONE": 2, "REVENUE": 6}
    return ev


def test_real_join_anchor_mapping_holds():
    # The rules DECLARE the mapping...
    assert RULES["by_task_cell"][ANCHOR_CELL]["value_class"] == ANCHOR_CLASS
    # ...and the report's grouping PLACES the cell in that value_class group.
    groups = mo3.group_task_cells(RULES)
    assert ANCHOR_CELL in groups[ANCHOR_CLASS], groups[ANCHOR_CLASS]
    assert not any(ANCHOR_CELL in cells for vc, cells in groups.items() if vc != ANCHOR_CLASS)


def test_minimal_rule_mutation_changes_grouping():
    # MINIMAL MUTATION of the real rules: flip the one anchor cell's value_class.
    mutated = copy.deepcopy(RULES)
    mutated["by_task_cell"][ANCHOR_CELL]["value_class"] = "GUARD"
    groups = mo3.group_task_cells(mutated)
    assert ANCHOR_CELL not in groups[ANCHOR_CLASS], "cell should have left REVENUE"
    assert ANCHOR_CELL in groups["GUARD"], "cell should now be grouped under GUARD"


def test_real_census_trips_cost_rule_rejected():
    res = mo3.attribute(RULES, EVIDENCE)
    assert res["verdict"] == "CHECK_REJECTED", res
    rules_hit = {v["rule"] for v in res["cost_rule_violations"]}
    assert "META cost > GUARD+REVENUE cost -> RED" in rules_hit, rules_hit
    # our verdict must agree with the census's own recorded audit_status
    assert res["census_audit_status"] == "RED"


def test_positive_control_balanced_census_ok():
    res = mo3.attribute(RULES, _balanced_evidence())
    assert res["verdict"] == "CHECK_OK", res
    assert res["cost_rule_violations"] == [], res


def test_empty_revenue_lane_reflips_to_rejected():
    ev = _balanced_evidence()
    assert mo3.attribute(RULES, ev)["verdict"] == "CHECK_OK"  # GREEN baseline
    ev["census"]["counts"]["REVENUE"] = 0                     # seed the fault
    res = mo3.attribute(RULES, ev)
    assert res["verdict"] == "CHECK_REJECTED", res
    assert any(v["rule"] == "REVENUE lane empty -> RED" for v in res["cost_rule_violations"])


def test_cost_totals_and_shares_come_from_census():
    res = mo3.attribute(RULES, EVIDENCE)
    counts = EVIDENCE["census"]["counts"]
    assert res["total_cost_loops"] == sum(counts.values())
    by_vc = {r["value_class"]: r["cost_loops"] for r in res["table"]}
    for vc, n in counts.items():
        assert by_vc[vc] == n, (vc, n, by_vc)


def test_report_is_read_only():
    files = [mo3.DEFAULT_RULES, EVIDENCE_PATH]
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    rc = subprocess.run([sys.executable, str(HERE / "mo3_value_class_cost.py")],
                        text=True, capture_output=True)
    assert rc.returncode == 1, f"real data should exit 1 (rejected): {rc.stdout}{rc.stderr}"
    after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    assert before == after, "report modified a ground-truth artifact!"


def test_never_emits_pass():
    for ev in (EVIDENCE, _balanced_evidence()):
        assert mo3.attribute(RULES, ev)["verdict"] in ("CHECK_OK", "CHECK_REJECTED")


TESTS = [test_real_join_anchor_mapping_holds,
         test_minimal_rule_mutation_changes_grouping,
         test_real_census_trips_cost_rule_rejected,
         test_positive_control_balanced_census_ok,
         test_empty_revenue_lane_reflips_to_rejected,
         test_cost_totals_and_shares_come_from_census,
         test_report_is_read_only,
         test_never_emits_pass]


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
