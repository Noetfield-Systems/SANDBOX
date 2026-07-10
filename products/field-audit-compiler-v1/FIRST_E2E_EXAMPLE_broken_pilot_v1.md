# FIRST E2E EXAMPLE — "Broken Pilot" Field Audit → Workflow Compile (v1)

**Package:** `FOUNDER_FIELD_AUDIT_TO_WORKFLOW_COMPILER_v1`
**Source of truth:** `_SPINE_v1.json` → `e2e_example` (this document is a readable render of that object; every id, field name, and value here is copied from the spine — nothing new is invented).
**Reads:** `VOICE_TO_OBSERVATION_SCHEMA_v1.json` (stage-1 objects) · `RECEIPT_SCHEMA_FIELD_AUDIT_v1.json` (`field_audit_receipt_v1`).
**Locked at:** 2026-07-09

---

## 0. What this walkthrough proves

One founder speaks **6 defects** into a phone against a surface they own. The compiler turns that single utterance into **19 deterministic, CF-re-derivable WorkflowContracts** (6 seed + 13 fan-out), runs them as sandbox jobs with `authority=none`, emits 6 machine-checkable receipts, and lands **6 pending ApprovalItems**. No PASS is self-minted, no canonical file is mutated, every patch is staged as a diff and none is applied.

This is the difference between a **compiler** and a chatbot: the output is not advice, it is a set of pure predicates (`HTTP status | DOM/selector presence | regex | hash equality`) an independent Cloudflare Worker can re-run with zero trust in the author.

### Authority binding (obeyed at every stage below)

| Layer | Role in this run |
|---|---|
| `sina-governance-SSOT` | Owns the templates registry + risk policy. Runs nothing here. |
| `sandbox` (`authority=none`) | Where this whole chain executes. **Cannot mint PASS.** Every write stays inside `sandbox/products/field-audit-compiler-v1/`. Jobs only inspect / patch-into-a-diff / test / return receipts. |
| `noetfield-cloud-factory-infra` | The independent **Cloudflare Worker verifier is the ONLY PASS issuer**; Supabase is the ledger. |
| `cat-05-sandbox-worktree-execution` | The **watcher slot** each `SandboxJob` runs in — an isolated worktree, not "the sandbox". |
| `cat-09-receipt-trust-audit-layer` | Promotion home for GUARD/META receipts (links, footer, request-id, chat, route health). |
| `cat-10-vertical-proof-products` | Promotion home for REVENUE receipts (CTA, auth, pricing/offer copy). |

**Execution rule (enforced below):** all work goes to sandbox FIRST. No direct deploy, merge, deletion, cron unlock, real send, or canonical-repo mutation from raw voice. Canonical changes require an approved `ApprovalItem`. The run targets a founder-supplied `{TARGET_URL}` only — `{TARGET_URL}` is a placeholder; nothing in this document fetches a live surface.

### The compile chain (10 steps)

```
VoiceNote ──▶ Transcript ──▶ Observation[6] ──▶ IssueCluster[6] ──▶ WorkflowContract[6 seed → 19 expanded]
     │             │              │                   │                        │
  (capture)   (normalize)     (extract)           (dedup)                 (compile)
                                                                              │
                    ApprovalItem[6] ◀── Receipt[6] ◀── VerificationRun[6] ◀── SandboxJob[6]
                       (human gate)     (field_audit    (CF Worker only        (cat-05 watcher,
                                        _receipt_v1)      issues PASS)          authority=none)
```

---

## 1. AuditSession — one founder pass against one surface

The root object. Every downstream object carries this `session_id`. The founder supplied `target_url: {TARGET_URL}`; the compiler never hardcodes a live surface.

```json
{
  "id": "AS-2026-07-09-fieldaudit",
  "founder_id": "founder-1",
  "surface_kind": "website",
  "target_url": "{TARGET_URL}",
  "created_at": "2026-07-09T20:00:00Z",
  "status": "awaiting_approval",
  "voice_note_ids": ["VN-1"],
  "observation_ids": ["OB-1", "OB-2", "OB-3", "OB-4", "OB-5", "OB-6"],
  "authority": "none"
}
```

The `VoiceNote` that anchors it (audio is a sandbox-local blob key, never an external URL):

```json
{
  "id": "VN-1",
  "session_id": "AS-2026-07-09-fieldaudit",
  "audio_ref": "sandbox/products/field-audit-compiler-v1/blobs/VN-1.webm",
  "captured_at": "2026-07-09T20:00:00Z",
  "source_lang": "en",
  "transcript_id": "TR-1"
}
```

---

## 2. Transcript — deterministic, replayable normalization

The founder said (verbatim ASR, `text_raw`):

> "apply for pilot link is broken cookie link goes nowhere sign-in is broken trust brief twelve thousand dollar six week package copy needs update request ids are not visible web chat ui is bad"

Normalization is **pure and replayable** — not an LLM rewrite. The ordered `normalization_ops` are the audit trail: `twelve thousand dollar → $12,000`, `six week → 8-week`, sentence splitting. This is what makes downstream regex checks (e.g. `price_matches_canonical`) deterministic.

```json
{
  "id": "TR-1",
  "voice_note_id": "VN-1",
  "session_id": "AS-2026-07-09-fieldaudit",
  "text_raw": "apply for pilot link is broken cookie link goes nowhere sign-in is broken trust brief twelve thousand dollar six week package copy needs update request ids are not visible web chat ui is bad",
  "text_normalized": "apply for pilot link is broken. cookie link goes nowhere. sign-in is broken. trust brief $12,000 8-week package copy needs update. request ids are not visible. web chat ui is bad.",
  "source_lang": "en",
  "translated": false,
  "normalization_ops": [
    { "op": "number_word_expand", "from": "twelve thousand", "to": "10000" },
    { "op": "currency_normalize", "from": "twelve thousand dollar", "to": "$12,000" },
    { "op": "hyphen_join", "from": "six week", "to": "8-week" },
    { "op": "punctuation_canon", "from": "<utterance>", "to": "<sentence-split>" }
  ],
  "confidence": 0.93
}
```

