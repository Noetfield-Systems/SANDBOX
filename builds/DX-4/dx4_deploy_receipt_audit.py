#!/usr/bin/env python3
"""
DX-4 — Deploy-Receipt Auditor  (catalog build B1 · DX-4 · TRUST SPINE)

The promotion gate writes a deploy receipt after every deploy attempt
(gates/promotion_gate.py::write_deploy_receipt), but nothing audits those
receipts after the fact. This is that read-only rollup: it re-implements the
gate's deploy-success predicate in a FRESH module and classifies each deploy
receipt PASS / FAIL / BLOCKED, emitting the exact rollback_hint the gate itself
would print on failure.

It NEVER invokes promotion_gate.py with deploy flags and NEVER runs any deploy
binary. It only READS on-disk deploy receipts. It is advisory:
verdict vocab is PASS/FAIL/BLOCKED (a deploy classification), stamped
origin=sandbox-advisory / authority=none — never a bare governance PASS.

Success predicate mirrored verbatim from write_deploy_receipt():
    smoke_ok        = brain_live is None or brain_live.skipped or brain_live.ok is True
    post_promote_ok = post_promote is None or post_promote.skipped or post_promote.ok is True
    deploy_success  = deploy_exit_code == 0 and identity_ok and smoke_ok and post_promote_ok
Content identity is read from either field name the gate emits across schema
generations: content_identity_ok (write_deploy_receipt) or
content_identity_confirmed (the step10a watched-deploy receipt).

    python3 dx4_deploy_receipt_audit.py [--receipt PATH] [--emit-verdict-dir DIR]
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
GATE_PATH = REPO / "gates" / "promotion_gate.py"
DEFAULT_RECEIPT = REPO / "receipts" / "phase0.3-step10a-watched-deploy-receipt.json"
# The worker name the gate hard-codes in every rollback_hint it prints.
WORKER_NAME = "sourcea-brain-chat-v1"


def _identity_ok(r: dict):
    """Read content identity from whichever field name the receipt carries.

    Returns True/False if known, or None if the receipt records neither field
    (identity cannot be established -> treated as not-ok downstream)."""
    if "content_identity_ok" in r:
        return r["content_identity_ok"] is True
    if "content_identity_confirmed" in r:
        return r["content_identity_confirmed"] is True
    return None


def _smoke_ok(r: dict) -> bool:
    bl = r.get("brain_live_smoke")
    return bl is None or bool(bl.get("skipped")) or bl.get("ok") is True


def _post_promote_ok(r: dict) -> bool:
    pp = r.get("post_promote")
    return pp is None or bool(pp.get("skipped")) or pp.get("ok") is True


def _rollback_hint(r: dict) -> str:
    """The exact string the gate prints: pre_version is the pre_live_version_id."""
    pre = r.get("pre_live_version_id")
    if not pre:
        return f"wrangler versions deploy <pre_live_version_id-unknown> --name {WORKER_NAME}"
    return f"wrangler versions deploy {pre} --name {WORKER_NAME}"


def classify(receipt: dict) -> dict:
    """Re-implement the gate deploy-success predicate; classify PASS/FAIL/BLOCKED."""
    exit_code = receipt.get("deploy_exit_code")
    reasons: list[str] = []

    # BLOCKED: the deploy never executed, so there is nothing to roll back.
    if exit_code is None:
        return {
            "origin": "sandbox-advisory", "authority": "none",
            "classification": "BLOCKED",
            "reasons": ["deploy did not execute (no deploy_exit_code recorded)"],
            "rollback_hint": None,
            "predicate": {"deploy_exit_code": None},
        }

    identity_ok = _identity_ok(receipt)
    smoke_ok = _smoke_ok(receipt)
    post_promote_ok = _post_promote_ok(receipt)

    if exit_code != 0:
        reasons.append(f"deploy_exit_code {exit_code} is nonzero")
    if identity_ok is None:
        reasons.append("content identity absent (neither content_identity_ok nor content_identity_confirmed present)")
    elif identity_ok is False:
        reasons.append("content identity not confirmed (post-deploy artifact sha256 != verifier-signed candidate)")
    if not smoke_ok:
        reasons.append("brain-live smoke did not pass")
    if not post_promote_ok:
        reasons.append("post_promote command did not pass")

    deploy_success = exit_code == 0 and identity_ok is True and smoke_ok and post_promote_ok
    classification = "PASS" if deploy_success else "FAIL"

    return {
        "origin": "sandbox-advisory", "authority": "none",
        "classification": classification,
        "reasons": reasons,
        # A FAIL needs the operator to roll back; a PASS has nothing to undo.
        "rollback_hint": None if deploy_success else _rollback_hint(receipt),
        "predicate": {
            "deploy_exit_code": exit_code,
            "identity_ok": identity_ok,
            "smoke_ok": smoke_ok,
            "post_promote_ok": post_promote_ok,
            "deploy_success": deploy_success,
        },
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    ap.add_argument("--emit-verdict-dir", type=Path, default=Path(__file__).resolve().parent / "verdicts")
    args = ap.parse_args(argv)

    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    result = classify(receipt)
    result["subject_receipt"] = str(args.receipt)
    result["subject_receipt_type"] = receipt.get("receipt_type")

    args.emit_verdict_dir.mkdir(parents=True, exist_ok=True)
    vp = args.emit_verdict_dir / f"verdict-{args.receipt.stem}.json"
    vp.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")  # verdict to SCRATCH, never the subject

    print(f"DX-4 DEPLOY_AUDIT: {result['classification']}  ({args.receipt.name})")
    for reason in result["reasons"]:
        print(f"  [reason] {reason}")
    if result["rollback_hint"]:
        print(f"  rollback_hint: {result['rollback_hint']}")
    print(f"  verdict written -> {vp}")
    return 0 if result["classification"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
