# SANDBOX → CLOUD FACTORY MAPPING v1

**Package:** FOUNDER_FIELD_AUDIT_TO_WORKFLOW_COMPILER_v1
**Reads and obeys:** `_SPINE_v1.json`, `VOICE_TO_OBSERVATION_SCHEMA_v1.json`, `RECEIPT_SCHEMA_FIELD_AUDIT_v1.json` (same object names, field names, `template_id`s, and the same canonical E2E chain — `AS-2026-07-09-fieldaudit`).
**Question this file answers:** once a `SandboxJob` has produced a `field_audit_receipt_v1` in the sandbox, *how does that proven result cross the wall into the verified-execution factory* — and what stays behind.

---

## 0. Authority model this file is bound to

| Layer | Role | Can it mint PASS? | Can it mutate a canonical surface? |
|---|---|---|---|
| `sina-governance-SSOT` | law / registry / locks — owns the `templates[]` registry + risk policy | No (runs nothing) | No |
| `/sandbox` (this product dir) | authoring & R&D bench, `authority=none` | **No** — self-writes are always `verifier_status=UNVERIFIED` | No — inspect / patch-into-a-diff / test only |
| `noetfield-cloud-factory-infra` / `PRODUCT_CATEGORY` | verified-execution factory; thin orchestrators | The **independent Cloudflare Worker verifier is the ONLY PASS issuer** | Only via an approved `ApprovalItem` or an explicitly-scoped low-risk rule |
| `CAT-05-SANDBOX-WORKTREE-EXECUTION` | a factory **WATCHER slot** that runs one `SandboxJob` in an isolated worktree — NOT the whole sandbox | No | No |
| `CAT-09-RECEIPT-TRUST-AUDIT-LAYER` | trust / receipt center of gravity; GUARD-class receipts promote here | The Worker bound to `EXPECTED_CATEGORY_ID=CAT-09` issues PASS for CAT-09 receipts | No — it grades, it does not deploy |
| `CAT-10-VERTICAL-PROOF-PRODUCTS` | REVENUE-class / vertical-proof receipts promote here | The Worker bound to `EXPECTED_CATEGORY_ID=CAT-10` issues PASS for CAT-10 receipts | No |

**EXECUTION RULE (non-negotiable):** all generated work goes to sandbox FIRST. No direct deploy, merge, deletion, cron unlock, real send, or canonical-repo mutation from raw voice. Sandbox jobs run ONLY against the founder-supplied `TARGET_URL`/`target_ref`; they never hardcode or fetch a live surface. The E2E chain below is an **illustrative worked example** (`{TARGET_URL}` is a placeholder), not a live run.

---

## 1. The promotion path (sandbox result → factory category slot)

Promotion is a one-way ratchet. A result only moves right after the layer to its left has finished; nothing skips a step.

```
[sandbox]                                   [wall]                        [factory]
AuditSession → … → WorkflowContract
      │                                        │                             │
      ▼                                        │                             │
(1) SandboxJob (CAT-05 watcher worktree)       │                             │
    authority=none · inspect|patch_diff|test   │                             │
      │  emits                                 │                             │
      ▼                                        │                             │
(2) VerificationRun (verifier_runtime=         │                             │
    sandbox_selfwrite)                         │                             │
      │  self-writes                           │                             │
      ▼                                        │                             │
(3) Receipt field_audit_receipt_v1             │                             │
    authority=none · verifier_status=UNVERIFIED│                             │
      │                                        │                             │
      ▼                                        │                             │
(4) PromotionProposal  ─────────────────────►  │                             │
    (contract.promotion = {factory_category,   │                             │
     value_class}; diff_ref if patch_diff)      ├── independent CF Worker ───►│
                                               │   verifier_runtime=          │
                                               │   cloudflare_worker          │
                                               │   • re-derives summary from  │
                                               │     checks[] (total/passed/  │
                                               │     failed)                  │
                                               │   • binds EXPECTED_CATEGORY_ID│
                                               │   • edge + secondary-CF-     │
                                               │     account proof            │
                                               │        │                     │
                                               │        ▼                     │
(5) Verified Receipt (verifier_status=          │   PASS|FAIL|BLOCKED          │
    PASS|FAIL|BLOCKED, verifier_runtime set,    │        │                     │
    verified_receipt_id, recomputed{})  ◄───────┘        ▼                     │
      │                                                (6) Supabase ledger row │
      ▼                                                    (append-only)        │
(7) ApprovalItem (decision=pending)  ── founder gate ──► approved → factory     │
    canonical_change ⇒ approval_required=true              category slot picks  │
    read_only ⇒ may auto-clear (see §5)                    up the verified      │
                                                           receipt              │
```

