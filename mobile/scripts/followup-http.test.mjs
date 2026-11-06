import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import test from 'node:test';
import { controllerModule, apiModule, clientModule } from './load-followup-test.mjs';

test('actual mobile controller and API against isolated pilot HTTP: both kinds, replay, recheck, filter and owner/session', async () => {
  const ctx = JSON.parse(process.env.AEGIS_FOLLOWUP_CONTEXT);
  const { followupClient } = clientModule;
  const { FollowupController } = controllerModule;
  const { login, logout, request } = apiModule;
  const session = await login('journal-owner@example.test', 'journal-test-password-123');
  const other = await login('journal-other@example.test', 'journal-test-password-123');
  let expired = 0, lose = false; const committed = [];
  const transport = { ...followupClient, command: async (...args) => {
    const response = await followupClient.command(...args); committed.push(response);
    if (lose) { lose = false; throw new Error('Injected response loss after server commit'); }
    return response;
  } };
  const c = new FollowupController(session.access_token, () => {}, () => expired++, randomUUID, transport);
  try {
    await c.start(); assert.equal(c.state.available, true);
    await c.choosePlot(ctx.plot); assert.ok(c.state.seasons.items.some(s => s.id === ctx.season));
    await c.chooseSeason(ctx.season, 'open'); assert.equal(c.state.cases.pagination.total, 2);
    await c.open(ctx.conditions); assert.equal(c.state.view.action_capabilities.actions.check.observation_required, true);
    c.edit('Read synthetic case'); await c.act('acknowledge'); assert.equal(c.state.detail.version, 2);
    c.edit('Observed synthetic evidence', ctx.observation); lose = true;
    await c.act('check'); assert.ok(c.state.pending); const pending = structuredClone(c.state.pending);
    await c.retry(); assert.equal(c.state.pending, undefined); assert.equal(c.state.detail.version, 3);
    assert.equal(committed[1].event.id, committed[2].event.id);
    assert.equal(committed[1].event.payload.client_event_id, undefined); // key belongs to storage event ID, not payload shape
    assert.ok(pending.body.client_event_id);
    await request(`/farm/observations/${ctx.observation}`, { method: 'PUT', body: JSON.stringify(ctx.correction) }, session.access_token);
    await c.refresh(); assert.equal(c.state.view.action_capabilities.needs_recheck, true);
    assert.ok(c.state.view.action_capabilities.recheck_reasons.includes('observation_changed'));
    c.edit('Rechecked corrected observation', ctx.observation); await c.act('check');
    assert.equal(c.state.detail.version, 4); assert.equal(c.state.view.action_capabilities.needs_recheck, false);
    const events = await request(`/farm/follow-ups/${ctx.conditions}/events`, {}, session.access_token);
    assert.equal(events.items.length, 4);
    assert.equal(events.items.find(e => e.version === 3).payload.observation_snapshot.revision, 1);
    await c.open(ctx.data); assert.equal(c.state.view.action_capabilities.actions.check.observation_required, false);
    c.edit('Acknowledge data quality'); await c.act('acknowledge');
    c.edit('Checked available data'); await c.act('check'); assert.equal(c.state.detail.version, 3);
    assert.equal(committed.at(-1).event.payload.observation_snapshot, null);
    await c.chooseSeason(ctx.season, 'checked'); assert.equal(c.state.cases.pagination.total, 2);
    const paged = await request(`/farm/seasons/${ctx.season}/follow-ups?state=checked&page=2&page_size=1`, {}, session.access_token);
    assert.equal(paged.items.length, 1); assert.equal(paged.pagination.total, 2);
    await assert.rejects(request(`/farm/seasons/${ctx.season}/follow-ups?state=bad`, {}, session.access_token), e => e.status === 400 && e.code === 'invalid_followup_filter');
    await assert.rejects(followupClient.detail(other.access_token, ctx.conditions), e => e.status === 404 && !!e.requestId);
    await c.open(ctx.conditions); await logout(session.access_token); await c.refresh();
    assert.equal(expired, 1); assert.equal(c.state.view, undefined); assert.equal(c.state.cases, undefined);
  } finally { c.dispose(); await logout(other.access_token); }
});
