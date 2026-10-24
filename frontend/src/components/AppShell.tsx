import { useEffect, useState, type PropsWithChildren } from "react";
import { useQuery } from "@tanstack/react-query";
import { NavLink, matchPath, useLocation, useNavigate } from "react-router-dom";

import { getOrganizations, getProjects } from "../api/resources";
import type { User } from "../types";
import { isWorkspaceSection, WORKSPACE_SECTIONS, workspacePath } from "../workspace";
import { WorkspaceSelectionContext } from "../workspaceSelection";
import {
  readWorkspacePreference, reconcileWorkspacePreference, writeWorkspacePreference,
  type WorkspacePreference,
} from "../workspacePersistence";

interface AppShellProps extends PropsWithChildren {
  user: User;
  onLogout: () => Promise<void>;
}

const SECTION_LABELS = {
  overview: "Overview",
  services: "Services",
  infrastructure: "Infrastructure",
  metrics: "Metrics",
  logs: "Logs",
  traces: "Traces",
  dashboards: "Dashboards",
  alerts: "Alerts",
  settings: "Settings",
} as const;

export function AppShell({ user, onLogout, children }: AppShellProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const organizations = useQuery({ queryKey: ["organizations"], queryFn: getOrganizations });
  const projects = useQuery({ queryKey: ["projects"], queryFn: getProjects });
  const [saved, setSaved] = useState(() => readWorkspacePreference(user.id));
  const workspaceMatch =
    matchPath("/orgs/:organizationSlug/projects/:projectSlug", location.pathname) ??
    matchPath("/orgs/:organizationSlug/projects/:projectSlug/:section", location.pathname);
  const onWorkspaceRoute = workspaceMatch !== null;
  const routeOrganization = (organizations.data ?? []).find(
    (item) => item.slug === workspaceMatch?.params.organizationSlug,
  );
  const routeProject = (projects.data ?? []).find(
    (item) => item.slug === workspaceMatch?.params.projectSlug &&
      item.organization_id === routeOrganization?.id,
  );
  // Client preferences never grant access: only server-returned memberships/projects do.
  const resolved = organizations.isSuccess && projects.isSuccess
    ? reconcileWorkspacePreference(organizations.data, projects.data, saved)
    : saved;
  // Explicit deep links are authoritative: never silently redirect a foreign or invalid URL.
  const organization = onWorkspaceRoute
    ? routeOrganization
    : (organizations.data ?? []).find((item) => item.id === resolved.organizationId);
  const project = onWorkspaceRoute
    ? routeProject
    : (projects.data ?? []).find(
        (item) => item.id === resolved.projectId && item.organization_id === organization?.id,
      );
  const activeSection = matchPath(
    "/orgs/:organizationSlug/projects/:projectSlug/:section",
    location.pathname,
  )?.params.section;

  const routeOrganizationId = routeOrganization?.id ?? "";
  const routeProjectId = routeProject?.id ?? "";
  useEffect(() => {
    if (!organizations.isSuccess || !projects.isSuccess) return;
    // Do not overwrite the last authorized choice when an explicit URL is invalid.
    if (onWorkspaceRoute && (!routeOrganizationId || !routeProjectId)) return;
    const next: WorkspacePreference = onWorkspaceRoute
      ? { organizationId: routeOrganizationId, projectId: routeProjectId, stale: false }
      : {
          organizationId: resolved.organizationId,
          projectId: resolved.projectId,
          stale: resolved.stale,
        };
    setSaved((old) => old.organizationId === next.organizationId &&
      old.projectId === next.projectId && old.stale === next.stale ? old : next);
    writeWorkspacePreference(user.id, next);
  }, [
    organizations.isSuccess, projects.isSuccess, onWorkspaceRoute,
    routeOrganizationId, routeProjectId, resolved.organizationId, resolved.projectId,
    resolved.stale, user.id,
  ]);

  function selectOrganization(organizationId: string) {
    const firstProject = (projects.data ?? []).find(
      (item) => item.organization_id === organizationId,
    );
    setSaved({ organizationId, projectId: firstProject?.id ?? "", stale: false });
    navigate("/");
  }

  function selectProject(projectId: string) {
    const nextProject = (projects.data ?? []).find(
      (item) => item.id === projectId && item.organization_id === organization?.id,
    );
    if (!nextProject || !organization) return;
    setSaved({ organizationId: organization.id, projectId: nextProject.id, stale: false });
    navigate(workspacePath(
      organization.slug, nextProject.slug,
      isWorkspaceSection(activeSection) ? activeSection : "overview",
    ));
  }

  const projectsInOrganization = (projects.data ?? []).filter(
    (item) => item.organization_id === organization?.id,
  );
  const hasValidSelection = Boolean(organization && project && !organizations.isError && !projects.isError);
  const contextLoading = organizations.isPending || projects.isPending;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <NavLink className="brand" to="/" aria-label="Sentrix overview">Sentrix</NavLink>
        <nav aria-label="Primary navigation">
          <NavLink className="nav-item" end to="/">Organizations & projects</NavLink>
          {hasValidSelection && organization && project
            ? WORKSPACE_SECTIONS.map((section) => (
                <NavLink
                  key={section}
                  className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
                  end={section === "overview"}
                  to={workspacePath(organization.slug, project.slug, section)}
                >
                  {SECTION_LABELS[section]}
                </NavLink>
              ))
            : null}
          <NavLink className="nav-item" to="/docs/telemetry-setup">Documentation</NavLink>
        </nav>
      </aside>
      <main className="main">
        <header className="topbar">
          <div className="topbar-context" aria-label="Global workspace selection">
            <label>
              <select
                aria-label="Organization"
                value={organization?.id ?? ""}
                onChange={(event) => selectOrganization(event.target.value)}
                disabled={contextLoading || organizations.isError}
              >
                <option value="">Select organization</option>
                {(organizations.data ?? []).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </label>
            <label>
              <select
                aria-label="Project"
                value={project?.id ?? ""}
                onChange={(event) => selectProject(event.target.value)}
                disabled={!organization || contextLoading || projects.isError}
              >
                <option value="">Select project</option>
                {projectsInOrganization.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </label>
            {organizations.isError || projects.isError ? (
              <span className="error" role="alert">Unable to load workspace choices.</span>
            ) : null}
            {!onWorkspaceRoute && !contextLoading && !organizations.isError &&
              !projects.isError && resolved.stale ? (
                <span className="muted" role="status">
                  Saved workspace was unavailable. First available selection restored.
                </span>
              ) : null}
          </div>
          <div className="topbar-account">
            <strong>{user.username}</strong>
            <button className="button secondary" onClick={() => void onLogout()} type="button">Sign out</button>
          </div>
        </header>
        <WorkspaceSelectionContext.Provider value={{ organizationId: organization?.id ?? "", selectOrganization }}>
          <section className="content">{children}</section>
        </WorkspaceSelectionContext.Provider>
      </main>
    </div>
  );
}