Step notes:

1. **`SandboxJob`** runs in the CAT-05 watcher worktree. `authority=none`, `job_kind ∈ {inspect, patch_diff, test}`. `patch_diff` writes a diff to `diff_ref` and **never applies it**. Target is the same founder-supplied `target` as the `WorkflowContract`.
2. **`VerificationRun`** with `verifier_runtime=sandbox_selfwrite` runs the `deterministic_checks` and produces `checks[]`.
3. **`Receipt`** (`schema=field_audit_receipt_v1`) is self-written with `authority=none`, `verifier_status=UNVERIFIED`. This is the *only* legal status for a sandbox self-write. `checks[].evidence` carries proof (`http_status`, `body_sha256`/`dom_sha256`, `selector`, `regex`, `artifact_path`), not prose.
4. **PromotionProposal** = the receipt + the contract's `promotion` block (`{factory_category, value_class}`) + `risk_class` + optional `diff_ref`. This is the payload handed across the wall. It carries no authority.
5. **Independent CF Worker** adjudicates. It **ignores the submitted `summary`** and recomputes `total=len(checks)`, `passed=count(passed==true)`, `failed=count(passed==false)`; any mismatch ⇒ `verifier_status=FAIL`. It binds to an `EXPECTED_CATEGORY_ID` and FAILs on `category_id` or `schema` mismatch. PASS additionally requires edge execution + secondary-CF-account proof. It writes back `verifier_runtime=cloudflare_worker`, `verified_receipt_id`, `recomputed{}`, and `failures[]` when not PASS.
6. **Supabase ledger** gets one append-only row for the verified receipt (see `never rm tracked files` / commit-receipts doctrine — receipts are proof artifacts, never gitignored, never deleted).
7. **`ApprovalItem`** is the founder gate. A verified receipt (or an explicitly-scoped low-risk result) becomes an approval-ready patch. **Only an approved `ApprovalItem` authorizes a canonical change — never raw voice, never a PASS by itself.**

> **A PASS is not a deploy.** In the canonical E2E every receipt is `verifier_status=FAIL` (the surface is genuinely broken), yet the pipeline still produces six pending `ApprovalItem`s. PASS/FAIL grades the *observation*; the founder gate authorizes the *change*. The two are independent.

---

## 2. The 6-file golden stack that wraps each promoted contract

Each `WorkflowContract` that promotes into a factory category slot is materialized as the factory-proven **golden stack** — thin orchestrators around one authoritative check. The category slot is not bespoke code; it is this stack instantiated for the contract's `template_id`.

| # | File | Repo it lives in | Responsibility | Authority |
|---|---|---|---|---|
| 1 | `README.md` | `noetfield-cloud-factory-infra/<category>/` | What the slot checks, which `template_id`, which `EXPECTED_CATEGORY_ID`, promotion + value_class | doc only |
| 2 | `.github/workflows/<category>.yml` (GHA) | factory category | thin cron/dispatch trigger; calls `task.py`; **no verdict logic** | orchestrator, no PASS |
| 3 | `task.py` | factory category | runs the contract's `deterministic_checks` against the founder `target`; emits a `field_audit_receipt_v1` self-write (`UNVERIFIED`) | `authority=none` |
| 4 | CF Worker verifier (`worker.js` / `src/`) | factory category (independent CF account) | **the ONLY PASS issuer**: re-derives `summary`, binds `EXPECTED_CATEGORY_ID`, edge + secondary-account proof | issues PASS/FAIL/BLOCKED |
| 5 | `wrangler.toml` | factory category | binds the Worker to its route + the *secondary* CF account used for independence proof | config |
| 6 | Supabase migration (`supabase/migrations/*.sql`) | factory category | append-only ledger table for verified receipts (schema mirrors `field_audit_receipt_v1`) | ledger |
| + | `check-once.js` (Railway) | factory category | single-shot liveness runner for the slot (mirrors the shipped CAT-10 `http_200` poller doctrine) | orchestrator, no PASS |

