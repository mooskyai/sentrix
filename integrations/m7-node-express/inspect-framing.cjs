"use strict";

// Read-only local framing proof: a fake key and one loopback OTLP receiver.
// Never prints Authorization or protobuf bytes and never calls Sentrix.
const http = require('node:http');
const { run } = require('./probe.cjs');

async function main() {
  let seen = 0;
  let framing = null;
  const server = http.createServer((request, response) => {
    seen += 1;
    let size = 0;
    request.on('data', (chunk) => { size += chunk.length; });
    request.on('end', () => {
      if (request.method !== 'POST' || request.url !== '/v1/traces' || size === 0) {
        response.writeHead(400); response.end(); return;
      }
      framing = {
        encoding: request.headers['transfer-encoding'] || 'absent',
        length: request.headers['content-length'] || 'absent',
        bytes: size,
      };
      response.writeHead(200, { 'Content-Type': 'application/x-protobuf' });
      response.end();
    });
  });
  await new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', resolve);
  });
  try {
    await run(`http://127.0.0.1:${server.address().port}`, 'FAKE_LOCAL_KEY');
    if (seen !== 1 || !framing) throw new Error('No single real SDK export captured.');
    process.stdout.write(`Node SDK Transfer-Encoding: ${framing.encoding}\n`);
    process.stdout.write(`Node SDK Content-Length: ${framing.length}\n`);
    process.stdout.write(`Nonempty protobuf body bytes: ${framing.bytes}\n`);
    process.stdout.write('Local fake receiver only; no Sentrix persistence claim.\n');
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
}

main().catch(() => {
  process.stderr.write('Local SDK request framing inspection failed.\n');
  process.exitCode = 1;
});
