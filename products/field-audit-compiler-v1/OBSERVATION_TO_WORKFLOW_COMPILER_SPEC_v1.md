# OBSERVATION → WORKFLOW COMPILER SPEC v1

`$id`: `noetfield:field-audit-compiler:obs-to-workflow:v1`
`reads`: `_SPINE_v1.json`, `VOICE_TO_OBSERVATION_SCHEMA_v1.json`, `RECEIPT_SCHEMA_FIELD_AUDIT_v1.json`
`locked_at`: 2026-07-09
`stage`: compiler middle-end — turns `Observation[]` into `WorkflowContract[]` via `IssueCluster[]`.

> This is the **deterministic compiler**, not a chatbot. Every rule here is a pure function of its inputs: same `Observation[]` + same `templates[]` registry ⇒ byte-identical `IssueCluster[]` and `WorkflowContract[]`. No LLM decides a `defect_kind`, a `template_id`, a `pass_condition`, or a `verifier_status`. Where the input is genuinely ambiguous, the compiler does **not** silently guess — it emits an `ApprovalItem` (needs-clarification) and stops that lane.

---

## 0. Authority binding (non-negotiable preamble)

This spec runs in `/sandbox` with `authority=none` (per `_SPINE_v1.authority_model`). Consequences baked into every rule below:

- The compiler only **reads** `Observation[]` and **writes** `IssueCluster[]` / `WorkflowContract[]` inside `sandbox/products/field-audit-compiler-v1/`. It CANNOT deploy, merge, delete, cron-unlock, send, or mutate any canonical surface.
- Generated `WorkflowContract.target` always references the **founder-supplied** `AuditSession.target_url` / `AuditSession.target_ref` (rendered as `{TARGET_URL}` in the canonical example). The compiler NEVER hardcodes or fetches a live surface (never `trustfield.ca`, never anything). The E2E chain in `_SPINE_v1.e2e_example` is an illustrative worked example, not a live run.
- A `WorkflowContract` cannot mint PASS. Its `deterministic_checks[]` are re-derived downstream by the independent Cloudflare Worker (`_SPINE_v1.authority_model.pass_issuance`). The compiler's job is to emit checks the Worker **can** re-derive with zero trust.
- `canonical_change` never happens from raw voice. It happens only through an approved `ApprovalItem` (`_SPINE_v1.authority_model.execution_rule`). The compiler's output is the *proposal*, never the mutation.

---

## 1. Pipeline position & I/O contract

```
Transcript ──(stage-1: VOICE_TO_OBSERVATION_SCHEMA)──► Observation[]
                                                          │
   ┌──────────────────────  THIS SPEC  ─────────────────┘
   ▼
Stage A  Observation extraction rules      span → defect_kind (+ severity_guess, confidence, surface_ref, needs_translation)
Stage B  Issue classification              defect_kind → candidate template_ids[]
Stage C  Clustering + dedupe               Observation[] → IssueCluster[]
Stage D  Template selection                IssueCluster → one winning template_id (+ scoring / tie-break)
Stage E  Contract generation               IssueCluster + template → WorkflowContract
Stage F  Confidence / needs-clarification  low-confidence or 'other' → ApprovalItem (never a silent guess)
   │
   ▼
WorkflowContract[] ──► SandboxJob ──► VerificationRun ──► field_audit_receipt_v1 ──► ApprovalItem
```

**Input:** `AuditSession` (for `surface_kind`, `target_url`/`target_ref`, `founder_id`) + its `Observation[]`.
**Output:** `IssueCluster[]`, `WorkflowContract[]`, and zero-or-more `ApprovalItem[]` of kind *needs-clarification*.
**Mutates on `AuditSession`:** advances `status` `extracting → clustered → contracted`.

Stage A is formally the tail of stage-1 (the `Observation` object is minted under `VOICE_TO_OBSERVATION_SCHEMA_v1.json`); it is restated here because span→`defect_kind` is the load-bearing decision the rest of the compiler depends on and must be specified precisely.

---

## 2. Stage A — Observation extraction (span → defect_kind)

Given a `Transcript`, the extractor slices the working text (`text_translated` if `translated=true`, else `text_normalized`) into atomic spans and tags each with a `defect_kind` from the closed enum. One span ⇒ one `Observation`.

### 2.1 Span slicing (deterministic)

```
function slice_spans(transcript):
    working = transcript.translated ? transcript.text_translated : transcript.text_normalized
    # text_normalized already has punctuation_canon → sentence-split applied (see normalization_ops)
    sentences = split_on(working, /[.;] /)          # stable, replayable delimiter
    spans = []
    for s in sentences:
        # a sentence may carry >1 defect ("cookie link goes nowhere and privacy is dead")
        for clause in split_on(s, / and | but | also /):
            clause = trim(clause)
            if clause != "": spans.push(clause)
    return spans
```

