#!/usr/bin/env bash
# install_git_hooks.sh — FOUNDER-RUN CLI (CI-4, phase B4 · CI)
#
# WHAT THIS DOES **WHEN THE FOUNDER RUNS IT** (do NOT run inside the sandbox):
#   1. Points git at the repo's version-controlled hooks:  core.hooksPath .githooks
#   2. Ensures .githooks/pre-commit is executable, and verifies it.
#
# This script is authored as a standalone artifact in the CI-4 build dir. The
# sandbox agent that authored it MUST NOT execute it (it would mutate live git
# config). It is safe for the founder to run from the repo root.
#
# Report-only siblings (never mutate git config): the CI 'hooks-present' check
# (hooks-present-check-v1.yml) and hooks_present_report.py only WARN.
set -euo pipefail

HOOKS_DIR=".githooks"
HOOK="${HOOKS_DIR}/pre-commit"

# Resolve repo root so this works from any subdirectory.
if ! REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  echo "ERROR: not inside a git repository (run from the repo checkout)." >&2
  exit 2
fi
cd "$REPO_ROOT"

if [[ ! -d "$HOOKS_DIR" ]]; then
  echo "ERROR: ${HOOKS_DIR}/ not found at repo root ${REPO_ROOT}." >&2
  exit 2
fi

# 1. Install: tell git to use the versioned hooks directory.
git config core.hooksPath "$HOOKS_DIR"
echo "OK: set core.hooksPath = ${HOOKS_DIR}"

# 2. Make the pre-commit hook executable.
if [[ ! -f "$HOOK" ]]; then
  echo "ERROR: expected hook ${HOOK} is missing." >&2
  exit 2
fi
chmod +x "$HOOK"

# 3. Verify the hook is now executable.
if [[ -x "$HOOK" ]]; then
  echo "OK: ${HOOK} is executable — git hooks installed."
else
  echo "ERROR: ${HOOK} is still not executable after chmod." >&2
  exit 1
fi

echo "DONE: git hooks installed (core.hooksPath=${HOOKS_DIR}, ${HOOK} executable)."
