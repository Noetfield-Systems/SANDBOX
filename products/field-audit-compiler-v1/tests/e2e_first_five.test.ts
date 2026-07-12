/**
 * Upgrade E2E — all FIVE first-five checks run against one 127.0.0.1 fixture surface, each emitting a
 * schema-valid field_audit_receipt_v1 (UNVERIFIED). Run: `npx tsx tests/e2e_first_five.test.ts`.
 * Proves the engine is multi-check (not one-template), and each check discriminates pass vs fail.
 */
import { rmSync } from 'node:fs';
import { createServer } from 'node:http';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';
import { loadRegistry } from '../src/cluster/select_template.ts';
import { generateContract } from '../src/compile/generate_contract.ts';
import { runSandboxJob } from '../src/runner/sandbox_job.ts';
import { resolveCheck, RUNNABLE_FIRST_FIVE } from '../src/runner/checks/index.ts';
import { compileFromFile } from '../src/lib/jsonschema.ts';
import type { IssueCluster } from '../src/cluster/cluster.ts';
import type { DefectKind } from '../src/stage1/extract_observations.ts';

const __dir = dirname(fileURLToPath(import.meta.url));
const PRODUCT_DIR = resolve(__dir, '..');
const RUNS = join(PRODUCT_DIR, '.sandbox_runs', 'first5');
const registry = loadRegistry();
const validateReceipt = compileFromFile(join(PRODUCT_DIR, 'RECEIPT_SCHEMA_FIELD_AUDIT_v1.json'));
function assert(c: boolean, m: string) { if (!c) throw new Error(m); }

const HTML = `<!doctype html><html><head><title>Full Fixture</title></head><body>
<nav>
  <a href="/healthy">Healthy</a>
  <a href="/apply-for-program" data-cta="apply-for-program">Apply for Program</a>
  <a href="/login">Sign in</a>
</nav>
<a href="mailto:x@y.com">Email</a>
<main><section data-offer="acme-brief">Acme Brief — $12,000 / 8-week</section></main>
<footer><a href="#">Cookie</a><a href="/healthy">Privacy</a></footer>
</body></html>`;
const HTML_WITH_REQID = HTML.replace('<main>', '<main><p data-request-id="req-abc123def">request id</p>');

function makeServer(html: string) {
  return createServer((req, res) => {
    const url = (req.url || '/').split('?')[0];
    if (url === '/') { res.writeHead(200, { 'content-type': 'text/html' }); res.end(html); }
    else if (url === '/healthy' || url === '/pricing') { res.writeHead(200); res.end('<p>ok</p>'); }
    else if (url === '/apply-for-program') { res.writeHead(404); res.end('nope'); }
    else if (url === '/login') { res.writeHead(500); res.end('boom'); }
    else { res.writeHead(404); res.end('nope'); }
  });
}
async function withServer<T>(html: string, fn: (base: string) => Promise<T>): Promise<T> {
  const server = makeServer(html);
  await new Promise<void>((r) => server.listen(0, '127.0.0.1', () => r()));
  const base = `http://127.0.0.1:${(server.address() as any).port}/`;
  try { return await fn(base); } finally { server.close(); }
}

function contractFor(kind: DefectKind, base: string) {
  const cluster: IssueCluster = { id: 'IC-1', session_id: 'AS-2026-07-09-fieldaudit', observation_ids: ['OB-1'], defect_kind: kind, label: `${kind} lane`, target_refs: ['x'], severity: 'high', dedup_note: '' };
  return generateContract(cluster, registry, { target_url: base });
}
async function run(kind: DefectKind, base: string) {
  const contract = contractFor(kind, base);
  const check = resolveCheck(contract.template_id);
  assert(!!check, `no runnable check for ${contract.template_id}`);
  return runSandboxJob(contract, check!, { runsDir: RUNS });
}

const TESTS: Array<[string, () => Promise<void>]> = [

  ['all five first-five templates resolve to a runnable check (mobile_responsive does not yet)', async () => {
    for (const id of RUNNABLE_FIRST_FIVE) assert(!!resolveCheck(id), `${id} must be runnable`);
    assert(resolveCheck('mobile_responsive_smoke_check') === null, 'mobile_responsive is honestly not-yet-runnable');
  }],

  ['route_health_check: / and /pricing pass; /apply-for-program 404 and /login 500 fail', async () => {
    await withServer(HTML, async (base) => {
      const { receipt } = await run('route_health', base);
      assert(receipt.summary.total === 4 && receipt.summary.passed === 2 && receipt.summary.failed === 2, `route_health summary ${JSON.stringify(receipt.summary)}`);
      assert(validateReceipt(receipt).valid, 'route_health receipt valid');
    });
  }],

  ['cta_route_check: CTA present but route 404 -> {2,1,1}', async () => {
    await withServer(HTML, async (base) => {
      const { receipt } = await run('cta_route', base);
      const present = receipt.checks.find((c) => c.name === 'cta_present')!;
      const resolves = receipt.checks.find((c) => c.name === 'cta_route_resolves')!;
      assert(present.passed === true, 'CTA must be present');
      assert(resolves.passed === false && resolves.evidence!.http_status === 404, 'CTA route must fail 404');
      assert(receipt.summary.passed === 1 && receipt.summary.failed === 1, 'cta {_,1,1}');
    });
  }],

  ['auth_entrypoint_check: sign-in present but /login 500 -> {2,1,1}', async () => {
    await withServer(HTML, async (base) => {
      const { receipt } = await run('auth_entrypoint', base);
      assert(receipt.checks.find((c) => c.name === 'auth_entry_present')!.passed === true, 'auth entry present');
      assert(receipt.checks.find((c) => c.name === 'auth_route_resolves')!.passed === false, 'auth route must fail (500)');
    });
  }],

  ['broken_link_scan over the richer surface: healthy passes, 404/500/# fail', async () => {
    await withServer(HTML, async (base) => {
      const { receipt } = await run('broken_link', base);
      assert(receipt.summary.passed === 1 && receipt.summary.failed >= 3, `broken_link should pass 1 (healthy), fail 404/500/#, got ${JSON.stringify(receipt.summary)}`);
    });
  }],

  // ------- RED-CAPABLE: request_id discriminates (fails without id, passes with it) -------
  ['RED-CAPABLE: request_id_visibility FAILs with no id, PASSes when a request id is rendered', async () => {
    const noId = await withServer(HTML, async (base) => (await run('request_id_visibility', base)).receipt);
    assert(noId.checks[0].passed === false, 'no request-id -> FAIL (if this passed, the check is blind -> RED)');
    const withId = await withServer(HTML_WITH_REQID, async (base) => (await run('request_id_visibility', base)).receipt);
    assert(withId.checks[0].passed === true, 'a rendered [data-request-id] -> PASS (proves discrimination)');
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
