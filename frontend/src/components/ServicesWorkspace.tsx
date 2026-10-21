import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";

import { getServiceCatalog, getServiceDetail } from "../api/resources";
import { DetailDrawer } from "./DetailDrawer";
import type { ObservedService } from "../types";

const RANGE_MS = {
  "1h": 60 * 60 * 1000,
  "6h": 6 * 60 * 60 * 1000,
  "24h": 24 * 60 * 60 * 1000,
  "7d": 7 * 24 * 60 * 60 * 1000,
} as const;

type Range = keyof typeof RANGE_MS;

function utc(value: string): string {
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

function description(service: ObservedService): string {
  return `${service.signals.length} observed signal ${service.signals.length === 1 ? "type" : "types"}`;
}

interface ServicesWorkspaceProps {
  projectId: string;
  metricsPath: string;
  logsPath: string;
  tracesPath: string;
}

export function ServicesWorkspace({
  projectId,
  metricsPath,
  logsPath,
  tracesPath,
}: ServicesWorkspaceProps) {
  const [range, setRange] = useState<Range>("24h");
  const [anchorMs, setAnchorMs] = useState(() => Date.now());
  const [searchParams, setSearchParams] = useSearchParams();
  const serviceName = searchParams.get("service_name");
  const environment = searchParams.get("environment");
  const hasSelection = serviceName !== null && environment !== null;

  const window = useMemo(
    () => ({
      start: new Date(anchorMs - RANGE_MS[range]).toISOString(),
      end: new Date(anchorMs).toISOString(),
    }),
    [anchorMs, range],
  );
  const catalog = useQuery({
    queryKey: ["service-catalog", projectId, window.start, window.end, 500],
    queryFn: () => getServiceCatalog(projectId, { ...window, limit: 500 }),
    retry: false,
  });

  const selected = hasSelection
    ? catalog.data?.services.find(
        (entry) => entry.service_name === serviceName && entry.environment === environment,
      )
    : undefined;

  const detail = useQuery({
    queryKey: [
      "service-detail", projectId, window.start, window.end,
      selected?.service_name ?? "", selected?.environment ?? "",
    ],
    queryFn: () => getServiceDetail(projectId, {
      ...window, service_name: selected!.service_name, environment: selected!.environment,
    }),
    enabled: Boolean(selected),
    retry: false,
  });

  function traceHref(traceId: string): string {
    return `${tracesPath}?${new URLSearchParams({ trace_id: traceId, ...window }).toString()}`;
  }

  function selectService(item: ObservedService) {
    setSearchParams({ service_name: item.service_name, environment: item.environment });
  }

  return (
    <div className="services-workspace grid gap-3" aria-label="Observed services">
      <div className="services-toolbar flex flex-wrap items-start justify-between gap-3 rounded-control border border-line bg-canvas-soft p-3">
        <div>
          <h3>Observed service catalog</h3>
          <p className="muted">
            Services appear only when metrics, logs, or spans were received during this window.
            Not observed does not mean deleted or down.
          </p>
        </div>
        <div className="services-actions flex flex-wrap items-end gap-3">
          <label className="grid gap-1.5 text-sm text-ink-soft">
            <span>Service observation window</span>
            <select
              aria-label="Service observation window"
              value={range}
              onChange={(event) => {
                setRange(event.target.value as Range);
                setAnchorMs(Date.now());
              }}
            >
              <option value="1h">Last 1 hour</option>
              <option value="6h">Last 6 hours</option>
              <option value="24h">Last 24 hours</option>
              <option value="7d">Last 7 days</option>
            </select>
          </label>
          <button className="button secondary" onClick={() => setAnchorMs(Date.now())} type="button">
            Refresh
          </button>
        </div>
      </div>

      <p className="muted service-window">
        Requested observation window: {utc(window.start)} — {utc(window.end)} (end exclusive)
      </p>
      {catalog.isPending ? <p role="status">Loading observed services…</p> : null}
      {catalog.isError ? (
        <p className="error" role="alert">Unable to load services: {catalog.error.message}</p>
      ) : null}
      {catalog.data ? (
        <>
          <p className="muted">
            Catalog window: {utc(catalog.data.start)} — {utc(catalog.data.end)} (end exclusive).
            Showing {catalog.data.services.length} observed identities.
          </p>
          {catalog.data.truncated ? (
            <p className="notice" role="status">
              Catalog truncated at {catalog.data.limit} service identities. Narrow the observation
              window before treating this list as complete.
            </p>
          ) : null}
          {catalog.data.services.length === 0 ? (
            <div className="empty-feature">
              <strong>No services observed in this window.</strong>
              <p className="muted">Try a wider window or send project-scoped OpenTelemetry data.</p>
            </div>
          ) : (
            <div className="metric-table-wrap">
              <table className="metric-table services-table">
                <thead>
                  <tr>
                    <th>Service</th><th>Environment</th><th>Signals</th>
                    <th>Metrics</th><th>Logs</th><th>Spans</th><th>Last observed</th><th>Detail</th>
                  </tr>
                </thead>
                <tbody>
                  {catalog.data.services.map((entry) => (
                    <tr key={JSON.stringify([entry.service_name, entry.environment])}>
                      <td>{entry.service_name}</td>
                      <td>{entry.environment || "(empty)"}</td>
                      <td>{entry.signals.join(", ")}</td>
                      <td>{entry.metric_points.toLocaleString()}</td>
                      <td>{entry.log_records.toLocaleString()}</td>
                      <td>{entry.span_records.toLocaleString()}</td>
                      <td>{utc(entry.last_seen)}</td>
                      <td>
                        <button
                          className="button secondary"
                          type="button"
                          onClick={() => selectService(entry)}
                          aria-label={`Inspect ${entry.service_name}, environment ${entry.environment || "empty"}`}
                        >
                          Inspect
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {hasSelection && !selected ? (
            <div className="empty-feature" role="status">
              <strong>Selected service is not in the returned catalog window.</strong>
              <p className="muted">
                {catalog.data.truncated
                  ? "Results are truncated; this does not prove the service was not observed."
                  : "The service was not observed in this window; this does not indicate downtime."}
              </p>
              <button className="button secondary" onClick={() => setSearchParams({})} type="button">
                Clear selection
              </button>
            </div>
          ) : null}
          {selected ? (
            <DetailDrawer title={`Service: ${selected.service_name}`} onClose={() => setSearchParams({})}>
            <section className="service-detail alert-rule-card" aria-label="Service detail">
              <div className="service-detail-heading flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h3>{selected.service_name}</h3>
                  <p className="muted">Environment: {selected.environment || "(empty)"}</p>
                  <p className="muted">{description(selected)} in the selected window.</p>
                </div>
                <button className="button secondary" type="button" onClick={() => setSearchParams({})}>
                  Close detail
                </button>
              </div>
              <div className="metric-summary">
                <div className="metric-stat"><span>Metric points</span><strong>{selected.metric_points}</strong></div>
                <div className="metric-stat"><span>Log records</span><strong>{selected.log_records}</strong></div>
                <div className="metric-stat"><span>Span records</span><strong>{selected.span_records}</strong></div>
                <div className="metric-stat"><span>Observed signals</span><strong>{selected.signals.join(", ")}</strong></div>
              </div>
              <p className="muted">First observed: {utc(selected.first_seen)}. Last observed: {utc(selected.last_seen)}.</p>
              <p className="muted">
                These are aggregated counts in the selected window, not health, ownership, SLO,
                throughput, or a complete inventory.
              </p>
              <nav aria-label="Service explorer links" className="services-links flex flex-wrap gap-2">
                <Link className="button secondary" to={metricsPath}>Open Metrics</Link>
                <Link className="button secondary" to={logsPath}>Open Logs</Link>
                <Link className="button secondary" to={tracesPath}>Open Traces</Link>
              </nav>
              <p className="muted">
                Explorer links retain this project. Metrics and Logs links do not prefilter data;
                apply exact service/environment filters there. Trace links below include an observed ID.
              </p>
              {detail.isPending ? <p role="status">Loading service references…</p> : null}
              {detail.isError ? (
                <p role="alert" className="error">Unable to load service detail: {detail.error.message}</p>
              ) : null}
              {detail.isSuccess ? (
                <div className="grid gap-3" aria-label="Service telemetry references">
                  <section>
                    <h4>Observed metric names</h4>
                    {detail.data.metric_names.length === 0 ? <p className="muted">No metric names returned.</p> : (
                      <ul>{detail.data.metric_names.map((metric) => (
                        <li key={metric.name}>{metric.name}: {metric.point_count.toLocaleString()} points</li>
                      ))}</ul>
                    )}
                  </section>
                  <section>
                    <h4>Recent error logs (severity 17+)</h4>
                    {detail.data.error_logs.length === 0 ? <p className="muted">No error logs returned.</p> : (
                      <ul>{detail.data.error_logs.map((log, index) => (
                        <li key={`${log.timestamp}-${index}`}>
                          {utc(log.timestamp)} · {log.severity_text || log.severity_number}: {log.body}
                          {log.trace_id ? <> · <Link to={traceHref(log.trace_id)}>Open related trace</Link></> : null}
                        </li>
                      ))}</ul>
                    )}
                  </section>
                  <section>
                    <h4>Recent trace IDs</h4>
                    {detail.data.trace_references.length === 0 ? <p className="muted">No trace IDs returned.</p> : (
                      <ul>{detail.data.trace_references.map((trace) => (
                        <li key={trace.trace_id}>
                          <Link to={traceHref(trace.trace_id)}>{trace.trace_id}</Link>
                          {" · "}{trace.span_records} spans · {utc(trace.last_seen)}
                        </li>
                      ))}</ul>
                    )}
                  </section>
                  {Object.values(detail.data.truncated).some(Boolean) ? (
                    <p className="notice" role="status">
                      Detail references are truncated. Narrow the observation window before treating these lists as complete.
                    </p>
                  ) : null}
                </div>
              ) : null}
            </section>
            </DetailDrawer>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
