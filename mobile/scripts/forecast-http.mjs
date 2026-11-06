// Called by the isolated Backend rehearsal. Credentials arrive via stdin.
import assert from 'node:assert/strict';
import { moduleUrl } from './load-followup-test.mjs';

const { issueForecast, forecastHistory, forecastSource, forecastOverview, summarizeSource } = await import(await moduleUrl(new URL('../src/features/prediction/client.ts', import.meta.url)));
let input = '';
for await (const chunk of process.stdin) input += chunk;
const { season, owner, other, offline, expectedTotal = 2 } = JSON.parse(input);
const source = await forecastSource(season, owner);
assert.equal(source.revision, 3);
assert.equal(summarizeSource(source).validHours, 119);
await assert.rejects(forecastSource(season, other), e => e.status === 404);
assert.equal((await forecastOverview(other)).items.length, 0);
const overview = (await forecastOverview(owner)).items.find(item => item.season_id === season);
assert.equal(overview.source_revision, 3);
if (offline) {
  await assert.rejects(issueForecast(season, owner, 'ready'), e => e.status === 503);
  await assert.rejects(issueForecast(season, owner, 'source'), e => e.status === 503);
} else {
  const managed = await issueForecast(season, owner, 'source');
  assert.equal(managed.source_revision, 3);
  assert.equal(managed.status, 'insufficient_data');
  const ready = await issueForecast(season, owner, 'ready');
  assert.equal(ready.status, 'forecast_ready');
  assert.equal((await issueForecast(season, owner, 'ready')).id, ready.id);
  const missing = await issueForecast(season, owner, 'insufficient');
  assert.equal(missing.status, 'insufficient_data');
  assert.equal(missing.score, null);
  assert.ok(missing.reasons.length);
  await assert.rejects(forecastHistory(season, other, 1), e => e.status === 404);
}
assert.equal((await forecastHistory(season, owner, 1)).pagination.total, expectedTotal);
