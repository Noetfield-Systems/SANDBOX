#!/usr/bin/env python3
"""hooks_present_report.py — REPORT-ONLY 'hooks-present' checker (CI-4, phase B4).

Advisory, non-blocking. It NEVER mutates git config and NEVER installs anything
(that is install_git_hooks.sh's job, and only the founder runs that). This module
only *reports* whether the versioned git hooks look installed, so the CI
'hooks-present' check can WARN — never block.

Checks, against a repo root on disk (no live git calls needed):
  - .githooks/pre-commit exists
  - .githooks/pre-commit is executable
  - the configured hooks path (passed in, e.g. from `git config core.hooksPath`)
    equals ".githooks"

Exit code is 0 by default (report-only / non-blocking) regardless of findings.
--strict is available for the test harness to make a red-run observable, but the
CI workflow invokes this in the default non-blocking mode.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

EXPECTED_HOOKS_DIR = ".githooks"
HOOK_NAME = "pre-commit"


def evaluate(root: str, configured_hooks_path: str | None) -> dict:
    """Pure report: inspect the sample repo root, return findings. No mutation."""
    hooks_dir = os.path.join(root, EXPECTED_HOOKS_DIR)
    hook_path = os.path.join(hooks_dir, HOOK_NAME)

    hook_exists = os.path.isfile(hook_path)
    hook_executable = hook_exists and os.access(hook_path, os.X_OK)
    # configured_hooks_path is what `git config core.hooksPath` reports; None = unset.
    path_configured = configured_hooks_path == EXPECTED_HOOKS_DIR

    warnings: list[str] = []
    if not hook_exists:
        warnings.append(f"missing hook: {EXPECTED_HOOKS_DIR}/{HOOK_NAME} not found")
    elif not hook_executable:
        warnings.append(f"hook not executable: {EXPECTED_HOOKS_DIR}/{HOOK_NAME}")
    if not path_configured:
        warnings.append(
            "core.hooksPath is not set to "
            f"{EXPECTED_HOOKS_DIR} (got: {configured_hooks_path!r}) — "
            f"run install_git_hooks.sh to install"
        )

    installed = hook_exists and hook_executable and path_configured
    return {
        "check": "hooks-present",
        "mode": "report-only",
        "blocking": False,
        "installed": installed,
        "hook_exists": hook_exists,
        "hook_executable": hook_executable,
        "hooks_path_configured": path_configured,
        "configured_hooks_path": configured_hooks_path,
        "warnings": warnings,
    }


def render_summary(report: dict) -> str:
    if report["installed"]:
        return "hooks-present: OK — versioned git hooks are installed."
    lines = ["hooks-present: WARNING — git hooks not fully installed (non-blocking)."]
    for w in report["warnings"]:
        lines.append(f"  - {w}")
    lines.append("  Fix: run ./install_git_hooks.sh from the repo root.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Report-only hooks-present checker.")
    ap.add_argument("--root", default=".", help="repo root to inspect")
    ap.add_argument(
        "--hooks-path",
        default=None,
        help="value of `git config core.hooksPath` (omit if unset)",
    )
    ap.add_argument("--json", action="store_true", help="emit JSON report")
    ap.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 when not installed (test/red-run only; CI runs WITHOUT this)",
    )
    args = ap.parse_args(argv)

    report = evaluate(args.root, args.hooks_path)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(render_summary(report))

    if args.strict and not report["installed"]:
        return 1
    return 0  # report-only / non-blocking by default


if __name__ == "__main__":
    raise SystemExit(main())
