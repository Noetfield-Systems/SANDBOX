#!/usr/bin/env python3
"""
GV-5 — Sandbox-registry gate-profile linter  (catalog build B0 · GV-5)

gates/promotion_gate.py::apply_sandbox_profile() reads specific fields off each
row of data/brain_domain_sandboxes_v1.json. A row missing deploy_root would
KeyError the gate; a gate_profile with a typo'd key is silently ignored (a
misconfiguration that never fires). This lints each row against what the gate
actually reads.

Checks per sandbox row:
  * sandbox_id: str (present)
  * deploy_root: str (present)  -- apply_sandbox_profile does sandbox["deploy_root"]
  * gate_profile (optional): dict; keys subset of what the gate reads; typed values
  * health_url (optional): str

Read-only. Exits 1 on any issue (RED), 0 when clean (GREEN).

    python3 gv5_gate_profile_lint.py [--registry PATH]
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
DEFAULT_REGISTRY = REPO / "data" / "brain_domain_sandboxes_v1.json"

# fields apply_sandbox_profile() reads off gate_profile / the row
PROFILE_KEYS_BOOL = {"bundle_artifacts_only", "brain_live_smoke_default"}
PROFILE_KEYS_STR = {"deploy_command", "source_bundle_path", "post_promote_command"}
KNOWN_PROFILE_KEYS = PROFILE_KEYS_BOOL | PROFILE_KEYS_STR


def lint_registry(reg: dict) -> list[str]:
    issues: list[str] = []
    rows = reg.get("sandboxes")
    if not isinstance(rows, list):
        return ["registry has no 'sandboxes' list"]
    for i, row in enumerate(rows):
        sid = row.get("sandbox_id", f"<row {i}>")
        if not isinstance(row.get("sandbox_id"), str):
            issues.append(f"[{sid}] sandbox_id missing or not a string")
        if not isinstance(row.get("deploy_root"), str):
            issues.append(f"[{sid}] deploy_root missing or not a string (gate does sandbox['deploy_root'])")
        if "health_url" in row and not isinstance(row["health_url"], str):
            issues.append(f"[{sid}] health_url present but not a string")
        gp = row.get("gate_profile")
        if gp is not None:
            if not isinstance(gp, dict):
                issues.append(f"[{sid}] gate_profile present but not an object")
                continue
            for k in gp:
                if k not in KNOWN_PROFILE_KEYS:
                    issues.append(f"[{sid}] gate_profile has unknown key {k!r} (gate never reads it — typo?)")
            for k in PROFILE_KEYS_BOOL & set(gp):
                if not isinstance(gp[k], bool):
                    issues.append(f"[{sid}] gate_profile.{k} should be a boolean")
            for k in PROFILE_KEYS_STR & set(gp):
                if not isinstance(gp[k], str):
                    issues.append(f"[{sid}] gate_profile.{k} should be a string")
    return issues


def lint(path: Path) -> list[str]:
    return lint_registry(json.loads(Path(path).read_text(encoding="utf-8")))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    args = ap.parse_args(argv)
    issues = lint(args.registry)
    if issues:
        print("GV-5 GATE_PROFILE: ISSUES:")
        for x in issues:
            print(f"  - {x}")
        return 1
    print("GV-5 GATE_PROFILE: CHECK_OK (every sandbox row matches what the gate reads)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
