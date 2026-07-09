#!/usr/bin/env python3
"""
TH-5 — Offline receipt-replay verifier harness  (catalog build B1 · TH-5)

Replays the CF verifier worker's PASS-eligibility rule over captured non-PASS
receipt fixtures, entirely offline (never calls the live worker /run — which would
mint a real GitHub App token and overwrite the live 'latest' KV).

The worker's rule (workers/github-app-advisory/index.js):
    L450  const secondaryAccountProven = env.CF_ACCOUNT_ID === SECONDARY_CF_ACCOUNT_ID
    L462  pass_eligible: edgeExecutionProven && secondaryAccountProven
It is a 2-line inline expression (not a pure exported fn), so it is mirrored here
in Python and DRIFT-GUARDED: the test asserts index.js still contains both exact
expressions — if the worker's rule changes, the guard fails and flags re-lift.

Replay verdict for a receipt:
  * claims PASS (pass_claimed or status==PASS) AND eligible AND account matches AND
    stored pass_eligible field consistent  -> CHECK_OK
  * claims PASS but not eligible / account mismatch / inconsistent stored field -> CHECK_REJECTED (tampered)
  * does not claim PASS                                                          -> NON_PASS (correctly not a pass)

Positive control MUST be ACCEPTED (a replay that rejects everything passes trivially).
"""
from __future__ import annotations
import copy, json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=HERE,
                           text=True, capture_output=True, check=True).stdout.strip())
INDEX_JS = REPO / "workers" / "github-app-advisory" / "index.js"
SECONDARY_CF_ACCOUNT_ID = "b7282b4a5c17b84d62e3ef8866b878f8"   # mirror index.js L9

STEP6 = json.loads((REPO / "receipts" / "step6-deliberate-non-pass-receipt.json").read_text())
STEP8 = json.loads((REPO / "receipts" / "step8-tampered-independence-receipt.json").read_text())


def recompute_pass_eligible(r: dict) -> bool:
    return bool(r.get("edge_execution_proven")) and bool(r.get("secondary_account_proven"))  # mirror L462


def replay(r: dict) -> dict:
    eligible = recompute_pass_eligible(r)
    account_ok = r.get("cf_account_id") == SECONDARY_CF_ACCOUNT_ID
    claims_pass = bool(r.get("pass_claimed")) or r.get("status") == "PASS" or r.get("result") == "PASS"
    stored_consistent = ("pass_eligible" not in r) or (bool(r.get("pass_eligible")) == eligible)
    reasons = []
    if not claims_pass:
        return {"verdict": "NON_PASS", "reasons": ["receipt does not claim PASS"], "recomputed_eligible": eligible}
    if not eligible:
        reasons.append("claims PASS but recomputed pass_eligible is False (edge & secondary not both proven)")
    if not account_ok:
        reasons.append("cf_account_id is not the secondary (independent) account")
    if not stored_consistent:
        reasons.append("stored pass_eligible field disagrees with recomputed value (tampered)")
    return {"verdict": "CHECK_OK" if not reasons else "CHECK_REJECTED", "reasons": reasons, "recomputed_eligible": eligible}


def _positive_control() -> dict:
    r = copy.deepcopy(STEP8)                          # minimal mutation of a REAL receipt
    r["secondary_account_proven"] = True              # make it genuinely independent
    r["pass_eligible"] = True                         # consistent with recomputed
    r["status"] = "PASS"; r["result"] = "PASS"; r["pass_claimed"] = True
    r["cf_account_id"] = SECONDARY_CF_ACCOUNT_ID
    return r


def test_drift_guard_source_rule_unchanged():
    src = INDEX_JS.read_text()
    assert "pass_eligible: edgeExecutionProven && secondaryAccountProven" in src, "worker pass rule changed — re-lift TH-5"
    assert "env.CF_ACCOUNT_ID === SECONDARY_CF_ACCOUNT_ID" in src, "secondary-account rule changed — re-lift TH-5"


def test_step8_tampered_pass_is_rejected():
    res = replay(STEP8)
    assert res["verdict"] == "CHECK_REJECTED", res
    assert any("secondary" in x or "pass_eligible" in x for x in res["reasons"]), res


def test_step6_fail_is_non_pass():
    assert replay(STEP6)["verdict"] == "NON_PASS", replay(STEP6)


def test_positive_control_is_accepted():
    assert replay(_positive_control())["verdict"] == "CHECK_OK", replay(_positive_control())


def test_not_reject_everything():
    # a replay that rejected everything would fail the positive control above; assert both outcomes occur
    verdicts = {replay(STEP8)["verdict"], replay(_positive_control())["verdict"]}
    assert verdicts == {"CHECK_REJECTED", "CHECK_OK"}, verdicts


TESTS = [test_drift_guard_source_rule_unchanged, test_step8_tampered_pass_is_rejected,
         test_step6_fail_is_non_pass, test_positive_control_is_accepted, test_not_reject_everything]


def _main() -> int:
    failed = 0
    for t in TESTS:
        try: t(); print(f"PASS  {t.__name__}")
        except AssertionError as e: failed += 1; print(f"FAIL  {t.__name__}: {e}")
    print(f"\n{len(TESTS)-failed}/{len(TESTS)} green")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_main())
