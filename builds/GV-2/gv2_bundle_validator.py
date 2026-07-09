#!/usr/bin/env python3
"""
GV-2 — Knowledge-Bundle Executable Spec + Three-Hash Validator  (catalog build B1 · GV-2)

The knowledge-bundle-spec-v0.1.md + brain-worker-code-spec-v0.1.md define what a valid
SourceA Brain knowledge bundle looks like, and the canonical hashing rules, but nothing
EXECUTES that spec offline. This tool does: it reproduces the specs' canonical hashing
rules and validates a knowledge bundle (shape / required keys / size bounds / must-parse /
chunk metadata) plus a three-hash descriptor cross-check, entirely offline (D4).

It NEVER emits a bare governance PASS — verdict vocab is CHECK_OK / CHECK_REJECTED — and
it NEVER edits the audited bundle or descriptor; verdicts are written to a scratch dir.

Canonical hashing rules reproduced (verbatim from the specs):
  * bundle-bytes hash: SHA256 over the EXACT submitted bundle bytes
    (knowledge-bundle-spec "Hash Rules": submitted bundle SHA256 MUST match proposed_sha256).
  * canonical path->SHA256 map hash: SHA256 of a UTF-8 JSON object mapping each path to its
    SHA256, keys SORTED, COMPACT JSON (no spaces after separators) — brain-worker-code-spec
    "Hash rules" (worker_code_sha256 / proposed_sha256).

Three hashes cross-checked for a knowledge_bundle descriptor (offline D4):
  H1  descriptor.proposed_sha256  == sha256(bundle bytes)          [spec: MUST match]
  H2  every chunk's content hash  == sha256(chunk content)          [content integrity]
  H3  descriptor.base_sha256      present and valid SHA256 hex       [spec: MUST be present/valid]

Ambiguity notes (encoded exactly as the specs state; where silent, noted not assumed):
  * The spec lists TWO alternative valid shapes ("original proposal" and "current SourceA
    Brain"). A bundle is accepted only if it FULLY satisfies one complete shape; shapes are
    never mixed and never relaxed. Shape is selected by discriminator key (bundle_version =>
    current, else original).
  * H2 content-integrity: the spec REQUIRES metadata.content_sha256 to be lowercase 64-hex
    but does not TEXTUALLY define what bytes it hashes. The on-disk real artifact demonstrates
    content_sha256 == sha256(chunk["text"]); we reproduce that rule for the original shape and
    note it is inferred from the artifact, not stated in prose. For the current SourceA shape
    the spec only bounds content_hash shape (>=16 hex), so H2 there is shape-only (documented).

    python3 gv2_bundle_validator.py [--bundle PATH] [--descriptor PATH] [--emit-verdict-dir DIR]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_BUNDLE = HERE / "fixture" / "knowledge-bundle.json"
DEFAULT_DESCRIPTOR = HERE / "fixture" / "descriptor.json"

HEX64 = re.compile(r"^[a-f0-9]{64}$")
HEX_MIN16 = re.compile(r"^[a-f0-9]{16,}$")

# knowledge-bundle-spec-v0.1.md "Size Bounds"
MIN_FILE_BYTES = 2
MAX_FILE_BYTES = 1_000_000
MAX_CHUNKS = 2_000
MAX_CHUNK_TEXT = 20_000

# knowledge-bundle-spec-v0.1.md: "No top-level executable code, functions, scripts, or HTML
# event handlers are valid bundle content." Conservative offline detectors:
_CODE_PATTERNS = [
    re.compile(r"<\s*/?\s*script", re.I),
    re.compile(r"\son[a-z]+\s*=\s*['\"]", re.I),   # inline HTML event handler e.g. onerror="
    re.compile(r"javascript:", re.I),
]


# ---------------------------------------------------------------------------
# canonical hashing rules (reproduced verbatim from the specs)
# ---------------------------------------------------------------------------
def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json_bytes(obj) -> bytes:
    """UTF-8 JSON, keys SORTED, COMPACT separators (no spaces) — brain-worker-code-spec."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_path_map_sha256(path_to_sha256: dict) -> str:
    """SHA256 of the sorted-keys/compact JSON object mapping each path to its SHA256.

    This is the brain-worker-code-spec rule for worker_code_sha256 / proposed_sha256.
    """
    return sha256_hex(canonical_json_bytes(path_to_sha256))


# ---------------------------------------------------------------------------
# bundle shape validation (knowledge-bundle-spec-v0.1.md)
# ---------------------------------------------------------------------------
def _nonempty_str(v) -> bool:
    return isinstance(v, str) and v.strip() != ""


