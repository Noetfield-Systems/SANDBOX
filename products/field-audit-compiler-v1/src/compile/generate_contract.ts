/**
 * T3 — Workflow Contract Generator (the compile step). IssueCluster + template -> WorkflowContract.
 * Pure, no-LLM, CF-re-derivable. Reproduces WC-1..WC-6. Every contract is explicitly sandbox-routed:
 * authority='none', allowed_actions inspect/patch_diff/test only, blocked_actions include
 * deploy/merge/delete/send/cron_unlock/canonical_write — there is NO field or path that grants deploy.
 */
import type { IssueCluster } from '../cluster/cluster.ts';
import { DEFECT_TO_TEMPLATE, type Registry } from '../cluster/select_template.ts';

export type RiskClass = 'read_only' | 'low_risk_patch' | 'canonical_change';

export interface WorkflowContract {
  id: string; cluster_id: string; session_id: string; template_id: string;
  target: { target_url?: string; target_ref?: string; scope_selector: string };
  params: Record<string, any>;
  deterministic_checks: Array<{ name: string; logic: string; pass_condition: string }>;
  expected_outputs: Record<string, any>;
  verifier_logic: string; pattern_expansion_rule: string;
  promotion: { factory_category: string; value_class: string };
  risk_class: RiskClass; approval_required: boolean;
  authority: 'none';
  allowed_actions: string[]; blocked_actions: string[];
  verifier_requirements: { runtime: string; recompute_summary: boolean; edge_proof_required: boolean; secondary_account_required: boolean };
  receipt_requirements: { schema: string; authority: string; min_verifier_status: string };
}

/** The invariant: only read_only contracts skip approval; low_risk_patch + canonical_change require it. */
export function approvalForRisk(risk: RiskClass): boolean {
  return risk !== 'read_only';
}

interface Profile { scope_selector: string; params: Record<string, any>; expected_outputs: Record<string, any>; verifier_logic: string; pattern_expansion_rule: string; risk_class: RiskClass }

const CONTRACT_PROFILE: Record<string, Profile> = {
  cta_route_check: { scope_selector: 'a[data-cta], button[data-cta]', params: { cta_selector: "a[data-cta='apply-for-program']", expected_status: [200] }, expected_outputs: { cta_present: true, cta_route_resolves: true }, verifier_logic: 'CF Worker re-selects CTA + re-fetches href; recompute summary; FAIL on mismatch.', pattern_expansion_rule: 'instantiate cta_route_check for every [data-cta] on the surface', risk_class: 'read_only' },
  legal_footer_link_check: { scope_selector: 'footer a[href]', params: { required: ['cookie'] }, expected_outputs: { cookie_link_present_and_resolves: true }, verifier_logic: 'CF Worker re-parses footer + re-fetches; recompute summary; FAIL on mismatch.', pattern_expansion_rule: 'instantiate for privacy/terms/cookie/accessibility footer links', risk_class: 'read_only' },
  auth_entrypoint_check: { scope_selector: "a[href*='login'], a[href*='signin']", params: { expected_status: [200] }, expected_outputs: { auth_entry_present: true, auth_route_resolves: true }, verifier_logic: 'CF Worker re-selects + re-fetches auth route; recompute summary; FAIL on mismatch.', pattern_expansion_rule: 'instantiate for every auth entrypoint (header, footer, in-body)', risk_class: 'read_only' },
  pricing_claim_consistency_check: { scope_selector: "[data-offer='acme-brief']", params: { canonical_copy_source: '{SSOT_PRICING_REF}', expected_price: '$12,000', expected_duration: '8-week' }, expected_outputs: { price_matches_canonical: false, duration_matches_canonical: false }, verifier_logic: 'CF Worker re-fetches page + canonical, re-runs regexes, re-compares; recompute summary; FAIL on mismatch.', pattern_expansion_rule: 'instantiate across all commercial surfaces referencing Acme Brief price/duration; spawn sibling offer_copy_consistency_check', risk_class: 'canonical_change' },
  request_id_visibility_check: { scope_selector: 'main, [data-request-id]', params: { id_regex: '(req|request|corr)[-_ ]?id[:#]?\\s*[A-Za-z0-9-]{6,}' }, expected_outputs: { request_id_visible: false }, verifier_logic: 'CF Worker re-fetches view + re-runs regex; recompute summary; FAIL on mismatch.', pattern_expansion_rule: 'instantiate across all views expected to show a request id', risk_class: 'low_risk_patch' },
  web_chat_ux_check: { scope_selector: '[data-chat]', params: { widget_selector: '[data-chat]', required_controls: ['input,textarea', 'button[type=submit],[data-chat-send]'] }, expected_outputs: { chat_widget_mounts: true, chat_controls_present: true, chat_input_labeled: false }, verifier_logic: 'CF Worker re-fetches HTML + re-selects widget/controls/attrs; recompute summary; FAIL on mismatch.', pattern_expansion_rule: 'instantiate on every page mounting the chat component', risk_class: 'low_risk_patch' },
  broken_link_scan: { scope_selector: 'a[href]', params: { ignore: ['mailto:', 'tel:'] }, expected_outputs: { href_resolves: true }, verifier_logic: 'CF Worker re-fetches each href, recomputes passed booleans + summary from checks[]; FAIL on any mismatch.', pattern_expansion_rule: 'instantiate one check per unique href across nav+footer+in-body', risk_class: 'read_only' },
  route_health_check: { scope_selector: 'nav a[href]', params: { routes: ['/', '/pricing', '/apply-for-program', '/login'], expected_status: [200] }, expected_outputs: { route_returns_2xx: true }, verifier_logic: 'CF Worker re-fetches each route, recomputes passed + summary; FAIL on mismatch.', pattern_expansion_rule: 'instantiate across all discovered/declared key routes', risk_class: 'read_only' },
  offer_copy_consistency_check: { scope_selector: '[data-offer], main', params: { canonical_copy_source: '{SSOT_OFFER_REF}', offer_key: 'acme_brief' }, expected_outputs: { offer_name_matches_canonical: false }, verifier_logic: 'CF Worker re-fetches + re-normalizes + re-compares; recompute summary; FAIL on mismatch.', pattern_expansion_rule: 'instantiate across all commercial surfaces referencing the offer', risk_class: 'canonical_change' },
  mobile_responsive_smoke_check: { scope_selector: 'main', params: { viewport: '375x812', min_tap_px: 44 }, expected_outputs: { viewport_meta_present: true, no_horizontal_overflow: true }, verifier_logic: 'CF Worker (headless) re-measures at fixed viewport; recompute summary; FAIL on mismatch.', pattern_expansion_rule: 'instantiate across all key routes at the fixed mobile viewport', risk_class: 'read_only' },
};

