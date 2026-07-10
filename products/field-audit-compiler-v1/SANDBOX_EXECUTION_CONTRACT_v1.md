# SANDBOX_EXECUTION_CONTRACT_v1

**Package:** FOUNDER_FIELD_AUDIT_TO_WORKFLOW_COMPILER_v1
**Reads (obey exactly):** `_SPINE_v1.json`, `VOICE_TO_OBSERVATION_SCHEMA_v1.json`, `RECEIPT_SCHEMA_FIELD_AUDIT_v1.json`
**Defines:** the on-disk `SandboxJob` format + the deterministic runner contract for **step 7** of `first_build_sequence` ("Sandbox runner in cat-05 watcher -> SandboxJob[] (inspect|patch_diff|test); stage diffs, never apply").

---

## 0. Authority binding (non-negotiable)

This file governs code that runs in **`/sandbox`** only. Per `_SPINE_v1.authority_model`:

- **sina-governance-SSOT** = law / registry / locks. Runs nothing. Owns the `templates[]` registry and risk policy this runner obeys.
- **sandbox** = authoring & R&D bench. `authority=none`. **CANNOT mint PASS.** Every write stays inside `sandbox/products/field-audit-compiler-v1/`. A `SandboxJob` may only **inspect / patch-into-a-diff / test / return a receipt**.
- **noetfield-cloud-factory-infra** = verified-execution factory. The independent **Cloudflare Worker verifier is the ONLY PASS issuer**; Supabase is the ledger.
- **cat-05-sandbox-worktree-execution** = the factory **WATCHER slot** that runs one `SandboxJob` in an isolated worktree. It is **not** the whole sandbox.
- **cat-09-receipt-trust-audit-layer** = trust / receipt center of gravity (GUARD-class promotes here).
- **cat-10-vertical-proof-products** = REVENUE-class / vertical-proof promotes here.

**Execution rule (spine `execution_rule`):** all generated work goes to sandbox FIRST. NO direct deploy, merge, deletion, cron unlock, real send, or canonical-repo mutation from raw voice. Canonical changes require an `ApprovalItem` or an explicitly-scoped low-risk rule. Jobs run **ONLY against the founder-supplied `target_url` / `target_ref`** — never hardcode or fetch a live surface. The `{TARGET_URL}` in the E2E is an **illustrative worked example**, not a live run.

**PASS issuance (spine `pass_issuance`):** `verifier_status=PASS` is issuable ONLY by the independent CF Worker after it recomputes `summary` from `checks[]` and confirms edge + secondary-CF-account proof. **Author-emitted sandbox receipts are always `authority="none"`, `verifier_status="UNVERIFIED"`.**

---

## 1. What a SandboxJob is

A `SandboxJob` is the **bounded execution of exactly one `WorkflowContract`** inside the cat-05 watcher worktree. It carries `authority="none"`, cannot mint PASS, cannot mutate any canonical surface, and terminates by emitting a `field_audit_receipt_v1` (always `UNVERIFIED` in sandbox).

The canonical object is defined in `_SPINE_v1.objects.SandboxJob`. Those field names are **load-bearing** and reproduced verbatim below. This contract adds a small, clearly-labelled **runtime envelope** (`allowed_effects`, `deterministic_checks`, `isolation`, `timeouts`, `canary`, plus mirrored `template_id` / `risk_class`) that the runner needs on disk to execute and self-police. The envelope never renames or overrides a spine field.

### 1.1 Spine fields (verbatim, from `_SPINE_v1.objects.SandboxJob`)

