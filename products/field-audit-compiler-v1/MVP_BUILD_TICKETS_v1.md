# MVP_BUILD_TICKETS_v1 — FOUNDER_FIELD_AUDIT_TO_WORKFLOW_COMPILER

Package: `noetfield:field-audit-compiler` · Spine: `_SPINE_v1.json` (v1.0.0, locked 2026-07-09)
Reads: `VOICE_TO_OBSERVATION_SCHEMA_v1.json`, `RECEIPT_SCHEMA_FIELD_AUDIT_v1.json`
Canonical E2E reused verbatim: session `AS-2026-07-09-fieldaudit`, target `{TARGET_URL}`.

> This is a **Voice-to-Workflow Compiler**, not a chatbot: founder SPEAKS defects on a real surface → Observations → IssueClusters → deterministic WorkflowContracts → SandboxJobs → independently-verifiable receipts → approval-ready patches → pattern expansion.

---

## Authority binding (applies to EVERY ticket below)

| Actor | Role in this MVP |
|---|---|
| `sina-governance-SSOT` | law / registry / locks. Runs nothing. Owns the templates registry + risk policy these tickets copy read-only. |
| **`sandbox` (this dir)** | **authority=none. All five tickets are sandbox-authoring.** Every file write stays inside `sandbox/products/field-audit-compiler-v1/`. Cannot mint PASS. |
| `noetfield-cloud-factory-infra` | verified-execution factory. The independent Cloudflare Worker verifier is the ONLY PASS issuer. Supabase is the ledger. **Out of scope for these five tickets.** |
| `cat-05-sandbox-worktree-execution` | the WATCHER slot the SandboxJob runs in (isolated worktree) — not the whole sandbox. |
| `cat-09-receipt-trust-audit-layer` | GUARD-class receipts promote here. |
| `cat-10-vertical-proof-products` | REVENUE-class receipts promote here. |

**Hard execution rule (non-negotiable in code):** All generated work goes to sandbox FIRST. NO direct deploy, merge, deletion, cron unlock, real send, or canonical-repo mutation from raw voice. SandboxJobs may only **inspect / patch-into-a-diff / test / return receipts** — they NEVER apply a diff. Jobs run ONLY against the **founder-supplied `TARGET_URL`/`target_ref`**; nothing hardcodes or fetches a live surface (no `trustfield.ca`, no production host). In tests, `{TARGET_URL}` is bound to a **sandbox-local fixture HTTP server on `127.0.0.1`** — the E2E is an illustrative worked example, never a live run. Every author-emitted `field_audit_receipt_v1` carries `authority:"none"` and `verifier_status:"UNVERIFIED"`.

---

## 1) Ordered MVP build sequence (from spine `first_build_sequence`)

| Step | What | sandbox_only | Covered by |
|---|---|:---:|---|
| 1 | Capture PWA: mic → `VoiceNote(audio_ref)` + `AuditSession(target_url/target_ref)` | ✅ | *fixtures only in MVP* (T1) |
| 2 | Transcriber → `Transcript(text_raw, text_normalized, normalization_ops, optional translation)` | ✅ | T1 |
| 3 | Observation extractor → `Observation[]` (`raw_span`, `target_hint`, `defect_kind`, `severity_guess`) | ✅ | **T1** |
| 4 | Clusterer → `IssueCluster[]` (group + dedup by `defect_kind` + resolved target scope) | ✅ | T2 |
| 5 | Template selector → pick `templates[].id` per cluster (first_five first) | ✅ | T2 |
| 6 | Contract generator → `WorkflowContract[]` (target+scope, `deterministic_checks`, `promotion`, `risk_class`) | ✅ | T3 |
| 7 | Sandbox runner in cat-05 watcher → `SandboxJob[]` (`inspect`\|`patch_diff`\|`test`); stage diffs, never apply | ✅ | T4 |
| 8 | Verifier: sandbox self-writes `field_audit_receipt_v1` (**UNVERIFIED**); independent CF Worker recomputes summary + edge/secondary-account proof to issue PASS/FAIL | ⛔ (Worker side) | T4 (sandbox self-write half only) · **CF Worker = factory, out of these 5 tickets** |
| 9 | Approval queue → `ApprovalItem[]` from receipts + staged diffs | ✅ | *post-MVP (T3 emits approval_required flags that seed it)* |
| 10 | Pattern expander → fan each contract across sibling routes/components | ✅ | *post-MVP (T3 records `pattern_expansion_rule`; expander deferred)* |

