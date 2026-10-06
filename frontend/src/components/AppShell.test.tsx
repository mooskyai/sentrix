import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AppShell } from "./AppShell";


describe("AppShell", () => {
  it("renders the signed-in user and content", () => {
    render(
      <AppShell
        user={{ id: 1, username: "udit", email: "", first_name: "", last_name: "" }}
        onLogout={vi.fn()}
      >
        <div>Workspace content</div>
      </AppShell>,
    );

    expect(screen.getByText("Sentrix")).toBeInTheDocument();
    expect(screen.getByText("udit")).toBeInTheDocument();
    expect(screen.getByText("Workspace content")).toBeInTheDocument();
  });
});
