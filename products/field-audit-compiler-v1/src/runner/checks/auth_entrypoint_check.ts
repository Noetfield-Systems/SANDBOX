/**
 * auth_entrypoint_check — a sign-in/login entrypoint exists AND its route returns HTTP 200
 * (not 4xx/5xx). Two checks: auth_entry_present, auth_route_resolves. Pure/no-LLM; target host only.
 */
import type { Check } from '../../verify/recompute_summary.ts';
import type { WorkflowContract } from '../../compile/generate_contract.ts';
import type { CheckCtx } from '../sandbox_job.ts';

/** Hrefs of anchors that point at a login/signin route. */
export function extractAuthHrefs(html: string): string[] {
  const re = /<a\b[^>]*\bhref\s*=\s*["']([^"']*)["'][^>]*>/gi;
  const out: string[] = [];
  let m: RegExpExecArray | null;
  while ((m = re.exec(html))) { if (/login|signin|sign-in/i.test(m[1])) out.push(m[1]); }
  return out;
}

export async function authEntrypointCheck(_contract: WorkflowContract, ctx: CheckCtx): Promise<Check[]> {
  ctx.guardedFetch(ctx.targetUrl);
  const html = await (await fetch(ctx.targetUrl, { redirect: 'manual' })).text();
  const auth = extractAuthHrefs(html);
  const present = auth.length > 0;
  const checks: Check[] = [{
    name: 'auth_entry_present', passed: present,
    detail: present ? `auth entrypoint found (${auth[0]})` : 'no auth entrypoint present',
    evidence: { selector: "a[href*='login']", match: present },
  }];
  let status = 0;
  if (present) {
    const url = new URL(auth[0], ctx.targetUrl).toString();
    ctx.guardedFetch(url);
    try { status = (await fetch(url, { redirect: 'manual' })).status; } catch { status = 0; }
  }
  checks.push({
    name: 'auth_route_resolves',
    passed: present && status === 200,
    detail: present ? `GET ${auth[0]} -> HTTP ${status}` : 'no auth route to resolve',
    evidence: { url: auth[0] ?? '', http_status: status },
  });
  return checks;
}