| field | type | note |
|---|---|---|
| `id` | `string(SJ-*)` | PK. |
| `workflow_contract_id` | `string(WC-*)` | FK -> `WorkflowContract.id`. |
| `session_id` | `string(AS-*)` | FK -> `AuditSession.id`. |
| `category_id` | `const(CAT-05-SANDBOX-WORKTREE-EXECUTION)` | Runs in the watcher slot. |
| `authority` | `const(none)` | Cannot mint PASS. |
| `job_kind` | `enum(inspect\|patch_diff\|test)` | Bounded action set. |
| `target` | `object` | Same founder-supplied ref+scope as the contract. |
| `inputs` | `object` | Instantiated params + resolved `surface_ref`s. |
| `status` | `enum(queued\|running\|done\|error)` | |
| `started_at` | `date-time` | |
| `finished_at` | `date-time` | |
| `output_ref` | `string` | Sandbox-local artifact bundle path. |
| `diff_ref` | `string\|null` | Path to proposed patch diff (`patch_diff` jobs only). **Never applied here.** |
| `receipt_id` | `string` | FK -> `Receipt` (`field_audit_receipt_v1`) emitted by the `VerificationRun`. |

### 1.2 Runtime envelope (added by this contract; operational, not a rename of anything in the spine)

| field | type | note |
|---|---|---|
| `template_id` | `string` | Mirror of `WorkflowContract.template_id`; must equal a `_SPINE_v1.templates[].id`. |
| `risk_class` | `enum(read_only\|low_risk_patch\|canonical_change)` | Mirror of `WorkflowContract.risk_class`. |
| `allowed_effects` | `array<enum(INSPECT\|PATCH_TO_DIFF\|TEST\|RECEIPT)>` | The **only** effects the runner may perform. Enforced structurally (§4.1). |
| `deterministic_checks` | `object[]` | Copied from the contract: `[{name, logic, pass_condition}]`. The exact checks the runner evaluates. |
| `isolation` | `object` | Worktree + network + FS confinement (§3). |
| `timeouts` | `object` | Wall-clock, per-request, fan-out and byte caps (§3.3). |
| `canary` | `object` | Mandatory negative-proof probe (§6). Every job ships one. |

`allowed_effects` is **derived from `job_kind`, never widened**:

| `job_kind` | `allowed_effects` |
|---|---|
| `inspect` | `["INSPECT","RECEIPT"]` |
| `patch_diff` | `["INSPECT","PATCH_TO_DIFF","RECEIPT"]` |
| `test` | `["INSPECT","TEST","RECEIPT"]` |

`INSPECT` (read-only fetch/select) and `RECEIPT` (emit the receipt) are present in **every** job. `PATCH_TO_DIFF` and `TEST` are mutually additive per `job_kind`. No `job_kind` — and no contract, and no voice — can ever produce `DEPLOY`, `MERGE`, `DELETE`, `SEND`, or `CANONICAL_WRITE`: those tokens are not in the enum, so they are unrepresentable (§7).

---

## 2. On-disk layout

Everything lives **inside the product dir**. Nothing is ever written outside it.

```
sandbox/products/field-audit-compiler-v1/
  runs/
    <session_id>/                         # e.g. AS-2026-07-09-fieldaudit
      <SJ-id>/                            # e.g. SJ-2c   -> this is output_ref
        job.json                          # the SandboxJob (spine fields + runtime envelope)
        inputs/
          resolved_targets.json           # scope_selector -> concrete hrefs/selectors resolved at run time
        evidence/                         # stored proof, not prose (feeds receipt.checks[].evidence)
          <hash>.body                     # raw fetched response body
          <hash>.dom.html                 # rendered/parsed DOM snapshot (when a check selects DOM)
          fetch_log.jsonl                 # {url, method, http_status, bytes, sha256, t_ms} per request
        canary.json                       # negative-proof result; MUST show fired=true (§6)
        patches/
          <name>.diff                     # unified diff -> diff_ref (patch_diff jobs only). NEVER applied.
        receipt.json                      # field_audit_receipt_v1, authority=none, verifier_status=UNVERIFIED
```

- `output_ref` = the `runs/<session_id>/<SJ-id>/` directory.
- `diff_ref` = `runs/<session_id>/<SJ-id>/patches/<name>.diff`, or `null` for `inspect`/`test`.
- `receipt_id` uses the spine's canonical form: `field_audit_receipt_v1:<session_id>:<WC-id>` (matches every `receipt_id` in the E2E, e.g. `field_audit_receipt_v1:AS-2026-07-09-fieldaudit:WC-1`).

