/**
 * cta_route_check — a primary CTA (a[data-cta]) exists AND its route resolves to HTTP 200.
 * Two checks: cta_present, cta_route_resolves. Pure/no-LLM; fetches only the job's target host.
 */
import type { Check } from '../../verify/recompute_summary.ts';
import type { WorkflowContract } from '../../compile/generate_contract.ts';
import type { CheckCtx } from '../sandbox_job.ts';

const UNRESOLVED = new Set(['', '#', 'javascript:void(0)']);

/** Extract href of every anchor carrying a data-cta attribute. */
export function extractCtaHrefs(html: string): string[] {
  const anchor = /<a\b[^>]*\bdata-cta\b[^>]*>/gi;
  const hrefRe = /\bhref\s*=\s*["']([^"']*)["']/i;
  const out: string[] = [];
  let m: RegExpExecArray | null;
  while ((m = anchor.exec(html))) { const h = m[0].match(hrefRe); out.push(h ? h[1] : ''); }
  return out;
}

export async function ctaRouteCheck(_contract: WorkflowContract, ctx: CheckCtx): Promise<Check[]> {
  ctx.guardedFetch(ctx.targetUrl);
  const html = await (await fetch(ctx.targetUrl, { redirect: 'manual' })).text();
  const ctas = extractCtaHrefs(html);
  const present = ctas.length > 0;
  const checks: Check[] = [{
    name: 'cta_present', passed: present,
    detail: present ? `${ctas.length} CTA(s) found` : 'no a[data-cta] present',
    evidence: { selector: 'a[data-cta]', match: present },
  }];
  const href = ctas[0] ?? '';
  const unresolved = UNRESOLVED.has(href.trim());
  let status = 0;
  if (present && !unresolved) {
    const url = new URL(href, ctx.targetUrl).toString();
    ctx.guardedFetch(url);
    try { status = (await fetch(url, { redirect: 'manual' })).status; } catch { status = 0; }
  }
  checks.push({
    name: 'cta_route_resolves',
    passed: present && !unresolved && status === 200,
    detail: present ? `GET ${href} -> HTTP ${status}` : 'no CTA route to resolve',
    evidence: { url: href, http_status: status },
  });
  return checks;
}
