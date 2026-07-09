#!/usr/bin/env python3
"""
TH for MO-8 — the dry-run scorer's own proof (RED-before-GREEN).

  * fully-ready SYNTHETIC draft scores 8/8 on the real predicates  (GREEN baseline).
  * a MINIMAL MUTATION of that ready draft (drop casl.unsubscribe_url) flips exactly
    one predicate to failed -> 7/8  (RED-before-GREEN on the PREDICATE SCORING: the
    scorer discriminates, it is not a rubber stamp that always says 8/8).
  * a not-ready synthetic draft scores strictly LOWER than the ready one.
  * STATE CAP: even the fully-ready 8/8 draft caps at founder_blocked with
    dispatch_now=False and send_authorized=False — full readiness does NOT unlock
    a send (this is designed move M05's whole point).
  * the send-safety detector has TEETH: a leaky record (state past founder_blocked,
    or dispatch_now=True) is flagged -> CHECK_REJECTED  (positive control; a clean
    pass therefore can't be a broken detector).
  * the send-token self-scan has TEETH: a positive-control line containing
    'send-broadcast' is flagged; the real tool source scans clean.
  * the on-disk ground queue stays [] and both ground files are byte-identical
    after running the tool (read-only, never enqueues, never sends).
  * verdict vocab is CHECK_OK/CHECK_REJECTED, never a bare governance PASS.
"""
from __future__ import annotations
import copy, hashlib, importlib.util, json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("mo8", HERE / "mo8_pulse_dispatch_dryrun.py")
mo8 = importlib.util.module_from_spec(spec); spec.loader.exec_module(mo8)

STATES = mo8.ground_states()


def test_ready_draft_scores_full_8_of_8():
    s = mo8.score_predicates(mo8.synthetic_draft(ready=True))
    assert s["readiness_score"] == "8/8", s
    assert s["predicates_failed"] == [], s
    assert s["all_predicates_ready"] is True, s


def test_minimal_mutation_drops_exactly_one_predicate():
    # GREEN baseline: ready draft is 8/8.
    ready = mo8.synthetic_draft(ready=True)
    assert mo8.score_predicates(ready)["readiness_score"] == "8/8"
    # MINIMAL MUTATION: remove one required field -> exactly one predicate fails.
    mutated = copy.deepcopy(ready)
    mutated["casl"]["unsubscribe_url"] = None
    s = mo8.score_predicates(mutated)
    assert s["readiness_score"] == "7/8", s
    assert s["predicates_failed"] == ["casl_unsubscribe"], s
    assert s["all_predicates_ready"] is False, s


def test_not_ready_draft_scores_strictly_lower():
    hi = mo8.score_predicates(mo8.synthetic_draft(ready=True))["readiness_fraction"]
    lo = mo8.score_predicates(mo8.synthetic_draft(ready=False))["readiness_fraction"]
    assert lo < hi, (lo, hi)
    assert lo < 1.0, lo


def test_state_capped_at_founder_blocked_even_when_fully_ready():
    rec = mo8.dry_run(mo8.synthetic_draft(ready=True), STATES)
    # Full 8/8 readiness...
    assert rec["readiness_score"] == "8/8"
    assert rec["all_predicates_ready"] is True
    # ...still capped: no send authorization.
    assert rec["highest_state_reached"] == "founder_blocked", rec
    assert rec["dispatch_now"] is False, rec
    assert rec["send_authorized"] is False, rec
    assert rec["verdict"] == "CHECK_OK", rec
    assert rec["label"] == "readiness score, NOT send authorization"
    # founder_blocked really is the ceiling in the ground state machine.
    assert STATES.index("approved_pending_send") > STATES.index("founder_blocked")


def test_send_safety_detector_catches_leaks_positive_control():
    good = mo8.dry_run(mo8.synthetic_draft(ready=True), STATES)
    assert mo8.enforce_send_safety(good, STATES) == []          # clean
    # Positive control A: state advanced past the cap.
    leak_state = copy.deepcopy(good); leak_state["highest_state_reached"] = "approved_pending_send"
    vs = mo8.enforce_send_safety(leak_state, STATES)
    assert vs and any("LEAK" in x for x in vs), vs
    # Positive control B: dispatch flipped on.
    leak_disp = copy.deepcopy(good); leak_disp["dispatch_now"] = True
    assert mo8.enforce_send_safety(leak_disp, STATES), "dispatch_now=True must be flagged"
    # Positive control C: send_authorized truthy.
    leak_auth = copy.deepcopy(good); leak_auth["send_authorized"] = True
    assert mo8.enforce_send_safety(leak_auth, STATES), "send_authorized truthy must be flagged"


def test_send_token_selfscan_has_teeth():
    # Positive control: a line that USES a send tool must be flagged.
    bad = "    client.send_broadcast('send-broadcast', payload)\n"
    assert mo8.scan_source_for_send_tokens(bad), "self-scan failed to flag a send-broadcast usage"
    # The real tool source scans clean (the token-definition line is excluded).
    real_src = (HERE / "mo8_pulse_dispatch_dryrun.py").read_text(encoding="utf-8")
    assert mo8.scan_source_for_send_tokens(real_src) == [], "tool source must not use a send tool"


def test_ground_queue_stays_empty_and_files_unmodified():
    ground = [mo8.QUEUE_PATH, mo8.GROUND_CHECKER]
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in ground}
    empty, n = mo8.queue_is_empty_on_disk()
    assert empty and n == 0, (empty, n)
    rc = subprocess.run([sys.executable, str(HERE / "mo8_pulse_dispatch_dryrun.py"), "--json"],
                        text=True, capture_output=True)
    assert rc.returncode == 0, f"clean dry-run should exit 0: {rc.stdout}{rc.stderr}"
    out = json.loads(rc.stdout)
    assert out["verdict"] == "CHECK_OK", out
    assert out["queue_empty_on_disk"] is True, out
    after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in ground}
    assert before == after, "dry-run modified a ground-truth file!"


def test_never_emits_bare_pass():
    for ready in (True, False):
        rec = mo8.dry_run(mo8.synthetic_draft(ready=ready), STATES)
        assert rec["verdict"] in ("CHECK_OK", "CHECK_REJECTED"), rec
        assert rec["pass_claimed"] is False
        assert rec["origin"] == "sandbox-advisory" and rec["authority"] == "none"


TESTS = [
    test_ready_draft_scores_full_8_of_8,
    test_minimal_mutation_drops_exactly_one_predicate,
    test_not_ready_draft_scores_strictly_lower,
    test_state_capped_at_founder_blocked_even_when_fully_ready,
    test_send_safety_detector_catches_leaks_positive_control,
    test_send_token_selfscan_has_teeth,
    test_ground_queue_stays_empty_and_files_unmodified,
    test_never_emits_bare_pass,
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
    sys.exit(_main())
