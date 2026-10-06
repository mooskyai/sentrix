import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, Route, Routes } from "react-router-dom";

import { getMe, login, logout } from "./api/resources";
import { AppShell } from "./components/AppShell";
import { LoginPage } from "./pages/LoginPage";
import { OverviewPage } from "./pages/OverviewPage";
import { ProjectWorkspacePage } from "./pages/ProjectWorkspacePage";

function NotFoundPage() {
  return (
    <section className="panel narrow-panel">
      <p className="eyebrow">Not found</p>
      <h1>Workspace unavailable</h1>
      <p className="muted">
        The requested Sentrix workspace does not exist or is not available to your account.
      </p>
      <Link className="button inline-button" to="/">
        Back to overview
      </Link>
    </section>
  );
}

export default function App() {
  const queryClient = useQueryClient();
  const [loginError, setLoginError] = useState<string | null>(null);
  const me = useQuery({ queryKey: ["me"], queryFn: getMe, retry: false });

  if (me.isPending) return <div className="center-state">Loading workspace…</div>;

  if (me.isError) {
    return (
      <LoginPage
        error={loginError}
        onLogin={async (username, password) => {
          setLoginError(null);
          try {
            await login(username, password);
            await queryClient.invalidateQueries({ queryKey: ["me"] });
          } catch (error) {
            setLoginError(error instanceof Error ? error.message : "Login failed.");
          }
        }}
      />
    );
  }

  return (
    <AppShell
      user={me.data}
      onLogout={async () => {
        await logout();
        queryClient.clear();
        window.location.reload();
      }}
    >
      <Routes>
        <Route path="/" element={<OverviewPage />} />
        <Route path="/orgs/:organizationSlug/projects/:projectSlug" element={<ProjectWorkspacePage />} />
        <Route
          path="/orgs/:organizationSlug/projects/:projectSlug/:section"
          element={<ProjectWorkspacePage />}
        />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </AppShell>
  );
}
