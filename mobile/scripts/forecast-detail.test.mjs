import assert from 'node:assert/strict';
import test from 'node:test';
import { moduleUrl, apiModule } from './load-followup-test.mjs';

const { loadForecastDetail, forecastAlert, acknowledgeForecastAlert, forecastReason, forecastExplanation, detailDate } =
  await import(await moduleUrl(new URL('../src/features/prediction/forecastDetail.ts', import.meta.url)));
const { fieldReadings, fieldStatus } = await import(await moduleUrl(new URL('../src/features/prediction/forecastFields.ts', import.meta.url)));
const plot = { id: 'plot', farm_id: 'farm', name: 'An Bình 1', area_ha: 1.2 };
const season = { id: 'season', plot_id: 'plot', name: 'Đông xuân', start_date: '2026-11-01', end_date: null };
const source = { revision: 2, created_at: '2026-11-09T00:00:00Z', input_sha256: 'a'.repeat(64),
  hourly: { source: 'synthetic', device_id: 'device', issued_at: '2026-11-09T00:00:00Z', telemetry: [
    { start_at: '2026-11-08T23:00:00Z', available_at: '2026-11-09T00:00:00Z', air_temperature_c: 28.5,
      relative_humidity_pct: 89, leaf_wet: true, quality: 'valid' },
  ] } };
const forecast = Object.freeze({ id: 'forecast', season_id: 'season', scenario: 'source', source: 'synthetic',
  model_version: 'fixture', status: 'forecast_ready', score: .8, predicted_event: 1, reasons: [],
  issued_at: '2026-11-09T00:00:00Z', target_window_end: '2026-11-12T00:00:00Z', created_at: '2026-11-09T00:00:01Z',
  source_revision: 2, simulation_clock: true, field_validated: false, threshold: .5, horizon_hours: 72 });
const alert = { id: 'alert', forecast_id: 'forecast', season_id: 'season', plot_id: 'plot', state: 'unread', version: 1,
  acknowledged_at: null, source: 'synthetic', field_validated: false, disease_confirmed: false };

async function mockedFetch(handler, run) {
  const originalFetch = globalThis.fetch;
  const originalUrl = process.env.EXPO_PUBLIC_API_URL;
  try {
    process.env.EXPO_PUBLIC_API_URL = 'http://forecast-detail.test/api';
    globalThis.fetch = async (url, options) => {
      assert.equal(options.headers.get('Authorization'), 'Bearer fixture-token');
      return handler(new URL(url).pathname.replace('/api', ''), options);
    };
    return await run();
  } finally {
    globalThis.fetch = originalFetch;
    if (originalUrl === undefined) delete process.env.EXPO_PUBLIC_API_URL;
    else process.env.EXPO_PUBLIC_API_URL = originalUrl;
  }
}

function detailResponse(path, options) {
  assert.equal(options.method ?? 'GET', 'GET');
  if (path.endsWith('/forecast-source')) return Response.json({ item: source });
  if (path.endsWith('/forecasts')) return Response.json({ items: [forecast], pagination: { page: 1, has_next: false } });
  if (path.endsWith('/cultivation-profile')) return Response.json({ item: { season_id: 'season', profile: { rice_variety: 'OM 5451', province_or_city: 'Cần Thơ' } } });
  if (path.endsWith('/alert-evaluation')) return Response.json({ item: { forecast_id: 'forecast', outcome: 'created', alert_id: 'alert' } });
  if (path.endsWith('/forecast-alerts/alert')) return Response.json({ item: alert });
  throw new Error('Unexpected request: ' + path);
}

test('detail loads the selected field, its exact source and read state without any automatic write', async () => {
  await mockedFetch(detailResponse, async () => {
    const detail = await loadForecastDetail('fixture-token', plot, season);
    assert.equal(detail.field.forecast.id, 'forecast');
    assert.equal(detail.field.forecast.horizon_hours, 72);
    assert.equal(detail.alert.state, 'unread');
    assert.equal(detail.profile.rice_variety, 'OM 5451');
    assert.deepEqual(detail.notes, []);
    assert.deepEqual(fieldReadings(detail.field.source), { temperature: 28.5, humidity: 89, soilPh: null, rainfall: null,
      observedAt: '2026-11-08T23:00:00Z' });
    await assert.rejects(loadForecastDetail('fixture-token', plot, { ...season, plot_id: 'other-owner-plot' }), /không thuộc/);
  });
});

