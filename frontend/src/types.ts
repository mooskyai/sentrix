export interface User {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
}

export type OrganizationRole = "owner" | "admin" | "editor" | "viewer";

export interface Organization {
  id: string;
  name: string;
  slug: string;
  role: OrganizationRole;
  created_at: string;
  updated_at: string;
}

export interface Project {
  id: string;
  organization_id: string;
  name: string;
  slug: string;
  created_by: number | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectApiKey {
  id: string;
  project_id: string;
  name: string;
  prefix: string;
  scopes: string[];
  created_by: number | null;
  expires_at: string | null;
  last_used_at: string | null;
  revoked_at: string | null;
  created_at: string;
}

export interface ProjectApiKeyCreateResult extends ProjectApiKey {
  secret: string;
}

export interface MetricCatalogItem {
  name: string;
  description: string;
  unit: string;
  metric_types: string[];
  value_types: string[];
  supports_numeric_series: boolean;
  point_count: number;
  last_seen_at: string;
}

export interface MetricCatalogResponse {
  project_id: string;
  start: string;
  end: string;
  metrics: MetricCatalogItem[];
}

export interface MetricSeriesPoint {
  timestamp: string;
  service_name: string;
  environment: string;
  metric_type: string;
  aggregation_temporality: string;
  is_monotonic: boolean;
  value_type: string;
  value: number;
  attributes: Record<string, string>;
}

export interface MetricSeriesResponse {
  project_id: string;
  metric_name: string;
  start: string;
  end: string;
  filters: {
    service_name: string | null;
    environment: string | null;
  };
  points: MetricSeriesPoint[];
  truncated: boolean;
}

export type DashboardPanelTimeRange = "1h" | "6h" | "24h" | "7d";

export interface ProjectDashboardPanel {
  id: string;
  project_id: string;
  title: string;
  metric_name: string;
  time_range: DashboardPanelTimeRange;
  service_name: string;
  environment: string;
  position: number;
  created_by: number | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectDashboardPanelCreateInput {
  title: string;
  metric_name: string;
  time_range: DashboardPanelTimeRange;
  service_name: string;
  environment: string;
}

export type AlertRuleTimeRange = "1h" | "6h" | "24h" | "7d";
export type AlertRuleComparator = "gt" | "gte" | "lt" | "lte";
export type AlertRuleStatus = "pending" | "ok" | "firing" | "no_data" | "error" | "disabled";

export interface AlertRuleState {
  status: AlertRuleStatus;
  evaluated_at: string | null;
  state_changed_at: string | null;
  source_timestamp: string | null;
  error_code: string;
  updated_at: string;
}

export interface AlertRule {
  id: string;
  project_id: string;
  name: string;
  metric_name: string;
  time_range: AlertRuleTimeRange;
  service_name: string;
  environment: string;
  comparator: AlertRuleComparator;
  threshold: number;
  enabled: boolean;
  state: AlertRuleState | null;
  created_by: number | null;
  created_at: string;
  updated_at: string;
}

export interface AlertRuleWriteInput {
  name: string;
  metric_name: string;
  time_range: AlertRuleTimeRange;
  service_name: string;
  environment: string;
  comparator: AlertRuleComparator;
  threshold: number;
  enabled: boolean;
}

export interface LogSearchRow {
  timestamp: string;
  observed_timestamp: string | null;
  service_name: string;
  environment: string;
  scope_name: string;
  scope_version: string;
  scope_attributes: Record<string, string>;
  resource_attributes: Record<string, string>;
  severity_number: number;
  severity_text: string;
  body: string;
  event_name: string;
  trace_id: string | null;
  span_id: string | null;
  flags: number;
  dropped_attributes_count: number;
  attributes: Record<string, string>;
}

export interface LogSearchResponse {
  project_id: string;
  start: string;
  end: string;
  filters: {
    service_name: string | null;
    environment: string | null;
    min_severity_number: number | null;
    body_contains: string | null;
    trace_id: string | null;
  };
  logs: LogSearchRow[];
  truncated: boolean;
}

export interface TraceSpan {
  start_time: string;
  end_time: string;
  duration_ns: number;
  service_name: string;
  environment: string;
  scope_name: string;
  scope_version: string;
  scope_attributes: Record<string, string>;
  resource_attributes: Record<string, string>;
  trace_id: string | null;
  span_id: string | null;
  parent_span_id: string | null;
  trace_state: string;
  span_name: string;
  span_kind: number;
  status_code: number;
  status_message: string;
  flags: number;
  dropped_attributes_count: number;
  dropped_events_count: number;
  dropped_links_count: number;
  attributes: Record<string, string>;
  events_json: string;
  links_json: string;
}

export interface TraceDetailResponse {
  project_id: string;
  trace_id: string;
  start: string;
  end: string;
  spans: TraceSpan[];
  truncated: boolean;
}

export interface ObservedResourceSet {
  attributes: Record<string, string>;
  first_seen: string;
  last_seen: string;
  metric_points: number;
  log_records: number;
  span_records: number;
}

export interface InfrastructureResponse {
  project_id: string;
  start: string;
  end: string;
  limit: number;
  truncated: boolean;
  observations: ObservedResourceSet[];
}

export interface ObservedService {
  service_name: string;
  environment: string;
  first_seen: string;
  last_seen: string;
  metric_points: number;
  log_records: number;
  span_records: number;
  signals: Array<"metrics" | "logs" | "traces">;
}

export interface ServiceCatalogResponse {
  project_id: string;
  start: string;
  end: string;
  limit: number;
  truncated: boolean;
  services: ObservedService[];
}
export interface ServiceMetricName {
  name: string;
  point_count: number;
}

export interface ServiceErrorLog {
  timestamp: string;
  severity_number: number;
  severity_text: string;
  body: string;
  trace_id: string | null;
}

export interface ServiceTraceReference {
  trace_id: string;
  last_seen: string;
  span_records: number;
}

export interface ServiceDetailResponse {
  project_id: string;
  service_name: string;
  environment: string;
  start: string;
  end: string;
  metric_names: ServiceMetricName[];
  error_logs: ServiceErrorLog[];
  trace_references: ServiceTraceReference[];
  truncated: {
    metric_names: boolean;
    error_logs: boolean;
    trace_references: boolean;
  };
}

export interface ObservedServiceRelationship {
  from_service: string;
  from_environment: string;
  to_service: string;
  to_environment: string;
  span_pairs: number;
  trace_ids: string[];
}

export interface ServiceMapResponse {
  project_id: string;
  start: string;
  end: string;
  limit: number;
  truncated: boolean;
  span_scan_truncated: boolean;
  scanned_spans: number;
  relationships: ObservedServiceRelationship[];
}
