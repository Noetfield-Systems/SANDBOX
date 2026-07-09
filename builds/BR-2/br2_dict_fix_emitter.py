#!/usr/bin/env python3
"""
BR-2 — DLM -> language_gate dictionary-fix PROPOSAL emitter  (catalog build B3 · BR-2)

The Decision Language Machine's dictionary_check stage marks any term with no
dictionary entry as DICTIONARY_FIX_NEEDED. This tool runs that check over the
80-item fixture (all DLM writes redirected to a temp dir, per TH-2) and emits a
dictionary-fix PROPOSAL: candidate dictionary entries for the fix-needed terms.

It is an EMITTER, never a writer:
  * it NEVER opens language_gate/dictionary_index.json for writing — it only reads
    it (via load_dictionary) to skip terms that already exist;
  * the proposal is written to THIS build dir only, stamped origin=sandbox-advisory
    / authority=none / status=DRAFT — a candidate list a human must ratify, not a
    dictionary mutation.

Detector contract (exit code): a "hit" is a fix-needed term that becomes a
candidate. Non-empty candidate list -> EXIT 1 (dictionary fixes are needed);
empty -> EXIT 0. So a seeded fix-needed term makes this exit nonzero (RED),
and a positive-control term already in the dictionary must NOT be re-proposed.

    python3 br2_dict_fix_emitter.py                       # real fixture -> proposal.json
    python3 br2_dict_fix_emitter.py --fixture PATH --out PATH
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    import subprocess
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=Path(__file__).resolve().parent, text=True, capture_output=True, check=True,
        )
        return Path(out.stdout.strip())
    except Exception:
        return Path(__file__).resolve().parents[3]


HERE = Path(__file__).resolve().parent
REPO = _repo_root()
DLM_DIR = REPO / "decision_language_machine_v1"
GATE_DIR = REPO / "language_gate"
DEFAULT_FIXTURE = DLM_DIR / "test_fixtures" / "form_official_80_open_v1.json"
DICTIONARY_INDEX = GATE_DIR / "dictionary_index.json"
DEFAULT_OUT = HERE / "dictionary_fix_proposal_v1.json"

# make DLM + language_gate importable in-process (per TH-2)
for _p in (str(DLM_DIR), str(GATE_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def run_dictionary_check(fixture_path: Path) -> list[dict[str, Any]]:
    """Run the DLM pipeline with ALL writes redirected to a temp dir; return processed items.

    Monkeypatches dlm_core_v1.OUTPUT_DIR / RECEIPTS_DIR and dlm_pipeline_v1.OUTPUT_DIR
    so nothing is written into tracked decision_language_machine_v1/output|receipts
    (append-only, Lock 5).
    """
    import dlm_core_v1 as core
    import dlm_pipeline_v1 as pipe

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "output"
        rec = Path(tmp) / "receipts"
        core.OUTPUT_DIR = out       # write_run_manifest / write_stage_receipt targets
        core.RECEIPTS_DIR = rec
        pipe.OUTPUT_DIR = out       # run_pipeline writes sheet/apply_map/processed directly
        summary = pipe.run_pipeline(Path(fixture_path))
        processed = json.loads(Path(summary["processed"]).read_text(encoding="utf-8"))
    return processed


def existing_dictionary_terms() -> set[str]:
    """Normalized set of every token the dictionary already knows (terms + aliases +
    code aliases + retired), read-only. A term in here is NEVER re-proposed."""
    from language_gate_core_v1 import load_dictionary

    d = load_dictionary(DICTIONARY_INDEX)
    known: set[str] = set()
    known |= set(d.terms.keys())
    known |= set(d.alias_map.keys())
    known |= set(d.code_alias)
    known |= set(d.retired_terms)
    return {k.lower() for k in known}


def collect_fix_needed(processed: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """normalized -> {term, seen_in_items[...]} for every DICTIONARY_FIX_NEEDED flag."""
    fix: dict[str, dict[str, Any]] = {}
    for item in processed:
        iid = item.get("id", "")
        for f in item.get("dictionary_flags", []):
            if f.get("status") != "DICTIONARY_FIX_NEEDED":
                continue
            low = f.get("normalized") or f.get("term", "").lower()
            if not low:
                continue
            entry = fix.setdefault(low, {"term": f.get("term", low), "seen_in_items": []})
            if iid and iid not in entry["seen_in_items"]:
                entry["seen_in_items"].append(iid)
    return fix


def build_proposal(fixture_path: Path = DEFAULT_FIXTURE) -> dict[str, Any]:
    processed = run_dictionary_check(Path(fixture_path))
    fix_needed = collect_fix_needed(processed)
    known = existing_dictionary_terms()

    candidates: list[dict[str, Any]] = []
    skipped_already_present: list[str] = []
    for low in sorted(fix_needed):
        if low in known:
            # already in dictionary_index.json — a DLM misfire; NEVER re-propose it.
            skipped_already_present.append(low)
            continue
        info = fix_needed[low]
        candidates.append({
            "normalized": low,
            "term": info["term"],
            "seen_in_items": sorted(info["seen_in_items"]),
            "proposed_action": "PROPOSE_ADD",
            "proposed_definition": "",   # left blank — a human authors the meaning
            "status": "CANDIDATE",
        })

    verdict = "FIX_NEEDED_TERMS_FOUND" if candidates else "NO_FIX_NEEDED"
    return {
        "receipt_type": "dictionary_fix_proposal_v1",
        "kind": "dictionary_fix_proposal",
        "origin": "sandbox-advisory",
        "authority": "none",
        "status": "DRAFT",
        "verdict": verdict,
        "pass_claimed": False,
        "catalog_item": "BR-2",
        "note": (
            "PROPOSAL only. Candidate dictionary entries for DLM DICTIONARY_FIX_NEEDED "
            "terms. This tool NEVER writes language_gate/dictionary_index.json — a human "
            "must author each definition and ratify the add."
        ),
        "source_fixture": str(fixture_path),
        "item_count": len(processed),
        "fix_needed_term_count": len(fix_needed),
        "candidate_count": len(candidates),
        "candidate_entries": candidates,
        "skipped_already_in_dictionary": sorted(skipped_already_present),
        "dictionary_index_written": False,
    }


def emit(fixture_path: Path = DEFAULT_FIXTURE, out_path: Path = DEFAULT_OUT) -> tuple[dict[str, Any], Path]:
    proposal = build_proposal(fixture_path)
    out_path = Path(out_path)
    # Hard fence: refuse to ever target the real dictionary index.
    if out_path.resolve() == DICTIONARY_INDEX.resolve():
        raise RuntimeError("refusing to write dictionary_index.json — this is a PROPOSAL emitter")
    out_path.write_text(json.dumps(proposal, indent=2) + "\n", encoding="utf-8")
    return proposal, out_path


def _main(argv: list[str]) -> int:
    fixture = DEFAULT_FIXTURE
    out = DEFAULT_OUT
    if "--fixture" in argv:
        fixture = Path(argv[argv.index("--fixture") + 1])
    if "--out" in argv:
        out = Path(argv[argv.index("--out") + 1])
    proposal, out_path = emit(fixture, out)
    print(f"verdict={proposal['verdict']} candidates={proposal['candidate_count']} "
          f"skipped_already_present={len(proposal['skipped_already_in_dictionary'])}")
    print(f"proposal -> {out_path}")
    # Detector contract: a fix-needed candidate is a hit -> nonzero exit.
    return 1 if proposal["candidate_count"] > 0 else 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
