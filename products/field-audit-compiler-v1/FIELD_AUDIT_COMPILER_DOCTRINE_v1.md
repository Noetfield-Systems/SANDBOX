# FIELD_AUDIT_COMPILER_DOCTRINE_v1

**The constitution of the FOUNDER_FIELD_AUDIT_TO_WORKFLOW_COMPILER.**

- Package: `FOUNDER_FIELD_AUDIT_TO_WORKFLOW_COMPILER_v1`
- Binds to: `_SPINE_v1.json` (`noetfield:field-audit-compiler:spine:v1`), `VOICE_TO_OBSERVATION_SCHEMA_v1.json`, `RECEIPT_SCHEMA_FIELD_AUDIT_v1.json`
- Authority of this file: **doctrine only.** It states law the implementation must obey. It runs nothing and mints nothing.
- Locked: 2026-07-09

This document is normative. Where a downstream file, prompt, or runner disagrees with the object names, field names, template ids, or the canonical E2E example in the three spine files, **the spine files win and this doctrine points at them** — it never redefines them.

---

## 0. One-liner (from the spine, verbatim)

> A deterministic Voice-to-Workflow Compiler: founder SPEAKS defects on a real surface -> observations -> issue clusters -> deterministic WorkflowContracts -> sandbox jobs -> independently verified receipts -> approval-ready patches -> pattern expansion. **NOT a chatbot or prompt generator.**

---

## 1. Core principle — this is a COMPILER, not a chatbot

The system is a **Voice-to-Deterministic-Workflow Compiler**. Spoken defect reports are the *source language*; deterministic, no-LLM `WorkflowContract` objects that a Cloudflare Worker can independently re-derive are the *target language*. Everything in between is a compilation pass, not a conversation.

Three consequences are load-bearing and non-negotiable:

1. **The output is a contract, not a prompt.** The unit the compiler emits (`WorkflowContract`) carries `deterministic_checks[]` whose `logic` is a PURE predicate — HTTP status, DOM/selector presence, regex match, or hash equality — with an explicit `pass_condition`. No step of an emitted contract asks any model to "judge," "review," or "decide." If a check cannot be expressed as a pure predicate, it is not a check; it is a non-goal (see §10).

2. **Understanding is proven downstream by re-derivation, never asserted upstream by fluency.** An LLM may be used in the *authoring* passes (transcription slicing, classification, clustering) but its output is always a *heuristic proposal* — `Observation.severity_guess`, `Observation.confidence`, `IssueCluster.dedup_note`. The truth of a claim is established only when the independent verifier re-runs the deterministic logic and the numbers match. Fluent-sounding intermediate text has zero authority.

3. **The compiler is deterministic where it counts.** The `Transcript` normalization is a replayable, ordered list of pure transforms (`normalization_ops[]`); the `deterministic_checks[]` are pure; the `verifier_logic` recomputes `summary` from `checks[]`. A chatbot would re-improvise each time. A compiler produces the same target from the same source, and a third party can rebuild it.

A one-line litmus test for any proposed feature: **"Can a Cloudflare Worker with no trust in the author re-derive this result from stored evidence?"** If no, it does not belong in the compiled output.

---

## 2. Design intent — what the founder must NEVER have to do by hand

The founder audits by **checking one page and speaking the defects out loud.** One `AuditSession` against one founder-supplied surface, a mic, a few sentences. The system does the expansion: one spoken pass becomes **10–20 deterministic workflows** fanned across every sibling route and component.

The design exists to abolish three manual burdens. The compiler is a failure if the founder ever has to do any of them:

- **No hand-converting notes into prompts.** The founder speaks "Apply for Program link is broken"; the compiler slices it into an `Observation` (`defect_kind: cta_route`), routes it to a template (`cta_route_check`), and emits the `WorkflowContract`. The founder never writes a prompt, never fills a form, never picks a template.
- **No hand-verifying that the system understood.** The founder does not read back a paraphrase and click "yes that's right." Understanding is demonstrated by the `field_audit_receipt_v1` the independent verifier adjudicates — a machine artifact grounded in stored evidence (`http_status`, `dom_sha256`, regex `match`), not a reassurance.
- **No hand-inspecting similar routes.** The founder mentions *one* broken CTA; the `pattern_expansion_rule` fans the check across `a[data-cta='apply-for-program']`, `a[data-cta='book-demo']`, `a[data-cta='get-started']`, `a[data-cta='contact-sales']` — every element matching the scope selector. The founder never has to remember or manually enumerate the other CTAs, footer links, or auth entrypoints.