def _scan_executable(node, path: str, reasons: list) -> None:
    if isinstance(node, str):
        for pat in _CODE_PATTERNS:
            if pat.search(node):
                reasons.append(f"executable/HTML-handler content at {path} (spec: not valid bundle content)")
                return
    elif isinstance(node, dict):
        for k, v in node.items():
            _scan_executable(v, f"{path}.{k}", reasons)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _scan_executable(v, f"{path}[{i}]", reasons)


def validate_bundle_bytes(raw: bytes) -> list:
    """Return a list of rejection reasons; empty list => bundle shape is valid.

    Enforces: size bounds, must-parse, root object, chunks array, per-shape required
    top-level keys and chunk metadata, size caps, and the no-executable-content rule.
    """
    reasons: list = []

    # --- Size Bounds (file-level) ---
    if len(raw) < MIN_FILE_BYTES:
        reasons.append(f"file {len(raw)} bytes < minimum {MIN_FILE_BYTES}")
    if len(raw) > MAX_FILE_BYTES:
        reasons.append(f"file {len(raw)} bytes > maximum {MAX_FILE_BYTES}")

    # --- Must Parse ---
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return reasons + ["bytes do not decode as UTF-8"]
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as e:
        return reasons + [f"JSON parse failed: {e}"]
    if not isinstance(obj, dict):
        return reasons + ["root value is not a JSON object"]
    if "chunks" not in obj or not isinstance(obj["chunks"], list):
        return reasons + ["'chunks' missing or not an array"]
    if len(obj["chunks"]) == 0:
        reasons.append("'chunks' is empty (spec requires non-empty array)")
    for i, ch in enumerate(obj["chunks"]):
        if not isinstance(ch, dict):
            reasons.append(f"chunks[{i}] is not an object")

    # --- Size Bounds (chunk-level) ---
    if len(obj["chunks"]) > MAX_CHUNKS:
        reasons.append(f"{len(obj['chunks'])} chunks > maximum {MAX_CHUNKS}")

    # --- Shape selection (never mixed / never relaxed) ---
    is_current = "bundle_version" in obj or "chunk_count" in obj
    if is_current:
        reasons += _validate_current_shape(obj)
    else:
        reasons += _validate_original_shape(obj)

    # --- No executable content ---
    _scan_executable(obj, "$", reasons)
    return reasons


def _validate_original_shape(obj: dict) -> list:
    reasons: list = []
    for k in ("version", "generated_at", "manifest_sha256", "chunks"):
        if k not in obj:
            reasons.append(f"[original shape] missing required top-level key '{k}'")
    if not _nonempty_str(obj.get("version")):
        reasons.append("[original shape] 'version' must be a non-empty string")
    if not _nonempty_str(obj.get("generated_at")):
        reasons.append("[original shape] 'generated_at' must be a non-empty string")
    ms = obj.get("manifest_sha256")
    if not (isinstance(ms, str) and HEX64.match(ms)):
        reasons.append("[original shape] 'manifest_sha256' must be lowercase 64-char SHA256 hex")
    for i, ch in enumerate(obj.get("chunks", [])):
        if not isinstance(ch, dict):
            continue
        for k in ("id", "source", "title", "text"):
            if not _nonempty_str(ch.get(k)):
                reasons.append(f"[original shape] chunks[{i}].{k} missing or empty")
        if isinstance(ch.get("text"), str) and len(ch["text"]) > MAX_CHUNK_TEXT:
            reasons.append(f"chunks[{i}].text length {len(ch['text'])} > max {MAX_CHUNK_TEXT}")
        md = ch.get("metadata")
        if not isinstance(md, dict):
            reasons.append(f"[original shape] chunks[{i}].metadata missing or not an object")
            continue
        if not _nonempty_str(md.get("source_path")):
            reasons.append(f"[original shape] chunks[{i}].metadata.source_path missing or empty")
        cs = md.get("content_sha256")
        if not (isinstance(cs, str) and HEX64.match(cs)):
            reasons.append(f"[original shape] chunks[{i}].metadata.content_sha256 must be lowercase 64-char SHA256 hex")
    return reasons


def _validate_current_shape(obj: dict) -> list:
    reasons: list = []
    for k in ("bundle_version", "generated_at", "chunk_count", "chunks"):
        if k not in obj:
            reasons.append(f"[current shape] missing required top-level key '{k}'")
    if not _nonempty_str(obj.get("bundle_version")):
        reasons.append("[current shape] 'bundle_version' must be a non-empty string")
    if not _nonempty_str(obj.get("generated_at")):
        reasons.append("[current shape] 'generated_at' must be a non-empty string")
    if not isinstance(obj.get("chunk_count"), int) or isinstance(obj.get("chunk_count"), bool):
        reasons.append("[current shape] 'chunk_count' must be an integer")
    for i, ch in enumerate(obj.get("chunks", [])):
        if not isinstance(ch, dict):
            continue
        for k in ("id", "source_path", "content", "lane", "kind"):
            if not _nonempty_str(ch.get(k)):
                reasons.append(f"[current shape] chunks[{i}].{k} missing or empty")
        if isinstance(ch.get("content"), str) and len(ch["content"]) > MAX_CHUNK_TEXT:
            reasons.append(f"chunks[{i}].content length {len(ch['content'])} > max {MAX_CHUNK_TEXT}")
        chsh = ch.get("content_hash")
        if not (isinstance(chsh, str) and HEX_MIN16.match(chsh)):
            reasons.append(f"[current shape] chunks[{i}].content_hash must be lowercase hex >=16 chars")
    return reasons