**MVP cut line:** Tickets T1–T5 deliver steps 2→8-sandbox-half for a single template (`broken_link_scan`) end-to-end. The CF Worker PASS issuer (step 8, factory), the approval queue UI (step 9), and the pattern expander (step 10) are explicitly deferred; T3 already emits the `approval_required` and `pattern_expansion_rule` fields that seed them.

### Stack + layout (all inside the product dir)
Language: **TypeScript / Node** (matches the CF Worker's JS so the verifier can re-derive with the same selectors/regex/hash logic). Pure functions, no LLM in stages 4–8.

```
sandbox/products/field-audit-compiler-v1/
  src/
    stage1/  validate.ts            # validates against VOICE_TO_OBSERVATION_SCHEMA_v1.json
             extract_observations.ts# Transcript -> Observation[]
    cluster/ cluster.ts             # Observation[] -> IssueCluster[]
             select_template.ts     # defect_kind -> templates[].id
    compile/ generate_contract.ts   # IssueCluster -> WorkflowContract
    templates/registry.json         # read-only mirror of spine templates[] (SSOT-locked)
    runner/  sandbox_job.ts         # cat-05 runner: inspect|patch_diff|test (never apply)
             checks/broken_link_scan.ts
    verify/  selfwrite_receipt.ts   # emits field_audit_receipt_v1 (UNVERIFIED, authority none)
             recompute_summary.ts   # shared with CF Worker doctrine: total/passed/failed from checks[]
  fixtures/
    AS-2026-07-09-fieldaudit/       # the canonical E2E as replayable fixtures
    target-surface/                 # static HTML served on 127.0.0.1 as {TARGET_URL} in tests
  tests/
```

---

## 2) The first five build tickets

Every ticket: **Authority = sandbox-authoring (authority=none, writes confined to `sandbox/products/field-audit-compiler-v1/`, cannot mint PASS).**

---

### TICKET 1 — Stand up the Observation extractor + stage-1 schema validator

**Goal.** Turn a normalized `Transcript` into the exact `Observation[]` the compiler routes on, and enforce `VOICE_TO_OBSERVATION_SCHEMA_v1.json` on every stage-1 object. Reproduce the canonical chain: `TR-1` → `OB-1..OB-6` verbatim.

**Scope (creates).**
- `src/stage1/validate.ts` — validates `AuditSession`, `VoiceNote`, `Transcript`, `Observation` against the stage-1 schema (`additionalProperties:false`, id patterns `AS-/VN-/TR-/OB-*`, the `defect_kind` closed enum, the `anyOf` target_url/target_ref rule).
- `src/stage1/extract_observations.ts` — pure `Transcript → Observation[]`; each Observation carries `raw_span` (exact substring of `text_normalized`/`text_translated`), `target_hint`, `severity_guess`, `defect_kind`, `confidence`, `needs_translation`, and `surface_ref` as `"unresolved:<hint>"` (NEVER a hardcoded live URL at compile time).
- `fixtures/AS-2026-07-09-fieldaudit/` — `session.json`, `voicenote.json` (`audio_ref` = sandbox-local blob key, never external URL), `transcript.json` (with the spine's `normalization_ops`: `twelve thousand`→`10000`, `twelve thousand dollar`→`$12,000`, `six week`→`8-week`), and golden `observations.json` = `OB-1..OB-6`.
- `tests/stage1.test.ts`.

**Objects produced:** `AuditSession`, `VoiceNote`, `Transcript`, `Observation`.

**Acceptance criteria.**
1. Extractor run on fixture `TR-1` returns exactly six Observations equal to the golden `OB-1..OB-6`, including the defect_kind mapping: `apply for pilot link is broken`→`cta_route`, `cookie link goes nowhere`→`legal_footer_link`, `sign-in is broken`→`auth_entrypoint`, `trust brief $12,000 8-week package copy needs update`→`pricing_claim`, `request ids are not visible`→`request_id_visibility`, `web chat ui is bad`→`web_chat_ux`.
2. Every emitted Observation passes `validate.ts`; `surface_ref` values are all `unresolved:*`.
3. `validate.ts` rejects any stage-1 object with an unknown key, a bad id pattern, a `defect_kind` outside the enum, or an `AuditSession` missing both `target_url` and `target_ref`.
4. **Red-capable test that MUST fire:** a `defect_kind_mapping` case asserts `raw_span:"sign-in is broken"` → `auth_entrypoint`. Seed the test suite with a deliberately wrong mapping table (`sign-in`→`broken_link`) and confirm the test goes RED; then ship the correct table and confirm GREEN. A second negative case feeds an `Observation` missing the required `needs_translation` field and asserts `validate.ts` returns invalid — if the validator accepts it, the test fires RED.

**Dependencies.** None (T1 is the root). Step-1 capture PWA is stubbed by fixtures for MVP.

**Out of scope.** Live mic capture / PWA UI; real ASR; translation of non-English audio (schema supports it, extractor only needs the `needs_translation` flag path exercised via a fixture); any clustering or template logic.

---

### TICKET 2 — Clusterer + deterministic Template selector

**Goal.** Collapse `Observation[]` into deduped `IssueCluster[]`, then route each cluster's `defect_kind` 1:1 to a `templates[].id`, first-five first.

**Scope (creates).**
- `src/cluster/cluster.ts` — `Observation[] → IssueCluster[]`: group by (`defect_kind` + resolved target scope), set `label`, `target_refs`, `severity` = **max** of member severities, and `dedup_note`. Reproduces the canonical `IC-1..IC-6`.
- `src/cluster/select_template.ts` — pure map `defect_kind → templates[].id`: `broken_link→broken_link_scan`, `cta_route→cta_route_check`, `legal_footer_link→legal_footer_link_check`, `auth_entrypoint→auth_entrypoint_check`, `offer_copy→offer_copy_consistency_check`, `pricing_claim→pricing_claim_consistency_check`, `request_id_visibility→request_id_visibility_check`, `web_chat_ux→web_chat_ux_check`, `mobile_responsive→mobile_responsive_smoke_check`, `route_health→route_health_check`. `other` → no template (flagged un-routable). Honors `first_five_template_ids` = `[route_health_check, broken_link_scan, cta_route_check, auth_entrypoint_check, request_id_visibility_check]` for scheduling priority.
- `src/templates/registry.json` — read-only mirror of the spine `templates[]` (SSOT-locked; loaded, never mutated).
- `tests/cluster.test.ts`, `tests/select_template.test.ts`.

**Objects produced:** `IssueCluster`. **Consumes:** `Observation[]`.

**Acceptance criteria.**
1. Clustering the golden `OB-1..OB-6` yields exactly `IC-1..IC-6` with matching `defect_kind`, `label`, `target_refs`, and `severity` (e.g. `IC-1` blocker, `IC-4` high). `IC-2` groups under `legal_footer_link` (more specific than generic `broken_link`), with the spine's `dedup_note`.
2. `select_template` returns the exact template ids above for all ten `defect_kind` values; the five first-five ids are marked priority.
3. Registry load fails closed if `registry.json` diverges from the ten spine template ids (drift guard).
4. **Red-capable test that MUST fire:** a dedup case feeds TWO observations with identical `defect_kind:"legal_footer_link"` + same `target_refs` and asserts they collapse into ONE `IssueCluster`. Seed the clusterer with a bug that emits one cluster per observation and confirm RED (2 ≠ 1); fix and confirm GREEN. A second case asserts `severity` = max: two members `{low, blocker}` must yield `blocker` — a `first()`-instead-of-`max()` bug fires RED.

**Dependencies.** T1 (`Observation[]` + validator).

**Out of scope.** Contract generation; running checks; the sibling `offer_copy_consistency_check` spawn (spine notes it; deferred to expander).

---

### TICKET 3 — Contract generator (the compile step)

**Goal.** Emit one deterministic `WorkflowContract` per `IssueCluster` — the pure, no-LLM, CF-re-derivable contract that makes this a compiler. Reproduce canonical `WC-1..WC-6`, with `broken_link_scan` wired for T4/T5.

**Scope (creates).**
- `src/compile/generate_contract.ts` — `IssueCluster + template → WorkflowContract`: fills `template_id`, `target:{target_url|target_ref, scope_selector}`, `params`, `deterministic_checks` (instantiated from the template's `[{name, logic, pass_condition}]`), `expected_outputs`, `verifier_logic`, `pattern_expansion_rule`, `promotion:{factory_category, value_class}`, `risk_class`, `approval_required`.
- Risk policy (copied read-only from SSOT): `read_only` → `approval_required:false`; `low_risk_patch`/`canonical_change` → `approval_required:true`. `target_url` is passed through as `{TARGET_URL}` (founder-supplied placeholder) — never resolved to a live host here.
- `tests/generate_contract.test.ts`.

**Objects produced:** `WorkflowContract`. **Consumes:** `IssueCluster`, `templates/registry.json`.

**Acceptance criteria.**
1. Generating from `IC-1..IC-6` yields `WC-1..WC-6` matching the spine: `WC-1` `cta_route_check` REVENUE→CAT-10 `read_only` `approval_required:false`; `WC-2` `legal_footer_link_check` GUARD→CAT-09 `read_only false`; `WC-3` `auth_entrypoint_check` REVENUE→CAT-10; `WC-4` `pricing_claim_consistency_check` REVENUE `canonical_change` `approval_required:true`; `WC-5` `request_id_visibility_check` GUARD `low_risk_patch true`; `WC-6` `web_chat_ux_check` META `low_risk_patch true`.
2. A `broken_link_scan` contract generated for a footer/nav scope (`scope_selector:"a[href]"`, `ignore:["mailto:","tel:"]`) carries the template's single check `href_resolves` with `pass_condition` `status in [200,301,302,308] AND href not in ['','#','javascript:void(0)']`, `promotion:{CAT-09-RECEIPT-TRUST-AUDIT-LAYER, GUARD}`, `risk_class:read_only`. This is the contract T4/T5 execute.
3. `deterministic_checks` are copied faithfully from the template (no free-text, no LLM); `verifier_logic` describes CF re-derivation (refetch/re-select/re-regex/re-hash + recompute summary).
4. **Red-capable test that MUST fire:** an invariant test asserts `risk_class:"canonical_change" ⇒ approval_required===true`. Seed the generator with a bug that emits `WC-4` as `approval_required:false` and confirm RED; fix and confirm GREEN. A second case asserts a `read_only` contract never sets `approval_required:true`.

**Dependencies.** T1, T2.

**Out of scope.** Executing any check; the pattern expander (records `pattern_expansion_rule` string only); building the `ApprovalItem` objects (they consume these flags later).

---

### TICKET 4 — cat-05 sandbox runner + UNVERIFIED receipt self-write

**Goal.** Stand up the bounded `SandboxJob` runner in the cat-05 watcher shape (`inspect`|`patch_diff`|`test`, authority=none, never applies a diff) and the `VerificationRun` self-write path that emits a `field_audit_receipt_v1` at `verifier_status:"UNVERIFIED"`. No live check logic yet — a stub check proves the harness, authority walls, and receipt shape.

**Scope (creates).**
- `src/runner/sandbox_job.ts` — executes a `WorkflowContract` as a `SandboxJob`: `category_id:"CAT-05-SANDBOX-WORKTREE-EXECUTION"`, `authority:"none"`, bounded `job_kind`. Writes `output_ref` (sandbox-local bundle) and, for `patch_diff`, a `diff_ref` file — **staged, never applied**. Refuses (throws) on any write outside `sandbox/products/field-audit-compiler-v1/`, any network target other than the contract's founder-supplied `target`, and any attempt to apply a diff/deploy/send.
- `src/verify/recompute_summary.ts` — shared summary derivation (`total=len(checks)`, `passed=count(passed==true)`, `failed=count(passed==false)`), the exact CF-Worker doctrine.
- `src/verify/selfwrite_receipt.ts` — `VerificationRun` (sandbox self-write) → `field_audit_receipt_v1` with `verifier_runtime:"sandbox_selfwrite"`, `verifier_status:"UNVERIFIED"`, `authority:"none"`, `category_id` from `promotion`, `checks[]` carrying `evidence` (http_status/hash/selector — proof, not prose), and `summary` computed by `recompute_summary`.
- `tests/runner.test.ts`, `tests/receipt_selfwrite.test.ts`.

**Objects produced:** `SandboxJob`, `VerificationRun`, `Receipt (field_audit_receipt_v1, UNVERIFIED)`.

**Acceptance criteria.**
1. A `patch_diff` job (e.g. the WC-4 shape) writes a `diff_ref` file under the product dir and leaves every other path untouched; snapshot the fixture surface + repo before/after and assert byte-identical.
2. Self-written receipts always carry `verifier_status:"UNVERIFIED"` and `authority:"none"`; the module has **no code path** that can set `PASS`. Receipt validates against `RECEIPT_SCHEMA_FIELD_AUDIT_v1.json` (required keys, `schema:"field_audit_receipt_v1"`, `category_id` enum, `checks[].evidence` shape).
3. `summary` on the emitted receipt equals `recompute_summary(checks)` — author never hand-writes the rollup.
4. **Red-capable test that MUST fire (two guards):**
   (a) *Authority wall:* invoke the runner with a job that tries to apply its diff / write to `../` / hit a non-target host; assert it throws and nothing outside the product dir changed. Seed a bug where the runner applies the diff and confirm the filesystem assertion goes RED.
   (b) *No self-mint:* force `selfwrite_receipt` to attempt `verifier_status:"PASS"`; assert it is rejected/coerced to `UNVERIFIED`. If a `PASS` self-write ever escapes, the test fires RED. Also tamper `summary.passed` to a wrong value and assert `recompute_summary` mismatch is detected (mirrors the CF Worker's FAIL-on-mismatch doctrine).

**Dependencies.** T3 (a `WorkflowContract` to run). Uses a stub check in this ticket; real `broken_link_scan` logic lands in T5.

**Out of scope.** The independent Cloudflare Worker PASS issuer (factory, step-8 second half — NOT built here); Supabase ledger writes; approval queue.

---

### TICKET 5 — First end-to-end SandboxJob: `broken_link_scan` → `field_audit_receipt_v1`

**Goal.** Run the full chain for one contract — `broken_link_scan` — against the founder-supplied `TARGET_URL` (bound to a sandbox-local fixture server in tests), emitting a schema-valid `field_audit_receipt_v1` (`UNVERIFIED`) whose failing checks reflect a genuinely broken surface, exactly like the canonical E2E (`ALL verifier_status=FAIL as expected: surface is genuinely broken`).

**Scope (creates).**
- `src/runner/checks/broken_link_scan.ts` — implements the template's `href_resolves` check: enumerate `a[href]` in fetched HTML (ignoring `mailto:`/`tel:`), HTTP GET/HEAD each resolved href against the job's `target`, per-link `{href, http_status, passed}` with `passed = status in [200,301,302,308] AND href not in ['','#','javascript:void(0)']`. Pattern-expansion fan-out over all nav+footer+in-body links (one check per unique href). Reads `target` from the contract only — no hardcoded host.
- `fixtures/target-surface/` — static HTML served on `127.0.0.1` as `{TARGET_URL}`: contains one healthy link (200), one footer Cookie link with `href="#"` (unresolved), one `/apply-for-program` returning 404 — reproducing the E2E's real defects without touching any live surface.
- `tests/e2e_broken_link_scan.test.ts` — drives T1→T5 end-to-end for the `broken_link_scan` contract.

**Objects exercised:** `WorkflowContract` → `SandboxJob(inspect)` → `VerificationRun` → `Receipt(field_audit_receipt_v1, UNVERIFIED)` for session `AS-2026-07-09-fieldaudit`.

**Acceptance criteria.**
1. Running the `broken_link_scan` contract against the fixture server emits one `field_audit_receipt_v1` with: `schema:"field_audit_receipt_v1"`, `session_id:"AS-2026-07-09-fieldaudit"`, `category_id:"CAT-09-RECEIPT-TRUST-AUDIT-LAYER"`, `value_class:"GUARD"`, `verifier_status:"UNVERIFIED"`, `authority:"none"`, and one `checks[]` entry per unique href.
2. The healthy link check has `passed:true` (evidence `http_status:200`); the `href="#"` Cookie link and the 404 `/apply-for-program` links have `passed:false` with evidence (`url`, `http_status`/`match:false`) — proof, not prose.
3. `summary` = `recompute_summary(checks)` and `total === checks.length === passed + failed`. Receipt validates against `RECEIPT_SCHEMA_FIELD_AUDIT_v1.json`.
4. No request leaves `127.0.0.1`; assert no fetch to any non-`target` host. Diff/deploy paths remain untouched (job_kind is `inspect`).
5. **Red-capable test that MUST fire (two guards):**
   (a) *False-negative guard:* assert the `href="#"` and 404 links report `passed:false`. Seed a bug where the check treats `#`/404 as passing and confirm RED; fix and confirm GREEN.
   (b) *Summary-integrity guard (CF Worker doctrine):* independently recompute `{total,passed,failed}` from `checks[]` and compare to the emitted `summary`; then mutate one `checks[].passed` boolean WITHOUT updating `summary` and assert the recompute detects the mismatch (the exact condition that makes the real CF Worker set `FAIL`). If the mismatch is not caught, the test fires RED.

**Dependencies.** T1, T2, T3, T4.

**Out of scope.** CF Worker adjudication to PASS (factory); other templates (`cta_route_check`, `auth_entrypoint_check`, etc. — sequenced after this proof); pattern expander enqueue; `ApprovalItem` creation. This ticket proves ONE template end-to-end; the remaining first-five templates reuse the same harness in follow-on tickets.

---

## 3) Definition-of-Done gates (all five tickets)

- [ ] Every write landed inside `sandbox/products/field-audit-compiler-v1/`; nothing else on disk changed.
- [ ] No receipt carries `verifier_status:"PASS"` or `authority` other than `"none"`; no code path can self-mint PASS.
- [ ] No live/production host is hardcoded or fetched; all runs target the founder-supplied ref (fixture `127.0.0.1` in tests).
- [ ] No diff applied, no deploy, no send, no cron unlock, no canonical mutation triggered from voice.
- [ ] Each ticket's named red-capable test has been observed RED against a seeded bug, then GREEN after the fix (not a tautology).
- [ ] Object names, field names, and template ids match `_SPINE_v1.json` / the two schema files exactly; the canonical E2E (`AS-2026-07-09-fieldaudit`, `{TARGET_URL}`, `OB-1..OB-6`, `WC-1..WC-6`) is reproduced, not re-invented.
