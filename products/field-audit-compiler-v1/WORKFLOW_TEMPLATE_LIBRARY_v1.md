# WORKFLOW_TEMPLATE_LIBRARY_v1

Part of **FOUNDER_FIELD_AUDIT_TO_WORKFLOW_COMPILER_v1**.
Binds to: `_SPINE_v1.json` (`noetfield:field-audit-compiler:spine:v1`), `VOICE_TO_OBSERVATION_SCHEMA_v1.json`, `RECEIPT_SCHEMA_FIELD_AUDIT_v1.json`.
Template names, ids, field names, and the canonical E2E example here are **identical to the spine** — this file is the executable reference for the 10 templates, nothing new is invented.

---

## 0. What a template IS (and is not)

A template is a **pure, no-LLM check factory**. The compiler routes a cluster's `defect_kind` to exactly one `template_id`, instantiates the template's `deterministic_checks` against the founder-supplied `target`, and emits a `WorkflowContract`. The contract is executed as a `SandboxJob` in the `CAT-05-SANDBOX-WORKTREE-EXECUTION` watcher slot, which self-writes a `field_audit_receipt_v1` at `verifier_status="UNVERIFIED"`. The **independent Cloudflare Worker verifier** re-derives every check and is the ONLY issuer of `verifier_status="PASS"`.

A template MUST satisfy all of the following or it does not belong in this library:

- **Deterministic**: given the same bytes at `target`, the check yields the same boolean every time. No model, no judgement, no "looks bad".
- **Re-derivable**: the CF Worker can recompute the boolean from stored `evidence` (http_status, dom/body hash, regex+match, selector) with **zero trust** in the sandbox author.
- **Bounded**: it only reads / measures / hashes. It never deploys, sends, deletes, unlocks cron, or mutates a canonical surface. Writes are staged as a `diff_ref` and applied ONLY through an approved `ApprovalItem`.
- **Target-scoped**: it runs ONLY against the session's `target_url`/`target_ref`. `{TARGET_URL}` is a per-session placeholder — no live surface is ever hardcoded or fetched.

### `defect_kind` → `template_id` routing (1:1)

| `Observation.defect_kind` | `template_id` |
|---|---|
| `broken_link` | `broken_link_scan` |
| `cta_route` | `cta_route_check` |
| `legal_footer_link` | `legal_footer_link_check` |
| `auth_entrypoint` | `auth_entrypoint_check` |
| `offer_copy` | `offer_copy_consistency_check` |
| `pricing_claim` | `pricing_claim_consistency_check` |
| `request_id_visibility` | `request_id_visibility_check` |
| `web_chat_ux` | `web_chat_ux_check` |
| `mobile_responsive` | `mobile_responsive_smoke_check` |
| `route_health` | `route_health_check` |
| `other` | *(unroutable — stays an Observation, no contract)* |

### `first_five_template_ids` (build/execute these first)

```
route_health_check, broken_link_scan, cta_route_check, auth_entrypoint_check, request_id_visibility_check
```

Rationale (from spine): all five are exercised by the canonical E2E and are purely deterministic with plain HTTP + static-DOM/regex logic a CF Worker already re-derives today (`route_health_check` mirrors the shipped CAT-10 `http_200` poller). `offer_copy_consistency_check` / `pricing_claim_consistency_check` need a supplied canonical source; `web_chat_ux_check` / `mobile_responsive_smoke_check` need rendering — all four are sequenced **after** the first five.

### Value-class lens (from receipt schema)

- **REVENUE** — directly blocks money paths (CTAs, auth, pricing/offer copy). Promotes to `CAT-10-VERTICAL-PROOF-PRODUCTS`.
- **GUARD** — protects trust/compliance (broken links, legal footer, request-id visibility, route health, responsive). Promotes to `CAT-09-RECEIPT-TRUST-AUDIT-LAYER` (mobile responsive promotes to CAT-10 per spine, see §9).
- **META** — tooling/UX signal (web chat UX). Promotes to `CAT-09-RECEIPT-TRUST-AUDIT-LAYER`.
- **NONE** — informational.

### Determinism normalization rules (shared by every check)

To keep the sandbox boolean and the CF re-derivation byte-identical, every template obeys these fixed conventions:

