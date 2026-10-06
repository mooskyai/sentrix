import type { PropsWithChildren } from "react";
import { NavLink, matchPath, useLocation } from "react-router-dom";

import type { User } from "../types";
import { WORKSPACE_SECTIONS, workspacePath } from "../workspace";

interface AppShellProps extends PropsWithChildren {
  user: User;
  onLogout: () => Promise<void>;
}

const SECTION_LABELS = {
  overview: "Overview",
  metrics: "Metrics",
  logs: "Logs",
  traces: "Traces",
  dashboards: "Dashboards",
  alerts: "Alerts",
  settings: "Settings",
} as const;

export function AppShell({ user, onLogout, children }: AppShellProps) {
  const location = useLocation();
  const workspaceMatch =
    matchPath("/orgs/:organizationSlug/projects/:projectSlug", location.pathname) ??
    matchPath("/orgs/:organizationSlug/projects/:projectSlug/:section", location.pathname);
  const organizationSlug = workspaceMatch?.params.organizationSlug;
  const projectSlug = workspaceMatch?.params.projectSlug;
  const hasWorkspaceContext = Boolean(organizationSlug && projectSlug);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <NavLink className="brand" to="/" aria-label="Sentrix overview">
          Sentrix
        </NavLink>
        <nav aria-label="Primary navigation">
          {hasWorkspaceContext && organizationSlug && projectSlug ? (
            WORKSPACE_SECTIONS.map((section) => (
              <NavLink
                key={section}
                className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
                end={section === "overview"}
                to={workspacePath(organizationSlug, projectSlug, section)}
              >
                {SECTION_LABELS[section]}
              </NavLink>
            ))
          ) : (
            <>
              <NavLink className="nav-item" end to="/">
                Overview
              </NavLink>
              <span className="nav-item disabled">Metrics</span>
              <span className="nav-item disabled">Logs</span>
              <span className="nav-item disabled">Traces</span>
              <span className="nav-item disabled">Dashboards</span>
              <span className="nav-item disabled">Alerts</span>
              <span className="nav-item disabled">Settings</span>
            </>
          )}
        </nav>
      </aside>
      <main className="main">
        <header className="topbar">
          <strong>{user.username}</strong>
          <button className="button secondary" onClick={() => void onLogout()} type="button">
            Sign out
          </button>
        </header>
        <section className="content">{children}</section>
      </main>
    </div>
  );
}
