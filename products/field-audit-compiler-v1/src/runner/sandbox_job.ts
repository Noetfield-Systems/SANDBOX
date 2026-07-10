/**
 * T4 — cat-05 Sandbox Runner Adapter. WorkflowContract -> SandboxJob (authority=none,
 * job_kind inspect|patch_diff|test). NEVER applies a diff, deploys, merges, sends, or writes outside
 * the product dir or to a non-target host. SANDBOX stores METADATA ONLY: the job emits git
 * worktree/branch INSTRUCTIONS against the canonical repo — it does NOT copy source (no stale clone).
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve, sep } from 'node:path';
import { selfWriteReceipt, type FieldAuditReceipt } from '../verify/selfwrite_receipt.ts';
import type { Check } from '../verify/recompute_summary.ts';
import type { WorkflowContract } from '../compile/generate_contract.ts';

const PRODUCT_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');

// ---- authority walls (exported so tests can prove they throw) ----
export const BLOCKED_ACTIONS = new Set(['deploy', 'merge', 'delete', 'send', 'cron_unlock', 'canonical_write', 'apply']);

export function assertNotBlocked(action: string): void {
  if (BLOCKED_ACTIONS.has(action)) throw new Error(`AUTHORITY VIOLATION: '${action}' is blocked in sandbox (authority=none)`);
}

export function assertInsideProductDir(p: string): void {
  const abs = resolve(p);
  if (abs !== PRODUCT_DIR && !abs.startsWith(PRODUCT_DIR + sep)) {
    throw new Error(`AUTHORITY VIOLATION: write outside product dir: ${abs}`);
  }
}

export function assertTargetHost(url: string, targetUrl: string): void {
  if (url.startsWith('/') || url.startsWith('#') || url === '') return; // relative / same-origin
  let host: string;
  try { host = new URL(url).host; } catch { return; } // not absolute -> allow (relative)
  let thost = '';
  try { thost = new URL(targetUrl).host; } catch { thost = ''; }
  if (host !== thost) throw new Error(`AUTHORITY VIOLATION: fetch target host '${host}' != job target '${thost}'`);
}

export interface SnapshotInstructions {
  canonical_repo: string; source_remote: string; source_branch: string; source_commit: string;
  worktree_path: string; worktree_cmd: string; cleanup_cmd: string;
}

export interface SandboxJob {
  id: string; workflow_contract_id: string; session_id: string;
  category_id: 'CAT-05-SANDBOX-WORKTREE-EXECUTION'; authority: 'none';
  job_kind: 'inspect' | 'patch_diff' | 'test';
  target: WorkflowContract['target']; inputs: Record<string, any>;
  status: 'queued' | 'running' | 'done' | 'error';
  snapshot_instructions: SnapshotInstructions; runner: string; verifier_target: string;
  output_ref: string | null; diff_ref: string | null; receipt_id?: string;
}

export interface RunOpts {
  target_url?: string; target_ref?: string; runner?: string; verifier_target?: string;
  snapshot?: Partial<SnapshotInstructions>; runsDir?: string; diffContent?: string;
}

export function createSandboxJob(contract: WorkflowContract, opts: RunOpts = {}): SandboxJob {
  const job_kind: SandboxJob['job_kind'] = contract.risk_class === 'read_only' ? 'inspect' : 'patch_diff';
  const snap: SnapshotInstructions = {
    canonical_repo: '{CANONICAL_REPO}', source_remote: '{SOURCE_REMOTE}', source_branch: '{SOURCE_BRANCH}',
    source_commit: '{SOURCE_COMMIT}', worktree_path: '{LANE_WORKTREE_OUTSIDE_SANDBOX}',
    worktree_cmd: 'git -C {CANONICAL_REPO} worktree add {LANE_WORKTREE_OUTSIDE_SANDBOX} {SOURCE_COMMIT}',
    cleanup_cmd: 'git -C {CANONICAL_REPO} worktree remove {LANE_WORKTREE_OUTSIDE_SANDBOX}',
    ...(opts.snapshot || {}),
  };
  const target = { ...contract.target };
  if (opts.target_url) target.target_url = opts.target_url;
  if (opts.target_ref) { target.target_ref = opts.target_ref; delete (target as any).target_url; }
  return {
    id: contract.id.replace(/^WC-/, 'SJ-'),
    workflow_contract_id: contract.id, session_id: contract.session_id,
    category_id: 'CAT-05-SANDBOX-WORKTREE-EXECUTION', authority: 'none', job_kind,
    target, inputs: contract.params, status: 'queued',
    snapshot_instructions: snap, runner: opts.runner ?? 'github_actions',
    verifier_target: opts.verifier_target ?? '{CAT_VERIFIER_URL}', output_ref: null, diff_ref: null,
  };
}

export interface CheckCtx { targetUrl: string; guardedFetch: (url: string) => void }
export type CheckFn = (contract: WorkflowContract, ctx: CheckCtx) => Promise<Check[]> | Check[];

/** Run the contract's checks in the cat-05 shape and self-write an UNVERIFIED receipt. */
export async function runSandboxJob(
  contract: WorkflowContract, checkFn: CheckFn, opts: RunOpts = {},
): Promise<{ job: SandboxJob; receipt: FieldAuditReceipt }> {
  const job = createSandboxJob(contract, opts);
  const targetUrl = job.target.target_url ?? job.target.target_ref ?? '{TARGET_URL}';
  const runsDir = opts.runsDir ?? join(PRODUCT_DIR, '.sandbox_runs');
  const jobDir = join(runsDir, job.id);
  assertInsideProductDir(jobDir);
  mkdirSync(jobDir, { recursive: true });
  job.status = 'running';

  const ctx: CheckCtx = { targetUrl, guardedFetch: (url) => assertTargetHost(url, targetUrl) };
  const checks = await checkFn(contract, ctx);

  const outPath = join(jobDir, 'output.json');
  assertInsideProductDir(outPath);
  writeFileSync(outPath, JSON.stringify({ job_id: job.id, contract_id: contract.id, checks }, null, 2));
  job.output_ref = outPath;

  if (job.job_kind === 'patch_diff') {
    const diffPath = join(jobDir, 'proposed.diff');
    assertInsideProductDir(diffPath); // staged only — there is NO apply path
    writeFileSync(diffPath, opts.diffContent ?? '# staged patch candidate for review — NEVER applied by the sandbox\n');
    job.diff_ref = diffPath;
  }

  job.status = 'done';
  const receipt = selfWriteReceipt({ contract, jobId: job.id, checks, checked_at: new Date().toISOString() });
  job.receipt_id = `${receipt.schema}:${receipt.session_id}:${receipt.workflow_contract_id}`;
  return { job, receipt };
}
