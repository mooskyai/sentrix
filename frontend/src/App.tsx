import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { getMe, login, logout } from "./api/resources";
import { AppShell } from "./components/AppShell";
import { LoginPage } from "./pages/LoginPage";
import { OverviewPage } from "./pages/OverviewPage";

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
      <OverviewPage />
    </AppShell>
  );
}
