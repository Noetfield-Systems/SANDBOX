/**
 * T4 tests — cat-05 Sandbox Runner. Run: `npx tsx tests/runner.test.ts`.
 * Proves: source stays canonical (worktree INSTRUCTIONS, not a copy); SANDBOX stores metadata only;
 * no stale source copy; authority walls throw (write outside / non-target host / blocked action);
 * patch_diff staged never applied.
 */
import { readFileSync, existsSync, rmSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';
import { loadRegistry } from '../src/cluster/select_template.ts';
import { generateContract } from '../src/compile/generate_contract.ts';
import { createSandboxJob, runSandboxJob, assertNotBlocked, assertInsideProductDir, assertTargetHost } from '../src/runner/sandbox_job.ts';
import type { IssueCluster } from '../src/cluster/cluster.ts';
import type { Check } from '../src/verify/recompute_summary.ts';

const __dir = dirname(fileURLToPath(import.meta.url));
const PRODUCT_DIR = resolve(__dir, '..');
const RUNS = join(PRODUCT_DIR, '.sandbox_runs', 't4');
const clusters: IssueCluster[] = JSON.parse(readFileSync(join(PRODUCT_DIR, 'fixtures', 'AS-2026-07-09-fieldaudit', 'clusters.json'), 'utf8'));
const registry = loadRegistry();
function assert(c: boolean, m: string) { if (!c) throw new Error(m); }
const stub: (r: number) => Check[] = () => [{ name: 'stub_check', passed: true, detail: 'harness ok', evidence: { match: true } }];

const TESTS: Array<[string, () => Promise<void> | void]> = [

  ['patch_diff job stages a diff under the product dir; source stays untouched (metadata only)', async () => {
    const wc4 = generateContract(clusters[3], registry); // WC-4 canonical_change -> patch_diff
    const canonicalFile = join(PRODUCT_DIR, 'src', 'stage1', 'extract_observations.ts');
    const before = readFileSync(canonicalFile, 'utf8');
    const { job } = await runSandboxJob(wc4, stub, { runsDir: RUNS, diffContent: '--- a\n+++ b\n@@ staged @@\n' });
    assert(job.job_kind === 'patch_diff', 'WC-4 must be patch_diff');
    assert(!!job.diff_ref && existsSync(job.diff_ref), 'diff_ref file must exist');
    assert(resolve(job.diff_ref!).startsWith(resolve(RUNS)), 'diff must be under the product-dir runs area');
    // SANDBOX stores metadata only: job dir holds output.json + proposed.diff, NO copied source
    const files = readdirSync(join(RUNS, job.id)).sort();
    assert(JSON.stringify(files) === JSON.stringify(['output.json', 'proposed.diff']), `job dir must hold metadata only, got ${files}`);
    // source untouched (never applied)
    assert(readFileSync(canonicalFile, 'utf8') === before, 'canonical source must be byte-identical after run (diff staged, never applied)');
  }],

  ['job carries repo-local worktree INSTRUCTIONS (canonical, no copy) + runner + verifier target', () => {
    const job = createSandboxJob(generateContract(clusters[0], registry));
    assert(job.category_id === 'CAT-05-SANDBOX-WORKTREE-EXECUTION' && job.authority === 'none', 'cat-05 / authority none');
    const s = job.snapshot_instructions;
    assert(/git .*worktree add/.test(s.worktree_cmd) && s.worktree_cmd.includes('{CANONICAL_REPO}'), 'worktree instruction must target the canonical repo');
    assert(s.worktree_path.includes('OUTSIDE_SANDBOX'), 'worktree path must be OUTSIDE the sandbox (no source copied into SANDBOX)');
    assert(job.runner === 'github_actions', 'runner selected');
    assert(job.verifier_target === '{CAT_VERIFIER_URL}', 'verifier target set (CF Worker)');
  }],

  // ------- RED-CAPABLE (a): authority walls -------
  ['RED-CAPABLE: authority walls throw on blocked action / write-outside / non-target host', () => {
    // blocked actions
    for (const a of ['deploy', 'merge', 'delete', 'send', 'cron_unlock', 'canonical_write', 'apply']) {
      let threw = false; try { assertNotBlocked(a); } catch { threw = true; }
      assert(threw, `assertNotBlocked('${a}') MUST throw (if it doesn't, the wall is down -> RED)`);
    }
    assert((() => { try { assertNotBlocked('inspect'); return true; } catch { return false; } })(), 'inspect must be allowed');
    // write outside product dir
    let threwOut = false; try { assertInsideProductDir(join(PRODUCT_DIR, '..', 'evil.txt')); } catch { threwOut = true; }
    assert(threwOut, 'writing outside the product dir MUST throw');
    assert((() => { try { assertInsideProductDir(join(RUNS, 'ok.json')); return true; } catch { return false; } })(), 'writing inside runs dir must be allowed');
    // non-target host
    let threwHost = false; try { assertTargetHost('http://evil.example.com/x', 'http://127.0.0.1:8123'); } catch { threwHost = true; }
    assert(threwHost, 'fetching a non-target host MUST throw');
    assert((() => { try { assertTargetHost('/apply-for-program', 'http://127.0.0.1:8123'); return true; } catch { return false; } })(), 'relative same-origin fetch must be allowed');
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
