# Upgrade receipt — first-five runnable + pattern expander + approval queue

**Authority:** `none` (sandbox authoring). **verifier_status:** `UNVERIFIED` — advisory; no PASS self-minted.
**Date:** 2026-07-09. **Runtime:** Node 24 + tsx. Upgrades the T1–T5 engine.

## Gap this closed (from the CHECK)
The engine ran **1 of 5** first-five checks (broken_link_scan only); the other four were contract-only;
the pattern expander (step 10) and approval queue (step 9) were deferred.

## Added
- **4 runnable checks** — `src/runner/checks/{route_health_check,cta_route_check,auth_entrypoint_check,request_id_visibility_check}.ts` (pure/no-LLM; fetch only the job's target host).
- **Check registry** — `src/runner/checks/index.ts` (`resolveCheck(template_id)` dispatch; `RUNNABLE_FIRST_FIVE`).
- **Pattern expander** — `src/compile/expand.ts` (one contract → N sibling contracts `WC-1a/b/c`, dedup + base-scope drop).
- **Approval queue** — `src/compile/approval.ts` (`buildApprovalItems`: failing receipt → one `ApprovalItem`, ALWAYS `decision:'pending'`; clean receipt → none; never auto-applied).
- **Tests** — `tests/e2e_first_five.test.ts` (6), `tests/expand_approval.test.ts` (5).

## Tests — **39/39 green** (was 28/28)
`stage1 5 · cluster 6 · generate_contract 6 · runner 3 · receipt_selfwrite 4 · e2e_broken_link_scan 4 · e2e_first_five 6 · expand_approval 5`

All five first-five checks run against one fixture and discriminate correctly:
- `route_health_check`: `/` + `/pricing` 200 PASS · `/apply-for-program` 404 + `/login` 500 FAIL → `{4,2,2}`
- `cta_route_check`: CTA present PASS · route 404 FAIL → `{2,1,1}`
- `auth_entrypoint_check`: sign-in present PASS · `/login` 500 FAIL → `{2,1,1}`
- `broken_link_scan`: healthy PASS · 404/500/# FAIL
- `request_id_visibility_check`: no id FAIL · rendered `[data-request-id]` PASS

## Red-canaries (observed RED → GREEN, not tautologies)
- `route_health_check` seeded `passed→true`: **e2e_first_five RED 5/6 (exit 1)** → reverted **GREEN 6/6 (exit 0)**.
- In-test: request_id discriminates (id present/absent); expander drops the base scope + duplicate siblings; a clean receipt yields no approval item; approval items are always `pending` / `decided_by:null`.

## DoD gates (unchanged, still hold)
authority=none · no PASS self-mint · no live host (127.0.0.1 fixtures) · no diff applied / deploy / merge / send · no source copied into SANDBOX · names match `_SPINE_v1.json`.

**Still deferred (honest):** `mobile_responsive_smoke_check` (needs headless render) and offer/pricing copy checks (need a supplied canonical) — `resolveCheck` returns null for these, asserted in test.
