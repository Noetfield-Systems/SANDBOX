#!/usr/bin/env python3
"""
TH for MO-6 — the ROI-heartbeat populator's own proof (RED-before-GREEN).

  * derived blocker_count MATCHES a hand-counted value from REAL local data
    (the latest agent-read-staleness receipt on disk).
  * a MINIMAL MUTATION of a real staleness receipt (append one BLOCKER entry to
    blockers[]) makes the derived count go up by exactly one — the derivation
    reads array content, it is not a frozen constant.
  * an underivable metric (cost_per_signal_cad, ...) STAYS 'unknown' and is
    asserted NOT fabricated to 0 — the no-fabrication contract.
  * the verify DETECTOR exits NONZERO on a fabricated heartbeat (positive
    control) and zero on a clean one — so a zero-hit can't be a broken check.
  * populate NEVER overwrites a prior heartbeat and NEVER writes into receipts/;
    the real on-disk staleness receipts are left byte-identical (read-only).
"""
from __future__ import annotations
import copy, hashlib, importlib.util, json, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("mo6", HERE / "mo6_roi_heartbeat_populate.py")
mo6 = importlib.util.module_from_spec(spec); spec.loader.exec_module(mo6)


def _hand_count(receipts_dir: Path) -> int:
    """Independent hand-count: open the latest staleness receipt and count
    severity=='BLOCKER' entries, without calling the tool's counter."""
    latest = mo6.latest_staleness_receipt(receipts_dir)
    data = json.loads(latest.read_text())
    return len([b for b in data.get("blockers", []) if b.get("severity") == "BLOCKER"])


def test_derived_blocker_count_matches_hand_count_on_real_data():
    got = mo6.derive_blocker_count(mo6.DEFAULT_RECEIPTS)
    expect = _hand_count(mo6.DEFAULT_RECEIPTS)
    assert got == expect, f"derived {got!r} != hand-counted {expect!r}"
    assert isinstance(got, int), got


def test_minimal_mutation_of_real_receipt_shifts_count_by_one(tmp_path):
    """Copy the real latest receipt into a temp receipts dir, append ONE blocker
    (minimal mutation of a real artifact), and require the derived count to rise
    by exactly one. Proves the count is derived from content, not hardcoded."""
    real_latest = mo6.latest_staleness_receipt(mo6.DEFAULT_RECEIPTS)
    data = json.loads(real_latest.read_text())
    base = len([b for b in data.get("blockers", []) if b.get("severity") == "BLOCKER"])

    rd = tmp_path / "receipts"; rd.mkdir()
    (rd / real_latest.name).write_text(json.dumps(data))
    assert mo6.derive_blocker_count(rd) == base

    mutated = copy.deepcopy(data)
    mutated.setdefault("blockers", []).append(
        {"severity": "BLOCKER", "kind": "seeded_fixture_blocker", "message": "minimal mutation"}
    )
    # keep `at` newest so it stays the latest
    mutated["at"] = "2099-01-01T00:00:00Z"
    (rd / "agent-read-staleness-20990101T000000Z.json").write_text(json.dumps(mutated))
    assert mo6.derive_blocker_count(rd) == base + 1, "mutation did not change derived count"


def test_underivable_metrics_stay_unknown_not_fabricated_to_zero():
    hb = mo6.build_heartbeat(mo6.DEFAULT_RECEIPTS)
    for name in mo6.NON_LOCALLY_DERIVABLE:
        val = hb["metrics"][name]
        assert val == "unknown", f"{name} = {val!r}, expected 'unknown'"
        assert val != 0 and val is not None, f"{name} was fabricated: {val!r}"


def test_no_derivable_source_keeps_blocker_count_unknown(tmp_path):
    """Empty receipts dir -> no staleness receipt -> blocker_count is 'unknown',
    NOT fabricated to 0 (the whole point of the no-fabrication contract)."""
    empty = tmp_path / "empty"; empty.mkdir()
    hb = mo6.build_heartbeat(empty)
    assert hb["blocker_count"] == "unknown", hb["blocker_count"]
    assert hb["blocker_count"] != 0


