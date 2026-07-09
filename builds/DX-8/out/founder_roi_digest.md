<!-- DO NOT PUSH — not for public hosting (advisory founder digest, sandbox receipts) -->
# Weekly Founder ROI Digest — DX-8

> **DO NOT PUSH — not for public hosting (advisory founder digest, sandbox receipts)**

- **As of:** 2026-07-08T13:38:48Z  ·  origin=sandbox-advisory · authority=none · pass_claimed=false
- **Operating mode:** PHASE_2_CLOUD_ONLY_ROI_TRACK
- _DERIVED — advisory, not a guaranteed claim — figures are read from repo receipts; this digest asserts, it does not promise._

## Source freshness

| Source | Timestamp | Age (days) | Badge |
|---|---|---|---|
| `receipts/p0pgr/phase2_queue_v1.json` | 2026-07-08T13:38:48Z | 0.0 | FRESH |
| `receipts/p0pgr/phase2_scorecard_v1.json` | 2026-07-08T13:32:00Z | 0.0 | FRESH |
| `receipts/p0pgr/P0PGR-EXEC-M03-20260708T1330Z.json` | 2026-07-08T13:30:00Z | 0.01 | FRESH |

## Running counters — NO-SEND / NO-DEPLOY invariant

**Invariant status: HELD (all zero)**

| Counter | Value | Status |
|---|---|---|
| cloud_executions | 2 | INFO |
| external_sends | 0 | OK |
| forms_submitted | 0 | OK |
| deploys | 0 | OK |
| merges | 0 | OK |
| authority_changes | 0 | OK |
| p0_leakage_count | 0 | INFO |
| hard_block_count | 0 | INFO |
| runtime_freeze_count | 0 | INFO |
| estimated_cost_usd | 0.0 | OK |

## Ranked moves (ROI queue)

_Weights: {"direct_revenue": 35, "trust_proof": 25, "workload_reduction": 15, "cloud_now": 15, "reversibility": 10}_

| # | Move | Packet | Score | Commercial | Route | Rationale |
|---|---|---|---|---|---|---|
| 1 | M03 | P0PGR-20260708-004 | 86.0 | yes | DISPATCH_CLOUD | Protects live CAD 4k offer + /register funnel; pure external read |
| 2 | M05 | P0PGR-20260708-006 | 74.0 | yes | DISPATCH_CLOUD | Unblocks first compliant outbound pipeline; predicate audit only, zero send |
| 3 | M04 | P0PGR-20260708-005 | 73.75 | yes | DISPATCH_CLOUD | Conversion audit; needs labeled test identity + gating care -> slightly less immediately executable |
| 4 | M02 | P0PGR-20260708-003 | 58.5 | no | DISPATCH_CLOUD | Registry trust underpins all dispatch; repo-evidence sweep |
| 5 | M06 | P0PGR-20260708-007 | 58.5 | no | DISPATCH_CLOUD | ~$20/mo dead-spend recovery + governor enforceability |
| 6 | M07 | P0PGR-20260708-008 | 58.0 | no | DISPATCH_CLOUD | Packet factory; ranked only for its revenue/trust template share per founder rule |
| 7 | M01 | P0PGR-20260708-002 | 54.5 | no | DISPATCH_CLOUD | Census triage; trust recovery, low direct revenue |
| 8 | M09 | P0PGR-20260708-010 | 50.5 | no | DISPATCH_CLOUD | P0 leak sweep; governance trust, no direct revenue |

## Executed candidates

- **M10** — deterministic ROI re-rank (this ranker run)  ·  quality: `PASS`  ·  cost: $0.0
    - receipt: `receipts/p0pgr/phase2_queue_v1.json`
- **M03** — trustfield.ca live-truth audit — 6 GTM routes, claims diff  ·  quality: `PARTIAL`  ·  cost: $0.0
    - F1 CLAIM_AMBIGUITY: CAD 4,000 vs CAD 3,500-prepay wording on /pilot
    - F2 DOC_STALE: repo P10 doc cites build v71, live is v108
    - receipt: `receipts/p0pgr/P0PGR-EXEC-M03-20260708T1330Z.json`

## Findings needing founder eyes

- **F1 [CLAIM_AMBIGUITY]** — /pilot shows both 'CAD 4,000 fixed (2,000 + 2,000)' and 'CAD 3,500 paid in full on signature'. If intentional prepay discount, wording should say so explicitly; a diligence-minded MSB may read it as inconsistent pricing.
    - next: candidate copy-fix packet (deploy-gated, founder-only)
- **F2 [DOC_STALE]** — Repo P10 doc cites build v71 (2026-07-07); live is v108 (2026-07-08). Live is ahead of committed doc — L12 doc-drift, not production drift. No public false claim found.
    - next: candidate hygiene packet: refresh P10 launch-credibility block

**Candidate follow-up packets:**
- F1: /pilot pricing copy-clarity fix (deploy-gated -> FOUNDER_ONLY)
- F2: P10 launch-credibility block refresh (hygiene, cloud-safe)

## Held items

- **M08** (P0PGR-20260708-009) — `HOLD_CLOUD_UNSAFE` — HOLD_CLOUD_UNSAFE: value is Mac-execution planning; founder directive defers all Mac-bound design in Phase 2
- **M10** (P0PGR-20260708-011) — `SELF` — SELF: executed by this script run

## Next in queue

- **M05** (P0PGR-20260708-006) — CASL-safe commercial dispatch readiness (predicate audit, zero send)
    - gates: CLOUD_ONLY + read-only + ROI 74 + no send — eligible under Phase 2 rules

