#!/usr/bin/env python3
"""
GV-3 — In-library CHESS pass validator CLI  (catalog build B0 · GV-3)

The library ships SCHEMAS/chess_pass.schema.json and a manifest that lists a
forbidden action label (BLOCK), but nothing enforces either. This is the missing
checker: it validates a CHESS pass against the schema AND asserts the action is
not a forbidden label. It also reports dangling manifest file refs (the manifest
points at TOOLS/chess_pass_cli.py + TOOLS/README.md, which are absent).

Standalone, library-internal, dependency-free (no jsonschema). Nothing downstream
depends on it (BR-3 is not gated by GV-3). Read-only; reports, never edits.

Exits 1 on any validation error / forbidden label / dangling manifest ref, else 0.

    python3 gv3_chess_pass_validate.py                     # validate the sample pass
    python3 gv3_chess_pass_validate.py --pass PATH
    python3 gv3_chess_pass_validate.py --manifest-check
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                             cwd=Path(__file__).resolve().parent, text=True, capture_output=True, check=True)
        return Path(out.stdout.strip())
    except Exception:
        return Path(__file__).resolve().parents[3]


REPO = _repo_root()
LIB = REPO / "SG-Canonical-Library" / "noetfield-library"
SCHEMA_PATH = LIB / "SCHEMAS" / "chess_pass.schema.json"
MANIFEST_PATH = LIB / "CHESS-v2" / "manifest.json"
SAMPLE_PATH = LIB / "EXAMPLES" / "sample_chess_pass.json"

_TYPES = {"string": str, "array": list, "object": dict, "number": (int, float), "boolean": bool}


def _validate(obj, schema: dict, path: str = "$") -> list[str]:
    """Minimal JSON-Schema check covering the constructs chess_pass.schema.json uses."""
    errs: list[str] = []
    t = schema.get("type")
    if t and not isinstance(obj, _TYPES[t]):
        return [f"{path}: expected {t}, got {type(obj).__name__}"]
    if t == "object":
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
                errs += _validate(obj[k], sub, f"{path}.{k}")
    elif t == "array":
        items = schema.get("items")
        if items:
            for i, el in enumerate(obj):
                errs += _validate(el, items, f"{path}[{i}]")
    if "enum" in schema and obj not in schema["enum"]:
        errs.append(f"{path}: value {obj!r} not in allowed {schema['enum']}")
    return errs


def forbidden_action_labels() -> list[str]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8")).get("forbidden_action_labels", [])


def validate_pass(pass_obj: dict) -> list[str]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errs = _validate(pass_obj, schema)
    forbidden = forbidden_action_labels()
    if pass_obj.get("action") in forbidden:
        errs.append(f"$.action: forbidden label {pass_obj.get('action')!r} (manifest forbidden_action_labels)")
    return errs


def manifest_dangling() -> list[str]:
    man = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    missing = []
    for f in man.get("files", []):
        if not (LIB / f).is_file() and not (LIB / "CHESS-v2" / f).is_file():
            missing.append(f)
    return missing


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pass", dest="pass_path", type=Path, default=SAMPLE_PATH)
    ap.add_argument("--manifest-check", action="store_true")
    args = ap.parse_args(argv)

    rc = 0
    if args.manifest_check:
        missing = manifest_dangling()
        if missing:
            print("GV-3 MANIFEST: DANGLING file refs:")
            for m in missing:
                print(f"  - {m} (listed in manifest, absent on disk)")
            rc = 1
        else:
            print("GV-3 MANIFEST: CHECK_OK (all manifest files present)")
        return rc

    pass_obj = json.loads(args.pass_path.read_text(encoding="utf-8"))
    errs = validate_pass(pass_obj)
    if errs:
        print(f"GV-3 CHESS_PASS: INVALID ({args.pass_path.name}):")
        for e in errs:
            print(f"  - {e}")
        return 1
    print(f"GV-3 CHESS_PASS: CHECK_OK ({args.pass_path.name} — schema valid, action not forbidden)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
