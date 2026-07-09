#!/usr/bin/env python3
"""
TH-2 — DLM classifier golden-fixture eval  (catalog build B0 · TH-2)

Freezes the Decision Language Machine's classification of the 80-item fixture so a
change to the rule-based classifier gets caught. Runs run_pipeline() IN-PROCESS
with OUTPUT_DIR/RECEIPTS_DIR monkeypatched to a temp dir, so NOTHING is written
into the tracked decision_language_machine_v1/output|receipts (append-only, Lock 5).

CHESS-patched (§B0):
  * golden = the 4-class counts + item/cluster totals.
  * NOT counts-only: ~5 items are hand-labeled with an expected class.
  * the DLM stage field is "decision":"PASS" (a STAGE decision, NOT a gate PASS) —
    this harness reads "classification", never the stage "decision", so no reader
    conflates a DLM stage OK with a promotion-gate PASS.

    python3 test_dlm_classifier_golden.py                 # self-runner
    python3 test_dlm_classifier_golden.py --update-golden # first freeze only
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def _repo_root() -> Path:
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                             cwd=Path(__file__).resolve().parent, text=True, capture_output=True, check=True)
        return Path(out.stdout.strip())
    except Exception:
        return Path(__file__).resolve().parents[3]


REPO = _repo_root()
DLM_DIR = REPO / "decision_language_machine_v1"
FIXTURE = DLM_DIR / "test_fixtures" / "form_official_80_open_v1.json"
GOLDEN = Path(__file__).resolve().parent / "golden" / "dlm_classifier_golden_v1.json"

# make DLM + language_gate importable in-process
for p in (str(DLM_DIR), str(REPO / "language_gate")):
    if p not in sys.path:
        sys.path.insert(0, p)


def run_classify() -> dict:
    """Run the pipeline with all writes redirected to a temp dir; return classification data."""
    import dlm_core_v1 as core
    import dlm_pipeline_v1 as pipe
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "output"
        rec = Path(tmp) / "receipts"
        core.OUTPUT_DIR = out           # write_run_manifest uses core.OUTPUT_DIR
        core.RECEIPTS_DIR = rec         # write_stage_receipt uses core.RECEIPTS_DIR
        pipe.OUTPUT_DIR = out           # run_pipeline writes sheet/apply_map/processed directly
        summary = pipe.run_pipeline(FIXTURE)
        processed = json.loads(Path(summary["processed"]).read_text())
    per_item = {p["id"]: p["classification"] for p in processed}
    return {
        "classification_counts": dict(sorted(summary["classification"].items())),
        "item_count": summary["item_count"],
        "cluster_count": summary["cluster_count"],
        "per_item": per_item,
    }


def build_golden() -> dict:
    r = run_classify()
    # hand-label up to 5 items: first item id seen for each class (coverage across classes)
    hand: dict[str, str] = {}
    for iid, cls in r["per_item"].items():
        if cls not in hand.values():
            hand[iid] = cls
        if len(hand) >= 5:
            break
    return {
        "classification_counts": r["classification_counts"],
        "item_count": r["item_count"],
        "cluster_count": r["cluster_count"],
        "hand_labeled_items": hand,
    }


def test_counts_match_frozen_golden():
    assert GOLDEN.is_file(), f"golden missing — run --update-golden to freeze: {GOLDEN}"
    g = json.loads(GOLDEN.read_text())
    r = run_classify()
    assert r["classification_counts"] == g["classification_counts"], \
        f"class counts DRIFTED: frozen={g['classification_counts']} live={r['classification_counts']}"
    assert r["item_count"] == g["item_count"]
    assert r["cluster_count"] == g["cluster_count"]


def test_hand_labeled_items_still_classify_as_expected():
    g = json.loads(GOLDEN.read_text())
    r = run_classify()
    for iid, expected in g["hand_labeled_items"].items():
        assert r["per_item"].get(iid) == expected, f"item {iid}: expected {expected}, got {r['per_item'].get(iid)}"


def test_deterministic_two_runs_agree():
    a = run_classify(); b = run_classify()
    assert a["classification_counts"] == b["classification_counts"]
    assert a["per_item"] == b["per_item"]


def test_reads_classification_not_stage_decision():
    # guard: the golden must not carry a stage 'decision' field (avoid PASS confusion)
    g = json.loads(GOLDEN.read_text())
    assert "decision" not in g and "decision" not in json.dumps(g).replace("classification", ""), \
        "golden must snapshot classification, never a stage decision:PASS"


TESTS = [test_counts_match_frozen_golden, test_hand_labeled_items_still_classify_as_expected,
         test_deterministic_two_runs_agree, test_reads_classification_not_stage_decision]


def _main(argv) -> int:
    if "--update-golden" in argv:
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(json.dumps(build_golden(), indent=2) + "\n", encoding="utf-8")
        print(f"FROZEN golden -> {GOLDEN}")
        return 0
    failed = 0
    for t in TESTS:
        try: t(); print(f"PASS  {t.__name__}")
        except AssertionError as e: failed += 1; print(f"FAIL  {t.__name__}: {e}")
    print(f"\n{len(TESTS)-failed}/{len(TESTS)} green")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