test('empty and incomplete data stay pending instead of inheriting a high or low risk', async () => {
  await mockedFetch(() => { throw new Error('No request allowed'); }, async () => {
    const detail = await loadForecastDetail('fixture-token', plot, null);
    assert.equal(fieldStatus(detail.field).tone, 'pending');
    assert.match(forecastExplanation(detail.field), /chưa có mùa vụ/);
  });
  await mockedFetch((path, options) => path.endsWith('/forecast-source') ? Response.json({ item: null }) : detailResponse(path, options), async () => {
    const detail = await loadForecastDetail('fixture-token', plot, season);
    assert.equal(detail.field.forecast, null);
    assert.equal(detail.alert, null);
    assert.equal(fieldStatus(detail.field).tone, 'pending');
    assert.match(forecastExplanation(detail.field), /chưa có dữ liệu môi trường/);
  });
  await mockedFetch((path, options) => path.endsWith('/forecast-source') ? Response.json({ error: { message: 'Unavailable' } }, { status: 503 }) : detailResponse(path, options), async () => {
    const detail = await loadForecastDetail('fixture-token', plot, season);
    assert.ok(detail.notes.length > 0);
    assert.equal(fieldStatus(detail.field).tone, 'pending');
  });
});

test('read receipt saves only the alert version and keeps forecast risk unchanged', async () => {
  const originalForecast = JSON.stringify(forecast);
  await mockedFetch((path, options) => {
    assert.equal(path, '/farm/forecast-alerts/alert/acknowledgements');
    assert.equal(options.method, 'POST');
    assert.deepEqual(JSON.parse(options.body), { base_version: 1 });
    return Response.json({ item: { ...alert, state: 'acknowledged', version: 2, acknowledged_at: '2026-11-09T00:00:02Z' } });
  }, async () => {
    const saved = await acknowledgeForecastAlert(alert, forecast, plot.id, 'fixture-token');
    assert.equal(saved.state, 'acknowledged');
    assert.equal(alert.state, 'unread');
    assert.equal(JSON.stringify(forecast), originalForecast);
    assert.equal(fieldStatus({ plot, season, source, forecast }).tone, 'high');
  });
});

test('cooldown anchors and unrelated alert owners cannot produce a read receipt for this field', async () => {
  const paths = [];
  await mockedFetch(path => {
    paths.push(path);
    return Response.json({ item: { forecast_id: 'forecast', outcome: 'suppressed_cooldown', alert_id: 'older-alert' } });
  }, async () => assert.equal(await forecastAlert(forecast, plot.id, 'fixture-token'), null));
  assert.equal(paths.length, 1);
  await mockedFetch((path, options) => path.endsWith('/forecast-alerts/alert') ? Response.json({ item: { ...alert, plot_id: 'other-plot' } }) : detailResponse(path, options),
    async () => assert.rejects(forecastAlert(forecast, plot.id, 'fixture-token'), /không khớp/));
  await mockedFetch(() => Response.json({ item: { ...alert, state: 'acknowledged', version: 2, id: 'different-alert' } }),
    async () => assert.rejects(acknowledgeForecastAlert(alert, forecast, plot.id, 'fixture-token'), /chưa xác nhận/));
});

test('session expiry propagates and absent measurements or model reasons remain explicit', async () => {
  await mockedFetch(() => Response.json({ error: { message: 'Expired' } }, { status: 401 }),
    async () => assert.rejects(loadForecastDetail('fixture-token', plot, season), error => error instanceof apiModule.ApiError && error.status === 401));
  assert.equal(detailDate(null), '—');
  assert.equal(detailDate('bad timestamp'), '—');
  assert.match(forecastReason({ code: 'incomplete_hourly_coverage', missing_hours: 6, variable: 'relative_humidity_pct' }), /6 giờ dữ liệu độ ẩm/);
  assert.match(forecastReason({ code: 'unknown_calendar_crop_age' }), /tuổi lúa/);
  assert.match(forecastExplanation({ plot, season, source, forecast: { ...forecast, status: 'insufficient_data' } }), /chưa đầy đủ/);
});
