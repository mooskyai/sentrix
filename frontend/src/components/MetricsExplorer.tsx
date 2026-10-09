import { useMemo, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { createProjectDashboardPanel, getMetricCatalog, getMetricSeries } from "../api/resources";
import type { MetricCatalogItem, MetricSeriesPoint } from "../types";

const RANGE_MS = {
  "1h": 60 * 60 * 1000,
  "6h": 6 * 60 * 60 * 1000,
  "24h": 24 * 60 * 60 * 1000,
  "7d": 7 * 24 * 60 * 60 * 1000,
} as const;

type MetricTimeRange = keyof typeof RANGE_MS;

interface AppliedFilters {
  service_name?: string;
  environment?: string;
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat(undefined, { maximumSignificantDigits: 6 }).format(value);
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

function formatAttributes(attributes: Record<string, string>): string {
  const entries = Object.entries(attributes);
  if (entries.length === 0) return "—";
  return entries.map(([key, value]) => `${key}=${value}`).join(", ");
}

export function MetricPointPlot({ points, unit }: { points: MetricSeriesPoint[]; unit: string }) {
  const timestamps = points.map((point) => Date.parse(point.timestamp));
  const values = points.map((point) => point.value);
  const minTime = Math.min(...timestamps);
  const maxTime = Math.max(...timestamps);
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const xFor = (timestamp: number) =>
    maxTime === minTime ? 400 : 40 + ((timestamp - minTime) / (maxTime - minTime)) * 720;
  const yFor = (value: number) =>
    maxValue === minValue ? 120 : 20 + (1 - (value - minValue) / (maxValue - minValue)) * 180;

  return (
    <div className="metric-plot">
      <div className="metric-plot-meta">
        <span>Max {formatNumber(maxValue)}{unit ? ` ${unit}` : ""}</span>
        <span>Min {formatNumber(minValue)}{unit ? ` ${unit}` : ""}</span>
      </div>
      <svg
        viewBox="0 0 800 240"
        role="img"
        aria-label={`Metric point plot showing ${points.length} observed points`}
      >
        <line className="metric-axis" x1="40" y1="210" x2="760" y2="210" />
        <line className="metric-axis" x1="40" y1="20" x2="40" y2="210" />
        {points.map((point, index) => (
          <circle
            className="metric-point"
            key={`${point.timestamp}-${point.service_name}-${point.environment}-${index}`}
            cx={xFor(timestamps[index])}
            cy={yFor(point.value)}
            r="3"
          >
            <title>
              {formatUtcTimestamp(point.timestamp)} · {formatNumber(point.value)}
              {unit ? ` ${unit}` : ""} · {point.service_name || "unknown service"}
            </title>
          </circle>
        ))}
      </svg>
    </div>
  );
}

function MetricDetails({ metric }: { metric: MetricCatalogItem }) {
  return (
    <div className="metric-summary" aria-label="Selected metric metadata">
      <div className="metric-stat">
        <span>Type</span>
        <strong>{metric.metric_types.join(", ") || "unknown"}</strong>
      </div>
      <div className="metric-stat">
        <span>Value</span>
        <strong>{metric.value_types.join(", ") || "unknown"}</strong>
      </div>
      <div className="metric-stat">
        <span>Unit</span>
        <strong>{metric.unit || "—"}</strong>
      </div>
      <div className="metric-stat">
        <span>Observed points</span>
        <strong>{metric.point_count.toLocaleString()}</strong>
      </div>
    </div>
  );
}

export function MetricsExplorer({
  projectId,
  canManageDashboard = false,
}: {
  projectId: string;
  canManageDashboard?: boolean;
}) {
  const [range, setRange] = useState<MetricTimeRange>("1h");
  const [anchorMs, setAnchorMs] = useState(() => Date.now());
  const [requestedMetric, setRequestedMetric] = useState("");
  const [serviceInput, setServiceInput] = useState("");
  const [environmentInput, setEnvironmentInput] = useState("");
  const [filters, setFilters] = useState<AppliedFilters>({});
  const queryClient = useQueryClient();

  const window = useMemo(
    () => ({
      start: new Date(anchorMs - RANGE_MS[range]).toISOString(),
      end: new Date(anchorMs).toISOString(),
    }),
    [anchorMs, range],
  );

  const catalog = useQuery({
    queryKey: ["metric-catalog", projectId, window.start, window.end],
    queryFn: () => getMetricCatalog(projectId, window),
    retry: false,
  });

  const numericMetrics = useMemo(
    () => catalog.data?.metrics.filter((metric) => metric.supports_numeric_series) ?? [],
    [catalog.data],
  );

  const selectedMetric = numericMetrics.some((metric) => metric.name === requestedMetric)
    ? requestedMetric
    : (numericMetrics[0]?.name ?? "");
  const selectedMetadata = catalog.data?.metrics.find((metric) => metric.name === selectedMetric);
  const series = useQuery({
    queryKey: [
      "metric-series",
      projectId,
      selectedMetric,
      window.start,
      window.end,
      filters.service_name ?? "",
      filters.environment ?? "",
    ],
    queryFn: () =>
      getMetricSeries(projectId, {
        metric_name: selectedMetric,
        ...window,
        ...filters,
      }),
    enabled: selectedMetric.length > 0,
    retry: false,
  });

  const pinPanel = useMutation({
    mutationFn: () =>
      createProjectDashboardPanel(projectId, {
        title: selectedMetadata?.name ?? selectedMetric,
        metric_name: selectedMetric,
        time_range: range,
        service_name: filters.service_name ?? "",
        environment: filters.environment ?? "",
      }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["dashboard-panels", projectId] }),
  });

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const serviceName = serviceInput.trim();
    const environment = environmentInput.trim();
    setFilters({
      ...(serviceName ? { service_name: serviceName } : {}),
      ...(environment ? { environment } : {}),
    });
  }

  function clearFilters() {
    setServiceInput("");
    setEnvironmentInput("");
    setFilters({});
  }

  const tablePoints = series.data?.points.slice(-100).reverse() ?? [];

  return (
    <div className="metrics-explorer">
      <div className="metrics-controls">
        <label>
          <span>Time range</span>
          <select
            aria-label="Time range"
            value={range}
            onChange={(event) => {
              setRange(event.target.value as MetricTimeRange);
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
          <span>Metric</span>
          <select
            aria-label="Metric"
            value={selectedMetric}
            onChange={(event) => setRequestedMetric(event.target.value)}
            disabled={catalog.isPending || numericMetrics.length === 0}
          >
            <option value="">Select a numeric metric</option>
            {(catalog.data?.metrics ?? []).map((metric) => (
              <option
                key={metric.name}
                value={metric.name}
                disabled={!metric.supports_numeric_series}
              >
                {metric.name}{metric.supports_numeric_series ? "" : " (non-scalar)"}
              </option>
            ))}
          </select>
        </label>

        <div className="metrics-actions">
          <button className="button secondary" type="button" onClick={() => setAnchorMs(Date.now())}>
            Refresh
          </button>
        </div>
      </div>

      {catalog.isPending ? <p className="muted metric-state">Loading observed metrics…</p> : null}
      {catalog.isError ? (
        <p className="error metric-state">Unable to load metrics: {catalog.error.message}</p>
      ) : null}
      {catalog.data?.metrics.length === 0 ? (
        <div className="empty-feature metric-state">
          <strong>No metrics observed in this time range.</strong>
          <p className="muted">Send OpenTelemetry metrics to this project or choose a wider range.</p>
        </div>
      ) : null}
      {catalog.data && catalog.data.metrics.length > 0 && numericMetrics.length === 0 ? (
        <div className="notice metric-state">
          Metrics were observed, but none have scalar number points. Histogram and summary families are
          intentionally not flattened in this explorer.
        </div>
      ) : null}

      {selectedMetadata ? <MetricDetails metric={selectedMetadata} /> : null}
      {selectedMetadata?.description ? (
        <p className="muted metric-description">{selectedMetadata.description}</p>
      ) : null}

      {canManageDashboard && selectedMetric ? (
        <div className="metric-dashboard-action">
          <button
            className="button secondary"
            type="button"
            disabled={pinPanel.isPending}
            onClick={() => pinPanel.mutate()}
          >
            {pinPanel.isPending ? "Pinning…" : "Pin current query to dashboard"}
          </button>
          <span className="muted">
            Saves this metric, time range, and applied exact filters in the project control plane.
          </span>
        </div>
      ) : null}
      {pinPanel.isError ? (
        <p className="error metric-state">Unable to pin dashboard panel: {pinPanel.error.message}</p>
      ) : null}
      {pinPanel.data ? (
        <p className="notice metric-state">Pinned “{pinPanel.data.title}” to Dashboards.</p>
      ) : null}

      {selectedMetric ? (
        <form className="metric-filter-form" onSubmit={applyFilters}>
          <label>
            <span>Service</span>
            <input
              aria-label="Service"
              value={serviceInput}
              onChange={(event) => setServiceInput(event.target.value)}
              placeholder="Exact service.name"
            />
          </label>
          <label>
            <span>Environment</span>
            <input
              aria-label="Environment"
              value={environmentInput}
              onChange={(event) => setEnvironmentInput(event.target.value)}
              placeholder="Exact deployment environment"
            />
          </label>
          <div className="metrics-actions">
            <button className="button" type="submit">Apply filters</button>
            <button className="button secondary" type="button" onClick={clearFilters}>Clear</button>
          </div>
        </form>
      ) : null}

      {series.isPending && selectedMetric ? (
        <p className="muted metric-state">Loading metric points…</p>
      ) : null}
      {series.isError ? (
        <p className="error metric-state">Unable to load metric points: {series.error.message}</p>
      ) : null}
      {series.data?.points.length === 0 ? (
        <div className="empty-feature metric-state">
          <strong>No numeric points matched this query.</strong>
          <p className="muted">Try a wider time range or clear the exact dimension filters.</p>
        </div>
      ) : null}
      {series.data?.truncated ? (
        <p className="notice metric-state">
          This result reached the server point limit. Narrow the time range or add exact filters before
          interpreting the visible points as complete.
        </p>
      ) : null}

      {series.data && series.data.points.length > 0 && selectedMetadata ? (
        <>
          <p className="muted metric-semantics">
            Values are raw observed gauge/sum number points. Sentrix does not derive rates, deltas, or
            histogram statistics in M3.2.
          </p>
          <MetricPointPlot points={series.data.points} unit={selectedMetadata.unit} />
          <div className="metric-table-header">
            <h3>Observed points</h3>
            <span className="muted">
              Showing latest {tablePoints.length} of {series.data.points.length} returned points
            </span>
          </div>
          <div className="metric-table-wrap">
            <table className="metric-table">
              <thead>
                <tr>
                  <th>Time (UTC)</th>
                  <th>Value</th>
                  <th>Service</th>
                  <th>Environment</th>
                  <th>Type</th>
                  <th>Attributes</th>
                </tr>
              </thead>
              <tbody>
                {tablePoints.map((point, index) => (
                  <tr key={`${point.timestamp}-${point.service_name}-${point.environment}-${index}`}>
                    <td>{formatUtcTimestamp(point.timestamp)}</td>
                    <td className="mono">
                      {formatNumber(point.value)}{selectedMetadata.unit ? ` ${selectedMetadata.unit}` : ""}
                    </td>
                    <td>{point.service_name || "—"}</td>
                    <td>{point.environment || "—"}</td>
                    <td>
                      <span className="metric-pill">{point.metric_type}</span>
                      {point.is_monotonic ? <span className="metric-pill">monotonic</span> : null}
                    </td>
                    <td className="metric-attributes">{formatAttributes(point.attributes)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </div>
  );
}
