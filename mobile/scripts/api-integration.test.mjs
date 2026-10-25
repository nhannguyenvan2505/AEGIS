import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/services/api.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } });
const api = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);

test('mobile API client against isolated Flask HTTP server', async () => {
  assert.ok(process.env.EXPO_PUBLIC_API_URL, 'Run through backend/checks/mobile_http.py');
  const email = `mobile-${Date.now()}@example.test`, password = 'Mobile-test-password-123';
  await api.register(email, password);
  await assert.rejects(api.register(email, password), error => error.status === 409 && error.code === 'email_exists');
  await assert.rejects(api.login(email, 'incorrect-password-123'), error => error.status === 401);
  const session = await api.login(email, password);
  assert.ok(session.access_token); assert.equal(session.user.email, email);
  assert.equal((await api.me(session.access_token)).user.id, session.user.id);
  const farm = await api.request('/farm/plots', { method: 'POST', body: JSON.stringify({ name: 'Ruộng mobile', location_text: 'Integration fixture' }) }, session.access_token);
  assert.equal((await api.request('/farm/plots', {}, session.access_token)).items[0].id, farm.item.id);
  const body = new FormData(); body.append('image', new Blob(['fixture-image'], { type: 'image/jpeg' }), 'leaf.jpg');
  const analysis = await api.detect(session.access_token, body);
  assert.equal(analysis.detections.length, 0); assert.equal(analysis.status, 'no_detection');
  const list = await api.history(session.access_token);
  assert.equal(list.items[0].analysis_id, analysis.analysis_id);
  assert.equal((await api.detail(session.access_token, analysis.analysis_id)).analysis_id, analysis.analysis_id);
  const otherEmail = `other-${Date.now()}@example.test`;
  await api.register(otherEmail, password); const other = await api.login(otherEmail, password);
  await assert.rejects(api.detail(other.access_token, analysis.analysis_id), error => error.status === 404);
  assert.equal((await api.history(other.access_token)).items.length, 0);
  await api.logout(session.access_token);
  await assert.rejects(api.me(session.access_token), error => error.status === 401);
  await api.logout(other.access_token);
});
