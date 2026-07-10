# Promotion decision packet — noetfield-field-audit-redesign-v1

**Recommendation: promote, with a scoped follow-up noted below — not a full sign-off on the whole site.**

## What this branch actually changes

A small, verified set of shared-token and two-file JS/CSS edits, applied
against 3 flagship pages (`/`, `/partners/`, `/pricing/`):

1. Real serif display typography (Source Serif 4) on headline-level
   elements, replacing a system where every headline sitewide silently
   rendered in the same typeface as body text.
2. Tighter corner radius (18px→10px / 12px→6px) for a more precise,
   less "soft consumer app" feel.
3. A real mobile bug fix — the floating chat button overlapping the
   sticky bottom CTA bar on the homepage.

9 files, 46 insertions, 14 deletions. No HTML restructuring, no copy
changes, no backend/API changes.

## Why promote

- Addresses the root cause of two of the four complaints raised
  ("dated/generic," "mobile/responsive issues") with the smallest change
  that could plausibly fix them — a token-level typography fix that
  cascades correctly through selectors that were already wired for it,
  rather than a rewrite.
- Went through an adversarial verification pass *before* this
  recommendation, not after — that pass caught a real blocking bug (the
  first mobile-fix attempt was silently inert on real phones) before it
  could have been reported as done. The corrected version was
  independently re-verified via computed-style inspection, not visual
  impression.
- Zero console/page errors across all 3 pages × 2 viewports after
  correction.
- Fully isolated: a repo-local branch off `origin/main`, production never
  touched, easy to inspect via `git diff origin/main..sandbox/noetfield-field-audit-redesign-v1`.

## Why "with a follow-up," not unconditional

Two complaints from the original review are **not** addressed by this
pass, by design:

- **"Too dense/cluttered"** — the homepage hero (3 pricing cards + a full
  interactive governance playground above the fold) needs layout
  restructuring, not a token change. Out of scope here.
- **"Inconsistent across pages"** — partially addressed (typography now
  consistent), but the duplicated "Board PDF" CTA block appearing
  verbatim on both `/` and `/partners/` is a content/layout issue this
  pass didn't touch.

There's also one minor, non-blocking item from the verification receipt:
`--font-serif` is consumed by ~20 selectors across 9 files this pass
didn't individually audit, and at least 3 of them (pricing numerals, one
small card heading) now pick up serif treatment that may or may not be
intentional — worth a quick visual spot-check, not a blocker.

## What "promote" means concretely

Promoting this branch means: merge `sandbox/noetfield-field-audit-redesign-v1`
into `main` (or open it as a normal reviewed PR first — recommended, matching
this repo's existing PR-based workflow for every other change this session),
then run the site's standard Cloudflare Pages deploy script. Nothing in this
packet authorizes that merge or deploy on its own — that action was
explicitly out of scope for this task ("do not deploy, merge, delete, or
mutate production").

## Rollback path

Trivial. The branch is 9 files / 46 lines against a known base commit
(`b609948b`). If merged and something looks wrong: `git revert` the merge
commit, or `git checkout b609948b -- <file>` per-file for a partial
rollback. No migrations, no backend state, no data involved — this is
pure static asset content, safe to revert at any granularity.
