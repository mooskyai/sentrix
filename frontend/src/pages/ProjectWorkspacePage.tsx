import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";

import { getOrganizations, getProjects } from "../api/resources";
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
  metrics: {
    title: "Metrics",
    description: "Metric ingestion and exploration arrive with the telemetry data-plane milestone.",
  },
  logs: {
    title: "Logs",
    description: "Log ingestion and search arrive with the telemetry data-plane milestone.",
  },
  traces: {
    title: "Traces",
    description: "Trace ingestion and service correlation arrive with the telemetry data-plane milestone.",
  },
  dashboards: {
    title: "Dashboards",
    description: "Dashboard authoring follows the first queryable telemetry signals.",
  },
  alerts: {
    title: "Alerts",
    description: "Alert evaluation follows queryable telemetry and notification infrastructure.",
  },
};

export function ProjectWorkspacePage() {
  const navigate = useNavigate();
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

  const organizationProjects = (projects.data ?? []).filter(
    (project) => project.organization_id === workspace.organization.id,
  );
  const copy = SECTION_COPY[activeSection];
  const writable = canWriteProjects(workspace.organization.role);

  return (
    <>
      <div className="page-heading workspace-heading">
        <div>
          <p className="eyebrow">{workspace.organization.name}</p>
          <h1>{workspace.project.name}</h1>
          <p className="muted">{copy.description}</p>
        </div>
        <span className={`role-badge ${writable ? "write" : "read-only"}`}>
          {workspace.organization.role} · {writable ? "write" : "read only"}
        </span>
      </div>

      <section className="panel workspace-toolbar" aria-label="Workspace switcher">
        <label>
          <span>Organization</span>
          <select
            value={workspace.organization.id}
            onChange={(event) => {
              const nextOrganization = (organizations.data ?? []).find(
                (organization) => organization.id === event.target.value,
              );
              if (!nextOrganization) return;
              const nextProject = (projects.data ?? []).find(
                (project) => project.organization_id === nextOrganization.id,
              );
              navigate(
                nextProject
                  ? workspacePath(nextOrganization.slug, nextProject.slug)
                  : "/",
              );
            }}
          >
            {(organizations.data ?? []).map((organization) => (
              <option key={organization.id} value={organization.id}>
                {organization.name}
              </option>
            ))}
          </select>
        </label>

        <label>
          <span>Project</span>
          <select
            value={workspace.project.id}
            onChange={(event) => {
              const nextProject = organizationProjects.find(
                (project) => project.id === event.target.value,
              );
              if (nextProject) {
                navigate(workspacePath(workspace.organization.slug, nextProject.slug, activeSection));
              }
            }}
          >
            {organizationProjects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </label>
      </section>

      <section className="panel workspace-section">
        <p className="eyebrow">{activeSection}</p>
        <h2>{copy.title}</h2>
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
        ) : (
          <div className="empty-feature">
            <strong>Workspace route ready.</strong>
            <p className="muted">{copy.description}</p>
            <p className="muted">
              This page intentionally contains no synthetic telemetry. The next data-plane milestone will
              connect real signals here.
            </p>
          </div>
        )}
      </section>
    </>
  );
}
