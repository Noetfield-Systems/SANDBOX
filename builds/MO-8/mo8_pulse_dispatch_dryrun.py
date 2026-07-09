#!/usr/bin/env python3
"""
MO-8 — Commercial-Pulse Dispatch-Check DRY-RUN  (catalog build B3 · designed move M05)

NEVER SENDS. This is a readiness scorer, not a sender. It scores the 8 real
`dispatchability_predicates` from the ground checker
(scripts/commercial_pulse_dispatch_check_v1.py) over a SYNTHETIC draft
(fake icp_stranger_id, example.com email, synthetic content), then — INDEPENDENT
of the predicate scores — HARDCODES the outcome to `founder_blocked` /
`dispatch_now=false`. Full predicate readiness does NOT unlock a send.

Core invariant (M05): the highest state a dry-run may ever reach is
`founder_blocked`. `approved_pending_send` / `sent` are OUT OF REACH by
construction. A dry-run that reports otherwise is a send-authorization LEAK and
is REJECTED.

Output is explicitly labelled 'readiness score, NOT send authorization'.

Never imports or calls any send / broadcast / batch-email tool. An AST-based
self-scan detector (with a positive control) enforces that no send-API import or
call exists in this file, so a clean scan can't be a broken-regex false-clean.

Verdict vocab: CHECK_OK / CHECK_REJECTED — never a bare governance PASS. Exits
NONZERO when the send-safety invariant is violated (this is not an always-exit-0
stub). Reads the ground queue read-only and confirms it stays [] on disk.

    python3 mo8_pulse_dispatch_dryrun.py [--json]
"""
from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

READINESS_LABEL = "readiness score, NOT send authorization"

# The cap. Anything at a higher ordered index than this is a send-authorization leak.
FOUNDER_BLOCK_STATE = "founder_blocked"

# Fallback state ordering if the ground queue can't be read (kept in sync with
# data/commercial_pulse_queue_v1.json "states").
_FALLBACK_STATES = [
    "idle", "drafting", "validate_failed", "queued_for_approval", "founder_blocked",
    "approved_pending_send", "sent", "awaiting_reply", "classified",
    "mutation_pending", "complete",
]

# Identifiers/imports that would give this file the CAPABILITY to send. The
# self-scan is AST-based, so it flags an actual import or call — never a mention
# in a string, comment, or docstring (those can't send). This keeps the guard
# about capability, not vocabulary.
FORBIDDEN_SEND_CALLS = {
    "send_email", "send_broadcast", "send_batch_emails", "send_batch",
    "compose_broadcast", "create_broadcast", "sendmail", "send_message",
}
FORBIDDEN_IMPORT_SUBSTR = ("send", "broadcast", "batch_email", "smtp")


def _repo_root() -> Path:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=Path(__file__).resolve().parent, text=True, capture_output=True, check=True,
        )
        return Path(out.stdout.strip())
    except Exception:
        return Path(__file__).resolve().parents[3]


REPO = _repo_root()
GROUND_CHECKER = REPO / "scripts" / "commercial_pulse_dispatch_check_v1.py"
QUEUE_PATH = REPO / "data" / "commercial_pulse_queue_v1.json"