**Provenance rule:** every `evidence/*` artifact is content-addressed by `sha256`; `receipt.checks[].evidence.{body_sha256,dom_sha256,artifact_path}` point at these files so the CF Worker can independently re-derive each boolean.

---

## 3. Isolation, confinement, and timeouts

### 3.1 Worktree isolation (cat-05 watcher)

- The runner executes in a **fresh, ephemeral git worktree + branch** for the cat-05 lane, branched from a commit that **excludes other lanes' files** (multi-agent worktree hygiene: commit explicit paths only, never `git add -A`, never touch/reset another lane).
- Canonical repos, if mounted for reference, are mounted **read-only**. The runner has no write handle to any path outside `sandbox/products/field-audit-compiler-v1/runs/<session_id>/<SJ-id>/`.
- The runner never runs `rm` on tracked files (append-only doctrine). Superseded artifacts are written as new files, not deletions.

### 3.2 Network confinement

- **Egress allowlist = exactly one host**: the host of the founder-supplied `target.target_url` (or the resolver for `target.target_ref`). Any request to any other host is refused by the runner and recorded as an isolation violation (job -> `status=error`).
- No hardcoded surfaces. `trustfield.ca` and every other live domain are **not** reachable unless the founder supplied them as this session's `target_url`.
- Methods restricted to **`GET` / `HEAD`** for `INSPECT` and `TEST`. `POST`/`PUT`/`PATCH`/`DELETE` egress is refused (that would be a `SEND`/`CANONICAL_WRITE`, which is prohibited — §7).

### 3.3 Timeouts and caps (`timeouts` block, concrete defaults)

```json
{
  "wall_clock_ms": 120000,
  "per_request_ms": 10000,
  "max_requests": 200,
  "max_bytes_per_response": 5242880,
  "max_total_bytes": 52428800,
  "max_redirects": 5
}
```

- `max_requests` bounds pattern-expansion fan-out per job (the fan-out itself is deterministic — one check per element matching `scope_selector`).
- Exceeding any cap ends the job with `status=error` and **no scored receipt** (a diagnostic is written to `output_ref`). Caps are enforced by the runner, not by the check logic.

---

## 4. The deterministic runner contract

### 4.1 Effect gate (structural, enforced before any I/O)

Every side-effecting primitive the runner exposes is tagged with one of `INSPECT | PATCH_TO_DIFF | TEST | RECEIPT`. Before performing it, the runner asserts the tag is in `job.allowed_effects`. A tag outside the set is a hard abort (`status=error`). There is **no** primitive tagged `DEPLOY`, `MERGE`, `DELETE`, `SEND`, or `CANONICAL_WRITE` anywhere in the runner — prohibitions are enforced by absence, not by a filter that could be bypassed.

### 4.2 Execution by `job_kind`

**`inspect`** (read-only; used for `read_only` contracts — e.g. `route_health_check`, `broken_link_scan`, `cta_route_check`, `auth_entrypoint_check`):
1. Resolve `target.scope_selector` against a **single read-only fetch** of the target surface into `inputs/resolved_targets.json` (enumerate every matching element/href — this is the deterministic fan-out).
2. For each `deterministic_checks[]`, evaluate the **pure, no-LLM** `logic` (HTTP status | DOM/selector presence | regex | hash equality) and record `passed` (boolean over `pass_condition`) with stored `evidence`.
3. Emit the receipt (§5). `diff_ref = null`.

**`patch_diff`** (used for `low_risk_patch` / `canonical_change` contracts — e.g. `pricing_claim_consistency_check`, `request_id_visibility_check`, `web_chat_ux_check`):
1. Run the same read-only inspection as above (a patch job still fully inspects and scores its checks — the mismatch is the evidence that justifies the patch).
2. Compute the proposed fix as a **unified diff** written to `patches/<name>.diff`; set `diff_ref`.
3. **The diff is NEVER applied.** It is staged for the approval queue only. Applying it is a canonical change that requires an approved `ApprovalItem` downstream (§8), never the runner.
4. Emit the receipt (§5).

