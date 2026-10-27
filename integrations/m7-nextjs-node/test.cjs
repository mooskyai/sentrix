'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const http = require('node:http');
const path = require('node:path');
const { spawn } = require('node:child_process');
const protobuf = require('protobufjs');

const cwd = __dirname;
const fixture = path.join(cwd, 'probe.mjs');
const schema = protobuf.loadSync(path.join(cwd, '..', 'm7-node-express', 'proto', 'trace.proto'));
const Request = schema.lookupType('opentelemetry.proto.collector.trace.v1.ExportTraceServiceRequest');
const SECRET = 'PRIVATE_M733A_TEST_KEY';

function execute(args, input = `${SECRET}\n`) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [fixture, ...args], {
      cwd, stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true,
    });
    let out = '', err = '';
    const timeout = setTimeout(() => child.kill('SIGKILL'), 100000);
    child.stdout.on('data', (chunk) => { out += chunk.toString('utf8'); });
    child.stderr.on('data', (chunk) => { err += chunk.toString('utf8'); });
    child.on('error', reject);
    child.on('close', (code) => {
      clearTimeout(timeout);
      resolve({ code, out, err });
    });
    child.stdin.end(input);
  });
}

async function withReceiver(status, fn) {
  const received = [];
  const server = http.createServer((req, res) => {
    const chunks = [];
    let length = 0;
    req.on('data', (chunk) => {
      length += chunk.length;
      if (length > 2 * 1024 * 1024) req.destroy();
      else chunks.push(chunk);
    });
    req.on('end', () => {
      received.push({
        path: req.url, method: req.method, headers: req.headers,
        body: Buffer.concat(chunks),
      });
      res.writeHead(status, { 'Content-Type': 'application/x-protobuf' });
      res.end();
    });
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  try { await fn(`http://127.0.0.1:${server.address().port}`, received); }
  finally { await new Promise((resolve) => server.close(resolve)); }
}

function attributes(values) {
  return Object.fromEntries(values.map(({ key, value }) => [key, value.stringValue]));
}

test('real Next.js route exports one genuine OTLP protobuf SERVER span', { timeout: 115000 }, async () => {
  await withReceiver(200, async (origin, received) => {
    const result = await execute(['--base-url', origin]);
    assert.equal(result.code, 0, result.err);
    assert.ok(!`${result.out}${result.err}`.includes(SECRET));
    assert.equal(received.length, 1);
    const item = received[0];
    assert.equal(item.path, '/v1/traces');
    assert.equal(item.method, 'POST');
    assert.equal(item.headers.authorization, `Bearer ${SECRET}`);
    assert.match(item.headers['content-type'], /^application\/x-protobuf/);
    const decoded = Request.decode(item.body);
    assert.equal(decoded.resourceSpans.length, 1);
    const resource = decoded.resourceSpans[0];
    const resourceAttrs = attributes(resource.resource.attributes);
    assert.equal(resourceAttrs['service.name'], 'm7-nextjs-node-runtime');
    assert.equal(resourceAttrs['deployment.environment.name'], 'integration');
    assert.match(resourceAttrs['sentrix.acceptance.run'], /^[0-9a-f]{32}$/);
    const spans = resource.scopeSpans.flatMap((scope) => scope.spans);
    assert.equal(spans.length, 1);
    const span = spans[0];
    assert.equal(span.name, 'm7.next.checkout');
    assert.equal(span.kind, 2);
    assert.equal(span.traceId.length, 16);
    assert.equal(span.spanId.length, 8);
    assert.ok(BigInt(span.startTimeUnixNano.toString()) > 0n);
    assert.ok(BigInt(span.endTimeUnixNano.toString()) > BigInt(span.startTimeUnixNano.toString()));
    assert.equal(attributes(span.attributes)['http.route'], '/api/checkout');
    assert.equal(attributes(span.attributes)['http.request.method'], 'GET');
    assert.equal(attributes(span.attributes)['sentrix.acceptance.run'], resourceAttrs['sentrix.acceptance.run']);
    assert.match(result.out, new RegExp(`Run ID: ${resourceAttrs['sentrix.acceptance.run']}`));
    assert.ok(result.out.includes(`Trace ID: ${Buffer.from(span.traceId).toString('hex')}`));
  });
});

test('401 receiver rejection fails closed without printing the secret', { timeout: 115000 }, async () => {
  await withReceiver(401, async (origin) => {
    const result = await execute(['--base-url', origin]);
    assert.notEqual(result.code, 0);
    assert.ok(!`${result.out}${result.err}`.includes(SECRET));
    assert.ok(!result.out.includes('export accepted'));
  });
});

test('malformed destinations and CLI credentials are rejected', async () => {
  for (const origin of ['http://public.example', 'http://localhost:8000/v1',
    'https://u:p@example.org', 'http://api:8000/?key=bad', 'file:///tmp/x']) {
    const result = await execute(['--base-url', origin]);
    assert.notEqual(result.code, 0);
    assert.ok(!`${result.out}${result.err}`.includes(SECRET));
  }
  const result = await execute(['--api-key', SECRET]);
  assert.notEqual(result.code, 0);
  assert.ok(!`${result.out}${result.err}`.includes(SECRET));
});

test('missing stdin credential rejects before attempting Next.js request', async () => {
  await withReceiver(200, async (origin, received) => {
    const result = await execute(['--base-url', origin], '');
    assert.notEqual(result.code, 0);
    assert.equal(received.length, 0);
  });
});
