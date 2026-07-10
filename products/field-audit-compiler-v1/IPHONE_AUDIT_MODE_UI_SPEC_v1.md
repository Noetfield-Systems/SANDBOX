# IPHONE_AUDIT_MODE_UI_SPEC_v1

**Package:** FOUNDER_FIELD_AUDIT_TO_WORKFLOW_COMPILER_v1
**Reads / obeys:** `_SPINE_v1.json`, `VOICE_TO_OBSERVATION_SCHEMA_v1.json`, `RECEIPT_SCHEMA_FIELD_AUDIT_v1.json`
**Status:** authoring artifact — authority=none. This is a UI spec, not a running surface.

---

## 0. What this screen is (and is not)

The iPhone/PWA **Audit Mode** is the founder-facing capture-and-review head of the Voice-to-Workflow Compiler. Its single ergonomic goal:

> **Stand in front of a real page on your phone, SPEAK the defects you see, tag each to what you're looking at, tap once — and get back independently-verified receipts and approval-ready patches. Type almost nothing.**

The app is a **client** of the **sandbox authoring service** (the `/sandbox/products/field-audit-compiler-v1/` bench, authority=none). It renders and edits the exact spine objects — `AuditSession`, `VoiceNote`, `Transcript`, `Observation`, `IssueCluster`, `WorkflowContract`, `SandboxJob`, `VerificationRun`, `Receipt` (`field_audit_receipt_v1`), `ApprovalItem` — and never invents divergent ones.

### Hard authority boundaries the UI enforces (non-negotiable)

Bound to `_SPINE_v1.authority_model`:

- **The UI never deploys, merges, deletes, sends, unlocks a cron, or mutates a canonical repo.** No button in this app does any of those. There is no "Apply to production" control anywhere.
- **The UI cannot mint PASS.** `verifier_status=PASS` is issuable **only** by the independent Cloudflare Worker after it recomputes `summary` from `checks[]` and confirms edge + secondary-CF-account proof. The app is a read-through display of whatever the Worker (or, before adjudication, the sandbox self-write) reports. A sandbox self-write always shows as `verifier_status=UNVERIFIED`, `authority=none`.
- **Every write the app triggers lands inside `sandbox/products/field-audit-compiler-v1/` first.** SandboxJobs may only `inspect` / `patch_diff` / `test` and return receipts. `patch_diff` jobs stage a `diff_ref`; the diff is **never applied** from here.
- **All jobs run only against the founder-supplied `target_url` / `target_ref`** entered per session. The app never hardcodes or fetches a live surface. `trustfield.ca` and the `{TARGET_URL}` E2E chain below are **illustrative** — a worked example baked into the empty-state/demo, not a live run.
- **Canonical change ⇒ approval.** Any `WorkflowContract.risk_class = canonical_change` (and `low_risk_patch` unless an explicitly-scoped low-risk rule is attached) surfaces only as an `ApprovalItem` in the Approval Queue. Approving it records a decision in the sandbox ledger; **it does not execute the change.** Execution is downstream of the factory + an approved item, never from voice and never from this UI.

The app therefore has exactly two verbs it can cause: **capture structured data** and **launch bounded sandbox jobs**. Everything else it does is display, edit-in-place, and record a human decision.

---

## 1. Founder-ergonomics goal → concrete UI consequences

| Ergonomic requirement | UI consequence |
|---|---|
| Speak while looking at a real page | Capture screen is a single full-height **hold-to-talk** button; phone can stay in one hand pointed at the founder's other device/screen. No modal steals focus mid-utterance. |
| Minimal typing | Text is a *fallback*, never the default. All structured fields (`defect_kind`, `severity_guess`, `target_hint`) are pre-filled by the extractor and edited by **tap-to-cycle chips**, not keyboards. |
| Tag a defect to what you're looking at, fast | Per-note `surface_ref` tagging via **paste URL / scan URL (camera) / pick-from-recent-targets**, one tap, without leaving the transcript. |
| Trust the result | Receipts screen shows **evidence, not prose** (http_status, selector, regex expected/actual) and never shows a green PASS the app itself computed. |
| One decision, not a config session | Compile is **one tap**. Approval is **approve / reject / scope**, three buttons, with a diff preview. |
| Works with bad venue wifi | **Offline-first PWA**: capture + transcribe-queue + review work fully offline; compile/verify sync when back online. |

---

## 2. Screen list

Nine screens + two global overlays. Each maps to a slice of `AuditSession.status` ∈ `{capturing, transcribing, extracting, clustered, contracted, verifying, awaiting_approval, closed}`.

