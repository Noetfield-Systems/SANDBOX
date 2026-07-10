/**
 * T4 — VerificationRun sandbox self-write. Emits a field_audit_receipt_v1 with
 * verifier_status ALWAYS 'UNVERIFIED' and authority ALWAYS 'none'. There is NO code path that can
 * set PASS — a requested PASS is ignored/coerced. PASS is issuable only by the independent CF Worker.
 */
import { recomputeSummary, type Check } from './recompute_summary.ts';
import type { WorkflowContract } from '../compile/generate_contract.ts';

export interface FieldAuditReceipt {
  schema: 'field_audit_receipt_v1';
  session_id: string;
  workflow_contract_id: string;
  sandbox_job_id: string;
  category_id: string;
  checked_at: string;
  checks: Check[];
  summary: { total: number; passed: number; failed: number };
  value_class: string;
  verifier_status: 'UNVERIFIED';
  authority: 'none';
}

export interface SelfWriteArgs {
  contract: Pick<WorkflowContract, 'id' | 'session_id' | 'promotion'>;
  jobId: string;
  checks: Check[];
  checked_at: string;
  /** Ignored — present only so a caller CANNOT smuggle a PASS through; it is coerced to UNVERIFIED. */
  requestedStatus?: string;
}

export function selfWriteReceipt(args: SelfWriteArgs): FieldAuditReceipt {
  // Hard invariant: sandbox self-writes are ALWAYS UNVERIFIED / authority none. requestedStatus is discarded.
  return {
    schema: 'field_audit_receipt_v1',
    session_id: args.contract.session_id,
    workflow_contract_id: args.contract.id,
    sandbox_job_id: args.jobId,
    category_id: args.contract.promotion.factory_category,
    checked_at: args.checked_at,
    checks: args.checks,
    summary: recomputeSummary(args.checks), // author never hand-writes the rollup
    value_class: args.contract.promotion.value_class,
    verifier_status: 'UNVERIFIED',
    authority: 'none',
  };
}
