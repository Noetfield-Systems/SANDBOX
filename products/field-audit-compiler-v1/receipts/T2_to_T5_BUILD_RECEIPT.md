# T2–T5 build receipt — the field-audit compiler is a running deterministic engine

**Authority:** `none` (sandbox authoring). **verifier_status:** `UNVERIFIED` — advisory; no PASS self-minted.
**Date:** 2026-07-09. **Runtime:** Node 24 + tsx (TypeScript). Reuses T1 (extractor + validator).

## What now runs (spec → engine)
`observation → cluster → template selection → workflow contract → sandbox job → broken_link_scan → self-written receipt → promotion decision packet`, all deterministic (no LLM in stages 4–8).

## Files created
- **T2** `src/cluster/cluster.ts`, `src/cluster/select_template.ts`, `src/templates/registry.json`, `fixtures/.../clusters.json`, `tests/cluster.test.ts`
- **T3** `src/lib/jsonschema.ts` (shared validator), `WORKFLOW_CONTRACT_SCHEMA_v1.json`, `src/compile/generate_contract.ts`, `tests/generate_contract.test.ts`
- **T4** `src/verify/recompute_summary.ts`, `src/verify/selfwrite_receipt.ts`, `src/runner/sandbox_job.ts`, `tests/runner.test.ts`, `tests/receipt_selfwrite.test.ts`
- **T5** `src/runner/checks/broken_link_scan.ts`, `fixtures/target-surface/index.html`, `tests/e2e_broken_link_scan.test.ts`, `demo/run_first_e2e.ts`, `receipts/T5_first_e2e_receipt.json`

## Tests run — 28/28 green
| ticket | test | result |
|---|---|---|
| T1 | stage1 | 5/5 |
| T2 | cluster | 6/6 |
| T3 | generate_contract | 6/6 |
| T4 | runner | 3/3 |
| T4 | receipt_selfwrite | 4/4 |
| T5 | e2e_broken_link_scan | 4/4 |

## Red-canary results (observed RED → GREEN, not tautologies)
- **T2** dedup + severity=max discriminate (seeded per-obs / first() bugs diverge).
- **T3** `canonical_change ⇒ approval_required` (seeded false → diverges).
- **T4** authority walls throw on blocked action / write-outside / non-target host; PASS cannot be self-minted; tampered summary detected.
- **T5** seeded `defaultClassify → true` (passes #/404): **e2e RED 1/4 (exit 1)** → reverted **GREEN 4/4 (exit 0)**.

## First E2E receipt ("Apply for Program link is broken.")
`field_audit_receipt_v1` · session `AS-2026-07-09-fieldaudit` · `CAT-09-RECEIPT-TRUST-AUDIT-LAYER` · `GUARD` · **UNVERIFIED** · authority `none`.
Checks (summary `{total:3, passed:1, failed:2}`): `/healthy`→200 PASS · **`/apply-for-program`→404 FAIL** · footer `#`→unresolved FAIL.
→ `PromotionDecisionPacket PDP-BL-1` (risk `high`, recommendation `needs_founder_decision`, **decision `pending`** — nothing promoted).

## DoD gates
- [x] All writes inside the product dir; runner artifacts confined to `.sandbox_runs/` (gitignored).
- [x] No receipt carries PASS; no code path self-mints PASS (`selfWriteReceipt` hard-codes UNVERIFIED).
- [x] No live host — `{TARGET_URL}` bound to a 127.0.0.1 fixture; only 127.0.0.1 hit; no diff applied, no deploy/merge/send.
- [x] Source stays canonical: the job emits git **worktree instructions** against the canonical repo; SANDBOX stores metadata only; no source copied in.
- [x] Names + canonical E2E (`OB-1..6`, `IC-1..6`, `WC-1..6`) match `_SPINE_v1.json`.

## Lower-cost runner that continues from here
The deterministic contracts now execute with **no LLM**: a **cron GitHub Actions** job checks out a pinned snapshot and runs `broken_link_scan` (and the other tier-0 checks — route_health / cta_route / auth_entrypoint / legal_footer) against a founder-supplied `TARGET_URL`, emits `field_audit_receipt_v1`, and an **independent Cloudflare Worker** re-derives the summary; **Supabase** ledgers it. ~$0/mo. LLM (tier-1) is only ever needed to classify fuzzy voice or draft copy — never for the checks themselves.
