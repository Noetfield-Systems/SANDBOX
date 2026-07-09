#!/usr/bin/env python3
"""
BR-4 — Node <-> schema descriptor-validator parity / differential test  (B1).

Cross-checks the live worker's pure validateArtifactDescriptor (extracted from the
CURRENT workers/github-app-advisory/index.js and run in node — never the live
worker) against the schema-of-record verifier/brain-config-artifact-descriptor-schema-v0.1.json
(validated in Python). Precondition: GV-2 built (catalog/builds/GV-2/).

On the CORE descriptor rules both agree. It also SURFACES two real divergences
(the JS is more permissive than the schema) as findings, not failures:
  * artifact_type: schema const 'knowledge_bundle' vs JS also allows 'brain_worker_bundle'
  * additionalProperties: schema false (rejects extras) vs JS ignores extras

Node is required. No network, no live worker call.
"""
from __future__ import annotations
import copy, json, re, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=HERE,
                           text=True, capture_output=True, check=True).stdout.strip())
INDEX_JS = REPO / "workers" / "github-app-advisory" / "index.js"
SCHEMA = json.loads((REPO / "verifier" / "brain-config-artifact-descriptor-schema-v0.1.json").read_text())
GV2_DESCRIPTOR = json.loads((REPO / "catalog" / "builds" / "GV-2" / "fixture" / "descriptor.json").read_text())
_T = {"string": str, "number": (int, float), "integer": int, "boolean": bool, "object": dict, "array": list}


def schema_ok(desc: dict) -> tuple[bool, list[str]]:
    s, errs = SCHEMA, []
    if s.get("additionalProperties") is False:
        for k in desc:
            if k not in s["properties"]:
                errs.append(f"additionalProperties: unexpected '{k}'")
    for r in s.get("required", []):
        if r not in desc:
            errs.append(f"missing required '{r}'")
    for k, sub in s["properties"].items():
        if k not in desc:
            continue
        v = desc[k]
        if "type" in sub and not isinstance(v, _T[sub["type"]]):
            errs.append(f"{k}: wrong type")
        if "const" in sub and v != sub["const"]:
            errs.append(f"{k}: must equal {sub['const']!r}")
        if "pattern" in sub and (not isinstance(v, str) or not re.search(sub["pattern"], v)):
            errs.append(f"{k}: pattern")
        if "enum" in sub and v not in sub["enum"]:
            errs.append(f"{k}: enum")
        if "minLength" in sub and (not isinstance(v, str) or len(v) < sub["minLength"]):
            errs.append(f"{k}: minLength")
    return (not errs, errs)


def js_ok(desc: dict) -> tuple[bool, list[str]]:
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "d.json"; p.write_text(json.dumps(desc))
        out = subprocess.run(["node", str(HERE / "br4_js_validate.mjs"), str(p), str(INDEX_JS)],
                             text=True, capture_output=True)
        assert out.returncode == 0, f"node failed: {out.stderr}"
        r = json.loads(out.stdout)
        return (r["ok"], r["failures"])


# clean descriptor both must accept (drop the sha_note/extras that would trip additionalProperties)
CLEAN = {k: GV2_DESCRIPTOR[k] for k in SCHEMA["required"]}


def _mut(**over):
    d = dict(CLEAN); d.update(over); return d


CORE_MUTATIONS = [
    ("missing_field",   {k: v for k, v in CLEAN.items() if k != "author_id"}),
    ("bad_author",      _mut(author_id="attacker")),
    ("bad_subject",     _mut(subject="something else")),
    ("nonhex_proposed", _mut(proposed_sha256="XYZ")),
    ("nonbool_schema",  _mut(schema_valid="yes")),
    ("empty_runtime",   _mut(validator_runtime="")),
]


def test_clean_descriptor_accepted_by_both():
    assert schema_ok(CLEAN)[0] is True, schema_ok(CLEAN)
    assert js_ok(CLEAN)[0] is True, js_ok(CLEAN)


def test_core_mutations_rejected_by_both_parity():
    for cid, desc in CORE_MUTATIONS:
        so, _ = schema_ok(desc); jo, _ = js_ok(desc)
        assert so == jo == False, f"[{cid}] parity broken: schema_ok={so} js_ok={jo}"


def test_known_divergences_are_detected():
    # JS more permissive than the schema-of-record -> BR-4 surfaces these.
    # brain_worker_bundle is a full valid descriptor to the JS (it requires the two extra
    # worker shas), but the schema pins artifact_type const knowledge_bundle + additionalProperties:false.
    bw = _mut(artifact_type="brain_worker_bundle", worker_code_sha256="a" * 64, knowledge_bundle_sha256="b" * 64)
    assert schema_ok(bw)[0] is False and js_ok(bw)[0] is True, f"artifact_type divergence not detected: schema={schema_ok(bw)} js={js_ok(bw)}"
    extra = _mut(surprise="x")
    assert schema_ok(extra)[0] is False and js_ok(extra)[0] is True, f"additionalProperties divergence not detected: schema={schema_ok(extra)} js={js_ok(extra)}"


TESTS = [test_clean_descriptor_accepted_by_both, test_core_mutations_rejected_by_both_parity,
         test_known_divergences_are_detected]


def _main() -> int:
    failed = 0
    for t in TESTS:
        try: t(); print(f"PASS  {t.__name__}")
        except AssertionError as e: failed += 1; print(f"FAIL  {t.__name__}: {e}")
    print(f"\n{len(TESTS)-failed}/{len(TESTS)} green")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_main())
