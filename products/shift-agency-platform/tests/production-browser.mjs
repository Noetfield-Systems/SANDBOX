import { chromium } from 'playwright';
import assert from 'node:assert/strict';

const origin = 'https://shift-web-production-363a.up.railway.app';
const seed = process.env.GITHUB_RUN_ID || String(Date.now());
const email = 'shift-qa+' + seed + '@example.com';
const password = 'QaSHIFT-' + seed + '-A7!secure';
let browser, context, page, accountCreated = false, accountDeleted = false;
const log = (...v) => console.log('[SHIFT E2E]', ...v);
const check = (condition, message) => { if (!condition) throw new Error(message); };

async function run() {
  browser = await chromium.launch({ headless: true });
  context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
  page = await context.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  const home = await page.goto(origin + '/?utm_source=qa-e2e&utm_medium=ci&utm_campaign=premium-release', { waitUntil: 'domcontentloaded' });
  assert.equal(home.status(), 200, 'Landing page must load');
  await page.locator('h1').waitFor();
  check((await page.locator('h1').innerText()).includes('agency'), 'Expected premium agency hero');
  await page.screenshot({ path: 'artifacts/shift-desktop.png', fullPage: true });
  log('Landing desktop rendered.');

  // Real, unauthenticated campaign generation. No fake account or paid lead.
  await page.locator('#gen').click();
  await page.locator('#result.show').waitFor({ timeout: 30000 });
  check((await page.locator('#output-text').innerText()).length > 80, 'Free content generator returned no useful content');
  await page.locator('[data-tab="ads"]').click();
  check((await page.locator('#output-text').innerText()).includes('AD VARIANT'), 'Ad variants missing');
  log('Free creator generated hooks and ad variants.');

  // One-domain navigation: no cross-site authentication.
  const archLink = page.locator('a[href="/architect"]').first();
  await archLink.click();
  await page.waitForURL('**/architect');
  await page.locator('#next').waitFor();
  assert.equal(new URL(page.url()).origin, origin);
  await page.screenshot({ path: 'artifacts/shift-architect-desktop.png', fullPage: true });
  log('Agency Architect reachable on the same origin.');

  // Complete the seven-step guided workflow.
  await page.locator('#next').click();
  await page.locator('#buyer').fill('Vancouver HVAC service owners with three to twenty employees');
  for (let i = 0; i < 5; i++) await page.locator('#next').click();
  await page.locator('#next').click();
  await page.locator('#results.show').waitFor({ timeout: 30000 });
  const cards = await page.locator('.blueprint-card').count();
  check(cards >= 9, 'Expected full structured blueprint sections; got ' + cards);
  check((await page.locator('#doc').innerText()).includes('90-DAY'), 'Missing execution roadmap');
  await page.screenshot({ path: 'artifacts/shift-blueprint-desktop.png', fullPage: true });
  log('Generated structured strategy with', cards, 'sections.');

  // Account and cross-page persistence smoke. QA-tagged and deleted on completion.
  await page.locator('#save').click();
  await page.locator('#login-dialog').waitFor({ state: 'visible' });
  await page.locator('#email').fill(email);
  await page.locator('#password').fill(password);
  await page.locator('#submit-auth').click();
  await page.waitForTimeout(1000);
  const signedIn = await context.request.get(origin + '/api/me');
  check(signedIn.status() === 200, 'Account registration or cross-service cookie failed: ' + signedIn.status());
  accountCreated = true;
  const me = await signedIn.json();
  assert.equal(me.user.email, email);
  check(me.kits.some(k => k.blueprint || k.kit?.blueprint), 'Saved blueprint missing from shared database.');
  log('QA account created, blueprint saved.');

  await page.goto(origin + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(450);
  check((await page.locator('#signin').innerText()).includes('Workspace'), 'Auth cookie did not persist between sections');
  const exportResponse = await context.request.get(origin + '/api/account/export');
  check(exportResponse.status() === 200, 'Self-service account export failed');
  const exportPayload = await exportResponse.json();
  assert.equal(exportPayload.account.email, email);
  check(exportPayload.saved_work?.length > 0, 'Export has no saved work');
  log('Unified session and account data export passed.');

  // Mobile layout: no horizontal overflow and accessible navigation.
  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload({ waitUntil: 'domcontentloaded' });
  check(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2), 'Mobile landing overflows viewport');
  await page.locator('#mobile-toggle').click();
  check(await page.locator('#site-nav').isVisible(), 'Mobile navigation does not open');
  await page.screenshot({ path: 'artifacts/shift-mobile.png', fullPage: true });
  await page.goto(origin + '/architect', { waitUntil: 'domcontentloaded' });
  check(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2), 'Mobile Agency Architect overflows viewport');
  await page.screenshot({ path: 'artifacts/shift-architect-mobile.png', fullPage: true });
  log('Mobile viewport and menu checks passed.');

  const invalid = await context.request.post(origin + '/architect/api/enquiry', {
    data: { name: 'x', email: 'not-email', description: '', budget: 'exploring', consent: false }
  });
  assert.equal(invalid.status(), 400, 'Invalid lead was accepted');
  log('Lead intake rejects invalid requests.');

  check(errors.length === 0, 'Browser runtime errors: ' + errors.join('; '));
} finally {
  if (accountCreated && !accountDeleted && context) {
    const cleanup = await context.request.post(origin + '/api/account/delete', { data: { confirmation: 'DELETE MY ACCOUNT', password } }).catch(() => null);
    if (cleanup?.status() === 200) {
      accountDeleted = true;
      const me = await context.request.get(origin + '/api/me');
      check(me.status() === 401, 'Deleted account was still accessible.');
      log('QA account deleted and session revoked.');
    } else {
      console.error('QA cleanup FAILED; delete temporary account', email, cleanup?.status());
      process.exitCode = 1;
    }
  }
  if (browser) await browser.close();
}
}
try { await run(); log('PASS — premium desktop/mobile, generator, agency strategy, unified authentication, export, data deletion, invalid lead.'); }
catch (error) { console.error('FAIL', error.stack || error); process.exitCode = 1; }