> **Why normalization is load-bearing:** the pricing check later asserts `extracted_price == '$12,000'` and `extracted_duration == '8-week'`. Those exact tokens only exist because `currency_normalize` and `hyphen_join` ran here, deterministically, and left a replayable record. A CF Worker re-running the same ops gets the same string.

---

## 3. Observations — 6 atomic defects sliced from one transcript

Each sentence becomes one `Observation`. `raw_span` is the provenance anchor (exact substring of `text_normalized`), `defect_kind` selects the template 1:1, `surface_ref` stays `unresolved:<hint>` until a sandbox job resolves it against `{TARGET_URL}`. Nothing here is verified — `severity_guess` and `confidence` are heuristic.

| id | raw_span | target_hint | defect_kind | severity_guess | confidence |
|---|---|---|---|---|---|
| OB-1 | "apply for pilot link is broken" | Apply for Program link | `cta_route` | blocker | 0.90 |
| OB-2 | "cookie link goes nowhere" | Cookie link | `legal_footer_link` | high | 0.88 |
| OB-3 | "sign-in is broken" | Sign-in | `auth_entrypoint` | blocker | 0.90 |
| OB-4 | "trust brief $12,000 8-week package copy needs update" | Acme Brief $12,000 8-week package copy | `pricing_claim` | high | 0.82 |
| OB-5 | "request ids are not visible" | Request IDs | `request_id_visibility` | medium | 0.85 |
| OB-6 | "web chat ui is bad" | Web chat UI | `web_chat_ux` | medium | 0.70 |

Full form of the two that drive the trickiest routing (`cta_route` chosen over generic `broken_link`; `pricing_claim` chosen over `offer_copy`):

```json
[
  { "id": "OB-1", "session_id": "AS-2026-07-09-fieldaudit", "transcript_id": "TR-1",
    "raw_span": "apply for pilot link is broken", "surface_ref": "unresolved:Apply for Program link",
    "target_hint": "Apply for Program link", "severity_guess": "blocker",
    "defect_kind": "cta_route", "confidence": 0.9, "needs_translation": false },

  { "id": "OB-4", "session_id": "AS-2026-07-09-fieldaudit", "transcript_id": "TR-1",
    "raw_span": "trust brief $12,000 8-week package copy needs update",
    "surface_ref": "unresolved:Acme Brief package copy",
    "target_hint": "Acme Brief $12,000 8-week package copy", "severity_guess": "high",
    "defect_kind": "pricing_claim", "confidence": 0.82, "needs_translation": false }
]
```

*(OB-2, OB-3, OB-5, OB-6 follow the identical shape — see the table.)*

---

## 4. IssueClusters — group + dedup, one contract each

Observations are grouped and deduped by `defect_kind` + resolved target scope. In this run each observation is distinct, so the map is 1:1 — but the `dedup_note` records the routing decisions that matter, and each cluster already declares the `target_refs` scope its contract will fan across.

```json
[
  { "id": "IC-1", "observation_ids": ["OB-1"], "defect_kind": "cta_route",
    "label": "Broken 'Apply for Program' CTA",
    "target_refs": ["a[data-cta='apply-for-program']", "/apply-for-program"],
    "severity": "blocker",
    "dedup_note": "Single CTA observation; will fan to all CTAs via pattern expansion." },

  { "id": "IC-2", "observation_ids": ["OB-2"], "defect_kind": "legal_footer_link",
    "label": "Footer Cookie link goes nowhere",
    "target_refs": ["footer a[href*='cookie']"], "severity": "high",
    "dedup_note": "Grouped under legal_footer_link (more specific than generic broken_link)." },

  { "id": "IC-3", "observation_ids": ["OB-3"], "defect_kind": "auth_entrypoint",
    "label": "Sign-in broken",
    "target_refs": ["a[href*='login']", "/login"], "severity": "blocker", "dedup_note": "" },

  { "id": "IC-4", "observation_ids": ["OB-4"], "defect_kind": "pricing_claim",
    "label": "Acme Brief $12,000 / 8-week copy stale",
    "target_refs": ["[data-offer='acme-brief']"], "severity": "high",
    "dedup_note": "pricing_claim chosen over offer_copy because the specific claim ($12,000, 8-week) is checkable against canonical; an offer_copy_consistency_check contract is spawned as a sibling in expansion." },

  { "id": "IC-5", "observation_ids": ["OB-5"], "defect_kind": "request_id_visibility",
    "label": "Request IDs not visible",
    "target_refs": ["main", "[data-request-id]"], "severity": "medium", "dedup_note": "" },

  { "id": "IC-6", "observation_ids": ["OB-6"], "defect_kind": "web_chat_ux",
    "label": "Web chat widget UX poor",
    "target_refs": ["[data-chat]"], "severity": "medium", "dedup_note": "" }
]
```

**Two routing decisions worth calling out (both from the spine):**
- **IC-1** picks `cta_route` (not `broken_link`) because a CTA is a money path — its receipt promotes to CAT-10 REVENUE, and its `cta_present` + `cta_route_resolves` checks are stronger than a bare href scan. The generic `broken_link_scan` still shows up later as a *sibling* in fan-out.
- **IC-4** picks `pricing_claim` (not `offer_copy`) because "$12,000 / 8-week" is a **concrete checkable claim** against a canonical source. An `offer_copy_consistency_check` is spawned as a sibling contract (WC-4b) to cover the surrounding name/inclusions copy.