**Why the 6-file stack is load-bearing here:** it is the same shape as the factory's proven `category_cloud_task_receipt_v1` slots, and `field_audit_receipt_v1` was *deliberately designed to mirror it* (`{schema, category_id, checked_at, checks:[{name,passed,detail}], summary:{total,passed,failed}}`). Because the receipt shapes match, a promoted contract drops into a golden-stack slot with **zero new verifier logic** — the same CF Worker doctrine (recompute-summary-from-checks, FAIL on mismatch, PASS only with edge+secondary-account proof) re-derives it. `task.py` (file 3) is a thin orchestrator; the *check semantics* stay in the template (see §4 anti-fork rule).

---

## 3. Template-family → factory-category mapping (all 10 templates)

Routing is deterministic and comes straight from each template's `factory_category` + `value_class` in `_SPINE_v1.templates[]`. Two rules, no judgement calls:

- **link / route / auth / request-id / liveness checks → `CAT-09-RECEIPT-TRUST-AUDIT-LAYER`** (GUARD/META value; trust + receipt center of gravity).
- **commercial copy / pricing / storefront / money-path checks → `CAT-10-VERTICAL-PROOF-PRODUCTS`** (REVENUE value; vertical proof).
- **the sandbox/worktree execution seam itself → `CAT-05-SANDBOX-WORKTREE-EXECUTION`** — this is *where every `SandboxJob` runs*, not a promotion destination for receipts. A receipt's owning promotion category is always CAT-09 or CAT-10; CAT-05 is the watcher slot it was produced in.

### Full mapping table (10 templates)

| # | `template_id` | `defect_kind` (Observation/Cluster) | Family | `value_class` | Promotes to `factory_category` | E2E `WorkflowContract` | First-five? | Golden-stack `EXPECTED_CATEGORY_ID` |
|---|---|---|---|---|---|---|---|---|
| 1 | `route_health_check` | `route_health` | link/route | GUARD | **CAT-09-RECEIPT-TRUST-AUDIT-LAYER** | (baseline; mirrors CAT-10 `http_200` poller) | ✅ | CAT-09 |
| 2 | `broken_link_scan` | `broken_link` | link/route | GUARD | **CAT-09-RECEIPT-TRUST-AUDIT-LAYER** | `WC-2c` (expansion of WC-2) | ✅ | CAT-09 |
| 3 | `cta_route_check` | `cta_route` | commercial/money-path | REVENUE | **CAT-10-VERTICAL-PROOF-PRODUCTS** | `WC-1` (Apply-for-Pilot CTA) | ✅ | CAT-10 |
| 4 | `auth_entrypoint_check` | `auth_entrypoint` | commercial/money-path | REVENUE | **CAT-10-VERTICAL-PROOF-PRODUCTS** | `WC-3` (Sign-in) | ✅ | CAT-10 |
| 5 | `request_id_visibility_check` | `request_id_visibility` | request-id/trust | GUARD | **CAT-09-RECEIPT-TRUST-AUDIT-LAYER** | `WC-5` (Request IDs) | ✅ | CAT-09 |
| 6 | `legal_footer_link_check` | `legal_footer_link` | link/route/compliance | GUARD | **CAT-09-RECEIPT-TRUST-AUDIT-LAYER** | `WC-2` (footer Cookie link) | — | CAT-09 |
| 7 | `offer_copy_consistency_check` | `offer_copy` | commercial copy/storefront | REVENUE | **CAT-10-VERTICAL-PROOF-PRODUCTS** | `WC-4b` (sibling of WC-4) | — | CAT-10 |
| 8 | `pricing_claim_consistency_check` | `pricing_claim` | commercial pricing/storefront | REVENUE | **CAT-10-VERTICAL-PROOF-PRODUCTS** | `WC-4` (Acme Brief $12,000 / 8-week) | — | CAT-10 |
| 9 | `web_chat_ux_check` | `web_chat_ux` | UX/tooling signal | META | **CAT-09-RECEIPT-TRUST-AUDIT-LAYER** | `WC-6` (web chat widget) | — | CAT-09 |
| 10 | `mobile_responsive_smoke_check` | `mobile_responsive` | UX/render signal | GUARD | **CAT-10-VERTICAL-PROOF-PRODUCTS** | (not exercised in E2E) | — | CAT-10 |

