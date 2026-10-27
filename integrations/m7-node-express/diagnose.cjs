'use strict';

// M7.3.2 bounded live diagnostic: intercept exactly one SDK OTLP request on
// loopback, forward the SAME bytes to Sentrix, inspect them using the backend's
// production Python decoder and then do an independent ClickHouse read-back.
// Bytes and the key exist only in memory/stdin; neither is saved or printed.
const http = require('node:http');
const https = require('node:https');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { stdout, stderr } = require('node:process');
const protobuf = require('protobufjs');
const { parseArgs, readToken, run } = require('./probe.cjs');

const MAX_BODY = 2 * 1024 * 1024;
const root = path.resolve(__dirname, '..', '..');
const schema = protobuf.loadSync(path.join(__dirname, 'proto', 'trace.proto'));
const Request = schema.lookupType('opentelemetry.proto.collector.trace.v1.ExportTraceServiceRequest');

function invokeDocker(args, input) {
  return new Promise((resolve, reject) => {
    const child = spawn('docker', ['compose', 'exec', '-T', 'api', '/opt/venv/bin/python', ...args], {
      cwd: root, stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true,
    });
    const captured = { out: '', err: '' };
    // Our two trusted backend scripts have intentionally sanitized output.
    for (const [stream, field] of [[child.stdout, 'out'], [child.stderr, 'err']]) {
      stream.on('data', (bytes) => { captured[field] += bytes.toString('utf8').slice(0, 2048); });
    }
    child.on('error', reject);
    child.on('close', (code) => resolve({ code, ...captured }));
    child.stdin.on('error', () => {});
    child.stdin.end(input);
  });
}

async function forward(url, body, key) {
  return new Promise((resolve, reject) => {
    const transport = url.protocol === 'https:' ? https : http;
    const request = transport.request(url, {
      method: 'POST', timeout: 6000,
      headers: {
        Authorization: `Bearer ${key}`,
        'Content-Type': 'application/x-protobuf',
        'Content-Length': String(body.length),
      },
    }, (response) => {
      const chunks = [];
      let bytes = 0;
      response.on('data', (part) => {
        bytes += part.length;
        if (bytes > 65536) response.destroy(new Error('OTLP response too large.'));
        else chunks.push(part);
      });
      response.on('end', () => resolve({
        status: response.statusCode,
        body: Buffer.concat(chunks),
        type: response.headers['content-type'] || 'application/x-protobuf',
      }));
      response.on('error', reject);
    });
    request.on('timeout', () => request.destroy(new Error('OTLP receiver timeout.')));
    request.on('error', reject);
    request.end(body);
  });
}

async function liveDiagnostic(origin, token) {
  const upstream = new URL(`${origin}/v1/traces`);
  let payload = null;
  let received = 0;
  const relay = http.createServer((req, res) => {
    ++received;
    if (received !== 1 || req.method !== 'POST' || req.url !== '/v1/traces' ||
        req.headers.authorization !== `Bearer ${token}` ||
        !/^application\/x-protobuf(?:;|$)/.test(req.headers['content-type'] || '') ||
        req.headers['content-encoding']) {
      res.writeHead(400); res.end(); return;
    }
    const chunks = [];
    let size = 0;
    req.on('data', (part) => {
      size += part.length;
      if (size > MAX_BODY) req.destroy(new Error('Request exceeded bound.'));
      else chunks.push(part);
    });
    req.on('end', async () => {
      try {
        payload = Buffer.concat(chunks);
        // Not a mock receiver: the original bytes go to the actual Sentrix API.
        const reply = await forward(upstream, payload, token);
        res.writeHead(reply.status, { 'Content-Type': reply.type });
        res.end(reply.body);
      } catch {
        res.writeHead(502); res.end();
      }
    });
    req.on('error', () => { if (!res.writableEnded) res.destroy(); });
  });
  await new Promise((resolve, reject) => {
    relay.once('error', reject);
    relay.listen(0, '127.0.0.1', resolve);
  });
  let receipt;
  try {
    receipt = await run(`http://127.0.0.1:${relay.address().port}`, token);
  } finally {
    await new Promise((resolve) => relay.close(resolve));
  }
  if (received !== 1 || !payload) throw new Error('No single real SDK OTLP request captured.');
  const decoded = Request.decode(payload);
  const resources = decoded.resourceSpans || [];
  const spans = resources.flatMap((resource) =>
    (resource.scopeSpans || []).flatMap((scope) => scope.spans || []));
  const ids = spans.map((span) => Buffer.from(span.traceId).toString('hex'));
  if (resources.length !== 1 || spans.length !== 1 || ids[0] !== receipt.traceId) {
    throw new Error('Captured protobuf does not match the real Express request.');
  }
  stdout.write('SDK OTLP request forwarded to Sentrix: 1 resource group, 1 nested span; HTTP 200.\n');
  const decodedByDjango = await invokeDocker([
    '-m', 'scripts.m7_node_wire_inspect', '--run-id', receipt.runId,
    '--trace-id', receipt.traceId,
  ], payload);
  if (decodedByDjango.code !== 0) {
    stdout.write('Django canonical wire inspection FAILED.\n');
    stderr.write(decodedByDjango.err.slice(0, 1024));
    throw new Error('Django decoder/normalizer did not recognize the live SDK bytes.');
  }
  stdout.write(decodedByDjango.out);
  const readback = await invokeDocker([
    '-m', 'scripts.m7_node_readback', '--run-id', receipt.runId,
    '--trace-id', receipt.traceId, '--time', receipt.observedAt,
  ], `${token}\n`);
  stdout.write(`Run ID: ${receipt.runId}\nTrace ID: ${receipt.traceId}\nTime (UTC): ${receipt.observedAt}\n`);
  if (readback.code !== 0) {
    stdout.write('READ-BACK FAILED: real SDK span not independently verified in ClickHouse.\n');
    stderr.write(readback.err.slice(0, 1024));
    throw new Error('Node SDK persistence is still not verified.');
  }
  stdout.write(readback.out);
  stdout.write('PASS: real Node Express SDK span was independently verified in ClickHouse.\n');
}

async function main() {
  try {
    const origin = parseArgs(process.argv.slice(2));
    const token = await readToken();
    await liveDiagnostic(origin, token);
  } catch {
    stderr.write('M7.3.2 live diagnostic failed. Review the sanitized stage output; no acceptance claimed.\n');
    process.exitCode = 1;
  }
}

if (require.main === module) main();
module.exports = { liveDiagnostic };
