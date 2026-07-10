/**
 * Ticket 1 tests — Observation extractor + stage-1 schema validator.
 * Self-contained runner (no test framework): prints PASS/FAIL and "N/N green", exit 1 on any failure.
 * Run: `npx tsx tests/stage1.test.ts`  (or `node tests/stage1.test.ts` on Node >= 23.6).
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { extractObservations, LEXICON, type LexRule, type AuditSession, type Transcript } from '../src/stage1/extract_observations.ts';
import { validate } from '../src/stage1/validate.ts';

const __dir = dirname(fileURLToPath(import.meta.url));
const FX = join(__dir, '..', 'fixtures', 'AS-2026-07-09-fieldaudit');
const load = (f: string) => JSON.parse(readFileSync(join(FX, f), 'utf8'));

const session: AuditSession = load('session.json');
const transcript: Transcript = load('transcript.json');
const golden = load('observations.json');

// --- tiny assert helpers ---
function sortKeys(v: any): any {
  if (Array.isArray(v)) return v.map(sortKeys);
  if (v && typeof v === 'object') return Object.fromEntries(Object.keys(v).sort().map((k) => [k, sortKeys(v[k])]));
  return v;
}
const eq = (a: any, b: any) => JSON.stringify(sortKeys(a)) === JSON.stringify(sortKeys(b));
function assert(cond: boolean, msg: string) { if (!cond) throw new Error(msg); }

// ---------------------------------------------------------------------------
const TESTS: Array<[string, () => void]> = [

  ['extractor reproduces the golden OB-1..OB-6 verbatim', () => {
    const got = extractObservations(transcript, session);
    assert(got.length === 6, `expected 6 observations, got ${got.length}`);
    assert(eq(got, golden), 'extracted observations != golden observations.json');
    // acceptance criterion 1: the exact defect_kind mapping
    const kinds = got.map((o) => `${o.raw_span} => ${o.defect_kind}`);
    const expect = [
      'apply for pilot link is broken => cta_route',
      'cookie link goes nowhere => legal_footer_link',
      'sign-in is broken => auth_entrypoint',
      'trust brief $12,000 8-week package copy needs update => pricing_claim',
      'request ids are not visible => request_id_visibility',
      'web chat ui is bad => web_chat_ux',
    ];
    assert(eq(kinds, expect), `defect_kind mapping mismatch:\n${kinds.join('\n')}`);
  }],

  ['every emitted Observation validates and surface_ref is unresolved:*', () => {
    for (const obs of extractObservations(transcript, session)) {
      const r = validate(obs, 'Observation');
      assert(r.valid, `Observation ${obs.id} invalid: ${r.errors.join('; ')}`);
      assert(obs.surface_ref.startsWith('unresolved:'), `${obs.id} surface_ref not unresolved:* -> ${obs.surface_ref}`);
    }
  }],

  ['validator rejects unknown key / bad id / bad enum / missing target', () => {
    const good = golden[0];
    assert(validate(good, 'Observation').valid, 'golden OB-1 should be valid');
    assert(!validate({ ...good, bogus: 1 }, 'Observation').valid, 'unknown key must be rejected (additionalProperties:false)');
    assert(!validate({ ...good, id: 'XX-1' }, 'Observation').valid, 'bad id pattern must be rejected');
    assert(!validate({ ...good, defect_kind: 'not_a_kind' }, 'Observation').valid, 'defect_kind outside enum must be rejected');
    const noTarget: any = { ...session }; delete noTarget.target_url; delete noTarget.target_ref;
    assert(!validate(noTarget, 'AuditSession').valid, 'AuditSession missing both target_url and target_ref must be rejected (anyOf)');
    assert(validate(session, 'AuditSession').valid, 'canonical session should be valid');
  }],

  // ------- RED-CAPABLE test (must be able to fire, per Ticket 1 acceptance #4) -------
  ['RED-CAPABLE: seeded wrong mapping (sign-in->broken_link) diverges from golden; correct table matches', () => {
    // GREEN path: correct default LEXICON maps "sign-in is broken" -> auth_entrypoint
    const ok = extractObservations(transcript, session);
    assert(ok[2].defect_kind === 'auth_entrypoint', `OB-3 must be auth_entrypoint, got ${ok[2].defect_kind}`);

    // Prove it is NOT a tautology: seed the deliberately-wrong table and show it WOULD go RED.
    const brokenLexicon: LexRule[] = LEXICON.map((r) =>
      r.id === 'auth_entrypoint' ? { ...r, defect_kind: 'broken_link' } : r);
    const bad = extractObservations(transcript, session, brokenLexicon);
    assert(bad[2].defect_kind === 'broken_link', 'seeded bug should classify sign-in as broken_link');
    assert(!eq(bad, golden), 'with the seeded-wrong table the golden equality test MUST fail (RED) — proves discrimination');
    console.log('    ↳ red-capability shown: wrong table => sign-in:broken_link (RED vs golden); correct table => auth_entrypoint (GREEN)');
  }],

  ['RED-CAPABLE: validator rejects an Observation missing needs_translation', () => {
    const missing: any = { ...golden[0] };
    delete missing.needs_translation;
    const r = validate(missing, 'Observation');
    assert(!r.valid, 'validator MUST reject an Observation missing required needs_translation (else this test fires RED)');
    assert(r.errors.some((e) => /needs_translation/.test(e)), `expected a needs_translation error, got: ${r.errors.join('; ')}`);
  }],
];

// --- runner ---
let failed = 0;
for (const [name, fn] of TESTS) {
  try { fn(); console.log(`PASS  ${name}`); }
  catch (e) { failed++; console.log(`FAIL  ${name}: ${(e as Error).message}`); }
}
console.log(`\n${TESTS.length - failed}/${TESTS.length} green`);
process.exit(failed ? 1 : 0);
