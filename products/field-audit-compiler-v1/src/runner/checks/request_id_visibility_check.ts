/**
 * request_id_visibility_check — a request/correlation id is rendered to the user (regex match on
 * text) OR a non-empty [data-request-id] attribute is present. One check. Pure/no-LLM; target only.
 */
import type { Check } from '../../verify/recompute_summary.ts';
import type { WorkflowContract } from '../../compile/generate_contract.ts';
import type { CheckCtx } from '../sandbox_job.ts';

const DEFAULT_ID_REGEX = '(req|request|corr)[-_ ]?id[:#]?\\s*[A-Za-z0-9-]{6,}';

export async function requestIdVisibilityCheck(contract: WorkflowContract, ctx: CheckCtx): Promise<Check[]> {
  ctx.guardedFetch(ctx.targetUrl);
  const html = await (await fetch(ctx.targetUrl, { redirect: 'manual' })).text();
  const src = (contract.params?.id_regex as string) ?? DEFAULT_ID_REGEX;
  const rx = new RegExp(src, 'i');
  const dataAttr = /data-request-id\s*=\s*["']([^"']+)["']/i.exec(html);
  const visible = rx.test(html) || (!!dataAttr && dataAttr[1].trim().length > 0);
  return [{
    name: 'request_id_visible',
    passed: visible,
    detail: visible ? 'request id visible in rendered view' : 'no request-id pattern or [data-request-id] in rendered view',
    evidence: { regex: src.slice(0, 60), match: visible },
  }];
}
