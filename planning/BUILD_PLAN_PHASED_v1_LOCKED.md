# BUILD_PLAN_PHASED v1.0 — LOCKED

**Status:** 🔒 LOCKED · **Date:** 2026-07-08 · **Worktree:** `sg-sandbox` @ `claude/sandbox-build`
**Scope:** how the 50-idea buildable catalog gets built in the sandbox, in 5 phases.
**CHESS verdict:** `PROCEED_WITH_PATCH` — passed the P0-DOCTRINE CHESS machine (CLI) + a 5-lens adversarial forecast (all 5 lenses `PROCEED_WITH_PATCH`). No `BLOCK` (forbidden; this is reversible work).
**Provenance:** CLI skeleton `./chess_machine_skeleton.json` · full 5-lens forecast + synthesis `./chess_forecast_full.json` (workflow `wf_7cea234c-2b1`, 6 agents). Catalog: `../FULL_CATALOG.md`.

> This plan is the patched move. It is not authority over the catalog; it is the locked *order and guardrails* for building it. Reversible — removal is free (0.6).

---

## 0. Founder DECIDE queue — do NOT execute without Sina
These crossed an irreversibility / authority line in the forecast. Everything else proceeds.

| Item | Why it's founder-gated | Sandbox-safe alternative (allowed) |
|------|------------------------|-------------------------------------|
| **CO-4b** — wiring overclaim enforcement to live `trustfield.ca` / the TrustField-Technologies repo | Live venture, separate not-yet-incorporated entity, RPAA/MSP/PSP regulatory-status teeth (Locks 2/9; invariant 0.2) | **CO-4a** — offline block-pattern engine + dry-run report over a *checked-in fixture copy* of the copy, banner: "lint result, not a legal/compliance determination" |
| **DLM fence-semantics edits** — `build_apply_map` (BLOCKED_UNVALIDATED branch, `machine_closed_without_founder`, `partial_batch` default) and the `classify_item` early-return (L65-69) | Editing these silently narrows Founder DECIDE / Author≠Subject (0.1/0.2) | **GV-6** *detects and flags* the leak without editing the fence; the fix is proposed to the founder, never applied in-sandbox |

---

## 1. Global patches — apply to EVERY build step (from the CHESS pass)

1. **Receipt-origin stamping.** Every sandbox verifier/auditor/motor stamps `origin=sandbox-advisory`, `authority=none`, verdict vocab `CHECK_OK` / `CHECK_REJECTED` — **never `PASS`**. Namespace any DLM stage `decision:PASS` as `STAGE_OK` in fixtures so no reader conflates a sandbox self-check with a promotion-gate PASS.
2. **Negative-proof rule (anti-theater).** Every verifier/linter/harness ships a **red-capable fixture built by minimal mutation of a real on-disk artifact** (flip one field) **plus a committed red-run canary**. Green-by-construction (golden-only snapshots, always-exit-0 linters) is rejected. Positives are minimally-mutated *conformant* artifacts — never strawmen, never schema-relaxed to pass.
3. **Live surfaces are out of bounds for automated calls.** No agent call to any live URL (`*.workers.dev`, `*.supabase.co`, `trustfield.ca`, GitHub App `api.github.com`). Run gate/verifier code with CF/Supabase secrets **absent from env** and `HOME` on a temp dir. **Never** invoke `promotion_gate.py` with `--deploy-command/--confirm-each-time/--semi-auto/--autonomous`. **Never** `git push` the worktree (Locks 1/2/3/6/9).
4. **Anti-downgrade.** "simplify / clean / wire / externalize" = improve clarity **without removing working capability**. Externalization is **additive-parity**: load the JSON and assert the set is byte-identical to the hardcoded source-of-truth **before** removing any constant; keep the constant as fallback. No removals unless explicitly named.
5. **Append-only.** Consume/annotate orphaned JSONs and the 92 `*.language_gate_review.json` sidecars **in place**; never delete or rewrite them (Lock 5).

---

## 2. The 5 phases (locked order, each `PROCEED_WITH_PATCH`)

### Phase B0 — LOCK THE BOARD  *(harnesses + cheap validators; no behavior change)*
**Items:** TH-1, TH-2, TH-3, TH-4, TH-5→(B1), TH-6, GV-3, GV-4, GV-5, WI-7 · **plus DX-3 pulled in (see edges)**
**Key patches:**
- **TH-1** asserts the **specific refusal-cause string** from `refusal_reasons()`/`independence_refusal_reasons()` — never `returncode==2` alone (overloaded). Add a conformant-PASS **positive control** that reaches `APPROVED_DRY_RUN` exit 0. Run **flagless, CF tokens unset, HOME=temp** — never any deploy flag.
- Every B0 harness ships a **red-capable fixture + a committed red-run canary** and hand-asserts ≥1 correct value. Linters (GV-4/GV-5/WI-7) **exit nonzero on any hit** and prove RED-before-GREEN on a seeded bad ref (not the `audit_*` always-exit-0 pattern).
**Exit gate:** all harnesses green on **current** behavior **AND** each ships a red-capable fixture + ≥1 hand-asserted value. Commit + **freeze** TH-1/TH-2/TH-3 goldens.