---

## 5. WorkflowContracts — the compile step (6 seed contracts)

Each cluster compiles to one `WorkflowContract`: a `template_id`, a `target` (founder ref + `scope_selector` for the fan-out), template `params`, the pure `deterministic_checks`, `verifier_logic` telling the CF Worker how to re-derive, a `pattern_expansion_rule`, a `promotion` (category + value_class), a `risk_class`, and `approval_required`.

The spine's **first-five** templates (`route_health_check`, `broken_link_scan`, `cta_route_check`, `auth_entrypoint_check`, `request_id_visibility_check`) are the deterministic HTTP+static-DOM core. WC-1/3/5 are covered by them; WC-2 (legal footer link) is covered via `broken_link_scan` fan-out and sequenced later, and WC-4 (pricing, needs a supplied canonical) and WC-6 (chat, needs rendering) are sequenced after.

### Contract summary

| WC | Cluster | template_id | scope_selector (fan-out) | risk_class | approval_required | promotion → value_class |
|---|---|---|---|---|---|---|
| WC-1 | IC-1 | `cta_route_check` | `a[data-cta], button[data-cta]` | read_only | false | CAT-10 → REVENUE |
| WC-2 | IC-2 | `legal_footer_link_check` | `footer a[href]` | read_only | false | CAT-09 → GUARD |
| WC-3 | IC-3 | `auth_entrypoint_check` | `a[href*='login'], a[href*='signin']` | read_only | false | CAT-10 → REVENUE |
| WC-4 | IC-4 | `pricing_claim_consistency_check` | `[data-offer='acme-brief']` | **canonical_change** | **true** | CAT-10 → REVENUE |
| WC-5 | IC-5 | `request_id_visibility_check` | `main, [data-request-id]` | low_risk_patch | true | CAT-09 → GUARD |
| WC-6 | IC-6 | `web_chat_ux_check` | `[data-chat]` | low_risk_patch | true | CAT-09 → META |

> **`risk_class` is where the authority model bites.** WC-1/2/3 are `read_only` *checks* (they only diagnose) — but the FIX they imply is a canonical change, which is why their ApprovalItems (§9) still carry `risk_class: canonical_change`. WC-4 is itself `canonical_change` (rewriting live copy). WC-5/6 are `low_risk_patch` (additive attribute/element). Nothing auto-applies.

### WC-1 — cta_route_check (full)

```json
{
  "id": "WC-1", "cluster_id": "IC-1", "session_id": "AS-2026-07-09-fieldaudit",
  "template_id": "cta_route_check",
  "target": { "target_url": "{TARGET_URL}", "scope_selector": "a[data-cta], button[data-cta]" },
  "params": { "cta_selector": "a[data-cta='apply-for-program']", "expected_status": [200] },
  "deterministic_checks": [
    { "name": "cta_present",        "logic": "DOM selector presence", "pass_condition": "querySelector matches" },
    { "name": "cta_route_resolves", "logic": "HTTP GET href",         "pass_condition": "status==200 && href not in ['','#']" }
  ],
  "expected_outputs": { "cta_present": true, "cta_route_resolves": true },
  "verifier_logic": "CF Worker re-selects CTA + re-fetches href; recompute summary; FAIL on mismatch.",
  "pattern_expansion_rule": "instantiate cta_route_check for every [data-cta] on the surface",
  "promotion": { "factory_category": "CAT-10-VERTICAL-PROOF-PRODUCTS", "value_class": "REVENUE" },
  "risk_class": "read_only", "approval_required": false
}
```

### WC-4 — pricing_claim_consistency_check (full)

Note the honest `expected_outputs`: the founder *said the copy is stale*, so the checks are **expected to fail** against canonical until patched. That is the compiler encoding the founder's assertion as a falsifiable predicate — not asserting it's already fixed.

```json
{
  "id": "WC-4", "cluster_id": "IC-4", "session_id": "AS-2026-07-09-fieldaudit",
  "template_id": "pricing_claim_consistency_check",
  "target": { "target_url": "{TARGET_URL}", "scope_selector": "[data-offer='acme-brief']" },
  "params": { "canonical_copy_source": "{SSOT_PRICING_REF}", "expected_price": "$12,000", "expected_duration": "8-week" },
  "deterministic_checks": [
    { "name": "price_matches_canonical",    "logic": "regex extract price + equality",    "pass_condition": "extracted_price=='$12,000'" },
    { "name": "duration_matches_canonical", "logic": "regex extract duration + equality", "pass_condition": "extracted_duration=='8-week'" }
  ],
  "expected_outputs": { "price_matches_canonical": false, "duration_matches_canonical": false,
    "interpretation": "founder said copy needs update -> canonical mismatch expected until patched" },
  "verifier_logic": "CF Worker re-fetches page + canonical, re-runs regexes, re-compares; recompute summary; FAIL on mismatch.",
  "pattern_expansion_rule": "instantiate across all commercial surfaces referencing Acme Brief price/duration; spawn sibling offer_copy_consistency_check",
  "promotion": { "factory_category": "CAT-10-VERTICAL-PROOF-PRODUCTS", "value_class": "REVENUE" },
  "risk_class": "canonical_change", "approval_required": true
}
```

<details>
<summary><b>WC-2, WC-3, WC-5, WC-6 — full JSON</b></summary>