The founder's whole job is: **pick a surface, speak, then approve or reject a queue of evidence-backed patches.** Everything between the speaking and the approving is the compiler's job.

---

## 3. Layer & authority model (confirmed — obey exactly)

This mirrors `_SPINE_v1.authority_model` and the package authority model. It is the constitution's separation of powers.

| Layer | Role | Authority | Hard rule |
|---|---|---|---|
| **sina-governance-SSOT** | Law / registry / locks. Owns the templates registry and risk policy. | Governs. **Runs nothing.** | The 10 `templates[]` and the risk policy this compiler obeys live here. This doctrine may not invent templates or risk classes outside it. |
| **/sandbox** (this product dir) | Authoring & R&D bench. | **authority = none. CANNOT mint PASS.** | Every write stays inside `sandbox/products/field-audit-compiler-v1/`. Sandbox jobs may only **inspect / patch-into-a-diff / test / return receipts.** |
| **noetfield-cloud-factory-infra** | Verified-execution factory. Thin orchestrators. | The **independent Cloudflare Worker verifier is the ONLY PASS issuer.** Supabase is the ledger. | Orchestrators are thin: they queue work and record receipts; they do not judge. |
| **cat-05-sandbox-worktree-execution** | A factory **WATCHER slot** that runs one `SandboxJob` in an isolated worktree. | authority = none. | It is *a* category (`CAT-05-SANDBOX-WORKTREE-EXECUTION`), **not the whole sandbox.** `SandboxJob.category_id` is const-pinned to it. |
| **cat-09-receipt-trust-audit-layer** | Trust / receipt center of gravity. | Owns adjudicated GUARD-class receipts. | GUARD-class receipts (broken links, legal footer, request-id visibility, route health, web-chat UX) promote here. |
| **cat-10-vertical-proof-products** | Vertical-proof / revenue. | Owns adjudicated REVENUE-class receipts. | REVENUE-class receipts (CTAs, auth, pricing/offer copy) promote here. |

### PASS issuance (the single most important rule)

`verifier_status = PASS` is issuable **ONLY** by the independent CF Worker, and **only after** it (a) recomputes `summary` from `checks[]` — `total = len(checks)`, `passed = count(passed==true)`, `failed = count(passed==false)` — and confirms it matches, and (b) confirms edge-execution + secondary-CF-account proof. Any mismatch → `FAIL`.

**Author-emitted sandbox receipts are ALWAYS `authority: "none"` and `verifier_status: "UNVERIFIED"`.** The sandbox can never self-mint PASS. `UNVERIFIED` is the *only* legal `verifier_status` for a sandbox self-write. (See `RECEIPT_SCHEMA_FIELD_AUDIT_v1` verifier doctrine — identical to `category_cloud_task_receipt_v1`.)

---

## 4. The 14-step required pipeline

Every audit MUST traverse these 14 steps in order. Each step names the spine object it produces and the layer it runs in. Steps 1–7 and 12–13 are sandbox-only (authority=none); step 10 (verify) is the only step where the independent CF Worker acts; step 14 (promotion) lands in a factory category.

