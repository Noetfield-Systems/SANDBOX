#!/usr/bin/env python3
"""
WI-5 — Externalize the Phase-2 rank factor table  (catalog build B2 · WI-5)

scripts/p0pgr_phase2_rank_v1.py hard-codes its WEIGHTS (weights) and FACTORS
(the per-move factor table) as in-module dict constants. That makes the scoring
inputs hard to review in isolation. This lane externalizes those two constants,
verbatim, into a reviewable data JSON (phase2_rank_factors.json) and then PROVES
PARITY: the ranking and every per-move score recomputed from the JSON is byte-
for-byte identical to the ranking/score computed from the live in-module
constants. No parity => CHECK_REJECTED.

This is an advisory verifier, not a governance gate. Verdict vocab is
CHECK_OK / CHECK_REJECTED — never a bare PASS. It imports the module constants
and computes IN-MEMORY only; it never runs the ranker's main() (no queue file is
written, no side effects) and never mutates the module or the source file.

Score formula (identical to the module, line ~82):
    score(mid) = round(sum(WEIGHTS[k] * FACTORS[mid][k] for k in WEIGHTS), 2)
Ranking: sort by (-score, move_id), same tie-break as the module.

    python3 wi5_rank_factor_parity.py [--data PATH]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                             cwd=Path(__file__).resolve().parent, text=True,
                             capture_output=True, check=True)
        return Path(out.stdout.strip())
    except Exception:
        return Path(__file__).resolve().parents[3]


REPO = _repo_root()
SOURCE_MODULE = REPO / "scripts" / "p0pgr_phase2_rank_v1.py"
DEFAULT_DATA = Path(__file__).resolve().parent / "phase2_rank_factors.json"


def load_module_constants() -> tuple[dict, dict]:
    """Import the ranker module and return its (WEIGHTS, FACTORS) — no main() run."""
    spec = importlib.util.spec_from_file_location("p0pgr_phase2_rank_v1", SOURCE_MODULE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)                      # defines constants; main() not called
    return mod.WEIGHTS, mod.FACTORS


def compute_ranking(weights: dict, factors: dict) -> tuple[dict, list]:
    """Return (scores_by_move, ranked_move_ids) — same formula/tie-break as the module."""
    scores = {mid: round(sum(weights[k] * factors[mid][k] for k in weights), 2)
              for mid in factors}
    ranked = sorted(factors, key=lambda mid: (-scores[mid], mid))
    return scores, ranked


def verify(data_path: Path = DEFAULT_DATA) -> dict:
    data = json.loads(data_path.read_text(encoding="utf-8"))
    json_weights = data["weights"]
    json_factors = data["factors"]
    mod_weights, mod_factors = load_module_constants()

    reasons: list[str] = []

    # constants transported verbatim
    if json_weights != mod_weights:
        reasons.append("WEIGHTS in JSON differ from module constant (not verbatim)")
    if set(json_factors) != set(mod_factors):
        reasons.append(f"FACTORS move set differs: json={sorted(json_factors)} module={sorted(mod_factors)}")
    else:
        for mid in mod_factors:
            if json_factors[mid] != mod_factors[mid]:
                reasons.append(f"FACTORS[{mid}] in JSON differ from module constant (not verbatim)")

    json_scores, json_rank = compute_ranking(json_weights, json_factors)
    mod_scores, mod_rank = compute_ranking(mod_weights, mod_factors)

    # parity of ranking + every score
    if json_rank != mod_rank:
        reasons.append(f"ranking parity FAILED: json={json_rank} module={mod_rank}")
    score_mismatch = [mid for mid in mod_scores if json_scores.get(mid) != mod_scores[mid]]
    if score_mismatch:
        reasons.append(f"score parity FAILED for {score_mismatch}")

    verdict = "CHECK_OK" if not reasons else "CHECK_REJECTED"
    return {
        "origin": "sandbox-advisory", "authority": "none", "verdict": verdict,
        "subject": {"source_module": str(SOURCE_MODULE.relative_to(REPO)),
                    "data_json": str(data_path)},
        "ranking_from_json": json_rank,
        "ranking_from_module": mod_rank,
        "scores_from_json": json_scores,
        "scores_from_module": mod_scores,
        "parity_reasons": reasons,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA)
    args = ap.parse_args(argv)

    result = verify(args.data)
    print(f"WI-5 RANK_FACTOR_PARITY: {result['verdict']}")
    print(f"  ranking (json)   : {result['ranking_from_json']}")
    print(f"  ranking (module) : {result['ranking_from_module']}")
    for mid in result["ranking_from_module"]:
        print(f"    {mid}: json={result['scores_from_json'].get(mid)} module={result['scores_from_module'][mid]}")
    for r in result["parity_reasons"]:
        print(f"  [parity] {r}")
    return 0 if result["verdict"] == "CHECK_OK" else 1


if __name__ == "__main__":
    sys.exit(main())
