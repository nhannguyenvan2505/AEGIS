import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { controllerModule, apiModule, clientModule } from './load-followup-test.mjs';
const { FollowupController } = controllerModule;
const { ApiError } = apiModule;
const fixtures = JSON.parse(await readFile(new URL('./fixtures/followup.json', import.meta.url), 'utf8'));
const record = name => structuredClone(fixtures.find(r => r.name === name).response.body);
const view = () => record('refresh assessment view').item;
const detail = () => record('refresh detail').item;
const page = items => ({ items, pagination: { page: 1, page_size: 20, total: items.length, total_pages: items.length ? 1 : 0, has_next: false } });
function setup(changes = {}) {
  let expired = 0, sent = [], ids = 0;
  const api = { capabilities: async () => ({ mode: 'pilot', follow_up: { available: true, source: 'mock' } }),
    plots: async () => page([{ id: 'plot', name: 'Plot' }]), seasons: async () => page([{ id: 'season', name: 'Season' }]),
    cases: async () => page([detail()]), detail: async () => ({ item: detail() }), view: async () => ({ item: view() }),
    observations: async () => record('available synthetic observation'),
    command: async (_t, _id, body) => { sent.push(structuredClone(body)); return {}; }, ...changes };
  const c = new FollowupController('secret', () => {}, () => expired++, () => `00000000-0000-4000-8000-${String(++ids).padStart(12, '0')}`, api);
  return { c, api, sent, expired: () => expired };
}
async function opened(h) {
  const d = detail(); await h.c.start(); await h.c.choosePlot('plot'); await h.c.chooseSeason(d.season_id); await h.c.open(d.id);
  assert.ok(h.c.state.view); h.c.edit('Synthetic intent', record('available synthetic observation').items[0].id);
}
test('missing or unknown projection disables commands rather than inferring from state', async () => {
  for (const change of [v => delete v.action_capabilities, v => { v.action_capabilities.projection_version = 'future'; }, v => { delete v.action_capabilities.actions.check.observation_constraints; }]) {
    const h = setup({ view: async () => { const v = view(); change(v); return { item: v }; } }); await opened(h);
    await h.c.act('check'); assert.equal(h.sent.length, 0);
  }
});
test('observation required enforced client-side; data task accepts null', async () => {
  const h = setup(); await opened(h); h.c.edit('Reason', ''); await h.c.act('check'); assert.equal(h.sent.length, 0);
  h.api.view = async () => { const v = view(); v.action_capabilities.actions.check.observation_required = false; return { item: v }; };
  await h.c.refresh(); h.c.edit('Data check'); await h.c.act('check'); assert.equal(h.sent.length, 1); assert.equal(h.sent[0].observation_id, null);
});
test('lost response preserves exact payload, blocks changed intent and duplicate clicks', async () => {
  let calls = 0, release;
  const h = setup({ command: async (_t, _id, body) => { h.sent.push(structuredClone(body)); if (++calls === 1) throw new Error('lost response'); await new Promise(r => { release = r; }); return {}; } });
  await opened(h); await h.c.act('check'); const original = structuredClone(h.c.state.pending.body);
  h.c.edit('Changed', ''); await h.c.chooseSeason('different'); await h.c.act('acknowledge');
  const retry = h.c.retry(); await h.c.retry(); assert.equal(h.sent.length, 2); assert.deepEqual(h.sent[1], original);
  release(); await retry; assert.equal(h.c.state.pending, undefined);
});
test('409 reads current snapshot, keeps user decision and never auto-reissues command', async () => {
  let sent = 0;
  const h = setup({ command: async () => { sent++; throw new ApiError('Conflict', 409, 'followup_version_conflict', 'rid'); } });
  await opened(h); await h.c.act('check'); assert.equal(sent, 1); assert.equal(h.c.state.pending, undefined);
  assert.ok(h.c.state.view); assert.match(h.c.state.message, /tự quyết định/); assert.match(h.c.state.error, /rid/);
});
test('401 wipes private view and pending intent and invokes session expiration', async () => {
  const h = setup({ command: async () => { throw new ApiError('Expired', 401); } }); await opened(h); await h.c.act('check');
  assert.equal(h.expired(), 1); assert.equal(h.c.state.view, undefined); assert.equal(h.c.state.pending, undefined); assert.equal(h.c.state.cases, undefined);
});
test('503 integrity on refresh removes stale actionable view; 404 does not fallback', async () => {
  const h = setup(); await opened(h);
  for (const status of [503, 404]) {
    h.api.view = async () => { throw new ApiError('Unavailable', status); };
    await h.c.refresh(); assert.equal(h.c.state.view, undefined); await h.c.act('check'); assert.equal(h.sent.length, 0);
  }
});
test('429 retains intent and honors Retry-After before replay', async () => {
  let calls = 0; const h = setup({ command: async () => { calls++; throw new ApiError('Slow', 429, 'rate_limit_exceeded', 'rid', '30'); } });
  await opened(h); await h.c.act('check'); assert.ok(h.c.state.pending); assert.ok(h.c.state.retryAt > Date.now());
  await h.c.retry(); assert.equal(calls, 1);
});
test('late season/case responses and disposed old account cannot replace current context', async () => {
  let release; const h = setup(); await h.c.start();
  h.api.cases = async (_t, season) => season === 'old' ? await new Promise(r => { release = r; }) : page([]);
  const old = h.c.chooseSeason('old'); await h.c.chooseSeason('new'); release(page([detail()])); await old;
  assert.equal(h.c.state.season, 'new'); assert.deepEqual(h.c.state.cases.items, []);
  let end; h.api.cases = async () => await new Promise(r => { end = r; });
  const disposed = h.c.chooseSeason('after'); h.c.dispose(); end(page([detail()])); await disposed; assert.equal(h.c.state.cases, undefined);
});
test('capability mismatch stops before querying business resources', async () => {
  let plots = 0; const h = setup({ capabilities: async () => ({ mode: 'core', follow_up: { available: false } }), plots: async () => { plots++; return page([]); } });
  await h.c.start(); assert.equal(plots, 0); assert.equal(h.c.state.available, false);
});
test('late case response is ignored after selecting a different case', async () => {
  const h = setup(); await opened(h); let release;
  h.api.view = async (_token, id) => id === 'old-case' ? await new Promise(r => { release = r; }) : { item: view() };
  const old = h.c.open('old-case'); await h.c.open(detail().id); release({ item: { ...view(), followup_id: 'old-case' } }); await old;
  assert.equal(h.c.state.caseId, detail().id); assert.equal(h.c.state.view.followup_id, detail().id);
});
test('effect reconnect after cleanup ignores first discovery response', async () => {
  let release, count = 0;
  const h = setup({ capabilities: async () => ++count === 1 ? await new Promise(r => { release = r; }) : { mode: 'pilot', follow_up: { available: true, source: 'mock' } } });
  const initial = h.c.start(); h.c.dispose(); h.c.activate(); await h.c.start();
  release({ mode: 'core', follow_up: { available: false } }); await initial;
  assert.equal(h.c.state.available, true); assert.equal(h.c.state.error, '');
});
test('observation eligibility rejects void, wrong source and too-old timestamp', () => {
  const p = clientModule.projection(view()); const o = record('available synthetic observation').items[0];
  assert.equal(clientModule.eligibleObservation(o, p), true);
  for (const bad of [{ ...o, source: 'field_observed' }, { ...o, payload: { ...o.payload, record_status: 'voided' } }, { ...o, observed_at: '2000-01-01T00:00:00Z' }]) assert.equal(clientModule.eligibleObservation(bad, p), false);
});