**Reading the table:**
- Family "link/route/auth/request-id/liveness" → CAT-09 covers templates **1, 2, 5, 6, 9** (route health, broken links, request-id visibility, legal footer, web-chat UX signal). These are GUARD/META — they protect trust and compliance, not money paths directly.
- Family "commercial copy / pricing / storefront / money-path" → CAT-10 covers templates **3, 4, 7, 8, 10** (CTA route, auth entrypoint, offer copy, pricing claim, mobile responsive). CTA and auth are REVENUE because a dead CTA/login blocks money; offer/pricing are REVENUE because they gate the storefront claim; `mobile_responsive_smoke_check` promotes to CAT-10 as a GUARD over the commercial surface's render health.
- **CAT-05 appears in no row's promotion column.** Every one of the 10 *executes* as a `SandboxJob` inside the CAT-05 watcher worktree (`category_id=CAT-05-SANDBOX-WORKTREE-EXECUTION` on the job), then the receipt promotes to the CAT-09/CAT-10 column shown. CAT-05 is the seam, never the destination.

> Sequencing note (from the spine): the **first five** (`route_health_check`, `broken_link_scan`, `cta_route_check`, `auth_entrypoint_check`, `request_id_visibility_check`) are pure HTTP + static-DOM/regex and drop into golden-stack slots today. `offer_copy` and `pricing_claim` need a founder-supplied canonical source; `web_chat_ux` and `mobile_responsive` need rendering — those four are sequenced after the first five even though their promotion category is fixed above.

---

## 4. Thin-orchestrator anti-fork rule

**The check logic never forks into the factory. Only a thin orchestrator does.**

- The *authoritative* check semantics live in exactly one place: the `templates[]` registry in `sina-governance-SSOT` (law/registry) and the `deterministic_checks` copied verbatim into the `WorkflowContract`. That is the single source of truth for "what does `cta_route_check` mean."
- The factory golden stack (`task.py`, the CF Worker) **checks out the authoritative logic read-only** and re-derives against it. It does not re-implement, "improve", or diverge the predicate. `task.py` is a runner; the CF Worker is a re-deriver. Neither is allowed to invent a check the contract didn't declare.
- **No second copy of a template's logic may be edited independently in the factory.** If a check needs to change, it changes in the SSOT registry and re-flows down through a new `WorkflowContract` version — never by patching the factory's copy. This is the anti-fork rule: one authoritative logic, many read-only re-derivations.
- Concretely, the CF Worker's job is *re-derivation, not authorship*: refetch/re-select/re-regex/re-hash exactly as `verifier_logic` states, recompute `summary` from `checks[]`, FAIL on mismatch. It has no license to add or drop checks. This is what keeps the verifier *independent* (it can disagree with the author) without letting it *fork* (it can't change the rules).
- Multi-lane hygiene (per workspace memory): each promotion runs in its own isolated worktree; commit explicit paths only, never `git add -A`; base off a commit that excludes other lanes; never touch/reset another lane's files. The factory checkout of template logic is **read-only** — a promotion lane reads the SSOT template, it does not write to it.

---

## 5. Founder gates at each promotion step (deploy/cron = FOUNDER_ONLY)

Gates are cumulative — a step's gate must clear before the next step is even eligible.

| Promotion step | Gate | Who clears it | FOUNDER_ONLY? |
|---|---|---|---|
| Run `SandboxJob` in CAT-05 watcher | scope gate: bounded to founder `target`, `job_kind ∈ {inspect,patch_diff,test}`, `authority=none` | automatic (policy-enforced) | No — but cannot deploy/apply |
| Self-write `field_audit_receipt_v1` | must be `authority=none`, `verifier_status=UNVERIFIED` | automatic | No |
| Independent CF Worker adjudicates PASS/FAIL | edge + secondary-CF-account proof; summary re-derivation; category/schema bind | the independent Worker (not the author) | No — but PASS is Worker-only, never self-minted |
| Write verified receipt to Supabase ledger | append-only; receipt committed as proof | factory orchestrator | No |
| **Open the factory category slot / enable its GHA cron** | **deploy + cron unlock** | **FOUNDER** | **✅ FOUNDER_ONLY** |
| `ApprovalItem` for a `canonical_change` | human approval of the staged diff | **FOUNDER** | **✅ FOUNDER_ONLY** |
| `ApprovalItem` for a `read_only` result | may auto-clear (`approval_required=false`) | automatic per explicitly-scoped low-risk rule | No |
| `ApprovalItem` for a `low_risk_patch` | still queued for approval by default | **FOUNDER** (unless an explicitly-scoped low-risk rule pre-authorizes) | **✅ FOUNDER_ONLY** by default |
| Apply the diff to the canonical surface | requires an **approved** `ApprovalItem` | **FOUNDER** | **✅ FOUNDER_ONLY** |

