# WHAT WE CAN BUILD HERE — Full Buildable Catalog v1.0

**Compiled:** 2026-07-08 · **Worktree:** `sg-sandbox` @ `claude/sandbox-build` (isolated) · **Owner:** Sina Kazemnezhad
**Provenance:** recovered from workflow `wf_87df5806-0c5` (13 agents: 11 subsystem mappers + synthesis + completeness critic), then critic-merged into one document. Raw evidence in `./source/`.
**Status:** advisory proposal. Nothing here is authority until reconciled into its owning repo. Sandbox artifact — never emits PASS.

---

## 0. How to read this

- **~50 buildable ideas**, every one grounded in a real asset already on disk (see `Builds on`), across **8 categories**.
- Each idea has a **stable ID** (e.g. `GV-1`). Say *"build GV-1"* and I know exactly what you mean.
- **Effort:** S (hours) · M (a session) · L (multi-session). **Value:** low / med / high.
- **Every idea below is Phase-0 safe** (read-only / advisory, no locked execution, no live deploy, no merge, no delete) unless explicitly flagged `⚠`. The locks that make that true are in §4.
- The single highest-leverage seam the first pass missed is **Category A — Cross-Subsystem Bridges**. Start there or at the Top Picks (§2).

---

## 1. The kit (existing machinery)

| Layer | Capability | State |
|-------|-----------|-------|
| **Dispatch brain (P0-PGR/PDR)** | Governed prompt-authoring + delivery loop: evidence reader, packet linter (7 semantic + P0-leak checks), shadow cycle (route-decision-only), campaign planner (10 packets/6 axes + CHESS), deterministic ROI ranker. Contract v1.1. | Phase-0 shadow live + 10/10 tests; Phase-2 cloud-only ROI track founder-unlocked, executed twice (0 sends/deploys). Registry data file, receipt verifier, repair re-linter all **UNBUILT**. R3 cron / R4 / R5 **LOCKED**. |
| **Decision Language Machine (DLM)** | LLM-free 8-stage pipeline: messy backlog → normalize → plain-English → dictionary check → cluster → classify (MACHINE/ADVISOR/FOUNDER_FACT/DEFER) → reduced founder sheet → validation-fenced apply-map. Per-stage JSON receipts. | Live end-to-end (8 sample runs committed); rule-based regex tuned to one corpus, **no regression harness**, md-only render. |
| **language_gate** | Fail-closed terminology gate: 225-term dictionary, regex lint for retired aliases/banned register/overclaims, deterministic plain-English rewrite, per-scan receipts, exit 1 on FAIL. | Core engine live. Two overlay indexes (165 entries) **ORPHANED**, no test harness, six allowlists hardcoded in Python. |
| **D4 verifier + promotion gate** | Trust boundary between sandbox candidate and live Worker: independent second-account CF verifier emits account-independence receipts; `gates/promotion_gate.py` (763 lines) refuses deploy unless every invariant passes. | Gate LIVE + exercised (caught a content-identity mismatch). Autonomous path LOCKED. `verifier/` side is v0.1 SPEC/scaffold — enforcing validator lives only in the remote Worker. |
| **scripts/ motor layer (50 files)** | Receipt-emitting deterministic motors: brain autorun, P0-PGR shadow pipeline, weekly census + staleness, auth probes, receipt-ledger audit, chess-risk pre-check. Registry-driven, mostly no-LLM ($0). | Mixed: autorun/census/staleness/auth-probe LIVE+scheduled; p0pgr_* shadow-only. `write_roi_heartbeat` emits all-'unknown' stub; `audit_*` always exit 0 (surface, never gate). |
| **Edge worker + Supabase census** | CF Worker independent verifier (GitHub App token, SHA256 recompute, account PASS proof) + WORKFLOW_CENSUS schema (per-loop rows + weekly GREEN/YELLOW/RED rollups) into Supabase. | Both LIVE on locked surfaces. Editing `index.js` / writing live census is **NOT** sandbox-safe; offline harnesses over the same code/schema are. |
| **Canonical Library P0-P8** | Ratified SSOT of laws/schemas/templates/registries: invariants, machine-loop registry (14 loops), founder-trigger-retirement registry, CHESS schemas, Prompt-Forge compiler, language-layer doctrine. | Live/ratified (143-file manifest, 92 gate sidecars). Spec-complete but **tool-incomplete**: CHESS validator CLI, dictionary index builder, 14 entry_scripts referenced by manifests live OUTSIDE the library. |
| **P9 Pattern Factory + P10 Product** | 7 sellable receipt-backed governance patterns + commercial docs with tiered pricing (Brain Audit, Operational Language Audit, Agentic Cost Governance) + 2 live-product blueprints (Sina Gateway, TrustField). | Definition layer rich + current. Tiers STAGED by proof-gate (Tier-1 sells now, Tier-3 locked). No Brain Coherence Report template, no cost-audit scanner. |
| **State registries + receipt ledger** | Machine-readable truth surface: 16-motor automation registry, alive-doc registry, brain deploy state, value-class rules, stale-law patterns, the full P0-PGR receipt state machine (92 receipts), human decision ledger. | Registries LIVE + written. Stale spots: brain `bundle_sha256=null`, **empty** `governance_stale_pointer_queue` (a ready sink). |
| **Agent skills + macOS audit apps** | 7 Claude Code skills wrapping governance scripts; 4 packaged as read-only `.app` dashboards; pr-conflict-resolver ships an eval harness proving +0.24 pass-rate lift. | Skills live. Only 1 of 4 audit skills has `evals/`; 3 desktop apps **hardcode** the founder's Desktop clone path. |
| **CI + git hooks** | 5 cron/dispatch GitHub Actions (autorun, p0pgr shadow, auth probe, census, staleness) uploading receipts as artifacts; local pre-commit language gate; governance PR template + Copilot rules. | **Zero workflows run on push/PR** — the PR-time gating surface is entirely empty. Pre-commit hook is **INERT** (`core.hooksPath` unset). |

