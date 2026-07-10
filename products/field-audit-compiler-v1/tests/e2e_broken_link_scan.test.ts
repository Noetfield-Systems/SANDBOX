/**
 * T5 E2E — observation -> cluster -> selection -> contract -> sandbox job -> broken_link_scan ->
 * verifier self-write -> field_audit_receipt_v1 (UNVERIFIED) -> promotion decision packet.
 * Runs against a sandbox-local 127.0.0.1 fixture server ({TARGET_URL}); NO live surface, NO mutation,
 * NO merge, NO deploy, NO source copy into SANDBOX. Run: `npx tsx tests/e2e_broken_link_scan.test.ts`.
 */
import { readFileSync, rmSync } from 'node:fs';
import { createServer } from 'node:http';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';
import { loadRegistry } from '../src/cluster/select_template.ts';
import { generateContract } from '../src/compile/generate_contract.ts';
import { runSandboxJob } from '../src/runner/sandbox_job.ts';
import { brokenLinkScan } from '../src/runner/checks/broken_link_scan.ts';
import { recomputeSummary, summaryMatches } from '../src/verify/recompute_summary.ts';
import { compileFromFile } from '../src/lib/jsonschema.ts';
import type { IssueCluster } from '../src/cluster/cluster.ts';

const __dir = dirname(fileURLToPath(import.meta.url));
const PRODUCT_DIR = resolve(__dir, '..');
const RUNS = join(PRODUCT_DIR, '.sandbox_runs', 't5');
const FX = join(PRODUCT_DIR, 'fixtures');
const html = readFileSync(join(FX, 'target-surface', 'index.html'), 'utf8');
const validateReceipt = compileFromFile(join(PRODUCT_DIR, 'RECEIPT_SCHEMA_FIELD_AUDIT_v1.json'));
const registry = loadRegistry();
function assert(c: boolean, m: string) { if (!c) throw new Error(m); }

// broken_link_scan contract for the "Apply for Program link is broken" surface scan
const cluster: IssueCluster = { id: 'IC-BL', session_id: 'AS-2026-07-09-fieldaudit', observation_ids: ['OB-1'], defect_kind: 'broken_link', label: 'Broken links (incl. Apply for Program)', target_refs: ['a[href]'], severity: 'blocker', dedup_note: 'broken_link_scan over nav+footer (WC-2c expansion) catches the Apply-for-Pilot 404.' };

async function withServer<T>(fn: (base: string, hostHits: Set<string>) => Promise<T>): Promise<T> {
  const hostHits = new Set<string>();
  const server = createServer((req, res) => {
    hostHits.add(req.headers.host || '');
    const url = (req.url || '/').split('?')[0];
    if (url === '/') { res.writeHead(200, { 'content-type': 'text/html' }); res.end(html); }
    else if (url === '/healthy') { res.writeHead(200, { 'content-type': 'text/html' }); res.end('<p>ok</p>'); }
    else if (url === '/apply-for-program') { res.writeHead(404, { 'content-type': 'text/html' }); res.end('<p>not found</p>'); }
    else { res.writeHead(404); res.end('nope'); }
  });
  await new Promise<void>((r) => server.listen(0, '127.0.0.1', () => r()));
  const port = (server.address() as any).port;
  try { return await fn(`http://127.0.0.1:${port}/`, hostHits); }
  finally { server.close(); }
}

