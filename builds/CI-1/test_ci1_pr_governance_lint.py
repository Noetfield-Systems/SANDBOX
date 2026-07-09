#!/usr/bin/env python3
"""
TH for CI-1  pr-governance-lint  — the parser's own proof + CI-guard assertions.

RED-CAPABLE by construction (positive vs a MINIMAL MUTATION of the same real fixture):
  * the VALID sample PR body (all governance fields filled, both required checkboxes
    checked) lints ok=True with an empty `missing` list;
  * a MINIMAL MUTATION — reverting exactly the receipt_id line back to its template
    placeholder comment (dropping the receipt_id value) — flips ok=False and puts
    "receipt_id" into `missing`. Nothing else changes. So the check reads the field
    from data, and is not green-by-construction.

Also asserts the workflow YAML carries every mandated CI guard:
  * permissions: contents: read  (ONLY — no write scopes anywhere);
  * on: pull_request  ONLY (never pull_request_target / push / schedule);
  * NO secrets: references and no credential env: keys;
  * job is NON-BLOCKING (continue-on-error) and invokes the parser in report-only mode
    (no --write-* / --fail-on-block-merge).
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("ci1", HERE / "ci1_pr_governance_lint.py")
ci1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ci1)

VALID_BODY = (HERE / "sample_pr_body_valid.md").read_text(encoding="utf-8")
YAML_PATH = HERE / "pr-governance-lint.yml"
YAML_TEXT = YAML_PATH.read_text(encoding="utf-8")
# Comment-stripped view: guard docstrings in `#` comments deliberately name the
# forbidden tokens; negative token scans must run over the EXECUTABLE yaml only.
YAML_CODE = "\n".join(re.sub(r"#.*$", "", ln) for ln in YAML_TEXT.splitlines())

PLACEHOLDER = '<!-- required if claiming autorun/done; else "human merge only" -->'


def _mutate_drop_receipt_id(body: str) -> str:
    """Minimal mutation: revert only the receipt_id line to its template placeholder."""
    mutated = re.sub(
        r"^receipt_id:.*$",
        f"receipt_id: {PLACEHOLDER}",
        body,
        count=1,
        flags=re.MULTILINE,
    )
    assert mutated != body, "mutation must actually change the body"
    return mutated


# ---------------------------------------------------------------- parser: positive
def test_valid_body_passes():
    report = ci1.lint_pr_body(VALID_BODY)
    assert report["ok"] is True, report["missing"]
    assert report["missing"] == []
    assert report["fields"]["lane"]["present"] is True
    assert report["fields"]["lane"]["value"] == "sg_governance"
    assert report["fields"]["receipt_id"]["present"] is True
    assert all(cb["checked"] for cb in report["required_checkboxes"])


# ---------------------------------------------------------------- parser: mutation teeth
def test_dropping_receipt_id_is_flagged():
    mutated = _mutate_drop_receipt_id(VALID_BODY)
    report = ci1.lint_pr_body(mutated)
    assert report["ok"] is False
    assert "receipt_id" in report["missing"]
    assert report["fields"]["receipt_id"]["present"] is False
    # discrimination: dropping ONLY receipt_id must not spuriously drop lane/checkboxes
    assert "lane" not in report["missing"]
    assert report["fields"]["lane"]["present"] is True


def test_unchecked_required_box_is_flagged():
    # a second, independent mutation: uncheck the non-duplication box
    mutated = VALID_BODY.replace(
        "- [x] This PR does not duplicate", "- [ ] This PR does not duplicate"
    )
    report = ci1.lint_pr_body(mutated)
    assert report["ok"] is False
    assert "checkbox:non_duplication" in report["missing"]


def test_report_only_exit_code_is_always_zero(tmp_path, capsys):
    # even a body that fails the lint must exit 0 (non-blocking / report-only)
    bad = tmp_path / "bad.md"
    bad.write_text("nothing useful here", encoding="utf-8")
    rc = ci1.main(["ci1", str(bad)])
    assert rc == 0
    out = capsys.readouterr().out
    assert '"ok": false' in out
    assert '"report_only": true' in out


# ---------------------------------------------------------------- CI-guard assertions
def _load_yaml():
    import yaml

    return yaml.safe_load(YAML_TEXT)


def _get_on(doc):
    # PyYAML parses the bare key `on:` as the boolean True (YAML 1.1 quirk).
    if "on" in doc:
        return doc["on"]
    return doc.get(True)


def test_guard_permissions_contents_read_only():
    doc = _load_yaml()
    # workflow-level permissions is exactly {contents: read}; no other scope granted
    assert doc["permissions"] == {"contents": "read"}, doc["permissions"]
    # no job re-grants a broader scope
    for job in doc["jobs"].values():
        assert "permissions" not in job or job["permissions"] == {"contents": "read"}
    # no write scope appears in the executable yaml
    assert "write" not in YAML_CODE.lower()


def test_guard_trigger_is_pull_request_only():
    doc = _load_yaml()
    on = _get_on(doc)
    keys = set(on.keys()) if isinstance(on, dict) else {on}
    assert keys == {"pull_request"}, keys
    for forbidden in ("pull_request_target", "\npush:", "schedule:", "workflow_dispatch"):
        assert forbidden not in YAML_CODE, forbidden


def test_guard_no_secrets_or_credentials():
    lowered = YAML_CODE.lower()
    assert "secrets." not in lowered
    assert "secrets:" not in lowered
    for cred in ("supabase", "cf_", "cloudflare", "token", "api_key", "password"):
        assert cred not in lowered, cred
    # the only env used is the PR body — never a credential
    assert "PR_BODY" in YAML_CODE


def test_guard_job_is_non_blocking_and_report_only():
    assert "continue-on-error: true" in YAML_CODE
    for danger in ("--write-supabase", "--write-receipt", "--fail-on-block-merge"):
        assert danger not in YAML_CODE, danger
    # posts findings to the job summary
    assert "GITHUB_STEP_SUMMARY" in YAML_CODE


def test_guard_yaml_invokes_the_parser():
    assert "ci1_pr_governance_lint.py" in YAML_TEXT


# ---------------------------------------------------------------- self-runner
def _run_all():
    import types

    tests = [
        (n, f)
        for n, f in sorted(globals().items())
        if n.startswith("test_") and isinstance(f, types.FunctionType)
    ]
    passed = 0
    for name, fn in tests:
        # skip fixture-taking tests in the bare self-runner
        argcount = fn.__code__.co_argcount
        if argcount:
            print(f"SKIP (needs pytest fixtures): {name}")
            continue
        fn()
        passed += 1
        print(f"PASS: {name}")
    print(f"\n{passed} self-runnable checks passed "
          f"({len(tests) - passed} pytest-fixture tests deferred to pytest)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run_all())