---

## 2. Top picks (highest leverage)

| # | Pick | ID | Why |
|---|------|----|-----|
| 1 | **DLM → P0-PGR packet bridge** | `BR-1` | *Critic's strongest.* DLM's classified, plain-English, de-duplicated decision items ARE the "problem statement" the P0-PGR packet compiler already consumes. A thin adapter fuses the system's two flagship brains into one messy-backlog → dispatchable-work assembly line. DRAFT/lint-only, dispatch stays false. |
| 2 | **P0-PGR Receipt Verifier (pipeline stage 11)** | `GV-1` | The 12-stage pipeline explicitly names a Receipt Verifier and the schema exists, but no script implements it. It's the adversarial spine that makes any future real execution trustworthy. 100% read-only. |
| 3 | **M07 prompt-registry data file + template compiler** | `MO-1` | The single widest-open plug point: schema built, data file absent. Converts one-off prompt-writing into a reusable asset — the unit of future autonomy — while every template ships `DRAFT`, never `AUTO_DISPATCH_APPROVED`. |
| 4 | **Wire the orphaned language_gate overlay indexes in** | `WI-1` | 165 entries across two overlay JSONs are fully built but nothing loads them. One merge-point change recovers the whole investment and kills the UNDEFINED_TERM noise. Highest value-per-line available. |
| 5 | **Promotion-gate "refusal teeth" pytest harness** | `TH-1` | A next-step the repo wrote for itself and stated is offline-safe. The gate is the load-bearing deploy trust boundary, yet nothing regression-tests that it actually refuses bad receipts. |
| 6 | **"Brain Coherence Report" Tier-1 deliverable template** | `CO-1` | The only near-term-revenue pick: brain-audit is the "sellable NOW" offer but is prose. A self-contained HTML report with the 7 diagnostic sections turns the offer into something a client receives. |

