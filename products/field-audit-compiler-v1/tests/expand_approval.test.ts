/**
 * Upgrade — pattern expander (step 10) + approval queue (step 9).
 * Run: `npx tsx tests/expand_approval.test.ts`.
 * Proves: one contract fans across sibling scopes (dedup, unique ids); approval items are ALWAYS
 * pending (never auto-approved / auto-applied); a clean receipt yields no approval item.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';
import { loadRegistry } from '../src/cluster/select_template.ts';
import { generateContract } from '../src/compile/generate_contract.ts';
import { expandContract, expansionWidth } from '../src/compile/expand.ts';
import { buildApprovalItems } from '../src/compile/approval.ts';
import { selfWriteReceipt } from '../src/verify/selfwrite_receipt.ts';
import type { Check } from '../src/verify/recompute_summary.ts';
import type { IssueCluster } from '../src/cluster/cluster.ts';

const __dir = dirname(fileURLToPath(import.meta.url));
const PRODUCT_DIR = resolve(__dir, '..');
const clusters: IssueCluster[] = JSON.parse(readFileSync(join(PRODUCT_DIR, 'fixtures', 'AS-2026-07-09-fieldaudit', 'clusters.json'), 'utf8'));
const registry = loadRegistry();
function assert(c: boolean, m: string) { if (!c) throw new Error(m); }

const wc1 = generateContract(clusters[0], registry); // cta_route_check WC-1 (read_only)
const wc4 = generateContract(clusters[3], registry); // pricing WC-4 (canonical_change)

const TESTS: Array<[string, () => void]> = [

  ['expander fans ONE contract across sibling scopes (WC-1 -> WC-1a/b/c), base kept', () => {
    const siblings = ["a[data-cta='book-demo']", "a[data-cta='get-started']", "a[data-cta='contact-sales']"];
    const out = expandContract(wc1, siblings);
    assert(out.length === 4, `1 base + 3 siblings = 4, got ${out.length}`);
    assert(out[0].id === 'WC-1' && out[1].id === 'WC-1a' && out[3].id === 'WC-1c', 'ids WC-1, WC-1a..c');
    const scopes = out.map((c) => c.target.scope_selector);
    assert(new Set(scopes).size === scopes.length, 'all expanded scopes are unique');
  }],

  ['RED-CAPABLE: duplicate sibling + the base scope are dropped (no double-scan)', () => {
    const dupSiblings = [wc1.target.scope_selector, "a[data-cta='book-demo']", "a[data-cta='book-demo']"];
    const width = expansionWidth(wc1, dupSiblings);
    assert(width === 2, `base + 1 unique sibling = 2 (dedup base + duplicate), got ${width} (a naive expander would emit 4 -> RED)`);
  }],

  ['approval item is built for a FAILING receipt, always pending, carries the staged diff', () => {
    const checks: Check[] = [{ name: 'cta_route_resolves', passed: false, detail: '404', evidence: { url: '/x', http_status: 404 } }];
    const receipt = selfWriteReceipt({ contract: wc4, jobId: 'SJ-4', checks, checked_at: '2026-07-09T20:00:00Z' });
    const items = buildApprovalItems(receipt, wc4, { diff_ref: '.sandbox_runs/SJ-4/proposed.diff' });
    assert(items.length === 1, 'one failing receipt -> one approval item');
    assert(items[0].decision === 'pending', 'approval item MUST be pending (never auto-approved)');
    assert(items[0].proposed_patch_ref === '.sandbox_runs/SJ-4/proposed.diff', 'carries the staged diff ref');
    assert(items[0].risk_class === 'canonical_change', 'preserves the contract risk_class');
    assert(items[0].id === 'AP-4' && items[0].workflow_contract_id === 'WC-4', 'AP id + FK to WC-4');
  }],

  ['RED-CAPABLE: a CLEAN receipt (0 failures) yields NO approval item', () => {
    const checks: Check[] = [{ name: 'route_returns_2xx', passed: true, detail: '200', evidence: { url: '/', http_status: 200 } }];
    const receipt = selfWriteReceipt({ contract: wc1, jobId: 'SJ-1', checks, checked_at: '2026-07-09T20:00:00Z' });
    const items = buildApprovalItems(receipt, wc1);
    assert(items.length === 0, 'a passing receipt MUST create no approval item (nothing to fix -> RED if one appears)');
  }],

  ['no auto-apply: no approval item is ever emitted as approved/applied', () => {
    const checks: Check[] = [{ name: 'x', passed: false, detail: 'fail', evidence: { match: false } }];
    const r = selfWriteReceipt({ contract: wc4, jobId: 'SJ-4', checks, checked_at: '2026-07-09T20:00:00Z' });
    for (const item of buildApprovalItems(r, wc4)) {
      assert(item.decision === 'pending' && item.decided_by === null && item.decided_at === null, 'items must be undecided (founder-gated)');
    }
  }],
];

let failed = 0;
for (const [name, fn] of TESTS) {
  try { fn(); console.log(`PASS  ${name}`); }
  catch (e) { failed++; console.log(`FAIL  ${name}: ${(e as Error).message}`); }
}
console.log(`\n${TESTS.length - failed}/${TESTS.length} green`);
process.exit(failed ? 1 : 0);
