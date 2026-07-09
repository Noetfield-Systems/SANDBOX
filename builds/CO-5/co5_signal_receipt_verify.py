#!/usr/bin/env python3
"""
CO-5 — Signal Factory structural receipt verifier  (catalog build B4 · CO-5)

Ground contract:
  SG-Canonical-Library/noetfield-library/P9-PATTERN-FACTORY/signal-factory-v1.md
  ("Every triage emits a structural-verifier-checked JSON receipt (author≠subject:
   the triage agent ≠ the verifier/subject)") + the signal-factory SKILL receipt shape.

The output contract is encoded once as signal_factory_receipt_schema_v1.json. This
verifier validates a Signal Factory receipt against that schema AND enforces the two
contract invariants the schema alone cannot express:

  1. author != subject   — the triage agent must not be the entity it triaged
                           (no self-triage; independence of the receipt).
  2. every score in 0..5  — trust / risk / automation_value / commercial_value,
                           and risk_score must equal scores.risk.

It emits an ADVISORY verdict (CHECK_OK / CHECK_REJECTED — never PASS) and NEVER edits
the subject receipt; verdicts are written to a scratch dir. A conformant receipt is
CHECK_OK; author==subject or an out-of-bounds score is CHECK_REJECTED with cited reasons.

    python3 co5_signal_receipt_verify.py [--receipt PATH] [--emit-verdict-dir DIR]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMA_PATH = HERE / "signal_factory_receipt_schema_v1.json"
DEFAULT_RECEIPT = HERE / "fixtures" / "receipt_conformant.json"

SCORE_DIMS = ("trust", "risk", "automation_value", "commercial_value")
SCORE_MIN, SCORE_MAX = 0, 5

_TYPES = {
    "string": str, "array": list, "object": dict,
    "number": (int, float), "integer": int, "boolean": bool,
}


def _schema_errors(obj, schema: dict, path: str = "$") -> list[str]:
    """Minimal, dependency-free structural validator (type/const/enum/pattern/
    minimum/maximum/minLength/required/properties). Never relaxed to admit input."""
    errs: list[str] = []
    t = schema.get("type")
    # bool is a subtype of int in Python; reject it explicitly for integer/number.
    if t in ("integer", "number") and isinstance(obj, bool):
        return [f"{path}: expected {t}, got bool"]
    if t and not isinstance(obj, _TYPES[t]):
        return [f"{path}: expected {t}, got {type(obj).__name__}"]
    if "const" in schema and obj != schema["const"]:
        errs.append(f"{path}: must equal {schema['const']!r}")
    if "enum" in schema and obj not in schema["enum"]:
        errs.append(f"{path}: {obj!r} not in {schema['enum']}")
    if "pattern" in schema and isinstance(obj, str) and not re.search(schema["pattern"], obj):
        errs.append(f"{path}: {obj!r} does not match /{schema['pattern']}/")
    if isinstance(obj, str) and "minLength" in schema and len(obj) < schema["minLength"]:
        errs.append(f"{path}: shorter than minLength {schema['minLength']}")
    if isinstance(obj, (int, float)) and not isinstance(obj, bool):
        if "minimum" in schema and obj < schema["minimum"]:
            errs.append(f"{path}: {obj} < minimum {schema['minimum']}")
        if "maximum" in schema and obj > schema["maximum"]:
            errs.append(f"{path}: {obj} > maximum {schema['maximum']}")
    if t == "object":
        for req in schema.get("required", []):
            if not isinstance(obj, dict) or req not in obj:
                errs.append(f"{path}: missing required field '{req}'")
        for k, sub in schema.get("properties", {}).items():
            if isinstance(obj, dict) and k in obj:
                errs += _schema_errors(obj[k], sub, f"{path}.{k}")
    if t == "array":
        if "minItems" in schema and len(obj) < schema["minItems"]:
            errs.append(f"{path}: needs >= {schema['minItems']} items, has {len(obj)}")
        if schema.get("items"):
            for i, el in enumerate(obj):
                errs += _schema_errors(el, schema["items"], f"{path}[{i}]")
    return errs


def _contract_reasons(r: dict) -> list[str]:
    """The two invariants the flat schema can't express."""
    reasons: list[str] = []

    # (1) author != subject — independence of the triage.
    author = r.get("author")
    subject = r.get("subject")
    if isinstance(author, str) and isinstance(subject, str):
        if author.strip().lower() == subject.strip().lower():
            reasons.append(
                f"author == subject ({author!r}) — the triage agent must differ "
                "from the signal's subject (author≠subject independence rule)"
            )

    # (2) score bounds 0..5 on every dimension (explicit, in addition to schema).
    scores = r.get("scores")
    if isinstance(scores, dict):
        for dim in SCORE_DIMS:
            if dim not in scores:
                reasons.append(f"scores.{dim} missing (required 0..5 dimension)")
                continue
            v = scores[dim]
            if isinstance(v, bool) or not isinstance(v, int):
                reasons.append(f"scores.{dim} = {v!r} is not an integer score")
            elif not (SCORE_MIN <= v <= SCORE_MAX):
                reasons.append(f"scores.{dim} = {v} is out of bounds (must be {SCORE_MIN}..{SCORE_MAX})")
    else:
        reasons.append("scores object absent — cannot bound-check the four dimensions")

    # (3) risk_score must mirror scores.risk (SKILL 'matching the SCORES line').
    rs = r.get("risk_score")
    if isinstance(scores, dict) and "risk" in scores and not isinstance(rs, bool) and isinstance(rs, int):
        if rs != scores.get("risk"):
            reasons.append(f"risk_score ({rs}) does not match scores.risk ({scores.get('risk')})")

    return reasons


def verify(receipt: dict) -> dict:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    schema_errs = _schema_errors(receipt, schema)
    contract = _contract_reasons(receipt)
    verdict = "CHECK_OK" if not schema_errs and not contract else "CHECK_REJECTED"
    return {
        "origin": "sandbox-advisory",
        "authority": "none",
        "verdict": verdict,
        "subject_signal_id": receipt.get("signal_id"),
        "schema_errors": schema_errs,
        "contract_reasons": contract,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    ap.add_argument("--emit-verdict-dir", type=Path, default=HERE / "verdicts")
    args = ap.parse_args(argv)

    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    result = verify(receipt)
    result["subject_receipt"] = str(args.receipt)

    # Verdict to SCRATCH — never mutate the subject receipt (append-only, Lock 5).
    args.emit_verdict_dir.mkdir(parents=True, exist_ok=True)
    vp = args.emit_verdict_dir / f"verdict-{args.receipt.stem}.json"
    vp.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(f"CO-5 SIGNAL_RECEIPT_VERIFY: {result['verdict']}  ({args.receipt.name})")
    for e in result["schema_errors"]:
        print(f"  [schema]   {e}")
    for e in result["contract_reasons"]:
        print(f"  [contract] {e}")
    print(f"  verdict written -> {vp}")
    return 0 if result["verdict"] == "CHECK_OK" else 1


if __name__ == "__main__":
    sys.exit(main())