**`test`** (used when a template must exercise behavior to produce evidence — e.g. `mobile_responsive_smoke_check` at a fixed viewport, or a route-liveness probe sequence):
1. Run the bounded, read-only test (headless measurement / fixed-viewport render / sequenced GETs) against the founder-supplied target only.
2. Persist raw measurements as `evidence/` artifacts; score each `deterministic_checks[]` from them.
3. Emit the receipt (§5). Tests **produce evidence; they do not change the surface**. `diff_ref = null`.

### 4.3 Determinism requirements

- All check `logic` is **pure and no-LLM**: HTTP status, DOM/selector presence, regex, hash equality — exactly the shapes the CF Worker re-derives.
- Normalization used inside a check (e.g. `offer_copy` / `pricing_claim` string compares) must be the same replayable normalization recorded upstream; the runner stores `expected`/`actual` in `evidence` so the compare is reproducible.
- No wall-clock- or ordering-dependent branching in check outcomes. Same target + same contract => same `checks[]` booleans.

---

## 5. Receipt emission (per `RECEIPT_SCHEMA_FIELD_AUDIT_v1.json`)

At the end of the run, a `VerificationRun` self-writes `receipt.json` as a `field_audit_receipt_v1`. It obeys the schema exactly:

- `schema` = `"field_audit_receipt_v1"` (fixed discriminator).
- `session_id`, `workflow_contract_id`, `sandbox_job_id` = FKs to this job's chain.
- `category_id` = the contract's `promotion.factory_category` (`CAT-09-...` for GUARD/link/receipt checks, `CAT-10-...` for REVENUE/vertical-proof). Set from the contract; the CF Worker binds an `EXPECTED_CATEGORY_ID` and FAILs on mismatch.
- `checks[]` = **one entry per evaluated `deterministic_checks[]`** (per fanned element for expansions). Each `{name, passed, detail, evidence}` where:
  - `name` MUST match a `deterministic_checks[].name` in the contract.
  - `passed` = pure boolean.
  - `detail` = one-liner, e.g. `"GET {TARGET_URL}/apply-for-program -> HTTP 404"`.
  - `evidence` = stored proof, **not prose** (`url`, `http_status`, `selector`, `regex`, `match`, `body_sha256`, `dom_sha256`, `artifact_path`, `expected`, `actual`).
- `summary` = `{total, passed, failed}` where `total == checks.length == passed + failed`. The author writes it, but the CF Worker **IGNORES the submitted summary and RECOMPUTES** it from `checks[]`; any mismatch => `verifier_status=FAIL`.
- `value_class` = the contract's `promotion.value_class` (`REVENUE|GUARD|META|NONE`).
- `verifier_status` = **`"UNVERIFIED"`** — the ONLY legal value for a sandbox self-write.
- `authority` = **`"none"`** — sandbox never self-mints PASS.

The runner does **not** set `verifier_runtime`, `verified_receipt_id`, `recomputed`, or `failures` — those are written by the independent CF Worker on adjudication. The `VerificationRun.verifier_runtime` for the sandbox self-write is `sandbox_selfwrite`; only `cloudflare_worker` may later issue `PASS`.

**Canary is NOT in the scored `checks[]`** (it would corrupt `summary`); it lives in `canary.json` and is asserted by the runner before emit (§6).

---

## 6. Red-capable requirement (mandatory negative-proof canary)

A checker that cannot produce RED is untrusted. **Every job ships a negative-proof canary that MUST fire.**

### 6.1 Definition

The `canary` is a synthetic, **known-bad** probe built from the same check `logic` as the job, run against a **guaranteed-failing input** so its correct outcome is `passed=false`. Its purpose is to prove the runner's check machinery is actually capable of detecting failure on this target — that it is not rubber-stamping.

