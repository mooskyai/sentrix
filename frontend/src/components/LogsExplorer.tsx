import { useMemo, useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { getLogs } from "../api/resources";
import type { LogSearchRow } from "../types";

const RANGE_MS = {
  "1h": 60 * 60 * 1000,
  "6h": 6 * 60 * 60 * 1000,
  "24h": 24 * 60 * 60 * 1000,
  "7d": 7 * 24 * 60 * 60 * 1000,
} as const;

type LogTimeRange = keyof typeof RANGE_MS;

type ResultLimit = 100 | 200 | 500 | 1000;

interface AppliedFilters {
  service_name?: string;
  environment?: string;
  min_severity_number?: number;
  body_contains?: string;
  trace_id?: string;
}

function formatUtcTimestamp(value: string | null): string {
  if (!value) return "—";
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

function formatAttributes(attributes: Record<string, string>): string {
  const entries = Object.entries(attributes).sort(([left], [right]) => left.localeCompare(right));
  if (entries.length === 0) return "—";
  return entries.map(([key, value]) => `${key}=${value}`).join(", ");
}

function severityLabel(log: LogSearchRow): string {
  const label = log.severity_text.trim() || (log.severity_number === 0 ? "Unspecified" : "Severity");
  return `${label} (${log.severity_number})`;
}

function logRowKey(log: LogSearchRow, index: number): string {
  return `${log.timestamp}-${log.trace_id ?? "no-trace"}-${log.span_id ?? "no-span"}-${index}`;
}

function isNavigableTraceId(value: string | null): value is string {
  return value !== null && /^[0-9a-f]{32}$/.test(value) && value !== "0".repeat(32);
}

function traceHref(tracePath: string, traceId: string, start: string, end: string): string {
  const params = new URLSearchParams({ trace_id: traceId, start, end });
  return `${tracePath}?${params.toString()}`;
}

export function LogsExplorer({ projectId, tracePath }: { projectId: string; tracePath: string }) {
  const [range, setRange] = useState<LogTimeRange>("1h");
  const [limit, setLimit] = useState<ResultLimit>(200);
  const [anchorMs, setAnchorMs] = useState(() => Date.now());
  const [serviceInput, setServiceInput] = useState("");
  const [environmentInput, setEnvironmentInput] = useState("");
  const [severityInput, setSeverityInput] = useState("");
  const [bodyInput, setBodyInput] = useState("");
  const [traceInput, setTraceInput] = useState("");
  const [filters, setFilters] = useState<AppliedFilters>({});

  const window = useMemo(
    () => ({
      start: new Date(anchorMs - RANGE_MS[range]).toISOString(),
      end: new Date(anchorMs).toISOString(),
    }),
    [anchorMs, range],
  );

  const logQuery = useQuery({
    queryKey: [
      "logs-search",
      projectId,
      window.start,
      window.end,
      limit,
      filters.service_name ?? "",
      filters.environment ?? "",
      filters.min_severity_number ?? "",
      filters.body_contains ?? "",
      filters.trace_id ?? "",
    ],
    queryFn: () => getLogs(projectId, { ...window, limit, ...filters }),
    retry: false,
  });

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const serviceName = serviceInput.trim();
    const environment = environmentInput.trim();
    const bodyContains = bodyInput.trim();
    const traceId = traceInput.trim().toLowerCase();
    setFilters({
      ...(serviceName ? { service_name: serviceName } : {}),
      ...(environment ? { environment } : {}),
      ...(severityInput ? { min_severity_number: Number(severityInput) } : {}),
      ...(bodyContains ? { body_contains: bodyContains } : {}),
      ...(traceId ? { trace_id: traceId } : {}),
    });
    setAnchorMs(Date.now());
  }

  function clearFilters() {
    setServiceInput("");
    setEnvironmentInput("");
    setSeverityInput("");
    setBodyInput("");
    setTraceInput("");
    setFilters({});
    setAnchorMs(Date.now());
  }

  return (
    <div className="logs-explorer">
      <div className="logs-controls">
        <label>
          <span>Time range</span>
          <select
            aria-label="Log time range"
            value={range}
            onChange={(event) => {
              setRange(event.target.value as LogTimeRange);
              setAnchorMs(Date.now());
            }}
          >
            <option value="1h">Last 1 hour</option>
            <option value="6h">Last 6 hours</option>
            <option value="24h">Last 24 hours</option>
            <option value="7d">Last 7 days</option>
          </select>
        </label>

        <label>
          <span>Result limit</span>
          <select
            aria-label="Log result limit"
            value={limit}
            onChange={(event) => {
              setLimit(Number(event.target.value) as ResultLimit);
              setAnchorMs(Date.now());
            }}
          >
            <option value={100}>100 rows</option>
            <option value={200}>200 rows</option>
            <option value={500}>500 rows</option>
            <option value={1000}>1,000 rows</option>
          </select>
        </label>

        <div className="logs-actions">
          <button className="button secondary" type="button" onClick={() => setAnchorMs(Date.now())}>
            Refresh
          </button>
        </div>
      </div>

      <form className="log-filter-form" onSubmit={applyFilters}>
        <div className="log-filter-grid">
          <label>
            <span>Service</span>
            <input
              aria-label="Log service"
              value={serviceInput}
              onChange={(event) => setServiceInput(event.target.value)}
              placeholder="Exact service.name"
            />
          </label>
          <label>
            <span>Environment</span>
            <input
              aria-label="Log environment"
              value={environmentInput}
              onChange={(event) => setEnvironmentInput(event.target.value)}
              placeholder="Exact deployment environment"
            />
          </label>
          <label>
            <span>Minimum severity</span>
            <select
              aria-label="Minimum log severity"
              value={severityInput}
              onChange={(event) => setSeverityInput(event.target.value)}
            >
              <option value="">Any severity</option>
              <option value="1">Trace and above (1)</option>
              <option value="5">Debug and above (5)</option>
              <option value="9">Info and above (9)</option>
              <option value="13">Warn and above (13)</option>
              <option value="17">Error and above (17)</option>
              <option value="21">Fatal and above (21)</option>
            </select>
          </label>
          <label className="log-filter-wide">
            <span>Body contains</span>
            <input
              aria-label="Log body contains"
              value={bodyInput}
              onChange={(event) => setBodyInput(event.target.value)}
              placeholder="Case-insensitive substring"
            />
          </label>
          <label className="log-filter-wide">
            <span>Trace ID</span>
            <input
              aria-label="Log trace ID"
              className="mono"
              value={traceInput}
              onChange={(event) => setTraceInput(event.target.value)}
              placeholder="32 hexadecimal characters"
            />
          </label>
        </div>
        <div className="logs-actions">
          <button className="button" type="submit">Apply filters</button>
          <button className="button secondary" type="button" onClick={clearFilters}>Clear</button>
        </div>
      </form>

      {logQuery.isPending ? <p className="muted log-state">Loading project logs…</p> : null}
      {logQuery.isError ? (
        <p className="error log-state">Unable to load logs: {logQuery.error.message}</p>
      ) : null}
      {logQuery.data?.logs.length === 0 ? (
        <div className="empty-feature log-state">
          <strong>No logs matched this query.</strong>
          <p className="muted">Try a wider time range or clear one or more filters.</p>
        </div>
      ) : null}
      {logQuery.data?.truncated ? (
        <p className="notice log-state">
          This result reached the selected row limit. Narrow the time range or add filters before
          treating the visible rows as complete.
        </p>
      ) : null}

      {logQuery.data && logQuery.data.logs.length > 0 ? (
        <>
          <div className="log-table-header">
            <div>
              <h3>Observed logs</h3>
              <p className="muted">
                Raw newest-first log rows from the project-scoped M4.1 query boundary.
              </p>
            </div>
            <span className="muted">{logQuery.data.logs.length.toLocaleString()} returned rows</span>
          </div>
          <div className="metric-table-wrap">
            <table className="metric-table log-table">
              <thead>
                <tr>
                  <th>Time (UTC)</th>
                  <th>Severity</th>
                  <th>Service</th>
                  <th>Body</th>
                  <th>Correlation</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {logQuery.data.logs.map((log, index) => (
                  <tr key={logRowKey(log, index)}>
                    <td className="mono">{formatUtcTimestamp(log.timestamp)}</td>
                    <td><span className="log-severity">{severityLabel(log)}</span></td>
                    <td>
                      <strong className="log-service">{log.service_name || "—"}</strong>
                      <span className="log-environment">{log.environment || "—"}</span>
                    </td>
                    <td className="log-body">
                      <span>{log.body || "—"}</span>
                      {log.event_name ? <small>event: {log.event_name}</small> : null}
                    </td>
                    <td className="log-correlation">
                      <span>
                        <strong>Trace</strong>
                        <code>{log.trace_id ?? "—"}</code>
                        {isNavigableTraceId(log.trace_id) ? (
                          <Link
                            className="trace-link"
                            to={traceHref(
                              tracePath,
                              log.trace_id,
                              logQuery.data.start,
                              logQuery.data.end,
                            )}
                          >
                            Open trace
                          </Link>
                        ) : null}
                      </span>
                      <span><strong>Span</strong> <code>{log.span_id ?? "—"}</code></span>
                    </td>
                    <td>
                      <details className="log-details">
                        <summary>Inspect</summary>
                        <dl>
                          <div>
                            <dt>Observed</dt>
                            <dd>{formatUtcTimestamp(log.observed_timestamp)}</dd>
                          </div>
                          <div>
                            <dt>Scope</dt>
                            <dd>{log.scope_name || "—"}{log.scope_version ? ` ${log.scope_version}` : ""}</dd>
                          </div>
                          <div>
                            <dt>Log attributes</dt>
                            <dd>{formatAttributes(log.attributes)}</dd>
                          </div>
                          <div>
                            <dt>Resource attributes</dt>
                            <dd>{formatAttributes(log.resource_attributes)}</dd>
                          </div>
                          <div>
                            <dt>Scope attributes</dt>
                            <dd>{formatAttributes(log.scope_attributes)}</dd>
                          </div>
                          <div>
                            <dt>Flags / dropped attributes</dt>
                            <dd>{log.flags} / {log.dropped_attributes_count}</dd>
                          </div>
                        </dl>
                      </details>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted log-semantics">
            Non-zero trace IDs can open the M4.3 project-scoped trace view using this log query's same
            bounded UTC window. Span IDs remain raw correlation data.
          </p>
        </>
      ) : null}
    </div>
  );
}