```json
[
  { "id": "WC-2", "cluster_id": "IC-2", "session_id": "AS-2026-07-09-fieldaudit",
    "template_id": "legal_footer_link_check",
    "target": { "target_url": "{TARGET_URL}", "scope_selector": "footer a[href]" },
    "params": { "required": ["cookie"] },
    "deterministic_checks": [
      { "name": "cookie_link_present_and_resolves", "logic": "footer match + HTTP GET",
        "pass_condition": "found && status==200 && href not in ['','#']" } ],
    "expected_outputs": { "cookie_link_present_and_resolves": true },
    "verifier_logic": "CF Worker re-parses footer + re-fetches; recompute summary; FAIL on mismatch.",
    "pattern_expansion_rule": "instantiate for privacy/terms/cookie/accessibility footer links",
    "promotion": { "factory_category": "CAT-09-RECEIPT-TRUST-AUDIT-LAYER", "value_class": "GUARD" },
    "risk_class": "read_only", "approval_required": false },

  { "id": "WC-3", "cluster_id": "IC-3", "session_id": "AS-2026-07-09-fieldaudit",
    "template_id": "auth_entrypoint_check",
    "target": { "target_url": "{TARGET_URL}", "scope_selector": "a[href*='login'], a[href*='signin']" },
    "params": { "expected_status": [200] },
    "deterministic_checks": [
      { "name": "auth_entry_present",   "logic": "DOM selector presence", "pass_condition": "at least one auth_selector matches" },
      { "name": "auth_route_resolves",  "logic": "HTTP GET auth href",    "pass_condition": "status==200" } ],
    "expected_outputs": { "auth_entry_present": true, "auth_route_resolves": true },
    "verifier_logic": "CF Worker re-selects + re-fetches auth route; recompute summary; FAIL on mismatch.",
    "pattern_expansion_rule": "instantiate for every auth entrypoint (header, footer, in-body)",
    "promotion": { "factory_category": "CAT-10-VERTICAL-PROOF-PRODUCTS", "value_class": "REVENUE" },
    "risk_class": "read_only", "approval_required": false },

  { "id": "WC-5", "cluster_id": "IC-5", "session_id": "AS-2026-07-09-fieldaudit",
    "template_id": "request_id_visibility_check",
    "target": { "target_url": "{TARGET_URL}", "scope_selector": "main, [data-request-id]" },
    "params": { "id_regex": "(req|request|corr)[-_ ]?id[:#]?\\s*[A-Za-z0-9-]{6,}" },
    "deterministic_checks": [
      { "name": "request_id_visible", "logic": "regex match on rendered text/attr",
        "pass_condition": "regex matches OR [data-request-id] non-empty" } ],
    "expected_outputs": { "request_id_visible": false },
    "verifier_logic": "CF Worker re-fetches view + re-runs regex; recompute summary; FAIL on mismatch.",
    "pattern_expansion_rule": "instantiate across all views expected to show a request id",
    "promotion": { "factory_category": "CAT-09-RECEIPT-TRUST-AUDIT-LAYER", "value_class": "GUARD" },
    "risk_class": "low_risk_patch", "approval_required": true },

  { "id": "WC-6", "cluster_id": "IC-6", "session_id": "AS-2026-07-09-fieldaudit",
    "template_id": "web_chat_ux_check",
    "target": { "target_url": "{TARGET_URL}", "scope_selector": "[data-chat]" },
    "params": { "widget_selector": "[data-chat]", "required_controls": ["input,textarea", "button[type=submit],[data-chat-send]"] },
    "deterministic_checks": [
      { "name": "chat_widget_mounts",   "logic": "DOM presence",            "pass_condition": "exactly one match" },
      { "name": "chat_controls_present","logic": "DOM presence input+send", "pass_condition": "each control selector matches" },
      { "name": "chat_input_labeled",   "logic": "attr presence",          "pass_condition": "aria-label or placeholder non-empty" } ],
    "expected_outputs": { "chat_widget_mounts": true, "chat_controls_present": true, "chat_input_labeled": false },
    "verifier_logic": "CF Worker re-fetches HTML + re-selects widget/controls/attrs; recompute summary; FAIL on mismatch.",
    "pattern_expansion_rule": "instantiate on every page mounting the chat component",
    "promotion": { "factory_category": "CAT-09-RECEIPT-TRUST-AUDIT-LAYER", "value_class": "META" },
    "risk_class": "low_risk_patch", "approval_required": true }
]
```
</details>

---

## 6. SandboxJobs — bounded execution in the cat-05 watcher

Each contract runs as one `SandboxJob` in `CAT-05-SANDBOX-WORKTREE-EXECUTION` with `authority=none`. The `job_kind` is bounded to `inspect | patch_diff | test`. **Read-only diagnostics** (`inspect`) produce a receipt only. **Patch jobs** (`patch_diff`) additionally stage a diff at `diff_ref` — **staged, never applied**.

| SJ | contract | job_kind | diff_ref | receipt_id |
|---|---|---|---|---|
| SJ-1 | WC-1 | `inspect` | null | `field_audit_receipt_v1:AS-2026-07-09-fieldaudit:WC-1` |
| SJ-2 | WC-2 | `inspect` | null | `field_audit_receipt_v1:AS-2026-07-09-fieldaudit:WC-2` |
| SJ-3 | WC-3 | `inspect` | null | `field_audit_receipt_v1:AS-2026-07-09-fieldaudit:WC-3` |
| SJ-4 | WC-4 | `patch_diff` | `sandbox/.../SJ-4/acme-brief-copy.diff` | `field_audit_receipt_v1:AS-2026-07-09-fieldaudit:WC-4` |
| SJ-5 | WC-5 | `patch_diff` | `sandbox/.../SJ-5/request-id-display.diff` | `field_audit_receipt_v1:AS-2026-07-09-fieldaudit:WC-5` |
| SJ-6 | WC-6 | `patch_diff` | `sandbox/.../SJ-6/chat-input-label.diff` | `field_audit_receipt_v1:AS-2026-07-09-fieldaudit:WC-6` |