Per template family:

| template family | canary probe (known-bad input) | correct outcome |
|---|---|---|
| `broken_link_scan`, `route_health_check`, `cta_route_check`, `auth_entrypoint_check`, `legal_footer_link` | GET a sentinel path guaranteed absent on the target host, e.g. `{TARGET_URL}/__canary_noetfield_should_404__` | `passed=false` (non-2xx) |
| `offer_copy_consistency_check`, `pricing_claim_consistency_check` | compare rendered copy against a sentinel canonical value that cannot match (e.g. `"__CANARY_NEVER_MATCHES__"`) | `passed=false` (mismatch) |
| `request_id_visibility_check`, `web_chat_ux_check` | run the selector/regex against an empty/sentinel DOM fragment | `passed=false` (no match) |
| `mobile_responsive_smoke_check` | measure a synthetic 2000px-wide fixture at the 375px viewport | `passed=false` (overflow) |

### 6.2 Firing rule

- **The canary MUST fire** — i.e. `canary.passed` MUST be `false` and the runner records `fired=true`.
- If the canary does **not** fire (it reports `passed=true`, or errors, or is skipped), the check machinery is not red-capable for this run. The runner **aborts**: `job.status=error`, **no scored receipt is emitted**, and a diagnostic (`canary.json` with `fired=false`) is written to `output_ref`. The chain does not advance.
- `canary.json` shape:

```json
{ "template_id": "broken_link_scan", "probe": "{TARGET_URL}/__canary_noetfield_should_404__",
  "expected_passed": false, "observed_passed": false, "fired": true,
  "evidence": { "url": "{TARGET_URL}/__canary_noetfield_should_404__", "http_status": 404 } }
```

### 6.3 Independent confirmation

The CF Worker **re-runs the canary probe** during adjudication and refuses to issue `PASS` on any job whose canary cannot fire — red-capability is verified independently, exactly as `checks[]` are. `canary.json` is part of the `output_ref` bundle handed to the Worker.

---

## 7. Hard prohibitions (structural, not advisory)

A `SandboxJob` **NEVER**:

1. **Deploys** anything (no publish, no promote-to-prod, no cron unlock).
2. **Merges** any branch or PR.
3. **Deletes** any file — tracked or otherwise (append-only; new files supersede).
4. **Sends** anything real (no email, no webhook, no message, no `POST`/mutating request to any surface). All email/broadcast/webhook MCP tools are out of scope for this runner.
5. **Writes to any canonical surface / repo.** All output stays inside `runs/<session_id>/<SJ-id>/`.
6. **Mints PASS.** Sandbox receipts are always `authority="none"`, `verifier_status="UNVERIFIED"`.
7. **Fetches a hardcoded or live surface.** It runs **only** against `target.target_url` / `target.target_ref` supplied by the founder for **this** session; egress is allowlisted to that one host.
8. **Applies a diff.** `patch_diff` jobs stage a unified diff to `diff_ref`; applying it requires an approved `ApprovalItem` downstream — never the runner, never raw voice.

Enforcement is by **absence** (no primitive exists for effects 1–5, 8) and by **effect-gate + egress allowlist** (§4.1, §3.2), so no contract, `job_kind`, or voice input can widen the surface. Any attempt is recorded as an isolation violation and ends the job at `status=error`.

---

## 8. From WorkflowContract to SandboxJob to ApprovalItem (chain position)