- **HTTP method**: `GET` with header `Range: bytes=0-0` is NOT used; use full `GET` unless the template says HEAD. Follow up to **5** redirects, recording the full redirect chain. The `http_status` stored in evidence is the **final** status after the chain.
- **Timeout**: 10000 ms per request. A timeout is a check failure with `http_status: 0` and `detail` noting `timeout`.
- **Static DOM**: for HTTP-only templates, "DOM" means the parsed **served HTML** (no client JS execution). Templates that require rendering (`web_chat_ux_check`, `mobile_responsive_smoke_check`) say so explicitly and route through the headless render service the Worker also calls.
- **Selector matching**: standard CSS selectors evaluated against the parsed served HTML. `:contains('X')` is shorthand for "an element whose normalized visible text contains the case-insensitive substring X" and is implemented as an explicit text scan, not a live jQuery call.
- **`normalize(s)`**: `trim → collapse internal whitespace to single space → NFC unicode → casefold`. Used for all text/copy equality checks. Never an LLM comparison.
- **Hashing**: `sha256` over exact response bytes (`body_sha256`) or over the canonical-serialized parsed subtree (`dom_sha256`). Same hasher on both sides.
- **`href not in ['', '#', 'javascript:void(0)']`** is the shared "dead href" predicate.

Each check below is written so the sandbox executor and the CF Worker run **the same logic on the same input** and must agree; the Worker additionally recomputes `summary` (`total=len(checks)`, `passed=count(passed==true)`, `failed=total-passed`) and FAILs on any mismatch, and requires edge + secondary-CF-account proof before it may emit `PASS`.

---

## Template 1 — `broken_link_scan`

- **id**: `broken_link_scan`
- **purpose**: Detect hrefs that resolve to non-2xx/3xx or empty/`#` targets across a scope.
- **target_kind**: `website | web_app | dashboard`
- **mapped factory_category**: `CAT-09-RECEIPT-TRUST-AUDIT-LAYER`
- **value_class**: `GUARD`

**inputs**
```json
{ "scope_selector": "a[href]", "ignore": ["mailto:", "tel:"] }
```
Target: `{ target_url, scope_selector }`. `ignore` prefixes are excluded from resolution (still enumerated, marked `skipped`, not counted as failures).

**deterministic checks (exact no-LLM logic)**

| name | logic | pass_condition |
|---|---|---|
| `href_resolves` | Enumerate every `a[href]` in served HTML matching `scope_selector`. For each unique resolved absolute href (skip `mailto:`/`tel:`), HTTP `GET`/`HEAD` it, following ≤5 redirects. | `status in [200,301,302,308] AND href not in ['', '#', 'javascript:void(0)']` |

One `checks[]` entry is produced **per unique resolved href** (name kept as `href_resolves`, disambiguated by `evidence.url`). Relative hrefs are resolved against `target_url`. Duplicate hrefs are deduped before fetching.

**pass/fail conditions**
- Check **passes** when the final status is one of `[200,301,302,308]` and the href is not a dead href.
- Check **fails** on any 4xx/5xx, network error/timeout (`http_status:0`), or a dead href (`''`, `#`, `javascript:void(0)`).
- Contract passes iff **all** per-href checks pass.

**outputs**
```json
{ "per_link": { "href": "...", "http_status": 200, "passed": true },
  "summary": { "total": N, "passed": P, "failed": F } }
```
Receipt `checks[].evidence`: `{ url, http_status, match }`.

**verifier re-derivation**: CF Worker re-fetches each `evidence.url`, recomputes the `passed` boolean under the identical predicate and redirect policy, recomputes `summary` from `checks[]`, and FAILs on any mismatch. `PASS` requires edge + secondary-account proof.

**pattern_expansion rule**: Fans to **ALL** nav + footer + in-body links matching `scope_selector`; one check per unique href. (Enumerate elements matching the scope, instantiate one check per element — the generic fan-out rule.)

---

## Template 2 — `cta_route_check`

- **id**: `cta_route_check`
- **purpose**: Verify a primary call-to-action element exists and its route/target resolves to a live 2xx page.
- **target_kind**: `website | web_app`
- **mapped factory_category**: `CAT-10-VERTICAL-PROOF-PRODUCTS`
- **value_class**: `REVENUE`

