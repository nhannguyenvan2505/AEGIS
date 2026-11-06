import assert from 'node:assert/strict';
import test from 'node:test';
import { moduleUrl, apiModule } from './load-followup-test.mjs';

const client = await import(await moduleUrl(new URL('../src/features/prediction/client.ts', import.meta.url)));
process.env.EXPO_PUBLIC_API_URL = 'http://127.0.0.1:1/api';

test('non-JSON errors retain status for session expiry and service errors', async () => {
  const original = globalThis.fetch;
  try {
    for (const status of [401, 503]) {
      globalThis.fetch = async () => new Response('<html>Unavailable</html>', {status});
      await assert.rejects(apiModule.request('/test'), e => e instanceof apiModule.ApiError && e.status === status);
    }
    globalThis.fetch = async () => new Response('not JSON', {status: 200});
    await assert.rejects(apiModule.request('/test'), e => e.code === 'invalid_response');
    globalThis.fetch = async () => { throw new TypeError('Network request failed'); };
    await assert.rejects(apiModule.request('/test'), /Không kết nối được Backend/);
  } finally { globalThis.fetch = original; }
});

test('source summary excludes future, late and old readings and preserves missing values', () => {
  const reading = {start_at: '2026-04-10T11:00:00Z', available_at: '2026-04-10T12:00:00Z',
    air_temperature_c: 0, relative_humidity_pct: 0, leaf_wet: false, quality: 'valid'};
  const source = {hourly: {issued_at: '2026-04-10T12:00:00Z', telemetry: [reading,
    {...reading, start_at: '2026-04-10T12:00:00Z'},
    {...reading, start_at: '2026-04-10T10:00:00Z', available_at: '2026-04-10T13:00:00Z'},
    {...reading, start_at: '2026-04-01T10:00:00Z'},
    {...reading, start_at: '2026-04-10T09:00:00Z', air_temperature_c: null, quality: 'missing'}]}};
  const summary = client.summarizeSource(source);
  assert.equal(summary.validHours, 1);
  assert.equal(summary.recent.length, 2);
  assert.equal(summary.latest.air_temperature_c, 0);
  assert.equal(summary.recent[0].air_temperature_c, null);
});

test('forecast client rejects mismatched horizons, thresholds and prediction decisions', async () => {
  const original = globalThis.fetch;
  const result = {id: 'forecast', season_id: 'season', scenario: 'source', source_revision: 1,
    source: 'synthetic', simulation_clock: true, field_validated: false, threshold: .5,
    horizon_hours: 72, model_version: 'fm02-logistic-v1', status: 'forecast_ready', score: .7,
    predicted_event: 1, reasons: [], issued_at: '2026-04-10T12:00:00Z',
    target_window_end: '2026-04-13T12:00:00Z', created_at: '2026-11-05T00:00:00Z'};
  try {
    for (const amendment of [{}, {threshold: .3}, {predicted_event: 0}, {source_revision: 0},
        {target_window_end: '2026-04-12T12:00:00Z'}, {field_validated: true}, {season_id: 'other'}]) {
      globalThis.fetch = async () => Response.json({item: {...result, ...amendment}});
      if (Object.keys(amendment).length) await assert.rejects(client.issueForecast('season', 'token', 'source'));
      else assert.equal((await client.issueForecast('season', 'token', 'source')).score, .7);
    }
  } finally { globalThis.fetch = original; }
});