| # | Screen | Primary spine objects | Session status it advances |
|---|---|---|---|
| S0 | **Session Setup** (target picker) | `AuditSession` | `→ capturing` |
| S1 | **Capture** (hold-to-talk + text fallback + live transcript + per-note tagging) | `VoiceNote`, `Transcript`, live `Observation` preview | `capturing → transcribing` |
| S2 | **Review — Observations** (edit/confirm/dismiss atomic defects) | `Observation` | `transcribing → extracting` |
| S3 | **Review — Clusters** (cards: merged defects per contract) | `IssueCluster` | `extracting → clustered` |
| S4 | **Compile** (one tap → contracts → launch jobs) | `WorkflowContract`, `SandboxJob` | `clustered → contracted → verifying` |
| S5 | **Results / Receipts** (pass/fail per check + evidence + expansion suggestions) | `VerificationRun`, `Receipt`, `pattern_expansion` | `verifying → awaiting_approval` |
| S6 | **Approval Queue** (diff preview, approve/reject/scope) | `ApprovalItem` | `awaiting_approval → closed` |
| S7 | **Session List / History** | `AuditSession[]` | (navigation) |
| S8 | **Session Summary** (chain view, close-out) | whole session `chain_summary` | `→ closed` |
| G1 | **Sync / Offline overlay** (banner + outbox) | local mutation queue | (cross-cutting) |
| G2 | **Authority banner** (persistent "authoring — no live changes" chip) | — | (cross-cutting) |

Navigation model: a linear **pipeline rail** at the top (Capture → Review → Compile → Results → Approve) reflecting `AuditSession.status`; the founder can move back to any completed stage but forward only when the stage's data exists.

---

## 3. State model

### 3.1 Session-level state machine (mirrors `AuditSession.status`)

```
                 target chosen
   [S0 Setup] ─────────────────▶ capturing
                                    │  (≥1 VoiceNote captured, "Done capturing")
                                    ▼
                                transcribing ──▶ (each VoiceNote gets a Transcript)
                                    │  auto-advances when all notes transcribed
                                    ▼
                                 extracting ──▶ Observation[] emitted, shown in S2
                                    │  founder confirms observation set
                                    ▼
                                 clustered ──▶ IssueCluster[] shown as cards in S3
                                    │  "Compile" tapped
                                    ▼
                                 contracted ──▶ WorkflowContract[] generated (S4)
                                    │  "Launch jobs" (auto after compile)
                                    ▼
                                 verifying ──▶ SandboxJob[] running, VerificationRun[]
                                    │  all receipts returned (UNVERIFIED→adjudicated)
                                    ▼
                              awaiting_approval ──▶ ApprovalItem[] in S6
                                    │  all items decided (approved/rejected/deferred)
                                    ▼
                                   closed
```

The status is **owned by the service**, not the client. The client polls / subscribes and renders. The client may *request* a transition (e.g. `POST …/compile`) but the sandbox service is the writer of `AuditSession.status`.

### 3.2 Per-object review state (client-local, overlaid on server objects)

The founder's edits are **local decorations** until synced. Each reviewable object carries a client `reviewState`:

- **Observation.reviewState** ∈ `{ suggested, confirmed, edited, dismissed }`
  - `suggested` = extractor output as received.
  - `confirmed` = founder accepted as-is.
  - `edited` = founder changed `defect_kind`, `severity_guess`, `target_hint`, or `surface_ref`.
  - `dismissed` = excluded from clustering (kept for provenance, not deleted — append-only).
- **IssueCluster.reviewState** ∈ `{ proposed, confirmed, split, merged, dropped }`.
- **ApprovalItem.decision** is the *server* field (`pending|approved|rejected|deferred`); the client mirrors it and shows an optimistic pending state until sync confirms.

### 3.3 Capture-screen sub-state (S1)

```
  idle ──(finger down on talk button)──▶ recording
  recording ──(finger up)──▶ captured(VoiceNote local) ──▶ queuedForTranscription
  queuedForTranscription ──(online + service)──▶ transcribing ──▶ transcript(shown)
  queuedForTranscription ──(offline)──▶ heldInOutbox (audio blob persisted locally)
  idle ──(tap "type instead")──▶ textEntry ──▶ captured(text pseudo-VoiceNote)
```

A text-fallback note is stored as a `VoiceNote` with `audio_ref` pointing at a sandbox-local text blob and a `Transcript` whose `text_raw = text_normalized` (no ASR); `translated=false`.

### 3.4 Sync state (G1) — see §11.

```
  synced ⇄ pendingPush(outbox n) ⇄ pushing ⇄ conflict(rare) 
  offline ──▶ pendingPush accumulates ──▶ (reconnect) ──▶ pushing ──▶ synced
```

---

## 4. S0 — Session Setup (target picker)

**Purpose:** create the `AuditSession` root and bind the founder-supplied target. This is the *only* place a target is entered; nothing is hardcoded.

