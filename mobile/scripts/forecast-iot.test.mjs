import assert from 'node:assert/strict';
import test from 'node:test';
import { moduleUrl } from './load-followup-test.mjs';

const { createIotPreviewStore } = await import(await moduleUrl(new URL('../src/features/prediction/iotPreview.ts', import.meta.url)));
const number = value => new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 1 }).format(value);

test('fields have distinct snapshots and exactly one adverse field throughout refresh cycles', () => {
  const store = createIotPreviewStore();
  const ids = Array.from({ length: 12 }, (_, index) => `plot-${index}`);
  const initial = ids.map(id => store.get(id));
  assert.equal(new Set(initial.map(item => JSON.stringify(item.readings))).size, ids.length);
  assert.equal(initial.filter(item => item.forecast.status.tone === 'high').length, 1);
  assert.equal(initial[0].forecast.status.tone, 'high');
  for (let frame = 0; frame < 5; frame++) {
    for (const id of ids) store.refresh(id);
    const snapshots = ids.map(id => store.get(id));
    assert.equal(snapshots.filter(item => item.forecast.status.tone === 'high').length, 1);
    assert.ok(snapshots.slice(1).every(item => item.forecast.status.tone === 'low'));
  }
});

test('refresh broadcasts the same atomic reading and forecast to all views of that field only', () => {
  let now = Date.parse('2026-11-09T00:00:00Z');
  const store = createIotPreviewStore(() => now);
  const original = store.get('a');
  const other = store.get('b');
  const views = [original, original, original];
  const unsubscribers = views.map((_, index) => store.subscribe('a', () => { views[index] = store.get('a'); }));
  let otherNotifications = 0;
  const unsubscribeOther = store.subscribe('b', () => otherNotifications++);
  now += 10000;
  const updated = store.refresh('a');
  assert.ok(views.every(view => view === updated));
  assert.notDeepEqual(updated.readings, original.readings);
  assert.equal(store.get('b'), other);
  assert.equal(otherNotifications, 0);
  assert.equal(updated.readings.observedAt, '2026-11-09T00:00:10.000Z');
  assert.equal(updated.forecast.issuedAt, updated.readings.observedAt);
  assert.ok(Object.isFrozen(original.readings));
  unsubscribers.forEach(unsubscribe => unsubscribe());
  unsubscribeOther();
  store.refresh('a');
  assert.ok(views.every(view => view === updated));
});

test('explanation, risk and 72 hour outlook match the current readings on every frame', () => {
  const store = createIotPreviewStore(() => Date.parse('2026-11-09T00:00:00Z'));
  for (const id of ['high', 'low']) {
    for (let frame = 0; frame < 5; frame++) {
      const { readings, forecast } = frame ? store.refresh(id) : store.get(id);
      for (const key of ['temperature', 'humidity', 'rainfall']) {
        assert.ok(forecast.explanation.includes(number(readings[key])));
      }
      assert.equal(forecast.issuedAt, readings.observedAt);
      assert.equal(Date.parse(forecast.targetWindowEnd) - Date.parse(forecast.issuedAt), 72 * 3600000);
      assert.equal(forecast.horizonHours, 72);
      assert.equal(forecast.status.tone, id);
      assert.match(forecast.outlook, /72 giờ/);
      if (id === 'high') assert.match(forecast.outlook, /kiểm tra lá trong 24 giờ/);
    }
  }
});

test('samples cycle while timestamps advance, and a fresh session starts with independent state', () => {
  const store = createIotPreviewStore(() => 100000);
  const first = store.get('a');
  let latest = first;
  for (let count = 0; count < 4; count++) latest = store.refresh('a');
  assert.deepEqual({ ...latest.readings, observedAt: null }, { ...first.readings, observedAt: null });
  assert.ok(Date.parse(latest.readings.observedAt) > Date.parse(first.readings.observedAt));
  assert.equal(latest.revision, 4);
  const fresh = createIotPreviewStore(() => 100000);
  assert.equal(fresh.get('a').revision, 0);
  assert.deepEqual(fresh.get('a'), first);
});