---

## 3. Buildable ideas by category

### A. Cross-Subsystem Bridges — *the seam the first pass missed*
The synthesis treated all subsystems as silos. The biggest leverage is fusing them: the output of one flagship brain is the input another was built to consume. All files-only, Phase-0 shadow.

| ID | Idea | Builds on | Effort | Value |
|----|------|-----------|:------:|:-----:|
| **BR-1** | **DLM → P0-PGR packet bridge** — adapter feeds DLM classifier output (MACHINE_VALIDATABLE items + advisor clusters) into the P0-PGR packet compiler as DRAFT, lint-clean packets | `dlm_classify_v1.py` + `dlm_apply_map_v1.py` output → `scripts/p0pgr_campaign_planner_v1.py` `compile_packet()` / `p0pgr_packet_lint_v1.py` | M | high |
| **BR-2** | **DLM → language_gate dictionary-fix emitter** — batch DICTIONARY_FIX_NEEDED / ALIAS_RETIRED into a dictionary *proposal* file (not a write) | `dlm_terms_v1.py` statuses (80-item fixture surfaces ~62 fix-needed terms) → `language_gate/dictionary_index.json` | S | high |
| **BR-3** | **CHESS → packet-lint bridge** — run chess_pass over a packet's task/context text, inject `likely_misread`/`IRREVERSIBLE_HINTS` as extra REPAIR_CANDIDATE reasons before routing | `scripts/chess_pass_cli_v1.py` + `scripts/p0pgr_packet_lint_v1.py` reasons list | S | med |
| **BR-4** | **Node ↔ Python verifier parity / differential test** — assert the from-scratch Python bundle validator and the lifted CF-worker JS functions agree on identical receipt fixtures | `GV-2` output + `workers/github-app-advisory/index.js` functions, cross-checked on step6/step8 fixtures | M | high |

### B. New Gates & Validators — *turn prose specs into executable checks*
The most recurring gap: a spec/schema is treated as authority, but the enforcing code lives remotely, in a comment, or nowhere.

