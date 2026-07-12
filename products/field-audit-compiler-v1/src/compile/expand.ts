/**
 * Pattern expander (pipeline step 10). Deterministically fans ONE WorkflowContract across sibling
 * routes/components: given a base contract + the sibling scope_selectors discovered on the surface,
 * emit one expanded contract per unique sibling (ids WC-<base>a, WC-<base>b, …). No LLM, no mutation.
 */
import type { WorkflowContract } from './generate_contract.ts';

const SUFFIX = 'abcdefghijklmnopqrstuvwxyz';

/**
 * expandContract(base, siblingScopes) -> [base, ...expanded]. The base is kept as the seed; each
 * unique sibling scope becomes an expanded contract with a suffixed id and its own scope_selector.
 * Duplicate scopes (and the base's own scope) are dropped so the fan-out is exactly the new siblings.
 */
export function expandContract(base: WorkflowContract, siblingScopes: string[]): WorkflowContract[] {
  const seen = new Set<string>([base.target.scope_selector]);
  const uniqueSiblings = siblingScopes.filter((s) => { if (seen.has(s)) return false; seen.add(s); return true; });
  const expanded = uniqueSiblings.map((scope, i) => ({
    ...base,
    id: `${base.id}${SUFFIX[i] ?? `-x${i}`}`,
    target: { ...base.target, scope_selector: scope },
  }));
  return [base, ...expanded];
}

/** Convenience: just the count of deterministic workflows one observation expands into. */
export function expansionWidth(base: WorkflowContract, siblingScopes: string[]): number {
  return expandContract(base, siblingScopes).length;
}