```json
[
  { "id": "SJ-1", "workflow_contract_id": "WC-1", "session_id": "AS-2026-07-09-fieldaudit",
    "category_id": "CAT-05-SANDBOX-WORKTREE-EXECUTION", "authority": "none", "job_kind": "inspect",
    "target": { "target_url": "{TARGET_URL}" }, "inputs": { "cta_selector": "a[data-cta='apply-for-program']" },
    "status": "done", "output_ref": "sandbox/.../SJ-1/", "diff_ref": null,
    "receipt_id": "field_audit_receipt_v1:AS-2026-07-09-fieldaudit:WC-1" },

  { "id": "SJ-4", "workflow_contract_id": "WC-4", "session_id": "AS-2026-07-09-fieldaudit",
    "category_id": "CAT-05-SANDBOX-WORKTREE-EXECUTION", "authority": "none", "job_kind": "patch_diff",
    "target": { "target_url": "{TARGET_URL}" }, "inputs": { "expected_price": "$12,000", "expected_duration": "8-week" },
    "status": "done", "output_ref": "sandbox/.../SJ-4/",
    "diff_ref": "sandbox/.../SJ-4/acme-brief-copy.diff",
    "receipt_id": "field_audit_receipt_v1:AS-2026-07-09-fieldaudit:WC-4" }
]
```

*(SJ-2/SJ-3 are `inspect` with `diff_ref: null`; SJ-5/SJ-6 are `patch_diff` staging `request-id-display.diff` / `chat-input-label.diff`. Same shape.)*

---

## 7. VerificationRuns + verifier logic — who is allowed to say PASS

Each job's checks are adjudicated by a `VerificationRun`. **In sandbox, a self-write is always `verifier_status: UNVERIFIED`.** Only the independent Cloudflare Worker (`verifier_runtime: cloudflare_worker`) may issue `PASS/FAIL/BLOCKED`.

### The verifier doctrine (identical to cat-09, from the receipt schema)

1. **Ignore the author's `summary`. Recompute it from `checks[]`:** `total = len(checks)`, `passed = count(passed==true)`, `failed = count(passed==false)`.
2. On **any** mismatch between submitted and recomputed summary → `verifier_status = FAIL`.
3. **Re-derive each check** by refetching/re-selecting/re-regexing/re-hashing against the founder's `{TARGET_URL}` (and the supplied canonical, for WC-4) — the Worker does not trust the author's booleans blindly; it validates evidence shape and re-derives.
4. Schema discriminator must be `field_audit_receipt_v1` and `category_id` must equal the Worker's bound `EXPECTED_CATEGORY_ID`, else FAIL.
5. **`PASS` additionally requires edge-execution + secondary-CF-account proof.** The sandbox author can never self-mint PASS.

In this run every check reflects a genuinely broken surface, so **all six runs return `FAIL`** — the *correct* outcome. A FAIL here is a true positive: the compiler proved the defect the founder spoke.

```json
[
  { "id": "VR-1", "sandbox_job_id": "SJ-1", "workflow_contract_id": "WC-1", "session_id": "AS-2026-07-09-fieldaudit",
    "verifier_runtime": "cloudflare_worker", "checked_at": "2026-07-09T20:05:00Z",
    "summary": { "total": 2, "passed": 1, "failed": 1 }, "verifier_status": "FAIL", "value_class": "REVENUE",
    "receipt_id": "field_audit_receipt_v1:AS-2026-07-09-fieldaudit:WC-1" },
  { "id": "VR-2", "sandbox_job_id": "SJ-2", "workflow_contract_id": "WC-2", "session_id": "AS-2026-07-09-fieldaudit",
    "verifier_runtime": "cloudflare_worker", "checked_at": "2026-07-09T20:05:10Z",
    "summary": { "total": 1, "passed": 0, "failed": 1 }, "verifier_status": "FAIL", "value_class": "GUARD",
    "receipt_id": "field_audit_receipt_v1:AS-2026-07-09-fieldaudit:WC-2" },
  { "id": "VR-3", "sandbox_job_id": "SJ-3", "workflow_contract_id": "WC-3", "session_id": "AS-2026-07-09-fieldaudit",
    "verifier_runtime": "cloudflare_worker", "checked_at": "2026-07-09T20:05:20Z",
    "summary": { "total": 2, "passed": 1, "failed": 1 }, "verifier_status": "FAIL", "value_class": "REVENUE",
    "receipt_id": "field_audit_receipt_v1:AS-2026-07-09-fieldaudit:WC-3" },
  { "id": "VR-4", "sandbox_job_id": "SJ-4", "workflow_contract_id": "WC-4", "session_id": "AS-2026-07-09-fieldaudit",
    "verifier_runtime": "cloudflare_worker", "checked_at": "2026-07-09T20:05:30Z",
    "summary": { "total": 2, "passed": 0, "failed": 2 }, "verifier_status": "FAIL", "value_class": "REVENUE",
    "receipt_id": "field_audit_receipt_v1:AS-2026-07-09-fieldaudit:WC-4" },
  { "id": "VR-5", "sandbox_job_id": "SJ-5", "workflow_contract_id": "WC-5", "session_id": "AS-2026-07-09-fieldaudit",
    "verifier_runtime": "cloudflare_worker", "checked_at": "2026-07-09T20:05:40Z",
    "summary": { "total": 1, "passed": 0, "failed": 1 }, "verifier_status": "FAIL", "value_class": "GUARD",
    "receipt_id": "field_audit_receipt_v1:AS-2026-07-09-fieldaudit:WC-5" },
  { "id": "VR-6", "sandbox_job_id": "SJ-6", "workflow_contract_id": "WC-6", "session_id": "AS-2026-07-09-fieldaudit",
    "verifier_runtime": "cloudflare_worker", "checked_at": "2026-07-09T20:05:50Z",
    "summary": { "total": 3, "passed": 2, "failed": 1 }, "verifier_status": "FAIL", "value_class": "META",
    "receipt_id": "field_audit_receipt_v1:AS-2026-07-09-fieldaudit:WC-6" }
]
```

