import type { PropsWithChildren } from "react";
import type { User } from "../types";

interface AppShellProps extends PropsWithChildren {
  user: User;
  onLogout: () => Promise<void>;
}

export function AppShell({ user, onLogout, children }: AppShellProps) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">Sentrix</div>
        <nav aria-label="Primary navigation">
          <a className="nav-item active" href="#overview">Overview</a>
          <span className="nav-item disabled">Metrics</span>
          <span className="nav-item disabled">Logs</span>
          <span className="nav-item disabled">Traces</span>
          <span className="nav-item disabled">Dashboards</span>
          <span className="nav-item disabled">Alerts</span>
        </nav>
      </aside>
      <main className="main">
        <header className="topbar">
          <div>
            <strong>{user.username}</strong>
            <span className="muted"> · control-plane V1</span>
          </div>
          <button className="button secondary" onClick={() => void onLogout()} type="button">
            Sign out
          </button>
        </header>
        <section className="content">{children}</section>
      </main>
    </div>
  );
}