def test_verify_detector_flags_fabricated_metric_positive_control():
    """POSITIVE CONTROL: a heartbeat with a fabricated non-derivable metric must
    be REJECTED — proves the detector actually fires (not a broken clean check)."""
    hb = mo6.build_heartbeat(mo6.DEFAULT_RECEIPTS)
    hb["metrics"]["cost_per_signal_cad"] = 0  # fabrication
    violations = mo6.no_fabrication_violations(hb)
    assert violations, "detector failed to flag a fabricated metric"
    assert any("cost_per_signal_cad" in m for m in violations)


def test_verify_detector_passes_clean_heartbeat():
    hb = mo6.build_heartbeat(mo6.DEFAULT_RECEIPTS)
    assert mo6.no_fabrication_violations(hb) == []


def test_verify_cli_exits_nonzero_on_fabrication(tmp_path):
    good = mo6.build_heartbeat(mo6.DEFAULT_RECEIPTS)
    bad = copy.deepcopy(good); bad["metrics"]["trap_battery_pass_pct"] = 100
    gp = tmp_path / "good.json"; gp.write_text(json.dumps(good))
    bp = tmp_path / "bad.json"; bp.write_text(json.dumps(bad))
    tool = str(HERE / "mo6_roi_heartbeat_populate.py")
    rc_good = subprocess.run([sys.executable, tool, "verify", str(gp)], capture_output=True)
    rc_bad = subprocess.run([sys.executable, tool, "verify", str(bp)], capture_output=True, text=True)
    assert rc_good.returncode == 0, "clean heartbeat should exit 0"
    assert rc_bad.returncode == 1, "fabricated heartbeat should exit nonzero"
    assert "CHECK_REJECTED" in rc_bad.stdout


def test_populate_is_append_only_and_receipts_read_only(tmp_path):
    """populate writes a NEW file into an out dir, refuses to overwrite it, and
    leaves the real receipts/ tree byte-identical."""
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in mo6._staleness_receipts(mo6.DEFAULT_RECEIPTS)}
    out = tmp_path / "out"
    hb = mo6.build_heartbeat(mo6.DEFAULT_RECEIPTS, ts="20260709T000000Z")
    path = mo6.write_heartbeat(hb, out)
    assert path.exists()
    # append-only: same id refuses to overwrite
    try:
        mo6.write_heartbeat(hb, out)
        raise AssertionError("overwrite was not refused")
    except FileExistsError:
        pass
    after = {p: hashlib.sha256(p.read_bytes()).hexdigest()
             for p in mo6._staleness_receipts(mo6.DEFAULT_RECEIPTS)}
    assert before == after, "populate mutated a real staleness receipt!"


def test_write_refuses_tracked_receipts_dir():
    hb = mo6.build_heartbeat(mo6.DEFAULT_RECEIPTS, ts="20260709T111111Z")
    try:
        mo6.write_heartbeat(hb, mo6.DEFAULT_RECEIPTS)
        raise AssertionError("write into receipts/ was not refused")
    except RuntimeError:
        pass


def test_never_emits_bare_pass():
    hb = mo6.build_heartbeat(mo6.DEFAULT_RECEIPTS)
    assert hb["pass_claimed"] is False
    assert hb["origin"] == "sandbox-advisory" and hb["authority"] == "none"


TESTS = [
    test_derived_blocker_count_matches_hand_count_on_real_data,
    test_minimal_mutation_of_real_receipt_shifts_count_by_one,
    test_underivable_metrics_stay_unknown_not_fabricated_to_zero,
    test_no_derivable_source_keeps_blocker_count_unknown,
    test_verify_detector_flags_fabricated_metric_positive_control,
    test_verify_detector_passes_clean_heartbeat,
    test_verify_cli_exits_nonzero_on_fabrication,
    test_populate_is_append_only_and_receipts_read_only,
    test_write_refuses_tracked_receipts_dir,
    test_never_emits_bare_pass,
]


def _main() -> int:
    import inspect
    failed = 0
    for t in TESTS:
        try:
            if "tmp_path" in inspect.signature(t).parameters:
                with tempfile.TemporaryDirectory() as d:
                    t(Path(d))
            else:
                t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            failed += 1; print(f"FAIL  {t.__name__}: {e}")
        except Exception as e:  # surface unexpected errors as failures too
            failed += 1; print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(TESTS)-failed}/{len(TESTS)} green")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_main())
