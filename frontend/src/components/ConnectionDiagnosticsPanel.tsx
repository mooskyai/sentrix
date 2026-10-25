import { useQuery } from "@tanstack/react-query";

import { getConnectionDiagnostics } from "../api/resources";
import type { ConnectionDiagnosticSignal } from "../types";

const SIGNALS = ["metrics", "logs", "traces"] as const;

function timestamp(value: string | null): string {
  return value ? new Date(value).toLocaleString() : "Not observed in this window";
}

function SignalRow({ name, signal }: { name: string; signal: ConnectionDiagnosticSignal }) {
  return (
    <li>
      <strong>{name}</strong>: {signal.observed ? `${signal.count} records` : "No observations"}
      {signal.observed ? ` · Last seen ${timestamp(signal.last_seen)}` : ""}
    </li>
  );
}

/** On-demand evidence of stored signal rows, not connection health or key status. */
export function ConnectionDiagnosticsPanel({ projectId }: { projectId: string }) {
  const query = useQuery({
    queryKey: ["connection-diagnostics", projectId],
    queryFn: () => getConnectionDiagnostics(projectId),
    retry: false,
    staleTime: 0,
  });

  const data = query.isError ? undefined : query.data;

  return (
    <section aria-label="First telemetry check" className="api-key-panel">
      <div className="api-key-header">
        <div>
          <h3>First telemetry check</h3>
          <p className="muted">
            Stored records in this project during the last 24 hours. This does not test live exporter
            connectivity or service health.
          </p>
        </div>
        <button
          className="button secondary"
          type="button"
          disabled={query.isFetching}
          onClick={() => void query.refetch()}
        >
          {query.isFetching ? "Checking…" : "Check again"}
        </button>
      </div>
      {query.isPending ? <p role="status">Checking stored telemetry…</p> : null}
      {query.isError ? (
        <p className="error" role="alert">Unable to query stored telemetry. Check the API and ClickHouse, then try again.</p>
      ) : null}
      {data ? (
        <div aria-live="polite">
          <p role="status">
            {data.observation_state === "observed"
              ? "Telemetry observed in the last 24 hours."
              : "No telemetry observed in the last 24 hours. This does not prove the exporter is disconnected."}
          </p>
          <ul>
            {SIGNALS.map((name) => (
              <SignalRow key={name} name={name} signal={data.signals[name]} />
            ))}
          </ul>
          <p className="muted">Window: {new Date(data.start).toLocaleString()} to {new Date(data.end).toLocaleString()}.</p>
        </div>
      ) : null}
    </section>
  );
}
