#!/usr/bin/env python3
"""
CI-3 — Reusable receipt validator  (catalog build B4 · CI)

The p0pgr-shadow-cycle-v1 workflow carries an inline "Independent receipt
validation" step that shells out to jsonschema.Draft202012Validator against
p0-pgr/P0_PROMPT_LOOP_STATE_SCHEMA_v1.json. That logic is trapped inside one
workflow. This is the extracted, dependency-free (no jsonschema) validator that
the sibling composite action.yml calls — take a receipt path + a schema path,
validate REPORT-ONLY, print findings, exit 1 on any error, 0 when conformant.

Report-only: it NEVER edits the receipt or the schema, never writes Supabase,
never writes a receipt, never fails-on-block-merge. It only reads two files and
prints. The consuming CI step is non-blocking (continue-on-error).

    python3 validate_receipt.py --receipt PATH --schema PATH
    python3 validate_receipt.py --receipt PATH --schema PATH --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_TYPES = {
    "string": str,
    "array": list,
    "object": dict,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
    "null": type(None),
}


def schema_errors(obj, schema: dict, path: str = "$") -> list[str]:
    """Minimal JSON-Schema check covering the constructs the loop-state schema uses.

    Supports: type, required, properties, additionalProperties:false, enum, const,
    pattern, minItems, minLength, minimum, maximum, items. jsonschema-free.
    """
    errs: list[str] = []
    t = schema.get("type")
    if t and not isinstance(obj, _TYPES[t]):
        # bool is an int subclass in python; keep integers honest
        if not (t == "integer" and isinstance(obj, bool) is False and isinstance(obj, int)):
            return [f"{path}: expected {t}, got {type(obj).__name__}"]
    if t == "integer" and isinstance(obj, bool):
        errs.append(f"{path}: expected integer, got boolean")

    if "const" in schema and obj != schema["const"]:
        errs.append(f"{path}: must equal {schema['const']!r}")
    if "enum" in schema and obj not in schema["enum"]:
        errs.append(f"{path}: {obj!r} not in allowed {schema['enum']}")
    if "pattern" in schema and isinstance(obj, str) and not re.search(schema["pattern"], obj):
        errs.append(f"{path}: {obj!r} does not match /{schema['pattern']}/")
    if isinstance(obj, str) and "minLength" in schema and len(obj) < schema["minLength"]:
        errs.append(f"{path}: shorter than minLength {schema['minLength']}")
    if isinstance(obj, (int, float)) and not isinstance(obj, bool):
        if "minimum" in schema and obj < schema["minimum"]:
            errs.append(f"{path}: {obj} < minimum {schema['minimum']}")
        if "maximum" in schema and obj > schema["maximum"]:
            errs.append(f"{path}: {obj} > maximum {schema['maximum']}")

    if t == "object" and isinstance(obj, dict):
        props = schema.get("properties", {})
        for req in schema.get("required", []):
            if req not in obj:
                errs.append(f"{path}: missing required field '{req}'")
        if schema.get("additionalProperties") is False:
            for k in obj:
                if k not in props:
                    errs.append(f"{path}: unexpected field '{k}' (additionalProperties=false)")
        for k, sub in props.items():
            if k in obj:
                errs += schema_errors(obj[k], sub, f"{path}.{k}")

    if t == "array" and isinstance(obj, list):
        if "minItems" in schema and len(obj) < schema["minItems"]:
            errs.append(f"{path}: needs >= {schema['minItems']} items, has {len(obj)}")
        items = schema.get("items")
        if items:
            for i, el in enumerate(obj):
                errs += schema_errors(el, items, f"{path}[{i}]")
    return errs


def validate(receipt_path: Path, schema_path: Path) -> dict:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errs = schema_errors(receipt, schema)
    return {
        "origin": "sandbox-advisory",
        "authority": "none",
        "receipt": str(receipt_path),
        "schema": str(schema_path),
        "verdict": "CHECK_OK" if not errs else "CHECK_REJECTED",
        "errors": errs,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--receipt", type=Path, required=True)
    ap.add_argument("--schema", type=Path, required=True)
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON (report mode)")
    args = ap.parse_args(argv)

    result = validate(args.receipt, args.schema)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"CI-3 VALIDATE_RECEIPT: {result['verdict']}  ({args.receipt.name} vs {args.schema.name})")
        for e in result["errors"]:
            print(f"  - {e}")
    return 0 if result["verdict"] == "CHECK_OK" else 1


if __name__ == "__main__":
    sys.exit(main())
