# T1 receipt — Observation extractor + stage-1 schema validator

**Authority:** `none` (sandbox authoring). **verifier_status:** `UNVERIFIED` — this is an advisory
sandbox receipt; it does NOT and cannot mint PASS. Only the Cloud-Factory CF Worker issues PASS.

**Ticket:** T1 (MVP_BUILD_TICKETS_v1). **Date:** 2026-07-09. **Runtime:** Node 24 + tsx.

## Built
- `src/stage1/extract_observations.ts` — pure `Transcript -> Observation[]` via an ordered
  most-specific-first `LEXICON` (injectable). `surface_ref` always `unresolved:*`; no live URL at compile time.
- `src/stage1/validate.ts` — self-contained JSON-Schema-subset validator (no npm deps) enforcing
  `additionalProperties:false`, id patterns `AS-/VN-/TR-/OB-*`, the `defect_kind` closed enum, and the
  AuditSession `anyOf(target_url|target_ref)` rule.
- `fixtures/AS-2026-07-09-fieldaudit/` — `session.json`, `voicenote.json`, `transcript.json`
  (spine `normalization_ops`), golden `observations.json` = `OB-1..OB-6`.
- `tests/stage1.test.ts` — 5 tests, self-contained runner.

## Result
`npx tsx tests/stage1.test.ts` → **5/5 green**.

Acceptance criteria met:
1. Extractor reproduces `OB-1..OB-6` verbatim, incl. the exact defect_kind mapping
   (`apply for pilot…`→`cta_route`, `cookie…`→`legal_footer_link`, `sign-in…`→`auth_entrypoint`,
   `trust brief $12,000 8-week…`→`pricing_claim`, `request ids…`→`request_id_visibility`,
   `web chat ui…`→`web_chat_ux`).
2. Every emitted Observation validates; all `surface_ref` are `unresolved:*`.
3. Validator rejects unknown key / bad id / bad enum / AuditSession missing both target fields.
4. **Red-capable, observed (not a tautology):** seeded `auth_entrypoint→broken_link` in source →
   **RED 3/5 (exit 1)**; reverted → **GREEN 5/5 (exit 0)**. The validator negative (Observation
   missing `needs_translation`) is likewise asserted to reject.

## DoD gates
- [x] All writes confined to `sandbox/products/field-audit-compiler-v1/`.
- [x] No receipt carries `PASS`; no code path mints PASS (extractor/validator only).
- [x] No live/production host fetched; extractor is pure text; fixtures use `{TARGET_URL}` + sandbox-local `audio_ref`.
- [x] No diff applied, no deploy, send, cron unlock, or canonical mutation.
- [x] Object/field/template names + the canonical E2E (`AS-2026-07-09-fieldaudit`, `OB-1..OB-6`) match `_SPINE_v1.json`.

**Next:** T2 (Clusterer + Template selector) consumes this `Observation[]`.
