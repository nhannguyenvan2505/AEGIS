import assert from 'node:assert/strict';
import test from 'node:test';
import { moduleUrl, apiModule } from './load-followup-test.mjs';

const { currentSeason, matchingForecast, fieldStatus, fieldReadings, fieldArea, loadForecastFarms } =
  await import(await moduleUrl(new URL('../src/features/prediction/forecastFields.ts', import.meta.url)));
const { createIotPreviewStore } =
  await import(await moduleUrl(new URL('../src/features/prediction/iotPreview.ts', import.meta.url)));

const season = (id, start, end = null) => ({ id, plot_id: 'plot-a', name: id, start_date: start, end_date: end });
const source = {
  revision: 2, created_at: '2026-11-09T00:00:00Z', input_sha256: 'a'.repeat(64),
  hourly: { source: 'synthetic', issued_at: '2026-11-09T00:00:00Z', device_id: 'device-a', telemetry: [
    { start_at: '2026-11-08T23:00:00Z', available_at: '2026-11-09T00:00:00Z',
      air_temperature_c: 27.5, relative_humidity_pct: 83, leaf_wet: false, quality: 'valid' },
  ] },
};
const forecast = {
  id: 'forecast-a', season_id: 'season-a', scenario: 'source', model_version: 'fixture',
  issued_at: '2026-11-09T00:00:00Z', target_window_end: '2026-11-12T00:00:00Z', created_at: '2026-11-09T00:00:01Z',
  status: 'forecast_ready', source: 'synthetic', horizon_hours: 72, score: .8, predicted_event: 1,
  reasons: [], source_revision: 2, simulation_clock: true, field_validated: false, threshold: .5,
};
const field = { plot: { id: 'plot-a', farm_id: 'farm-a', name: 'Ruộng Đông', area_ha: 1.2 },
  season: season('season-a', '2026-01-01'), source, forecast };

test('field opens the current season before old and planned seasons without changing their order', () => {
  const seasons = [season('past', '2026-01-01', '2026-05-01'), season('planned', '2026-12-01'),
    season('current', '2026-06-01'), season('older-current', '2026-05-01')];
  assert.equal(currentSeason(seasons, '2026-11-09').id, 'current');
  assert.equal(seasons[0].id, 'past');
  assert.equal(currentSeason([seasons[0], seasons[1]], '2026-11-09').id, 'past');
  assert.equal(currentSeason([season('later', '2027-02-01'), seasons[1]], '2026-11-09').id, 'planned');
  assert.equal(currentSeason([], '2026-11-09'), null);
});

test('independent test scenarios and obsolete sources cannot set a field risk badge', () => {
  const unrelated = [{ ...forecast, scenario: 'ready' }, { ...forecast, source_revision: 1 },
    { ...forecast, issued_at: '2026-11-08T00:00:00Z' }];
  assert.equal(matchingForecast(unrelated, source), null);
  assert.equal(matchingForecast([...unrelated, forecast], source), forecast);
  assert.equal(matchingForecast([forecast], null), null);
  assert.equal(fieldStatus(field).tone, 'high');
  assert.equal(fieldStatus({ ...field, forecast: { ...forecast, predicted_event: 0 } }).tone, 'low');
  for (const amendment of [{ source: null }, { season: null }, { forecast: null },
    { forecast: { ...forecast, status: 'insufficient_data' } }, { error: 'offline' }]) {
    assert.equal(fieldStatus({ ...field, ...amendment }).tone, 'pending');
  }
});

test('IoT preview preserves zero and missing values and excludes future or suspect readings', () => {
  assert.deepEqual(fieldReadings(source), { temperature: 27.5, humidity: 83, soilPh: null, rainfall: null,
    observedAt: '2026-11-08T23:00:00Z' });
  const reading = source.hourly.telemetry[0];
  const withReadings = telemetry => ({ ...source, hourly: { ...source.hourly, telemetry } });
  assert.equal(fieldReadings(withReadings([{ ...reading, air_temperature_c: 0, relative_humidity_pct: 0 }])).humidity, 0);
  assert.equal(fieldReadings(withReadings([{ ...reading, air_temperature_c: null }])).temperature, null);
  assert.equal(fieldReadings(withReadings([{ ...reading, quality: 'suspect' }])).humidity, null);
  assert.equal(fieldReadings(withReadings([{ ...reading, start_at: '2026-11-09T01:00:00Z' }])).temperature, null);
  assert.equal(fieldReadings(null).observedAt, null);
  assert.deepEqual(fieldArea([{ area_ha: 1.2 }, { area_ha: null }, { area_ha: 1.6 }]), { total: 2.8, missing: 1 });
});

