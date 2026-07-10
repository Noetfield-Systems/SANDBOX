# Workflow contract — noetfield-field-audit-redesign-v1

**Status:** executed · **Type:** visual-system redesign (scoped) · **Repo under work:** Noetfield-Systems/Noetfield
**Isolation:** repo-local branch/worktree, not a cross-repo source copy

## Trigger

Founder review of `/`, `/partners/`, `/pricing/` screenshots flagged the site as
"too dense/cluttered," "dated/generic," "inconsistent across pages," and having
mobile/responsive issues. Founder accepted the recommendation to establish a
refined design system against 2-3 flagship pages before any site-wide rollout,
explicitly as a sandboxed, isolated pass — review before deciding, not a live edit.

## Scope (locked in before execution)

- Pages: `/` (homepage), `/partners/`, `/pricing/` only
- Shared files these pages depend on: `assets/noetfield-tokens.css`,
  `assets/noetfield-shell.css`, `assets/noetfield-shell.js`,
  `assets/noetfield-v20-tier1.css`, `assets/noetfield-chat.css`,
  `assets/noetfield-chat.js`
- Out of scope: any other page, any backend/API behavior, any content/copy
  changes, any deploy or merge action

## Isolation mechanism

- Branch: `sandbox/noetfield-field-audit-redesign-v1`
- Base ref: `origin/main` at merge commit `b609948b` (PR #103)
- Location: git worktree inside the canonical `Noetfield-Systems/Noetfield`
  repo (`.claude/worktrees/sandbox+noetfield-field-audit-redesign-v1`) — NOT
  a copy into a separate repository
- Production `main` was never touched; no deploy, merge, or delete was
  performed against it

## Constraint correction mid-task

An earlier attempt to seed this work by copying production source files
(pages, CSS/JS, partials) into the separate `Noetfield-Systems/SANDBOX` repo
was blocked by a data-exfiltration guardrail and abandoned without retry or
workaround. The founder then specified the corrected strategy this contract
follows: SANDBOX stores evidence/metadata only; source-level isolation
happens via a repo-local branch/worktree in the canonical repo instead.

## Findings that shaped the scope

Static analysis of the design-token architecture, done before any edit,
found the actual root cause of the "generic/dated" complaint: `--font-display`
and `--font-serif` both resolved to Inter — the same typeface as body copy —
across every headline sitewide, with two separate files re-declaring this
after the base token definition (one of them, `noetfield-v20-tier1.css`,
explicitly commented "Linear / Stripe / Vercel grade"). This made the fix
surgical rather than exploratory: a small number of token-level changes
cascade correctly through already-correct selector wiring, rather than
requiring new component HTML/CSS.

See `receipts/noetfield-field-audit-redesign-v1-audit-receipt.json` for the
verification record and `promotion-decisions/noetfield-field-audit-redesign-v1-promotion-decision.md`
for the recommendation.
