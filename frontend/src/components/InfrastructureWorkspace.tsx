import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { getInfrastructure } from "../api/resources";

const WINDOWS = {
  "1h": 60 * 60 * 1000,
  "6h": 6 * 60 * 60 * 1000,
  "24h": 24 * 60 * 60 * 1000,
  "7d": 7 * 24 * 60 * 60 * 1000,
} as const;
type TimeRange = keyof typeof WINDOWS;

const LABELS: Record<string, string> = {
  "host.name": "Host", "k8s.cluster.name": "Cluster",
  "k8s.namespace.name": "Namespace", "k8s.node.name": "Node",
  "k8s.deployment.name": "Deployment", "k8s.statefulset.name": "StatefulSet",
  "k8s.daemonset.name": "DaemonSet", "k8s.job.name": "Job",
  "k8s.cronjob.name": "CronJob", "k8s.pod.name": "Pod",
  "k8s.container.name": "Container",
};

interface Props { projectId: string }

export function InfrastructureWorkspace({ projectId }: Props) {
  const [range, setRange] = useState<TimeRange>("24h");
  const [anchor, setAnchor] = useState(() => Date.now());
  const window = useMemo(() => ({
    start: new Date(anchor - WINDOWS[range]).toISOString(),
    end: new Date(anchor).toISOString(),
  }), [anchor, range]);
  const infrastructure = useQuery({
    queryKey: ["infrastructure", projectId, window.start, window.end, 200],
    queryFn: () => getInfrastructure(projectId, { ...window, limit: 200 }),
    retry: false,
  });

  return (
    <div className="grid gap-3" aria-label="Observed infrastructure">
      <div className="services-toolbar flex flex-wrap items-end justify-between gap-2">
        <div>
          <h3>Observed resource attributes</h3>
          <p className="muted">Grouped sets received on the same OpenTelemetry resource, not a live host or Kubernetes inventory.</p>
        </div>
        <div className="services-actions flex flex-wrap items-end gap-3">
          <label className="grid gap-1.5 text-sm text-ink-soft">
            <span>Infrastructure observation window</span>
            <select aria-label="Infrastructure observation window" value={range}
              onChange={(event) => { setRange(event.target.value as TimeRange); setAnchor(Date.now()); }}>
              <option value="1h">Last 1 hour</option>
              <option value="6h">Last 6 hours</option>
              <option value="24h">Last 24 hours</option>
              <option value="7d">Last 7 days</option>
            </select>
          </label>
          <button type="button" className="button secondary" onClick={() => setAnchor(Date.now())}>Refresh</button>
        </div>
      </div>
      <p className="muted">Window: {window.start} to {window.end} (exclusive). Resources missing from this window are not necessarily deleted or down.</p>
      {infrastructure.isPending ? <p role="status">Loading observed infrastructure…</p> : null}
      {infrastructure.isError ? <p className="error" role="alert">Infrastructure unavailable: {infrastructure.error.message}</p> : null}
      {infrastructure.data ? (
        <>
          <p className="muted">Showing {infrastructure.data.observations.length} observed attribute sets in this project.</p>
          {infrastructure.data.truncated ? <p className="notice" role="status">Results truncated at {infrastructure.data.limit} sets. Narrow the time window before interpreting absence.</p> : null}
          {infrastructure.data.observations.length === 0 ? (
            <div className="empty-feature">
              <strong>No infrastructure attributes observed in this window.</strong>
              <p className="muted">Send OTLP telemetry with host.name or supported k8s.* resource attributes, or select a wider window.</p>
            </div>
          ) : (
            <div className="metric-table-wrap">
              <table className="metric-table">
                <thead><tr><th>Co-observed resource attributes</th><th>Metrics</th><th>Logs</th><th>Spans</th><th>Last observed (UTC)</th></tr></thead>
                <tbody>
                  {infrastructure.data.observations.map((observation, index) => (
                    <tr key={`${index}-${JSON.stringify(observation.attributes)}`}>
                      <td>
                        <dl className="flex flex-wrap gap-3">
                          {Object.entries(observation.attributes).map(([key, value]) => (
                            <div key={key} className="grid gap-1">
                              <dt className="muted">{LABELS[key] ?? key}</dt>
                              <dd className="mono">{value}</dd>
                            </div>
                          ))}
                        </dl>
                      </td>
                      <td>{observation.metric_points.toLocaleString()}</td>
                      <td>{observation.log_records.toLocaleString()}</td>
                      <td>{observation.span_records.toLocaleString()}</td>
                      <td>{observation.last_seen}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      ) : null}
    </div>
  );
}
