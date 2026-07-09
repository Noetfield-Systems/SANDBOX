#!/usr/bin/env python3
"""
WI-6 — Externalize the six language_gate allowlists to JSON  (catalog build B2 · WI-6).

ADDITIVE-PARITY externalization: allowlists_v1.json is a reviewable COPY of the six
hardcoded sets (STRUCTURAL / STATUS_LABEL / FRAGMENT / TECH_REFERENCE / CENSUS_VERB /
ENTITY). The Python constants in language_gate_core_v1.py REMAIN the source of truth
and are NEVER deleted; core.load_allowlist() prefers the JSON but falls back to the
constants when the JSON is absent.

This tool is the adversarial spine for that claim. It loads each externalized set from
the JSON and asserts it is BYTE-IDENTICAL (== as a set) to the corresponding hardcoded
constant. Anything that is missing, extra, or a key omitted -> CHECK_REJECTED with cited
reasons. Parity is never "relaxed" by trimming the constant to match a partial JSON.

It NEVER emits a governance PASS (verdict vocab CHECK_OK / CHECK_REJECTED) and NEVER
edits the gate file or the JSON — it only reads them.

    python3 wi6_allowlist_externalize.py [--json PATH]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _repo_root() -> Path:
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                             cwd=HERE, text=True, capture_output=True, check=True)
        return Path(out.stdout.strip())
    except Exception:
        return HERE.parents[2]


REPO = _repo_root()
DEFAULT_JSON = HERE / "allowlists_v1.json"

ALLOWLIST_NAMES = [
    "STRUCTURAL_ALLOWLIST",
    "STATUS_LABEL_ALLOWLIST",
    "FRAGMENT_ALLOWLIST",
    "TECH_REFERENCE_ALLOWLIST",
    "CENSUS_VERB_ALLOWLIST",
    "ENTITY_ALLOWLIST",
]


def _load_core():
    sys.path.insert(0, str(REPO / "language_gate"))
    import language_gate_core_v1 as core  # noqa: E402
    return core


def verify_parity(json_path: Path | None = None) -> tuple[str, list[str], dict]:
    """Return (verdict, reasons, detail). verdict in {CHECK_OK, CHECK_REJECTED}."""
    core = _load_core()
    path = json_path or DEFAULT_JSON
    reasons: list[str] = []
    detail: dict = {"json": str(path), "sets": {}}

    if not path.is_file():
        return "CHECK_REJECTED", [f"externalized JSON absent: {path}"], detail

    doc = json.loads(path.read_text(encoding="utf-8"))
    block = doc.get("allowlists")
    if not isinstance(block, dict):
        return "CHECK_REJECTED", ["JSON has no 'allowlists' object"], detail

    for name in ALLOWLIST_NAMES:
        hardcoded = getattr(core, name)
        if name not in block:
            reasons.append(f"{name}: key missing from JSON")
            detail["sets"][name] = {"parity": False, "reason": "missing key"}
            continue
        # exercise the core loader's prefer-JSON path against this exact file
        loaded = core.load_allowlist(name, json_path=path)
        missing = sorted(set(hardcoded) - loaded)   # in constant, absent from JSON
        extra = sorted(loaded - set(hardcoded))      # in JSON, absent from constant
        ok = not missing and not extra
        detail["sets"][name] = {
            "parity": ok,
            "hardcoded_count": len(hardcoded),
            "json_count": len(loaded),
            "missing_from_json": missing[:8],
            "extra_in_json": extra[:8],
        }
        if not ok:
            reasons.append(
                f"{name}: NOT byte-identical (missing_from_json={missing[:4]} extra_in_json={extra[:4]})"
            )

    verdict = "CHECK_OK" if not reasons else "CHECK_REJECTED"
    return verdict, reasons, detail


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="WI-6 allowlist externalization parity verifier")
    ap.add_argument("--json", type=Path, default=None, help="externalized allowlists JSON")
    args = ap.parse_args(argv)

    verdict, reasons, detail = verify_parity(args.json)
    print(json.dumps({"verdict": verdict, "reasons": reasons, "detail": detail}, indent=2))
    print(f"\n{verdict}  (origin=sandbox-advisory, authority=none, never a governance PASS)")
    return 0 if verdict == "CHECK_OK" else 1


if __name__ == "__main__":
    sys.exit(main())
