import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import ts from 'typescript';
import { unzipSync, strFromU8 } from 'fflate';
import { moduleUrl } from './load-followup-test.mjs';

const modelUrl = await moduleUrl(new URL('../src/features/reports/reportModel.ts', import.meta.url));
const model = await import(modelUrl);
const source = await readFile(new URL('../src/features/reports/reportDocument.ts', import.meta.url), 'utf8');
let documentCode = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } }).outputText;
documentCode = documentCode.replace(/from ['"]fflate['"]/g, `from '${import.meta.resolve('fflate')}'`).replace(/from ['"].\/reportModel['"]/g, `from '${modelUrl}'`);
const { renderReportHtml, buildReportWorkbook, reportFileName } = await import('data:text/javascript;base64,' + Buffer.from(documentCode).toString('base64'));
const { buildPreviewReport, reportTotals, reportDay, parseReportDay, validateReportRange, sampleReportPoints, reportKey } = model;
const now = Date.parse('2026-11-10T01:00:00Z');
const input = {
  farm: { id: 'farm-a', name: 'Nông trại A', address: 'Cần Thơ', manager: '', notes: '', version: 1, plot_count: 2, area_ha: 3, plots_without_area: 0 },
  plot: { id: 'plot-a', farm_id: 'farm-a', name: 'An Bình 1', location_text: 'Cần Thơ', area_ha: 1.2 },
  range: { start: '2026-11-07', end: '2026-11-10' },
  latest: { temperature: 27.5, humidity: 94, soilPh: 4.8, rainfall: 18.4, observedAt: '2026-11-10T00:30:00Z' },
};

test('report dates validate calendar boundaries, UTC+7, ordering and bounded periods', () => {
  assert.equal(reportDay(Date.parse('2026-11-09T17:00:00Z')), '2026-11-10');
  assert.equal(parseReportDay('10/11/2026'), '2026-11-10');
  assert.equal(parseReportDay('29/02/2024'), '2024-02-29');
  for (const day of ['29/02/2026', '31/11/2026', '00/11/2026', 'bad']) assert.equal(parseReportDay(day), null);
  assert.equal(validateReportRange(input.range, now), '');
  for (const range of [{ start: '2026-11-11', end: '2026-11-10' }, { start: '2026-11-07', end: '2026-11-11' }, { start: '2026-01-01', end: '2026-11-10' }]) assert.ok(validateReportRange(range, now));
});

test('reports use the exact four existing IoT metrics and latest snapshot without mutating it', () => {
  const original = structuredClone(input);
  const report = buildPreviewReport(input, now);
  assert.deepEqual(report.points.at(-1), { day: '2026-11-10', ...input.latest });
  assert.deepEqual(model.reportMetrics.map(metric => metric.key), ['temperature', 'humidity', 'soilPh', 'rainfall']);
  assert.equal(report.asOf, input.latest.observedAt);
  assert.deepEqual(input, original);
  assert.ok(report.points.every(point => point.day >= input.range.start && point.day <= input.range.end && Date.parse(point.observedAt) <= now));
  assert.equal(report.key, reportKey(input));
  assert.throws(() => buildPreviewReport({ ...input, plot: { ...input.plot, farm_id: 'another-farm' } }, now), /không thuộc/);
});

test('overlapping periods use identical historical observations and never include future or unavailable data', () => {
  const full = buildPreviewReport(input, now);
  const shorter = buildPreviewReport({ ...input, range: { start: '2026-11-08', end: '2026-11-09' } }, now);
  assert.deepEqual(shorter.points, full.points.filter(point => point.day >= '2026-11-08' && point.day <= '2026-11-09'));
  const future = buildPreviewReport({ ...input, latest: { ...input.latest, observedAt: '2026-11-11T00:00:00Z' } }, now);
  assert.equal(future.points.length, 0);
  const empty = buildPreviewReport({ ...input, range: { start: '2026-01-01', end: '2026-01-04' } }, now);
  assert.equal(empty.asOf, null);
  assert.equal(empty.points.length, 0);
  assert.equal(reportTotals(empty).forecasts, 0);
  assert.throws(() => buildReportWorkbook(empty), /Chưa có dữ liệu/);
  assert.throws(() => renderReportHtml(empty), /Chưa có dữ liệu/);
});

test('zero measurements remain data, missing weather does not become a low risk forecast', () => {
  const zero = buildPreviewReport({ ...input, latest: { ...input.latest, rainfall: 0, humidity: 0, temperature: 0, soilPh: 0 } }, now);
  assert.equal(zero.points.at(-1).rainfall, 0);
  assert.equal(zero.points.at(-1).temperature, 0);
  assert.equal(zero.points.at(-1).humidity, 0);
  assert.equal(zero.points.at(-1).soilPh, 0);
  const precise = { ...input.latest, temperature: 28.37, humidity: 84.25, soilPh: 6.15, rainfall: 12.35 };
  assert.deepEqual(buildPreviewReport({ ...input, latest: precise }, now).points.at(-1), { day: '2026-11-10', ...precise });
  const missing = buildPreviewReport({ ...input, latest: { ...input.latest, temperature: NaN, humidity: null } }, now);
  assert.ok(missing.points.every(point => point.temperature === null && point.humidity === null));
  assert.equal(reportTotals(missing).forecasts, 0);
});

test('summary counters, risk events, alert events and sampling agree within the selected period', () => {
  const report = buildPreviewReport(input, now);
  const totals = reportTotals(report);
  assert.equal(totals.scans, totals.suspected + totals.unclear);
  assert.equal(totals.forecasts, totals.high + totals.low);
  assert.equal(totals.alerts, totals.high);
  assert.equal(totals.unread, totals.alerts);
  assert.ok(report.scans.every(scan => reportDay(Date.parse(scan.at)) >= input.range.start && reportDay(Date.parse(scan.at)) <= input.range.end));
  const points = Array.from({ length: 30 }, (_, index) => index);
  const sampled = sampleReportPoints(points);
  assert.equal(sampled.length, 7);
  assert.equal(sampled[0], 0);
  assert.equal(sampled.at(-1), 29);
  assert.deepEqual(sampleReportPoints(points, 1), [29]);
});

test('PDF HTML and true XLSX preserve the selected field, Vietnamese text, metrics and summary', async () => {
  const report = buildPreviewReport(input, now);
  const totals = reportTotals(report);
  const html = renderReportHtml(report);
  assert.equal((html.match(/<section class="page">/g) ?? []).length, 2);
  for (const text of [input.plot.name, input.farm.name, 'pH đất', 'Lượng mưa', 'Dữ liệu minh họa']) assert.ok(html.includes(text));
  const workbook = buildReportWorkbook(report);
  assert.equal(String.fromCharCode(workbook[0], workbook[1]), 'PK');
  const files = unzipSync(workbook);
  assert.equal(Object.keys(files).filter(name => /^xl\/worksheets\/sheet\d.xml$/.test(name)).length, 5);
  const environment = strFromU8(files['xl/worksheets/sheet2.xml']);
  for (const text of ['Nhiệt độ (°C)', 'Độ ẩm không khí (%)', 'pH đất (pH)', 'Lượng mưa (mm)', '<v>27.5</v>']) assert.ok(environment.includes(text));
  assert.ok(strFromU8(files['xl/worksheets/sheet1.xml']).includes(`<v>${totals.scans}</v>`));
  const artifact = new URL('../.expo/reports-review/', import.meta.url);
  await mkdir(artifact, { recursive: true });
  await writeFile(new URL('report-sample.xlsx', artifact), workbook);
  await writeFile(new URL('report-sample.html', artifact), html);
});

test('exported field names are escaped literal text and filenames cannot escape the export directory', () => {
  const report = buildPreviewReport({ ...input, plot: { ...input.plot, id: '../../plot', name: '=SUM(1,2)<script>alert(1)</script>&' } }, now);
  const html = renderReportHtml(report);
  assert.ok(!html.includes('<script>'));
  assert.ok(html.includes('&lt;script&gt;'));
  const files = unzipSync(buildReportWorkbook(report));
  const sheet = strFromU8(files['xl/worksheets/sheet1.xml']);
  assert.ok(sheet.includes('=SUM(1,2)&lt;script&gt;'));
  assert.ok(!sheet.includes('<f>'));
  assert.ok(!reportFileName(report, 'xlsx').includes('/'));
  assert.ok(!reportFileName(report, 'pdf').includes('..'));
});