### Phase B1 — TRUST SPINE  *(verifiers, each proven by a rejected real bad)*
**Items:** GV-1, GV-2, GV-6, BR-4, DX-4, TH-5 · **order: GV-2 → BR-4**
**Key patches:**
- **GV-1** runs against the **real** `receipts/p0pgr/P0PGR-EXEC-M03` and records `CHECK_REJECTED` (missing `founder_authorization_ref` / `evidence_artifacts`, `quality_state=PARTIAL`). Forbid relaxing any schema field to pass a synthetic good. Emit a **new** verdict receipt beside M03 (never edit it, Lock 5); report `AUDITOR_DISAGREES_WITH_GATE`, never its own PASS.
- **GV-6** validates a **persisted** `apply_map.json` (never re-calls `build_apply_map`), **ignores** the self-emitted `decision`, tests the **default `partial_batch=True`** path, asserts `machine_closed` never intersects `picks`, and flags dropped unvalidated items. Does **not** relax to pass current behavior.
- **BR-4/TH-5** run lifted JS validation functions against **local committed fixtures only** — never curl the live worker `/run` (mints a real token + overwrites live KV). `index.js` stays subject-of-record, unedited.
- **DX-4** re-implements gate success logic in a **fresh read-only module** (or reads the written receipt) — never invokes the gate with deploy flags. Adds the recorded `FAILED_INVARIANT` deploy (`phase0.3-step10a`) as a fixture that **must** classify FAIL.
**Exit gate:** each verifier reproduces a minimally-mutated known-good **AND** rejects a minimally-mutated real known-bad.

### Phase B2 — RECOVER ORPHANED INVESTMENT  *(wiring)*
**Items:** DX-3 (front), WI-1, WI-2, WI-3, WI-4, WI-5, WI-6
**Key patches:**
- **WI-1/WI-3** intent-classify **each** overlay entry before wiring: allow-terms → allowlist; **`CONFLICT_PHRASE` and `REGULATORY_COPY_RISK` stay BLOCK** (explicitly excluded). Add a regression assert: a known RPAA/MSP/PSP overclaim still returns FAIL, a legitimately-undefined term still WARNs (anti-downgrade). Never touch the `OVERCLAIM_PATTERNS` escape hatch.
- **WI-6** additive-parity: assert the JSON-loaded set is **byte-identical** to the hardcoded sets before removing any constant; keep constants as fallback when `SUPPLEMENT_PATH` absent; reset runtime caches in the test.
- **DX-3** swaps the pinned `REPO=…/sina-governance-SSOT` constant for a `git-rev-parse`/bundle-relative resolver so sandbox dashboards read `sg-sandbox` — **do not delete** the `.app` bundles.
- **WI-4** exits nonzero on a dangling `retires_trigger_ids` ref; prove RED on a seeded ref then clean.
**Freeze-order gate:** WI-1/WI-3/WI-6 land **only after** the B0 golden freeze. A post-wiring golden diff means **INVESTIGATE, never re-baseline to pass.**

### Phase B3 — FUSE THE BRAINS + CLOSE LOOPS  *(bridges + motors)*
**Items:** BR-1, BR-2, BR-3, MO-1, MO-2, MO-3, MO-4, MO-5, MO-6, MO-7, MO-8
**Key patches:**
- **BR-1** consumes **only a GV-6-passed `apply_map.json`** (refuses raw `dlm_classify`/`.processed.json`); bridges only `MACHINE_VALIDATABLE` + advisor items in `validated_picks`; **excludes `FOUNDER_FACT`** and unvalidated advisor items; hardcodes `status=DRAFT`, `dispatch_now=false` regardless of apply-map status; emits a `machine_closed_without_founder` manifest for founder eyes.
- **B3 sub-gate:** every BR-1 packet passes **GV-1 receipt-verify AND BR-3 packet-lint** *before* MO-1 clusters the outbox into `TPL-*` templates; MO-1 uses a literal `DRAFT` default and a lint rejecting any non-DRAFT status. `dispatch_now`/`AUTO_DISPATCH_APPROVED`/shadow cron untouched (Lock 1).
- **MO-8** keeps the queue `[]` on disk, runs only against a **synthetic** draft (`example.com`), hardcodes `founder_blocked=true`, asserts highest state = `founder_blocked`, calls **no** send/broadcast/batch tool (Lock 7). Output labelled "readiness score, NOT send authorization."
- **MO-6** derives metrics from **local** census/receipt JSON only (no live Supabase); keeps the "unknown if underivable" contract; **appends** a new timestamped receipt (Lock 5/6).
- **MO-2/MO-7** exit nonzero on a hit; MO-7 needs a positive-control surface containing a stale-law pattern so a zero-hit can't be a broken-regex false-clean.

