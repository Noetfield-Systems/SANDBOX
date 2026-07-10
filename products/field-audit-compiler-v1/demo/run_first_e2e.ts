/**
 * Demo — run the first real E2E ("Apply for Program link is broken.") end to end against a local
 * 127.0.0.1 fixture and write the resulting field_audit_receipt_v1 + PromotionDecisionPacket to
 * receipts/T5_first_e2e_receipt.json. Illustrative only — no live surface, no mutation.
 * Run: `npx tsx demo/run_first_e2e.ts`
 */
import { createServer } from 'node:http';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';
import { loadRegistry } from '../src/cluster/select_template.ts';
import { generateContract } from '../src/compile/generate_contract.ts';
import { runSandboxJob } from '../src/runner/sandbox_job.ts';
import { brokenLinkScan } from '../src/runner/checks/broken_link_scan.ts';
import type { IssueCluster } from '../src/cluster/cluster.ts';

const PRODUCT_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const html = readFileSync(join(PRODUCT_DIR, 'fixtures', 'target-surface', 'index.html'), 'utf8');

const cluster: IssueCluster = { id: 'IC-BL', session_id: 'AS-2026-07-09-fieldaudit', observation_ids: ['OB-1'], defect_kind: 'broken_link', label: 'Broken links (incl. Apply for Program)', target_refs: ['a[href]'], severity: 'blocker', dedup_note: 'broken_link_scan over nav+footer catches the Apply-for-Pilot 404.' };

const server = createServer((req, res) => {
  const url = (req.url || '/').split('?')[0];
  if (url === '/') { res.writeHead(200, { 'content-type': 'text/html' }); res.end(html); }
  else if (url === '/healthy') { res.writeHead(200); res.end('<p>ok</p>'); }
  else if (url === '/apply-for-program') { res.writeHead(404); res.end('<p>not found</p>'); }
  else { res.writeHead(404); res.end('nope'); }
});

async function main() {
await new Promise<void>((r) => server.listen(0, '127.0.0.1', () => r()));
const base = `http://127.0.0.1:${(server.address() as any).port}/`;
const registry = loadRegistry();
const contract = generateContract(cluster, registry, { target_url: '{TARGET_URL}' }); // committed contract shows placeholder
const runContract = { ...contract, target: { ...contract.target, target_url: base } }; // run against fixture
const { job, receipt } = await runSandboxJob(runContract, (c, ctx) => brokenLinkScan(c, ctx), { runsDir: join(PRODUCT_DIR, '.sandbox_runs', 'demo') });
server.close();

const failing = receipt.checks.filter((c) => !c.passed);
const pdp = {
  id: 'PDP-BL-1', session_id: receipt.session_id, snapshot_id: 'SNAP-fixture-2026-07-09',
  what_changed: `broken_link_scan found ${failing.length} broken links (/apply-for-program 404, footer Cookie #)`,
  why: 'founder: "Apply for Program link is broken."',
  affected_routes_files: failing.map((c) => c.evidence?.url).filter(Boolean),
  before_after_evidence: failing.map((c) => ({ check: c.name, before: c.detail, after: 'proposed fix staged in sandbox diff (not applied)' })),
  verifier_result: receipt.verifier_status, risk_level: 'high',
  rollback_path: 'no change applied — read-only scan; nothing to roll back',
  promotion_recommendation: 'needs_founder_decision', decision: 'pending', decided_by: null, decided_at: null,
};

// normalize the volatile timestamp so the committed artifact is stable
const stableReceipt = { ...receipt, checked_at: '<generated-at-run-time>' };
const bundle = { note: 'Illustrative first E2E — {TARGET_URL} bound to a local 127.0.0.1 fixture; no live surface, no mutation.', contract: { ...contract, id: contract.id }, sandbox_job: { id: job.id, category_id: job.category_id, authority: job.authority, job_kind: job.job_kind, diff_ref: job.diff_ref, runner: job.runner, verifier_target: job.verifier_target }, receipt: stableReceipt, promotion_decision_packet: pdp };
mkdirSync(join(PRODUCT_DIR, 'receipts'), { recursive: true });
writeFileSync(join(PRODUCT_DIR, 'receipts', 'T5_first_e2e_receipt.json'), JSON.stringify(bundle, null, 2));
console.log(JSON.stringify({ receipt: stableReceipt, pdp }, null, 2));
}
main();
