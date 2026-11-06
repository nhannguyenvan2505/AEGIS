// Sanitized Newman summary only; never serialize headers, bodies or environment.
const fs = require('node:fs');
const path = require('node:path');
const newman = require('./tools/node_modules/newman');
const [base, output] = process.argv.slice(2);
let url;
try { url = new URL(base); } catch { throw new Error('Loopback URL required'); }
if (url.protocol !== 'http:' || !['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname) || url.username || url.password || url.pathname !== '/' || url.search || url.hash || !output || fs.existsSync(output)) {
  throw new Error('Use a loopback HTTP origin and a new summary file');
}
const collection = JSON.parse(fs.readFileSync(path.join(__dirname, '../postman/AEGIS-Pilot-Raw.postman_collection.json'), 'utf8'));
newman.run({ collection, environment: { values: [{ key: 'base_url', value: url.origin, enabled: true }] },
  reporters: [], timeoutRequest: 10000, bail: true }, (error, summary) => {
  if (error || !summary) { process.stderr.write('Pilot raw collection could not complete\n'); process.exitCode = 2; return; }
  const report = { software_fixture_only: true, checkpoint_loaded: false, model_inference_performed: false,
    requests: summary.run.stats.requests, assertions: summary.run.stats.assertions,
    failures: summary.run.failures.map(f => ({ item: f.source?.name || 'unknown', name: f.error?.name || 'failure' })),
    executions: summary.run.executions.map(e => ({ name: e.item.name, status: e.response?.code || null })) };
  fs.writeFileSync(output, JSON.stringify(report, null, 2) + '\n', { flag: 'wx' });
  process.stdout.write(JSON.stringify({ requests: report.requests.total, assertions: report.assertions.total, failures: report.failures.length }) + '\n');
  process.exitCode = report.failures.length ? 1 : 0;
});
