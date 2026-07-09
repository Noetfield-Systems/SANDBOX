#!/usr/bin/env python3
"""
GV-4 — Registry cross-consistency linter  (catalog build B0 · GV-4)

Catches silent drift between the automation registries: every motor id referenced
in a "references" field must resolve to a DEFINED motor or agent. A reference to an
id that no longer exists (rename, delete, typo) is exactly the drift this flags.

Universe of known ids (references must land in here):
  * registry motors[].motor_id
  * registry agent_lanes[].agent_id
  * inventory repos[].workflows[].motor_id  and  repos[].mac_motors[].id
(The registry motors list is a curated SG-owned subset, so the inventory-declared
 motor ids are folded in — otherwise every cross-repo workflow is a false positive.)

References checked (each must resolve to the universe):
  1. registry motors[].conflicts_with[]
  2. registry duplication_forbidden[].allowed_motors[]
  3. inventory conflict_matrix[].motors[]

Read-only. Exits 1 on any dangling reference (RED), 0 when all resolve (GREEN).
Not the audit_* always-exit-0 pattern — it has teeth.

    python3 gv4_registry_xref_lint.py                       # lint the real registries
    python3 gv4_registry_xref_lint.py --registry X --inventory Y
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
DEFAULT_REGISTRY = REPO / "data" / "github_automation_registry_v1.json"
DEFAULT_INVENTORY = REPO / "data" / "automation_surface_inventory_v1.json"


def build_universe(reg: dict, inv: dict) -> set[str]:
    known: set[str] = set()
    for m in reg.get("motors", []):
        known.add(m.get("motor_id"))
    for a in reg.get("agent_lanes", []):
        known.add(a.get("agent_id"))
    for r in inv.get("repos", []):
        for w in (r.get("workflows") or []):
            if w.get("motor_id"):
                known.add(w["motor_id"])
        for mm in (r.get("mac_motors") or []):
            if mm.get("id"):
                known.add(mm["id"])
    known.discard(None)
    return known


def find_dangling(reg: dict, inv: dict) -> list[dict]:
    """Return a list of {source, id} for every reference that resolves to nothing."""
    known = build_universe(reg, inv)
    dangling: list[dict] = []

    def check(source: str, ids):
        for i in (ids or []):
            if i not in known:
                dangling.append({"source": source, "id": i})

    for m in reg.get("motors", []):
        check(f"registry.motors[{m.get('motor_id')}].conflicts_with", m.get("conflicts_with"))
    for d in reg.get("duplication_forbidden", []):
        check(f"registry.duplication_forbidden[{d.get('task')}].allowed_motors", d.get("allowed_motors"))
    for c in inv.get("conflict_matrix", []):
        check(f"inventory.conflict_matrix[{c.get('task_cell')}].motors", c.get("motors"))
    return dangling


def lint(registry_path: Path, inventory_path: Path) -> list[dict]:
    reg = json.loads(Path(registry_path).read_text(encoding="utf-8"))
    inv = json.loads(Path(inventory_path).read_text(encoding="utf-8"))
    return find_dangling(reg, inv)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    ap.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    args = ap.parse_args(argv)
    dangling = lint(args.registry, args.inventory)
    if dangling:
        print("GV-4 REGISTRY_XREF: DANGLING (unresolved references):")
        for d in dangling:
            print(f"  - {d['source']} -> {d['id']!r} (not a known motor or agent)")
        return 1
    print("GV-4 REGISTRY_XREF: CHECK_OK (all references resolve)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