---

## 8. Receipts — the `field_audit_receipt_v1` artifacts

Each run emits one receipt. The shape deliberately mirrors the factory-proven `category_cloud_task_receipt_v1` so the CF Worker can re-derive it. `checks[].evidence` carries **stored proof, not prose** (http_status, hashes, selector, regex expected/actual). Every sandbox receipt carries `authority: "none"`.

### Receipt roll-up

| Receipt (WC) | category_id | checks pass/total | value_class | verifier_status | key evidence |
|---|---|---|---|---|---|
| WC-1 | CAT-10 | 1/2 | REVENUE | FAIL | `GET {TARGET_URL}/apply-for-program → 404` |
| WC-2 | CAT-09 | 0/1 | GUARD | FAIL | footer Cookie `href='#'` → unresolved |
| WC-3 | CAT-10 | 1/2 | REVENUE | FAIL | `GET {TARGET_URL}/login → 500` |
| WC-4 | CAT-10 | 0/2 | REVENUE | FAIL | rendered `$9,000`/`5-week` ≠ `$12,000`/`8-week` |
| WC-5 | CAT-09 | 0/1 | GUARD | FAIL | no request-id pattern in rendered view |
| WC-6 | CAT-09 | 2/3 | META | FAIL | chat input missing aria-label + placeholder |

### WC-1 receipt (full — CTA 404)

```json
{
  "schema": "field_audit_receipt_v1",
  "session_id": "AS-2026-07-09-fieldaudit",
  "workflow_contract_id": "WC-1", "sandbox_job_id": "SJ-1",
  "category_id": "CAT-10-VERTICAL-PROOF-PRODUCTS",
  "checked_at": "2026-07-09T20:05:00Z",
  "checks": [
    { "name": "cta_present", "passed": true,  "detail": "a[data-cta='apply-for-program'] found",
      "evidence": { "selector": "a[data-cta='apply-for-program']", "match": true } },
    { "name": "cta_route_resolves", "passed": false, "detail": "GET {TARGET_URL}/apply-for-program -> HTTP 404",
      "evidence": { "url": "{TARGET_URL}/apply-for-program", "http_status": 404 } }
  ],
  "summary": { "total": 2, "passed": 1, "failed": 1 },
  "value_class": "REVENUE", "verifier_status": "FAIL", "authority": "none"
}
```

### WC-4 receipt (full — stale pricing, both checks fail)

```json
{
  "schema": "field_audit_receipt_v1",
  "session_id": "AS-2026-07-09-fieldaudit",
  "workflow_contract_id": "WC-4", "sandbox_job_id": "SJ-4",
  "category_id": "CAT-10-VERTICAL-PROOF-PRODUCTS",
  "checked_at": "2026-07-09T20:05:30Z",
  "checks": [
    { "name": "price_matches_canonical", "passed": false, "detail": "rendered '$9,000' != canonical '$12,000'",
      "evidence": { "regex": "\\$[0-9,]+", "expected": "$12,000", "actual": "$9,000", "match": false } },
    { "name": "duration_matches_canonical", "passed": false, "detail": "rendered '5-week' != canonical '8-week'",
      "evidence": { "regex": "[0-9]+-week", "expected": "8-week", "actual": "5-week", "match": false } }
  ],
  "summary": { "total": 2, "passed": 0, "failed": 2 },
  "value_class": "REVENUE", "verifier_status": "FAIL", "authority": "none"
}
```

<details>
<summary><b>WC-2, WC-3, WC-5, WC-6 receipts — full JSON</b></summary>

```json
[
  { "schema": "field_audit_receipt_v1", "session_id": "AS-2026-07-09-fieldaudit",
    "workflow_contract_id": "WC-2", "sandbox_job_id": "SJ-2", "category_id": "CAT-09-RECEIPT-TRUST-AUDIT-LAYER",
    "checked_at": "2026-07-09T20:05:10Z",
    "checks": [ { "name": "cookie_link_present_and_resolves", "passed": false,
      "detail": "footer Cookie link href='#' -> unresolved",
      "evidence": { "selector": "footer a[href*='cookie']", "url": "#", "match": false } } ],
    "summary": { "total": 1, "passed": 0, "failed": 1 },
    "value_class": "GUARD", "verifier_status": "FAIL", "authority": "none" },

  { "schema": "field_audit_receipt_v1", "session_id": "AS-2026-07-09-fieldaudit",
    "workflow_contract_id": "WC-3", "sandbox_job_id": "SJ-3", "category_id": "CAT-10-VERTICAL-PROOF-PRODUCTS",
    "checked_at": "2026-07-09T20:05:20Z",
    "checks": [
      { "name": "auth_entry_present", "passed": true, "detail": "Sign-in link found",
        "evidence": { "selector": "a[href*='login']", "match": true } },
      { "name": "auth_route_resolves", "passed": false, "detail": "GET {TARGET_URL}/login -> HTTP 500",
        "evidence": { "url": "{TARGET_URL}/login", "http_status": 500 } } ],
    "summary": { "total": 2, "passed": 1, "failed": 1 },
    "value_class": "REVENUE", "verifier_status": "FAIL", "authority": "none" },

  { "schema": "field_audit_receipt_v1", "session_id": "AS-2026-07-09-fieldaudit",
    "workflow_contract_id": "WC-5", "sandbox_job_id": "SJ-5", "category_id": "CAT-09-RECEIPT-TRUST-AUDIT-LAYER",
    "checked_at": "2026-07-09T20:05:40Z",
    "checks": [ { "name": "request_id_visible", "passed": false,
      "detail": "no request-id pattern or [data-request-id] in rendered view",
      "evidence": { "regex": "(req|request|corr)[-_ ]?id", "match": false } } ],
    "summary": { "total": 1, "passed": 0, "failed": 1 },
    "value_class": "GUARD", "verifier_status": "FAIL", "authority": "none" },

  { "schema": "field_audit_receipt_v1", "session_id": "AS-2026-07-09-fieldaudit",
    "workflow_contract_id": "WC-6", "sandbox_job_id": "SJ-6", "category_id": "CAT-09-RECEIPT-TRUST-AUDIT-LAYER",
    "checked_at": "2026-07-09T20:05:50Z",
    "checks": [
      { "name": "chat_widget_mounts", "passed": true, "detail": "[data-chat] present",
        "evidence": { "selector": "[data-chat]", "match": true } },
      { "name": "chat_controls_present", "passed": true, "detail": "input + send present",
        "evidence": { "match": true } },
      { "name": "chat_input_labeled", "passed": false, "detail": "chat input missing aria-label and placeholder",
        "evidence": { "selector": "[data-chat] input", "match": false } } ],
    "summary": { "total": 3, "passed": 2, "failed": 1 },
    "value_class": "META", "verifier_status": "FAIL", "authority": "none" }
]
```
</details>