### Phase B4 — SURFACE + SELL + GUARD  *(dashboards + commercial + report-only CI)*
**Items:** DX-1, DX-2, DX-5, DX-6, DX-7, DX-8, CO-1 (parallel lane, see edges), CO-2, CO-3, **CO-4a only**, CO-5, CO-6, CI-1..CI-5
**Key patches:**
- **CI-1..CI-5:** `permissions: contents:read` only; trigger on `pull_request` (**never** `pull_request_target`/`push`/`schedule`); **no** `secrets:`/`env:` credential refs; scripts run report-only (`--json`, never `--write-*`); findings → job summary; non-blocking, no auto-merge (Lock 4). CI-4 ships `install_git_hooks.sh` as a founder-run CLI — **do not** set `core.hooksPath` (Lock 8). Never touch `brain-loop-autorun-v1.yml` (Lock 3).
- **CO-4a** (offline only): dry-run `REGULATORY_COPY_RISK` report over a **checked-in fixture copy**, banner "lint result, not a legal/compliance determination; publishing is founder-gated." Author **no** RPAA/FINTRAC/MSB status assertions. (CO-4b → founder queue.)
- **Lock-10 on every CO/DX HTML:** write to a local `out/` path with a visible **"DO NOT PUSH — not for public hosting"** banner; no Cloudflare/Railway/Vercel. CO-1/CO-2 render Tier-3/Tier-4 as **LOCKED/proof-gated**, never available, and must pass `language_gate` over their own generated HTML before "done" (dogfood the overclaim guard).
- **CO-3** hardcodes the synthetic fixture path; watermark every `leak_rate` "SYNTHETIC — not a guaranteed-savings claim."
- **DX-1/DX-2/DX-6/DX-8 + MO-6:** distinguish **EMPTY-SINK / STUB / STALE from CLEAN** — render `unknown`/null/empty with an explicit `UNPOPULATED`/freshness badge, never as `0`/blank that reads all-clear.
**Exit gate:** dashboards render with **per-source freshness + empty-vs-clean distinction**; ≥1 client-receivable deliverable (CO-1) rendered before B4's non-commercial breadth is counted done.

---

## 3. Dependency edges (adopted from the sequencing lens)
```
B0 golden freeze ──► WI-1 / WI-3 / WI-6            (never re-baseline after wiring)
DX-3 (de-pin) ──► DX-1 / DX-2 / DX-6               (dashboards must read sg-sandbox, not the pinned SSOT clone)
GV-2 ──► BR-4                                       (parity needs the Python validator first)
GV-6 ──► BR-1 ──► {GV-1 receipt-verify + BR-3 lint} ──► MO-1   (fence → bridge → verify → cluster)
WI-3 ──► CO-1 / CO-2 / CO-3                         (product overlay makes the sellable docs gate-clean)
CO-1 = parallel REVENUE lane, starts right after B0 (do not starve R=0 behind ~35 plumbing ideas)
```
**Locked sequence:** `B0 → (B1 ∥ CO-1 lane) → B2 → B3 → B4`.

---

## 4. Residuals (non-blocking, tracked — not resolved this plan)
1. DLM `classify_item` early-return (L65-69) can mis-route a real `FOUNDER_FACT`; fix is founder-gated → BR-1's `FOUNDER_FACT` exclusion is the only mitigation, path stays documented-open.
2. `build_apply_map` fence-gap: dropped items surfaced nowhere in the default path; GV-6 **flags** but the additive fix is founder-gated → not closed this phase.
3. No conformant known-good execution receipt exists on disk (M03 is PARTIAL); GV-1's positive proof rests on a minimally-mutated synthetic until a real one is emitted.
4. Two-move push latency: local commits that later merge to `main` could feed the 30-min autorun; mitigated only by no-push discipline (Lock 9).
5. Dashboard freshness badges must be verified rendering on a deliberately-empty source, else stub sinks can still read all-clear.
6. Shared `receipts/` bus: origin stamping only works if every reader honors the marker.
7. CO-4a lint PASS could be socially misread as compliance sign-off despite the banner; the regulatory determination stays founder-only.

---

## 5. Lock
**v1.0_20260708** · locked after CHESS `PROCEED_WITH_PATCH` (machine + 5 lenses). Evidence: `./chess_machine_skeleton.json`, `./chess_forecast_full.json`, receipt `./CHESS_RECEIPT_build_plan_v1.md`. Reopens only on a new fact (0.4). First build: **B0 · TH-1**.
