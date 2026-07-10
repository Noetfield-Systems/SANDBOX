/**
 * T5 — the real broken_link_scan check. Fetches the target page, enumerates a[href] (ignoring
 * mailto:/tel:), HTTP GETs each resolved href against the JOB'S target only (ctx.guardedFetch
 * enforces same-host), and emits one deterministic check per unique href:
 *   passed = href not in ['','#','javascript:void(0)'] AND status in [200,301,302,308].
 * Pure/no-LLM. Reads the target from the contract/ctx — never a hardcoded host.
 */
import type { Check } from '../../verify/recompute_summary.ts';
import type { WorkflowContract } from '../../compile/generate_contract.ts';
import type { CheckCtx } from '../sandbox_job.ts';

const IGNORE_PREFIX = ['mailto:', 'tel:'];
const UNRESOLVED = new Set(['', '#', 'javascript:void(0)']);
const OK_STATUS = new Set([200, 301, 302, 308]);

export function extractHrefs(html: string): string[] {
  const hrefs: string[] = [];
  const re = /<a\b[^>]*\bhref\s*=\s*["']([^"']*)["']/gi;
  let m: RegExpExecArray | null;
  while ((m = re.exec(html))) hrefs.push(m[1]);
  return hrefs;
}

/** Default pass classifier — the honest rule. Injectable so a seeded-wrong rule can be shown RED. */
export function defaultClassify(href: string, status: number): boolean {
  return !UNRESOLVED.has(href.trim()) && OK_STATUS.has(status);
}

export async function brokenLinkScan(
  _contract: WorkflowContract, ctx: CheckCtx,
  classify: (href: string, status: number) => boolean = defaultClassify,
): Promise<Check[]> {
  const base = ctx.targetUrl;
  ctx.guardedFetch(base);
  const pageRes = await fetch(base, { redirect: 'manual' });
  const html = await pageRes.text();
  const links = extractHrefs(html).filter((h) => !IGNORE_PREFIX.some((p) => h.toLowerCase().startsWith(p)));
  const unique = [...new Set(links)];
  const checks: Check[] = [];
  for (const href of unique) {
    const unresolved = UNRESOLVED.has(href.trim());
    let status = 0;
    let resolved = href;
    if (!unresolved) {
      resolved = new URL(href, base).toString();
      ctx.guardedFetch(resolved); // AUTHORITY WALL: only the job's target host
      try { status = (await fetch(resolved, { redirect: 'manual' })).status; } catch { status = 0; }
    }
    const passed = classify(href, status);
    checks.push({
      name: 'href_resolves',
      passed,
      detail: unresolved ? `href '${href}' is unresolved (empty/#/void)` : `GET ${href} -> HTTP ${status}`,
      evidence: unresolved ? { url: href, match: false } : { url: resolved, http_status: status },
    });
  }
  return checks;
}