> **Adversarial note:** if a sandbox author tried to inflate WC-4's receipt by writing `summary: {total:2, passed:2, failed:0}` while `checks[]` still show both `passed:false`, the CF Worker recomputes `{total:2, passed:0, failed:2}`, sees the mismatch, and forces `verifier_status: FAIL` with the reason appended to `failures[]`. The author cannot lie its way to PASS.

---

## 9. ApprovalItems — the human gate

Each receipt becomes one `ApprovalItem`. **Only an approved ApprovalItem authorizes a canonical change — never raw voice.** Read-only diagnostic contracts (WC-1/2/3) had no staged diff (`proposed_patch_ref: null`); their fixes are canonical changes the founder must author/approve. Patch jobs (WC-4/5/6) attached the staged diff so approval = "apply this exact diff". Every decision is `pending`.

| AP | title | proposed_patch_ref | risk_class | value_class | decision |
|---|---|---|---|---|---|
| AP-1 | Fix broken 'Apply for Program' CTA route (404) | null | canonical_change | REVENUE | pending |
| AP-2 | Point footer Cookie link to /cookie-policy | null | canonical_change | GUARD | pending |
| AP-3 | Fix Sign-in route 500 | null | canonical_change | REVENUE | pending |
| AP-4 | Update Acme Brief copy to $12,000 / 8-week | `sandbox/.../SJ-4/acme-brief-copy.diff` | canonical_change | REVENUE | pending |
| AP-5 | Render request id on trust/support views | `sandbox/.../SJ-5/request-id-display.diff` | low_risk_patch | GUARD | pending |
| AP-6 | Add aria-label/placeholder to chat input | `sandbox/.../SJ-6/chat-input-label.diff` | low_risk_patch | META | pending |

```json
[
  { "id": "AP-1", "session_id": "AS-2026-07-09-fieldaudit",
    "receipt_id": "field_audit_receipt_v1:AS-2026-07-09-fieldaudit:WC-1", "workflow_contract_id": "WC-1",
    "title": "Fix broken 'Apply for Program' CTA route (404)", "proposed_patch_ref": null,
    "risk_class": "canonical_change", "value_class": "REVENUE",
    "target": { "target_url": "{TARGET_URL}", "scope_selector": "a[data-cta='apply-for-program']" },
    "decision": "pending", "decided_by": null, "decided_at": null,
    "rationale": "Route returns 404; fix requires canonical change -> founder approval." },

  { "id": "AP-4", "session_id": "AS-2026-07-09-fieldaudit",
    "receipt_id": "field_audit_receipt_v1:AS-2026-07-09-fieldaudit:WC-4", "workflow_contract_id": "WC-4",
    "title": "Update Acme Brief copy to $12,000 / 8-week",
    "proposed_patch_ref": "sandbox/.../SJ-4/acme-brief-copy.diff",
    "risk_class": "canonical_change", "value_class": "REVENUE",
    "target": { "target_url": "{TARGET_URL}", "scope_selector": "[data-offer='acme-brief']" },
    "decision": "pending", "decided_by": null, "decided_at": null,
    "rationale": "Diff prepared in sandbox; canonical copy change needs founder approval." }
]
```

*(AP-2 "Point footer Cookie link to /cookie-policy", AP-3 "Fix Sign-in route 500", AP-5 "Render request id on trust/support views", AP-6 "Add aria-label/placeholder to chat input" follow the same shape — see the table. AP-5/AP-6 carry `low_risk_patch` but are still queued for approval, not auto-applied.)*

---

## 10. Pattern expansion — 6 spoken defects → 19 deterministic workflows

This is the fan-out that turns a point observation into **surface-wide coverage**. Each seed contract's `pattern_expansion_rule` enumerates every element matching its `scope_selector` and instantiates one contract per element. The founder pointed at *one* CTA; the compiler checks *all* of them.

