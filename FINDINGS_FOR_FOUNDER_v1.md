# FINDINGS FOR FOUNDER — sandbox audit v1

**Date:** 2026-07-09 · **Source:** sandbox worktree `sg-sandbox` @ `claude/sandbox-build` (advisory; nothing here changed live state).
**What this is:** real problems the B0/B1 verifiers surfaced while building — each proven by a red-capable test against a real on-disk artifact. Advisory only; every fix below is YOUR decision. Nothing was reconciled, deployed, or sent.

Ordered by how much they touch trust / money / founder authority.

---

## 1. A recorded deploy is a FAILED invariant  · `DX-4` · **REVIEW**
- **What:** `receipts/phase0.3-step10a-watched-deploy-receipt.json` has `content_identity_confirmed = false`. The deploy-receipt auditor classifies it **FAIL** and pins the rollback hint to pre-live version `628ebc37-5c66-44e5-9cad-4e05f...`.
- **Why it matters:** a deploy receipt where content identity was never confirmed is not proof the right thing shipped. Whether this is historical/expected or needs action is a judgment only you can make.
- **Your decision:** confirm the live Brain is on the intended version; if this receipt represents an unresolved watched-deploy, decide whether to re-verify or annotate it closed. The auditor (`catalog/builds/DX-4/`) can re-run over all deploy receipts on demand.

## 2. The DLM fence silently drops founder items  · `GV-6` · **FOUNDER-GATED FIX**
- **What:** `decision_language_machine_v1/dlm_apply_map_v1.py` `build_apply_map` with its **default** `partial_batch=True` produced an apply_map that silently drops **51 unvalidated ADVISOR/FOUNDER items** — they are neither applied nor recorded in any `deferred_unvalidated` list.
- **Why it matters:** this is the one place the machine can narrow **Founder-DECIDE** authority (invariant 0.2 / Author≠Subject 0.1) — a genuine FOUNDER_FACT could be classified and dropped without ever reaching your sheet. If a future R3/R4/R5 unlock wires the DLM→P0-PGR bridge (BR-1), that bypass gets industrialized.
- **Status:** GV-6 now **detects and flags** this on any persisted apply_map. The **fix is founder-gated** (I did not touch the fence): either (a) emit an explicit `deferred_unvalidated` list so dropped items are accountable, or (b) block when picks are incomplete. Your call which.

## 3. The live verifier is looser than its own schema  · `BR-4` · **DECISION: source of truth**
- **What:** `workers/github-app-advisory/index.js` `validateArtifactDescriptor` **accepts** `artifact_type = brain_worker_bundle` and **ignores extra fields** — but the schema-of-record `verifier/brain-config-artifact-descriptor-schema-v0.1.json` pins `const knowledge_bundle` and `additionalProperties: false`.
- **Why it matters:** two implementations of the same descriptor contract disagree; the live edge worker is more permissive than the schema you'd point an auditor at. A descriptor the schema rejects would pass the live worker.
- **Your decision:** pick the source of truth and align the other — either widen the schema (if `brain_worker_bundle` is legitimately supported) or tighten the worker. Do not merge live-worker changes without your sign-off (Lock 2).

## 4. No real execution has produced a PASS-eligible receipt  · `GV-1` · **INFORMATIONAL**
- **What:** the only real execution receipt, `receipts/p0pgr/P0PGR-EXEC-M03-...json`, is missing `recorded_at`, `evidence_artifacts`, and `founder_authorization_ref`, and is `quality_state: PARTIAL`. The verifier rejects it — consistent with the receipt's own honest `PARTIAL` self-label.
- **Why it matters:** it confirms the honest state — nothing real has cleared the bar yet. Any future real execution must carry founder-authorization + stored evidence + machine timestamps or GV-1 will (correctly) reject it. This is the brake the R-ladder was missing; it now exists.
- **Your decision:** none required now. When you authorize a real execution, record the founder-unlock receipt under `receipts/p0pgr/founder/` first.

## 5. CHESS manifest points at files that don't exist  · `GV-3` · **LOW-RISK FIX**
- **What:** `SG-Canonical-Library/noetfield-library/CHESS-v2/manifest.json` lists `TOOLS/chess_pass_cli.py` and `TOOLS/README.md`, which are absent — the real CLI lives at `scripts/chess_pass_cli_v1.py`.
- **Why it matters:** a manifest that points at missing files erodes "registry is truth." Cosmetic vs the above, but easy.
- **Your decision:** approve a one-line manifest path correction (append-only edit). I can prepare it as a sandbox proposal on request.

