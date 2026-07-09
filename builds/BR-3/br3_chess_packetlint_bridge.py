#!/usr/bin/env python3
"""
BR-3 — CHESS -> packet-lint bridge  (catalog build B3 · BR-3)

READ-ONLY advisory bridge. Given a P0-PGR prompt packet it:
  1. runs the REAL packet linter (scripts/p0pgr_packet_lint_v1.py :: lint_packet)
     over the packet to get the base lint result + its reasons vocab, and
  2. runs the REAL CHESS forecast CLI (scripts/chess_pass_cli_v1.py) over the
     packet's worker-facing text (task + context_summary as the raw_move), then
  3. if the CHESS output carries `likely_misread` findings OR
     `action == "ASK_IF_IRREVERSIBLE"`, injects those as EXTRA
     REPAIR_CANDIDATE-style reasons onto the lint result.

Both ground tools are invoked as-is (no reimplementation, no strawman): the
linter is imported and lint_packet() called; CHESS is executed as its real CLI
over a temp JSON. The packet is never modified — the tool only reads it.

This bridge is STANDALONE and advisory: nothing downstream is BLOCKED by it. It
is a DETECTOR of CHESS forecast risk latent in a packet, so it exits NONZERO
when it injects any CHESS reason (a hit) and 0 when the packet is CHESS-clean.

Verdict vocab: CHECK_OK / CHECK_REJECTED — never a bare governance PASS. The
linter's own PASS/REPAIR_CANDIDATE verdict is preserved verbatim as
`lint_verdict`; the bridge's advisory verdict is separate.

    python3 br3_chess_packetlint_bridge.py PACKET.json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def _repo_root() -> Path:
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                             cwd=Path(__file__).resolve().parent, text=True,
                             capture_output=True, check=True)
        return Path(out.stdout.strip())
    except Exception:
        return Path(__file__).resolve().parents[3]


REPO = _repo_root()
SCRIPTS = REPO / "scripts"
CHESS_CLI = SCRIPTS / "chess_pass_cli_v1.py"
LINT_MODULE = SCRIPTS / "p0pgr_packet_lint_v1.py"

# Worker-facing packet text CHESS should forecast over (same fields the linter
# treats as WORKER_TEXT_FIELDS).
MOVE_TEXT_FIELDS = ("task", "context_summary")


def _load_linter():
    spec = importlib.util.spec_from_file_location("p0pgr_packet_lint_v1", LINT_MODULE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def packet_move_text(packet: dict) -> str:
    return " ".join(str(packet.get(f, "")) for f in MOVE_TEXT_FIELDS).strip()


def run_chess(move_text: str) -> dict:
    """Invoke the REAL chess_pass_cli over the packet's move text (read-only)."""
    payload = {"raw_move": move_text}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                     encoding="utf-8") as tf:
        json.dump(payload, tf)
        tmp = tf.name
    try:
        proc = subprocess.run([sys.executable, str(CHESS_CLI), tmp],
                              capture_output=True, text=True, check=True)
        return json.loads(proc.stdout)
    finally:
        Path(tmp).unlink(missing_ok=True)


def chess_reasons(chess: dict) -> list[str]:
    """Translate a CHESS forecast into extra REPAIR_CANDIDATE-style lint reasons.

    Injected only when CHESS actually flags risk: a non-empty `likely_misread`
    OR action == ASK_IF_IRREVERSIBLE. A PROCEED / empty forecast injects nothing.
    """
    reasons: list[str] = []
    for lm in chess.get("likely_misread", []) or []:
        reasons.append(f"REPAIR_CANDIDATE chess.likely_misread: {lm}")
    for smr in chess.get("second_move_risk", []) or []:
        reasons.append(f"REPAIR_CANDIDATE chess.second_move_risk: {smr}")
    if chess.get("action") == "ASK_IF_IRREVERSIBLE":
        reasons.append("REPAIR_CANDIDATE chess.action=ASK_IF_IRREVERSIBLE: "
                       "packet text names an irreversible/destructive move; "
                       "confirm before execution.")
    return reasons


def bridge(packet: dict) -> dict:
    """Read-only: lint the packet, forecast it with CHESS, inject CHESS reasons."""
    linter = _load_linter()
    base = linter.lint_packet(packet)  # ground linter, unmodified
    base_reasons = list(base.get("reasons", []))

    move_text = packet_move_text(packet)
    chess = run_chess(move_text)
    injected = chess_reasons(chess)

    combined = base_reasons + injected
    # DETECTOR semantics: a CHESS hit (any injected reason) is the finding.
    verdict = "CHECK_REJECTED" if injected else "CHECK_OK"
    return {
        "schema": "br3-chess-packetlint-bridge-v1",
        "origin": "sandbox-advisory",
        "authority": "none",
        "pass_claimed": False,
        "packet_id": packet.get("id", "UNKNOWN"),
        "packet_modified": False,
        "lint_verdict": base.get("verdict"),          # linter's own vocab, verbatim
        "lint_reasons": base_reasons,
        "chess_action": chess.get("action"),
        "chess_likely_misread": chess.get("likely_misread", []),
        "injected_chess_reasons": injected,
        "reasons": combined,                          # lint result + CHESS reasons
        "verdict": verdict,                           # bridge advisory verdict
        "downstream_blocked": False,                  # standalone: blocks nothing
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("packet", type=Path)
    args = ap.parse_args(argv)

    packet = json.loads(args.packet.read_text(encoding="utf-8"))
    res = bridge(packet)

    print(f"BR-3 CHESS->PACKETLINT BRIDGE: {res['verdict']}  "
          f"(lint_verdict={res['lint_verdict']}, chess_action={res['chess_action']}, "
          f"{len(res['injected_chess_reasons'])} chess reason(s) injected)")
    for r in res["injected_chess_reasons"]:
        print(f"  [+chess] {r}")
    if not res["injected_chess_reasons"]:
        print("  no CHESS forecast risk — packet is CHESS-clean, no reasons injected")
    # DETECTOR: exit nonzero on a hit (>=1 injected CHESS reason).
    return 1 if res["injected_chess_reasons"] else 0


if __name__ == "__main__":
    sys.exit(main())
