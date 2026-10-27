'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const { spawn } = require('node:child_process');
const path = require('node:path');
const protobuf = require('protobufjs');
const { validateOrigin } = require('./probe.cjs');

const fixture = path.join(__dirname, 'probe.cjs');
const schema = protobuf.loadSync(path.join(__dirname, 'proto', 'trace.proto'));
const Request = schema.lookupType('opentelemetry.proto.collector.trace.v1.ExportTraceServiceRequest');
const SECRET = 'PRIVATE_M7_TEST_KEY';

function execute(args, stdinValue = `${SECRET}\n`) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [fixture, ...args], { cwd: __dirname, stdio: ['pipe', 'pipe', 'pipe'] });
    let out = '', err = '';
    const timer = setTimeout(() => child.kill('SIGKILL'), 12000);
    child.stdout.on('data', (data) => { out += data.toString(); });
    child.stderr.on('data', (data) => { err += data.toString(); });
    child.on('error', reject);
    child.on('close', (code) => { clearTimeout(timer); resolve({ code, out, err }); });
    child.stdin.end(stdinValue);
  });
}

async function withReceiver(status, fn) {
  const received = [];
  const server = http.createServer((req, res) => {
    const body = [];
    req.on('data', (chunk) => body.push(chunk));
    req.on('end', () => {
      received.push({ path: req.url, method: req.method, headers: req.headers, body: Buffer.concat(body) });
      res.writeHead(status, { 'Content-Type': 'application/x-protobuf' });
      res.end();
    });
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  try { await fn(`http://127.0.0.1:${server.address().port}`, received); }
  finally { await new Promise((resolve) => server.close(resolve)); }
}

function attrs(entries) {
  return Object.fromEntries(entries.map(({ key, value }) => [key, value.stringValue]));
}

test('actual Express process exports one genuine protobuf server span', async () => {
  await withReceiver(200, async (origin, received) => {
    const result = await execute(['--base-url', origin]);
    assert.equal(result.code, 0, result.err);
    assert.ok(!`${result.out}${result.err}`.includes(SECRET));
    assert.equal(received.length, 1);
    assert.equal(received[0].path, '/v1/traces');
    assert.equal(received[0].method, 'POST');
    assert.equal(received[0].headers.authorization, `Bearer ${SECRET}`);
    assert.match(received[0].headers['content-type'], /^application\/x-protobuf/);
    const decoded = Request.decode(received[0].body);
    assert.equal(decoded.resourceSpans.length, 1);
    const resource = decoded.resourceSpans[0];
    const labels = attrs(resource.resource.attributes);
    assert.equal(labels['service.name'], 'm7-node-express-runtime');
    assert.equal(labels['deployment.environment.name'], 'integration');
    assert.match(labels['sentrix.acceptance.run'], /^[a-f0-9]{32}$/);
    const spans = resource.scopeSpans.flatMap((scope) => scope.spans);
    assert.equal(spans.length, 1);
    const span = spans[0];
    assert.equal(span.name, 'm7.node.checkout');
    assert.equal(span.kind, 2); // OTLP SPAN_KIND_SERVER
    // The real wire format encodes both timestamps as fixed64, not uint64 varints.
    const spanType = schema.lookupType('opentelemetry.proto.collector.trace.v1.Span');
    assert.equal(spanType.fields.startTimeUnixNano.type, 'fixed64');
    assert.equal(spanType.fields.endTimeUnixNano.type, 'fixed64');
    assert.ok(BigInt(span.startTimeUnixNano.toString()) > 0n);
    assert.ok(BigInt(span.endTimeUnixNano.toString()) > BigInt(span.startTimeUnixNano.toString()));
    assert.equal(span.traceId.length, 16);
    assert.equal(span.spanId.length, 8);
    assert.equal(attrs(span.attributes)['http.request.method'], 'GET');
    assert.equal(attrs(span.attributes)['http.route'], '/checkout');
    assert.equal(attrs(span.attributes)['sentrix.acceptance.run'], labels['sentrix.acceptance.run']);
    assert.match(result.out, new RegExp(`Run ID: ${labels['sentrix.acceptance.run']}`));
    assert.ok(result.out.includes(`Trace ID: ${Buffer.from(span.traceId).toString('hex')}`));
  });
});

test('receiver rejection fails closed without printing the key', async () => {
  await withReceiver(401, async (origin) => {
    const result = await execute(['--base-url', origin]);
    assert.notEqual(result.code, 0);
    assert.ok(!`${result.out}${result.err}`.includes(SECRET));
    assert.ok(!result.out.includes('export accepted'));
  });
});

test('prohibited URLs and CLI secrets are rejected', async () => {
  for (const value of ['http://public.example', 'http://localhost:8000/v1', 'https://u:p@example.org', 'http://api:8000/?token=bad', 'file:///tmp/x']) {
    assert.throws(() => validateOrigin(value));
    const result = await execute(['--base-url', value]);
    assert.notEqual(result.code, 0);
    assert.ok(!`${result.out}${result.err}`.includes(SECRET));
  }
  const argKey = await execute(['--api-key', SECRET]);
  assert.notEqual(argKey.code, 0);
  assert.ok(!`${argKey.out}${argKey.err}`.includes(SECRET));
});

test('missing stdin key fails without contacting receiver', async () => {
  await withReceiver(200, async (origin, received) => {
    const result = await execute(['--base-url', origin], '');
    assert.notEqual(result.code, 0);
    assert.equal(received.length, 0);
  });
});
