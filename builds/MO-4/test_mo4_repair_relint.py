#!/usr/bin/env python3
"""
TH for MO-4 — the repair-candidate re-linter's own proof (RED-before-GREEN).

Ground truth: a real on-disk packet from receipts/p0pgr/outbox/ (currently
lint-clean) and the ground linter scripts/p0pgr_packet_lint_v1.py.

  * a REAL outbox packet re-lints clean -> CHECK_OK (positive; no relaxation).
  * a MINIMAL MUTATION of that same real packet (flip ONE value:
    hard_block_allowed_reasons -> a bogus enum) makes the ground linter flag it,
    and MO-4 reports CHECK_REJECTED citing that exact reason (positive control:
    if this packet is NOT flagged, the detector is broken / regex false-clean).
  * a second independent minimal mutation (DROP the required execution_mode
    field) is also flagged -> CHECK_REJECTED (detector isn't tied to one reason).
  * repair-candidate diff semantics: a candidate whose packet still carries its
    filed reason -> still_present, CHECK_REJECTED (repair NOT confirmed); a
    candidate whose packet re-lints clean -> resolved, CHECK_OK (repair confirmed).
  * a candidate whose referenced packet is missing -> UNRESOLVED_PACKET,
    CHECK_REJECTED (cannot re-verify; reported, not hidden).
  * MO-4 mutates NOTHING: outbox packets + repair_candidates are byte-identical
    after a full run; all mutations happen on temp copies only.
  * verdict vocab is CHECK_OK/CHECK_REJECTED, never a bare PASS.
"""
from __future__ import annotations
import copy, hashlib, importlib.util, json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("mo4", HERE / "mo4_repair_relint.py")
mo4 = importlib.util.module_from_spec(spec); spec.loader.exec_module(mo4)

LINTER = mo4.load_linter()
CORPUS = mo4.DEFAULT_CORPUS
CANDIDATES = mo4.DEFAULT_CANDIDATES
# A concrete real packet used as the clean baseline / mutation source.
REAL_PACKET_PATH = CORPUS / "P0PGR-20260708-002.json"
REAL_PACKET = json.loads(REAL_PACKET_PATH.read_text())


def _mutate_bad_hardblock(pk: dict) -> dict:
    """MINIMAL MUTATION #1: flip exactly one value — a single hard_block reason to
    a value outside the linter's allowed enum. Nothing else changes."""
    m = copy.deepcopy(pk)
    m.setdefault("quality_handling", {})["hard_block_allowed_reasons"] = ["totally_bogus_reason"]
    return m


def _mutate_drop_execution_mode(pk: dict) -> dict:
    """MINIMAL MUTATION #2: remove exactly one required field."""
    m = copy.deepcopy(pk)
    m.pop("execution_mode", None)
    return m


def test_real_outbox_packet_relints_clean():
    rep = mo4.assess_packet(REAL_PACKET, LINTER)
    assert rep["verdict"] == "CHECK_OK", rep
    assert rep["reasons"] == [], rep


def test_positive_control_bad_hardblock_is_flagged():
    # If this real-packet mutation is NOT flagged, the detector is broken —
    # a zero-hit elsewhere cannot be trusted as a true clean.
    rep = mo4.assess_packet(_mutate_bad_hardblock(REAL_PACKET), LINTER)
    assert rep["verdict"] == "CHECK_REJECTED", rep
    assert any("totally_bogus_reason" in r for r in rep["reasons"]), rep


def test_second_independent_mutation_also_flagged():
    rep = mo4.assess_packet(_mutate_drop_execution_mode(REAL_PACKET), LINTER)
    assert rep["verdict"] == "CHECK_REJECTED", rep
    assert any("execution_mode" in r for r in rep["reasons"]), rep


def test_diff_resolved_vs_still_present():
    before = ["schema: 'execution_mode' is a required property"]
    # after == clean  -> the before reason is RESOLVED
    d_clean = mo4.diff_reasons(before, [])
    assert d_clean["resolved"] == before and d_clean["still_present"] == []
    # after still carries it -> still_present (not repaired)
    d_same = mo4.diff_reasons(before, before)
    assert d_same["still_present"] == before and d_same["resolved"] == []


