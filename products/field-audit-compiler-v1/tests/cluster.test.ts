/**
 * T2 tests — Clusterer + Template selector. Self-contained runner. Run: `npx tsx tests/cluster.test.ts`.
 * Proves: 1 observation -> multiple workflows; duplicates collapse; unrelated stay separate;
 * severity=max; registry drift fails closed; NO patching/source mutation (pure functions only).
 */
import { readFileSync, writeFileSync, rmSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { extractObservations, type AuditSession, type Transcript, type Observation } from '../src/stage1/extract_observations.ts';
import { clusterObservations, maxSeverity } from '../src/cluster/cluster.ts';
import { loadRegistry, selectTemplate, selectTemplates, DEFECT_TO_TEMPLATE } from '../src/cluster/select_template.ts';

const __dir = dirname(fileURLToPath(import.meta.url));
const FX = join(__dir, '..', 'fixtures', 'AS-2026-07-09-fieldaudit');
const load = (f: string) => JSON.parse(readFileSync(join(FX, f), 'utf8'));
const session: AuditSession = load('session.json');
const transcript: Transcript = load('transcript.json');
const goldenClusters = load('clusters.json');

function sortKeys(v: any): any {
  if (Array.isArray(v)) return v.map(sortKeys);
  if (v && typeof v === 'object') return Object.fromEntries(Object.keys(v).sort().map((k) => [k, sortKeys(v[k])]));
  return v;
}
const eq = (a: any, b: any) => JSON.stringify(sortKeys(a)) === JSON.stringify(sortKeys(b));
function assert(c: boolean, m: string) { if (!c) throw new Error(m); }

const obs = () => extractObservations(transcript, session);
const registry = loadRegistry();

const TESTS: Array<[string, () => void]> = [

  ['clusterer reproduces the golden IC-1..IC-6 (unrelated observations stay separate)', () => {
    const clusters = clusterObservations(obs());
    assert(clusters.length === 6, `expected 6 clusters (6 distinct kinds), got ${clusters.length}`);
    assert(eq(clusters, goldenClusters), 'clusters != golden clusters.json');
  }],

  ['selector: 1:1 defect_kind -> template id for all 10 kinds + first-five priority', () => {
    const expect: Record<string, string | null> = {
      broken_link: 'broken_link_scan', cta_route: 'cta_route_check', legal_footer_link: 'legal_footer_link_check',
      auth_entrypoint: 'auth_entrypoint_check', offer_copy: 'offer_copy_consistency_check',
      pricing_claim: 'pricing_claim_consistency_check', request_id_visibility: 'request_id_visibility_check',
      web_chat_ux: 'web_chat_ux_check', mobile_responsive: 'mobile_responsive_smoke_check',
      route_health: 'route_health_check', other: null,
    };
    for (const [k, v] of Object.entries(expect)) assert(DEFECT_TO_TEMPLATE[k as keyof typeof DEFECT_TO_TEMPLATE] === v, `${k} -> ${DEFECT_TO_TEMPLATE[k as keyof typeof DEFECT_TO_TEMPLATE]} != ${v}`);
    // first-five marked priority
    const sel = selectTemplates('auth_entrypoint', registry);
    assert(sel[0].template_id === 'auth_entrypoint_check' && sel[0].priority === true, 'auth_entrypoint_check must be first-five priority');
    assert(selectTemplates('web_chat_ux', registry)[0].priority === false, 'web_chat_ux_check is not first-five');
  }],

  ['ONE observation expands into MULTIPLE deterministic workflows (pricing -> primary + sibling)', () => {
    const sel = selectTemplates('pricing_claim', registry);
    assert(sel.length === 2, `pricing_claim must yield 2 workflows (primary + sibling), got ${sel.length}`);
    assert(sel[0].template_id === 'pricing_claim_consistency_check' && sel[0].role === 'primary', 'primary must be pricing_claim_consistency_check');
    assert(sel[1].template_id === 'offer_copy_consistency_check' && sel[1].role === 'sibling', 'sibling must be offer_copy_consistency_check');
  }],

  ['registry drift fails closed', () => {
    const badPath = join(__dir, '..', 'fixtures', '__bad_registry.json');
    // write a divergent registry to a temp fixture, expect loadRegistry to throw
    const good = JSON.parse(readFileSync(join(__dir, '..', 'src', 'templates', 'registry.json'), 'utf8'));
    good.templates = good.templates.filter((t: any) => t.id !== 'route_health_check'); // drop one -> drift
    writeFileSync(badPath, JSON.stringify(good));
    let threw = false;
    try { loadRegistry(badPath); } catch { threw = true; }
    rmSync(badPath, { force: true });
    assert(threw, 'loadRegistry MUST throw on a registry missing a spine template id (fail closed)');
  }],

  // ------- RED-CAPABLE #1: dedup (identical defect_kind+scope collapse to ONE cluster) -------
  ['RED-CAPABLE: two identical legal_footer_link observations collapse into ONE cluster', () => {
    const dupA: Observation = { id: 'OB-A', session_id: session.id, transcript_id: 'TR-1', raw_span: 'cookie link goes nowhere', surface_ref: 'unresolved:footer Cookie link', target_hint: 'Cookie link', severity_guess: 'high', defect_kind: 'legal_footer_link', confidence: 0.88, needs_translation: false };
    const dupB: Observation = { ...dupA, id: 'OB-B', severity_guess: 'low' };
    const clusters = clusterObservations([dupA, dupB], session.id);
    assert(clusters.length === 1, `two identical-kind+scope observations MUST collapse to 1 cluster, got ${clusters.length} (RED if a per-observation bug emits 2)`);
    assert(eq(clusters[0].observation_ids, ['OB-A', 'OB-B']), 'both observation ids must merge into the one cluster');
    // severity = MAX(high, low) = high  (a first()-instead-of-max() bug fires RED here)
    assert(clusters[0].severity === 'high', `severity must be MAX(high,low)=high, got ${clusters[0].severity}`);
    // prove maxSeverity discriminates (low+blocker -> blocker)
    assert(maxSeverity('low', 'blocker') === 'blocker' && maxSeverity('blocker', 'low') === 'blocker', 'maxSeverity must return blocker');
  }],

  ['no source mutation: clusterer + selector are pure (input array untouched)', () => {
    const input = obs();
    const snapshot = JSON.stringify(input);
    clusterObservations(input);
    selectTemplates('pricing_claim', registry);
    assert(JSON.stringify(input) === snapshot, 'inputs must not be mutated (pure functions, no patching)');
  }],
];

let failed = 0;
for (const [name, fn] of TESTS) {
  try { fn(); console.log(`PASS  ${name}`); }
  catch (e) { failed++; console.log(`FAIL  ${name}: ${(e as Error).message}`); }
}
console.log(`\n${TESTS.length - failed}/${TESTS.length} green`);
process.exit(failed ? 1 : 0);
