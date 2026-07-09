#!/usr/bin/env python3
"""
TH for GV-2 — the knowledge-bundle three-hash validator's own proof.

Grounding artifact (REAL, on disk, unmodified):
  proposals/step4-submitted-knowledge-bundle/knowledge-bundle.json          (the bundle)
  receipts/step4-submitted-knowledge-bundle-receipt.json                     (the descriptor)

  * the REAL bundle+descriptor pair -> CHECK_OK (byte-exact real artifact, no strawman).
  * a MINIMAL MUTATION that stays conformant (edit chunk text, recompute content_sha256 AND
    descriptor.proposed_sha256) -> CHECK_OK.
  * corrupting ONE hex char of proposed_sha256 -> CHECK_REJECTED citing H1 (hash reproduction has teeth).
  * corrupting ONE chunk content_sha256 -> CHECK_REJECTED citing H2 (content integrity).
  * removing ONE required top-level / chunk field -> CHECK_REJECTED (schema is NEVER relaxed).
  * blowing the 20,000-char chunk-text size bound -> CHECK_REJECTED.
  * canonical path->SHA256 map hash reproduces the brain-worker-code-spec rule (sorted/compact).
  * running the validator never edits the subject bundle or descriptor (sha unchanged).
  * verdict vocab CHECK_OK/CHECK_REJECTED, never a bare PASS; stamped origin=sandbox-advisory/authority=none.
"""
from __future__ import annotations
import copy, hashlib, importlib.util, json, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("gv2", HERE / "gv2_bundle_validator.py")
gv2 = importlib.util.module_from_spec(spec); spec.loader.exec_module(gv2)

# Locate the REAL on-disk grounding artifacts (walk up to sg-sandbox root).
def _sandbox_root() -> Path:
    p = HERE
    for _ in range(8):
        if (p / "proposals" / "step4-submitted-knowledge-bundle" / "knowledge-bundle.json").is_file():
            return p
        p = p.parent
    raise RuntimeError("could not locate sg-sandbox root")

ROOT = _sandbox_root()
REAL_BUNDLE = ROOT / "proposals" / "step4-submitted-knowledge-bundle" / "knowledge-bundle.json"
REAL_DESCRIPTOR = ROOT / "receipts" / "step4-submitted-knowledge-bundle-receipt.json"
BUNDLE_OBJ = json.loads(REAL_BUNDLE.read_text())
DESC_OBJ = json.loads(REAL_DESCRIPTOR.read_text())


def _write_pair(tmp: Path, bundle_obj: dict, desc_obj: dict, fix_proposed: bool = True):
    """Write a (bundle, descriptor) pair to tmp. If fix_proposed, set proposed_sha256 to the
    real sha256 of the written bundle bytes so H1 is consistent unless a test corrupts it."""
    bpath = tmp / "kb.json"
    dpath = tmp / "desc.json"
    raw = json.dumps(bundle_obj, indent=2).encode("utf-8")
    bpath.write_bytes(raw)
    desc = copy.deepcopy(desc_obj)
    if fix_proposed:
        desc["proposed_sha256"] = hashlib.sha256(raw).hexdigest()
    dpath.write_text(json.dumps(desc, indent=2))
    return bpath, dpath


def _conformant_mutation() -> dict:
    """MINIMAL mutation of the real bundle that stays conformant: change the chunk text and
    recompute its content_sha256 (the rule the real artifact demonstrates)."""
    b = copy.deepcopy(BUNDLE_OBJ)
    new_text = "Step 4 candidate chunk (minimally mutated): advisory truth layer, recomputed."
    b["chunks"][0]["text"] = new_text
    b["chunks"][0]["metadata"]["content_sha256"] = hashlib.sha256(new_text.encode("utf-8")).hexdigest()
    return b


# --------------------------------------------------------------------------- tests
def test_real_pair_is_accepted():
    # byte-exact REAL on-disk artifact + REAL descriptor -> CHECK_OK
    res = gv2.check(REAL_BUNDLE, REAL_DESCRIPTOR)
    assert res["verdict"] == "CHECK_OK", res


def test_minimally_mutated_conformant_is_accepted():
    with tempfile.TemporaryDirectory() as t:
        bp, dp = _write_pair(Path(t), _conformant_mutation(), DESC_OBJ)
        res = gv2.check(bp, dp)
        assert res["verdict"] == "CHECK_OK", res


def test_corrupt_proposed_sha256_one_char_rejected():
    with tempfile.TemporaryDirectory() as t:
        bp, dp = _write_pair(Path(t), _conformant_mutation(), DESC_OBJ)
        desc = json.loads(dp.read_text())
        p = desc["proposed_sha256"]
        desc["proposed_sha256"] = ("f" if p[0] != "f" else "0") + p[1:]  # flip ONE hex char
        dp.write_text(json.dumps(desc))
        res = gv2.check(bp, dp)
        assert res["verdict"] == "CHECK_REJECTED", res
        assert any(r.startswith("H1") for r in res["hash_reasons"]), res["hash_reasons"]


