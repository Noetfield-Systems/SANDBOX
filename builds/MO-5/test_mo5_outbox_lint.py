#!/usr/bin/env python3
"""
TH for MO-5 — the batch outbox linter's own proof (RED-before-GREEN).

  * REAL outbox -> CHECK_OK: all 10 packets lint clean, exit 0, honestly reported
    (positive-control on the whole live set — this is the true verdict, not a stub).
  * a MINIMAL MUTATION of one real packet (drop the required `fallback_route` key)
    in a TEMP COPY of the outbox flips that ONE packet to a REPAIR_CANDIDATE and the
    batch summary to CHECK_REJECTED, exit 1; the other 9 stay PASS (RED, seed cited).
  * a SECOND independent minimal mutation (cloud_safe=false on a CLOUD_ONLY packet)
    also flips the batch to CHECK_REJECTED -> the gate isn't keyed to one lucky field
    (a broken-regex false-clean would miss at least one of these).
  * POSITIVE CONTROL: a temp outbox that is a byte copy of the real one (no mutation)
    stays CHECK_OK -> the rejection is caused by the mutation, not by copying.
  * running MO-5 leaves every real outbox packet AND the ground linter byte-identical
    (read-only).
  * verdict vocab is CHECK_OK/CHECK_REJECTED, never a bare governance PASS.
"""
from __future__ import annotations
import hashlib, importlib.util, json, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("mo5", HERE / "mo5_outbox_lint.py")
mo5 = importlib.util.module_from_spec(spec); spec.loader.exec_module(mo5)

REAL_OUTBOX = mo5.DEFAULT_OUTBOX
REAL_PACKETS = sorted(REAL_OUTBOX.glob("*.json"))


def _copy_outbox() -> Path:
    """Byte-for-byte temp copy of the real outbox (nothing mutated yet)."""
    tmp = Path(tempfile.mkdtemp(prefix="mo5-outbox-"))
    for p in REAL_PACKETS:
        shutil.copy2(p, tmp / p.name)
    return tmp


def _cloud_only_packet(outbox: Path) -> Path:
    for p in sorted(outbox.glob("*.json")):
        if json.loads(p.read_text()).get("execution_mode") == "CLOUD_ONLY":
            return p
    raise AssertionError("no CLOUD_ONLY packet found to mutate")


def test_real_outbox_all_clean_check_ok():
    assert len(REAL_PACKETS) == 10, f"expected 10 outbox packets, got {len(REAL_PACKETS)}"
    summary = mo5.lint_outbox(REAL_OUTBOX)
    assert summary["verdict"] == "CHECK_OK", summary
    assert summary["packet_count"] == 10
    assert summary["violation_count"] == 0, summary["violations"]
    assert all(r["lint_verdict"] == "PASS" for r in summary["results"]), summary


def test_dropped_required_field_flips_one_packet_to_rejected():
    # GREEN baseline: the byte-copy of the real outbox is still CHECK_OK.
    tmp = _copy_outbox()
    assert mo5.lint_outbox(tmp)["verdict"] == "CHECK_OK"
    # MINIMAL MUTATION: drop the required `fallback_route` key from ONE packet.
    victim = sorted(tmp.glob("*.json"))[0]
    packet = json.loads(victim.read_text())
    assert "fallback_route" in packet, "fixture assumption: real packet has fallback_route"
    del packet["fallback_route"]
    victim.write_text(json.dumps(packet, indent=2))
    # RED: that one packet is now a REPAIR_CANDIDATE, batch is CHECK_REJECTED.
    summary = mo5.lint_outbox(tmp)
    assert summary["verdict"] == "CHECK_REJECTED", summary
    assert summary["violation_count"] == 1, summary["violations"]
    v = summary["violations"][0]
    assert v["packet_file"] == victim.name, v
    assert any("fallback_route" in r for r in v["reasons"]), v
    # the other 9 packets are untouched and still PASS
    others = [r for r in summary["results"] if r["packet_file"] != victim.name]
    assert len(others) == 9 and all(r["lint_verdict"] == "PASS" for r in others), summary


def test_second_independent_mutation_also_flips():
    tmp = _copy_outbox()
    victim = _cloud_only_packet(tmp)
    packet = json.loads(victim.read_text())
    assert packet.get("cloud_safe") is True, "fixture assumption: CLOUD_ONLY packet is cloud_safe"
    packet["cloud_safe"] = False
    victim.write_text(json.dumps(packet, indent=2))
    summary = mo5.lint_outbox(tmp)
    assert summary["verdict"] == "CHECK_REJECTED", summary
    assert any(vi["packet_file"] == victim.name for vi in summary["violations"]), summary


def test_positive_control_unmutated_copy_stays_ok():
    # Copying alone must NOT cause a rejection — proves the flip is the mutation's doing.
    tmp = _copy_outbox()
    assert mo5.lint_outbox(tmp)["verdict"] == "CHECK_OK"


def test_real_run_exit_codes_and_read_only():
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in REAL_PACKETS}
    before[mo5.GROUND_LINTER] = hashlib.sha256(mo5.GROUND_LINTER.read_bytes()).hexdigest()
    # real outbox -> exit 0 (CHECK_OK)
    rc = subprocess.run([sys.executable, str(HERE / "mo5_outbox_lint.py")],
                        text=True, capture_output=True)
    assert rc.returncode == 0, f"real outbox should exit 0: {rc.stdout}{rc.stderr}"
    assert "CHECK_OK" in rc.stdout, rc.stdout
    # mutated temp outbox -> exit 1 (CHECK_REJECTED)
    tmp = _copy_outbox()
    victim = sorted(tmp.glob("*.json"))[0]
    packet = json.loads(victim.read_text()); del packet["fallback_route"]
    victim.write_text(json.dumps(packet, indent=2))
    rc2 = subprocess.run([sys.executable, str(HERE / "mo5_outbox_lint.py"),
                          "--outbox", str(tmp)], text=True, capture_output=True)
    assert rc2.returncode == 1, f"mutated outbox should exit 1: {rc2.stdout}{rc2.stderr}"
    assert "CHECK_REJECTED" in rc2.stdout, rc2.stdout
    # read-only: real packets and ground linter unchanged
    after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in REAL_PACKETS}
    after[mo5.GROUND_LINTER] = hashlib.sha256(mo5.GROUND_LINTER.read_bytes()).hexdigest()
    assert before == after, "MO-5 modified a ground-truth file!"


def test_never_emits_bare_pass():
    for ob in (REAL_OUTBOX, _copy_outbox()):
        assert mo5.lint_outbox(ob)["verdict"] in ("CHECK_OK", "CHECK_REJECTED")


TESTS = [test_real_outbox_all_clean_check_ok,
         test_dropped_required_field_flips_one_packet_to_rejected,
         test_second_independent_mutation_also_flips,
         test_positive_control_unmutated_copy_stays_ok,
         test_real_run_exit_codes_and_read_only,
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