## 6. Loop registry retires triggers it never defines  · `WI-4` · **REVIEW**
- **What:** `SG-Canonical-Library/noetfield-library/P0-FOUNDATION-SPINE/data/machine-process-loops-v1.json` has **7 `retires_trigger_ids`** that resolve to no `trigger_id` defined in `founder-trigger-retirement-registry-v1.json`: `FT-FOUNDER-TIER-ROUTING`, `FT-FOUNDER-MISSION-PICK`, `FT-FOUNDER-VALIDATOR-CHECK`, `FT-DUP-IMPL-FOUNDER`, `FT-FOUNDER-RECEIPT-READ`, `FT-FOUNDER-CI-TRIAGE`, `FT-FOUNDER-UNCERTAINTY`.
- **Why it matters:** these are the founder-touchpoint triggers the machine loops claim to *retire* (automate away). If the retirement registry never defined them, either the loops are retiring triggers that were never ratified, or the registry is missing 7 entries — "registry is routing truth" (L4) is broken either way.
- **Your decision:** confirm whether those 7 founder triggers should be defined in the retirement registry (then add them) or the loops shouldn't claim to retire them (then correct the loop refs). The reconciler (`catalog/builds/WI-4/`) re-checks on demand.

## 7. Four of six census motors are DEAD  · `MO-2` · **HIGH**
- **What:** the dead-motor detector globs each motor's `receipt_glob` against disk and finds **4 of 6 motors produce zero receipts**: `cf_gateway_ops_v1`, `cf_gateway_heartbeat_v1`, `railway_sina_gateway_v1`, `gh_gateway_railway_deadman_v1`. Their globs are prose descriptors ("gateway-ops receipt via Telegram", "gateway_leads insert receipt") with no resolvable on-disk artifact. The 2 path-glob motors (staleness, auth-probe) do produce receipts.
- **Why it matters:** these are your Sina Gateway / Railway gateway motors — the revenue-organ surface. If they emit no receipts, either they aren't running or their proof isn't landing anywhere the census can see. A motor with no receipt is not alive (Living System doctrine).
- **Your decision:** confirm whether these 4 gateway/railway motors are actually running; if they are, give them a real receipt path (not a prose glob) so the census can see them; if they're not, mark them retired. Re-runnable: `catalog/builds/MO-2/`.

## 8. Governance overhead exceeds value-producing work  · `MO-3` · **HIGH**
- **What:** the value-class cost attribution joins your census rules with the newest evidence bundle: **22 of 38 loops (57.9%) are class META**, exceeding GUARD+REVENUE **combined (8 loops)**. This trips your own standing-audit rule ("META cost > value-producing").
- **Why it matters:** most of the machine's motion is *about* the machine (meta/governance) rather than producing guarded outcomes or revenue. That's the exact anti-pattern the ROI/value-class rules exist to catch — the metabolism ladder can't climb if 58% of loops are internal.
- **Your decision:** review the META loops — which can be retired, merged, or converted to GUARD/REVENUE. This is a ROI-rebalancing call, not a code fix. Table: `catalog/builds/MO-3/`.

## 9. All repair candidates reference missing packets  · `MO-4` · **REVIEW**
- **What:** all **5** on-disk repair candidates in `receipts/p0pgr/repair_candidates/` are `UNRESOLVED_PACKET` — the packets they claim to repair are not found on disk.
- **Why it matters:** a repair loop that points at packets that don't exist can't close; the rejection→repair cycle is broken at the reference layer.
- **Your decision:** confirm whether those packets were moved/archived (then fix the refs) or the candidates are stale (then retire them). Re-checker: `catalog/builds/MO-4/`.

## 10. Two dispatch packets carry latent CHESS risk the linter misses  · `BR-3` · **REVIEW**
- **What:** packet `P0PGR-20260708-010` (task says "clean") triggers a CHESS `likely_misread` (clean→delete-capability risk); `P0PGR-20260708-007` (task says "spend") triggers `action=ASK_IF_IRREVERSIBLE`. The packet linter passes both; the CHESS→lint bridge flags them.
- **Why it matters:** these packets would be dispatched as lint-clean, but CHESS says an agent should confirm intent first (the anti-downgrade / irreversible-spend forecast). Wiring the CHESS bridge into the packet path would catch this pre-dispatch.
- **Your decision:** none urgent (nothing is dispatching). If/when the packet path goes live, run BR-3 as a pre-dispatch gate. Bridge: `catalog/builds/BR-3/`.

---

## Recommended order
1. **#2 (DLM fence)** — the only one touching founder authority; decide (a) `deferred_unvalidated` or (b) block.
2. **#7 (4 dead gateway motors)** — HIGH; revenue-organ motors emitting no proof. Confirm running + give real receipt paths.
3. **#8 (META > value)** — HIGH; 58% of loops are governance overhead. ROI-rebalance the META loops.
4. **#6 (dangling triggers)** — 7 founder-touchpoint triggers retired-but-undefined; a registry-truth gap.
5. **#1 (FAIL deploy)** — verify live version; 5-minute check with the auditor's rollback hint.
6. **#9 (unresolved repair candidates)** · **#3 (worker↔schema)** · **#5 (manifest)** — cleanup, whenever.
7. **#4, #10** — no action now; the bar/gate is enforced and ready when the packet path goes live.

**Evidence for every finding:** the named `catalog/builds/<ID>/` dir holds the tool, a red-capable test, a red-run canary, and a receipt. None of these fixes were applied — they await your DECIDE.
