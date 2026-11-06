import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

test('pending expiry cannot erase a later queued login; a storage failure does not poison later writes', async () => {
  let value = 'old-token';
  let release;
  let failDelete = false;
  const gate = new Promise(resolve => { release = resolve; });
  globalThis.__aegisTestStorage = {
    getItemAsync: async () => value,
    setItemAsync: async (_, token) => { value = token; },
    deleteItemAsync: async () => { await gate; if (failDelete) throw new Error('storage failure'); value = null; },
  };
  try {
    const source = await readFile(new URL('../src/services/tokenStorage.ts', import.meta.url), 'utf8');
    const {outputText} = ts.transpileModule(source, {compilerOptions: {target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext}});
    const adapted = outputText.replace(/import \* as SecureStore from ['"]expo-secure-store['"];?/, 'const SecureStore = globalThis.__aegisTestStorage;');
    assert.notEqual(adapted, outputText);
    const {tokenStorage} = await import(`data:text/javascript;base64,${Buffer.from(adapted).toString('base64')}`);
    const cleared = tokenStorage.clear();
    const saved = tokenStorage.set('new-token');
    const read = tokenStorage.get();
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(value, 'old-token');
    release();
    await Promise.all([cleared, saved]);
    assert.equal(await read, 'new-token');
    failDelete = true;
    await assert.rejects(tokenStorage.clear(), /storage failure/);
    await tokenStorage.set('recovered-token');
    assert.equal(await tokenStorage.get(), 'recovered-token');
  } finally { delete globalThis.__aegisTestStorage; }
});