`raw_span` on the resulting `Observation` MUST be the **exact substring** of the working text — it is the provenance anchor (schema: *"Exact substring of text_normalized/text_translated"*). Never paraphrase into `raw_span`.

### 2.2 Span → defect_kind lexicon (decision table)

Each row is an ordered rule: first row whose trigger matches the span (case-insensitive over the normalized text) wins. Rules are ordered **most-specific-first** so `legal_footer_link` beats generic `broken_link`, and `pricing_claim` beats `offer_copy`.

| # | Trigger lexicon (regex-ish, over normalized span) | `defect_kind` | `target_hint` source | Notes |
|---|---|---|---|---|
| 1 | `\b(cookie\|privacy\|terms\|gdpr\|legal\|accessibility)\b` **and** (`link\|footer\|policy\|goes nowhere\|dead\|broken\|missing`) | `legal_footer_link` | matched legal noun | Footer/compliance link. Beats broken_link. |
| 2 | `\b(sign[- ]?in\|sign[- ]?up\|log[- ]?in\|login\|auth\|create account)\b` | `auth_entrypoint` | matched auth phrase | Money/onboarding path. |
| 3 | `\b(apply\|book\|get started\|start\|demo\|contact sales\|cta\|call to action\|button)\b` **and** (`broken\|dead\|nowhere\|404\|not working\|doesn'?t work`) | `cta_route` | the named CTA | Primary conversion element. Beats broken_link. |
| 4 | `\$?\d[\d,]*\b` **or** `\b(price\|pricing\|cost\|\$?\d+[- ]?(week\|month\|day)\|per month\|/mo)\b` **and** (`wrong\|stale\|update\|outdated\|mismatch\|says`) | `pricing_claim` | the offer/plan name | Specific checkable numeric claim. Beats offer_copy. |
| 5 | `\b(offer\|package\|copy\|wording\|headline\|tagline\|plan name\|inclusions)\b` **and** (`wrong\|stale\|update\|outdated\|off\|old`) | `offer_copy` | the offer name | Copy match vs canonical (non-numeric). |
| 6 | `\b(request\|correlation\|corr\|trace)[- ]?id(s)?\b` | `request_id_visibility` | "Request IDs" | Traceability on trust/support views. |
| 7 | `\b(chat\|web chat\|chat widget\|chatbot\|support widget)\b` | `web_chat_ux` | "Web chat" | Widget smoke UX. |
| 8 | `\b(mobile\|responsive\|phone\|small screen\|zoom\|overflow\|tap target)\b` | `mobile_responsive` | affected view | Viewport smoke. |
| 9 | `\b(page\|route\|/\S+\|home\|pricing page\|dashboard)\b` **and** (`down\|500\|blank\|empty\|won'?t load\|error\|not loading`) | `route_health` | the route | Baseline liveness. |
| 10 | `\b(link\|href\|url)\b` **and** (`broken\|dead\|nowhere\|404`) — and no row 1/3 match | `broken_link` | the link phrase | Generic link scan (fallback for links). |
| 11 | *no trigger matched* | `other` | verbatim span | → Stage F needs-clarification; NO template. |

The enum is closed and identical to `VOICE_TO_OBSERVATION_SCHEMA_v1.$defs.defect_kind` and `Observation.defect_kind`. Rows 1→11 are evaluated in order; ties impossible by construction (first match wins). Row ordering is the *only* place specificity precedence lives — encode it as a static ordered list, not model judgement.

### 2.3 severity_guess heuristic (pure)

```
function severity_guess(defect_kind, span):
    if matches(span, /\b(completely|totally|entirely)\b/) : bump = +1 else bump = 0
    base = {
        cta_route:            blocker,   # blocks conversion
        auth_entrypoint:      blocker,   # blocks signup/login
        route_health:         blocker,   # surface spine down
        legal_footer_link:    high,      # compliance exposure
        pricing_claim:        high,      # wrong money claim
        broken_link:          high,
        offer_copy:           medium,
        request_id_visibility:medium,
        web_chat_ux:          medium,
        mobile_responsive:    medium,
        other:                low
    }[defect_kind]
    return clamp(shift(base, bump), blocker..info)   # enum: blocker|high|medium|low|info
```

### 2.4 confidence (pure, drives Stage F)

```
function confidence(defect_kind, span, transcript):
    c = 0.5
    c += 0.30 if trigger_was_row(1..9)          # a specific (non-fallback) rule fired
    c += 0.10 if named_target_present(span)      # span names a concrete element
    c += transcript.confidence_bonus()           # +0.05 if transcript.confidence >= 0.9
    c -= 0.15 if defect_kind == broken_link       # generic fallback rows are weaker
    c -= 0.20 if defect_kind == other
    c -= 0.10 if transcript.translated           # translation adds a hop
    return clamp(c, 0.0, 1.0)                     # number[0..1]
```