export interface GenerateOpts { target_url?: string; target_ref?: string; approvalFn?: (r: RiskClass) => boolean }

export function generateContract(cluster: IssueCluster, registry: Registry, opts: GenerateOpts = {}): WorkflowContract {
  const templateId = DEFECT_TO_TEMPLATE[cluster.defect_kind];
  if (!templateId) throw new Error(`un-routable cluster ${cluster.id}: defect_kind '${cluster.defect_kind}' has no template`);
  const template = registry.templates.find((t) => t.id === templateId);
  if (!template) throw new Error(`template ${templateId} not in registry`);
  const prof = CONTRACT_PROFILE[templateId];
  if (!prof) throw new Error(`no contract profile for template ${templateId}`);
  const approvalFn = opts.approvalFn ?? approvalForRisk;
  const target: WorkflowContract['target'] = { scope_selector: prof.scope_selector };
  if (opts.target_ref) target.target_ref = opts.target_ref; else target.target_url = opts.target_url ?? '{TARGET_URL}';
  return {
    id: cluster.id.replace(/^IC-/, 'WC-'),
    cluster_id: cluster.id,
    session_id: cluster.session_id,
    template_id: templateId,
    target,
    params: prof.params,
    deterministic_checks: (template as any).deterministic_checks, // copied FAITHFULLY from the template (no free-text, no LLM)
    expected_outputs: prof.expected_outputs,
    verifier_logic: prof.verifier_logic,
    pattern_expansion_rule: prof.pattern_expansion_rule,
    promotion: { factory_category: (template as any).factory_category, value_class: (template as any).value_class },
    risk_class: prof.risk_class,
    approval_required: approvalFn(prof.risk_class),
    authority: 'none',
    allowed_actions: ['inspect', 'patch_diff', 'test'],
    blocked_actions: ['deploy', 'merge', 'delete', 'send', 'cron_unlock', 'canonical_write'],
    verifier_requirements: { runtime: 'cloudflare_worker', recompute_summary: true, edge_proof_required: true, secondary_account_required: true },
    receipt_requirements: { schema: 'field_audit_receipt_v1', authority: 'none', min_verifier_status: 'UNVERIFIED' },
  };
}
