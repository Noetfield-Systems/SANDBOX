#!/usr/bin/env python3
"""
CI-1  pr-governance-lint  (REPORT-ONLY parser)

Given a pull-request body STRING, assert the governance-required fields from
.github/pull_request_template.md are present and prints a JSON report.

Ground truth (.github/pull_request_template.md structured fields):
  - lane:                    (required)
  - motor_id_or_human_gate:  (advisory here)
  - Repo:                    (advisory)
  - Task cell:               (advisory)
  - receipt_id:              (required)
  - [ ] This PR does not duplicate a registered GitHub Action / CF cron / venture Worker motor   (required checked)
  - [ ] No promote * deploy prod * register brain artifact * SG/NOOS canonical append ...         (required checked)

This is REPORT-ONLY governance advice, matching .github/copilot-instructions.md
("keep changes repo-local ... verifier support flows"):
  * it NEVER writes, NEVER blocks a merge, NEVER touches Supabase / receipts;
  * it prints a JSON report and ALWAYS exits 0 (non-blocking) so the CI job is advisory.
The pass/fail signal lives in the JSON report's "ok" field, not the exit code.

A field/value is "present" only if, after stripping the HTML placeholder comment
`<!-- ... -->`, a non-empty value remains. A bare template line (value still the
placeholder comment, checkbox still `- [ ]`) is treated as UNFILLED, never as satisfied.
"""
from __future__ import annotations

import json
import re
import sys
from typing import Any

# Required scalar fields: key -> human label. Regex keys match the template lines.
REQUIRED_FIELDS = {
    "lane": "lane",
    "receipt_id": "receipt_id",
}
# Advisory (parsed + reported, but not required for ok=True).
ADVISORY_FIELDS = {
    "motor_id_or_human_gate": "motor_id_or_human_gate",
}

# Required checkboxes, matched by a stable substring of the template label.
REQUIRED_CHECKBOX_MARKERS = [
    ("non_duplication", "does not duplicate a registered"),
    ("no_promote_deploy", "No promote"),
]

_PLACEHOLDER_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def _strip_placeholder(raw: str) -> str:
    """Remove HTML-comment placeholders and surrounding whitespace."""
    return _PLACEHOLDER_RE.sub("", raw).strip()


def _extract_field(body: str, key: str) -> dict[str, Any]:
    """
    Find a `key: value` line (key at start of a line, case-insensitive on the key).
    Returns {"present": bool, "value": str|None, "raw": str|None}.
    """
    pattern = re.compile(
        r"^[ \t>*_-]*" + re.escape(key) + r"\s*:\s*(.*)$",
        re.IGNORECASE | re.MULTILINE,
    )
    m = pattern.search(body)
    if not m:
        return {"present": False, "value": None, "raw": None}
    raw = m.group(1).rstrip()
    value = _strip_placeholder(raw)
    return {"present": bool(value), "value": value or None, "raw": raw}


# A markdown task-list item: capture the checkbox state and the trailing label text.
_CHECKBOX_RE = re.compile(r"^[ \t>]*[-*]\s*\[( |x|X)\]\s*(.+?)\s*$", re.MULTILINE)


def _extract_checkboxes(body: str) -> list[dict[str, Any]]:
    boxes = []
    for state, label in _CHECKBOX_RE.findall(body):
        boxes.append({"label": label.strip(), "checked": state.lower() == "x"})
    return boxes


def lint_pr_body(body: str) -> dict[str, Any]:
    """Parse a PR body string and return a report-only governance-lint dict."""
    if body is None:
        body = ""

    fields: dict[str, Any] = {}
    missing: list[str] = []

    for key, label in REQUIRED_FIELDS.items():
        info = _extract_field(body, key)
        info["required"] = True
        fields[label] = info
        if not info["present"]:
            missing.append(label)

    for key, label in ADVISORY_FIELDS.items():
        info = _extract_field(body, key)
        info["required"] = False
        fields[label] = info

    all_boxes = _extract_checkboxes(body)
    required_checkboxes: list[dict[str, Any]] = []
    for cid, marker in REQUIRED_CHECKBOX_MARKERS:
        match = next(
            (b for b in all_boxes if marker.lower() in b["label"].lower()), None
        )
        entry = {
            "id": cid,
            "marker": marker,
            "found": match is not None,
            "checked": bool(match and match["checked"]),
            "label": match["label"] if match else None,
        }
        required_checkboxes.append(entry)
        if not entry["checked"]:
            missing.append(f"checkbox:{cid}")

    findings = [f"MISSING_OR_UNFILLED: {m}" for m in missing]

    ok = len(missing) == 0
    return {
        "check": "pr-governance-lint",
        "origin": "sandbox-advisory",
        "authority": "none",
        "report_only": True,
        "ok": ok,
        "verdict": "GOVERNANCE_FIELDS_PRESENT" if ok else "GOVERNANCE_FIELDS_MISSING",
        "required_fields": list(REQUIRED_FIELDS.values()),
        "fields": fields,
        "required_checkboxes": required_checkboxes,
        "all_checkboxes": all_boxes,
        "missing": missing,
        "findings": findings,
    }


def _read_body(argv: list[str]) -> str:
    """PR body from a file path arg, or stdin."""
    args = [a for a in argv[1:] if not a.startswith("-")]
    if args:
        with open(args[0], "r", encoding="utf-8") as fh:
            return fh.read()
    return sys.stdin.read()


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    body = _read_body(argv)
    report = lint_pr_body(body)
    print(json.dumps(report, indent=2))
    # REPORT-ONLY / NON-BLOCKING: always exit 0. The "ok" field carries the signal;
    # the CI job posts findings to the summary and never blocks the merge.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
