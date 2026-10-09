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
