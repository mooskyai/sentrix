import { useEffect, useState, type PropsWithChildren } from "react";
import { useQuery } from "@tanstack/react-query";
import { NavLink, matchPath, useLocation, useNavigate } from "react-router-dom";

import { getOrganizations, getProjects } from "../api/resources";
import type { User } from "../types";
import { isWorkspaceSection, WORKSPACE_SECTIONS, workspacePath } from "../workspace";
import { WorkspaceSelectionContext } from "../workspaceSelection";

interface AppShellProps extends PropsWithChildren {
  user: User;
  onLogout: () => Promise<void>;
}

const SECTION_LABELS = {
  overview: "Overview",
  services: "Services",
  metrics: "Metrics",
  logs: "Logs",
  traces: "Traces",
  dashboards: "Dashboards",
  alerts: "Alerts",
  settings: "Settings",
} as const;

function storedSelection(userId: number): { organizationId: string; projectId: string } {
  try {
    const value = JSON.parse(sessionStorage.getItem(`sentrix.workspace.${userId}`) ?? "null") as unknown;
    if (value && typeof value === "object" && "organizationId" in value && "projectId" in value) {
      const selected = value as Record<string, unknown>;
      return {
        organizationId: typeof selected.organizationId === "string" ? selected.organizationId : "",
        projectId: typeof selected.projectId === "string" ? selected.projectId : "",
      };
    }
  } catch { /* Invalid or disabled browser storage is treated as no selection. */ }
  return { organizationId: "", projectId: "" };
}

export function AppShell({ user, onLogout, children }: AppShellProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const organizations = useQuery({ queryKey: ["organizations"], queryFn: getOrganizations });
  const projects = useQuery({ queryKey: ["projects"], queryFn: getProjects });
  const [saved, setSaved] = useState(() => storedSelection(user.id));
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
  // A route never authorizes a workspace: only server-returned memberships and projects do.
  const organization = onWorkspaceRoute
    ? routeOrganization
    : (organizations.data ?? []).find((item) => item.id === saved.organizationId);
  const project = onWorkspaceRoute
    ? routeProject
    : (projects.data ?? []).find(
        (item) => item.id === saved.projectId && item.organization_id === organization?.id,
      );
  const activeSection = matchPath(
    "/orgs/:organizationSlug/projects/:projectSlug/:section",
    location.pathname,
  )?.params.section;

  const routeOrganizationId = routeOrganization?.id ?? "";
  const routeProjectId = routeProject?.id ?? "";
  useEffect(() => {
    if (!onWorkspaceRoute || !routeOrganizationId || !routeProjectId) return;
    const next = { organizationId: routeOrganizationId, projectId: routeProjectId };
    // Sync the header when navigation originates from browser history or a deep link.
    setSaved((old) => old.organizationId === next.organizationId && old.projectId === next.projectId ? old : next);
  }, [onWorkspaceRoute, routeOrganizationId, routeProjectId]);

  useEffect(() => {
    try { sessionStorage.setItem(`sentrix.workspace.${user.id}`, JSON.stringify(saved)); }
    catch { /* Browser storage may be unavailable. */ }
  }, [saved, user.id]);

  function selectOrganization(organizationId: string) {
    setSaved({ organizationId, projectId: "" });
    navigate("/");
  }

  function selectProject(projectId: string) {
    const nextProject = (projects.data ?? []).find(
      (item) => item.id === projectId && item.organization_id === organization?.id,
    );
    if (!nextProject || !organization) return;
    setSaved({ organizationId: organization.id, projectId: nextProject.id });
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
        </nav>
      </aside>
      <main className="main">
        <header className="topbar">
          <div className="topbar-context" aria-label="Global workspace selection">
            <label>
              <span>Organization</span>
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
              <span>Project</span>
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
