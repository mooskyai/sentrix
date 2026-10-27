import { randomUUID } from 'node:crypto';
import { spawn } from 'node:child_process';
import { createServer } from 'node:net';
import http from 'node:http';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { stdin, stdout, stderr } from 'node:process';
import { validateOrigin, SERVICE, ENVIRONMENT } from './lib/tracing.mjs';

const root = path.dirname(fileURLToPath(import.meta.url));

export function parseArgs(args) {
  if (args.length !== 2 || args[0] !== '--base-url') {
    throw new Error('Only --base-url <origin> is supported. Supply the key on stdin.');
  }
  return validateOrigin(args[1]);
}

async function readToken() {
  if (stdin.isTTY) throw new Error('Supply the key on stdin, not the CLI.');
  let value = '';
  for await (const chunk of stdin) {
    value += chunk.toString('utf8');
    if (value.length > 8192) throw new Error('Project key input is too long.');
  }
  const token = value.trim();
  if (!token || !/^[\x21-\x7e]+$/.test(token)) throw new Error('Missing project key.');
  return token;
}

async function freePort() {
  const server = createServer();
  await new Promise((resolve, reject) => server.once('error', reject).listen(0, '127.0.0.1', resolve));
  const port = server.address().port;
  await new Promise((resolve) => server.close(resolve));
  return port;
}

function request(port, pathname) {
  return new Promise((resolve, reject) => {
    const req = http.get(`http://127.0.0.1:${port}${pathname}`, { timeout: 15000 }, (res) => {
      const chunks = [];
      let length = 0;
      res.on('data', (chunk) => {
        length += chunk.length;
        if (length > 65536) res.destroy(new Error('Next response too large.'));
        else chunks.push(chunk);
      });
      res.on('end', () => resolve({ status: res.statusCode, text: Buffer.concat(chunks).toString('utf8') }));
      res.on('error', reject);
    });
    req.on('timeout', () => req.destroy(new Error('Next request timeout.')));
    req.on('error', reject);
  });
}

async function ready(port, child) {
  const deadline = Date.now() + 65000;
  while (Date.now() < deadline) {
    if (child.exitCode !== null || child.signalCode !== null) throw new Error('Next server terminated.');
    try {
      const result = await request(port, '/');
      if (result.status === 200) return;
    } catch { /* Server is still starting. */ }
    await new Promise((resolve) => setTimeout(resolve, 400));
  }
  throw new Error('Next server did not become ready.');
}

export async function run(origin, token) {
  const runId = randomUUID().replaceAll('-', '');
  const observedAt = new Date().toISOString();
  const port = await freePort();
  const child = spawn(process.execPath, [path.join(root, 'node_modules', 'next', 'dist', 'bin', 'next'),
    'dev', '--hostname', '127.0.0.1', '--port', String(port)], {
    cwd: root,
    env: {
      ...process.env,
      NEXT_TELEMETRY_DISABLED: '1',
      SENTRIX_API_KEY: token,
      SENTRIX_OTLP_BASE_URL: origin,
      SENTRIX_ACCEPTANCE_RUN: runId,
    },
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  });
  // Never relay child output: it might contain environment-derived diagnostics.
  child.stdout.resume();
  child.stderr.resume();
  try {
    await ready(port, child);
    const result = await request(port, '/api/checkout');
    if (result.status !== 200) throw new Error('Next checkout rejected the SDK export.');
    const payload = JSON.parse(result.text);
    if (payload.run_id !== runId || payload.service !== SERVICE ||
        payload.environment !== ENVIRONMENT || !/^[0-9a-f]{32}$/.test(payload.trace_id) ||
        /^0+$/.test(payload.trace_id)) throw new Error('Next runtime result did not match the SDK run.');
    return { runId, traceId: payload.trace_id, observedAt };
  } finally {
    // A short-lived local fixture, not a production Next.js service.
    child.kill('SIGTERM');
    // Limit cleanup wait. The parent only manages the child it created.
    await Promise.race([
      new Promise((resolve) => child.once('close', resolve)),
      new Promise((resolve) => setTimeout(resolve, 1500)),
    ]);
  }
}

async function main() {
  try {
    const origin = parseArgs(process.argv.slice(2));
    const token = await readToken();
    const { runId, traceId, observedAt } = await run(origin, token);
    stdout.write(`Real Next.js App Router HTTP request and SDK OTLP export accepted.\nRun ID: ${runId}\nTrace ID: ${traceId}\nTime (UTC): ${observedAt}\nService: ${SERVICE} (environment: ${ENVIRONMENT})\nHTTP 200 is not durable proof. Run independent Next.js ClickHouse read-back.\n`);
  } catch {
    stderr.write('Next.js runtime probe NOT VERIFIED. Check Node, dependencies, endpoint and server-side key.\n');
    process.exitCode = 1;
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main();
