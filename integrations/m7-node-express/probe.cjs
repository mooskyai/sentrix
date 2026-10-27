'use strict';

const { randomUUID } = require('node:crypto');
const http = require('node:http');
const { stdin, stderr, stdout } = require('node:process');
const { NodeSDK } = require('@opentelemetry/sdk-node');
const { OTLPTraceExporter } = require('@opentelemetry/exporter-trace-otlp-proto');
const { resourceFromAttributes } = require('@opentelemetry/resources');

const SERVICE = 'm7-node-express-runtime';
const ENVIRONMENT = 'integration';
const RUN_ATTRIBUTE = 'sentrix.acceptance.run';

function validateOrigin(value) {
  let url;
  try { url = new URL(value); } catch { throw new Error('Invalid OTLP origin.'); }
  if (!['http:', 'https:'].includes(url.protocol) || !url.hostname ||
      url.username || url.password || url.pathname !== '/' || url.search || url.hash ||
      !url.port && value.endsWith(':')) {
    throw new Error('OTLP destination must be a clean HTTP(S) origin.');
  }
  if (url.protocol === 'http:' && !['localhost', '127.0.0.1', '[::1]', 'api'].includes(url.hostname)) {
    throw new Error('Nonlocal OTLP destinations must use HTTPS.');
  }
  return url.origin;
}

function parseArgs(args) {
  if (args.length !== 2 || args[0] !== '--base-url') {
    throw new Error('Use only --base-url <origin>; the key must come from stdin.');
  }
  return validateOrigin(args[1]);
}

async function readToken() {
  if (stdin.isTTY) throw new Error('Supply the project key on stdin, not as an argument.');
  let value = '';
  for await (const chunk of stdin) {
    value += chunk.toString('utf8');
    if (value.length > 8192) throw new Error('Project key input is too long.');
  }
  const token = value.trim();
  if (!token || !/^[\x21-\x7e]+$/.test(token)) {
    throw new Error('Missing or invalid project key on stdin.');
  }
  return token;
}

function makeExporter(origin, token) {
  const exporter = new OTLPTraceExporter({
    url: `${origin}/v1/traces`,
    headers: { Authorization: `Bearer ${token}` },
    timeoutMillis: 5000,
  });
  let accepted = 0;
  return {
    get accepted() { return accepted; },
    export(spans, callback) {
      exporter.export(spans, (result) => {
        if (result.code === 0) accepted += spans.length;
        callback(result);
      });
    },
    shutdown() { return exporter.shutdown(); },
    forceFlush() { return exporter.forceFlush(); },
  };
}

function localRequest(port) {
  return new Promise((resolve, reject) => {
    const request = http.get(`http://127.0.0.1:${port}/checkout`, { timeout: 6000 }, (response) => {
      const fragments = [];
      response.on('data', (fragment) => fragments.push(fragment));
      response.on('end', () => {
        if (response.statusCode !== 200) return reject(new Error('Express returned a non-200 status.'));
        try { resolve(JSON.parse(Buffer.concat(fragments).toString('utf8'))); }
        catch { reject(new Error('Express returned invalid JSON.')); }
      });
      response.on('error', reject);
    });
    request.on('timeout', () => request.destroy(new Error('Express request timeout.')));
    request.on('error', reject);
  });
}

async function run(origin, token) {
  const runId = randomUUID().replaceAll('-', '');
  const observedAt = new Date().toISOString();
  const exporter = makeExporter(origin, token);
  const sdk = new NodeSDK({
    resource: resourceFromAttributes({
      'service.name': SERVICE,
      'deployment.environment.name': ENVIRONMENT,
      [RUN_ATTRIBUTE]: runId,
    }),
    traceExporter: exporter,
    instrumentations: [],
  });
  sdk.start();
  // Require the Express application only after the SDK has started.
  const { createApp } = require('./app.cjs');
  const server = createApp(runId).listen(0, '127.0.0.1');
  let shutdownComplete = false;
  try {
    await new Promise((resolve, reject) => {
      if (server.listening) return resolve();
      server.once('listening', resolve);
      server.once('error', reject);
    });
    const result = await localRequest(server.address().port);
    if (!/^[a-f0-9]{32}$/.test(result.trace_id) || /^0+$/.test(result.trace_id)) {
      throw new Error('Express did not return an SDK trace ID.');
    }
    await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
    await sdk.shutdown();
    shutdownComplete = true;
    if (exporter.accepted !== 1) throw new Error('OTLP receiver did not confirm exactly one span.');
    return { runId, traceId: result.trace_id, observedAt };
  } finally {
    if (server.listening) server.close();
    if (!shutdownComplete) await sdk.shutdown().catch(() => undefined);
  }
}

async function main() {
  try {
    const origin = parseArgs(process.argv.slice(2));
    const token = await readToken();
    const result = await run(origin, token);
    stdout.write(`Real Express HTTP request and SDK OTLP export accepted.\nRun ID: ${result.runId}\nTrace ID: ${result.traceId}\nTime (UTC): ${result.observedAt}\nService: ${SERVICE} (environment: ${ENVIRONMENT})\nHTTP 200 is not durable proof. Run the independent Node read-back.\n`);
  } catch {
    stderr.write('Node Express probe failed. Check origin, API key, SDK and receiver; no persistence has been verified.\n');
    process.exitCode = 1;
  }
}

if (require.main === module) main();
module.exports = { validateOrigin, parseArgs, readToken, makeExporter, run, SERVICE, ENVIRONMENT, RUN_ATTRIBUTE };
