/**
 * T3 tests — Workflow Contract Generator. Run: `npx tsx tests/generate_contract.test.ts`.
 * Proves: WC-1..WC-6 reproduced; contracts valid against schema; no deploy/merge/delete authority;
 * sandbox routing explicit; deterministic_checks copied from template; canonical_change => approval.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { loadRegistry } from '../src/cluster/select_template.ts';
import { generateContract, approvalForRisk, type WorkflowContract } from '../src/compile/generate_contract.ts';
import { compileFromFile } from '../src/lib/jsonschema.ts';
import type { IssueCluster } from '../src/cluster/cluster.ts';

const __dir = dirname(fileURLToPath(import.meta.url));
const FX = join(__dir, '..', 'fixtures', 'AS-2026-07-09-fieldaudit');
const goldenClusters: IssueCluster[] = JSON.parse(readFileSync(join(FX, 'clusters.json'), 'utf8'));
const registry = loadRegistry();
const validateContract = compileFromFile(join(__dir, '..', 'WORKFLOW_CONTRACT_SCHEMA_v1.json'));

function assert(c: boolean, m: string) { if (!c) throw new Error(m); }
const contracts = () => goldenClusters.map((c) => generateContract(c, registry));

const TESTS: Array<[string, () => void]> = [

  ['generates WC-1..WC-6 with the exact spine template/value_class/category/risk/approval', () => {
    const cs = contracts();
    const expect = [
      { id: 'WC-1', template_id: 'cta_route_check', value_class: 'REVENUE', cat: 'CAT-10-VERTICAL-PROOF-PRODUCTS', risk: 'read_only', approval: false },
      { id: 'WC-2', template_id: 'legal_footer_link_check', value_class: 'GUARD', cat: 'CAT-09-RECEIPT-TRUST-AUDIT-LAYER', risk: 'read_only', approval: false },
      { id: 'WC-3', template_id: 'auth_entrypoint_check', value_class: 'REVENUE', cat: 'CAT-10-VERTICAL-PROOF-PRODUCTS', risk: 'read_only', approval: false },
      { id: 'WC-4', template_id: 'pricing_claim_consistency_check', value_class: 'REVENUE', cat: 'CAT-10-VERTICAL-PROOF-PRODUCTS', risk: 'canonical_change', approval: true },
      { id: 'WC-5', template_id: 'request_id_visibility_check', value_class: 'GUARD', cat: 'CAT-09-RECEIPT-TRUST-AUDIT-LAYER', risk: 'low_risk_patch', approval: true },
      { id: 'WC-6', template_id: 'web_chat_ux_check', value_class: 'META', cat: 'CAT-09-RECEIPT-TRUST-AUDIT-LAYER', risk: 'low_risk_patch', approval: true },
    ];
    cs.forEach((wc, i) => {
      const e = expect[i];
      assert(wc.id === e.id, `${i}: id ${wc.id} != ${e.id}`);
      assert(wc.template_id === e.template_id, `${wc.id}: template ${wc.template_id} != ${e.template_id}`);
      assert(wc.promotion.value_class === e.value_class, `${wc.id}: value_class ${wc.promotion.value_class} != ${e.value_class}`);
      assert(wc.promotion.factory_category === e.cat, `${wc.id}: cat ${wc.promotion.factory_category} != ${e.cat}`);
      assert(wc.risk_class === e.risk, `${wc.id}: risk ${wc.risk_class} != ${e.risk}`);
      assert(wc.approval_required === e.approval, `${wc.id}: approval ${wc.approval_required} != ${e.approval}`);
    });
  }],

  ['every contract validates against WORKFLOW_CONTRACT_SCHEMA_v1.json', () => {
    for (const wc of contracts()) {
      const r = validateContract(wc);
      assert(r.valid, `${wc.id} invalid: ${r.errors.join('; ')}`);
    }
  }],

  ['NO direct deploy/merge/delete authority; sandbox routing explicit', () => {
    for (const wc of contracts()) {
      assert(wc.authority === 'none', `${wc.id} authority must be 'none'`);
      assert(JSON.stringify(wc.allowed_actions) === JSON.stringify(['inspect', 'patch_diff', 'test']), `${wc.id} allowed_actions must be inspect/patch_diff/test only`);
      for (const blocked of ['deploy', 'merge', 'delete', 'send', 'cron_unlock', 'canonical_write']) {
        assert(wc.blocked_actions.includes(blocked), `${wc.id} must block '${blocked}'`);
        assert(!wc.allowed_actions.includes(blocked), `${wc.id} must NOT allow '${blocked}'`);
      }
    }
  }],

  ['deterministic_checks are copied FAITHFULLY from the template (no free-text / no LLM)', () => {
    for (const wc of contracts()) {
      const tmpl = registry.templates.find((t) => t.id === wc.template_id) as any;
      assert(JSON.stringify(wc.deterministic_checks) === JSON.stringify(tmpl.deterministic_checks), `${wc.id} deterministic_checks diverge from template`);
    }
  }],

  ['broken_link_scan contract: a[href] scope, href_resolves check, CAT-09/GUARD, read_only', () => {
    const bl: IssueCluster = { id: 'IC-BL', session_id: 'AS-2026-07-09-fieldaudit', observation_ids: ['OB-X'], defect_kind: 'broken_link', label: 'broken links', target_refs: ['a[href]'], severity: 'high', dedup_note: '' };
    const wc = generateContract(bl, registry);
    assert(wc.id === 'WC-BL' && wc.template_id === 'broken_link_scan', 'broken_link -> broken_link_scan / WC-BL');
    assert(wc.target.scope_selector === 'a[href]', 'scope must be a[href]');
    assert(wc.deterministic_checks[0].name === 'href_resolves', 'check must be href_resolves');
    assert(wc.promotion.factory_category === 'CAT-09-RECEIPT-TRUST-AUDIT-LAYER' && wc.promotion.value_class === 'GUARD', 'promotion CAT-09/GUARD');
    assert(wc.risk_class === 'read_only', 'broken_link_scan is read_only');
    assert(validateContract(wc).valid, 'broken_link_scan contract must validate');
  }],

  // ------- RED-CAPABLE: canonical_change => approval_required===true -------
  ['RED-CAPABLE: canonical_change MUST require approval; a wrong mapping diverges (RED)', () => {
    assert(approvalForRisk('canonical_change') === true, 'invariant: canonical_change => approval true');
    assert(approvalForRisk('low_risk_patch') === true, 'invariant: low_risk_patch => approval true');
    assert(approvalForRisk('read_only') === false, 'invariant: read_only => approval false');
    // GREEN path: WC-4 (canonical_change) requires approval
    const wc4 = generateContract(goldenClusters[3], registry);
    assert(wc4.risk_class === 'canonical_change' && wc4.approval_required === true, 'WC-4 must require approval');
    // Seed the deliberately-wrong approval fn -> WC-4 would be approval_required:false (RED vs invariant)
    const buggy = generateContract(goldenClusters[3], registry, { approvalFn: () => false });
    assert(buggy.approval_required === false, 'seeded bug should drop approval');
    assert(buggy.approval_required !== wc4.approval_required, 'seeded-wrong mapping MUST diverge from correct (proves discrimination)');
    // read_only never requires approval
    const wc1 = generateContract(goldenClusters[0], registry);
    assert(wc1.risk_class === 'read_only' && wc1.approval_required === false, 'read_only WC-1 must NOT require approval');
  }],
];

let failed = 0;
for (const [name, fn] of TESTS) {
  try { fn(); console.log(`PASS  ${name}`); }
  catch (e) { failed++; console.log(`FAIL  ${name}: ${(e as Error).message}`); }
}
console.log(`\n${TESTS.length - failed}/${TESTS.length} green`);
process.exit(failed ? 1 : 0);