test('preview snapshots stay shared without changing the source or API forecasting risk', () => {
  const originalSource = JSON.stringify(source);
  const store = createIotPreviewStore();
  const list = store.get('plot-a');
  const detail = store.get('plot-a');
  assert.equal(list, detail);
  for (const name of ['temperature', 'humidity', 'soilPh', 'rainfall']) assert.equal(Number.isFinite(list.readings[name]), true);
  assert.equal(Number.isFinite(Date.parse(list.readings.observedAt)), true);
  assert.equal(JSON.stringify(source), originalSource);
  assert.equal(fieldReadings(source).soilPh, null);
  assert.equal(fieldStatus({ ...field, source: null, forecast: null }).tone, 'pending');
  assert.equal(fieldStatus(field).tone, 'high');
});

test('farms group their own fields once, including fields without seasons; preview only makes GET requests', async () => {
  const originalFetch = globalThis.fetch;
  const originalUrl = process.env.EXPO_PUBLIC_API_URL;
  const requests = [];
  const farms = [{ id: 'farm-a', name: 'Nông trại A' }, { id: 'farm-b', name: 'Nông trại B' }];
  const plots = [field.plot, { ...field.plot, id: 'plot-b' }, { ...field.plot, farm_id: 'farm-b', id: 'plot-c' }];
  const page = (items, hasNext = false, number = 1) => ({ items, pagination: { page: number, has_next: hasNext } });
  try {
    process.env.EXPO_PUBLIC_API_URL = 'http://forecast-fields.test/api';
    globalThis.fetch = async (url, options) => {
      const parsed = new URL(url);
      requests.push(parsed.pathname);
      assert.equal(options.method ?? 'GET', 'GET');
      assert.equal(options.headers.get('Authorization'), 'Bearer fixture-token');
      const path = parsed.pathname.replace('/api', '');
      if (path === '/farm/farms') return Response.json(parsed.searchParams.get('page') === '1'
        ? page([farms[0]], true) : page([farms[1]], false, 2));
      if (path === '/farm/farms/farm-a/plots') return Response.json(page(plots.slice(0, 2)));
      if (path === '/farm/farms/farm-b/plots') return Response.json(page(plots.slice(2)));
      if (path === '/farm/plots/plot-a/seasons') return Response.json(page([field.season]));
      if (path.endsWith('/seasons')) return Response.json(page([]));
      if (path.endsWith('/forecast-source')) return Response.json({ item: source });
      if (path.endsWith('/forecasts')) return Response.json(page([{ ...forecast, scenario: 'ready' }, forecast]));
      throw new Error('Unexpected request: ' + path);
    };
    const groups = await loadForecastFarms('fixture-token');
    assert.deepEqual(groups.map(group => [group.farm.id, group.fields.map(field => field.plot.id)]),
      [['farm-a', ['plot-a', 'plot-b']], ['farm-b', ['plot-c']]]);
    assert.equal(groups[0].fields[0].forecast.id, forecast.id);
    assert.equal(groups[0].fields[1].season, null);
    assert.equal(groups[1].fields[0].season, null);
    assert.equal(requests.filter(path => path.endsWith('/forecast-source')).length, 1);
    requests.length = 0;
    const previewGroups = await loadForecastFarms('fixture-token', { readForecast: false });
    assert.equal(previewGroups[0].fields[0].plot.id, 'plot-a');
    assert.equal(previewGroups[0].fields[0].source, null);
    assert.equal(previewGroups[0].fields[0].forecast, null);
    assert.ok(requests.every(path => !path.endsWith('/forecast-source') && !path.endsWith('/forecasts')));
    globalThis.fetch = async () => Response.json({ error: { message: 'Expired' } }, { status: 401 });
    await assert.rejects(loadForecastFarms('fixture-token'), error => error instanceof apiModule.ApiError && error.status === 401);
  } finally {
    globalThis.fetch = originalFetch;
    if (originalUrl === undefined) delete process.env.EXPO_PUBLIC_API_URL;
    else process.env.EXPO_PUBLIC_API_URL = originalUrl;
  }
});