**inputs**
```json
{ "cta_selector": "a[data-cta], button[data-cta], a:contains('Apply')",
  "expected_status": [200] }
```

**deterministic checks**

| name | logic | pass_condition |
|---|---|---|
| `cta_present` | DOM selector presence in served HTML. | `document.querySelector(cta_selector) != null` |
| `cta_route_resolves` | HTTP `GET` the CTA's `href` (anchor) or `formaction`/`action` (button), ≤5 redirects. | `status == 200 AND href not in ['','#']` |

**pass/fail conditions**
- `cta_present` fails if no node matches `cta_selector`.
- `cta_route_resolves` fails on any non-200 final status or a dead href. (In the canonical E2E, `GET {TARGET_URL}/apply-for-program → HTTP 404` → `cta_route_resolves` fails; `cta_present` passes; summary `{2,1,1}`, `verifier_status=FAIL`.)
- Contract passes iff both checks pass.

**outputs**
```json
{ "cta": { "selector": "...", "href": "...", "present": true,
           "http_status": 404, "passed": false },
  "summary": { "total": 2, "passed": 1, "failed": 1 } }
```
Evidence: `cta_present` → `{ selector, match }`; `cta_route_resolves` → `{ url, http_status }`.

**verifier re-derivation**: CF Worker re-selects the CTA in fetched HTML and re-fetches its href; recomputes `summary`; FAILs on mismatch.

**pattern_expansion rule**: Fans to **ALL** CTAs (every `[data-cta]`/primary button) across the surface. E2E expansion: `WC-1 → [WC-1, WC-1a, WC-1b, WC-1c]` over `a[data-cta='apply-for-program' | 'book-demo' | 'get-started' | 'contact-sales']`.

**risk note**: `read_only` (WC-1 in E2E). A detected 404 becomes `ApprovalItem` AP-1 (`canonical_change`, `REVENUE`, decision `pending`) — the fix, not the check, is the canonical change.

---

## Template 3 — `legal_footer_link_check`

- **id**: `legal_footer_link_check`
- **purpose**: Ensure required legal/compliance footer links (Privacy, Terms, Cookie) exist and resolve.
- **target_kind**: `website | web_app`
- **mapped factory_category**: `CAT-09-RECEIPT-TRUST-AUDIT-LAYER`
- **value_class**: `GUARD`

**inputs**
```json
{ "required": ["privacy", "terms", "cookie"], "scope_selector": "footer a[href]" }
```

