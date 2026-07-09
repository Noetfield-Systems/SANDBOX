#!/usr/bin/env python3
"""
TH for BR-3 — the CHESS->packet-lint bridge's own proof (RED-before-GREEN).

Fixtures are REAL on-disk P0-PGR packets; the negative case is a MINIMAL
MUTATION of a real packet (inject 'clean/simplify/delete' wording into its task
text). No strawman, no relaxation.

  * REAL plain packet (P0PGR-20260708-002, no CHESS risk words) -> CHECK_OK,
    ZERO CHESS reasons injected  (positive: accepted).
  * MINIMAL MUTATION of that plain packet (append 'clean / simplify / delete'
    to its task) -> CHECK_REJECTED, CHESS reasons injected  (RED-before-GREEN:
    the same packet was green; the injected wording makes it red).
  * REAL packet P0PGR-20260708-010 (naturally contains 'clean') is flagged
    as-is -> CHECK_REJECTED via likely_misread  (real artifact, no strawman).
  * REAL packet P0PGR-20260708-007 (contains 'spend') is flagged via the
    action=ASK_IF_IRREVERSIBLE branch, even with empty likely_misread.
  * POSITIVE CONTROL: a text containing 'delete' MUST make CHESS fire, so a
    zero-hit on the plain packet cannot be a broken/always-clean detector.
  * running the bridge leaves the packet file byte-identical (read-only) and
    never mutates the in-memory packet dict.
  * verdict vocab is CHECK_OK/CHECK_REJECTED, never a bare governance PASS.
"""
from __future__ import annotations
import copy, hashlib, importlib.util, json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("br3", HERE / "br3_chess_packetlint_bridge.py")
br3 = importlib.util.module_from_spec(spec); spec.loader.exec_module(br3)

OUTBOX = br3.REPO / "receipts" / "p0pgr" / "outbox"
PLAIN_PATH = OUTBOX / "P0PGR-20260708-002.json"      # no CHESS risk words
REAL_CLEAN_PATH = OUTBOX / "P0PGR-20260708-010.json"  # naturally says 'clean'
REAL_SPEND_PATH = OUTBOX / "P0PGR-20260708-007.json"  # naturally says 'spend'

PLAIN = json.loads(PLAIN_PATH.read_text())
REAL_CLEAN = json.loads(REAL_CLEAN_PATH.read_text())
REAL_SPEND = json.loads(REAL_SPEND_PATH.read_text())


def _mutated_plain() -> dict:
    """MINIMAL MUTATION of the real plain packet: append clarity/removal wording
    to its task. Nothing else changes; the bridge and CHESS tool are untouched."""
    p = copy.deepcopy(PLAIN)
    p["task"] = p.get("task", "") + " Also clean and simplify the deck and delete stale sections."
    return p


def test_real_plain_packet_is_chess_clean():
    res = br3.bridge(PLAIN)
    assert res["verdict"] == "CHECK_OK", res
    assert res["injected_chess_reasons"] == [], res
    # bridge preserves the linter's own verdict verbatim (its native vocab)
    assert res["lint_verdict"] in ("PASS", "REPAIR_CANDIDATE")


def test_minimally_mutated_plain_flips_to_rejected():
    # GREEN baseline: the unmutated real packet is CHESS-clean.
    assert br3.bridge(PLAIN)["verdict"] == "CHECK_OK"
    # Inject 'clean/simplify/delete' into the task -> RED.
    res = br3.bridge(_mutated_plain())
    assert res["verdict"] == "CHECK_REJECTED", res
    assert res["injected_chess_reasons"], res
    # the injection is CHESS-derived (likely_misread from the clarity wording)
    assert any("likely_misread" in r for r in res["injected_chess_reasons"]), res


def test_real_clean_packet_flagged_as_is():
    res = br3.bridge(REAL_CLEAN)
    assert res["verdict"] == "CHECK_REJECTED", res
    assert res["chess_likely_misread"], res
    assert any("likely_misread" in r for r in res["injected_chess_reasons"]), res


def test_real_spend_packet_flagged_via_ask_branch():
    res = br3.bridge(REAL_SPEND)
    assert res["verdict"] == "CHECK_REJECTED", res
    assert res["chess_action"] == "ASK_IF_IRREVERSIBLE", res
    assert any("ASK_IF_IRREVERSIBLE" in r for r in res["injected_chess_reasons"]), res


def test_positive_control_chess_fires_on_delete():
    """Guard against a broken/always-clean detector: 'delete' MUST make CHESS
    produce reasons; if this ever goes empty, a zero-hit elsewhere is suspect."""
    chess = br3.run_chess("please delete and simplify everything")
    assert br3.chess_reasons(chess), "positive control failed: CHESS emitted no reasons on 'delete/simplify'"


def test_injected_reasons_extend_not_replace_lint_reasons():
    """Bridge ADDS CHESS reasons on top of the lint result, never drops the
    linter's own reasons."""
    m = _mutated_plain()
    res = br3.bridge(m)
    for lr in res["lint_reasons"]:
        assert lr in res["reasons"], "bridge dropped a base lint reason"
    for cr in res["injected_chess_reasons"]:
        assert cr in res["reasons"], "bridge dropped an injected chess reason"
    assert len(res["reasons"]) == len(res["lint_reasons"]) + len(res["injected_chess_reasons"])


def test_bridge_is_read_only():
    before = hashlib.sha256(PLAIN_PATH.read_bytes()).hexdigest()
    snapshot = copy.deepcopy(PLAIN)
    rc = subprocess.run([sys.executable, str(HERE / "br3_chess_packetlint_bridge.py"),
                         str(REAL_CLEAN_PATH)], text=True, capture_output=True)
    assert rc.returncode == 1, f"real 'clean' packet should exit 1 (hit): {rc.stdout}{rc.stderr}"
    after = hashlib.sha256(PLAIN_PATH.read_bytes()).hexdigest()
    assert before == after, "bridge modified a ground-truth packet file!"
    # in-memory packet dict not mutated by bridge()
    br3.bridge(PLAIN)
    assert PLAIN == snapshot, "bridge mutated the in-memory packet dict!"


def test_exit_code_matches_hit():
    clean = subprocess.run([sys.executable, str(HERE / "br3_chess_packetlint_bridge.py"),
                            str(PLAIN_PATH)], text=True, capture_output=True)
    assert clean.returncode == 0, f"plain packet must exit 0: {clean.stdout}"
    hit = subprocess.run([sys.executable, str(HERE / "br3_chess_packetlint_bridge.py"),
                          str(REAL_CLEAN_PATH)], text=True, capture_output=True)
    assert hit.returncode == 1, f"flagged packet must exit 1: {hit.stdout}"


def test_never_emits_bare_pass():
    for p in (PLAIN, REAL_CLEAN, REAL_SPEND, _mutated_plain()):
        assert br3.bridge(p)["verdict"] in ("CHECK_OK", "CHECK_REJECTED")


TESTS = [test_real_plain_packet_is_chess_clean,
         test_minimally_mutated_plain_flips_to_rejected,
         test_real_clean_packet_flagged_as_is,
         test_real_spend_packet_flagged_via_ask_branch,
         test_positive_control_chess_fires_on_delete,
         test_injected_reasons_extend_not_replace_lint_reasons,
         test_bridge_is_read_only,
         test_exit_code_matches_hit,
         test_never_emits_bare_pass]


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
