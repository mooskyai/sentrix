import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AppShell } from "./AppShell";

const user = { id: 1, username: "udit", email: "", first_name: "", last_name: "" };

describe("AppShell", () => {
  it("renders the signed-in user and content", () => {
    render(
      <MemoryRouter>
        <AppShell user={user} onLogout={vi.fn()}>
          <div>Workspace content</div>
        </AppShell>
      </MemoryRouter>,
    );

    expect(screen.getByText("Sentrix")).toBeInTheDocument();
    expect(screen.getByText("udit")).toBeInTheDocument();
    expect(screen.getByText("Workspace content")).toBeInTheDocument();
    expect(screen.queryByText(/\bV1\b/i)).not.toBeInTheDocument();
  });

  it("enables project workspace navigation when the route has tenant context", () => {
    render(
      <MemoryRouter initialEntries={["/orgs/acme/projects/api/logs"]}>
        <AppShell user={user} onLogout={vi.fn()}>
          <div>Logs content</div>
        </AppShell>
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "Metrics" })).toHaveAttribute(
      "href",
      "/orgs/acme/projects/api/metrics",
    );
    expect(screen.getByRole("link", { name: "Settings" })).toHaveAttribute(
      "href",
      "/orgs/acme/projects/api/settings",
    );
    expect(screen.getByRole("link", { name: "Logs" })).toHaveClass("active");
  });
});
