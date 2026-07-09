#!/usr/bin/env python3
"""test_ci4_hooks.py — RED-capable tests for CI-4 (phase B4 · CI).

Two halves:
  A) Exercise the REPORT-ONLY script hooks_present_report.py on sample inputs:
       - a valid installed sample  -> installed / no warnings   (green)
       - a MINIMAL MUTATION (drop the pre-commit exec bit)      -> flagged
       - a MINIMAL MUTATION (unset core.hooksPath)              -> flagged
  B) Assert the CI guards on hooks-present-check-v1.yml:
       contents:read only · pull_request-only · no secrets/creds · non-blocking.
  C) Assert install_git_hooks.sh is `bash -n` valid and sets core.hooksPath.

Runnable directly (`python3 test_ci4_hooks.py`) and under pytest.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import hooks_present_report as report  # noqa: E402

YAML_PATH = os.path.join(HERE, "hooks-present-check-v1.yml")
INSTALLER = os.path.join(HERE, "install_git_hooks.sh")


# --- tiny stdlib-only YAML helpers (no third-party deps; runs under HOME=temp) ---

def _yaml_lines() -> list[str]:
    out = []
    for ln in open(YAML_PATH).read().splitlines():
        if ln.strip() == "" or ln.lstrip().startswith("#"):
            continue
        out.append(ln)
    return out


def _indent(ln: str) -> int:
    return len(ln) - len(ln.lstrip(" "))


def _block_children(header: str) -> list[str]:
    """Return the child lines nested under a top-level `header:` key."""
    lines = _yaml_lines()
    for i, ln in enumerate(lines):
        if _indent(ln) == 0 and ln.rstrip().split(":")[0].strip() == header:
            base = _indent(ln)
            kids = []
            for nxt in lines[i + 1:]:
                if _indent(nxt) <= base:
                    break
                kids.append(nxt)
            return kids
    return []


# --- helpers ---------------------------------------------------------------

def _make_sample(root: str, *, executable: bool = True) -> None:
    """Create <root>/.githooks/pre-commit, optionally executable."""
    hooks_dir = os.path.join(root, ".githooks")
    os.makedirs(hooks_dir, exist_ok=True)
    hook = os.path.join(hooks_dir, "pre-commit")
    with open(hook, "w") as fh:
        fh.write("#!/usr/bin/env bash\nexit 0\n")
    mode = 0o644
    if executable:
        mode = 0o755
    os.chmod(hook, mode)


# --- A) report-only script behaviour ---------------------------------------

def test_valid_sample_reports_installed():
    with tempfile.TemporaryDirectory() as root:
        _make_sample(root, executable=True)
        rep = report.evaluate(root, ".githooks")
        assert rep["installed"] is True
        assert rep["warnings"] == []
        assert rep["blocking"] is False


def test_mutation_exec_bit_removed_is_flagged():
    # MINIMAL MUTATION: same valid config, but the hook is not executable.
    with tempfile.TemporaryDirectory() as root:
        _make_sample(root, executable=False)
        rep = report.evaluate(root, ".githooks")
        assert rep["installed"] is False
        assert rep["hook_exists"] is True
        assert rep["hook_executable"] is False
        assert any("not executable" in w for w in rep["warnings"])


def test_mutation_hookspath_unset_is_flagged():
    # MINIMAL MUTATION: hook is fine, but core.hooksPath is not configured.
    with tempfile.TemporaryDirectory() as root:
        _make_sample(root, executable=True)
        rep = report.evaluate(root, None)
        assert rep["installed"] is False
        assert rep["hooks_path_configured"] is False
        assert any("core.hooksPath" in w for w in rep["warnings"])


def test_report_only_default_exit_zero_even_when_not_installed():
    # Non-blocking contract: default mode always exits 0.
    with tempfile.TemporaryDirectory() as root:
        _make_sample(root, executable=False)
        code = report.main(["--root", root, "--json"])
        assert code == 0
        # --strict is a test/red-run affordance only; CI never passes it.
        code_strict = report.main(["--root", root, "--strict"])
        assert code_strict == 1


# --- B) CI guards on the workflow YAML -------------------------------------

def test_yaml_permissions_contents_read_only():
    kids = _block_children("permissions")
    # exactly one child: contents: read
    entries = [k.strip() for k in kids]
    assert entries == ["contents: read"], entries


def test_yaml_trigger_pull_request_only():
    kids = _block_children("on")
    keys = {k.strip().rstrip(":").strip() for k in kids if _indent(k) == _indent(kids[0])}
    assert keys == {"pull_request"}, keys
    forbidden = {"pull_request_target", "push", "schedule", "workflow_dispatch"}
    assert not (keys & forbidden)


def test_yaml_no_secrets_or_credential_env():
    lowered = open(YAML_PATH).read().lower()
    assert "secrets." not in lowered
    assert "${{ secrets" not in lowered
    # no credential-ish env references copied from census/autorun/auth blocks
    for token in ("cf_", "cloudflare", "supabase", "github_token",
                  "gh_token", "api_key", "access_token"):
        assert token not in lowered, f"credential-like token present: {token}"


def test_yaml_non_blocking():
    # Assert against the ACTUAL yaml (comments stripped) so doc-comments that
    # merely name a forbidden flag can't mask a real occurrence.
    body = "\n".join(_yaml_lines())
    # the reporting run-step must be continue-on-error and end by exiting 0
    assert "continue-on-error: true" in body
    assert "exit 0" in body
    # report-only invocation: --json present, and NEVER a write/install/strict flag
    assert "--json" in body
    assert "hooks_present_report.py" in body
    for bad in ("--strict", "--write", "--install"):
        assert bad not in body, f"non-report-only flag in CI: {bad}"
    # CI must not itself run the installer or WRITE git config. Reading
    # core.hooksPath (no value arg) is allowed; setting it (value arg) is not.
    assert "install_git_hooks.sh" not in body
    assert 'git config core.hooksPath ".githooks"' not in body
    assert "git config core.hooksPath .githooks" not in body
    assert "git config --global" not in body
    # no blocking / required-status / auto-merge keywords anywhere
    for bad in ("auto-merge", "automerge", "required", "fail-on"):
        assert bad not in body.lower()


# --- C) installer script sanity --------------------------------------------

def test_installer_bash_syntax_valid():
    proc = subprocess.run(["bash", "-n", INSTALLER], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_installer_sets_hooks_path():
    raw = open(INSTALLER).read()
    assert "git config core.hooksPath" in raw
    assert ".githooks" in raw
    assert "pre-commit" in raw
    # verifies executability of the hook
    assert "-x " in raw


# --- self-runner -----------------------------------------------------------

def _run_all() -> int:
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        t()
        print(f"  PASS {t.__name__}")
        passed += 1
    print(f"\n{passed}/{len(tests)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run_all())
