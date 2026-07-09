#!/usr/bin/env python3
"""CI-2 test: RED-capably exercises the report-only wrapper on the language-gate
test files, and asserts the workflow YAML carries every required CI guard.

Two axes:
  A) SCRIPT behaviour (RED-capable):
       - clean_example.md          -> valid input  -> clean (no findings, decision PASS/WARN)
       - violations_example.md     -> flagged (OVERCLAIM/BANNED_REGISTER blockers, decision FAIL)
       - MINIMAL MUTATION of the clean file (inject one overclaim token) -> flagged
         (proves the pass is not vacuous; reverting the token reproduces the clean verdict)
       - report-only: the wrapper writes NOTHING into the tracked repo (receipts -> tempdir)
  B) YAML guards:
       - permissions: contents: read  (only; no write:)
       - on: pull_request ONLY (no pull_request_target / push / schedule)
       - no secrets: and no credential env: references
       - non-blocking (continue-on-error / `|| true`; no auto-merge / required-status)

Self-runnable: `python3 test_ci2_language_gate_ci.py`  (prints PASS lines, exit 0).
Pytest:        `pytest test_ci2_language_gate_ci.py`.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

BUILD_DIR = Path(__file__).resolve().parent
REPO_ROOT = BUILD_DIR.parents[2]
sys.path.insert(0, str(BUILD_DIR))

import language_gate_ci_wrapper as wrap  # noqa: E402

TEST_FILES = REPO_ROOT / "language_gate" / "test_files"
CLEAN = TEST_FILES / "clean_example.md"
VIOLATIONS = TEST_FILES / "violations_example.md"
YAML = BUILD_DIR / "language-gate-ci-v1.yml"


def _run(files: list[str], surface: str = "auto") -> dict:
    """Run the wrapper report-only with an ephemeral receipts dir (no repo writes)."""
    receipts = Path(tempfile.mkdtemp(prefix="ci2_test_receipts_"))
    return wrap.run_over_files(
        files, surface=surface, soft_undefined=True, receipts_dir=receipts
    )


def _result_for(report: dict, needle: str) -> dict:
    for r in report["results"]:
        if needle in r["file"]:
            return r
    raise AssertionError(f"no result for {needle} in {[r['file'] for r in report['results']]}")


# ---------------------------------------------------------------- A) SCRIPT

def test_clean_file_passes_clean():
    report = _run([str(CLEAN)])
    r = _result_for(report, "clean_example.md")
    assert r["status"] == "SCANNED"
    assert r["decision"] in {"PASS", "WARN"}, r["decision"]
    assert r["flagged"] is False, r
    assert r["blocking_count"] == 0


def test_violations_file_is_flagged():
    report = _run([str(VIOLATIONS)])
    r = _result_for(report, "violations_example.md")
    assert r["decision"] == "FAIL", r["decision"]
    assert r["flagged"] is True
    assert r["blocking_count"] >= 1
    types = {f["type"] for f in r["findings"]}
    assert types & {"OVERCLAIM", "BANNED_REGISTER", "BANNED_SURFACE"}, types


def test_minimal_mutation_flips_clean_to_flagged():
    """Valid clean input passes; a ONE-token overclaim injection makes it flagged.

    Same wrapper, same gate policy (surface=public), single-field mutation -> opposite
    verdict on BLOCKING findings. Reverting the token reproduces the clean verdict.
    """
    clean_text = CLEAN.read_text(encoding="utf-8")
    tmp = Path(tempfile.mkdtemp(prefix="ci2_mutant_")) / "clean_example.md"

    # baseline: the unmutated copy carries NO blocking findings on a public surface
    tmp.write_text(clean_text, encoding="utf-8")
    base = _result_for(_run([str(tmp)], surface="public"), "clean_example.md")
    assert base["blocking_count"] == 0, base
    assert base["decision"] in {"PASS", "WARN"}, base["decision"]

    # minimal mutation: append one overclaim sentence -> OVERCLAIM blocker -> FAIL
    tmp.write_text(clean_text + "\nOur system is 100% guaranteed and fully certified.\n", encoding="utf-8")
    mutant = _result_for(_run([str(tmp)], surface="public"), "clean_example.md")
    assert mutant["blocking_count"] >= 1, mutant
    assert mutant["decision"] == "FAIL", mutant["decision"]
    assert {f["type"] for f in mutant["findings"]} & {"OVERCLAIM", "BANNED_REGISTER"}, mutant

    # revert reproduces the clean verdict
    tmp.write_text(clean_text, encoding="utf-8")
    reverted = _result_for(_run([str(tmp)], surface="public"), "clean_example.md")
    assert reverted["blocking_count"] == 0, reverted


def test_report_only_writes_nothing_to_tracked_repo():
    """The wrapper must not create receipts/sidecars in language_gate/ or test_files/."""
    receipts_before = {p.name for p in (REPO_ROOT / "language_gate" / "receipts").glob("*.receipt.json")}
    sidecars_before = set((REPO_ROOT / "language_gate" / "test_files").glob("*.language_gate_review.json"))
    _run([str(VIOLATIONS), str(CLEAN)])
    receipts_after = {p.name for p in (REPO_ROOT / "language_gate" / "receipts").glob("*.receipt.json")}
    sidecars_after = set((REPO_ROOT / "language_gate" / "test_files").glob("*.language_gate_review.json"))
    assert receipts_after == receipts_before, receipts_after - receipts_before
    assert sidecars_after == sidecars_before, sidecars_after - sidecars_before


def test_wrapper_is_non_blocking_exit_zero():
    """Even with a flagged file, the CLI exits 0 (advisory / non-blocking)."""
    code = wrap.main([str(VIOLATIONS), "--json"])
    assert code == 0, code


def test_filter_skips_ineligible_paths():
    assert wrap._eligible("docs/x.md")
    assert wrap._eligible("a.txt") and wrap._eligible("a.json") and wrap._eligible("a.mdc")
    assert not wrap._eligible("src/app.py")
    assert not wrap._eligible("language_gate/receipts/foo.json")
    assert not wrap._eligible("node_modules/pkg/readme.md")


# ---------------------------------------------------------------- B) YAML guards

def _yaml_text() -> str:
    return YAML.read_text(encoding="utf-8")


def _yaml_config() -> str:
    """YAML with `#` comment lines stripped, so token guards check real config, not docs."""
    out = []
    for line in _yaml_text().splitlines():
        if line.lstrip().startswith("#"):
            continue
        out.append(line)
    return "\n".join(out)


def _top_block(cfg: str, key: str) -> list[str]:
    """Return the indented child lines of a top-level `key:` block (comments already stripped)."""
    lines = cfg.splitlines()
    out: list[str] = []
    inside = False
    for line in lines:
        if not line.strip():
            continue
        if not line.startswith(" ") and line.rstrip().split(":", 1)[0] == key:
            inside = True
            # inline value on same line (e.g. `on: pull_request`)
            tail = line.split(":", 1)[1].strip() if ":" in line else ""
            if tail:
                out.append("__INLINE__" + tail)
            continue
        if inside:
            if line.startswith(" "):
                out.append(line)
            else:
                break
    return out


def test_yaml_permissions_contents_read_only():
    """permissions: { contents: read } only — no write scope anywhere."""
    cfg = _yaml_config()
    block = _top_block(cfg, "permissions")
    kv = {}
    for ln in block:
        s = ln.strip()
        if ":" in s:
            k, v = s.split(":", 1)
            kv[k.strip()] = v.strip()
    assert kv == {"contents": "read"}, kv
    assert "write" not in "\n".join(block).lower()


def test_yaml_trigger_is_pull_request_only():
    """on: pull_request ONLY — never pull_request_target / push / schedule / dispatch."""
    cfg = _yaml_config()
    block = _top_block(cfg, "on")
    # collect trigger keys (either inline `on: pull_request` or child `pull_request:` lines)
    keys = set()
    for ln in block:
        if ln.startswith("__INLINE__"):
            keys.add(ln.replace("__INLINE__", "").strip())
            continue
        # child key at the shallowest indent
        stripped = ln.strip()
        if stripped and ln[: len(ln) - len(ln.lstrip())] == "  " and ":" in stripped:
            keys.add(stripped.split(":", 1)[0].strip())
        elif stripped and ln[: len(ln) - len(ln.lstrip())] == "  " and stripped:
            keys.add(stripped)
    assert keys == {"pull_request"}, keys
    forbidden = {"pull_request_target", "push", "schedule", "workflow_dispatch", "workflow_run"}
    assert not (keys & forbidden), keys & forbidden
    # hard textual backstop
    assert "pull_request_target" not in cfg
    assert "\nschedule:" not in cfg and "  schedule:" not in cfg


def test_yaml_no_secrets_or_credential_env():
    text = _yaml_config().lower()
    assert "secrets." not in text and "secrets:" not in text
    # no credential env blocks copied from census/autorun/auth-probe
    for token in ("supabase", "cloudflare", "cf_api", "github_token", "gh_token", "service_role", "anon_key"):
        assert token not in text, token
    # no top-level/job/step `env:` credential block at all
    cfg = _yaml_config()
    assert "\nenv:" not in cfg and "    env:" not in cfg and "  env:" not in cfg


def test_yaml_is_non_blocking():
    cfg = _yaml_config()
    # the gate step must be explicitly non-blocking (belt on top of the wrapper's exit-0)
    assert "continue-on-error: true" in cfg
    low = cfg.lower()
    for token in ("--write-supabase", "--write-receipt", "--fail-on-block-merge", "auto-merge", "automerge", "gh pr merge"):
        assert token not in low, token


def test_yaml_invokes_wrapper_report_only():
    cfg = _yaml_config()
    assert "language_gate_ci_wrapper.py" in cfg
    assert "--soft-undefined" in cfg
    assert "--write" not in cfg  # never mutation mode / no --write-* flags in the actual run


# ---------------------------------------------------------------- self-runner

def _self() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        t()
        passed += 1
        print(f"PASS {t.__name__}")
    print(f"\n{passed}/{len(tests)} green")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self())