| # | Step | Produces (spine object) | Layer / authority | What it does |
|---|---|---|---|---|
| 1 | **capture** | `AuditSession`, `VoiceNote` | sandbox (none) | Mic PWA records a spoken utterance to a **sandbox-local** `audio_ref` (never an external URL) inside an `AuditSession` bound to the founder-supplied `target_url` **or** `target_ref` (exactly one required). |
| 2 | **normalize / translate** | `Transcript` | sandbox (none) | Verbatim ASR → `text_raw`; then an **ordered, replayable** `normalization_ops[]` (number_word_expand, currency_normalize, hyphen_join, lowercase, whitespace_canon, punctuation_canon, translate) → `text_normalized`. If `source_lang != en`, `translated = true` and `text_translated` carries the English working text. |
| 3 | **observation** | `Observation[]` | sandbox (none) | Slice each atomic asserted defect out of the transcript. Each carries a `raw_span` (exact substring — the provenance anchor), a `target_hint` (founder's words), and `needs_translation`. |
| 4 | **classify** | `Observation.defect_kind` + `severity_guess` + `confidence` | sandbox (none) | Tag each observation with a `defect_kind` from the closed enum. `defect_kind` maps **1:1** to a `template_id`. `severity_guess`/`confidence` are heuristic, not verified. |
| 5 | **cluster / dedupe** | `IssueCluster[]` | sandbox (none) | Group observations sharing `defect_kind` + resolved target scope into one cluster each; `dedup_note` records why merged/kept-separate; `severity = max` of members; `target_refs[]` are the resolved surface pointers. |
| 6 | **template-select** | `WorkflowContract.template_id` | sandbox (none) | Deterministic routing `defect_kind → templates[].id`. **First-five templates first** (see §6). No free-form choice. |
| 7 | **contract-gen** | `WorkflowContract[]` | sandbox (none) | **The compile step.** Emit the deterministic contract: `target{target_url\|target_ref, scope_selector}`, `params`, `deterministic_checks[]`, `expected_outputs`, `verifier_logic`, `pattern_expansion_rule`, `promotion{factory_category,value_class}`, `risk_class`, `approval_required`. |
| 8 | **sandbox-job** | `SandboxJob[]` | cat-05 watcher (none) | Instantiate the contract as a bounded job. `job_kind ∈ {inspect, patch_diff, test}`. `patch_diff` writes a **staged diff** to `diff_ref` — **never applied.** `category_id` const `CAT-05-SANDBOX-WORKTREE-EXECUTION`. |
| 9 | **deterministic-run** | `SandboxJob` outputs + `VerificationRun` (self-write) | cat-05 watcher (none) | Run the pure `deterministic_checks[]` against the founder-supplied target ONLY. Sandbox self-writes a `field_audit_receipt_v1` with `verifier_status: UNVERIFIED`, `authority: none`. |
| 10 | **verify** | `VerificationRun` (`verifier_runtime: cloudflare_worker`) | **CF Worker (ONLY PASS issuer)** | Independent Worker refetches/re-selects/re-regexes/re-hashes, **recomputes `summary` from `checks[]`**, checks edge + secondary-CF-account proof, and sets `verifier_status ∈ {PASS, FAIL, BLOCKED}`. FAIL on any mismatch or category/schema mismatch. |
| 11 | **receipt** | `Receipt` (`field_audit_receipt_v1`) | ledger (Supabase) | The adjudicated receipt is the durable, re-derivable artifact. `checks[].evidence` carries stored proof (http_status, body/dom sha256, artifact_path), **not prose.** |
| 12 | **pattern-expand** | expanded `WorkflowContract[]` | sandbox (none) | Apply each contract's `pattern_expansion_rule`: enumerate every element matching `scope_selector` and instantiate one contract/check per element. One spoken defect → surface-wide coverage. Expanded contracts re-enter at step 8. |
| 13 | **approval-queue** | `ApprovalItem[]` | sandbox (none) | Turn each receipt (+ staged `diff_ref`) into an approval-ready item. `decision: pending`. **Only an approved `ApprovalItem` authorizes a canonical change — never raw voice.** |
| 14 | **promotion** | promoted `Receipt` in a factory category | cat-09 / cat-10 | A PASS (or explicitly-scoped low-risk) receipt promotes to its `promotion.factory_category`: GUARD/receipt-trust → **CAT-09**, REVENUE/vertical-proof → **CAT-10**. |

> Note on build order: `_SPINE_v1.first_build_sequence[]` lists a 10-step **implementation** sequence (capture → … → pattern-expander). This 14-step pipeline is the **doctrinal required traversal** of every audit and simply names the verify/receipt/promotion boundaries the build sequence folds into its steps 8–10. They do not conflict; the 14-step order is authoritative for what every session must pass through.

---

## 5. Execution rule (sandbox-first; nothing irreversible from raw voice)

Restated from `_SPINE_v1.authority_model.execution_rule` and binding on every runner:

- **All generated work goes to sandbox FIRST.**
- **From raw voice, NO:** direct deploy, merge, deletion, cron unlock, real send, or canonical-repo mutation. Not one of these may be triggered by an utterance.
- **Sandbox jobs may only:** inspect / patch-into-a-diff / test / return receipts. They **stage** diffs (`SandboxJob.diff_ref`); they never apply them.
- **Canonical changes require an `ApprovalItem`** with `decision: approved`, **or** an explicitly-scoped low-risk rule from the SSOT risk policy. There is no third path.
- **Target binding:** jobs run **only** against the founder-supplied `target_url` / `target_ref` on the `AuditSession`. The compiler **never hardcodes or fetches a live surface.** The canonical E2E's `{TARGET_URL}` is an *illustrative placeholder*, not a live run; `surface_ref`/`Observation.surface_ref` may be `unresolved:<hint>` at compile time but is **never** a hardcoded production URL.
- **`risk_class` gates `approval_required`:** `read_only` never mutates and may set `approval_required: false`; `low_risk_patch` and `canonical_change` are queued for approval; `canonical_change` **always** needs an approved item. (In the canonical E2E, even the two `low_risk_patch` items — WC-5, WC-6 — are queued `pending`, not auto-applied.)

---

## 6. Determinism guarantees

1. **No-LLM runners.** `SandboxJob` execution and the CF Worker verifier run **pure** logic only: HTTP GET/HEAD status, DOM/selector presence, regex match, hash equality. No model is in the runtime path of a check. An LLM may propose observations/clusters upstream; it may never *decide a check's boolean*.

2. **The verifier re-derives; it does not trust.** The Worker ignores the author-claimed `summary` and **recomputes it from `checks[]`**. `total` MUST equal `passed + failed` and equal `checks.length`; any mismatch → `verifier_status: FAIL`. This is the exact `cat-09-receipt-trust-audit-layer` doctrine and the shipped `category_cloud_task_receipt_v1` shape.

3. **Replayable normalization.** `Transcript.normalization_ops[]` is an ordered list of pure `{op, from, to}` transforms, so `text_raw → text_normalized` is auditable and reproducible (e.g. `twelve thousand → 10000 → $12,000`, `six week → 8-week`).

4. **Evidence, not prose.** Every check stores machine-checkable proof in `checks[].evidence` (`url`, `http_status`, `selector`, `regex`, `match`, `body_sha256`, `dom_sha256`, `artifact_path`, `expected`, `actual`). A human or a second Worker can rebuild the boolean from the evidence alone.

5. **Category & schema binding.** The verifier binds to an `EXPECTED_CATEGORY_ID` and the `field_audit_receipt_v1` discriminator; a mismatched `category_id` or `schema` → `FAIL`, exactly as the factory verifiers do.

6. **PASS requires independent proof.** Beyond summary re-derivation, PASS requires edge-execution + secondary-CF-account proof. Sandbox self-writes stay `UNVERIFIED`.

### The 10 templates (registry-owned; `defect_kind` → `template_id` 1:1)

`broken_link_scan` (GUARD/CAT-09) · `cta_route_check` (REVENUE/CAT-10) · `legal_footer_link_check` (GUARD/CAT-09) · `auth_entrypoint_check` (REVENUE/CAT-10) · `offer_copy_consistency_check` (REVENUE/CAT-10) · `pricing_claim_consistency_check` (REVENUE/CAT-10) · `request_id_visibility_check` (GUARD/CAT-09) · `web_chat_ux_check` (META/CAT-09) · `mobile_responsive_smoke_check` (GUARD/CAT-10) · `route_health_check` (GUARD/CAT-09).

**First-five (build + run first):** `route_health_check`, `broken_link_scan`, `cta_route_check`, `auth_entrypoint_check`, `request_id_visibility_check` — all pure HTTP + static-DOM/regex a CF Worker re-derives today (route_health mirrors the shipped CAT-10 `http_200` poller). `offer_copy` / `pricing_claim` need a supplied canonical source; `web_chat_ux` / `mobile_responsive` need rendering — **sequenced after the first five.**

---

## 7. Canonical E2E example (the one chain every file reuses)

The doctrine is bound to the **single canonical worked chain** in `_SPINE_v1.e2e_example`. Do not invent a divergent example. In brief (verbatim ids and values):

**Founder voice note:** *"Apply for Program link is broken. Cookie link goes nowhere. Sign-in is broken. Acme Brief twelve-thousand-dollar six-week package copy needs update. Request IDs are not visible. Web chat UI is bad."*

- Session `AS-2026-07-09-fieldaudit`, `surface_kind: website`, `target_url: {TARGET_URL}` (placeholder — not live).
- 1 `VoiceNote` (`VN-1`) → 1 `Transcript` (`TR-1`, normalized `$12,000` / `8-week`) → 6 `Observation`s (`OB-1..OB-6`) → 6 `IssueCluster`s (`IC-1..IC-6`) → 6 `WorkflowContract`s (`WC-1..WC-6`) → 6 cat-05 `SandboxJob`s (3 `inspect`, 3 `patch_diff`) → 6 `VerificationRun`s → 6 `field_audit_receipt_v1` → 6 pending `ApprovalItem`s (`AP-1..AP-6`) → pattern expansion fans each template across siblings.

Mapping (defect → cluster → template → value/risk):

| OB | defect_kind | Cluster | Contract | template_id | value_class | risk_class |
|---|---|---|---|---|---|---|
| OB-1 | cta_route | IC-1 | WC-1 | `cta_route_check` | REVENUE | read_only |
| OB-2 | legal_footer_link | IC-2 | WC-2 | `legal_footer_link_check` | GUARD | read_only |
| OB-3 | auth_entrypoint | IC-3 | WC-3 | `auth_entrypoint_check` | REVENUE | read_only |
| OB-4 | pricing_claim | IC-4 | WC-4 | `pricing_claim_consistency_check` | REVENUE | canonical_change |
| OB-5 | request_id_visibility | IC-5 | WC-5 | `request_id_visibility_check` | GUARD | low_risk_patch |
| OB-6 | web_chat_ux | IC-6 | WC-6 | `web_chat_ux_check` | META | low_risk_patch |

**Outcome (from the spine `chain_summary`):** ALL six receipts are `verifier_status: FAIL` — as expected, because the surface is genuinely broken (CTA 404, cookie `href='#'`, login 500, `$9,000/5-week` ≠ canonical `$12,000/8-week`, no request-id, unlabeled chat input). **No PASS self-minted; no canonical mutation; all diffs staged, none applied; all six `ApprovalItem`s pending.** This is the correct, healthy shape of a first run: the compiler proved the defects deterministically and parked every fix behind the human gate.

---

## 8. Invariants (must always hold)

- **I1 — Provenance:** every `Observation.raw_span` is an exact substring of `text_normalized`/`text_translated`; every downstream object threads the same `session_id`.
- **I2 — 1:1 routing:** every `defect_kind` (except `other`) selects exactly one `template_id`; `other` is un-routable and never emits a contract.
- **I3 — Sandbox mints nothing:** every author-emitted receipt is `authority: none`, `verifier_status: UNVERIFIED`.
- **I4 — Summary integrity:** `summary.total == passed + failed == checks.length`; the verifier recomputes and FAILs on mismatch.
- **I5 — Staged, not applied:** `patch_diff` jobs write `diff_ref` and stop; application requires an approved `ApprovalItem`.
- **I6 — Target isolation:** all fetches hit only the founder-supplied `target_url`/`target_ref`; no hardcoded/live surface.
- **I7 — Evidence over prose:** every check carries `evidence`, not just a `detail` sentence.
- **I8 — Registry supremacy:** templates and risk policy come from sina-governance-SSOT; this compiler never invents them.

---

## 9. Non-goals

- **Not a chatbot / assistant.** It does not converse, answer questions, or hold a dialogue. It compiles voice → contracts.
- **Not a prompt generator.** It emits `deterministic_checks[]`, not prompts for another model to interpret.
- **Not an LLM judge.** No model decides a check's boolean, a receipt's PASS, or a patch's approval.
- **Not a deployer.** It never deploys, merges, deletes, unlocks cron, sends for real, or mutates a canonical repo. It stages diffs and queues approvals.
- **Not a PASS issuer.** The sandbox never mints PASS; only the independent CF Worker does.
- **Not a subjective UX critic.** `web_chat_ux_check` / `mobile_responsive_smoke_check` are pure structural smoke checks (mount node, controls, aria/placeholder, viewport meta, overflow), not taste judgements.
- **Not a live-surface crawler.** It audits one founder-supplied target per session; it does not discover or fetch arbitrary live sites (including `trustfield.ca`).
- **Not a canonical mutator from voice.** No irreversible action is ever reachable from a raw utterance.

---

## 10. Amendment rule

This doctrine is subordinate to the three spine files. If an implementation need conflicts with an object name, field name, template id, or the canonical E2E, **the spine files are amended first (under SSOT law), then this doctrine points at the change** — never the reverse. Divergent names are a defect, not a variant.
