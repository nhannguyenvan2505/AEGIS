// Midterm rehearsal: actual mobile TS API/controller, real Backend/AI HTTP.
// Accounts, observations and environment readings are disposable software fixtures.
import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';
import { createHash, randomUUID } from 'node:crypto';
import { apiModule as api, clientModule, controllerModule } from '../mobile/scripts/load-followup-test.mjs';

const output = process.env.AEGIS_REHEARSAL_CLIENT_OUT;
const origin = process.env.EXPO_PUBLIC_API_URL?.replace(/\/api\/?$/, '');
const steps = [];
const result = { success: false, actual_mobile_typescript: true, real_ai_inference: false,
  environment_source: 'mock', observation_source: 'synthetic', native_ui_tested: false, steps };
let stage = 'configuration';
let controller;
function verify(name, condition) {
  stage = name;
  steps.push({ name, passed: Boolean(condition) });
  assert.ok(condition, name);
}
async function denied(name, work, status, code) {
  stage = name;
  await assert.rejects(work, e => e instanceof api.ApiError && e.status === status && (!code || e.code === code));
  verify(name, true);
}
try {
  assert.ok(output && origin && process.env.AEGIS_REHEARSAL_IMAGE);
  const bytes = await readFile(process.env.AEGIS_REHEARSAL_IMAGE);
  const password = 'Midterm-software-fixture-123';
  const email = `midterm-${randomUUID()}@example.test`;
  const otherEmail = `midterm-${randomUUID()}@example.test`;
  stage = 'register_and_login';
  await api.register(email, password); await api.register(otherEmail, password);
  const session = await api.login(email, password);
  const other = await api.login(otherEmail, password);
  const token = session.access_token;
  verify('login_me', (await api.me(token)).user.id === session.user.id);
  const caps = await api.request('/mobile/capabilities', {}, token);
  verify('pilot_with_worker_and_raw_write_off', caps.mode === 'pilot' && caps.follow_up.available &&
    !caps.mock_automation_process_enabled && !caps.controlled_experiment_raw_write);
  const post = (path, body) => api.request(path, { method: 'POST', body: JSON.stringify(body) }, token);
  const plot = (await post('/farm/plots', { name: 'Midterm software demonstration', location_text: 'Synthetic demo context' })).item;
  const now = new Date();
  const dateAt = days => new Date(now.getTime() + days * 86400000).toISOString().slice(0, 10);
  const season = (await post(`/farm/plots/${plot.id}/seasons`, { name: 'Software demonstration season',
    start_date: dateAt(-3), end_date: dateAt(3) })).item;
  verify('owned_plot_and_season', (await api.request(`/farm/plots/${plot.id}/seasons`, {}, token)).items[0].id === season.id);

  stage = 'real_image_detection';
  const form = new FormData();
  form.append('image', new Blob([bytes], { type: 'image/jpeg' }), 'midterm-fixture.jpg');
  const analysis = await api.detect(token, form);
  verify('real_v4_identity', analysis.model_version === 'aegis-yolo11n-v4-50epochs' &&
    analysis.model_sha256 === process.env.AEGIS_REHEARSAL_MODEL_SHA256);
  verify('request_trace_and_timings', typeof analysis.request_id === 'string' &&
    analysis.timings.ai_processing_ms >= 0 && analysis.timings.ai_roundtrip_ms >= 0);
  result.real_ai_inference = true;
  result.image = { fixture_sha256: createHash('sha256').update(bytes).digest('hex'),
    model_version: analysis.model_version, model_sha256: analysis.model_sha256,
    status: analysis.status, detection_count: analysis.detections.length,
    diseases: [...new Set(analysis.detections.map(d => d.disease))], timings: analysis.timings };
  verify('history_contains_analysis', (await api.history(token)).items[0].analysis_id === analysis.analysis_id);
  verify('detail_matches_saved_result', JSON.stringify(await api.detail(token, analysis.analysis_id)) === JSON.stringify(analysis));
  const image = await fetch(origin + analysis.image_url, { headers: { Authorization: `Bearer ${token}` } });
  verify('private_image_bytes_match', image.status === 200 &&
    createHash('sha256').update(Buffer.from(await image.arrayBuffer())).digest('hex') === result.image.fixture_sha256);
  await denied('foreign_analysis_rejected', () => api.detail(other.access_token, analysis.analysis_id), 404);
  verify('foreign_history_empty', (await api.history(other.access_token)).items.length === 0);
  const foreignImage = await fetch(origin + analysis.image_url, { headers: { Authorization: `Bearer ${other.access_token}` } });
  verify('foreign_private_image_404', foreignImage.status === 404);
  verify('unauthenticated_private_image_401', (await fetch(origin + analysis.image_url)).status === 401);
  const bad = new FormData(); bad.append('image', new Blob(['not-an-image']), 'invalid.jpg');
  await denied('invalid_image_rejected', () => api.detect(token, bad), 400, 'invalid_image');
  verify('invalid_image_did_not_persist', (await api.history(token)).pagination.total === 1);

  stage = 'mock_environment_and_assessment';
  const device = (await post(`/farm/seasons/${season.id}/devices`, { name: 'Software-only mock',
    device_code: `MIDTERM-${randomUUID()}`, source: 'mock' })).item;
  const end = Math.floor(Date.now() / 3600000) * 3600000;
  const records = Array.from({ length: 24 }, (_, i) => ({ start_at: new Date(end - (24 - i) * 3600000).toISOString(),
    air_temperature_c: 26, relative_humidity_pct: 95, leaf_wet: true }));
  verify('mock_24_buckets_saved', (await post(`/farm/devices/${device.id}/telemetry`, { source: 'mock', records })).inserted === 24);
  verify('same_mock_buckets_replayed', (await post(`/farm/devices/${device.id}/telemetry`, { source: 'mock', records })).replayed === 24);
  const assessment = (await post(`/farm/devices/${device.id}/assessments`, { as_of: new Date(end).toISOString() })).item;
  verify('advisory_explicitly_mock', assessment.result.status === 'advisory' && assessment.result.is_mock && !assessment.result.field_validated);
  await post(`/farm/assessments/${assessment.id}/analyses`, { analysis_id: analysis.analysis_id });
  verify('real_analysis_linked_to_mock_context', (await api.request(`/farm/assessments/${assessment.id}/analyses`, {}, token)).items[0].analysis_id === analysis.analysis_id);
  const followup = (await post(`/farm/assessments/${assessment.id}/follow-up`, { reason: 'Observe synthetic demonstration context' })).item;
  const visitPayload = { client_visit_id: randomUUID(), source: 'synthetic', observed_at: new Date().toISOString(), scheduled: true,
    finding: 'uncertain', notes: 'Software fixture, not field observation', analysis_id: analysis.analysis_id,
    review: null, record_status: 'active', change_reason: 'Midterm software demonstration' };
  const visit = (await post(`/farm/seasons/${season.id}/observations`, visitPayload)).item;
  const committed = [];
  const transport = { ...clientModule.followupClient, command: async (...args) => {
    const response = await clientModule.followupClient.command(...args);
    committed.push({ command: structuredClone(args[2]), response }); return response;
  } };
  let expired = 0;
  controller = new controllerModule.FollowupController(token, () => {}, () => expired++, randomUUID, transport);
  stage = 'actual_followup_controller';
  await controller.start(); await controller.choosePlot(plot.id); await controller.chooseSeason(season.id);
  await controller.open(followup.id);
  verify('controller_reads_required_current', controller.state.view?.required.id === assessment.id && controller.state.view?.current.id === assessment.id);
  controller.edit('Read synthetic work item'); await controller.act('acknowledge');
  verify('controller_acknowledged', controller.state.detail?.state === 'acknowledged');
  controller.edit('Checked synthetic observation', visit.id); await controller.act('check');
  verify('controller_checked', controller.state.detail?.state === 'checked' && !controller.state.view.action_capabilities.needs_recheck);
  const correction = Object.fromEntries(['finding', 'notes', 'analysis_id', 'review', 'record_status', 'change_reason'].map(k => [k, visitPayload[k]]));
  Object.assign(correction, { base_revision: 1, notes: 'Corrected software evidence' });
  await api.request(`/farm/observations/${visit.id}`, { method: 'PUT', body: JSON.stringify(correction) }, token);
  await controller.refresh();
  verify('correction_requires_recheck', controller.state.view?.action_capabilities.recheck_reasons.includes('observation_changed'));
  const eventsPath = `/farm/follow-ups/${followup.id}/events`;
  const close = version => ({ client_event_id: randomUUID(), base_version: version, action: 'close',
    reason: 'Close software demonstration workflow', observation_id: null, resolution: 'followup_recorded' });
  await denied('close_blocked_until_recheck', () => post(eventsPath, close(3)), 409, 'followup_observation_changed');
  controller.edit('Rechecked corrected synthetic evidence', visit.id); await controller.act('check');
  verify('recheck_uses_current_revision', controller.state.detail?.version === 4 && !controller.state.view.action_capabilities.needs_recheck);
  const closed = await post(eventsPath, close(4));
  verify('workflow_closed_without_disease_confirmation', closed.item.state === 'closed' && !closed.item.disease_confirmed);
  const replay = await post(eventsPath, committed[0].command);
  verify('old_command_exact_replay_preserved', replay.event.id === committed[0].response.event.id && replay.item.version === 5);
  verify('assessment_snapshot_unchanged', JSON.stringify((await api.request(`/farm/assessments/${assessment.id}`, {}, token)).item) === JSON.stringify(assessment));
  await denied('foreign_followup_rejected', () => clientModule.followupClient.detail(other.access_token, followup.id), 404);
  await api.logout(token); await controller.refresh();
  verify('logout_revokes_token_and_clears_controller', expired === 1 && controller.state.view === undefined);
  await denied('revoked_history_rejected', () => api.history(token), 401);
  await api.logout(other.access_token);
  result.success = true;
} catch (error) {
  result.error_type = error.name;
  result.failed_stage = stage; // No body, credentials, headers or error message exported.
  process.exitCode = 1;
} finally {
  controller?.dispose();
  await writeFile(output, JSON.stringify(result, null, 2), { flag: 'wx' });
  console.log(JSON.stringify({ success: result.success, checks: steps.length, failed_stage: result.failed_stage }));
}
