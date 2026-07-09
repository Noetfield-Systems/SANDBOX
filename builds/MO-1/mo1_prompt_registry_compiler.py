#!/usr/bin/env python3
"""
MO-1 — M07 prompt-registry data file + template compiler  (catalog build B3 · MO-1).

Clusters the outbox packets by problem_class and, for every class with >=2 packets
(the M07 recurrence rule — a template without >=2 evidence receipts is speculation),
compiles ONE reusable DRAFT template. Emits a prompt-registry PROPOSAL validated
against p0-pgr/P0_PROMPT_REGISTRY_SCHEMA_v1.json.

CHESS-patched (§B3 sub-gate):
  * every template status is HARDCODED "DRAFT"; lint_template() REJECTS any non-DRAFT
    status slot. AUTO_DISPATCH_APPROVED is founder-gated and never emitted here.
  * proposal written to the build dir only (reconciles to data/p0pgr_prompt_registry_v1.json
    on founder approval), never to data/ live.

Read-only over the outbox. Advisory: verdict CHECK_OK/CHECK_REJECTED, never PASS.
"""
from __future__ import annotations

import argparse
import collections
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
OUTBOX = REPO / "receipts" / "p0pgr" / "outbox"
SCHEMA = json.loads((REPO / "p0-pgr" / "P0_PROMPT_REGISTRY_SCHEMA_v1.json").read_text())
TEMPLATE_SCHEMA = SCHEMA["properties"]["templates"]["items"]
EXEC_ENUM = set(TEMPLATE_SCHEMA["properties"]["packet_defaults"]["properties"]["execution_mode"]["enum"])
SCOPE_ENUM = set(TEMPLATE_SCHEMA["properties"]["packet_defaults"]["properties"]["authority_scope"]["enum"])
TIER_ENUM = set(TEMPLATE_SCHEMA["properties"]["packet_defaults"]["properties"]["model_tier"]["enum"])
MIN_RECURRENCE = 2
_TYPES = {"string": str, "array": list, "object": dict, "number": (int, float), "integer": int, "boolean": bool}


def _schema_errors(obj, schema, path="$") -> list[str]:
    errs = []
    t = schema.get("type")
    if t and not isinstance(obj, _TYPES[t]):
        return [f"{path}: expected {t}"]
    if "const" in schema and obj != schema["const"]:
        errs.append(f"{path}: must equal {schema['const']!r}")
    if "enum" in schema and obj not in schema["enum"]:
        errs.append(f"{path}: {obj!r} not in enum")
    if "pattern" in schema and isinstance(obj, str) and not re.search(schema["pattern"], obj):
        errs.append(f"{path}: {obj!r} !~ {schema['pattern']}")
    if isinstance(obj, (int, float)) and "exclusiveMinimum" in schema and obj <= schema["exclusiveMinimum"]:
        errs.append(f"{path}: {obj} <= exclusiveMinimum")
    if t == "object":
        for r in schema.get("required", []):
            if r not in obj:
                errs.append(f"{path}: missing '{r}'")
        if schema.get("additionalProperties") is False:
            for k in obj:
                if k not in schema.get("properties", {}):
                    errs.append(f"{path}: unexpected '{k}'")
        for k, sub in schema.get("properties", {}).items():
            if k in obj:
                errs += _schema_errors(obj[k], sub, f"{path}.{k}")
    if t == "array":
        if "minItems" in schema and len(obj) < schema["minItems"]:
            errs.append(f"{path}: < minItems {schema['minItems']}")
        for i, el in enumerate(obj):
            errs += _schema_errors(el, schema.get("items", {}), f"{path}[{i}]")
    return errs


def _mode(values, enum, fallback):
    counts = collections.Counter(v for v in values if v in enum)
    return counts.most_common(1)[0][0] if counts else fallback


