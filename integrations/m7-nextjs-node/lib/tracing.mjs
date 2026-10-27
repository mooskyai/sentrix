import { SpanKind } from '@opentelemetry/api';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-proto';
import { resourceFromAttributes } from '@opentelemetry/resources';
import { NodeTracerProvider } from '@opentelemetry/sdk-trace-node';
import { SimpleSpanProcessor } from '@opentelemetry/sdk-trace-base';

export const SERVICE = 'm7-nextjs-node-runtime';
export const ENVIRONMENT = 'integration';
export const RUN_ATTRIBUTE = 'sentrix.acceptance.run';
export const SPAN_NAME = 'm7.next.checkout';
const STORAGE = Symbol.for('sentrix.m733a.private-tracer');

export function validateOrigin(value) {
  let url;
  try { url = new URL(value); } catch { throw new Error('Invalid OTLP origin.'); }
  if (!['http:', 'https:'].includes(url.protocol) || !url.hostname || url.username ||
      url.password || url.pathname !== '/' || url.search || url.hash ||
      (!url.port && value.endsWith(':'))) {
    throw new Error('OTLP destination must be a clean HTTP(S) origin.');
  }
  if (url.protocol === 'http:' && !['localhost', '127.0.0.1', '[::1]', 'api'].includes(url.hostname)) {
    throw new Error('Nonlocal OTLP destinations must use HTTPS.');
  }
  return url.origin;
}

export function initialize() {
  if (globalThis[STORAGE]) return globalThis[STORAGE];
  if (process.env.NEXT_RUNTIME === 'edge') throw new Error('Node runtime required.');
  const runId = process.env.SENTRIX_ACCEPTANCE_RUN || '';
  const token = process.env.SENTRIX_API_KEY || '';
  if (!/^[0-9a-f]{32}$/.test(runId) || /^0+$/.test(runId) ||
      !/^[\x21-\x7e]+$/.test(token) || token.length > 8192) {
    throw new Error('Server-side acceptance configuration is missing.');
  }
  const origin = validateOrigin(process.env.SENTRIX_OTLP_BASE_URL || '');
  const exporter = new OTLPTraceExporter({
    url: `${origin}/v1/traces`,
    headers: { Authorization: `Bearer ${token}` },
    timeoutMillis: 8000,
  });
  const pending = new Map();
  const trackedExporter = {
    export(spans, callback) {
      exporter.export(spans, (result) => {
        for (const span of spans) {
          const id = span.spanContext().traceId;
          const item = pending.get(id);
          if (item) {
            if (result.code === 0 && spans.length === 1) item.resolve();
            else item.reject(new Error('OTLP receiver did not accept the single span.'));
          }
        }
        callback(result);
      });
    },
    forceFlush() { return exporter.forceFlush(); },
    shutdown() { return exporter.shutdown(); },
  };
  // Use a dedicated tracer provider: Next.js may own the global OTel provider.
  // This fixture proves a manually instrumented Next server request, not auto-instrumentation.
  const provider = new NodeTracerProvider({
    resource: resourceFromAttributes({
      'service.name': SERVICE,
      'deployment.environment.name': ENVIRONMENT,
      [RUN_ATTRIBUTE]: runId,
    }),
    spanProcessors: [new SimpleSpanProcessor(trackedExporter)],
  });
  const state = { tracer: provider.getTracer('sentrix.m7.next.runtime'), provider, pending, runId };
  globalThis[STORAGE] = state;
  return state;
}

export async function instrumentCheckout() {
  const state = initialize();
  const { tracer, pending, runId } = state;
  let resolve;
  let reject;
  const ack = new Promise((ok, fail) => { resolve = ok; reject = fail; });
  const span = tracer.startSpan(SPAN_NAME, {
    kind: SpanKind.SERVER,
    attributes: {
      [RUN_ATTRIBUTE]: runId,
      'http.request.method': 'GET',
      'http.route': '/api/checkout',
    },
  });
  const traceId = span.spanContext().traceId;
  if (!/^[a-f0-9]{32}$/.test(traceId) || /^0+$/.test(traceId) || pending.has(traceId)) {
    span.end();
    throw new Error('Could not create one real SDK span.');
  }
  pending.set(traceId, { resolve, reject });
  let timer;
  try {
    span.end();
    await Promise.race([
      ack,
      new Promise((_, fail) => {
        timer = setTimeout(() => fail(new Error('OTLP export acknowledgement timed out.')), 12000);
      }),
    ]);
    return { trace_id: traceId, run_id: runId, service: SERVICE, environment: ENVIRONMENT };
  } finally {
    clearTimeout(timer);
    pending.delete(traceId);
  }
}