**Layout:**
- `surface_kind` selector (segmented control): `website | web_app | dashboard | repo | workflow | other` (from `AuditSession.surface_kind` enum). This choice filters which templates are eligible downstream.
- **Target input** (one of, per schema `anyOf`):
  - For `website|web_app|dashboard`: **`target_url`** — three fast inputs:
    1. **Paste** (from clipboard, auto-detected on screen open),
    2. **Scan** (camera → QR / on-screen URL OCR),
    3. **Recent targets** (list of prior `target_url`s from this founder's sessions).
  - For `repo|workflow`: **`target_ref`** — git ref / repo path / workflow id field.
- Founder id is taken from the session auth context (`AuditSession.founder_id`), not typed.

**Guardrails shown inline:** a persistent note — *"Jobs run only against this target. Nothing here is sent live or deployed."* Bound to `execution_rule`.

**On "Start audit":** create session with `status=capturing`, empty `voice_note_ids`, empty `observation_ids`, `authority="none"`.

**API calls:**
- `POST /v1/sessions`
  → body `{ founder_id, surface_kind, target_url?|target_ref?, created_at }`
  → returns `AuditSession { id: "AS-…", status:"capturing", authority:"none", voice_note_ids:[], observation_ids:[] }`.
- `GET /v1/sessions?founder_id=…&recent_targets=1` (to populate "Recent targets").

**E2E instance:** creates `AS-2026-07-09-fieldaudit`, `surface_kind:"website"`, `target_url:"{TARGET_URL}"`.

---

## 5. S1 — Capture (hold-to-talk + text fallback + live transcript + per-note tagging)

This is the heart of the ergonomic goal. The founder is looking at a real page; this screen must demand almost no visual attention.

### 5.1 Hold-to-talk voice

- **Full-width, thumb-reachable talk button** pinned to the bottom third. **Press-and-hold to record, release to stop** (walkie-talkie). No "start/stop tap" ambiguity; releasing always ends the note, so one utterance = one `VoiceNote`.
- Haptic on down (start) and up (stop). A live **waveform + elapsed timer** confirms capture without the founder looking closely.
- On release: a `VoiceNote` is created locally with `audio_ref` = sandbox-local blob key (never an external URL), `captured_at`, `duration_ms`, detected `source_lang`.
- **Multiple notes per session** are expected and encouraged — the founder walks the page speaking one defect at a time. Each becomes its own `VoiceNote` → `Transcript` → one-or-more `Observation`s.

### 5.2 Live transcript

- As each note transcribes (online) it appears as a **transcript bubble** showing `Transcript.text_normalized` (the deterministic normalization result, e.g. `"twelve thousand dollar"` rendered as `"$12,000"`, `"six week"` as `"8-week"`). A small ⓘ reveals `text_raw` and the ordered `normalization_ops`.
- Non-English capture: if `source_lang != "en"`, the bubble shows `text_translated` with a language chip; `translated=true` is surfaced and later flows to `Observation.needs_translation`.
- Offline: bubble shows *"queued — will transcribe on reconnect"*; the audio blob is persisted in the outbox.

### 5.3 Per-note `surface_ref` tagging (paste/scan URL or pick target)

Each transcript bubble has a **"Tag surface" chip**. This resolves the founder's spoken `target_hint` toward a concrete `Observation.surface_ref`:

- **Paste / Scan URL** → sets `surface_ref` to a route/href relative to the session `target_url` (e.g. paste `/apply-for-program` or scan the page URL).
- **Pick target** → choose from a short list: `route path`, `CSS selector`, `href`, `component name`, or leave as `unresolved:<target_hint>` (the schema-legal placeholder). Never a hardcoded live production URL at compile time.
- Default when untagged: `surface_ref = "unresolved:<target_hint>"` exactly as in the E2E (`"unresolved:Apply for Program link"`).

Tagging is optional at capture time — the extractor and, later, the SandboxJob resolve `unresolved:` hints against the founder's `TARGET_URL`. The chip exists so a founder who *knows* the selector can lock it in one tap and skip a round-trip.

### 5.4 Text fallback

- A small **"type instead"** affordance opens a single text field. Submitting creates a `VoiceNote` (text-backed `audio_ref`) + `Transcript` with `text_raw==text_normalized`, `translated=false`. Used when it's too loud to talk or for a precise selector.

### 5.5 Advancing

- **"Done capturing"** moves session `capturing → transcribing`; the app waits for any queued transcriptions, then auto-advances to `extracting` and navigates to **S2**.

**API calls (S1):**
- `POST /v1/sessions/{id}/voice-notes` (multipart: audio blob + `{ captured_at, duration_ms, source_lang }`)
  → returns `VoiceNote { id:"VN-…", session_id, audio_ref, transcript_id:null }`; appends to `AuditSession.voice_note_ids`.
- `POST /v1/voice-notes/{vn}/transcribe`
  → returns `Transcript { id:"TR-…", text_raw, text_normalized, source_lang, translated, text_translated?, normalization_ops[], confidence }`; back-links `VoiceNote.transcript_id`.
- `PATCH /v1/observations/{ob}` *(pre-tag)* or client-held tag applied at S2 — sets `surface_ref`.
- `POST /v1/voice-notes` with `{ kind:"text", text }` for the text fallback.
- `POST /v1/sessions/{id}/advance` `{ to:"transcribing" }` on "Done capturing".

**E2E instance:** one `VN-1` (the six-clause utterance) → `TR-1` with `normalization_ops` `[number_word_expand, currency_normalize, hyphen_join, punctuation_canon]`, `confidence:0.93`.

---

## 6. S2 — Review: Observations (edit / confirm / dismiss)

**Purpose:** turn `Transcript` prose into the confirmed set of atomic `Observation`s — the compiler's structured unit. Extractor output is heuristic and **unverified**; the founder is the fast human filter.

**Layout:** a scrollable list of **observation rows**, one per `Observation`. Each row shows, as tap-editable chips (no keyboard needed):

- **`raw_span`** (the provenance anchor — exact substring of `text_normalized`/`text_translated`), shown as quoted text, read-only.
- **`target_hint`** (founder's words, editable).
- **`defect_kind`** chip — tap cycles the closed enum: `broken_link, cta_route, legal_footer_link, auth_entrypoint, offer_copy, pricing_claim, request_id_visibility, web_chat_ux, mobile_responsive, route_health, other`. This selects the downstream template 1:1, so it's the most important chip.
- **`severity_guess`** chip — `blocker | high | medium | low | info`.
- **`surface_ref`** chip — the tag from S1, or `unresolved:<hint>`; editable via the same paste/scan/pick control.
- **`confidence`** shown as a subtle bar; low-confidence rows float to the top for attention.
- **`needs_translation`** flag badge when the span came from a non-English transcript.

**Row actions (swipe or buttons):**
- **Confirm** (`reviewState: confirmed`).
- **Edit** any chip (`reviewState: edited`).
- **Dismiss** (`reviewState: dismissed`) — excluded from clustering; kept for provenance (append-only, never hard-deleted).
- **Split** — if the founder crammed two defects in one clause, split into two `Observation`s sharing the `transcript_id`.

**Advance:** "Looks right → Cluster" sends confirmed/edited observations forward; session `extracting → clustered`.

**API calls:**
- `GET /v1/sessions/{id}/observations` → `Observation[]` (extractor output).
- `POST /v1/sessions/{id}/extract` (if not auto-run) → triggers extraction from transcripts.
- `PATCH /v1/observations/{ob}` `{ defect_kind?, severity_guess?, target_hint?, surface_ref?, reviewState }`.
- `POST /v1/observations/{ob}/dismiss`.
- `POST /v1/observations/{ob}/split` `{ spans:[…] }`.
- `POST /v1/sessions/{id}/cluster` (advance to clustering).

**E2E instance:** six rows `OB-1…OB-6` exactly as in the spine —
`OB-1 cta_route (blocker)`, `OB-2 legal_footer_link (high)`, `OB-3 auth_entrypoint (blocker)`, `OB-4 pricing_claim (high)`, `OB-5 request_id_visibility (medium)`, `OB-6 web_chat_ux (medium)`. All `needs_translation:false`.

---

## 7. S3 — Review: Clusters (cards)

**Purpose:** show the deduped groupings that each become **one** `WorkflowContract`. This is where "6 spoken defects → 6 contracts" becomes legible.

**Layout:** a vertical stack of **cluster cards** (`IssueCluster`), each showing:

- **`label`** as the card title (e.g. *"Broken 'Apply for Program' CTA"*).
- **`defect_kind`** badge + resolved **`severity`** (max of member severities).
- **`target_refs[]`** as monospace chips (e.g. `a[data-cta='apply-for-program']`, `/apply-for-program`).
- Member **`observation_ids`** collapsed under a "N observations" expander, each linking back to its S2 row (provenance).
- **`dedup_note`** in small text explaining why observations were merged or kept separate (e.g. IC-4's note that `pricing_claim` was chosen over `offer_copy` because the specific `$12,000 / 8-week` claim is checkable, with an `offer_copy_consistency_check` spawned as a sibling in expansion).

**Card actions:** **Confirm**, **Split** (break one cluster into two), **Merge** (combine two cards — drag one onto another), **Drop** (exclude). Editing a card's `defect_kind` re-routes its template at compile.

**Advance:** the **"Compile all"** button (primary, bottom) is enabled once every card is `confirmed`/`dropped`.

**API calls:**
- `GET /v1/sessions/{id}/clusters` → `IssueCluster[]`.
- `PATCH /v1/clusters/{ic}` `{ label?, defect_kind?, target_refs?, reviewState }`.
- `POST /v1/clusters/{ic}/split` / `POST /v1/clusters/merge` `{ ids:[…] }`.
- `POST /v1/clusters/{ic}/drop`.

**E2E instance:** six cards `IC-1…IC-6` with the exact labels and `target_refs` from the spine.

---

## 8. S4 — Compile (one tap → contracts → launch sandbox jobs)

**Purpose:** the compile step. One tap turns confirmed clusters into deterministic `WorkflowContract`s and launches bounded `SandboxJob`s. This is what makes the product a **compiler, not a chatbot**.

**Flow (single primary action, staged reveal):**

1. **Tap "Compile"** → service generates one `WorkflowContract` per confirmed cluster (template selection is deterministic from `defect_kind`; first-five templates prioritized). Session `clustered → contracted`.
2. **Contracts sheet** appears — one collapsible row per `WorkflowContract` showing:
   - **`template_id`** (e.g. `cta_route_check`), **`target`** `{ target_url|target_ref, scope_selector }`, **`params`**.
   - **`deterministic_checks[]`** as `{ name, logic, pass_condition }` — plain pure predicates, no LLM.
   - **`risk_class`** badge: `read_only` (green), `low_risk_patch` (amber), `canonical_change` (red). Red/amber rows carry an **"approval required"** tag.
   - **`promotion`** `{ factory_category, value_class }` and **`pattern_expansion_rule`** (as a "will also fan to…" preview).
   - **`job_kind`** the launch will use: `read_only` → `inspect`; a patchable defect → `patch_diff` (stages a diff, never applies); a check-only rerun → `test`.
3. **"Launch jobs"** (or auto-launch after a 3s undo window) → creates one `SandboxJob` per contract in the **cat-05 watcher** (`category_id = CAT-05-SANDBOX-WORKTREE-EXECUTION`, `authority="none"`). Session `contracted → verifying`. The app navigates to **S5** and shows live job status.

**Guardrails shown:** a fixed footer — *"Sandbox jobs inspect / stage a diff / test against your target only. No deploy. No send. PASS is issued by the independent verifier, not this app."* Bound to `pass_issuance` + `execution_rule`.

**API calls:**
- `POST /v1/sessions/{id}/compile`
  → returns `WorkflowContract[]` (`WC-…`), each `{ template_id, target{target_url|target_ref, scope_selector}, params, deterministic_checks[], expected_outputs, verifier_logic, pattern_expansion_rule, promotion{factory_category,value_class}, risk_class, approval_required }`; session `→ contracted`.
- `POST /v1/sessions/{id}/launch-jobs` `{ contract_ids:[…] }`
  → creates `SandboxJob[]` `{ id:"SJ-…", workflow_contract_id, category_id:"CAT-05-SANDBOX-WORKTREE-EXECUTION", authority:"none", job_kind:"inspect|patch_diff|test", target, inputs, status:"queued" }`; session `→ verifying`.
- `GET /v1/sessions/{id}/jobs` (poll/subscribe for `status: queued→running→done|error`).

**E2E instance:** compiles `WC-1…WC-6` exactly:
`WC-1 cta_route_check (read_only, REVENUE)`, `WC-2 legal_footer_link_check (read_only, GUARD)`, `WC-3 auth_entrypoint_check (read_only, REVENUE)`, `WC-4 pricing_claim_consistency_check (canonical_change, REVENUE)`, `WC-5 request_id_visibility_check (low_risk_patch, GUARD)`, `WC-6 web_chat_ux_check (low_risk_patch, META)`. Launches `SJ-1…SJ-6` (SJ-1/2/3 `inspect`; SJ-4/5/6 `patch_diff`, each staging a `diff_ref`, none applied).

---

## 9. S5 — Results / Receipts (pass/fail per check + evidence + pattern-expansion suggestions)

**Purpose:** show what the checks found, with **stored evidence, not prose**, and never a self-minted PASS.

**Layout:** one **receipt card** per `field_audit_receipt_v1` (via its `VerificationRun`). Each card shows:

- **Header:** the source contract's `label`, `template_id`, `value_class` badge (`REVENUE|GUARD|META|NONE`), and the owning **`category_id`** (`CAT-09-…` / `CAT-10-…`).
- **Verifier status pill** — the load-bearing element:
  - `UNVERIFIED` (grey) — sandbox self-write, `authority="none"`, **not yet adjudicated**. Shown while the independent CF Worker hasn't ruled. Copy: *"Awaiting independent verifier."*
  - `PASS` (green) — **only** ever rendered when `verifier_runtime="cloudflare_worker"` and the Worker issued it. The app **cannot** produce this pill from client math.
  - `FAIL` (red), `BLOCKED` (amber) with `failures[]` reasons.
  - A small note shows the verifier's **`recomputed` summary** next to the author-claimed `summary`, so any mismatch (which forces FAIL) is visible.
- **Checks list** — one row per `checks[]` entry: `name`, a pass/fail dot (`passed`), the `detail` one-liner (e.g. *"GET {TARGET_URL}/apply-for-program → HTTP 404"*), and an **Evidence** disclosure showing the stored proof object: `url`, `http_status`, `selector`, `regex`, `expected`/`actual`, `match`, and any `artifact_path` / `body_sha256` / `dom_sha256`. No prose stands in for evidence.
- **Diff preview link** for `patch_diff` jobs — opens the staged `diff_ref` read-only (see S6). Labeled *"staged — not applied."*

**Pattern-expansion suggestions:** below the receipts, an **"Expand coverage"** section renders `pattern_expansion[]`: for each `from_contract` it shows the `rule` (e.g. *"fan to ALL CTAs"*), the `expanded_targets[]`, and the `new_contract_ids[]`. A **"Compile expansion"** button re-enters S4 with the expanded contract set (same deterministic path). This turns one spoken defect into surface-wide coverage without more talking.

**Advance:** once every job's receipt has returned, session `verifying → awaiting_approval`; a banner routes to **S6** for anything with `approval_required=true`.

**API calls:**
- `GET /v1/sessions/{id}/verification-runs` → `VerificationRun[]` `{ verifier_runtime, checked_at, summary, verifier_status, value_class, receipt_id }`.
- `GET /v1/receipts/{receipt_id}` → `field_audit_receipt_v1` (full `checks[]` with `evidence`).
- `GET /v1/jobs/{sj}/diff` → read-only staged diff text for `patch_diff` jobs.
- `GET /v1/sessions/{id}/pattern-expansion` → `pattern_expansion[]`.
- `POST /v1/sessions/{id}/compile` `{ expand_from:[contract_ids] }` (re-uses the compile endpoint for expansion).

**E2E instance:** six receipts, **all `verifier_status=FAIL`** (the illustrative surface is genuinely broken), each carrying evidence:
- `WC-1`: `cta_present=true`, `cta_route_resolves=false` (`http_status:404`) → 1/2.
- `WC-2`: `cookie_link_present_and_resolves=false` (href `#`) → 0/1.
- `WC-3`: `auth_entry_present=true`, `auth_route_resolves=false` (`http_status:500`) → 1/2.
- `WC-4`: `price_matches_canonical=false` (`$9,000`≠`$12,000`), `duration_matches_canonical=false` (`5-week`≠`8-week`) → 0/2.
- `WC-5`: `request_id_visible=false` → 0/1.
- `WC-6`: `chat_widget_mounts=true`, `chat_controls_present=true`, `chat_input_labeled=false` → 2/3.
Expansion cards render the spine's `pattern_expansion` fan-outs (e.g. WC-1 → `WC-1a/1b/1c` across `book-demo`/`get-started`/`contact-sales`).

---

## 10. S6 — Approval Queue (diff preview, approve / reject / scope)

**Purpose:** the **human gate**. A verified (or explicitly-scoped low-risk) result becomes an approval-ready item. **Only an approved `ApprovalItem` authorizes a canonical change — never raw voice, and never this UI directly.** Approving records the decision; it does not execute.

**Layout:** a queue of **`ApprovalItem` cards**, sorted by `value_class` then `severity`. Each shows:

- **`title`** (e.g. *"Fix broken 'Apply for Program' CTA route (404)"*).
- **`risk_class`** + **`value_class`** badges, and the justifying **`receipt_id`** (tap → back to the S5 receipt with its evidence).
- **`target`** `{ target_url|target_ref, scope_selector }` the patch would touch.
- **Diff preview** — if `proposed_patch_ref` is set, an inline **read-only unified-diff viewer** of the staged `SandboxJob.diff_ref`. A clear banner: *"Staged in sandbox — approving records your decision; it does not deploy."* Items with `proposed_patch_ref:null` (no diff yet, e.g. AP-1/2/3 canonical route fixes) show *"No patch staged — approval authorizes creating one downstream."*
- **`rationale`** text from the item.

**Three actions per card** (the only decision verbs):
- **Approve** → `decision=approved`, records `decided_by`, `decided_at`. (Downstream factory, not this app, may then act on an approved canonical change.)
- **Reject** → `decision=rejected` with an optional reason into `rationale`.
- **Scope** → narrow/annotate before deciding: adjust `target.scope_selector`, downgrade to an explicitly-scoped low-risk rule where policy allows, or set `decision=deferred`. "Scope" is how a founder says *"yes, but only for this selector / not the whole fan-out."*

**Guardrail:** a persistent footer — *"Approvals are recorded in the sandbox ledger. No change is deployed, merged, or sent from this screen."*

**Advance:** when every item is decided, session `awaiting_approval → closed`; routes to **S8** summary.

**API calls:**
- `GET /v1/sessions/{id}/approval-items` → `ApprovalItem[]` `{ id:"AP-…", receipt_id, workflow_contract_id, title, proposed_patch_ref, risk_class, value_class, target, decision, rationale }`.
- `GET /v1/jobs/{sj}/diff` (render `proposed_patch_ref` read-only).
- `POST /v1/approval-items/{ap}/decide` `{ decision:"approved|rejected|deferred", decided_by, rationale? }` → records decision in ledger; **no execution side-effect**.
- `PATCH /v1/approval-items/{ap}` `{ target:{ scope_selector }, risk_class? }` (the "Scope" action).

**E2E instance:** `AP-1…AP-6`, all initially `decision:"pending"`:
- `AP-1/2/3` `canonical_change`, `proposed_patch_ref:null` (route/500/compliance fixes needing a downstream patch).
- `AP-4` `canonical_change` with staged `…/SJ-4/trust-brief-copy.diff` (update copy to `$12,000 / 8-week`).
- `AP-5` `low_risk_patch` with `…/SJ-5/request-id-display.diff`.
- `AP-6` `low_risk_patch` with `…/SJ-6/chat-input-label.diff`.
Every diff is staged, none applied — matching `chain_summary`.

---

## 11. Offline-first PWA behavior + sync (G1)

**Design principle:** capture and review must work with zero connectivity (founder in a venue, basement, plane). Compile/verify need the service; they queue gracefully.

### 11.1 What works offline

| Stage | Offline capability |
|---|---|
| S0 Setup | Create session locally (temp `AS-local-…` id, reconciled on push). |
| S1 Capture | **Fully offline.** Audio blobs persisted to IndexedDB/Cache Storage; text notes fully local. `surface_ref` tagging works offline. |
| S1 Transcribe | If an on-device ASR model is bundled, transcribe locally into `Transcript`; else hold in outbox, transcribe on reconnect. Normalization (`normalization_ops`) is deterministic and runs locally regardless. |
| S2 Observations | Extraction runs locally if the (deterministic) extractor is bundled; otherwise observations appear on reconnect. Edits/confirm/dismiss are local and queued. |
| S3 Clusters | Local clustering (deterministic dedup) when bundled; else queued. |
| S4 Compile | **Requires service** for authoritative contracts + jobs. Offline: "Compile" is disabled with *"Reconnect to compile & launch jobs."* Contracts can be *previewed* locally (deterministic) but jobs cannot run offline — jobs run in the cat-05 watcher, not on-device. |
| S5 Results | Read-only cache of last-fetched receipts; new verification requires the service + the independent CF Worker. |
| S6 Approvals | Decisions can be recorded **offline** into the outbox and pushed on reconnect (they're just ledger writes; still no execution). |

### 11.2 PWA mechanics

- **Service worker**: app-shell precached; API responses cached stale-while-revalidate for read screens (S5/S6 history). Audio blobs and pending mutations in **IndexedDB**.
- **Installable**: standalone display, home-screen icon, `theme-color`; camera permission for URL scan; microphone permission for capture.
- **Background Sync**: queued VoiceNote uploads, transcription requests, observation/cluster edits, compile requests, and approval decisions flush via the Background Sync API when connectivity returns.

### 11.3 Outbox & conflict model

- The **outbox** is an ordered, append-only local queue of mutations (`create-voice-note`, `patch-observation`, `decide-approval`, …). Bound to the append-only discipline: **the app never deletes server objects** — "dismiss"/"drop" are status flags, not deletions.
- **Sync order:** session → voice notes (with blobs) → transcripts → observation edits → cluster edits → compile → job launch → approval decisions. Server assigns canonical ids (`AS-`, `VN-`, `TR-`, `OB-`, `IC-`, `WC-`, `SJ-`, `AP-`); the client remaps local temp ids.
- **Conflicts** are rare (single-founder authoring) but resolved **server-wins for status**, **client-wins for founder review edits** (the founder's confirm/dismiss/scope intent is authoritative over a stale suggestion). A conflict banner surfaces only when the server object was independently advanced past the client's base status.
- **Sync UI (G1):** a top banner — `synced ✓` / `n changes pending ↑` / `offline — n queued` / `syncing…` — plus an outbox detail sheet listing queued mutations with retry.

**Sync API calls:**
- `POST /v1/sessions/{id}/sync` `{ mutations:[…], base_versions:{…} }` → `{ applied:[…], remapped_ids:{local→server}, conflicts:[…], session:{status} }`.
- Individual endpoints (§4–10) are also called directly when online; `sync` is the batched offline-flush path.

---

## 12. Global authority banner (G2)

A slim, always-visible chip: **"Authoring mode · authority=none · no live deploy/send"**. Tapping it opens a short explainer bound to `_SPINE_v1.authority_model`: where PASS comes from (independent CF Worker only), that all writes stay in `sandbox/products/field-audit-compiler-v1/`, and that canonical changes require an approved `ApprovalItem`. This is the founder's constant reassurance that the phone in their hand cannot break production.

---

## 13. End-to-end walkthrough (the single canonical chain, on the phone)

The illustrative worked example (`{TARGET_URL}`, founder-supplied — not a live fetch):

1. **S0:** Founder picks `surface_kind=website`, pastes `{TARGET_URL}` → `AS-2026-07-09-fieldaudit` (`status:capturing`).
2. **S1:** Holds the talk button and says the six-clause note ("Apply for Program link is broken… web chat UI is bad"). One `VN-1`; live transcript shows `TR-1` normalized to `$12,000` / `8-week`. Taps "Done capturing".
3. **S2:** Six observation rows `OB-1…OB-6` appear pre-tagged with `defect_kind`/`severity_guess`; founder confirms them with taps (no keyboard).
4. **S3:** Six cluster cards `IC-1…IC-6`; founder confirms; taps **Compile**.
5. **S4:** `WC-1…WC-6` generated; jobs `SJ-1…SJ-6` launch in the cat-05 watcher (3 `inspect`, 3 `patch_diff`, `authority=none`).
6. **S5:** Six `field_audit_receipt_v1` cards return **all FAIL** with evidence (404, `#`, 500, `$9,000`/`5-week`, no request-id, unlabeled chat input). Expansion suggestions offer to fan each template across siblings.
7. **S6:** Six `ApprovalItem`s (`AP-1…AP-6`), all `pending`. AP-4/5/6 show staged diffs (`trust-brief-copy.diff`, `request-id-display.diff`, `chat-input-label.diff`) in read-only preview. Founder approves/scopes each.
8. **S8:** Session summary renders the spine's `chain_summary`: *1 voice note → 1 transcript → 6 observations → 6 clusters → 6 contracts → 6 sandbox jobs → 6 receipts (all FAIL as expected) → 6 pending approvals → pattern expansion. No PASS self-minted; no canonical mutation; all diffs staged, none applied.*

---

## 14. API surface summary (client → sandbox authoring service)

All endpoints are served by the **sandbox authoring service** (authority=none; every write inside the product dir). None deploy, send, or mutate a canonical repo. `verifier_status=PASS` is set only by the independent Cloudflare Worker and merely *read* here.

| Screen | Method + path | Effect |
|---|---|---|
| S0 | `POST /v1/sessions` | create `AuditSession` (`status:capturing`) |
| S0/S7 | `GET /v1/sessions`, `GET /v1/sessions/{id}` | list / load |
| S1 | `POST /v1/sessions/{id}/voice-notes` | create `VoiceNote` (audio blob) |
| S1 | `POST /v1/voice-notes/{vn}/transcribe` | create `Transcript` |
| S1 | `POST /v1/sessions/{id}/advance {to}` | move `AuditSession.status` |
| S2 | `GET /v1/sessions/{id}/observations` / `POST …/extract` | list / run extraction |
| S2 | `PATCH /v1/observations/{ob}` · `POST …/dismiss` · `POST …/split` | edit / dismiss / split |
| S3 | `GET /v1/sessions/{id}/clusters` · `POST …/cluster` | list / run clustering |
| S3 | `PATCH /v1/clusters/{ic}` · `POST …/split` · `POST /clusters/merge` · `POST …/drop` | edit clusters |
| S4 | `POST /v1/sessions/{id}/compile` | generate `WorkflowContract[]` |
| S4 | `POST /v1/sessions/{id}/launch-jobs` | create `SandboxJob[]` in cat-05 watcher |
| S4/S5 | `GET /v1/sessions/{id}/jobs` · `GET /v1/jobs/{sj}/diff` | poll jobs / read staged diff |
| S5 | `GET /v1/sessions/{id}/verification-runs` · `GET /v1/receipts/{id}` | read runs / receipt evidence |
| S5 | `GET /v1/sessions/{id}/pattern-expansion` · `POST …/compile {expand_from}` | expansion suggestions / expand |
| S6 | `GET /v1/sessions/{id}/approval-items` | list `ApprovalItem[]` |
| S6 | `POST /v1/approval-items/{ap}/decide` · `PATCH /v1/approval-items/{ap}` | record decision / scope |
| G1 | `POST /v1/sessions/{id}/sync` | batched offline-flush |

**Endpoints that do NOT exist (by design):** no `deploy`, no `apply-diff`, no `send`, no `merge`, no `delete`, no `cron`, no `mint-pass`. The absence is the safety property.
