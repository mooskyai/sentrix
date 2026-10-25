import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { getOrganizations, getProjects } from "../api/resources";
import { AlertsWorkspace } from "../components/AlertsWorkspace";
import { ConnectionDiagnosticsPanel } from "../components/ConnectionDiagnosticsPanel";
import { DashboardPanels } from "../components/DashboardPanels";
import { InfrastructureWorkspace } from "../components/InfrastructureWorkspace";
import { LogsExplorer } from "../components/LogsExplorer";
import { MetricsExplorer } from "../components/MetricsExplorer";
import { ProjectApiKeysPanel } from "../components/ProjectApiKeysPanel";
import { ServicesWorkspace } from "../components/ServicesWorkspace";
import { TraceExplorer } from "../components/TraceExplorer";
import {
  canWriteProjects,
  isWorkspaceSection,
  resolveWorkspace,
  workspacePath,
  type WorkspaceSection,
} from "../workspace";

const SECTION_COPY: Record<WorkspaceSection, { title: string; description: string }> = {
  overview: {
    title: "Project workspace",
    description: "Tenant and project context are established and ready for telemetry features.",
  },
  services: {
    title: "Services",
    description: "Discover services observed through project-scoped OpenTelemetry signals.",
  },
  infrastructure: {
    title: "Infrastructure",
    description: "Explore host and Kubernetes attributes observed in this project’s telemetry.",
  },
  metrics: {
    title: "Metrics",
    description: "Explore real numeric gauge and sum points from this project’s telemetry.",
  },
  logs: {
    title: "Logs",
    description: "Search real project logs with bounded time, severity, text, and correlation filters.",
  },
  traces: {
    title: "Traces",
    description: "Inspect project-scoped traces with raw span parentage, timing, status, and attributes.",
  },
  dashboards: {
    title: "Dashboards",
    description: "View project-scoped metric panels pinned from the Metrics explorer.",
  },
  alerts: {
    title: "Alerts",
    description: "Manage project alert rules and inspect their persisted current evaluation state.",
  },
  settings: {
    title: "Project settings",
    description: "Manage credentials used by collectors and telemetry exporters for this project.",
  },
};

export function ProjectWorkspacePage() {
  const { organizationSlug = "", projectSlug = "", section } = useParams();
  const organizations = useQuery({ queryKey: ["organizations"], queryFn: getOrganizations });
  const projects = useQuery({ queryKey: ["projects"], queryFn: getProjects });
  const activeSection = section === undefined ? "overview" : section;

  const workspace = useMemo(
    () =>
      resolveWorkspace(
        organizations.data ?? [],
        projects.data ?? [],
        organizationSlug,
        projectSlug,
      ),
    [organizations.data, projects.data, organizationSlug, projectSlug],
  );

  if (organizations.isPending || projects.isPending) {
    return <div className="panel">Loading project workspace…</div>;
  }

  if (organizations.isError || projects.isError) {
    return (
      <section className="panel narrow-panel">
        <p className="eyebrow">Workspace error</p>
        <h1>Unable to load project context</h1>
        <p className="error">
          {organizations.error?.message ?? projects.error?.message ?? "Unable to load workspace."}
        </p>
      </section>
    );
  }

  if (!workspace || !isWorkspaceSection(activeSection)) {
    return (
      <section className="panel narrow-panel">
        <p className="eyebrow">Not found</p>
        <h1>Workspace unavailable</h1>
        <p className="muted">
          This project does not exist or is not available through your organization memberships.
        </p>
        <Link className="button inline-button" to="/">
          Back to overview
        </Link>
      </section>
    );
  }

  const copy = SECTION_COPY[activeSection];
  const writable = canWriteProjects(workspace.organization.role);

  return (
    <>
      <div className="page-heading workspace-heading">
        <div>
          <h1>{activeSection === "overview" ? workspace.project.name : copy.title}</h1>
          <p className="muted">{copy.description}</p>
        </div>
        <span className={`role-badge ${writable ? "write" : "read-only"}`}>
          {workspace.organization.role} · {writable ? "write" : "read only"}
        </span>
      </div>

      <section
        className={`workspace-section ${
          activeSection === "overview" || activeSection === "dashboards" || activeSection === "alerts"
            ? "workspace-section--collection"
            : "workspace-section--surface"
        }`}
        aria-label="Project workspace content"
      >
        {activeSection === "overview" ? <h2>{copy.title}</h2> : null}
        {activeSection === "overview" ? (
          <div className="workspace-grid">
            <div className="workspace-card">
              <span className="muted">Organization</span>
              <strong>{workspace.organization.name}</strong>
              <small>{workspace.organization.slug}</small>
            </div>
            <div className="workspace-card">
              <span className="muted">Project</span>
              <strong>{workspace.project.name}</strong>
              <small>{workspace.project.slug}</small>
            </div>
            <div className="workspace-card">
              <span className="muted">Project ID</span>
              <strong className="mono">{workspace.project.id}</strong>
              <small>Use this immutable ID at backend/data-plane boundaries.</small>
            </div>
            <div className="workspace-card">
              <span className="muted">Access</span>
              <strong>{writable ? "Read & write" : "Read only"}</strong>
              <small>Authorization remains enforced by Django.</small>
            </div>
          </div>
        ) : activeSection === "services" ? (
          <ServicesWorkspace
            key={workspace.project.id}
            projectId={workspace.project.id}
            metricsPath={workspacePath(workspace.organization.slug, workspace.project.slug, "metrics")}
            logsPath={workspacePath(workspace.organization.slug, workspace.project.slug, "logs")}
            tracesPath={workspacePath(workspace.organization.slug, workspace.project.slug, "traces")}
          />
        ) : activeSection === "infrastructure" ? (
          <InfrastructureWorkspace key={workspace.project.id} projectId={workspace.project.id} />
        ) : activeSection === "metrics" ? (
          <MetricsExplorer
            key={workspace.project.id}
            projectId={workspace.project.id}
            canManageDashboard={writable}
          />
        ) : activeSection === "logs" ? (
          <LogsExplorer
            key={workspace.project.id}
            projectId={workspace.project.id}
            tracePath={workspacePath(workspace.organization.slug, workspace.project.slug, "traces")}
          />
        ) : activeSection === "traces" ? (
          <TraceExplorer key={workspace.project.id} projectId={workspace.project.id} />
        ) : activeSection === "dashboards" ? (
          <DashboardPanels
            key={workspace.project.id}
            projectId={workspace.project.id}
            canManage={writable}
          />
        ) : activeSection === "alerts" ? (
          <AlertsWorkspace
            key={`${workspace.project.id}:${writable ? "manage" : "read"}`}
            projectId={workspace.project.id}
            canManage={writable}
          />
        ) : activeSection === "settings" ? (
          <>
            <ConnectionDiagnosticsPanel key={`diagnostics:${workspace.project.id}`} projectId={workspace.project.id} />
            <ProjectApiKeysPanel
              key={`${workspace.project.id}:${writable ? "manage" : "read"}`}
              projectId={workspace.project.id}
              canManage={writable}
            />
          </>
        ) : (
          <div className="empty-feature">
            <strong>Explorer UI is not connected yet.</strong>
            <p className="muted">{copy.description}</p>
            <p className="muted">
              This page intentionally contains no synthetic telemetry. Real data will appear only after
              tenant-safe query APIs and explorer behavior are implemented.
            </p>
          </div>
        )}
      </section>
    </>
  );
}