1. **Contract generator (spine step 6)** emits a `WorkflowContract` (`WC-*`) with `template_id`, `target{target_url|target_ref, scope_selector}`, `params`, `deterministic_checks`, `promotion`, `risk_class`, `approval_required`.
2. **Runner (spine step 7 — this contract)** instantiates a `SandboxJob` by copying, unchanged: `workflow_contract_id`, `session_id`, `target` (the same founder-supplied ref+scope), and mirroring `template_id`, `risk_class`, `deterministic_checks`. It sets `inputs` = instantiated `params` + resolved `surface_ref`s, derives `job_kind`/`allowed_effects`, attaches `isolation`/`timeouts`/`canary`.

   **`risk_class` -> `job_kind` mapping:**
   | contract `risk_class` | `job_kind` | rationale |
   |---|---|---|
   | `read_only` | `inspect` | never mutates; scores checks only. |
   | `low_risk_patch` | `patch_diff` | stage additive fix as diff; still queued for approval. |
   | `canonical_change` | `patch_diff` | stage fix as diff; requires approval to apply. |
   | (template needs to exercise behavior for evidence) | `test` | e.g. `mobile_responsive_smoke_check`. |

3. **VerificationRun (spine step 8)** runs the checks, asserts the canary fired, self-writes `receipt.json` (`UNVERIFIED`). The independent CF Worker later recomputes `summary` + edge/secondary-account proof to issue `PASS/FAIL/BLOCKED`.
4. **Approval queue (spine step 9)** turns receipts + staged diffs into `ApprovalItem`s. Only an **approved** `ApprovalItem` authorizes a canonical change. For a `patch_diff` job, `ApprovalItem.proposed_patch_ref` = the job's `diff_ref`.

Consistent with the E2E `chain_summary`: 6 cat-05 sandbox jobs (3 `inspect`, 3 `patch_diff`), 6 receipts (all `FAIL` at the Worker because the surface is genuinely broken), 6 pending `ApprovalItem`s. **No PASS self-minted; no canonical mutation; all diffs staged, none applied.**

---

## 9. Concrete example — SandboxJob for `broken_link_scan`

This uses the **single canonical E2E** (`session_id = AS-2026-07-09-fieldaudit`, target shown as the founder-supplied `{TARGET_URL}`). In the E2E, `broken_link_scan` is the sibling contract `WC-2c(broken_link_scan)` spawned by the pattern expansion of `WC-2` ("fan to ALL required legal footer links + generic broken_link_scan over nav+footer"). Its job is `SJ-2c`. The template is `read_only` / GUARD / promotes to `CAT-09-RECEIPT-TRUST-AUDIT-LAYER`, so `job_kind=inspect`, `diff_ref=null`.

### 9.1 `job.json`

```json
{
  "id": "SJ-2c",
  "workflow_contract_id": "WC-2c",
  "session_id": "AS-2026-07-09-fieldaudit",
  "category_id": "CAT-05-SANDBOX-WORKTREE-EXECUTION",
  "authority": "none",
  "job_kind": "inspect",
  "template_id": "broken_link_scan",
  "risk_class": "read_only",
  "allowed_effects": ["INSPECT", "RECEIPT"],
  "target": {
    "target_url": "{TARGET_URL}",
    "target_ref": null,
    "scope_selector": "nav a[href], footer a[href]"
  },
  "inputs": {
    "scope_selector": "nav a[href], footer a[href]",
    "ignore": ["mailto:", "tel:"]
  },
  "deterministic_checks": [
    {
      "name": "href_resolves",
      "logic": "HTTP GET/HEAD each resolved href",
      "pass_condition": "status in [200,301,302,308] AND href not in ['', '#', 'javascript:void(0)']"
    }
  ],
  "isolation": {
    "worktree": "cat-05 ephemeral worktree/branch, explicit-paths-only, canonical repos read-only",
    "egress_allowlist": ["{TARGET_URL_HOST}"],
    "methods": ["GET", "HEAD"],
    "fs_write_root": "sandbox/products/field-audit-compiler-v1/runs/AS-2026-07-09-fieldaudit/SJ-2c/"
  },
  "timeouts": {
    "wall_clock_ms": 120000,
    "per_request_ms": 10000,
    "max_requests": 200,
    "max_bytes_per_response": 5242880,
    "max_total_bytes": 52428800,
    "max_redirects": 5
  },
  "canary": {
    "template_id": "broken_link_scan",
    "probe": "{TARGET_URL}/__canary_noetfield_should_404__",
    "expected_passed": false,
    "observed_passed": false,
    "fired": true,
    "evidence": { "url": "{TARGET_URL}/__canary_noetfield_should_404__", "http_status": 404 }
  },
  "status": "done",
  "started_at": "2026-07-09T20:06:00Z",
  "finished_at": "2026-07-09T20:06:04Z",
  "output_ref": "sandbox/products/field-audit-compiler-v1/runs/AS-2026-07-09-fieldaudit/SJ-2c/",
  "diff_ref": null,
  "receipt_id": "field_audit_receipt_v1:AS-2026-07-09-fieldaudit:WC-2c"
}
```

