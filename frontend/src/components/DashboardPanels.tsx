import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  deleteProjectDashboardPanel,
  getMetricSeries,
  getProjectDashboardPanels,
} from "../api/resources";
import type { DashboardPanelTimeRange, ProjectDashboardPanel } from "../types";
import { MetricPointPlot } from "./MetricsExplorer";

const RANGE_MS: Record<DashboardPanelTimeRange, number> = {
  "1h": 60 * 60 * 1000,
  "6h": 6 * 60 * 60 * 1000,
  "24h": 24 * 60 * 60 * 1000,
  "7d": 7 * 24 * 60 * 60 * 1000,
};

const RANGE_LABEL: Record<DashboardPanelTimeRange, string> = {
  "1h": "Last 1 hour",
  "6h": "Last 6 hours",
  "24h": "Last 24 hours",
  "7d": "Last 7 days",
};

function formatNumber(value: number): string {
  return new Intl.NumberFormat(undefined, { maximumSignificantDigits: 6 }).format(value);
}

function DashboardPanelCard({
  panel,
  projectId,
  anchorMs,
  canManage,
  removing,
  onRemove,
}: {
  panel: ProjectDashboardPanel;
  projectId: string;
  anchorMs: number;
  canManage: boolean;
  removing: boolean;
  onRemove: (panel: ProjectDashboardPanel) => void;
}) {
  const window = useMemo(
    () => ({
      start: new Date(anchorMs - RANGE_MS[panel.time_range]).toISOString(),
      end: new Date(anchorMs).toISOString(),
    }),
    [anchorMs, panel.time_range],
  );
  const series = useQuery({
    queryKey: [
      "dashboard-panel-series",
      projectId,
      panel.id,
      panel.metric_name,
      panel.time_range,
      panel.service_name,
      panel.environment,
      window.start,
      window.end,
    ],
    queryFn: () =>
      getMetricSeries(projectId, {
        metric_name: panel.metric_name,
        ...window,
        ...(panel.service_name ? { service_name: panel.service_name } : {}),
        ...(panel.environment ? { environment: panel.environment } : {}),
        limit: 500,
      }),
    retry: false,
  });

  const values = series.data?.points.map((point) => point.value) ?? [];
  const latest = series.data?.points.at(-1);
  const minimum = values.length > 0 ? Math.min(...values) : null;
  const maximum = values.length > 0 ? Math.max(...values) : null;

  return (
    <article className="dashboard-panel">
      <header className="dashboard-panel-header">
        <div>
          <h3>{panel.title}</h3>
          <p className="mono muted">{panel.metric_name}</p>
        </div>
        {canManage ? (
          <button
            className="button danger"
            type="button"
            disabled={removing}
            onClick={() => onRemove(panel)}
          >
            {removing ? "Removing…" : "Remove"}
          </button>
        ) : null}
      </header>

      <div className="dashboard-panel-query">
        <span className="metric-pill">{RANGE_LABEL[panel.time_range]}</span>
        {panel.service_name ? <span className="metric-pill">service={panel.service_name}</span> : null}
        {panel.environment ? (
          <span className="metric-pill">environment={panel.environment}</span>
        ) : null}
      </div>

      {series.isPending ? <p className="muted metric-state">Loading panel telemetry…</p> : null}
      {series.isError ? (
        <p className="error metric-state">Unable to load panel telemetry: {series.error.message}</p>
      ) : null}
      {series.data?.points.length === 0 ? (
        <div className="empty-feature dashboard-panel-empty">
          <strong>No numeric points matched this saved query.</strong>
          <p className="muted">
            The panel remains configured; wait for telemetry or adjust it from Metrics by pinning a new
            query.
          </p>
        </div>
      ) : null}
      {series.data?.truncated ? (
        <p className="notice metric-state">
          This panel reached its 500-point dashboard limit. Use a narrower pinned query before treating
          the visible points as complete.
        </p>
      ) : null}

      {series.data && series.data.points.length > 0 && latest && minimum !== null && maximum !== null ? (
        <>
          <div className="dashboard-panel-stats" aria-label={`${panel.title} summary`}>
            <div className="metric-stat">
              <span>Latest</span>
              <strong>{formatNumber(latest.value)}</strong>
            </div>
            <div className="metric-stat">
              <span>Min</span>
              <strong>{formatNumber(minimum)}</strong>
            </div>
            <div className="metric-stat">
              <span>Max</span>
              <strong>{formatNumber(maximum)}</strong>
            </div>
            <div className="metric-stat">
              <span>Points</span>
              <strong>{series.data.points.length.toLocaleString()}</strong>
            </div>
          </div>
          <MetricPointPlot points={series.data.points} unit="" />
          <p className="muted dashboard-panel-semantics">
            Raw observed gauge/sum number points. No rate, delta, average, or histogram derivation.
          </p>
        </>
      ) : null}
    </article>
  );
}

export function DashboardPanels({
  projectId,
  canManage,
}: {
  projectId: string;
  canManage: boolean;
}) {
  const [anchorMs, setAnchorMs] = useState(() => Date.now());
  const queryClient = useQueryClient();
  const panels = useQuery({
    queryKey: ["dashboard-panels", projectId],
    queryFn: () => getProjectDashboardPanels(projectId),
    retry: false,
  });
  const removePanel = useMutation({
    mutationFn: (panelId: string) => deleteProjectDashboardPanel(projectId, panelId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["dashboard-panels", projectId] }),
  });

  function requestRemove(panel: ProjectDashboardPanel) {
    if (!window.confirm(`Remove “${panel.title}” from this dashboard?`)) return;
    removePanel.mutate(panel.id);
  }

  return (
    <div className="dashboard-panels">
      <div className="dashboard-toolbar">
        <div>
          <h3>Project dashboard</h3>
          <p className="muted">
            Read-only telemetry panels pinned from Metrics. Configuration is stored in the project
            control plane; values are queried from ClickHouse.
          </p>
        </div>
        <button className="button secondary" type="button" onClick={() => setAnchorMs(Date.now())}>
          Refresh panels
        </button>
      </div>

      {panels.isPending ? <p className="muted metric-state">Loading dashboard panels…</p> : null}
      {panels.isError ? (
        <p className="error metric-state">Unable to load dashboard panels: {panels.error.message}</p>
      ) : null}
      {removePanel.isError ? (
        <p className="error metric-state">Unable to remove dashboard panel: {removePanel.error.message}</p>
      ) : null}
      {panels.data?.length === 0 ? (
        <div className="empty-feature metric-state">
          <strong>No dashboard panels configured.</strong>
          <p className="muted">
            {canManage
              ? "Open Metrics, select a numeric metric/query, and pin it to this dashboard."
              : "A project editor can pin numeric metric queries from the Metrics workspace."}
          </p>
        </div>
      ) : null}

      {panels.data && panels.data.length > 0 ? (
        <div className="dashboard-grid">
          {panels.data.map((panel) => (
            <DashboardPanelCard
              key={panel.id}
              panel={panel}
              projectId={projectId}
              anchorMs={anchorMs}
              canManage={canManage}
              removing={removePanel.isPending && removePanel.variables === panel.id}
              onRemove={requestRemove}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}