def test_candidate_repair_confirmed_when_packet_clean(tmp_path):
    # Candidate references the REAL (clean) packet but was filed with a stale reason.
    cand = {"packet_id": "P0PGR-20260708-002", "cycle_id": "C-TEST",
            "packet_path": str(REAL_PACKET_PATH),
            "reasons": ["schema: 'execution_mode' is a required property"]}
    rep = mo4.assess_candidate(cand, CORPUS, LINTER)
    assert rep["status"] == "RESOLVED" and rep["verdict"] == "CHECK_OK", rep
    assert rep["reason_diff"]["resolved"] == cand["reasons"], rep
    assert rep["after_reasons"] == [], rep


def test_candidate_repair_not_confirmed_when_packet_still_dirty(tmp_path):
    # Write a MUTATED copy of the real packet to a temp file (real artifact,
    # minimal mutation) and file a candidate pointing at it whose 'before' reason
    # still holds -> repair NOT confirmed.
    dirty = _mutate_bad_hardblock(REAL_PACKET)
    pkt_file = tmp_path / "P0PGR-DIRTY.json"
    pkt_file.write_text(json.dumps(dirty))
    cand = {"packet_id": "P0PGR-DIRTY", "cycle_id": "C-TEST",
            "packet_path": str(pkt_file),
            "reasons": ["hard_block reason not in allowed enum: totally_bogus_reason"]}
    rep = mo4.assess_candidate(cand, CORPUS, LINTER)
    assert rep["status"] == "RESOLVED" and rep["verdict"] == "CHECK_REJECTED", rep
    assert "hard_block reason not in allowed enum: totally_bogus_reason" in rep["reason_diff"]["still_present"], rep


def test_candidate_unresolved_packet_is_rejected():
    cand = {"packet_id": "P0PGR-NEVER", "cycle_id": "C-TEST",
            "packet_path": "/no/such/path/ghost.json", "reasons": ["x"]}
    rep = mo4.assess_candidate(cand, CORPUS, LINTER)
    assert rep["status"] == "UNRESOLVED_PACKET" and rep["verdict"] == "CHECK_REJECTED", rep


def test_full_run_is_read_only():
    watched = list(CORPUS.glob("*.json")) + (
        list(CANDIDATES.glob("*.json")) if CANDIDATES.is_dir() else [])
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in watched}
    rc = subprocess.run([sys.executable, str(HERE / "mo4_repair_relint.py")],
                        text=True, capture_output=True)
    # real repo: candidates reference ephemeral temp packets -> UNRESOLVED -> exit 1
    assert rc.returncode in (0, 1), rc.stderr
    after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in watched}
    assert before == after, "MO-4 modified a ground-truth packet or candidate!"


def test_never_emits_pass():
    reps = [mo4.assess_packet(REAL_PACKET, LINTER),
            mo4.assess_packet(_mutate_bad_hardblock(REAL_PACKET), LINTER)]
    for r in reps:
        assert r["verdict"] in ("CHECK_OK", "CHECK_REJECTED"), r
        assert r["pass_claimed"] is False, r


TESTS = [test_real_outbox_packet_relints_clean,
         test_positive_control_bad_hardblock_is_flagged,
         test_second_independent_mutation_also_flagged,
         test_diff_resolved_vs_still_present,
         test_candidate_repair_confirmed_when_packet_clean,
         test_candidate_repair_not_confirmed_when_packet_still_dirty,
         test_candidate_unresolved_packet_is_rejected,
         test_full_run_is_read_only,
         test_never_emits_pass]


def _main() -> int:
    import tempfile
    failed = 0
    for t in TESTS:
        try:
            if "tmp_path" in t.__code__.co_varnames:
                with tempfile.TemporaryDirectory() as d:
                    t(Path(d))
            else:
                t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            failed += 1; print(f"FAIL  {t.__name__}: {e}")
    print(f"\n{len(TESTS)-failed}/{len(TESTS)} green")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_main())
