#!/usr/bin/env python3
"""
GV-1 — P0-PGR Execution Receipt Verifier  (catalog build B1 · GV-1)

The 12-stage pipeline names a Receipt Verifier and p0-pgr/P0_EXECUTION_RECEIPT_SCHEMA_v1.json
exists, but no script implements it. This is the adversarial spine: it validates a
real execution receipt against the schema AND runs provenance brakes, then emits a
verdict. It NEVER emits PASS (verdict vocab CHECK_OK / CHECK_REJECTED) and NEVER
edits the audited receipt — verdicts go to a scratch path.

CHECK_OK requires ALL of: schema-valid + quality_state==PASS + founder_authorization_ref
present + >=1 evidence_artifact + non-bare-$0 cost + machine-plausible executed_at +
recorded_at present and >= executed_at. Anything less -> CHECK_REJECTED with cited reasons.
Schema is never relaxed to admit a receipt.

    python3 gv1_receipt_verify.py [--receipt PATH] [--emit-verdict-dir DIR]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
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
SCHEMA_PATH = REPO / "p0-pgr" / "P0_EXECUTION_RECEIPT_SCHEMA_v1.json"
DEFAULT_RECEIPT = REPO / "receipts" / "p0pgr" / "P0PGR-EXEC-M03-20260708T1330Z.json"
_TYPES = {"string": str, "array": list, "object": dict, "number": (int, float), "integer": int, "boolean": bool}


def _schema_errors(obj, schema: dict, path: str = "$") -> list[str]:
    errs: list[str] = []
    t = schema.get("type")
    if t and not isinstance(obj, _TYPES[t]):
        return [f"{path}: expected {t}, got {type(obj).__name__}"]
    if "const" in schema and obj != schema["const"]:
        errs.append(f"{path}: must equal {schema['const']!r}")
    if "enum" in schema and obj not in schema["enum"]:
        errs.append(f"{path}: {obj!r} not in {schema['enum']}")
    if "pattern" in schema and isinstance(obj, str) and not re.search(schema["pattern"], obj):
        errs.append(f"{path}: {obj!r} does not match /{schema['pattern']}/")
    if isinstance(obj, (int, float)) and "minimum" in schema and obj < schema["minimum"]:
        errs.append(f"{path}: {obj} < minimum {schema['minimum']}")
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


def _provenance_reasons(r: dict) -> list[str]:
    reasons: list[str] = []
    if r.get("quality_state") != "PASS":
        reasons.append(f"quality_state is {r.get('quality_state')!r}, not PASS — not PASS-eligible")
    if not str(r.get("founder_authorization_ref") or "").strip():
        reasons.append("no founder_authorization_ref (real execution needs an in-repo unlock receipt)")
    ev = r.get("evidence_artifacts")
    if not isinstance(ev, list) or not ev:
        reasons.append("no evidence_artifacts (stored proof, not prose)")
    cost = r.get("cost") or {}
    if cost.get("total_usd") == 0 and not str(cost.get("accounting_note") or "").strip():
        reasons.append("bare $0 cost with no accounting_note (implausible for executed work)")
    ex = str(r.get("executed_at") or "")
    if re.search(r"[T ]\d{2}:\d{2}:00Z?$", ex) or re.search(r"[T ]\d{2}:00:00", ex):
        reasons.append(f"executed_at {ex!r} is a round :00 timestamp (machine timestamps rarely land on :00)")
    rec = r.get("recorded_at")
    if not rec:
        reasons.append("recorded_at absent (cannot verify write-time provenance)")
    elif r.get("executed_at") and str(rec) < str(r.get("executed_at")):
        reasons.append("recorded_at predates executed_at (impossible ordering)")
    return reasons


def verify(receipt: dict) -> dict:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    schema_errs = _schema_errors(receipt, schema)
    prov = _provenance_reasons(receipt)
    verdict = "CHECK_OK" if not schema_errs and not prov else "CHECK_REJECTED"
    self_label = str(receipt.get("quality_state") or receipt.get("pass_fail") or "").split()[0] if receipt.get("pass_fail") else receipt.get("quality_state")
    auditor_says_ok = verdict == "CHECK_OK"
    receipt_claims_pass = str(receipt.get("quality_state")) == "PASS"
    reconcile = {
        "receipt_self_quality_state": receipt.get("quality_state"),
        "auditor_verdict": verdict,
        "auditor_disagrees_with_receipt": auditor_says_ok != receipt_claims_pass,
    }
    return {
        "origin": "sandbox-advisory", "authority": "none", "verdict": verdict,
        "subject_packet_id": receipt.get("packet_id"),
        "schema_errors": schema_errs, "provenance_reasons": prov, "reconcile": reconcile,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    ap.add_argument("--emit-verdict-dir", type=Path, default=Path(__file__).resolve().parent / "verdicts")
    args = ap.parse_args(argv)

    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    result = verify(receipt)
    result["subject_receipt"] = str(args.receipt)

    args.emit_verdict_dir.mkdir(parents=True, exist_ok=True)
    vp = args.emit_verdict_dir / f"verdict-{args.receipt.stem}.json"
    vp.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")   # verdict to SCRATCH, never the subject

    print(f"GV-1 RECEIPT_VERIFY: {result['verdict']}  ({args.receipt.name})")
    for e in result["schema_errors"]:
        print(f"  [schema]     {e}")
    for e in result["provenance_reasons"]:
        print(f"  [provenance] {e}")
    if result["reconcile"]["auditor_disagrees_with_receipt"]:
        print("  AUDITOR_DISAGREES_WITH_RECEIPT")
    print(f"  verdict written -> {vp}")
    return 0 if result["verdict"] == "CHECK_OK" else 1


if __name__ == "__main__":
    sys.exit(main())
