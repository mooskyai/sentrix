import { api, ensureCsrf } from "./client";
import type {
  MetricCatalogResponse,
  MetricSeriesResponse,
  Organization,
  Project,
  ProjectApiKey,
  ProjectApiKeyCreateResult,
  ProjectDashboardPanel,
  ProjectDashboardPanelCreateInput,
  User,
} from "../types";

export async function login(username: string, password: string): Promise<User> {
  await ensureCsrf();
  return api<User>("/auth/login/", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export function logout(): Promise<void> {
  return api<void>("/auth/logout/", { method: "POST" });
}

export function getMe(): Promise<User> {
  return api<User>("/auth/me/");
}

export function getOrganizations(): Promise<Organization[]> {
  return api<Organization[]>("/organizations/");
}

export function createOrganization(input: { name: string; slug: string }): Promise<Organization> {
  return api<Organization>("/organizations/", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getProjects(): Promise<Project[]> {
  return api<Project[]>("/projects/");
}

export function createProject(input: {
  organization_id: string;
  name: string;
  slug: string;
}): Promise<Project> {
  return api<Project>("/projects/", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getProjectApiKeys(projectId: string): Promise<ProjectApiKey[]> {
  return api<ProjectApiKey[]>(`/projects/${encodeURIComponent(projectId)}/api-keys/`);
}

export function createProjectApiKey(
  projectId: string,
  input: { name: string; expires_at: string | null },
): Promise<ProjectApiKeyCreateResult> {
  return api<ProjectApiKeyCreateResult>(`/projects/${encodeURIComponent(projectId)}/api-keys/`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function revokeProjectApiKey(projectId: string, apiKeyId: string): Promise<void> {
  return api<void>(
    `/projects/${encodeURIComponent(projectId)}/api-keys/${encodeURIComponent(apiKeyId)}/`,
    { method: "DELETE" },
  );
}

interface MetricWindowQuery {
  start: string;
  end: string;
}

interface MetricSeriesQuery extends MetricWindowQuery {
  metric_name: string;
  service_name?: string;
  environment?: string;
  limit?: number;
}

function metricQueryString(query: Record<string, string | number | undefined>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== "") params.set(key, String(value));
  }
  return params.toString();
}

export function getMetricCatalog(
  projectId: string,
  query: MetricWindowQuery,
): Promise<MetricCatalogResponse> {
  const params = metricQueryString({ start: query.start, end: query.end });
  return api<MetricCatalogResponse>(
    `/projects/${encodeURIComponent(projectId)}/metrics/catalog/?${params}`,
  );
}

export function getMetricSeries(
  projectId: string,
  query: MetricSeriesQuery,
): Promise<MetricSeriesResponse> {
  const params = metricQueryString({
    metric_name: query.metric_name,
    start: query.start,
    end: query.end,
    service_name: query.service_name,
    environment: query.environment,
    limit: query.limit,
  });
  return api<MetricSeriesResponse>(
    `/projects/${encodeURIComponent(projectId)}/metrics/series/?${params}`,
  );
}

export function getProjectDashboardPanels(projectId: string): Promise<ProjectDashboardPanel[]> {
  return api<ProjectDashboardPanel[]>(
    `/projects/${encodeURIComponent(projectId)}/dashboard-panels/`,
  );
}

export function createProjectDashboardPanel(
  projectId: string,
  input: ProjectDashboardPanelCreateInput,
): Promise<ProjectDashboardPanel> {
  return api<ProjectDashboardPanel>(
    `/projects/${encodeURIComponent(projectId)}/dashboard-panels/`,
    {
      method: "POST",
      body: JSON.stringify(input),
    },
  );
}

export function deleteProjectDashboardPanel(projectId: string, panelId: string): Promise<void> {
  return api<void>(
    `/projects/${encodeURIComponent(projectId)}/dashboard-panels/${encodeURIComponent(panelId)}/`,
    { method: "DELETE" },
  );
}

export interface LogSearchQuery {
  start: string;
  end: string;
  limit?: number;
  service_name?: string;
  environment?: string;
  min_severity_number?: number;
  body_contains?: string;
  trace_id?: string;
}

export function getLogs(
  projectId: string,
  query: LogSearchQuery,
): Promise<import("../types").LogSearchResponse> {
  const params = metricQueryString({
    start: query.start,
    end: query.end,
    limit: query.limit,
    service_name: query.service_name,
    environment: query.environment,
    min_severity_number: query.min_severity_number,
    body_contains: query.body_contains,
    trace_id: query.trace_id,
  });
  return api<import("../types").LogSearchResponse>(
    `/projects/${encodeURIComponent(projectId)}/logs/search/?${params}`,
  );
}

export interface TraceDetailQuery {
  start: string;
  end: string;
  limit?: number;
}

export function getTrace(
  projectId: string,
  traceId: string,
  query: TraceDetailQuery,
): Promise<import("../types").TraceDetailResponse> {
  const params = metricQueryString({
    start: query.start,
    end: query.end,
    limit: query.limit,
  });
  return api<import("../types").TraceDetailResponse>(
    `/projects/${encodeURIComponent(projectId)}/traces/${encodeURIComponent(traceId)}/?${params}`,
  );
}
