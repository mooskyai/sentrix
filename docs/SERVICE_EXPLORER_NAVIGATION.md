# Sentrix — service-to-explorer context (M6 UI correction)

The Services detail drawer links to Metrics, Logs and Traces with a URL-scoped
`service_name`, explicit `environment` (including empty) and observation range.
Links remain inside the current project route and never confer tenant access;
the backend still authorizes membership before ClickHouse queries.

Metrics and Logs prefill and immediately apply exact service/environment filters.
A suggested metric name is taken from observed service detail and is used only
when the metric catalog actually offers a numeric series. Clear removes the
service filters. A missing service, metric or empty result is not downtime.

Traces has a trace-ID lookup, **not** a service-wide trace search API. When
service detail returns real trace references, the Open Traces link includes an
observed trace ID and its UTC observation window. The trace still displays **all**
returned spans, including other services, preserving distributed parentage; the
selected service is identified among them. Without an observed reference, Traces
shows the service context and waits for a trace ID; it does not invent results.

An explicitly empty `environment=` must be distinguished from an absent
`environment` query parameter by both Logs and Metrics APIs. Parameterized
ClickHouse filters and all existing bounded query limits remain unchanged.

Browser acceptance (not yet recorded): verify these links using a newly emitted
multi-service M6 trace, test `(empty)` environment, Clear, back/forward/reload,
project switching, error/empty states and narrow mobile viewport. Record actual
results in M6 acceptance checklists without exposing project credentials.