const TESTS: Array<[string, () => Promise<void>]> = [

  ['full E2E emits a schema-valid field_audit_receipt_v1 (UNVERIFIED) with one check per unique href', async () => {
    await withServer(async (base, hostHits) => {
      const contract = generateContract(cluster, registry, { target_url: base });
      const { job, receipt } = await runSandboxJob(contract, (c, ctx) => brokenLinkScan(c, ctx), { runsDir: RUNS });
      assert(receipt.schema === 'field_audit_receipt_v1', 'schema');
      assert(receipt.session_id === 'AS-2026-07-09-fieldaudit', 'session_id');
      assert(receipt.category_id === 'CAT-09-RECEIPT-TRUST-AUDIT-LAYER', `category ${receipt.category_id}`);
      assert(receipt.value_class === 'GUARD', 'value_class GUARD');
      assert(receipt.verifier_status === 'UNVERIFIED' && receipt.authority === 'none', 'UNVERIFIED / authority none');
      assert(job.job_kind === 'inspect', 'broken_link_scan is read_only -> inspect');
      // one check per unique href: /healthy, /apply-for-program, #
      assert(receipt.checks.length === 3, `expected 3 unique-href checks, got ${receipt.checks.length}`);
      const v = validateReceipt(receipt);
      assert(v.valid, `receipt must validate: ${v.errors.join('; ')}`);
      // no request left 127.0.0.1
      assert([...hostHits].every((h) => h.startsWith('127.0.0.1')), `only 127.0.0.1 may be hit, saw ${[...hostHits]}`);
    });
  }],

  ['healthy link passes (200); Cookie # and Apply-for-Pilot 404 FAIL with evidence', async () => {
    await withServer(async (base) => {
      const contract = generateContract(cluster, registry, { target_url: base });
      const { receipt } = await runSandboxJob(contract, (c, ctx) => brokenLinkScan(c, ctx), { runsDir: RUNS });
      const byUrl = (frag: string) => receipt.checks.find((c) => (c.evidence?.url || '').includes(frag));
      assert(byUrl('/healthy')!.passed === true && byUrl('/healthy')!.evidence!.http_status === 200, 'healthy must pass with 200');
      assert(byUrl('/apply-for-program')!.passed === false && byUrl('/apply-for-program')!.evidence!.http_status === 404, 'apply-for-program must FAIL with 404');
      const cookie = receipt.checks.find((c) => c.evidence?.url === '#');
      assert(!!cookie && cookie.passed === false, 'Cookie # must FAIL (unresolved)');
      assert(receipt.summary.total === 3 && receipt.summary.passed === 1 && receipt.summary.failed === 2, `summary {3,1,2}, got ${JSON.stringify(receipt.summary)}`);
    });
  }],

  ['produces a PromotionDecisionPacket (pending) — nothing promoted automatically', async () => {
    await withServer(async (base) => {
      const contract = generateContract(cluster, registry, { target_url: base });
      const { job, receipt } = await runSandboxJob(contract, (c, ctx) => brokenLinkScan(c, ctx), { runsDir: RUNS });
      const failing = receipt.checks.filter((c) => !c.passed);
      const pdp = {
        id: 'PDP-BL-1', session_id: receipt.session_id, snapshot_id: 'SNAP-fixture-2026-07-09',
        what_changed: `broken_link_scan found ${failing.length} broken links (incl. /apply-for-program 404, footer Cookie #)`,
        why: 'founder: "Apply for Program link is broken."',
        affected_routes_files: failing.map((c) => c.evidence?.url).filter(Boolean),
        before_after_evidence: failing.map((c) => ({ check: c.name, before: c.detail, after: 'proposed fix staged in sandbox diff (not applied)' })),
        verifier_result: receipt.verifier_status, // UNVERIFIED pending independent CF Worker
        risk_level: 'high', rollback_path: 'no change applied — sandbox diff staged only; nothing to roll back',
        promotion_recommendation: 'needs_founder_decision', decision: 'pending', decided_by: null, decided_at: null,
      };
      for (const k of ['what_changed', 'why', 'affected_routes_files', 'before_after_evidence', 'verifier_result', 'risk_level', 'rollback_path', 'promotion_recommendation']) {
        assert(k in pdp && (pdp as any)[k] != null, `PDP missing ${k}`);
      }
      assert(pdp.decision === 'pending' && pdp.verifier_result === 'UNVERIFIED', 'nothing promoted automatically; verifier still UNVERIFIED');
      assert(pdp.affected_routes_files.length === 2, 'two broken targets surfaced');
      assert(job.diff_ref === null, 'inspect job stages no diff (read_only scan)');
    });
  }],

  // ------- RED-CAPABLE (a) false-negative guard + (b) summary integrity -------
  ['RED-CAPABLE: a bug that passes #/404 diverges (RED); summary tamper detected', async () => {
    await withServer(async (base) => {
      const contract = generateContract(cluster, registry, { target_url: base });
      // GREEN: honest classifier fails #/404
      const { receipt } = await runSandboxJob(contract, (c, ctx) => brokenLinkScan(c, ctx), { runsDir: RUNS });
      assert(receipt.summary.failed === 2, 'honest: 2 failures');
      // seeded bug: classify everything as passing -> #/404 wrongly pass (RED vs honest)
      const buggy = await brokenLinkScan(contract, { targetUrl: base, guardedFetch: () => {} }, () => true);
      assert(buggy.every((c) => c.passed), 'seeded bug passes everything');
      assert(recomputeSummary(buggy).failed === 0 && recomputeSummary(receipt.checks).failed === 2, 'seeded-wrong result diverges from honest (proves discrimination)');
      // (b) summary integrity: tamper one passed boolean without updating summary -> mismatch
      const tampered = receipt.checks.map((c, i) => (i === 0 ? { ...c, passed: !c.passed } : c));
      assert(!summaryMatches(receipt.summary, tampered), 'summary must not match tampered checks (CF-Worker FAIL doctrine)');
    });
  }],
];

(async () => {
  let failed = 0;
  for (const [name, fn] of TESTS) {
    try { await fn(); console.log(`PASS  ${name}`); }
    catch (e) { failed++; console.log(`FAIL  ${name}: ${(e as Error).message}`); }
  }
  rmSync(join(PRODUCT_DIR, '.sandbox_runs'), { recursive: true, force: true });
  console.log(`\n${TESTS.length - failed}/${TESTS.length} green`);
  process.exit(failed ? 1 : 0);
})();
