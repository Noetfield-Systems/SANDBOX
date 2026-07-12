/**
 * Check registry — maps a template_id to its runnable CheckFn so the sandbox runner can dispatch by
 * contract. Only deterministic (no-LLM) checks are registered. Templates without an entry are
 * contract-only (not yet executable) and resolveCheck returns null.
 */
import type { CheckFn } from '../sandbox_job.ts';
import { brokenLinkScan } from './broken_link_scan.ts';
import { routeHealthCheck } from './route_health_check.ts';
import { ctaRouteCheck } from './cta_route_check.ts';
import { authEntrypointCheck } from './auth_entrypoint_check.ts';
import { requestIdVisibilityCheck } from './request_id_visibility_check.ts';

export const CHECK_REGISTRY: Record<string, CheckFn> = {
  broken_link_scan: (c, ctx) => brokenLinkScan(c, ctx),
  route_health_check: routeHealthCheck,
  cta_route_check: ctaRouteCheck,
  auth_entrypoint_check: authEntrypointCheck,
  request_id_visibility_check: requestIdVisibilityCheck,
};

/** The first-five template ids that now have a runnable check. */
export const RUNNABLE_FIRST_FIVE = [
  'route_health_check', 'broken_link_scan', 'cta_route_check', 'auth_entrypoint_check', 'request_id_visibility_check',
];

export function resolveCheck(template_id: string): CheckFn | null {
  return CHECK_REGISTRY[template_id] ?? null;
}
