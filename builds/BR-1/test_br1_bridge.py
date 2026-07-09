#!/usr/bin/env python3
"""
TH for BR-1 — the founder-authority brakes, proven.

Reuses GV-6's DLM-in-temp generation (writes redirected to a temp dir; ZERO writes
to tracked DLM dirs). The REAL default apply_map (GV-6-rejected, leaky) is the
negative; a MINIMAL MUTATION of it (add deferred_unvalidated) is the GV-6-passed positive.

  * REAL leaky apply_map (GV-6 CHECK_REJECTED) -> BR-1 REFUSES, 0 packets.
  * GV-6-passed conformant apply_map -> BR-1 bridges MACHINE_VALIDATABLE items.
  * NO FOUNDER_FACT is ever bridged; FOUNDER_FACT ids appear in the manifest.
  * EVERY packet hardcodes status=DRAFT, dispatch_now=false; no AUTO_DISPATCH anywhere.
  * BR-1 never imports/calls build_apply_map.
"""
from __future__ import annotations
import copy, importlib.util, json, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=HERE,
                           text=True, capture_output=True, check=True).stdout.strip())
DLM_DIR = REPO / "decision_language_machine_v1"
FIXTURE = DLM_DIR / "test_fixtures" / "form_official_80_open_v1.json"
for p in (str(DLM_DIR), str(REPO / "language_gate")):
    if p not in sys.path:
        sys.path.insert(0, p)

spec = importlib.util.spec_from_file_location("br1", HERE / "br1_dlm_p0pgr_bridge.py")
br1 = importlib.util.module_from_spec(spec); spec.loader.exec_module(br1)
gv6 = br1.gv6


def _real_run():
    import dlm_core_v1 as core, dlm_pipeline_v1 as pipe
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "output"; rec = Path(tmp) / "receipts"
        core.OUTPUT_DIR = out; core.RECEIPTS_DIR = rec; pipe.OUTPUT_DIR = out
        summary = pipe.run_pipeline(FIXTURE)
        apply_map = json.loads(Path(out, f"{summary['run_id']}.apply_map.json").read_text())
        processed = json.loads(Path(summary["processed"]).read_text())
    return apply_map, processed


REAL_MAP, PROCESSED = _real_run()
UNIVERSE = gv6.advisor_founder_ids(PROCESSED)


def _conformant():
    m = copy.deepcopy(REAL_MAP)
    m["deferred_unvalidated"] = sorted(UNIVERSE - gv6._pick_ids(m))
    return m


def test_refuses_gv6_rejected_leaky_map():
    res = br1.bridge(REAL_MAP, PROCESSED, UNIVERSE)
    assert res["refused"] is True, res
    assert res["gv6_verdict"] == "CHECK_REJECTED"
    assert res["packets"] == [], "a refused bridge must emit ZERO packets"


def test_bridges_gv6_passed_map():
    res = br1.bridge(_conformant(), PROCESSED, UNIVERSE)
    assert res["refused"] is False and res["gv6_verdict"] == "CHECK_OK", res
    assert len(res["packets"]) > 0, "conformant map should yield packets"
    # only MACHINE_VALIDATABLE / validated-advisor sources
    by_id = {p["id"]: p for p in PROCESSED}
    for pk in res["packets"]:
        cls = by_id[pk["source_item_id"]]["classification"]
        assert cls in ("MACHINE_VALIDATABLE", "ADVISOR_REVIEW"), cls


def test_no_founder_fact_is_ever_bridged():
    res = br1.bridge(_conformant(), PROCESSED, UNIVERSE)
    by_id = {p["id"]: p for p in PROCESSED}
    ff = {i for i, p in by_id.items() if p["classification"] == "FOUNDER_FACT"}
    bridged = {pk["source_item_id"] for pk in res["packets"]}
    assert not (ff & bridged), f"FOUNDER_FACT leaked into packets: {ff & bridged}"
    assert set(res["machine_closed_manifest"]["founder_fact_ids"]) == ff, "FOUNDER_FACT must be in the manifest"


def test_every_packet_is_draft_and_dispatch_off():
    res = br1.bridge(_conformant(), PROCESSED, UNIVERSE)
    blob = json.dumps(res)
    assert "AUTO_DISPATCH_APPROVED" not in blob and "AUTO_DISPATCH" not in blob
    for pk in res["packets"]:
        assert pk["status"] == "DRAFT", pk
        assert pk["dispatch_now"] is False, pk
        assert pk["authority_scope"] == "observe", pk


def test_manifest_covers_all_excluded():
    res = br1.bridge(_conformant(), PROCESSED, UNIVERSE)
    by_id = {p["id"]: p for p in PROCESSED}
    bridged = {pk["source_item_id"] for pk in res["packets"]}
    excluded = set(by_id) - bridged
    mc = set(res["machine_closed_manifest"]["machine_closed_without_founder"])
    assert excluded <= mc, f"excluded items missing from manifest: {excluded - mc}"


def test_never_calls_build_apply_map():
    src = (HERE / "br1_dlm_p0pgr_bridge.py").read_text()
    assert "build_apply_map(" not in src and "import dlm_apply_map" not in src


TESTS = [test_refuses_gv6_rejected_leaky_map, test_bridges_gv6_passed_map, test_no_founder_fact_is_ever_bridged,
         test_every_packet_is_draft_and_dispatch_off, test_manifest_covers_all_excluded, test_never_calls_build_apply_map]


def _main() -> int:
    failed = 0
    for t in TESTS:
        try: t(); print(f"PASS  {t.__name__}")
        except AssertionError as e: failed += 1; print(f"FAIL  {t.__name__}: {e}")
    print(f"\n{len(TESTS)-failed}/{len(TESTS)} green")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_main())
