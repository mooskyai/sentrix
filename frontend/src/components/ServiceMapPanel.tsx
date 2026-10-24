import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { getServiceMap } from "../api/resources";

interface ServiceMapPanelProps {
  projectId: string;
  start: string;
  end: string;
  tracesPath: string;
}

export function ServiceMapPanel({ projectId, start, end, tracesPath }: ServiceMapPanelProps) {
  const map = useQuery({
    queryKey: ["service-map", projectId, start, end, 100],
    queryFn: () => getServiceMap(projectId, { start, end, limit: 100 }),
    retry: false,
  });

  function traceHref(traceId: string): string {
    return `${tracesPath}?${new URLSearchParams({ trace_id: traceId, start, end }).toString()}`;
  }

  return (
    <section className="service-map" aria-label="Observed service map">
      <h3>Observed service relationships</h3>
      <p className="muted">
        Directed links require an actual parent and child span in the same trace, project and
        observation window. Missing links do not imply a disconnected or unhealthy service.
      </p>
      {map.isPending ? <p role="status">Loading observed relationships…</p> : null}
      {map.isError ? (
        <p role="alert" className="error">Unable to load service relationships: {map.error.message}</p>
      ) : null}
      {map.data ? (
        <>
          <p className="muted">
            {map.data.relationships.length} observed directed links from {map.data.scanned_spans.toLocaleString()} scanned spans.
          </p>
          {map.data.truncated ? (
            <p role="status" className="notice">
              Relationship map is incomplete: {map.data.span_scan_truncated
                ? "the span scan reached its safety cap"
                : "the relationship result reached its limit"}.
              Narrow the window before interpreting the visible links as complete.
            </p>
          ) : null}
          {map.data.relationships.length === 0 ? (
            <p className="muted">No cross-service parent/child spans observed in this window.</p>
          ) : (
            <ol className="service-map-links">
              {map.data.relationships.map((edge) => (
                <li key={JSON.stringify([
                  edge.from_service, edge.from_environment, edge.to_service, edge.to_environment,
                ])} className="service-map-edge">
                  <div className="service-map-pair">
                    <div className="service-map-node">
                      <strong>{edge.from_service}</strong>
                      <small>Environment: {edge.from_environment || "(empty)"}</small>
                    </div>
                    <span className="service-map-arrow" aria-label="calls">→</span>
                    <div className="service-map-node">
                      <strong>{edge.to_service}</strong>
                      <small>Environment: {edge.to_environment || "(empty)"}</small>
                    </div>
                  </div>
                  <p className="muted">{edge.span_pairs.toLocaleString()} observed span pairs</p>
                  <div className="service-map-traces">
                    {edge.trace_ids.map((id) => (
                      <Link key={id} to={traceHref(id)}>Inspect trace {id.slice(0, 8)}…</Link>
                    ))}
                  </div>
                </li>
              ))}
            </ol>
          )}
        </>
      ) : null}
    </section>
  );
}