**Hard invariants (restating the execution rule at the gate level):**
- **Deploy is FOUNDER_ONLY.** Standing up or promoting a factory category slot, and unlocking its cron, is a founder action. No agent, no PASS, no receipt unlocks a cron on its own.
- **Cron unlock is FOUNDER_ONLY.** The GHA `.yml` (golden-stack file 2) and any scheduled runner ship *disabled/dispatch-only* until the founder enables the schedule.
- **Canonical mutation requires an approved `ApprovalItem`** whose `risk_class` and staged `proposed_patch_ref` the founder has seen — never raw voice, never a bare PASS.
- **`read_only` contracts** (E2E: `WC-1`, `WC-2`, `WC-3` — `risk_class=read_only`, `approval_required=false`) can be *promoted and run* without a per-run approval because they only inspect. But note: in the E2E their *fixes* (AP-1, AP-2, AP-3) are `risk_class=canonical_change` — inspecting is read-only, fixing the 404/500/dead-link is a canonical change that goes back through the founder gate.

---

## 6. Worked example: WC-1 promotion, end to end

Following the single canonical chain (`AS-2026-07-09-fieldaudit`), tracing `WC-1` (the broken Apply-for-Pilot CTA) across the wall. Nothing here fetches a live surface; `{TARGET_URL}` is founder-supplied.

1. **Contract:** `WC-1`, `template_id=cta_route_check`, `promotion={factory_category: CAT-10-VERTICAL-PROOF-PRODUCTS, value_class: REVENUE}`, `risk_class=read_only`, `approval_required=false`, `target={target_url:{TARGET_URL}, scope_selector:"a[data-cta], button[data-cta]"}`.
2. **SandboxJob `SJ-1`:** `category_id=CAT-05-SANDBOX-WORKTREE-EXECUTION`, `authority=none`, `job_kind=inspect`, `diff_ref=null`. Runs the two checks (`cta_present`, `cta_route_resolves`).
3. **VerificationRun `VR-1`** self-writes, then the CF Worker re-derives: `verifier_runtime=cloudflare_worker`, `summary={total:2,passed:1,failed:1}`, `verifier_status=FAIL`.
4. **Receipt `field_audit_receipt_v1:AS-2026-07-09-fieldaudit:WC-1`:** `category_id=CAT-10-VERTICAL-PROOF-PRODUCTS`, `checks[]` = [`cta_present` passed=true (selector matched), `cta_route_resolves` passed=false (`GET {TARGET_URL}/apply-for-program → HTTP 404`, `evidence.http_status=404`)], `value_class=REVENUE`, `verifier_status=FAIL`, `authority=none`.
5. **Golden-stack slot:** this promotes into the **CAT-10** golden stack. The Worker was bound to `EXPECTED_CATEGORY_ID=CAT-10-VERTICAL-PROOF-PRODUCTS` and matched; it recomputed `summary` from `checks[]` (2/1/1) and confirmed the author's rollup, then graded FAIL on the failed check with edge + secondary-account proof. The verified receipt lands in the Supabase ledger.
6. **Founder gate:** because the *fix* is a canonical change, `ApprovalItem AP-1` — "Fix broken 'Apply for Program' CTA route (404)", `risk_class=canonical_change`, `value_class=REVENUE`, `decision=pending`. **The 404 fix does not ship until the founder approves AP-1.** The FAIL receipt is proof of the defect; it is not authority to change the surface.

Net: one spoken sentence → one CAT-10 REVENUE golden-stack slot graded by an independent Worker → one pending founder-gated approval. No PASS self-minted, no canonical mutation, the CAT-05 worktree never deployed anything, and pattern expansion (`WC-1a/1b/1c`) fans the same `cta_route_check` across every other `[data-cta]` on the surface through the identical promotion path.
