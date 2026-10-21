import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getOrganizations, getProjects } from "../api/resources";
import { AppShell } from "./AppShell";

vi.mock("../api/resources", () => ({ getOrganizations: vi.fn(), getProjects: vi.fn() }));
const user = { id: 1, username: "udit", email: "", first_name: "", last_name: "" };
const orgs = [
  { id: "org-a", slug: "acme", name: "Acme", role: "owner", created_at: "", updated_at: "" },
  { id: "org-b", slug: "beta", name: "Beta", role: "viewer", created_at: "", updated_at: "" },
] as const;
const projects = [
  { id: "project-a", organization_id: "org-a", slug: "api", name: "API", created_by: 1, created_at: "", updated_at: "" },
  { id: "project-worker", organization_id: "org-a", slug: "worker", name: "Worker", created_by: 1, created_at: "", updated_at: "" },
  { id: "project-b", organization_id: "org-b", slug: "store", name: "Store", created_by: 1, created_at: "", updated_at: "" },
];
function mount(path = "/") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <AppShell user={user} onLogout={vi.fn()}><div>Workspace content</div></AppShell>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("AppShell", () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.mocked(getOrganizations).mockResolvedValue([...orgs]);
    vi.mocked(getProjects).mockResolvedValue(projects);
  });
  afterEach(() => { cleanup(); vi.clearAllMocks(); });

  it("keeps project links hidden until both selectors have an authorized choice", async () => {
    mount();
    expect(screen.getByText("Sentrix")).toBeInTheDocument();
    expect(screen.getByText("udit")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Services" })).not.toBeInTheDocument();
    await screen.findByRole("option", { name: "Acme" });
    fireEvent.change(screen.getByLabelText("Organization"), { target: { value: "org-a" } });
    expect(screen.queryByRole("link", { name: "Metrics" })).not.toBeInTheDocument();
    await screen.findByRole("option", { name: "API" });
    fireEvent.change(screen.getByLabelText("Project"), { target: { value: "project-a" } });
    expect(await screen.findByRole("link", { name: "Metrics" })).toHaveAttribute("href", "/orgs/acme/projects/api/metrics");
    expect(screen.getByRole("link", { name: "Services" })).toHaveAttribute("href", "/orgs/acme/projects/api/services");
    fireEvent.change(screen.getByLabelText("Organization"), { target: { value: "org-b" } });
    expect(screen.getByLabelText("Project")).toHaveValue("");
    expect(screen.queryByRole("link", { name: "Metrics" })).not.toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "API" })).not.toBeInTheDocument();
  });

  it("uses server-listed route membership and restores selection across navigation", async () => {
    mount("/orgs/acme/projects/api/logs");
    expect(await screen.findByRole("link", { name: "Logs" })).toHaveClass("active");
    expect(screen.getByLabelText("Organization")).toHaveValue("org-a");
    expect(screen.getByLabelText("Project")).toHaveValue("project-a");
    await waitFor(() => expect(JSON.parse(sessionStorage.getItem("sentrix.workspace.1") ?? "{}"))
      .toMatchObject({ organizationId: "org-a", projectId: "project-a" }));
  });

  it("changes project without losing the active explorer section", async () => {
    mount("/orgs/acme/projects/api/logs");
    await screen.findByRole("option", { name: "Worker" });
    fireEvent.change(screen.getByLabelText("Project"), { target: { value: "project-worker" } });
    expect(await screen.findByRole("link", { name: "Logs" })).toHaveAttribute(
      "href", "/orgs/acme/projects/worker/logs",
    );
    fireEvent.click(screen.getByRole("link", { name: "Organizations & projects" }));
    expect(screen.getByLabelText("Project")).toHaveValue("project-worker");
    expect(screen.getByRole("link", { name: "Services" })).toHaveAttribute(
      "href", "/orgs/acme/projects/worker/services",
    );
  });

  it("does not show project links for an unauthorized route", async () => {
    mount("/orgs/unknown/projects/no-access/logs");
    await screen.findByRole("option", { name: "Acme" });
    expect(screen.queryByRole("link", { name: "Logs" })).not.toBeInTheDocument();
  });
});
