'use strict';

// Loaded only AFTER the NodeSDK starts in probe.cjs. This is real Express,
// manually instrumented (not proof of automatic Express instrumentation).
const express = require('express');
const { trace, SpanKind } = require('@opentelemetry/api');

function createApp(runId) {
  const app = express();
  app.get('/checkout', (_request, response) => {
    trace.getTracer('sentrix.m7.node.runtime').startActiveSpan(
      'm7.node.checkout',
      {
        kind: SpanKind.SERVER,
        attributes: {
          'sentrix.acceptance.run': runId,
          'http.request.method': 'GET',
          'http.route': '/checkout',
        },
      },
      (span) => {
        try {
          response.status(200).json({ trace_id: span.spanContext().traceId });
        } finally {
          span.end();
        }
      },
    );
  });
  return app;
}

module.exports = { createApp };
