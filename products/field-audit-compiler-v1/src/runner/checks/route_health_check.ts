/**
 * route_health_check — GET each declared route; passed = HTTP 200 AND non-empty body.
 * Pure/no-LLM. Reads routes from the contract; fetches only the job's target host (guardedFetch).
 */
import type { Check } from '../../verify/recompute_summary.ts';
import type { WorkflowContract } from '../../compile/generate_contract.ts';
import type { CheckCtx } from '../sandbox_job.ts';

export async function routeHealthCheck(contract: WorkflowContract, ctx: CheckCtx): Promise<Check[]> {
  const routes: string[] = (contract.params?.routes as string[]) ?? ['/'];
  const checks: Check[] = [];
  for (const route of routes) {
    const url = new URL(route, ctx.targetUrl).toString();
    ctx.guardedFetch(url);
    let status = 0; let len = 0;
    try { const r = await fetch(url, { redirect: 'manual' }); status = r.status; len = (await r.text()).length; } catch { status = 0; }
    checks.push({
      name: 'route_returns_2xx',
      passed: status === 200 && len > 0,
      detail: `GET ${route} -> HTTP ${status} (${len}b)`,
      evidence: { url, http_status: status },
    });
  }
  return checks;
}
