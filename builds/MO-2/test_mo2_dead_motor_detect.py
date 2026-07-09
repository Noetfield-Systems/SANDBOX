#!/usr/bin/env python3
"""
TH for MO-2 — the dead-motor detector's own proof (RED-before-GREEN).

  * REAL census -> CHECK_REJECTED: the 4 gateway/deadman motors declare prose
    receipt_globs that match ZERO on-disk receipts and are reported as dead. No
    relaxation, no strawman — the real field values are globbed as-is.
  * POSITIVE CONTROL (glob engine is not broken-clean): the two real motors whose
    receipt_glob is a genuine path pattern (agent-read-staleness / auth-surface-probe)
    DO match on-disk receipts and are NEVER flagged dead. A zero-hit therefore
    cannot be a false-clean from a broken glob.
  * a MINIMAL MUTATION of the real census (repoint each dead motor's receipt_glob
    at a glob that genuinely matches) is all-alive -> CHECK_OK (detector is not
    always-fail).
  * SEEDING one fake motor with a glob that matches nothing into that clean copy
    flips it back -> CHECK_REJECTED, seed loop_id cited (RED-before-GREEN).
  * no-relaxation: breaking one real motor's glob in the clean copy re-rejects.
  * running the detector leaves the census + receipt dirs byte-identical (read-only).
  * verdict vocab is CHECK_OK/CHECK_REJECTED, never PASS.
"""
from __future__ import annotations
import copy, glob, hashlib, importlib.util, json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("mo2", HERE / "mo2_dead_motor_detect.py")
mo2 = importlib.util.module_from_spec(spec); spec.loader.exec_module(mo2)

ROOT = mo2.REPO
CENSUS = json.loads(mo2.DEFAULT_CENSUS.read_text())

# The 4 motors whose receipt_glob is prose / points at nothing on disk.
REAL_DEAD = {
    "cf_gateway_ops_v1", "cf_gateway_heartbeat_v1",
    "railway_sina_gateway_v1", "gh_gateway_railway_deadman_v1",
}
# The 2 motors with genuine path globs that DO match receipts (positive control).
REAL_ALIVE = {"sg_agent_read_staleness_v1", "sg_auth_surface_probe_v1"}

# A glob that is known to match >=1 real on-disk receipt (used to revive motors).
LIVE_GLOB = "receipts/agent-read-staleness-*.json"


def _clean_census() -> dict:
    """MINIMAL MUTATION of the real census: repoint ONLY the dead motors'
    receipt_glob at a pattern that genuinely matches on disk. Nothing else changes;
    the detector is untouched."""
    c = copy.deepcopy(CENSUS)
    dead = {m["loop_id"] for m in mo2.detect(CENSUS, ROOT)["dead_motors"]}
    for value in c.values():
        if isinstance(value, list):
            for entry in value:
                if isinstance(entry, dict) and entry.get("loop_id") in dead:
                    entry["receipt_glob"] = LIVE_GLOB
    return c


def test_positive_control_live_globs_actually_match():
    # If this fails the whole detector is meaningless (broken glob engine).
    assert len(glob.glob(str(ROOT / LIVE_GLOB))) > 0, "positive-control glob matched nothing"


def test_real_census_reports_dead_motors():
    res = mo2.detect(CENSUS, ROOT)
    assert res["verdict"] == "CHECK_REJECTED", res
    got = {d["loop_id"] for d in res["dead_motors"]}
    assert got == REAL_DEAD, f"real dead set mismatch: {got}"
    # every dead motor genuinely matched zero receipts
    for d in res["dead_motors"]:
        assert d["match_count"] == 0, d


def test_real_alive_motors_never_flagged():
    res = mo2.detect(CENSUS, ROOT)
    dead = {d["loop_id"] for d in res["dead_motors"]}
    assert REAL_ALIVE.isdisjoint(dead), f"a live motor was flagged dead: {REAL_ALIVE & dead}"
    alive = {m["loop_id"] for m in res["motors"] if m["match_count"] > 0}
    assert REAL_ALIVE <= alive, f"positive-control motors did not match: {REAL_ALIVE - alive}"


def test_minimally_revived_census_is_all_alive():
    res = mo2.detect(_clean_census(), ROOT)
    assert res["verdict"] == "CHECK_OK", res
    assert res["dead_count"] == 0, res


def test_seeded_dead_motor_flips_clean_to_rejected():
    # GREEN baseline: revived census passes.
    assert mo2.detect(_clean_census(), ROOT)["verdict"] == "CHECK_OK"
    # Seed ONE fake motor with a glob that matches nothing -> RED.
    c = _clean_census()
    c.setdefault("cloudflare_workers", []).append(
        {"loop_id": "SEEDED-PHANTOM-MOTOR",
         "receipt_glob": "receipts/__mo2_no_such_receipt_ever__-*.json"})
    res = mo2.detect(c, ROOT)
    assert res["verdict"] == "CHECK_REJECTED", res
    assert any(d["loop_id"] == "SEEDED-PHANTOM-MOTOR" for d in res["dead_motors"]), res


def test_no_relaxation_breaking_a_real_glob_reflips():
    c = _clean_census()
    # Break one motor's glob back to a non-matching pattern -> must re-reject.
    for value in c.values():
        if isinstance(value, list):
            for entry in value:
                if isinstance(entry, dict) and entry.get("loop_id") == "cf_gateway_ops_v1":
                    entry["receipt_glob"] = "gateway-ops receipt via Telegram"
    res = mo2.detect(c, ROOT)
    assert res["verdict"] == "CHECK_REJECTED", res
    assert any(d["loop_id"] == "cf_gateway_ops_v1" for d in res["dead_motors"]), res


def _sha_tree(*paths):
    out = {}
    for p in paths:
        p = Path(p)
        if p.is_file():
            out[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
        elif p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file():
                    out[str(f)] = hashlib.sha256(f.read_bytes()).hexdigest()
    return out


def test_detector_is_read_only():
    watched = (mo2.DEFAULT_CENSUS, ROOT / "receipts")
    before = _sha_tree(*watched)
    rc = subprocess.run([sys.executable, str(HERE / "mo2_dead_motor_detect.py")],
                        text=True, capture_output=True)
    assert rc.returncode == 1, f"real census should exit 1 (dead motors): {rc.stdout}{rc.stderr}"
    after = _sha_tree(*watched)
    assert before == after, "detector modified the census or a receipt directory!"


def test_never_emits_pass():
    for c in (CENSUS, _clean_census()):
        assert mo2.detect(c, ROOT)["verdict"] in ("CHECK_OK", "CHECK_REJECTED")


TESTS = [test_positive_control_live_globs_actually_match,
         test_real_census_reports_dead_motors,
         test_real_alive_motors_never_flagged,
         test_minimally_revived_census_is_all_alive,
         test_seeded_dead_motor_flips_clean_to_rejected,
         test_no_relaxation_breaking_a_real_glob_reflips,
         test_detector_is_read_only,
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
