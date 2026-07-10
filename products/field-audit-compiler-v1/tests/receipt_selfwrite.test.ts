/**
 * T4 tests — VerificationRun self-write. Run: `npx tsx tests/receipt_selfwrite.test.ts`.
 * Proves: receipt is UNVERIFIED/authority=none and validates against RECEIPT_SCHEMA; NO PASS can be
 * self-minted; summary == recompute(checks); a tampered summary is detected (CF-Worker FAIL doctrine).
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';
import { loadRegistry } from '../src/cluster/select_template.ts';
import { generateContract } from '../src/compile/generate_contract.ts';
import { selfWriteReceipt } from '../src/verify/selfwrite_receipt.ts';
import { recomputeSummary, summaryMatches, type Check } from '../src/verify/recompute_summary.ts';
import { compileFromFile } from '../src/lib/jsonschema.ts';
import type { IssueCluster } from '../src/cluster/cluster.ts';

const __dir = dirname(fileURLToPath(import.meta.url));
const PRODUCT_DIR = resolve(__dir, '..');
const clusters: IssueCluster[] = JSON.parse(readFileSync(join(PRODUCT_DIR, 'fixtures', 'AS-2026-07-09-fieldaudit', 'clusters.json'), 'utf8'));
const registry = loadRegistry();
const validateReceipt = compileFromFile(join(PRODUCT_DIR, 'RECEIPT_SCHEMA_FIELD_AUDIT_v1.json'));
function assert(c: boolean, m: string) { if (!c) throw new Error(m); }

const wc1 = generateContract(clusters[0], registry); // cta_route_check
const checks: Check[] = [
  { name: 'cta_present', passed: true, detail: 'a[data-cta] found', evidence: { selector: "a[data-cta]", match: true } },
  { name: 'cta_route_resolves', passed: false, detail: 'GET /apply-for-program -> 404', evidence: { url: '/apply-for-program', http_status: 404 } },
];
const AT = '2026-07-09T20:05:00Z';

const TESTS: Array<[string, () => void]> = [

  ['self-written receipt is UNVERIFIED / authority=none and validates against RECEIPT_SCHEMA', () => {
    const r = selfWriteReceipt({ contract: wc1, jobId: 'SJ-1', checks, checked_at: AT });
    assert(r.verifier_status === 'UNVERIFIED', 'must be UNVERIFIED');
    assert(r.authority === 'none', 'authority must be none');
    assert(r.schema === 'field_audit_receipt_v1', 'schema discriminator');
    const v = validateReceipt(r);
    assert(v.valid, `receipt must validate: ${v.errors.join('; ')}`);
  }],

  ['summary equals recompute(checks); total == passed + failed == checks.length', () => {
    const r = selfWriteReceipt({ contract: wc1, jobId: 'SJ-1', checks, checked_at: AT });
    const expect = recomputeSummary(checks);
    assert(JSON.stringify(r.summary) === JSON.stringify(expect), 'summary must equal recompute');
    assert(r.summary.total === r.summary.passed + r.summary.failed && r.summary.total === checks.length, 'total == passed+failed == len');
    assert(r.summary.total === 2 && r.summary.passed === 1 && r.summary.failed === 1, 'expected {2,1,1}');
  }],

  // ------- RED-CAPABLE (b): no self-mint + tamper detection -------
  ['RED-CAPABLE: PASS cannot be self-minted (requestedStatus PASS -> coerced UNVERIFIED)', () => {
    const r = selfWriteReceipt({ contract: wc1, jobId: 'SJ-1', checks, checked_at: AT, requestedStatus: 'PASS' });
    assert(r.verifier_status === 'UNVERIFIED', 'a requested PASS MUST be coerced to UNVERIFIED (if PASS escapes -> RED)');
    assert(r.authority === 'none', 'authority stays none');
  }],

  ['RED-CAPABLE: a tampered summary is detected (CF-Worker FAIL-on-mismatch doctrine)', () => {
    const r = selfWriteReceipt({ contract: wc1, jobId: 'SJ-1', checks, checked_at: AT });
    assert(summaryMatches(r.summary, r.checks), 'honest receipt: summary matches checks');
    const tampered = { ...r, summary: { ...r.summary, passed: 2, failed: 0 } }; // lie: claim all passed
    assert(!summaryMatches(tampered.summary, tampered.checks), 'tampered summary MUST be detected as mismatch (else RED)');
  }],
];

let failed = 0;
for (const [name, fn] of TESTS) {
  try { fn(); console.log(`PASS  ${name}`); }
  catch (e) { failed++; console.log(`FAIL  ${name}: ${(e as Error).message}`); }
}
console.log(`\n${TESTS.length - failed}/${TESTS.length} green`);
process.exit(failed ? 1 : 0);
