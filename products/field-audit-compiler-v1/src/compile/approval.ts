/**
 * Approval queue (pipeline step 9). Turns a self-written receipt + its contract into ApprovalItem(s).
 * A canonical/live change is authorized ONLY by an approved ApprovalItem — NEVER by raw voice and
 * NEVER auto-applied. Items are always emitted `decision: 'pending'`; read_only contracts with zero
 * failures produce no item (nothing to fix).
 */
import type { WorkflowContract } from './generate_contract.ts';
import type { FieldAuditReceipt } from '../verify/selfwrite_receipt.ts';

export interface ApprovalItem {
  id: string; session_id: string; receipt_id: string; workflow_contract_id: string;
  title: string; proposed_patch_ref: string | null;
  risk_class: string; value_class: string;
  target: WorkflowContract['target'];
  decision: 'pending' | 'approved' | 'rejected' | 'deferred';
  decided_by: string | null; decided_at: string | null; rationale: string;
}

export interface ApprovalOpts { diff_ref?: string | null }

export function buildApprovalItems(
  receipt: FieldAuditReceipt, contract: WorkflowContract, opts: ApprovalOpts = {},
): ApprovalItem[] {
  if (receipt.summary.failed === 0) return []; // nothing failing -> nothing to approve
  const receiptId = `${receipt.schema}:${receipt.session_id}:${receipt.workflow_contract_id}`;
  return [{
    id: `AP-${contract.id.replace(/^WC-/, '')}`,
    session_id: receipt.session_id,
    receipt_id: receiptId,
    workflow_contract_id: contract.id,
    title: `Fix ${contract.template_id} (${receipt.summary.failed}/${receipt.summary.total} checks failing)`,
    proposed_patch_ref: opts.diff_ref ?? null,
    risk_class: contract.risk_class,
    value_class: contract.promotion.value_class,
    target: contract.target,
    decision: 'pending', // ALWAYS pending — never auto-approved, never auto-applied
    decided_by: null, decided_at: null,
    rationale: `${receipt.summary.failed}/${receipt.summary.total} deterministic checks failed; risk_class=${contract.risk_class} -> founder decision required before any canonical change.`,
  }];
}