def test_corrupt_content_sha256_one_char_rejected():
    b = _conformant_mutation()
    cs = b["chunks"][0]["metadata"]["content_sha256"]
    b["chunks"][0]["metadata"]["content_sha256"] = ("f" if cs[0] != "f" else "0") + cs[1:]  # still valid hex64, wrong value
    with tempfile.TemporaryDirectory() as t:
        bp, dp = _write_pair(Path(t), b, DESC_OBJ)
        res = gv2.check(bp, dp)
        assert res["verdict"] == "CHECK_REJECTED", res
        assert any(r.startswith("H2") for r in res["hash_reasons"]), res["hash_reasons"]


def test_remove_required_field_rejected():
    # remove one top-level required key -> rejected (no schema relaxation)
    for field in ("version", "generated_at", "manifest_sha256", "chunks"):
        b = _conformant_mutation()
        del b[field]
        with tempfile.TemporaryDirectory() as t:
            bp, dp = _write_pair(Path(t), b, DESC_OBJ)
            assert gv2.check(bp, dp)["verdict"] == "CHECK_REJECTED", f"removing top-level {field}"
    # remove one required chunk field -> rejected
    for field in ("id", "source", "title", "text"):
        b = _conformant_mutation()
        del b["chunks"][0][field]
        with tempfile.TemporaryDirectory() as t:
            bp, dp = _write_pair(Path(t), b, DESC_OBJ)
            assert gv2.check(bp, dp)["verdict"] == "CHECK_REJECTED", f"removing chunk {field}"
    # remove a required chunk metadata field -> rejected
    b = _conformant_mutation()
    del b["chunks"][0]["metadata"]["content_sha256"]
    with tempfile.TemporaryDirectory() as t:
        bp, dp = _write_pair(Path(t), b, DESC_OBJ)
        assert gv2.check(bp, dp)["verdict"] == "CHECK_REJECTED", "removing metadata.content_sha256"


def test_size_bound_chunk_text_rejected():
    b = _conformant_mutation()
    big = "x" * (gv2.MAX_CHUNK_TEXT + 1)
    b["chunks"][0]["text"] = big
    b["chunks"][0]["metadata"]["content_sha256"] = hashlib.sha256(big.encode()).hexdigest()  # keep H2 valid
    with tempfile.TemporaryDirectory() as t:
        bp, dp = _write_pair(Path(t), b, DESC_OBJ)
        res = gv2.check(bp, dp)
        assert res["verdict"] == "CHECK_REJECTED", res
        assert any("> max" in r for r in res["shape_reasons"]), res["shape_reasons"]


def test_canonical_path_map_hash_reproduces_spec_rule():
    raw = REAL_BUNDLE.read_bytes()
    m = {str(REAL_BUNDLE): gv2.sha256_hex(raw)}
    # independent recomputation of the sorted-keys / compact-JSON rule
    expected = hashlib.sha256(json.dumps(m, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    assert gv2.canonical_path_map_sha256(m) == expected
    # compact rule really is compact (no spaces after separators)
    assert b", " not in gv2.canonical_json_bytes(m) and b": " not in gv2.canonical_json_bytes(m)


def test_running_validator_never_edits_subject():
    b_before = hashlib.sha256(REAL_BUNDLE.read_bytes()).hexdigest()
    d_before = hashlib.sha256(REAL_DESCRIPTOR.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory() as t:
        rc = subprocess.run(
            [sys.executable, str(HERE / "gv2_bundle_validator.py"),
             "--bundle", str(REAL_BUNDLE), "--descriptor", str(REAL_DESCRIPTOR),
             "--emit-verdict-dir", t], text=True, capture_output=True)
        assert rc.returncode == 0, f"real conformant pair should exit 0: {rc.stderr}\n{rc.stdout}"
        assert (Path(t) / "verdict-knowledge-bundle.json").is_file(), "verdict not written to scratch"
    assert hashlib.sha256(REAL_BUNDLE.read_bytes()).hexdigest() == b_before, "bundle was modified!"
    assert hashlib.sha256(REAL_DESCRIPTOR.read_bytes()).hexdigest() == d_before, "descriptor was modified!"


def test_never_emits_pass_and_is_advisory():
    res = gv2.check(REAL_BUNDLE, REAL_DESCRIPTOR)
    assert res["verdict"] in ("CHECK_OK", "CHECK_REJECTED")
    assert res["origin"] == "sandbox-advisory" and res["authority"] == "none" and res["pass_claimed"] is False


TESTS = [
    test_real_pair_is_accepted,
    test_minimally_mutated_conformant_is_accepted,
    test_corrupt_proposed_sha256_one_char_rejected,
    test_corrupt_content_sha256_one_char_rejected,
    test_remove_required_field_rejected,
    test_size_bound_chunk_text_rejected,
    test_canonical_path_map_hash_reproduces_spec_rule,
    test_running_validator_never_edits_subject,
    test_never_emits_pass_and_is_advisory,
]


def _main() -> int:
    failed = 0
    for t in TESTS:
        try:
            t(); print(f"PASS  {t.__name__}")
        except AssertionError as e:
            failed += 1; print(f"FAIL  {t.__name__}: {e}")
    print(f"\n{len(TESTS)-failed}/{len(TESTS)} green")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_main())
