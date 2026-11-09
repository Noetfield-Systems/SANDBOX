# SHIFT — AI Agency Launch Platform

**Operator:** Noetfield Systems Inc.  
**Status:** First public release (2026-11-09); production URL `https://shift-web-production-363a.up.railway.app/`  
**Railway project:** `agencyshift-ai` / production  
**Runtime:** Bun TypeScript Railway Function, PostgreSQL 18

## Product promise

Help independent professionals move from a vague desire to start an AI agency to a **specific niche, a clear offer, publishable draft assets, and measurable buyer conversations**. The free creative tool is the acquisition mechanism, not a substitute for a commercial delivery system.

## Implemented

- Dark 2027-style, accessible responsive landing page
- No-login free creative studio for hooks, video scripts, ads, positioning, outreach and seven-day launch plan
- Six core niches plus creators, platform and voice selection
- Downloadable **campaign draft CSV**; not a verified direct Google/Meta/TikTok Ads upload
- Email/password account registration, Bun Argon2id hashing, hashed database sessions, secure HTTP-only SameSite cookie
- Save, list and reopen users' generated assets
- PostgreSQL-backed lead enquiries and explicit marketing opt-in
- Campaign metrics **manually submitted by the user**: impressions, clicks, leads, paying clients, spend and attributed revenue; computed CTR, cost per lead, lead-to-customer conversion, ROAS
- Anonymous campaign-UTM event collection
- Health endpoint verified through Railway's external POST test (HTTP 200, DB connection)
- Privacy, terms, and income disclaimer
- Optional DeepSeek Chat Completions integration if and only if `DEEPSEEK_API_KEY` is configured; template fallback is explicit in UI

## Configuration

1. Deploy a Railway PostgreSQL service with durable volume.
2. Create a Railway Function named `shift-web` using `railway-function/index.tsx`.
3. Set `DATABASE_URL=${{Postgres.DATABASE_URL}}` in the same Railway environment.
4. Optionally set `DEEPSEEK_API_KEY` in Railway Variables (secret); `DEEPSEEK_MODEL` defaults to `deepseek-chat`.
5. Give the service a public domain. Its HTTP listener uses `PORT` automatically.

**Never commit live API keys.** Database connection strings, secrets and personal information are not present in this repository.

## Conversion model (targets, NOT results)

- **Attract:** 1M+ distributed views, earned through original useful short-form content, SEO, creator affiliates and selective paid tests.
- **Activate:** free builder with useful output **before account registration**.
- **Capture:** opt-in account creation and brand-specific launch plans.
- **Convert:** sell genuinely provisioned paid automation/research features only after real service delivery, billing/entitlements and customer management are commissioned.

Early KPI dashboard: visitors -> tool use -> signup -> qualified enquiry -> purchased service; break down by UTM channel. A high number of impressions is not equivalent to users or sales. Do not represent projected traffic or illustrative product mock-ups as real traction.

## Critical remaining work (do not misrepresent as launched)

- Stripe **live billing**: product/price, taxes, checkout, billing portal, webhook, subscription entitlement and churn/dunning (not connected).
- AI mode needs dedicated provider credential; currently template generation is always available.
- Premium differentiated research needs verified external data sources, attribution, source-date transparency and evaluation. Do not call it live deep research before implementing those steps.
- Meta/TikTok/Google **live ad launching** needs platform OAuth, account authorization, app review where applicable, billing permissions, campaign policy compliance and budget approval.
- User data self-service export/deletion, verified email, password reset, mail notifications and deliverability, formal monitoring/sentry, abuse protection, accessibility/performance audit, backups/PITR, retention policies and production load testing.
- Agency operations integration with Sina OS/Company OS is not connected; contract and authorization boundary to be defined.
- Formal test suite and automated end-to-end independent verification are not included in v1; public health and deployment evidence alone do not establish all user journeys.

## Security/design choices

- No invented customer reviews, earnings figures, scarcity counter, lead counts or guaranteed ROAS.
- No autonomous campaign spend or outbound spam. Marketing communications require compliant consent, sender identity and unsubscribe.
- User-level DB access is enforced by session derived user ID and parameterized SQL.
- No client-controlled HTTP destination, no public admin APIs, no raw database credentials in frontend.

## Validating

1. `POST /health` => HTTP 200 with `db:connected`, when Railway Postgres is healthy.
2. Use the browser to generate assets without registering; expect hooks, script, ad drafts and 7-day plan.
3. Register with a genuine email / secure password; save a campaign; sign out; sign in; reload saved campaign.
4. In the workspace, record a metric snapshot and reopen; test CTR/CPL/ROAS against your actual data.
5. Open the mobile view, keyboard navigate and test all CTA/consent flows.
6. Verify production logs and HTTP error rates after each release.

No ad spend or third-party marketing campaign was launched as part of v1.