def _load_ground_checker():
    """Import the real dispatch checker by path. Importing has no side effects
    (writes only happen inside its main()/write_malformed_receipt, which we never
    call — we use check_dispatchable(), a pure function)."""
    spec = importlib.util.spec_from_file_location("cpdc_v1", GROUND_CHECKER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GROUND = _load_ground_checker()
PREDICATES = tuple(GROUND.PREDICATES)  # the 8, straight from ground truth


def ground_states() -> list[str]:
    """Read the ordered state machine from the ground queue file (read-only)."""
    try:
        q = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
        states = q.get("states")
        if isinstance(states, list) and FOUNDER_BLOCK_STATE in states:
            return states
    except Exception:
        pass
    return list(_FALLBACK_STATES)


# --------------------------------------------------------------------------- #
# Synthetic drafts — fake ids, example.com, synthetic content. Never real leads.
# --------------------------------------------------------------------------- #
def synthetic_draft(ready: bool) -> dict:
    """A fully-ready synthetic draft satisfies all 8 predicates. `ready=False`
    omits several predicate fields so it scores strictly lower. Everything is
    fake: SYNTH ids, example.com address, do-not-send body."""
    draft = {
        "draft_id": "SYNTH-DRYRUN-0001",
        "state": "drafting",
        "icp_stranger_id": "SYNTH-ICP-STRANGER-000",
        "offer_id": "SYNTH-OFFER-000",
        "price_display": "$0 (synthetic)",
        "entity": "Noetfield Systems Inc.",
        "subject": "[SYNTHETIC DRY-RUN — DO NOT SEND]",
        "body": "synthetic content for readiness scoring only; not a real message",
        "email": "synthetic-stranger@example.com",
        "casl": {
            "mailing_address": "123 Example St, Exampleton",
            "unsubscribe_url": "https://example.com/unsubscribe",
        },
        "link_check_receipt_id": "SYNTH-LINKCHK-000",
        "approval": {"required": True, "status": "pending"},
        "approval_window_expired": False,
    }
    if not ready:
        # Minimally under-fill so predicates legitimately fail (lower score).
        draft["icp_stranger_id"] = None
        draft["offer_id"] = None
        draft["price_display"] = None
        draft["casl"]["unsubscribe_url"] = None
        draft["link_check_receipt_id"] = None
    return draft


def score_predicates(draft: dict) -> dict:
    """Score the 8 real predicates using the ground checker's pure function."""
    ok, failed = GROUND.check_dispatchable(draft)
    passed = [p for p in PREDICATES if p not in failed]
    return {
        "predicates_total": len(PREDICATES),
        "predicates_passed": passed,
        "predicates_failed": failed,
        "readiness_score": f"{len(passed)}/{len(PREDICATES)}",
        "readiness_fraction": round(len(passed) / len(PREDICATES), 4),
        "all_predicates_ready": ok,
    }


def dry_run(draft: dict, states: list[str] | None = None) -> dict:
    """Produce a dry-run record. The state is HARDCODED to founder_blocked and
    dispatch_now to False, INDEPENDENT of the predicate scores. Readiness is
    reported; authorization is never granted."""
    states = states or ground_states()
    scoring = score_predicates(draft)
    record = {
        "origin": "sandbox-advisory",
        "authority": "none",
        "pass_claimed": False,
        "label": READINESS_LABEL,
        "designed_move": "M05",
        "draft_id": draft.get("draft_id"),
        "synthetic": True,
        # --- hardcoded, score-independent ---
        "highest_state_reached": FOUNDER_BLOCK_STATE,
        "dispatch_now": False,
        "send_authorized": False,
        "block_reason": "founder_blocked: readiness scored, send withheld pending founder decision",
        # --- readiness (advisory only) ---
        **scoring,
    }
    violations = enforce_send_safety(record, states)
    record["send_safety_violations"] = violations
    record["verdict"] = "CHECK_OK" if not violations else "CHECK_REJECTED"
    return record


# --------------------------------------------------------------------------- #
# Detectors — each returns violations and drives a NONZERO exit on a hit.
# --------------------------------------------------------------------------- #
def enforce_send_safety(record: dict, states: list[str]) -> list[str]:
    """The send-authorization-leak detector. A dry-run must cap at
    founder_blocked with dispatch withheld. Returns a list of violations; empty
    means safe."""
    v: list[str] = []
    cap_idx = states.index(FOUNDER_BLOCK_STATE)
    reached = record.get("highest_state_reached")
    if reached not in states:
        v.append(f"unknown highest_state_reached {reached!r}")
    elif states.index(reached) > cap_idx:
        v.append(
            f"send-authorization LEAK: highest_state_reached {reached!r} is past "
            f"the founder_blocked cap {FOUNDER_BLOCK_STATE!r}"
        )
    if record.get("dispatch_now") is not False:
        v.append(f"dispatch_now must be False, got {record.get('dispatch_now')!r}")
    if record.get("send_authorized"):
        v.append("send_authorized is truthy — a dry-run may never authorize a send")
    return v


def scan_source_for_send_tokens(source: str) -> list[str]:
    """Positive-controlled self-scan (AST-based): report an actual IMPORT or CALL
    of a send / broadcast tool. String literals, comments and docstrings are
    ignored — they can't send — so the detector reports CAPABILITY, not the
    guard's own vocabulary. A clean scan therefore can't be a broken-regex
    false-clean; the test seeds a real send call as a positive control."""
    hits: list[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return [f"unparseable source: {e}"]
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [getattr(node, "module", "") or ""] + [a.name for a in node.names]
            for nm in names:
                low = (nm or "").lower()
                if any(s in low for s in FORBIDDEN_IMPORT_SUBSTR):
                    hits.append(f"import of send/broadcast module: {nm!r}")
        elif isinstance(node, ast.Call):
            f = node.func
            name = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")
            if name in FORBIDDEN_SEND_CALLS:
                hits.append(f"call to send tool: {name!r}()")
    return hits


def queue_is_empty_on_disk() -> tuple[bool, int]:
    """Read-only: confirm the ground queue's `queue` array is still []."""
    q = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    arr = q.get("queue", [])
    return (arr == [], len(arr))


# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="emit the dry-run record as JSON")
    args = ap.parse_args(argv)

    states = ground_states()
    ready = dry_run(synthetic_draft(ready=True), states)
    not_ready = dry_run(synthetic_draft(ready=False), states)

    # Guard 1: this file never uses a send tool.
    src_hits = scan_source_for_send_tokens(Path(__file__).read_text(encoding="utf-8"))
    # Guard 2: on-disk queue is still empty (we never enqueued anything).
    q_empty, q_len = queue_is_empty_on_disk()

    violations = list(ready["send_safety_violations"]) + list(not_ready["send_safety_violations"])
    if src_hits:
        violations += [f"send-tool token used in tool source: {h}" for h in src_hits]
    if not q_empty:
        violations.append(f"ground queue is NOT empty on disk ({q_len} entries) — dry-run must not enqueue")

    verdict = "CHECK_OK" if not violations else "CHECK_REJECTED"

    if args.json:
        print(json.dumps({
            "verdict": verdict, "label": READINESS_LABEL,
            "ready_draft": ready, "not_ready_draft": not_ready,
            "queue_empty_on_disk": q_empty, "source_send_token_hits": src_hits,
        }, indent=2))
    else:
        print(f"MO-8 PULSE DISPATCH DRY-RUN: {verdict}   [{READINESS_LABEL}]")
        print(f"  ready draft     : readiness {ready['readiness_score']}  "
              f"(all_predicates_ready={ready['all_predicates_ready']})  "
              f"-> state={ready['highest_state_reached']} dispatch_now={ready['dispatch_now']}")
        print(f"  not-ready draft : readiness {not_ready['readiness_score']}  "
              f"failed={not_ready['predicates_failed']}  "
              f"-> state={not_ready['highest_state_reached']} dispatch_now={not_ready['dispatch_now']}")
        print(f"  founder_blocked cap holds for BOTH: full readiness does NOT unlock a send.")
        print(f"  queue empty on disk: {q_empty}   send-token hits in source: {len(src_hits)}")
        for x in violations:
            print(f"  [violation] {x}")

    return 0 if verdict == "CHECK_OK" else 1


if __name__ == "__main__":
    sys.exit(main())
