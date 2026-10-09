import { useMemo, useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { getTrace } from "../api/resources";
import type { TraceSpan } from "../types";

const RANGE_MS = {
  "1h": 60 * 60 * 1000,
  "6h": 6 * 60 * 60 * 1000,
  "24h": 24 * 60 * 60 * 1000,
  "7d": 7 * 24 * 60 * 60 * 1000,
} as const;

type TraceTimeRange = keyof typeof RANGE_MS;

const TRACE_ID_PATTERN = /^[0-9a-f]{32}$/;
const ZERO_TRACE_ID = "0".repeat(32);

function isTraceId(value: string): boolean {
  return TRACE_ID_PATTERN.test(value) && value !== ZERO_TRACE_ID;
}

function formatUtcTimestamp(value: string): string {
  return `${new Date(value).toLocaleString(undefined, {
    timeZone: "UTC",
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  })} UTC`;
}

function formatDuration(durationNs: number): string {
  if (durationNs < 1_000) return `${durationNs} ns`;
  if (durationNs < 1_000_000) return `${(durationNs / 1_000).toFixed(2)} µs`;
  if (durationNs < 1_000_000_000) return `${(durationNs / 1_000_000).toFixed(2)} ms`;
  return `${(durationNs / 1_000_000_000).toFixed(3)} s`;
}

function formatAttributes(attributes: Record<string, string>): string {
  const entries = Object.entries(attributes).sort(([left], [right]) => left.localeCompare(right));
  if (entries.length === 0) return "—";
  return entries.map(([key, value]) => `${key}=${value}`).join(", ");
}

function spanKind(value: number): string {
  return {
    0: "unspecified",
    1: "internal",
    2: "server",
    3: "client",
    4: "producer",
    5: "consumer",
  }[value] ?? `unknown:${value}`;
}

function spanStatus(value: number): string {
  return { 0: "unset", 1: "ok", 2: "error" }[value] ?? `unknown:${value}`;
}

function rangeForWindow(start: string | null, end: string | null): TraceTimeRange {
  if (!start || !end) return "1h";
  const duration = Date.parse(end) - Date.parse(start);
  const match = (Object.entries(RANGE_MS) as [TraceTimeRange, number][]).find(
    ([, milliseconds]) => Math.abs(milliseconds - duration) < 1_000,
  );
  return match?.[0] ?? "1h";
}

function traceWindow(range: TraceTimeRange, anchorMs: number) {
  return {
    start: new Date(anchorMs - RANGE_MS[range]).toISOString(),
    end: new Date(anchorMs).toISOString(),
  };
}

function parentLabel(span: TraceSpan, returnedSpanIds: ReadonlySet<string>): string {
  if (!span.parent_span_id) return "root";
  if (returnedSpanIds.has(span.parent_span_id)) return span.parent_span_id;
  return `${span.parent_span_id} (parent not returned)`;
}

export function TraceExplorer({ projectId }: { projectId: string }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTraceId = (searchParams.get("trace_id") ?? "").trim().toLowerCase();
  const [traceInput, setTraceInput] = useState(activeTraceId);
  const [range, setRange] = useState<TraceTimeRange>(() =>
    rangeForWindow(searchParams.get("start"), searchParams.get("end")),
  );
  const [anchorMs, setAnchorMs] = useState(() => Date.now());
  const [inputError, setInputError] = useState<string | null>(null);

  const localWindow = useMemo(() => traceWindow(range, anchorMs), [anchorMs, range]);
  const window = {
    start: searchParams.get("start") ?? localWindow.start,
    end: searchParams.get("end") ?? localWindow.end,
  };
  const validActiveTrace = isTraceId(activeTraceId);

  const traceQuery = useQuery({
    queryKey: ["trace-detail", projectId, activeTraceId, window.start, window.end, 500],
    queryFn: () => getTrace(projectId, activeTraceId, { ...window, limit: 500 }),
    enabled: validActiveTrace,
    retry: false,
  });

  function setActiveWindow(nextRange: TraceTimeRange, nextAnchorMs: number) {
    setRange(nextRange);
    setAnchorMs(nextAnchorMs);
    if (!validActiveTrace) return;
    const nextWindow = traceWindow(nextRange, nextAnchorMs);
    setSearchParams({ trace_id: activeTraceId, ...nextWindow });
  }

  function lookupTrace(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = traceInput.trim().toLowerCase();
    if (!isTraceId(normalized)) {
      setInputError("Trace ID must be a non-zero 32-character hexadecimal identifier.");
      return;
    }
    const now = Date.now();
    const nextWindow = traceWindow(range, now);
    setInputError(null);
    setAnchorMs(now);
    setTraceInput(normalized);
    setSearchParams({ trace_id: normalized, ...nextWindow });
  }

  function clearTrace() {
    setTraceInput("");
    setInputError(null);
    setAnchorMs(Date.now());
    setSearchParams({});
  }

  const spans = traceQuery.data?.spans ?? [];
  const returnedSpanIds = new Set<string>(
    spans.flatMap((span) => (span.span_id ? [span.span_id] : [])),
  );
  const services = new Set<string>(spans.map((span) => span.service_name).filter(Boolean));
  const traceDurationMs = spans.length
    ? Math.max(
        0,
        Math.max(...spans.map((span) => Date.parse(span.end_time))) -
          Math.min(...spans.map((span) => Date.parse(span.start_time))),
      )
    : 0;

  return (
    <div className="trace-explorer">
      <form className="trace-controls" onSubmit={lookupTrace}>
        <label className="trace-id-field">
          <span>Trace ID</span>
          <input
            aria-label="Trace ID"
            className="mono"
            value={traceInput}
            onChange={(event) => setTraceInput(event.target.value)}
            placeholder="32 hexadecimal characters"
          />
        </label>
        <label>
          <span>Time range</span>
          <select
            aria-label="Trace time range"
            value={range}
            onChange={(event) => setActiveWindow(event.target.value as TraceTimeRange, Date.now())}
          >
            <option value="1h">Last 1 hour</option>
            <option value="6h">Last 6 hours</option>
            <option value="24h">Last 24 hours</option>
            <option value="7d">Last 7 days</option>
          </select>
        </label>
        <div className="trace-actions">
          <button className="button" type="submit">Lookup trace</button>
          <button
            className="button secondary"
            type="button"
            disabled={!validActiveTrace}
            onClick={() => setActiveWindow(range, Date.now())}
          >
            Refresh
          </button>
          <button className="button secondary" type="button" onClick={clearTrace}>Clear</button>
        </div>
      </form>

      {inputError ? <p className="error trace-state">{inputError}</p> : null}
      {!activeTraceId ? (
        <div className="empty-feature trace-state">
          <strong>Enter a trace ID to inspect project spans.</strong>
          <p className="muted">
            Trace lookup is bounded to the selected UTC window and remains authorized by project membership.
          </p>
        </div>
      ) : null}
      {activeTraceId && !validActiveTrace ? (
        <p className="error trace-state">The URL contains an invalid trace ID.</p>
      ) : null}
      {validActiveTrace && traceQuery.isPending ? (
        <p className="muted trace-state">Loading trace spans…</p>
      ) : null}
      {traceQuery.isError ? (
        <p className="error trace-state">Unable to load trace: {traceQuery.error.message}</p>
      ) : null}
      {traceQuery.data?.spans.length === 0 ? (
        <div className="empty-feature trace-state">
          <strong>No spans matched this trace in the selected window.</strong>
          <p className="muted">Try a wider time range or verify the trace ID.</p>
        </div>
      ) : null}
      {traceQuery.data?.truncated ? (
        <p className="notice trace-state">
          This trace reached the 500-span browser limit. Parent spans may be outside the returned subset.
        </p>
      ) : null}

      {traceQuery.data && spans.length > 0 ? (
        <>
          <div className="trace-summary">
            <div className="trace-stat">
              <span>Trace ID</span>
              <strong className="mono">{traceQuery.data.trace_id}</strong>
            </div>
            <div className="trace-stat">
              <span>Returned spans</span>
              <strong>{spans.length.toLocaleString()}</strong>
            </div>
            <div className="trace-stat">
              <span>Services</span>
              <strong>{services.size.toLocaleString()}</strong>
            </div>
            <div className="trace-stat">
              <span>Observed duration</span>
              <strong>{traceDurationMs.toLocaleString()} ms</strong>
            </div>
          </div>

          <div className="trace-table-header">
            <div>
              <h3>Trace spans</h3>
              <p className="muted">
                Spans are ordered by observed start time. Parent IDs and timing come directly from OTLP data.
              </p>
            </div>
            <span className="muted">
              Window {formatUtcTimestamp(traceQuery.data.start)} — {formatUtcTimestamp(traceQuery.data.end)}
            </span>
          </div>

          <div className="metric-table-wrap">
            <table className="metric-table trace-table">
              <thead>
                <tr>
                  <th>Start (UTC)</th>
                  <th>Duration</th>
                  <th>Service</th>
                  <th>Span</th>
                  <th>Parent</th>
                  <th>Kind / status</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {spans.map((span, index) => (
                  <tr key={`${span.span_id ?? "missing-span"}-${span.start_time}-${index}`}>
                    <td className="mono">{formatUtcTimestamp(span.start_time)}</td>
                    <td className="mono">{formatDuration(span.duration_ns)}</td>
                    <td>
                      <strong className="trace-service">{span.service_name || "—"}</strong>
                      <span className="trace-environment">{span.environment || "—"}</span>
                    </td>
                    <td className="trace-span-name">
                      <strong>{span.span_name || "—"}</strong>
                      <code>{span.span_id ?? "missing span ID"}</code>
                    </td>
                    <td className="trace-parent mono">{parentLabel(span, returnedSpanIds)}</td>
                    <td>
                      <span className="trace-pill">{spanKind(span.span_kind)}</span>
                      <span className="trace-pill">{spanStatus(span.status_code)}</span>
                      {span.status_message ? <small className="trace-status-message">{span.status_message}</small> : null}
                    </td>
                    <td>
                      <details className="trace-details">
                        <summary>Inspect</summary>
                        <dl>
                          <div><dt>End</dt><dd>{formatUtcTimestamp(span.end_time)}</dd></div>
                          <div><dt>Trace state</dt><dd>{span.trace_state || "—"}</dd></div>
                          <div>
                            <dt>Scope</dt>
                            <dd>{span.scope_name || "—"}{span.scope_version ? ` ${span.scope_version}` : ""}</dd>
                          </div>
                          <div><dt>Span attributes</dt><dd>{formatAttributes(span.attributes)}</dd></div>
                          <div><dt>Resource attributes</dt><dd>{formatAttributes(span.resource_attributes)}</dd></div>
                          <div><dt>Scope attributes</dt><dd>{formatAttributes(span.scope_attributes)}</dd></div>
                          <div><dt>Events JSON</dt><dd className="mono">{span.events_json || "[]"}</dd></div>
                          <div><dt>Links JSON</dt><dd className="mono">{span.links_json || "[]"}</dd></div>
                          <div>
                            <dt>Flags / dropped attrs / events / links</dt>
                            <dd>
                              {span.flags} / {span.dropped_attributes_count} / {span.dropped_events_count} / {span.dropped_links_count}
                            </dd>
                          </div>
                        </dl>
                      </details>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted trace-semantics">
            Sentrix does not invent missing spans. A parent marked “not returned” was not present in this bounded response.
          </p>
        </>
      ) : null}
    </div>
  );
}
