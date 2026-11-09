import assert from 'node:assert/strict';

const main = 'https://shift-web-production-363a.up.railway.app';
const architect = 'https://shift-architect-production.up.railway.app';
const niches = ['home-services', 'restaurants', 'real-estate', 'ecommerce', 'wellness', 'professional', 'creators'];

async function get(url, options = {}) {
  const res = await fetch(url, { signal: AbortSignal.timeout(18000), ...options });
  return { res, text: await res.text() };
}
function fail(msg) { throw new Error('[SHIFT LIVE CHECK] ' + msg); }
function json(body) { return { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) }; }

for (const [name, root] of [['landing', main], ['architect', architect]]) {
  const health = await get(root + '/health', { method: 'POST' });
  if (health.res.status !== 200) fail(name + ' health endpoint HTTP ' + health.res.status);
  const data = JSON.parse(health.text);
  assert.equal(data.status, 'ok', name + ' database-backed health is not ok');
  assert.equal(data.db, 'connected');
  console.log('OK', name, 'health', data);
  const homepage = await get(root + '/');
  if (homepage.res.status !== 200) fail(name + ' homepage HTTP ' + homepage.res.status);
  assert.match(homepage.text, /SHIFT/i);
  assert.match(homepage.res.headers.get('content-type') || '', /text\/html/i);
  console.log('OK', name, 'home HTML + content type');
}

const landing = await get(main + '/');
assert.match(landing.text, /https:\/\/shift-architect-production\.up\.railway\.app\//);
console.log('OK main landing links to real Agency Architect');

for (const niche of niches) {
  const r = await get(architect + '/api/blueprint', json({
    niche, buyer: 'Independent small-business owners in Vancouver',
    problem: 'followup', model: 'setup', experience: 'starter',
    channel: 'organic', target: 3000
  }));
  if (r.res.status !== 200) fail(niche + ' generator HTTP ' + r.res.status + ': ' + r.text.slice(0, 140));
  const output = JSON.parse(r.text);
  assert.ok(output.kit.title.length > 10);
  assert.ok(output.kit.blueprint.includes('90 DAYS'));
  assert.ok(output.kit.blueprint.includes('NOT') || output.kit.blueprint.includes('not'));
  assert.ok(output.kit.math.required >= 1);
  assert.ok(output.kit.hooks.length >= 2);
  console.log('OK blueprint contract', niche);
}

const anon = await get(architect + '/api/me');
assert.equal(anon.res.status, 401, 'private workspace is exposed to anonymous users');
const noAuth = await get(architect + '/api/save', json({ kit: { title: 'Nope' }}));
assert.equal(noAuth.res.status, 401, 'anonymous users can save kits');
const invalid = await get(architect + '/api/enquiry', json({ name: 'x', email: 'invalid', description: '', consent: false }));
assert.equal(invalid.res.status, 400, 'invalid enquiries were accepted');
console.log('PASS: health, content, seven niche generators, anonymous session boundary, negative lead validation.');
