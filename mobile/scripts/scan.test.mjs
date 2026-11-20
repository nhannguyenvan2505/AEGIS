import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';

const code = ts.transpileModule(await readFile(new URL('../src/features/diagnosis/scanHelpers.ts', import.meta.url), 'utf8'),
  { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } }).outputText;
const { summarizeDetections, validateScanImage, analysisImageSource, scanDate } = await import('data:text/javascript;base64,' + Buffer.from(code).toString('base64'));

test('scan rejects unsuitable uploads and accepts the existing API boundaries', () => {
  const image = { width: 4000, height: 4000, mimeType: 'image/jpeg', fileSize: 8 * 1024 * 1024, type: 'image' };
  assert.equal(validateScanImage(image), '');
  for (const change of [{ width: 4001 }, { height: 31 }, { width: NaN }, { type: 'video' },
    { mimeType: 'image/heic' }, { mimeType: 'image/gif' }, { fileSize: image.fileSize + 1 }]) {
    assert.notEqual(validateScanImage({ ...image, ...change }), '', JSON.stringify(change));
  }
  assert.equal(validateScanImage({ width: 32, height: 32, mimeType: null, type: null }), '');
});

test('AI summary picks strongest real detection and retains separate disease groups', () => {
  const result = { detections: [{ disease: 'rice_blast', confidence: .4 }, { disease: 'brown_spot', confidence: .7 },
    { disease: 'rice_blast', confidence: .91 }, { disease: 'new_model_label', confidence: .2 }] };
  assert.deepEqual(summarizeDetections(result), [{ name: 'Đạo ôn lá', confidence: .91, count: 2 },
    { name: 'Đốm nâu', confidence: .7, count: 1 }, { name: 'new model label', confidence: .2, count: 1 }]);
  assert.deepEqual(summarizeDetections({ detections: [] }), []);
  assert.equal(result.detections[0].confidence, .4);
});

test('history images keep authentication on configured API and encode the resource ID', () => {
  const previous = process.env.EXPO_PUBLIC_API_URL;
  try {
    process.env.EXPO_PUBLIC_API_URL = 'http://127.0.0.1:5000/api/';
    assert.deepEqual(analysisImageSource('other/../id', 'private-token'), {
      uri: 'http://127.0.0.1:5000/api/disease/analyses/other%2F..%2Fid/image', headers: { Authorization: 'Bearer private-token' },
    });
    delete process.env.EXPO_PUBLIC_API_URL;
    assert.equal(analysisImageSource('id', 'private-token'), undefined);
    assert.equal(scanDate('invalid date'), 'Chưa có thời gian');
  } finally {
    if (previous === undefined) delete process.env.EXPO_PUBLIC_API_URL;
    else process.env.EXPO_PUBLIC_API_URL = previous;
  }
});
