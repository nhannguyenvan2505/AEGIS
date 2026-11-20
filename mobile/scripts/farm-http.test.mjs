import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';

async function moduleText(path) {
  const source = await readFile(new URL(path, import.meta.url), 'utf8');
  return ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } }).outputText;
}
const apiUrl = 'data:text/javascript;base64,' + Buffer.from(await moduleText('../src/services/api.ts')).toString('base64');
const api = await import(apiUrl);
const source = (await moduleText('../src/features/farms/client.ts')).replace("'../../services/api'", JSON.stringify(apiUrl));
const { farmClient, searchText, validDay } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));

test('Vietnamese search and calendar validation', () => {
  assert.equal(searchText('  Nông trại Đông Bình  '), 'nong trai dong binh');
  assert.equal(validDay('2024-02-29'), true);
  for (const date of ['2026-02-29', '2026-02-30', '2026-13-01', '2026-1-01', '0000-01-01', 'not-a-date']) assert.equal(validDay(date), false, date);
});

test('mobile farm -> plot -> season client against isolated Flask HTTP', async () => {
  assert.ok(process.env.EXPO_PUBLIC_API_URL, 'Run through backend/checks/mobile_http.py');
  const password = 'Farm-mobile-test-123';
  const email = `farm-mobile-${Date.now()}@example.test`;
  await api.register(email, password);
  const { access_token: token } = await api.login(email, password);
  const values = { name: 'An Bình', address: 'Bình Thủy, Cần Thơ', manager: 'Nguyễn Văn Minh', notes: 'Kiểm tra mực nước.\nTheo dõi buổi sáng.' };
  const farm = (await farmClient.save(token, values)).item;
  assert.equal((await farmClient.farms(token)).length, 1);
  const updated = (await farmClient.save(token, { ...values, name: 'An Bình mới' }, farm)).item;
  assert.equal(updated.version, 2);
  assert.equal(updated.notes, values.notes);
  await assert.rejects(farmClient.save(token, values, farm), error => error.status === 409);
  const plot = (await farmClient.createPlot(token, farm.id, { name: 'Ruộng Đông', location_text: 'Cạnh kênh', area_ha: 1.5 })).item;
  assert.equal(plot.farm_id, farm.id);
  assert.equal((await farmClient.plots(token, farm.id))[0].area_ha, 1.5);
  const season = (await farmClient.createSeason(token, plot.id, { name: 'Đông xuân', start_date: '2026-11-01' })).item;
  assert.equal((await farmClient.seasons(token, plot.id))[0].id, season.id);
  assert.equal((await farmClient.farms(token))[0].plot_count, 1);
  await assert.rejects(farmClient.remove(token, updated), error => error.status === 409 && error.code === 'farm_not_empty');
  const empty = (await farmClient.save(token, { ...values, name: 'Nông trại trống' })).item;
  await farmClient.remove(token, empty);
  assert.equal((await farmClient.farms(token)).length, 1);
  await api.logout(token);
});
