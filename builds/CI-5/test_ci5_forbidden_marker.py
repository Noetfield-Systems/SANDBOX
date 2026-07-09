#!/usr/bin/env python3
"""
TH for CI-5 - the forbidden-marker PR grep gate's own proof.

Two halves, both red-capable:

  A. SCRIPT behavior (report-only scanner):
     * NEGATIVE-before-POSITIVE by construction: a CLEAN sample file is NOT flagged
       (exit 0, clean=True); the SAME file with ONE line mutated to embed the forbidden
       marker IS flagged (exit 1, clean=False, correct file+line reported).
     * minimality: reversing the single injected line reproduces the clean file
       byte-for-byte -> same scanner, opposite verdicts (no strawman, no relaxed rule).
     * the shipped dirty fixture is flagged and the shipped clean fixture is not.

  B. YAML CI guards (asserted directly on the proposal):
     * permissions: contents: read ONLY, no write scope.
     * on: pull_request ONLY - never pull_request_target / push / schedule.
     * NO secrets: / env: credential references anywhere.
     * NON-BLOCKING - scan step is continue-on-error, no auto-merge / required-status.

Run standalone (`python3 test_ci5_forbidden_marker.py`) or under pytest.
"""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "scan_forbidden_marker_v1.py"
YAML = HERE / "ci5-forbidden-marker-pr-gate-v1.yml"
CLEAN_FIXTURE = HERE / "fixtures" / "clean_config.sample"
DIRTY_FIXTURE = HERE / "fixtures" / "dirty_config.sample"

# Assembled from fragments so THIS test source does not embed the literal marker.
MARKER = "-".join(("kazemnezhadsina144", "dot"))

_spec = importlib.util.spec_from_file_location("ci5_scan", SCRIPT)
scan = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scan)


def _run(*args: str) -> tuple[int, dict | str]:
    """Invoke the scanner as a subprocess; return (exit_code, parsed_json_or_stdout)."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True,
    )
    out = proc.stdout
    try:
        return proc.returncode, json.loads(out)
    except json.JSONDecodeError:
        return proc.returncode, out


def _yaml_no_comments() -> str:
    """YAML text with full-line comments stripped, so words that only appear in
    explanatory comments (e.g. 'pull_request_target') cannot fool guard checks."""
    kept = []
    for line in YAML.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("#"):
            continue
        kept.append(line)
    return "\n".join(kept)


# --------------------------------------------------------------------------- A
def test_marker_default_matches_ground_truth():
    ground = (HERE.parents[2] / ".github" / "copilot-instructions.md").read_text(encoding="utf-8")
    assert MARKER in ground, "assembled marker must be the one named in copilot-instructions.md"
    assert scan.DEFAULT_MARKER == MARKER, "scanner default marker drifted from ground truth"


def test_clean_file_not_flagged():
    code, report = _run(str(CLEAN_FIXTURE), "--json")
    assert isinstance(report, dict)
    assert code == 0, "clean file must exit 0"
    assert report["clean"] is True
    assert report["hit_count"] == 0
    assert report["files_with_hits"] == []


def test_dirty_file_flagged():
    code, report = _run(str(DIRTY_FIXTURE), "--json")
    assert isinstance(report, dict)
    assert code == 1, "file with the forbidden marker must exit nonzero"
    assert report["clean"] is False
    assert report["hit_count"] >= 1
    assert str(DIRTY_FIXTURE) in report["files_with_hits"]


def test_minimal_mutation_red_before_green(tmp_path):
    """Same file, one injected line: clean -> flagged; reverse -> byte-identical clean."""
    original = CLEAN_FIXTURE.read_bytes()

    clean_copy = tmp_path / "candidate.sample"
    clean_copy.write_bytes(original)
    code_clean, rep_clean = _run(str(clean_copy), "--json")
    assert code_clean == 0 and rep_clean["clean"] is True  # RED baseline: passes clean

    # MINIMAL MUTATION: append exactly one line embedding the marker.
    mutated = original + f"active_ref: {MARKER}\n".encode()
    clean_copy.write_bytes(mutated)
    code_hit, rep_hit = _run(str(clean_copy), "--json")
    assert code_hit == 1 and rep_hit["clean"] is False, "mutation must be caught"
    flagged = [r for r in rep_hit["results"] if r["status"] == "flagged"]
    assert flagged and flagged[0]["hits"][0]["line"] == len(mutated.decode().splitlines())

    # minimality: reverse the single injection -> identical bytes, clean verdict again.
    clean_copy.write_bytes(original)
    assert clean_copy.read_bytes() == original
    code_rev, rep_rev = _run(str(clean_copy), "--json")
    assert code_rev == 0 and rep_rev["clean"] is True


def test_files_from_list(tmp_path):
    listing = tmp_path / "changed.txt"
    listing.write_text(f"{CLEAN_FIXTURE}\n{DIRTY_FIXTURE}\n")
    code, report = _run("--files-from", str(listing), "--json")
    assert code == 1
    assert report["scanned_count"] == 2
    assert report["files_with_hits"] == [str(DIRTY_FIXTURE)]


# --------------------------------------------------------------------------- B
def test_yaml_permissions_contents_read_only():
    body = _yaml_no_comments()
    assert re.search(r"permissions:\s*\n\s*contents:\s*read\b", body), "must declare contents: read"
    assert "write" not in body.split("jobs:")[0], "no write permission scope allowed"


def test_yaml_trigger_is_pull_request_only():
    body = _yaml_no_comments()
    assert re.search(r"^on:\s*\n\s*pull_request:", body, re.M), "on: must be pull_request"
    for forbidden in ("pull_request_target", "\npush:", "  push:", "schedule:"):
        assert forbidden not in body, f"forbidden trigger present: {forbidden!r}"


def test_yaml_has_no_secrets_or_env_credentials():
    body = _yaml_no_comments()
    assert "secrets." not in body, "no secrets.* references allowed"
    assert not re.search(r"^\s*env:", body, re.M), "no env: blocks allowed (avoid credential refs)"
    for tok in ("SUPABASE", "CF_", "GITHUB_TOKEN", "ACCESS_TOKEN", "API_KEY"):
        assert tok not in body, f"credential-like token present: {tok}"


def test_yaml_is_non_blocking():
    body = _yaml_no_comments()
    assert "continue-on-error: true" in body, "scan step must be non-blocking"
    for merge_tok in ("gh pr merge", "automerge", "auto-merge", "--merge"):
        assert merge_tok not in body, f"must not auto-merge: {merge_tok!r}"


def test_yaml_script_invoked_report_only():
    body = _yaml_no_comments()
    assert "scan_forbidden_marker_v1.py" in body
    for write_flag in ("--write-supabase", "--write-receipt", "--fail-on-block-merge"):
        assert write_flag not in body, f"report-only violation: {write_flag}"


# ------------------------------------------------------------------ self-runner
def _main() -> int:
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    import tempfile
    passed = 0
    for name, fn in tests:
        try:
            if "tmp_path" in fn.__code__.co_varnames[: fn.__code__.co_argcount]:
                with tempfile.TemporaryDirectory() as d:
                    fn(Path(d))
            else:
                fn()
            print(f"  PASS  {name}")
            passed += 1
        except AssertionError as exc:
            print(f"  FAIL  {name}: {exc}")
            return 1
    print(f"\n{passed}/{len(tests)} green")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