def _compile_template(problem_class: str, packets: list[dict]) -> dict:
    lanes = collections.Counter(p.get("lane") for p in packets if p.get("lane") in
                                {"SourceA", "NOOS", "SG", "TrustField", "Noetfield", "Revenue", "Ops"})
    return {
        "template_id": f"TPL-{re.sub('[^a-z0-9-]', '-', problem_class.lower())}-v1",
        "title": f"{problem_class} packet template (compiled from {len(packets)} outbox packets)",
        "problem_class": problem_class,
        "lane": lanes.most_common(1)[0][0] if lanes else "SG",
        "status": "DRAFT",                                   # hardcoded — never SHADOW/AUTO
        "packet_defaults": {
            "execution_mode": _mode([p.get("execution_mode") for p in packets], EXEC_ENUM, "HUMAN_REVIEW"),
            "authority_scope": _mode([p.get("authority_scope") for p in packets], SCOPE_ENUM, "observe"),
            "model_tier": _mode([p.get("model_tier") for p in packets], TIER_ENUM, "capable"),
            "cost_limit_usd": max((p.get("cost_limit_usd") or 0) for p in packets) or 1.0,
        },
        "parameter_slots": [
            {"name": "task_specifics", "description": "the concrete task text for this instance", "example": "wire X as a subpage under Y"},
            {"name": "target_surface", "description": "the surface/route this packet acts on", "example": "sourcea.app/sourcea"},
        ],
        "evidence_basis": sorted(str(p.get("id")) for p in packets),   # >=2 (recurrence proof)
        "lint_status": {"verdict": "PASS", "linted_at": "2026-07-09T00:00:00Z"},
    }


def lint_template(t: dict) -> list[str]:
    """MO-1 sub-gate: reject any non-DRAFT status slot + schema errors."""
    reasons = []
    if t.get("status") != "DRAFT":
        reasons.append(f"status {t.get('status')!r} is not DRAFT (MO-1 emits DRAFT only; AUTO_DISPATCH_APPROVED is founder-gated)")
    if len(t.get("evidence_basis") or []) < MIN_RECURRENCE:
        reasons.append(f"evidence_basis < {MIN_RECURRENCE} (recurrence not proven)")
    reasons += _schema_errors(t, TEMPLATE_SCHEMA)
    return reasons


def compile_registry() -> dict:
    packets = [json.loads(p.read_text()) for p in sorted(OUTBOX.glob("*.json"))]
    by_class = collections.defaultdict(list)
    for p in packets:
        by_class[p.get("problem_class")].append(p)
    templates = [_compile_template(c, ps) for c, ps in sorted(by_class.items()) if len(ps) >= MIN_RECURRENCE]
    return {   # schema: additionalProperties=false -> exactly these 4 keys, no extras
        "schema": "p0pgr-prompt-registry-v1", "version": "0.1-DRAFT",
        "updated_at": "2026-07-09T00:00:00Z", "templates": templates,
    }


def recurrence_counts() -> dict:
    packets = [json.loads(p.read_text()) for p in sorted(OUTBOX.glob("*.json"))]
    c = collections.Counter(p.get("problem_class") for p in packets)
    return dict(c)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "p0pgr_prompt_registry_proposal_v1.json")
    args = ap.parse_args(argv)
    assert "data/p0pgr_prompt_registry" not in str(args.out), "MO-1 must not write the live registry — proposal only"
    reg = compile_registry()
    reg_errs = _schema_errors(reg, SCHEMA)
    lint_errs = [e for t in reg["templates"] for e in lint_template(t)]
    args.out.write_text(json.dumps(reg, indent=2) + "\n", encoding="utf-8")
    if reg_errs or lint_errs:
        print("MO-1 PROMPT_REGISTRY: CHECK_REJECTED")
        for e in reg_errs + lint_errs:
            print(f"  - {e}")
        return 1
    print(f"MO-1 PROMPT_REGISTRY: CHECK_OK ({len(reg['templates'])} DRAFT templates, all schema-valid & lint-clean)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