The canonical example values are the ground truth this function must reproduce (see `_SPINE_v1.e2e_example.observations`): OB-1 `cta_route` 0.9, OB-2 `legal_footer_link` 0.88, OB-3 `auth_entrypoint` 0.9, OB-4 `pricing_claim` 0.82, OB-5 `request_id_visibility` 0.85, OB-6 `web_chat_ux` 0.70.

### 2.5 surface_ref & needs_translation

- `surface_ref` at extraction time is a **placeholder**, never a live URL: `"unresolved:<target_hint>"` (schema: *"May be a placeholder like 'unresolved:<target_hint>' until the sandbox job resolves it"*). Resolution to a concrete selector/route happens in Stage C/E against the founder's ref. E.g. OB-1 → `"unresolved:Apply for Program link"`.
- `needs_translation = transcript.translated` (true iff span came from a non-English transcript via `text_translated`).

### 2.6 Worked Stage-A output (canonical)

From `founder_voice_note` = *"Apply for Program link is broken. Cookie link goes nowhere. Sign-in is broken. Acme Brief twelve-thousand-dollar eight-week package copy needs update. Request IDs are not visible. Web chat UI is bad."* the extractor emits exactly `OB-1..OB-6` as in the spine — reproduced, not re-invented:

| id | raw_span | row | defect_kind | severity_guess | confidence |
|----|----------|-----|-------------|----------------|------------|
| OB-1 | `apply for pilot link is broken` | 3 | `cta_route` | blocker | 0.90 |
| OB-2 | `cookie link goes nowhere` | 1 | `legal_footer_link` | high | 0.88 |
| OB-3 | `sign-in is broken` | 2 | `auth_entrypoint` | blocker | 0.90 |
| OB-4 | `trust brief $12,000 8-week package copy needs update` | 4 | `pricing_claim` | high | 0.82 |
| OB-5 | `request ids are not visible` | 6 | `request_id_visibility` | medium | 0.85 |
| OB-6 | `web chat ui is bad` | 7 | `web_chat_ux` | medium | 0.70 |

---

## 3. Stage B — Issue classification (defect_kind → candidate template_ids)

`defect_kind` maps **1:1** to a primary `template_id` (`VOICE_TO_OBSERVATION_SCHEMA`: *"Each value maps to exactly one template_id"*). Ambiguity that *feels* like "matches multiple templates" is handled by (a) the ordered lexicon already picking one `defect_kind`, and (b) a small **sibling-spawn** table that expands one primary into related coverage during Stage E pattern expansion. Stage D scoring exists to break the *primary vs sibling* tie deterministically.

### 3.1 Primary map (1:1) + eligibility

| `defect_kind` | primary `template_id` | `target_kind` (eligibility) | promotion `factory_category` | `value_class` | in first-five? |
|---|---|---|---|---|---|
| `route_health` | `route_health_check` | website·web_app·dashboard | CAT-09-RECEIPT-TRUST-AUDIT-LAYER | GUARD | ✅ |
| `broken_link` | `broken_link_scan` | website·web_app·dashboard | CAT-09-RECEIPT-TRUST-AUDIT-LAYER | GUARD | ✅ |
| `cta_route` | `cta_route_check` | website·web_app | CAT-10-VERTICAL-PROOF-PRODUCTS | REVENUE | ✅ |
| `auth_entrypoint` | `auth_entrypoint_check` | website·web_app·dashboard | CAT-10-VERTICAL-PROOF-PRODUCTS | REVENUE | ✅ |
| `request_id_visibility` | `request_id_visibility_check` | web_app·dashboard | CAT-09-RECEIPT-TRUST-AUDIT-LAYER | GUARD | ✅ |
| `legal_footer_link` | `legal_footer_link_check` | website·web_app | CAT-09-RECEIPT-TRUST-AUDIT-LAYER | GUARD | — |
| `pricing_claim` | `pricing_claim_consistency_check` | website·web_app | CAT-10-VERTICAL-PROOF-PRODUCTS | REVENUE | — |
| `offer_copy` | `offer_copy_consistency_check` | website·web_app | CAT-10-VERTICAL-PROOF-PRODUCTS | REVENUE | — |
| `web_chat_ux` | `web_chat_ux_check` | website·web_app | CAT-09-RECEIPT-TRUST-AUDIT-LAYER | META | — |
| `mobile_responsive` | `mobile_responsive_smoke_check` | website·web_app | CAT-10-VERTICAL-PROOF-PRODUCTS | GUARD | — |
| `other` | *(none)* | — | — | NONE | — |

`value_class` / `factory_category` values are copied verbatim from `_SPINE_v1.templates[]`; never re-derive them.

**Eligibility filter.** A template is eligible only if `AuditSession.surface_kind ∈ template.target_kind`. Example: on `surface_kind=repo` all of the above (all website/web_app scoped) are ineligible → those observations route to Stage F needs-clarification rather than a wrong contract. The canonical session is `surface_kind=website`, so all rows are eligible.

### 3.2 Candidate set (why "multiple templates" arises)

Two defect_kinds legitimately generate a **candidate set** > 1 because a single spoken defect implies related deterministic checks:

| `defect_kind` | candidate `template_ids` (primary first) | resolved by |
|---|---|---|
| `pricing_claim` | `pricing_claim_consistency_check` (primary), `offer_copy_consistency_check` (sibling) | Stage D scoring picks primary; Stage E spawns the sibling as an expansion contract |
| `legal_footer_link` | `legal_footer_link_check` (primary), `broken_link_scan` (sibling over nav+footer) | Stage D picks primary; Stage E spawns the broad scan as expansion |
| `cta_route` | `cta_route_check` (primary), `route_health_check` (sibling for the CTA's route) | primary only unless route named separately |

All other defect_kinds have a single-element candidate set. This is the ONLY source of template multiplicity; it is a fixed table, not a search.

---

## 4. Stage C — Clustering + dedupe (Observation[] → IssueCluster[])

Goal: collapse duplicate/overlapping observations into exactly one `IssueCluster` per *(defect_kind, resolved target scope)* so that one `WorkflowContract` is generated per real issue. This is where *"Apply for Program broken"* + *"Cookie link nowhere"* stay **separate** (different kinds/scopes) while *"the cookie link is dead"* said twice **collapse** into one.

### 4.1 Cluster key

```
cluster_key(obs) = ( obs.defect_kind , resolve_scope(obs) )
resolve_scope(obs):
    hint = normalize(obs.target_hint)                 # lowercase, strip stopwords
    # deterministic resolution of the founder's words → a canonical scope token
    return SCOPE_RESOLVER[obs.defect_kind](hint)      # see 4.2; independent of live surface
```

`resolve_scope` maps the founder's phrase to a **stable canonical selector/route token** using the template's declared `inputs.scope_selector` as the base and the `target_hint` as a discriminator. It does not fetch anything; it produces the same `target_refs` the spine records.

### 4.2 Scope resolver (per defect_kind → target_refs)

| `defect_kind` | resolver output (`IssueCluster.target_refs`) — canonical example |
|---|---|
| `cta_route` | `["a[data-cta='<slug(hint)>']", "/<slug(hint)>"]` → `["a[data-cta='apply-for-program']","/apply-for-program"]` |
| `legal_footer_link` | `["footer a[href*='<legal-noun>']"]` → `["footer a[href*='cookie']"]` |
| `auth_entrypoint` | `["a[href*='login']","/login"]` (or `signin`) |
| `pricing_claim` | `["[data-offer='<slug(offer)>']"]` → `["[data-offer='trust-brief']"]` |
| `request_id_visibility` | `["main","[data-request-id]"]` |
| `web_chat_ux` | `["[data-chat]"]` |
| `broken_link` | `["nav a[href]","footer a[href]"]` |
| `route_health` | `["/", "/pricing", "/apply-for-program", "/login"]` (declared/nav-derived) |
| `mobile_responsive` | key routes at fixed `375x812` |
| `offer_copy` | `["[data-offer='<slug(offer)>']","main"]` |

`slug(hint)` is a deterministic transform (`"Apply for Program"` → `apply-for-program`). `<legal-noun>` is the matched noun from lexicon row 1.

### 4.3 Merge / dedupe algorithm

```
function cluster(observations):
    buckets = {}                                   # cluster_key → Observation[]
    for obs in stable_sort(observations, by=obs.id):   # deterministic order
        k = cluster_key(obs)
        buckets.setdefault(k, []).push(obs)
    clusters = []
    for (key, members) in stable_sort(buckets.items()):
        (defect_kind, scope) = key
        ic = IssueCluster(
            id            = next_cluster_id(),                 # IC-<n>
            session_id    = members[0].session_id,
            observation_ids = [m.id for m in members],
            defect_kind   = defect_kind,
            label         = human_label(defect_kind, scope),   # "Broken 'Apply for Program' CTA"
            target_refs   = scope_refs(defect_kind, scope),    # 4.2
            severity      = max_severity([m.severity_guess for m in members]),  # spine: "Max of member severities"
            dedup_note    = dedup_reason(defect_kind, members) # why merged/kept separate
        )
        clusters.push(ic)
    return clusters
```

Dedupe rules embedded above:
1. **Exact-duplicate collapse** — two observations with identical `cluster_key` (same kind + same resolved scope) merge into one cluster; their ids both appear in `observation_ids`. `dedup_note` records the merge.
2. **Cross-note collapse** — clustering is per `session_id`, so the same defect spoken in two different `VoiceNote`s (different `transcript_id`) still shares a `cluster_key` and merges. Provenance survives because every merged `Observation` keeps its own `transcript_id`/`raw_span`.
3. **Specificity keeps kinds separate** — *"Apply for Program broken"* (`cta_route`, scope `apply-for-program`) and *"Cookie link nowhere"* (`legal_footer_link`, scope `cookie`) have different `cluster_key`s ⇒ two clusters, not one links-cluster. They only re-converge later as *sibling expansion contracts* (Stage E), never as a merged cluster. The **broad** `broken_link_scan` over nav+footer is the thing that would sweep them together — and that is spawned in expansion, exactly as `_SPINE_v1.e2e_example.pattern_expansion[WC-2]` shows (`WC-2c(broken_link_scan)`).
4. **`severity` = max** of member `severity_guess` (spine field note).

### 4.4 Canonical Stage-C output

Reproduces `_SPINE_v1.e2e_example.issue_clusters` exactly: `IC-1 cta_route` (OB-1), `IC-2 legal_footer_link` (OB-2), `IC-3 auth_entrypoint` (OB-3), `IC-4 pricing_claim` (OB-4), `IC-5 request_id_visibility` (OB-5), `IC-6 web_chat_ux` (OB-6). Note `IC-4.dedup_note` records the pricing-over-offer decision, and `IC-2.dedup_note` records "grouped under legal_footer_link (more specific than generic broken_link)". Six observations → six clusters (no two share a key here).

---

## 5. Stage D — Template selection (scoring + tie-break)

For clusters whose candidate set is a single template (most), selection is trivial: pick it. Scoring exists to deterministically choose the **primary** when `defect_kind` yields a candidate set >1 (§3.2), and to break ties reproducibly.

### 5.1 Score function (pure, integer, total order)

```
function score(template, cluster, session):
    if template.target_kind does not include session.surface_kind: return -INF   # ineligible → excluded
    s = 0
    s += 100 if template == primary_template(cluster.defect_kind)   # 1:1 primary always wins its cluster
    s +=  40 if template.id in first_five_template_ids             # prefer proven pure-HTTP templates
    s +=  20 * specificity_rank(template)                          # narrower checkable claim ranks higher
    s +=  10 if canonical_source_available(template, session)      # offer/pricing need a supplied canonical
    s +=   1 * (10 - stable_index(template.id))                    # final deterministic tie-break by registry order
    return s

select_template(cluster, session):
    cands = candidate_templates(cluster.defect_kind)              # §3.2, primary first
    ranked = stable_sort(cands, key = -score(t, cluster, session))
    winner = ranked[0]
    if score(winner) == -INF: return NEEDS_CLARIFICATION          # no eligible template → Stage F
    return winner
```

`specificity_rank`: `pricing_claim_consistency_check` (2, exact numeric equality) > `offer_copy_consistency_check` (1, string equality) > `broken_link_scan` (0, broad sweep). This is why, for an `IC` derived from `pricing_claim`, the pricing template beats the offer-copy sibling as **primary** — matching `IC-4.dedup_note`: *"pricing_claim chosen over offer_copy because the specific claim ($12,000, 8-week) is checkable against canonical."*

### 5.2 Tie-break decision table

| Contention | Winner | Rule that decides it |
|---|---|---|
| `pricing_claim_consistency_check` vs `offer_copy_consistency_check` | pricing (primary) | +100 primary, +20·specificity(2 vs 1) |
| `legal_footer_link_check` vs `broken_link_scan` (a cookie link) | legal_footer (primary) | +100 primary; broad scan is not the cluster's kind |
| `cta_route_check` vs `route_health_check` (a broken CTA) | cta_route (primary) | +100 primary; route_health is a sibling for the CTA's route only |
| two equally-scoring eligible templates | lower `stable_index(template.id)` | final `+1*(10-index)` registry-order tie-break — total order, never random |
| no eligible template (`surface_kind` mismatch or `other`) | — | `-INF` → `NEEDS_CLARIFICATION` (Stage F) |

Selection is a pure ranking over a fixed candidate list with an integer key that is **totally ordered** (registry index guarantees no ties survive). No stochastic choice, ever.

### 5.3 Canonical Stage-D result

`IC-1→cta_route_check`, `IC-2→legal_footer_link_check`, `IC-3→auth_entrypoint_check`, `IC-4→pricing_claim_consistency_check` (sibling `offer_copy_consistency_check` deferred to expansion), `IC-5→request_id_visibility_check`, `IC-6→web_chat_ux_check` — identical to the `template_id` on `WC-1..WC-6`.

---

## 6. Stage E — Contract generation (IssueCluster + template → WorkflowContract)

Emit one `WorkflowContract` per cluster, filling every required field of `_SPINE_v1.objects.WorkflowContract` from the cluster, the selected template, and the session ref. Shape follows `_SPINE_v1.workflow_contract_shape`.

### 6.1 Generator

```
function generate_contract(cluster, template, session, n):
    return WorkflowContract(
      id            = "WC-" + n,                                   # per §6.5, keyed to cluster order
      cluster_id    = cluster.id,
      session_id    = session.id,
      template_id   = template.id,
      target = {
        target_url  = session.target_url,     # founder-supplied; {TARGET_URL} placeholder, NEVER live-hardcoded
        target_ref  = session.target_ref,     # for repo/workflow surfaces
        scope_selector = fanout_scope(template, cluster)           # §6.2
      },
      params        = fill_params(template, cluster, session),     # §6.3
      deterministic_checks = instantiate_checks(template, cluster),# copy template.deterministic_checks, bind params
      expected_outputs = expected_from_intent(cluster, template),  # §6.4
      verifier_logic = template.verifier_logic,                    # copied verbatim from registry
      pattern_expansion_rule = expansion_rule(template, cluster),  # §7
      promotion = { factory_category: template.factory_category,
                    value_class:      template.value_class },      # copied verbatim
      risk_class        = risk_of(cluster.defect_kind),            # §6.6 table
      approval_required = (risk_of(cluster.defect_kind) != read_only)
    )
```

### 6.2 `target.scope_selector` — the fan-out scope

`scope_selector` is the CSS/route/glob that defines what the contract fans across (spine: *"CSS/route/glob selector defining the fan-out scope"*). It is **broader** than the cluster's `target_refs` (a single element) because the contract is designed to expand:

| template | `scope_selector` (canonical) |
|---|---|
| `cta_route_check` | `a[data-cta], button[data-cta]` |
| `legal_footer_link_check` | `footer a[href]` |
| `auth_entrypoint_check` | `a[href*='login'], a[href*='signin']` |
| `pricing_claim_consistency_check` | `[data-offer='trust-brief']` |
| `request_id_visibility_check` | `main, [data-request-id]` |
| `web_chat_ux_check` | `[data-chat]` |
| `route_health_check` | declared routes / `/**` |
| `broken_link_scan` | `a[href]` (ignore `mailto:`,`tel:`) |

### 6.3 `params` — template-specific fill

Bind the template's declared `inputs` using the cluster's resolved scope + session-supplied canonical sources. Canonical fills (matching `WC-1..WC-6`):

| WC | template | `params` |
|----|----------|----------|
| WC-1 | `cta_route_check` | `{ cta_selector:"a[data-cta='apply-for-program']", expected_status:[200] }` |
| WC-2 | `legal_footer_link_check` | `{ required:["cookie"] }` |
| WC-3 | `auth_entrypoint_check` | `{ expected_status:[200] }` |
| WC-4 | `pricing_claim_consistency_check` | `{ canonical_copy_source:"{SSOT_PRICING_REF}", expected_price:"$12,000", expected_duration:"8-week" }` |
| WC-5 | `request_id_visibility_check` | `{ id_regex:"(req\|request\|corr)[-_ ]?id[:#]?\\s*[A-Za-z0-9-]{6,}" }` |
| WC-6 | `web_chat_ux_check` | `{ widget_selector:"[data-chat]", required_controls:["input,textarea","button[type=submit],[data-chat-send]"] }` |

`canonical_copy_source` is a founder/SSOT-supplied ref (`{SSOT_PRICING_REF}`), never fetched live and never invented. `expected_price`/`expected_duration` come from the founder's own spoken claim, already normalized to `$12,000` / `8-week` by the transcript `normalization_ops`.

### 6.4 `deterministic_checks` & `expected_outputs`

`deterministic_checks[]` are **copied** from `template.deterministic_checks` (each `{name, logic, pass_condition}`) with params bound. The `name`s MUST equal the template's — because the downstream `field_audit_receipt_v1.checks[].name` MUST match a `deterministic_checks[].name` (receipt schema note) and the CF Worker keys re-derivation on that name.

`expected_outputs` encodes what a *passing* run looks like — but the compiler sets it from **founder intent**, not optimism. When the founder asserts a defect, the expected result of the check against the *current* surface is the failing boolean, and the contract records that so the receipt's FAIL is the *expected* signal, not a surprise. E.g. `WC-4.expected_outputs = { price_matches_canonical:false, duration_matches_canonical:false, interpretation:"founder said copy needs update → canonical mismatch expected until patched" }` and `WC-1.expected_outputs = { cta_present:true, cta_route_resolves:true }` (the founder expects it to work; the receipt then shows the 404 FAIL, proving the defect).

### 6.5 IDs & ordering

`WC-<session>-<n>` per `workflow_contract_shape`; in the canonical example rendered compactly as `WC-<n>` where `n` follows cluster order (`IC-1→WC-1` …). Generation order = stable cluster order = deterministic.

### 6.6 `risk_class` & `approval_required` (decision table)

`risk_class` describes what the contract's **SandboxJob** does to produce evidence (`inspect` vs `patch_diff`) — it is NOT the remediation risk (that lives on the `ApprovalItem`). A `read_only` inspect contract can still yield a `canonical_change` `ApprovalItem` when the *fix* (a missing route, a 500) needs human/infra work the sandbox must not author.

| `defect_kind` | `SandboxJob.job_kind` | contract `risk_class` | `approval_required` | resulting `ApprovalItem.risk_class` / `proposed_patch_ref` |
|---|---|---|---|---|
| `cta_route` | `inspect` | `read_only` | false | `canonical_change` / `null` (route fix is infra) |
| `legal_footer_link` | `inspect` | `read_only` | false | `canonical_change` / `null` |
| `auth_entrypoint` | `inspect` | `read_only` | false | `canonical_change` / `null` |
| `route_health` | `inspect` | `read_only` | false | `canonical_change` / `null` |
| `broken_link` | `inspect` | `read_only` | false | `canonical_change` / `null` |
| `pricing_claim` | `patch_diff` | `canonical_change` | true | `canonical_change` / staged copy diff |
| `offer_copy` | `patch_diff` | `canonical_change` | true | `canonical_change` / staged copy diff |
| `request_id_visibility` | `patch_diff` | `low_risk_patch` | true | `low_risk_patch` / additive display diff |
| `web_chat_ux` | `patch_diff` | `low_risk_patch` | true | `low_risk_patch` / additive attribute diff |
| `mobile_responsive` | `patch_diff` | `low_risk_patch` | true | `low_risk_patch` / staged CSS diff |

This reproduces the spine exactly: `WC-1/2/3` `read_only`+`approval_required:false` (their `SJ` are `inspect`, `diff_ref:null`), while their `ApprovalItem`s `AP-1/2/3` are `canonical_change` with `proposed_patch_ref:null`; `WC-4` `canonical_change`, `WC-5/6` `low_risk_patch`, each `patch_diff` with a staged `diff_ref` that is **never applied** in sandbox (`_SPINE_v1.authority_model`: *"Sandbox jobs may only inspect / patch-into-a-diff / test"*).

> `approval_required=false` for `read_only` does **not** authorize any canonical change — a read-only check just runs and returns a receipt. The moment the receipt implies a fix, an `ApprovalItem` is minted and the human gate applies (§8, and `_SPINE_v1.authority_model.execution_rule`).

---

## 7. Pattern expansion rule (fan-out) — `WorkflowContract.pattern_expansion_rule`

Every contract carries a **deterministic** fan-out rule (spine field: *"How this contract fans across similar routes/components"*): enumerate all elements matching `scope_selector`, instantiate one check per element. Expansion happens at execution time (Stage 10 of `first_build_sequence`), producing sibling contracts `WC-<n>a`, `WC-<n>b`, … against the founder's `TARGET_URL` only.

```
function expansion_rule(template, cluster):
    return "enumerate all nodes matching target.scope_selector on {TARGET_URL}; " +
           "instantiate one " + template.id + " per matched element; " +
           SIBLING_SPAWN.get(cluster.defect_kind, "")     # §3.2 sibling templates
```

Canonical expansions (identical to `_SPINE_v1.e2e_example.pattern_expansion`):

| from | rule | expanded_targets (example) | new_contract_ids |
|---|---|---|---|
| WC-1 | fan to ALL CTAs | `apply-for-program`, `book-demo`, `get-started`, `contact-sales` | `WC-1, WC-1a, WC-1b, WC-1c` |
| WC-2 | ALL legal footer links **+** `broken_link_scan` over nav+footer | cookie, privacy, terms, nav+footer links | `WC-2, WC-2a, WC-2b, WC-2c(broken_link_scan)` |
| WC-3 | ALL auth entrypoints | header/footer login, signup, get-started | `WC-3, WC-3a, WC-3b` |
| WC-4 | pricing **+** `offer_copy_consistency_check` across commercial surfaces | `/`, `/pricing`, `/partner-access` | `WC-4, WC-4a, WC-4b(offer_copy_consistency_check)` |
| WC-5 | ALL views expected to show a request id | `/support`, `/trust`, error states | `WC-5, WC-5a` |
| WC-6 | ALL pages mounting the chat component | `/`, `/pricing`, `/support` | `WC-6, WC-6a, WC-6b` |

Expansion is where the separately-clustered `cta_route` and `legal_footer_link` defects finally get swept together — via `WC-2`'s spawned `broken_link_scan` over `nav a[href], footer a[href]` — without ever having been force-merged at clustering. Sibling spawns (`WC-2c`, `WC-4b`) are the §3.2 candidate-set siblings realized as real contracts.

---

## 8. Stage F — Confidence & needs-clarification (never a silent guess)

The compiler must never fabricate a `defect_kind`, `template_id`, or `target_ref` it isn't entitled to. Three gates route uncertainty to a **needs-clarification `ApprovalItem`** instead of a fabricated contract.

### 8.1 Gates

```
CONF_MIN = 0.60                 # below this, do not auto-compile

function gate(obs, session):
    if obs.defect_kind == "other":
        return CLARIFY("unroutable span — no template matches")
    if select_template(cluster_of(obs), session) == NEEDS_CLARIFICATION:
        return CLARIFY("no template eligible for surface_kind=" + session.surface_kind)
    if obs.confidence < CONF_MIN:
        return CLARIFY("low-confidence classification (" + obs.confidence + ")")
    if resolve_scope(obs) startswith "unresolved:" AND no_stable_scope(obs):
        return CLARIFY("could not resolve a stable target scope from target_hint")
    return COMPILE
```

### 8.2 Needs-clarification ApprovalItem

A CLARIFY result mints an `ApprovalItem` with **no** verified receipt behind it and **no** proposed patch — it is a question to the founder, using the exact `_SPINE_v1.objects.ApprovalItem` fields:

```
ApprovalItem(
  id            = "AP-clarify-" + n,
  session_id    = session.id,
  receipt_id    = null,                       # no receipt: this is pre-verification
  workflow_contract_id = null,                # no contract minted yet
  title         = "Clarify: '" + obs.target_hint + "' — " + reason,
  proposed_patch_ref = null,
  risk_class    = "read_only",                # asking a question mutates nothing
  value_class   = "NONE",
  target        = { target_url: session.target_url, scope_selector: obs.surface_ref },
  decision      = "pending",
  rationale     = reason + " — need founder to confirm defect_kind / element before compiling."
)
```

The founder's answer feeds back as a corrected `Observation` (or a manual `defect_kind` override), and the lane re-enters Stage B. **No contract is emitted for that observation until the ambiguity is resolved.** This is the concrete meaning of "low-confidence → ApprovalItem, never a silent guess."

### 8.3 What is NOT a Stage-F case

A *high-confidence* observation whose check is *expected to FAIL* (e.g. OB-4 pricing mismatch, OB-1 404) is **not** needs-clarification — it compiles normally to a `WorkflowContract` and the FAIL is the intended, receipted proof. Clarification is about *ambiguous input*, not *bad surface*. In the canonical example all six observations clear the gates (min confidence 0.70 ≥ 0.60), so zero clarification items are minted and all six compile — matching the spine.

---

## 9. End-to-end determinism & replay guarantees

1. **Pure functions only.** Stages A–E are deterministic functions of `(Observation[], AuditSession, templates[])`. Re-running yields byte-identical `IssueCluster[]` / `WorkflowContract[]`. The registry `templates[]` and `first_five_template_ids` are the only external inputs, both locked in `_SPINE_v1.json`.
2. **No live surface at compile time.** Every `target` is the founder-supplied `{TARGET_URL}`/`target_ref`; the compiler never fetches. Surface resolution (`unresolved:*` → real selector) is deferred to the `SandboxJob` running against the founder's ref in the cat-05 watcher.
3. **CF-re-derivable checks.** `deterministic_checks[].pass_condition` are pure predicates (HTTP status, DOM/selector presence, regex, hash equality) — exactly what `_SPINE_v1.workflow_contract_shape.verifier_logic` requires the Worker to recompute. The compiler emits nothing an LLM would have to judge.
4. **No PASS, no mutation from the compiler.** Contracts propose; the independent CF Worker adjudicates PASS/FAIL; only an approved `ApprovalItem` authorizes a canonical change. The compiler sits entirely inside `authority=none`.

---

## 10. Canonical E2E trace (reference — do not diverge)

`AS-2026-07-09-fieldaudit`, `surface_kind=website`, `target_url={TARGET_URL}`:

```
1 VoiceNote (VN-1)
  → 1 Transcript (TR-1)  normalize: "twelve thousand dollar"→"$12,000", "six week"→"8-week"
  → 6 Observations (OB-1..OB-6)              [Stage A]
  → 6 IssueClusters (IC-1..IC-6)             [Stage C — 1:1, no merges this session]
  → template selection                       [Stage D]
      IC-1→cta_route_check          IC-4→pricing_claim_consistency_check
      IC-2→legal_footer_link_check  IC-5→request_id_visibility_check
      IC-3→auth_entrypoint_check    IC-6→web_chat_ux_check
  → 6 WorkflowContracts (WC-1..WC-6)         [Stage E]
      read_only:  WC-1, WC-2, WC-3           (SJ inspect,   diff_ref=null)
      canonical:  WC-4                        (SJ patch_diff, staged copy diff)
      low_risk:   WC-5, WC-6                  (SJ patch_diff, staged additive diff)
  → 6 SandboxJobs (cat-05, authority=none)   → 6 VerificationRuns → 6 field_audit_receipt_v1
      ALL verifier_status=FAIL (surface genuinely broken: 404 /apply-for-program,
      500 /login, cookie href='#', $9,000/5-week ≠ $12,000/8-week, no request-id, unlabeled chat input)
  → 6 pending ApprovalItems (AP-1..AP-6)     [human gate]
  → pattern expansion fans each template across siblings (WC-1a.., WC-2c(broken_link_scan), WC-4b(offer_copy_consistency_check)..)

Zero clarification items (all confidences ≥ 0.60). No PASS self-minted. No canonical mutation. All diffs staged, none applied.
```

This chain is the single canonical example shared across the package; every id, `defect_kind`, `template_id`, `params` value, and `verifier_status` above is taken verbatim from `_SPINE_v1.e2e_example`. Do not introduce divergent names.