### 9.2 `inputs/resolved_targets.json` (deterministic fan-out — one check per unique href)

```json
{
  "scope_selector": "nav a[href], footer a[href]",
  "resolved_hrefs": [
    "{TARGET_URL}/",
    "{TARGET_URL}/pricing",
    "{TARGET_URL}/apply-for-program",
    "#",
    "{TARGET_URL}/privacy"
  ],
  "ignored": [],
  "note": "mailto:/tel: excluded per inputs.ignore; '#' kept so it can be scored as a broken target."
}
```

### 9.3 `receipt.json` (`field_audit_receipt_v1`, one `href_resolves` check per unique href)

```json
{
  "schema": "field_audit_receipt_v1",
  "session_id": "AS-2026-07-09-fieldaudit",
  "workflow_contract_id": "WC-2c",
  "sandbox_job_id": "SJ-2c",
  "category_id": "CAT-09-RECEIPT-TRUST-AUDIT-LAYER",
  "checked_at": "2026-07-09T20:06:04Z",
  "checks": [
    { "name": "href_resolves", "passed": true,  "detail": "GET {TARGET_URL}/ -> HTTP 200",
      "evidence": { "url": "{TARGET_URL}/", "http_status": 200, "match": true, "artifact_path": "runs/AS-2026-07-09-fieldaudit/SJ-2c/evidence/a1b2.body" } },
    { "name": "href_resolves", "passed": true,  "detail": "GET {TARGET_URL}/pricing -> HTTP 200",
      "evidence": { "url": "{TARGET_URL}/pricing", "http_status": 200, "match": true } },
    { "name": "href_resolves", "passed": false, "detail": "GET {TARGET_URL}/apply-for-program -> HTTP 404",
      "evidence": { "url": "{TARGET_URL}/apply-for-program", "http_status": 404, "match": false } },
    { "name": "href_resolves", "passed": false, "detail": "footer link href='#' -> unresolved target",
      "evidence": { "url": "#", "match": false } },
    { "name": "href_resolves", "passed": true,  "detail": "GET {TARGET_URL}/privacy -> HTTP 200",
      "evidence": { "url": "{TARGET_URL}/privacy", "http_status": 200, "match": true } }
  ],
  "summary": { "total": 5, "passed": 3, "failed": 2 },
  "value_class": "GUARD",
  "verifier_status": "UNVERIFIED",
  "authority": "none"
}
```

Notes:
- `summary` is author-claimed (`total=5=checks.length`, `passed=3`, `failed=2`). The CF Worker will **recompute** it from `checks[]` and FAIL on any mismatch; it also re-fetches each `href` to re-derive every boolean.
- `verifier_status="UNVERIFIED"` and `authority="none"` because this is a sandbox self-write. Only the CF Worker may promote it to `PASS`/`FAIL` (this surface would come back `FAIL` — two dead links).
- The `#` and `/apply-for-program` failures corroborate the founder's spoken defects; because `broken_link_scan` is `read_only`, `SJ-2c` stages **no** diff (`diff_ref=null`) — remediation flows through `WC-1`/`WC-2` `ApprovalItem`s, not this scan.
- The canary (`/__canary_noetfield_should_404__` -> 404, `fired=true`) proves the scanner is red-capable for this target; had it not fired, `SJ-2c` would be `status=error` with no receipt.