| ID | Idea | Builds on | Effort | Value |
|----|------|-----------|:------:|:-----:|
| **GV-1** | **P0-PGR Receipt Verifier (pipeline stage 11)** — jsonschema + provenance checks (executed_at vs created_at, founder_authorization_ref, evidence present, non-bare-$0), emit verdict receipt | `p0-pgr/P0_EXECUTION_RECEIPT_SCHEMA_v1.json` + a real exec receipt (no `scripts/p0pgr_receipt_verify_v1.py` exists) | M | high |
| **GV-2** | **Executable knowledge-bundle + three-hash validator (offline D4)** — reproduce sorted-keys/compact-separator path→SHA256 rule, self-check against a local fixture bundle | `verifier/knowledge-bundle-spec-v0.1.md` + `brain-worker-code-spec-v0.1.md` + `brain-config-artifact-descriptor-schema-v0.1.json` | M | high |
| **GV-3** | **In-library CHESS pass validator CLI** — close the dangling `TOOLS/` reference; assert schema + no-BLOCK | `SCHEMAS/chess_pass.schema.json` + `CHESS-v2/manifest.json` | S | high |
| **GV-4** | **Registry cross-consistency linter** — cross-join motor_ids; print any id present in one registry but missing in another | `data/github_automation_registry_v1.json` + `data/automation_surface_inventory_v1.json` + `receipts/p0pgr/evidence/evidence-*.json` | S | high |
| **GV-5** | **Sandbox-registry gate-profile linter** — iterate rows asserting each field the gate reads | `data/brain_domain_sandboxes_v1.json` + `apply_sandbox_profile()` in `gates/promotion_gate.py` | S | med |
| **GV-6** | **DLM apply-map round-trip validator** — assert every ADVISOR/FOUNDER_FACT id is in picks or missing_ids, machine_closed never overlaps picks, status never a FORM_OFFICIAL auto-submit *(hardens DLM's one governance fence)* | `dlm_apply_map_v1.py` `build_apply_map`/`load_validated_picks` (no `dlm_verify_apply_map_v1.py` exists) | S | high |

### C. Test & Eval Harnesses — *lock current behavior before anyone tunes it*
Multiple live subsystems are rule-based (regex, allowlists, factor tables) with NO regression guard. Golden/pytest harnesses are the cheapest way to make the fragile parts safe to edit.

| ID | Idea | Builds on | Effort | Value |
|----|------|-----------|:------:|:-----:|
| **TH-1** | **Promotion-gate "refusal teeth" pytest harness** — craft a non-PASS receipt fixture, assert the gate REFUSES with exit 2 | `gates/promotion_gate.py` `refusal_reasons()`/`independence_refusal_reasons()` + `verifier/step7-manual-live-deploy-note-v0.1.md` | M | high |
| **TH-2** | **DLM classifier golden-fixture eval** — snapshot current classification counts as the golden baseline | `dlm_classify_v1.py` + `test_fixtures/*.json` + `write_stage_receipt` | M | high |
| **TH-3** | **language_gate pytest regression harness** — capture current decision+findings per fixture as asserts | `language_gate/test_files/*` + `decide()`/`run_pipeline()` | S | high |
| **TH-4** | **Three missing skill eval suites** — author scenarios for the 3 audit skills lacking `evals/` | `skills/pr-conflict-resolver/evals/*` (only skill with evals) | M | high |
| **TH-5** | **Offline receipt-replay verifier harness** — lift the pure validation functions from the CF worker into a scratch test module, feed captured non-PASS fixtures | `workers/github-app-advisory/index.js` validation fns + `receipts/*.json` | S | high |
| **TH-6** | **Prompt-Forge deterministic snapshot harness (--no-llm)** — capture `--no-llm --demo` output as golden | `P5-LINE-ENGINE/reference-code/prompt_forge_pipeline_v1.py` | S | med |

### D. Automation Motors & Closed Loops — *finish the half-built loops*
Several motors emit work items nothing re-reads, or emit stub/unknown metrics. Close them using the already-present receipt buses. Deterministic, no LLM, $0.

| ID | Idea | Builds on | Effort | Value |
|----|------|-----------|:------:|:-----:|
| **MO-1** | **M07 prompt-registry data file + template compiler** — cluster outbox packets by problem_class, draft one DRAFT-status TPL-* template with parameter slots | `p0-pgr/P0_PROMPT_REGISTRY_SCHEMA_v1.json` + `receipts/p0pgr/outbox/*.json` (10) + `p0pgr_packet_lint_v1.py` | M | high |
| **MO-2** | **Dead-motor detector** — glob each census receipt_glob against `receipts/`, list globs with zero recent matches | `scripts/workflow_census_v1.py` + `data/workflow_census_extensions_v1.json` | M | high |
| **MO-3** | **Value-class cost attribution table (designed move M06)** — join value_class_rules with evidence census, print cost grouped by value_class | `data/workflow_census_value_class_rules_v1.json` + `receipts/p0pgr/evidence/evidence-*.json` | M | high |
| **MO-4** | **Repair-candidate re-linter** — re-run the packet linter against a rejected candidate's referenced packet, diff the reasons | `scripts/p0pgr_packet_lint_v1.py` + `receipts/p0pgr/repair_candidates/` | S | med |
| **MO-5** | **Batch outbox linter** — run the linter over every outbox packet, collect verdicts into one summary | `scripts/p0pgr_packet_lint_v1.py` + `receipts/p0pgr/outbox/*.json` | S | med |
| **MO-6** | **ROI heartbeat populator** — replace one 'unknown' metric (blocker_count) with a real count from receipts | `scripts/write_roi_heartbeat_v1.py` + census receipts | M | med |
| **MO-7** | **Stale-law sweep to populate the empty governance queue** — grep stale-law regexes across ACTIVE surface paths, print hits | `data/stale_law_guard_patterns_v1.json` + `agent_read_surfaces_v1.json` + `governance_stale_pointer_queue_v1.json` | S | med |
| **MO-8** | **Commercial-pulse dispatch-check dry-run (designed move M05)** — score the 8 dispatchability_predicates over a labeled test draft, emit per-predicate readiness | `scripts/commercial_pulse_dispatch_check_v1.py` + `data/commercial_pulse_queue_v1.json` (send stays founder_blocked) | S | med |

### E. Wiring & Data-Externalization — *connect built-but-orphaned assets*
Assets fully built to a stable schema that nothing loads, or vocabulary hardcoded in Python where it should be reviewable data.

| ID | Idea | Builds on | Effort | Value |
|----|------|-----------|:------:|:-----:|
| **WI-1** | **Wire the orphaned language_gate overlay indexes in** — fold SourceA overlay COMMAND_FRAGMENT/STATUS_LABEL classes into the allowlist behind a test | `sourcea_dictionary_overlay_index_v1.json` + `trustfield_dictionary_overlay_index_v1.json` + `effective_structural_allowlist()` | M | high |
| **WI-2** | **In-gate read-only library scan runner** — globbing runner that emits the library_scan details schema over test files | `receipts/…library_scan.*.details.json` schema + `scan()`/`decide()` | M | high |
| **WI-3** | **NOETFIELD product-dictionary overlay (+ machine index)** — author the commercial-term overlay that clears the open UNDEFINED_TERM sidecar backlog (Brain Coherence Report, Managed Deterministic Brain, BaaS HOLD…) | P9/P10 `*.language_gate_review.json` sidecars (5 in P9) + `SOURCEA_DICTIONARY_OVERLAY_v1.md` pattern | M | high |
| **WI-4** | **Static reconciler + autonomy scoreboard over the two P0 registries** — assert every `retires_trigger_ids` resolves, print dangling refs | `machine-process-loops-v1.json` + `founder-trigger-retirement-registry-v1.json` | M | med |
| **WI-5** | **Externalize the Phase-2 rank factor table** — serialize FACTORS/WEIGHTS to data JSON, load back, assert identical ranking | `scripts/p0pgr_phase2_rank_v1.py` FACTORS/WEIGHTS | S | med |
| **WI-6** | **Externalize the six hardcoded language_gate allowlists to JSON** — dump the constants via the existing supplement merge path | `effective_structural_allowlist()` + `dictionary_rc2_supplement.json` | S | med |
| **WI-7** | **Skill-manifest self-linter** — parse each SKILL.md compatibility block, `exists()` each referenced path | the `compatibility:` frontmatter in all 7 `SKILL.md` | S | med |

### F. Developer Experience, Dashboards & Onboarding — *read-only visibility*
Every subsystem emits stable machine-readable JSON that a self-contained HTML page can render. All read-only, all "simple web page, not a deck," none pushed to Cloudflare.

| ID | Idea | Builds on | Effort | Value |
|----|------|-----------|:------:|:-----:|
| **DX-1** | **P0-PGR read-only status dashboard** — ranked queue + gate states + R1-R5 ladder as one static page | `phase1/phase2_scorecard_v1.json` + `phase2_queue_v1.json` + `P0_PGR_CLOUD_ACTIVATION_LADDER_v1.md` | M | med |
| **DX-2** | **Unified "Governance Console"** — compose the 4 auditors into one parent page | the 3 desktop-app `generate.py` scripts + shared STYLE block | M | high |
| **DX-3** | **De-pin the desktop audit apps** — replace the hardcoded REPO constant with a git-rev-parse/bundle-relative resolver so they run on any checkout | REPO constant in the 3 `desktop-app/*/generate.py` (all pinned to Desktop path) | S | high |
| **DX-4** | **Deploy-receipt auditor** — read-only rollup that reproduces the gate's success logic (content_identity_ok, deploy_exit_code, smoke, post_promote) and classifies PASS/FAIL/BLOCKED; surfaces an already-recorded FAILED_INVARIANT deploy on day one | `gates/promotion_gate.py` `write_deploy_receipt()` + `receipts/phase0.3-step10a-watched-deploy-receipt.json` | M | high |
| **DX-5** | **Wording-debt rollup over the 92 language_gate_review sidecars** — tally review reasons per file, ranked HTML table | the 92 `*.language_gate_review.json` sidecars | S | med |
| **DX-6** | **State-surface index dashboard for onboarding** — motors/lanes + census value-class counts on one page | `github_automation_registry_v1.json` + `phase2_scorecard_v1.json` + newest evidence bundle | M | high |
| **DX-7** | **DLM founder sheet as HTML** — add `render_founder_sheet_html()` reading the same dict as the md renderer | `dlm_founder_sheet_v1.py` `render_founder_sheet_md` | S | high |
| **DX-8** | **Weekly founder ROI digest generator (R5 rung deliverable)** — deterministic md/HTML: ranked moves, executed candidates, findings needing founder eyes, held items, running cost/send/deploy counters (push cadence, not a page you visit) | `phase2_queue_v1.json` + `phase2_scorecard_v1.json` + `P0PGR-EXEC-M03` receipt | M | high |

### G. Pattern Factory & Commercial Layer — *turn sellable-NOW prose into deliverables*
P9/P10 are rich definition docs, but the Tier-1 offers that "sell now" have no repeatable deliverable. On synthetic/mock data only, honoring the proof-gate (no Tier-3 claims).

| ID | Idea | Builds on | Effort | Value |
|----|------|-----------|:------:|:-----:|
| **CO-1** | **"Brain Coherence Report" deliverable template + scoring rubric** — self-contained HTML report, one scored section per diagnostic (stack fragmentation, definition drift, agent theater, missing receipts, dead workflows, founder overload, missing decision-spine) | `P9-PATTERN-FACTORY/brain-audit-v1.md` + `brain-as-a-service.md` Tier-1 anchor | S | high |
| **CO-2** | **Pattern Factory catalog / storefront (simple HTML)** — one card per pattern + its P10 pricing | `pattern-factory-index.md` + `brain-as-a-service.md` + pricing docs | S | high |
| **CO-3** | **Tier-1 AI Spend Leak Audit scanner (synthetic data)** — compute leak_rate over a synthetic token-log fixture using the ROI metrics table | `P10/agentic-cost-governance-SSOT.md` ROI table + `agentic-cost-governance-service.md` | M | high |
| **CO-4** | **TrustField overclaim enforcement ⚠** — drive REGULATORY_COPY_RISK / CONFLICT_PHRASE (RPAA MSP/PSP self-claim guards) as block patterns on website/public surfaces; the only idea with direct regulatory-liability teeth for a live venture | `trustfield_dictionary_overlay_index_v1.json` + `OVERCLAIM_PATTERNS`/`block_private` path | M | high |
| **CO-5** | **Signal Factory structural receipt verifier** — encode the output contract as JSON schema, assert author≠subject + score bounds | `P9-PATTERN-FACTORY/signal-factory-v1.md` output contract | S | med |
| **CO-6** | **Gateway lead-intelligence dashboard (mock data only)** — synthesize mock rows, render a priority_tag breakdown | `SINA_GATEWAY_BLUEPRINT_LOCKED_v1.md` §7 backlog + gateway_leads schema §5 | M | med |

> **⚠ CO-4 note:** building the *enforcement logic and a dry-run report* is sandbox-safe; actually gating the live trustfield.ca copy is a founder-gated deploy. Build + prove offline; you decide the wiring.

### H. CI & Hooks — *claim the empty PR/push gating surface*
Templates and rules exist but nothing enforces them; the pre-commit hook is inert. Non-blocking/report-only CI is phase-safe. The locked P0-PGR shadow cycle stays excluded from PR triggers.

| ID | Idea | Builds on | Effort | Value |
|----|------|-----------|:------:|:-----:|
| **CI-1** | **pr-governance-lint workflow** — parser (tested locally) asserting lane + receipt_id + checkboxes from the PR body | `.github/pull_request_template.md` + `copilot-instructions.md` | M | high |
| **CI-2** | **language-gate-ci job** — run the gate pipeline over a PR's changed-file list | `.githooks/pre-commit` + `language_gate_pipeline_v1.py` | M | high |
| **CI-3** | **Reusable validate-receipt composite action** — extract the shadow-cycle's independent-validation jsonschema step into a standalone `action.yml` | `p0pgr-shadow-cycle-v1.yml` validation step + upload-artifact globs | M | high |
| **CI-4** | **git-hooks installer + hooks-present PR check** — `install_git_hooks.sh` sets `core.hooksPath .githooks`, verify pre-commit executable | `.githooks/pre-commit` + unset `core.hooksPath` | S | med |
| **CI-5** | **forbidden-marker PR grep gate** — grep changed files for the forbidden active-config marker, exit 1 on hit | `copilot-instructions.md` forbidden marker | S | med |

---

## 4. Guardrails — the locks that bound everything above

1. **P0-PGR real execution** beyond cloud-only read-only ranking — deploy, merge, cron, auto-dispatch, rungs R3/R4/R5 — is gated behind founder-unlock receipts that do not exist. Never uncomment the shadow-cycle cron, never flip `dispatch_now`, never set `AUTO_DISPATCH_APPROVED`.
2. **Live Cloudflare deploys** — `promote_brain_worker --autonomous-deploy`, `promotion_gate.py execute_deploy_flow`, the live github-app-advisory worker — are founder-gated. Build offline harnesses over the same code/schema.
3. **`brain-loop-autorun-v1.yml`** (every 30m, can deploy when CF secrets present) is a live-deploy boundary — do not modify.
4. **No auto-merge / no self-merge** of any PR.
5. **Never delete artifacts** — rejection is not permission to `rm`; receipts are append-only/immutable.
6. **No writes to live Supabase** — run census/probe scripts in `--json` report-only mode (no `--write-supabase`/`--write-receipt`); use a sandbox DB for census-row work.
7. **No outbound sends** — commercial_pulse send stays `founder_blocked`; dispatch-checks are dry-run/scoring only.
8. **No new `.cursor/hooks` or pre-commit wiring** during gate experiments — ship standalone CLIs.
9. **Deploy fence** blocks dirty-tree pushes; the real www stack is Cloudflare www + Railway backend, never Vercel.
10. **Deliverables are simple self-contained HTML pages, never `.pptx` decks; build the file, never push it live.**

---

## 5. Suggested build sequence

A dependency-aware order — each step leaves a durable, provable artifact:

1. **`TH-1` + `TH-3`** (harnesses first) — lock the gate and the language_gate before touching either. Cheap, and every later change rides on them.
2. **`GV-1`** (Receipt Verifier) — the adversarial spine; unblocks trusting any future execution receipt.
3. **`WI-1`** (wire overlays) — recovers 165 built entries, kills the UNDEFINED_TERM noise that pollutes every gate scan.
4. **`BR-1`** (DLM → P0-PGR bridge) — the fusion play; turns two demos into one assembly line. Do it after GV-1 so its emitted packets can be receipt-checked.
5. **`CO-1`** (Brain Coherence Report) — the revenue-facing deliverable; parallelizable, no dependency on the above.
6. Then breadth: `MO-2`/`MO-3` (close motor loops), `DX-4`/`DX-6` (visibility), `CI-1` (claim the PR surface).

---

*Provenance receipt: `./RECEIPT.json`. Raw 13-agent evidence: `./source/`. This document is advisory; promotion of any idea to a real repo follows the normal proposal → verify → receipt path.*
