#!/usr/bin/env python3
"""TH for MO-1 — DRAFT-only templates, >=2 recurrence, schema-valid, red-capable."""
from __future__ import annotations
import copy, importlib.util, json, sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("mo1",HERE/"mo1_prompt_registry_compiler.py")
mo1=importlib.util.module_from_spec(spec); spec.loader.exec_module(mo1)
REG=mo1.compile_registry()

def test_only_recurring_classes_get_templates():
    classes={t["problem_class"] for t in REG["templates"]}
    assert "hygiene" not in classes, "hygiene has 1 packet (<2) — must not get a template"
    assert {"verification","architecture","revenue"} <= classes, classes

def test_every_template_is_draft():
    assert all(t["status"]=="DRAFT" for t in REG["templates"])
    assert "AUTO_DISPATCH_APPROVED" not in json.dumps(REG)

def test_registry_and_templates_schema_valid():
    assert mo1._schema_errors(REG, mo1.SCHEMA)==[], mo1._schema_errors(REG,mo1.SCHEMA)
    for t in REG["templates"]:
        assert mo1.lint_template(t)==[], mo1.lint_template(t)

def test_template_ids_and_evidence():
    import re
    for t in REG["templates"]:
        assert re.match(r"^TPL-[a-z0-9-]+-v[0-9]+$", t["template_id"]), t["template_id"]
        assert len(t["evidence_basis"])>=2

def test_lint_rejects_non_draft_status():
    t=copy.deepcopy(REG["templates"][0]); t["status"]="AUTO_DISPATCH_APPROVED"
    r=mo1.lint_template(t)
    assert any("not DRAFT" in x for x in r), r

def test_compiler_refuses_to_write_live_registry():
    import subprocess
    p=subprocess.run([sys.executable,str(HERE/"mo1_prompt_registry_compiler.py"),"--out","data/p0pgr_prompt_registry_v1.json"],text=True,capture_output=True)
    assert p.returncode!=0, "must refuse writing the live registry path"

TESTS=[test_only_recurring_classes_get_templates,test_every_template_is_draft,test_registry_and_templates_schema_valid,test_template_ids_and_evidence,test_lint_rejects_non_draft_status,test_compiler_refuses_to_write_live_registry]
def _main():
    f=0
    for t in TESTS:
        try: t(); print("PASS ",t.__name__)
        except AssertionError as e: f+=1; print("FAIL ",t.__name__,e)
    print(f"\n{len(TESTS)-f}/{len(TESTS)} green"); return 1 if f else 0
if __name__=="__main__": sys.exit(_main())