**deterministic checks** (one instantiated per `required` name; the spine's canonical check name is `cookie_link_present_and_resolves` for the `cookie` requirement — the pattern is `<name>_link_present_and_resolves`)

| name | logic | pass_condition |
|---|---|---|
| `cookie_link_present_and_resolves` | In `footer a[href]`, find a link whose `normalize(text)` or `href` contains the required token (e.g. `cookie`); HTTP `GET` its target, ≤5 redirects. | `link matching 'cookie' exists AND status==200 AND href not in ['','#']` |

**pass/fail conditions**
- Fails if the required link is **absent**, or present but resolves to non-200, or has a dead href.
- E2E: footer Cookie link `href='#'` → unresolved → fails; summary `{1,0,1}`, `verifier_status=FAIL`.
- Contract passes iff every required-name check passes.

**outputs**
```json
{ "per_required": { "name": "cookie", "found": true, "href": "#",
                    "http_status": null, "passed": false },
  "summary": { "total": 1, "passed": 0, "failed": 1 } }
```
Evidence: `{ selector, url, match }`.

**verifier re-derivation**: CF Worker re-parses the footer, matches required names by the same token rule, re-fetches each, recomputes `summary`, FAILs on mismatch.

**pattern_expansion rule**: Fans to **ALL** required legal links (privacy/terms/cookie/accessibility) in the footer. E2E: `WC-2 → [WC-2, WC-2a, WC-2b, WC-2c(broken_link_scan)]` — expansion also spawns a sibling generic `broken_link_scan` over `nav a[href]` + `footer a[href]`.

**risk note**: `read_only`. Dead compliance link → AP-2 (`canonical_change`, `GUARD`, title "Point footer Cookie link to /cookie-policy", pending).

---

## Template 4 — `auth_entrypoint_check`

- **id**: `auth_entrypoint_check`
- **purpose**: Verify sign-in / sign-up entrypoints exist and their routes return a working auth page (not 4xx/5xx).
- **target_kind**: `website | web_app | dashboard`
- **mapped factory_category**: `CAT-10-VERTICAL-PROOF-PRODUCTS`
- **value_class**: `REVENUE`

**inputs**
```json
{ "auth_selectors": ["a:contains('Sign in')", "a[href*='login']", "a[href*='signin']"],
  "expected_status": [200] }
```

**deterministic checks**

| name | logic | pass_condition |
|---|---|---|
| `auth_entry_present` | DOM selector presence: test each `auth_selector` against served HTML. | at least one `auth_selector` matches |
| `auth_route_resolves` | HTTP `GET` the matched auth entrypoint's `href`, ≤5 redirects. | `status == 200` |

**pass/fail conditions**
- `auth_entry_present` fails only if **no** auth selector matches.
- `auth_route_resolves` fails on any non-200 final status (incl. 5xx). E2E: `GET {TARGET_URL}/login → HTTP 500` → fails; `auth_entry_present` passes; summary `{2,1,1}`, `verifier_status=FAIL`.
- Contract passes iff both pass.

**outputs**
```json
{ "auth": { "selector": "a[href*='login']", "href": "/login", "present": true,
            "http_status": 500, "passed": false },
  "summary": { "total": 2, "passed": 1, "failed": 1 } }
```
Evidence: `auth_entry_present` → `{ selector, match }`; `auth_route_resolves` → `{ url, http_status }`.

**verifier re-derivation**: CF Worker re-selects the auth entrypoint in fetched HTML and re-fetches its route; recomputes `summary`; FAILs on mismatch.

**pattern_expansion rule**: Fans to **ALL** auth entrypoints (header sign-in, footer sign-in, in-body CTAs to login/signup). E2E: `WC-3 → [WC-3, WC-3a, WC-3b]` over `header a[href*='login']`, `footer a[href*='login']`, `a[href*='signup']`, `a[data-cta='get-started']`.

**risk note**: `read_only`. 500 on auth → AP-3 (`canonical_change`, `REVENUE`, "Fix Sign-in route 500", pending — blocks signups).

---

## Template 5 — `offer_copy_consistency_check`

- **id**: `offer_copy_consistency_check`
- **purpose**: Verify offer/package copy on the surface matches the canonical SSOT offer text (name, inclusions).
- **target_kind**: `website | web_app`
- **mapped factory_category**: `CAT-10-VERTICAL-PROOF-PRODUCTS`
- **value_class**: `REVENUE`
- **sequencing**: NOT in first-five. Requires a founder-supplied canonical source; sequenced after the first five.

**inputs**
```json
{ "canonical_copy_source": "SSOT offer registry ref (founder-supplied)",
  "offer_key": "acme_brief", "scope_selector": "[data-offer], main" }
```

**deterministic checks**

| name | logic | pass_condition |
|---|---|---|
| `offer_name_matches_canonical` | Extract rendered offer name from `scope_selector` subtree; fetch canonical name from `canonical_copy_source` for `offer_key`; compare with `normalize()`. | `normalize(rendered) == normalize(canonical.name)` |

Purely string/hash equality against a **supplied** canonical — no LLM, no semantic similarity.

**pass/fail conditions**
- Passes iff normalized rendered offer name equals the normalized canonical name.
- Fails on any normalized inequality (renamed/stale offer) or if the offer node is absent (`rendered` empty → not equal → fail).

**outputs**
```json
{ "offer": { "key": "acme_brief", "rendered": "...", "canonical": "...", "passed": true },
  "summary": { "total": 1, "passed": 1, "failed": 0 } }
```
Evidence: `{ selector, expected, actual, match, dom_sha256 }` (`dom_sha256` over the offer subtree).

**verifier re-derivation**: CF Worker re-fetches the page + the canonical source, re-normalizes both, re-compares, recomputes `summary`, FAILs on mismatch. (No LLM — pure string/hash equality against the supplied canonical.)

**pattern_expansion rule**: Fans across **ALL** commercial surfaces/pages that reference the offer (home, pricing, product, partner pages). In the E2E this is the **sibling** spawned by the pricing cluster's expansion: `WC-4 → [..., WC-4b(offer_copy_consistency_check)]`.

**risk note**: `canonical_change` when a copy fix is proposed (approval required).

---

## Template 6 — `pricing_claim_consistency_check`

- **id**: `pricing_claim_consistency_check`
- **purpose**: Verify a specific price/duration claim on the surface equals the canonical value (e.g. `$12,000` / `8-week`).
- **target_kind**: `website | web_app`
- **mapped factory_category**: `CAT-10-VERTICAL-PROOF-PRODUCTS`
- **value_class**: `REVENUE`
- **sequencing**: NOT in first-five. Requires a canonical pricing source; sequenced after the first five.

**inputs**
```json
{ "canonical_copy_source": "SSOT pricing registry ref",
  "expected_price": "$12,000", "expected_duration": "8-week",
  "scope_selector": "[data-offer], main" }
```

**deterministic checks**

| name | logic | pass_condition |
|---|---|---|
| `price_matches_canonical` | Regex-extract the price token from the `scope_selector` subtree (`\$[0-9,]+`), compare to `expected_price` by string equality. | `extracted_price == '$12,000'` |
| `duration_matches_canonical` | Regex-extract the duration token (`[0-9]+-week`), compare to `expected_duration`. | `extracted_duration == '8-week'` |

**pass/fail conditions**
- Each check passes on exact token equality; fails on mismatch or no-match (empty extraction ≠ expected → fail).
- **E2E is a deliberate FAIL** (founder said the copy needs updating): rendered `$9,000` ≠ `$12,000` and `5-week` ≠ `8-week` → both fail; summary `{2,0,2}`, `verifier_status=FAIL`. `expected_outputs` in the contract explicitly encode `false/false` with interpretation "canonical mismatch expected until patched."

**outputs**
```json
{ "claim": { "expected_price": "$12,000", "expected_duration": "8-week",
             "found_price": "$9,000", "found_duration": "5-week", "passed": false },
  "summary": { "total": 2, "passed": 0, "failed": 2 } }
```
Evidence per check: `{ regex, expected, actual, match }`.

**verifier re-derivation**: CF Worker re-fetches the page, re-runs the **same** regexes, re-compares to canonical, recomputes `summary`, FAILs on mismatch.

**pattern_expansion rule**: Fans across **ALL** commercial surfaces where the price/duration is claimed. E2E: `WC-4 → [WC-4, WC-4a, WC-4b(offer_copy_consistency_check)]` over `/ [data-offer='acme-brief']`, `/pricing [data-offer='acme-brief']`, `/partner-access [data-offer='acme-brief']`, spawning a sibling `offer_copy_consistency_check`.

**risk note**: `canonical_change`, `approval_required: true`. Sandbox job is `patch_diff` — stages `sandbox/.../SJ-4/acme-brief-copy.diff`, never applies. Becomes AP-4 (`canonical_change`, `REVENUE`, "Update Acme Brief copy to $12,000 / 8-week", `proposed_patch_ref` set, pending).

---

## Template 7 — `request_id_visibility_check`

- **id**: `request_id_visibility_check`
- **purpose**: Verify a request/correlation id is rendered to the user on relevant views (support/trust surfaces) so issues are traceable.
- **target_kind**: `web_app | dashboard`
- **mapped factory_category**: `CAT-09-RECEIPT-TRUST-AUDIT-LAYER`
- **value_class**: `GUARD`

**inputs**
```json
{ "id_regex": "(req|request|corr)[-_ ]?id[:#]?\\s*[A-Za-z0-9-]{6,}",
  "scope_selector": "main, [data-request-id]" }
```

**deterministic checks**

| name | logic | pass_condition |
|---|---|---|
| `request_id_visible` | Run `id_regex` over the rendered text of `scope_selector`; OR check `[data-request-id]` attribute is non-empty. | `id_regex matches rendered DOM text OR [data-request-id] attribute is non-empty` |

**pass/fail conditions**
- Passes if either the regex matches visible text or a non-empty `[data-request-id]` attribute exists.
- Fails if neither holds. E2E: no request-id pattern and no `[data-request-id]` → fails; summary `{1,0,1}`, `verifier_status=FAIL`.

**outputs**
```json
{ "request_id": { "found": false, "sample": null, "passed": false },
  "summary": { "total": 1, "passed": 0, "failed": 1 } }
```
Evidence: `{ regex, match }` (and `selector`/`sample` when found).

**verifier re-derivation**: CF Worker re-fetches the view and re-runs the **same** regex over rendered text/attributes, recomputes `summary`, FAILs on mismatch.

**pattern_expansion rule**: Fans across **ALL** views expected to show a request id (support pages, error states, receipt/trust views). E2E: `WC-5 → [WC-5, WC-5a]` over `/support`, `/trust`, error states.

**risk note**: `low_risk_patch`, `approval_required: true`. Sandbox job is `patch_diff` → stages `sandbox/.../SJ-5/request-id-display.diff`. Becomes AP-5 (`low_risk_patch`, `GUARD`, "Render request id on trust/support views", additive display element, still queued for approval).

---

## Template 8 — `web_chat_ux_check`

- **id**: `web_chat_ux_check`
- **purpose**: Smoke-check the web chat widget: mount node present, input + send control present, ARIA/label sanity. A UX **signal**, not a subjective judgement.
- **target_kind**: `website | web_app`
- **mapped factory_category**: `CAT-09-RECEIPT-TRUST-AUDIT-LAYER`
- **value_class**: `META`
- **sequencing**: NOT in first-five. Needs rendering (widget mounts client-side) — sequenced after the first five and routed through the headless render service the Worker calls.

**inputs**
```json
{ "widget_selector": "[data-chat], #chat-widget",
  "required_controls": ["input,textarea", "button[type=submit],[data-chat-send]"] }
```

**deterministic checks**

| name | logic | pass_condition |
|---|---|---|
| `chat_widget_mounts` | DOM selector presence in the rendered DOM. | `widget_selector matches exactly one node` |
| `chat_controls_present` | DOM presence of an input control AND a send control. | each `required_controls` selector matches ≥1 node |
| `chat_input_labeled` | Attribute presence on the chat input. | input has non-empty `aria-label` OR non-empty `placeholder` |

**pass/fail conditions**
- `chat_widget_mounts` requires **exactly one** match (0 = not mounted, >1 = duplicate mounts) → both fail.
- `chat_controls_present` fails if either the input or the send control is missing.
- `chat_input_labeled` fails when neither `aria-label` nor `placeholder` is present/non-empty.
- E2E: widget mounts (pass), controls present (pass), input missing `aria-label` + `placeholder` (fail); summary `{3,2,1}`, `verifier_status=FAIL`.

**outputs**
```json
{ "widget": { "mounts": true, "controls_present": true, "labeled": false, "passed": false },
  "summary": { "total": 3, "passed": 2, "failed": 1 } }
```
Evidence per check: `{ selector, match }`.

**verifier re-derivation**: CF Worker re-fetches rendered HTML (via the render service) and re-selects widget + controls + attributes, recomputes `summary`, FAILs on mismatch.

**pattern_expansion rule**: Fans across **ALL** pages that mount the chat widget (or the shared component instance). E2E: `WC-6 → [WC-6, WC-6a, WC-6b]` over `/`, `/pricing`, `/support`.

**risk note**: `low_risk_patch`, `approval_required: true`. Sandbox job `patch_diff` → `sandbox/.../SJ-6/chat-input-label.diff`. Becomes AP-6 (`low_risk_patch`, `META`, "Add aria-label/placeholder to chat input", additive attribute).

---

## Template 9 — `mobile_responsive_smoke_check`

- **id**: `mobile_responsive_smoke_check`
- **purpose**: Smoke-check mobile viewport health: viewport meta present, no horizontal overflow, tap targets not sub-min.
- **target_kind**: `website | web_app`
- **mapped factory_category**: `CAT-10-VERTICAL-PROOF-PRODUCTS`
- **value_class**: `GUARD`
- **sequencing**: NOT in first-five. Heavier than pure HTTP — needs a headless render at a fixed viewport; sequenced after the first five.

**inputs**
```json
{ "viewport": "375x812", "min_tap_px": 44 }
```

**deterministic checks**

| name | logic | pass_condition |
|---|---|---|
| `viewport_meta_present` | Regex on served HTML `<head>` for `<meta name="viewport">`. | `meta[name=viewport]` with `width=device-width` present |
| `no_horizontal_overflow` | Headless render at exactly 375px width; measure `document.scrollWidth` vs `innerWidth`. | `document.scrollWidth <= 375 + tolerance` |

`tolerance` is fixed (e.g. 1px) and identical on both sides so the measurement is reproducible. `min_tap_px` (44) governs an optional tap-target sub-check when tap targets are enumerated; the two mandatory checks above are the deterministic core.

**pass/fail conditions**
- `viewport_meta_present` fails when the meta tag is absent or lacks `width=device-width`.
- `no_horizontal_overflow` fails when measured `scrollWidth` exceeds `375 + tolerance` (page overflows horizontally on mobile).
- Contract passes iff both pass.

**outputs**
```json
{ "responsive": { "viewport_meta": true, "overflow_px": 0, "passed": true },
  "summary": { "total": 2, "passed": 2, "failed": 0 } }
```
Evidence: `viewport_meta_present` → `{ regex, match }`; `no_horizontal_overflow` → `{ actual, expected, match }` (measured px vs 375+tolerance).

**verifier re-derivation**: CF Worker (or the headless render service the Worker calls) re-measures at the **fixed** viewport (375x812), recomputes `summary`, FAILs on mismatch. Heavier than pure HTTP — sequenced after the first five.

**pattern_expansion rule**: Fans across **ALL** key routes (home, pricing, product, auth) at the fixed mobile viewport.

**risk note**: `read_only` for measurement; any layout fix is a downstream `canonical_change` requiring approval.

---

## Template 10 — `route_health_check`

- **id**: `route_health_check`
- **purpose**: Verify a set of key routes return 2xx and are non-empty (baseline liveness of the surface's spine).
- **target_kind**: `website | web_app | dashboard`
- **mapped factory_category**: `CAT-09-RECEIPT-TRUST-AUDIT-LAYER`
- **value_class**: `GUARD`
- **note**: First-of-first-five. Mirrors the shipped CAT-10 `http_200` poller doctrine exactly.

**inputs**
```json
{ "routes": ["/", "/pricing", "/apply-for-program", "/login"], "expected_status": [200] }
```
Routes are resolved against `target_url`.

**deterministic checks** (one instantiated per route)

| name | logic | pass_condition |
|---|---|---|
| `route_returns_2xx` | HTTP `GET` each route (resolved against `target_url`), ≤5 redirects; read final status and `content-length`/body bytes. | `status == 200 AND content-length > 0` |

**pass/fail conditions**
- Each route check passes on final status `200` with a non-empty body.
- Fails on any non-200 (incl. 3xx that doesn't terminate at 200, 4xx, 5xx), timeout, or empty body.
- Contract passes iff **all** route checks pass.

**outputs**
```json
{ "per_route": { "route": "/pricing", "http_status": 200, "bytes": 21843, "passed": true },
  "summary": { "total": 4, "passed": P, "failed": F } }
```
Evidence: `{ url, http_status, body_sha256 }` (body hash proves non-empty + pins the served bytes).

**verifier re-derivation**: CF Worker re-fetches each route, recomputes `passed` + `summary` from `checks[]`; FAILs on mismatch. Mirrors the CAT-10 `http_200` poller doctrine exactly.

**pattern_expansion rule**: Fans across **ALL** discovered/declared key routes (sitemap or nav-derived) — enumerate routes from the sitemap or nav and instantiate one `route_returns_2xx` per route.

**risk note**: `read_only`. A dead route surfaces as a `canonical_change` ApprovalItem for the fix (as with the `/apply-for-program` 404 and `/login` 500 in the E2E).

---

## Canonical E2E — how the 10 templates chain (reference, do not diverge)

Single canonical worked chain from `_SPINE_v1.json.e2e_example` (founder-supplied `{TARGET_URL}`; nothing here fetches a live surface):

- **Founder voice note**: *"Apply for Program link is broken. Cookie link goes nowhere. Sign-in is broken. Acme Brief twelve-thousand-dollar six-week package copy needs update. Request IDs are not visible. Web chat UI is bad."*
- **1 VoiceNote (VN-1) → 1 Transcript (TR-1)** — normalized `twelve thousand dollar → $12,000`, `six week → 8-week`.
- **6 Observations (OB-1…OB-6)** → **6 IssueClusters (IC-1…IC-6)** → **6 WorkflowContracts (WC-1…WC-6)**:

| Contract | Cluster | template_id | risk_class | value_class | factory_category |
|---|---|---|---|---|---|
| WC-1 | IC-1 | `cta_route_check` | read_only | REVENUE | CAT-10-VERTICAL-PROOF-PRODUCTS |
| WC-2 | IC-2 | `legal_footer_link_check` | read_only | GUARD | CAT-09-RECEIPT-TRUST-AUDIT-LAYER |
| WC-3 | IC-3 | `auth_entrypoint_check` | read_only | REVENUE | CAT-10-VERTICAL-PROOF-PRODUCTS |
| WC-4 | IC-4 | `pricing_claim_consistency_check` (+ sibling `offer_copy_consistency_check`) | canonical_change | REVENUE | CAT-10-VERTICAL-PROOF-PRODUCTS |
| WC-5 | IC-5 | `request_id_visibility_check` | low_risk_patch | GUARD | CAT-09-RECEIPT-TRUST-AUDIT-LAYER |
| WC-6 | IC-6 | `web_chat_ux_check` | low_risk_patch | META | CAT-09-RECEIPT-TRUST-AUDIT-LAYER |

- **6 SandboxJobs** in `CAT-05-SANDBOX-WORKTREE-EXECUTION` (3 `inspect`: SJ-1/2/3; 3 `patch_diff`: SJ-4/5/6, diffs staged never applied) → **6 VerificationRuns** → **6 `field_audit_receipt_v1`** — **ALL `verifier_status=FAIL`** (the surface is genuinely broken: 404 CTA, dead cookie href, 500 login, `$9,000`/`5-week` vs `$12,000`/`8-week`, no request id, unlabeled chat input) → **6 pending ApprovalItems (AP-1…AP-6)**.
- **Pattern expansion** fans each template across siblings (CTAs, legal links + generic `broken_link_scan`, auth entrypoints, commercial surfaces + `offer_copy_consistency_check`, request-id views, chat-mounting pages).
- **Invariant**: No PASS self-minted; no canonical mutation; all diffs staged, none applied. Only the independent CF Worker may issue PASS, only after recomputing `summary` from `checks[]` and confirming edge + secondary-CF-account proof.

## Authority binding (every template obeys)

- **sina-governance-SSOT** = law/registry/locks; owns the templates registry + risk policy this library instantiates. Runs nothing.
- **/sandbox** (this product dir) = authoring & R&D bench, `authority=none`, CANNOT mint PASS; every write stays inside `sandbox/products/field-audit-compiler-v1/`. Sandbox jobs only inspect / patch-into-a-diff / test / return receipts.
- **noetfield-cloud-factory-infra** = verified-execution factory; the independent Cloudflare Worker verifier is the ONLY PASS issuer; Supabase is the ledger.
- **CAT-05-SANDBOX-WORKTREE-EXECUTION** = the watcher slot that runs the `SandboxJob` in an isolated worktree (a factory category, not the whole sandbox).
- **CAT-09-RECEIPT-TRUST-AUDIT-LAYER** = trust/receipt center of gravity; GUARD/META receipts promote here.
- **CAT-10-VERTICAL-PROOF-PRODUCTS** = REVENUE / vertical-proof receipts promote here.
- **EXECUTION RULE**: all generated work goes to sandbox FIRST; NO direct deploy, merge, deletion, cron unlock, real send, or canonical-repo mutation from raw voice. Canonical changes require an approved `ApprovalItem` or an explicitly-scoped low-risk rule. Every check runs ONLY against the founder-supplied `{TARGET_URL}`/`target_ref`.