# ---------------------------------------------------------------------------
# three-hash descriptor cross-check (offline D4)
# ---------------------------------------------------------------------------
def validate_three_hashes(raw: bytes, descriptor: dict) -> list:
    """H1/H2/H3 as documented at module top. Returns rejection reasons (empty => OK)."""
    reasons: list = []

    # H1: descriptor.proposed_sha256 == sha256(bundle bytes)
    actual = sha256_hex(raw)
    proposed = descriptor.get("proposed_sha256")
    if not (isinstance(proposed, str) and HEX64.match(proposed)):
        reasons.append("H1: descriptor.proposed_sha256 missing or not valid SHA256 hex")
    elif proposed != actual:
        reasons.append(f"H1: proposed_sha256 {proposed} != sha256(bundle bytes) {actual}")

    # H3: descriptor.base_sha256 present and valid hex
    base = descriptor.get("base_sha256")
    if not (isinstance(base, str) and HEX64.match(base)):
        reasons.append("H3: descriptor.base_sha256 missing or not valid SHA256 hex")

    # H2: chunk content integrity (original shape only; current shape is shape-only per spec)
    try:
        obj = json.loads(raw.decode("utf-8"))
    except Exception:
        return reasons  # shape validation already reported parse failure
    is_current = "bundle_version" in obj or "chunk_count" in obj
    if not is_current and isinstance(obj.get("chunks"), list):
        for i, ch in enumerate(obj["chunks"]):
            if not isinstance(ch, dict):
                continue
            md = ch.get("metadata") or {}
            cs = md.get("content_sha256")
            txt = ch.get("text")
            if isinstance(cs, str) and isinstance(txt, str):
                recomputed = sha256_hex(txt.encode("utf-8"))
                if cs != recomputed:
                    reasons.append(
                        f"H2: chunks[{i}].content_sha256 {cs} != sha256(text) {recomputed}")
    return reasons


# ---------------------------------------------------------------------------
# top-level check
# ---------------------------------------------------------------------------
def check(bundle_path: Path, descriptor_path: Path | None = None) -> dict:
    raw = Path(bundle_path).read_bytes()
    shape_reasons = validate_bundle_bytes(raw)
    hash_reasons: list = []
    descriptor = None
    if descriptor_path is not None:
        descriptor = json.loads(Path(descriptor_path).read_text(encoding="utf-8"))
        hash_reasons = validate_three_hashes(raw, descriptor)
    reasons = shape_reasons + hash_reasons
    verdict = "CHECK_OK" if not reasons else "CHECK_REJECTED"
    return {
        "origin": "sandbox-advisory",
        "authority": "none",
        "verdict": verdict,                    # never a bare governance PASS
        "pass_claimed": False,
        "bundle": str(bundle_path),
        "descriptor": str(descriptor_path) if descriptor_path else None,
        "bundle_sha256": sha256_hex(raw),
        "shape_reasons": shape_reasons,
        "hash_reasons": hash_reasons,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="GV-2 knowledge-bundle three-hash validator (advisory)")
    ap.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    ap.add_argument("--descriptor", type=Path, default=DEFAULT_DESCRIPTOR)
    ap.add_argument("--emit-verdict-dir", type=Path, default=HERE / "verdicts")
    args = ap.parse_args(argv)

    result = check(args.bundle, args.descriptor)

    args.emit_verdict_dir.mkdir(parents=True, exist_ok=True)
    vp = args.emit_verdict_dir / f"verdict-{Path(args.bundle).stem}.json"
    vp.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")  # verdict to SCRATCH, never the subject

    print(f"GV-2 BUNDLE_VALIDATE: {result['verdict']}  ({Path(args.bundle).name})")
    for e in result["shape_reasons"]:
        print(f"  [shape] {e}")
    for e in result["hash_reasons"]:
        print(f"  [hash]  {e}")
    print(f"  verdict written -> {vp}")
    return 0 if result["verdict"] == "CHECK_OK" else 1


if __name__ == "__main__":
    sys.exit(main())
