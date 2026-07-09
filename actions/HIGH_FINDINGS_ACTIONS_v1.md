# HIGH findings — action plan v1

**Date:** 2026-07-09 · Acting on the 3 HIGH findings, tied to R>0. Each has a root cause, a concrete fix, and a clear owner. I prepared everything that isn't your DECIDE; the irreversible/authority parts are left ready for you.

---

## HIGH-1 · Dead gateway motors → **it's a MEASUREMENT gap, not a dead organ**
**Root cause (diagnosed):** all 4 gateway motors have a **prose `receipt_glob`, not a file path** — `"gateway-ops receipt via Telegram"`, `"daily heartbeat with offers_sent/replies"`, `"gateway_leads insert receipt"`, `"deadman /ready probe receipt"`. Their proof lands in **external sinks** (Telegram, the `gateway_leads` DB, /ready probes) that the on-disk census cannot glob. So the census flags them dead even if the workers/Railway service are running — and, critically, **the revenue organ's ROI numerator (offers_sent / replies / leads) is unmeasurable locally**, which is exactly what R>0 depends on.

**The fix (two parts):**
- **YOURS (1 check):** confirm liveness — hit the `health_url`s for the CF gateway worker + `sina-gateway-production` Railway service. Alive vs down decides everything.
- **MINE (on your word):** if alive, build a **gateway census bridge** — a motor that pulls offers_sent/replies/leads counts from the external sinks into a real on-disk census receipt, and replace the prose `receipt_glob`s with the real receipt path. Then MO-2 sees them and the ROI numerator becomes computable. *(I did not change the census entries — that's the fix, pending your liveness check.)*

**Why this is the top move:** you cannot prove the revenue organ is alive today. No proof → no ROI → the metabolism ladder can't climb. This is the closest finding to R>0.

---

## HIGH-2 · META = 58% of loops → **mostly a CLASSIFICATION gap, not pure overhead**
**Root cause (diagnosed):** the value-class rules classify only **9 META / 17 GUARD / 6 REVENUE** task_cells (32 total), but the census has ~38 loops. Loops whose task_cell has **no rule default to META** — so the 22 "META" loops are a mix of *genuinely-meta* loops and *unclassified* ones inflating the number. It's not 22 real governance loops; it's classification debt plus some real overhead.

**The fix (two parts):**
- **MINE (on your word):** run a classification audit — list every unclassified loop and propose its true class (many gateway/verify loops are GUARD or REVENUE, not META). This alone deflates the false META count.
- **YOURS (ROI DECIDE):** for the loops that are *genuinely* META after reclassification, decide retire / merge / convert-to-GUARD-or-REVENUE. That's an ROI call, not a code fix.

**Honest note:** I added 50 governance items this session — I contributed to the META side. The reclassification will show how much of the 58% is real vs debt.

---

## HIGH-3 · DLM fence drops 51 founder items → **fix is ready, it's your approval**
**Root cause (confirmed):** `build_apply_map` with the default `partial_batch=True` puts unvalidated `ADVISOR_REVIEW`/`FOUNDER_FACT` items into `machine_closed_without_founder` **but never into any accountable `deferred_unvalidated` list** — only `DEFER`-classified items get a deferred list. GV-6 detects it; BR-1 refuses to bridge any apply_map that leaks this way. The fix is **one additive line**.

**The fix:** attached as `dlm_fence_deferred_unvalidated.patch` (a unified diff, ready to `git apply`). It adds `"deferred_unvalidated": unvalidated` to the returned map — the exact accountability field GV-6's conformant test expects. **I did NOT apply it** — fence-semantics edits are founder-gated per the locked plan (§0). Your DECIDE: approve the patch (option a, accountability) — or if you prefer option b (hard-block on incomplete picks), flip the default to `partial_batch=False` and I'll prepare that variant instead.

---

## Summary of who does what
| Finding | I've done | Your DECIDE |
|---------|-----------|-------------|
| Gateway motors | root-cause diagnosis + census-bridge fix design | hit the 2 health_urls (alive?) → then I wire the bridge |
| META rebalance | root-cause (classification debt) | approve the reclassification audit → then ROI-decide genuine META |
| DLM fence | **patch ready** (`dlm_fence_deferred_unvalidated.patch`) | approve (a) the patch, or (b) block-default — I apply on your word |

None of these were applied to live/authority surfaces. Say which to execute and I move.