| Seed | template_id | rule | expanded targets | contract ids |
|---|---|---|---|---|
| WC-1 | `cta_route_check` | fan to ALL CTAs | apply-for-program, book-demo, get-started, contact-sales | WC-1, WC-1a, WC-1b, WC-1c |
| WC-2 | `legal_footer_link_check` (+ `broken_link_scan`) | fan to ALL required legal footer links + generic broken-link scan over nav+footer | cookie, privacy, terms, `nav a[href]`, `footer a[href]` | WC-2, WC-2a, WC-2b, WC-2c *(broken_link_scan)* |
| WC-3 | `auth_entrypoint_check` | fan to ALL auth entrypoints | header login, footer login, signup, get-started CTA | WC-3, WC-3a, WC-3b |
| WC-4 | `pricing_claim_consistency_check` (+ `offer_copy_consistency_check`) | fan pricing/offer copy across ALL commercial surfaces | `/`, `/pricing`, `/partner-access` (each `[data-offer='acme-brief']`) | WC-4, WC-4a, WC-4b *(offer_copy_consistency_check)* |
| WC-5 | `request_id_visibility_check` | fan to ALL views expected to show a request id | `/support`, `/trust`, error states | WC-5, WC-5a |
| WC-6 | `web_chat_ux_check` | fan to ALL pages mounting the chat component | `/`, `/pricing`, `/support` | WC-6, WC-6a, WC-6b |

```json
[
  { "from_contract": "WC-1", "template_id": "cta_route_check", "rule": "fan to ALL CTAs",
    "expanded_targets": ["a[data-cta='apply-for-program']", "a[data-cta='book-demo']", "a[data-cta='get-started']", "a[data-cta='contact-sales']"],
    "new_contract_ids": ["WC-1", "WC-1a", "WC-1b", "WC-1c"] },
  { "from_contract": "WC-2", "template_id": "legal_footer_link_check",
    "rule": "fan to ALL required legal footer links + generic broken_link_scan over nav+footer",
    "expanded_targets": ["footer a[href*='cookie']", "footer a[href*='privacy']", "footer a[href*='terms']", "nav a[href]", "footer a[href]"],
    "new_contract_ids": ["WC-2", "WC-2a", "WC-2b", "WC-2c(broken_link_scan)"] },
  { "from_contract": "WC-3", "template_id": "auth_entrypoint_check", "rule": "fan to ALL auth entrypoints",
    "expanded_targets": ["header a[href*='login']", "footer a[href*='login']", "a[href*='signup']", "a[data-cta='get-started']"],
    "new_contract_ids": ["WC-3", "WC-3a", "WC-3b"] },
  { "from_contract": "WC-4", "template_id": "pricing_claim_consistency_check + offer_copy_consistency_check",
    "rule": "fan pricing/offer copy across ALL commercial surfaces",
    "expanded_targets": ["/ [data-offer='acme-brief']", "/pricing [data-offer='acme-brief']", "/partner-access [data-offer='acme-brief']"],
    "new_contract_ids": ["WC-4", "WC-4a", "WC-4b(offer_copy_consistency_check)"] },
  { "from_contract": "WC-5", "template_id": "request_id_visibility_check",
    "rule": "fan to ALL views expected to show a request id",
    "expanded_targets": ["/support", "/trust", "error states"], "new_contract_ids": ["WC-5", "WC-5a"] },
  { "from_contract": "WC-6", "template_id": "web_chat_ux_check", "rule": "fan to ALL pages mounting the chat component",
    "expanded_targets": ["/", "/pricing", "/support"], "new_contract_ids": ["WC-6", "WC-6a", "WC-6b"] }
]
```

### The count: 6 → 19

```
WC-1 → 4   (WC-1, WC-1a, WC-1b, WC-1c)
WC-2 → 4   (WC-2, WC-2a, WC-2b, WC-2c broken_link_scan)
WC-3 → 3   (WC-3, WC-3a, WC-3b)
WC-4 → 3   (WC-4, WC-4a, WC-4b offer_copy_consistency_check)
WC-5 → 2   (WC-5, WC-5a)
WC-6 → 3   (WC-6, WC-6a, WC-6b)
──────────────────────────────────
6 spoken defects → 19 deterministic WorkflowContracts
```

Every expanded contract inherits its seed's template `deterministic_checks`, `verifier_logic`, `promotion`, and `risk_class` — it is the *same pure predicate* re-pointed at a sibling element, so the CF Worker re-derives all 19 identically. Note the two cross-template siblings the clustering decisions in §4 predicted: **WC-2c** brings in `broken_link_scan` for a full nav+footer sweep, and **WC-4b** brings in `offer_copy_consistency_check` for the surrounding Acme Brief name/inclusions copy.

---

## 11. Chain summary (verbatim from the spine)

> 1 voice note → 1 transcript (normalized: `'$12,000'`, `'8-week'`) → 6 observations → 6 deduped clusters → 6 WorkflowContracts (first-five templates seed WC-1/3/5 (WC-2 via broken_link_scan fan-out, sequenced later); WC-4 pricing, WC-6 chat sequenced later) → 6 cat-05 sandbox jobs (3 inspect, 3 patch_diff) → 6 verification runs → 6 `field_audit_receipt_v1` (ALL `verifier_status=FAIL` as expected: surface is genuinely broken) → 6 pending ApprovalItems → pattern expansion fans each template across siblings. **No PASS self-minted; no canonical mutation; all diffs staged, none applied.**

### Invariants this run never violated

- **No PASS self-minted.** All sandbox receipts are `authority:"none"`; PASS is issuable only by the independent CF Worker after summary re-derivation + edge/secondary-account proof.
- **No canonical mutation from raw voice.** Every fix is gated behind a `pending` ApprovalItem; the three staged diffs sit at their `diff_ref` unapplied.
- **Target discipline.** Every job ran against the founder-supplied `{TARGET_URL}` only; no live surface was hardcoded or fetched.
- **Determinism.** Every check is `HTTP status | DOM/selector presence | regex | hash equality` — re-derivable by a Worker with zero trust in the author. That is what makes this a **compiler**, not a chatbot.
