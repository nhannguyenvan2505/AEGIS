import { readFile } from 'node:fs/promises';
import { Buffer } from 'node:buffer';
import ts from 'typescript';
const urls = new Map();
export async function moduleUrl(url) {
  const key = url.href;
  if (urls.has(key)) return urls.get(key);
  const source = await readFile(url, 'utf8');
  let { outputText } = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } });
  for (const match of [...outputText.matchAll(/from ['"]([^'"]+)['"]/g)]) {
    if (match[1].startsWith('.')) outputText = outputText.replace(match[0], `from '${await moduleUrl(new URL(match[1] + '.ts', url))}'`);
  }
  const value = `data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`;
  urls.set(key, value); return value;
}
export const controllerModule = await import(await moduleUrl(new URL('../src/features/followup/controller.ts', import.meta.url)));
export const apiModule = await import(await moduleUrl(new URL('../src/services/api.ts', import.meta.url)));
export const clientModule = await import(await moduleUrl(new URL('../src/features/followup/client.ts', import.meta.url)));
