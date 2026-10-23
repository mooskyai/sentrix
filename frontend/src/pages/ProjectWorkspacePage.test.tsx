import { cleanup, render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getOrganizations, getProjects } from "../api/resources";
import { ProjectWorkspacePage } from "./ProjectWorkspacePage";

vi.mock("../api/resources", () => ({ getOrganizations: vi.fn(), getProjects: vi.fn() }));
vi.mock("../components/ServicesWorkspace", () => ({
  ServicesWorkspace: () => <div data-testid="service-list">Observed services</div>,
}));

vi.mock("../components/InfrastructureWorkspace", () => ({
  InfrastructureWorkspace: () => <div data-testid="infrastructure">Observed infrastructure</div>,
}));

const mockedOrganizations = vi.mocked(getOrganizations);
const mockedProjects = vi.mocked(getProjects);

function renderOverview(initialRoute = "/orgs/acme/projects/shop") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MemoryRouter initialEntries={[initialRoute]}>
      <QueryClientProvider client={client}>
        <Routes>
          <Route path="/orgs/:organizationSlug/projects/:projectSlug" element={<ProjectWorkspacePage />} />
          <Route path="/orgs/:organizationSlug/projects/:projectSlug/:section" element={<ProjectWorkspacePage />} />
        </Routes>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

describe("ProjectWorkspacePage layout", () => {
  afterEach(() => cleanup());

  beforeEach(() => {
    vi.clearAllMocks();
    mockedOrganizations.mockResolvedValue([
      { id: "org-a", slug: "acme", name: "Acme", role: "owner", created_at: "", updated_at: "" },
    ]);
    mockedProjects.mockResolvedValue([
      { id: "project-a", organization_id: "org-a", slug: "shop", name: "Online Store", created_by: 1, created_at: "", updated_at: "" },
    ]);
  });

  it("renders the section on a flat surface while retaining independent fact cards", async () => {
    renderOverview();
    const section = await screen.findByRole("region", { name: "Project workspace content" });
    expect(section).toHaveClass("workspace-section");
    expect(section).not.toHaveClass("panel");
    expect(section).toHaveClass("workspace-section--collection");
    expect(within(section).getByRole("heading", { name: "Project workspace" })).toBeInTheDocument();
    expect(within(section).getByText("Read & write")).toBeInTheDocument();
    expect(section.querySelectorAll(".workspace-card")).toHaveLength(4);
    expect(screen.queryByLabelText("Workspace switcher")).not.toBeInTheDocument();
  });
  it("gives Services one enclosing surface and no nested panels", async () => {
    renderOverview("/orgs/acme/projects/shop/services");
    const section = await screen.findByRole("region", { name: "Project workspace content" });
    expect(section).toHaveClass("workspace-section--surface");
    expect(section.querySelectorAll(".panel")).toHaveLength(0);
    expect(within(section).getByTestId("service-list")).toBeInTheDocument();
  });
  it("gives Infrastructure the same single-level content surface", async () => {
    renderOverview("/orgs/acme/projects/shop/infrastructure");
    const section = await screen.findByRole("region", { name: "Project workspace content" });
    expect(section).toHaveClass("workspace-section--surface");
    expect(section.querySelectorAll(".panel")).toHaveLength(0);
    expect(within(section).getByTestId("infrastructure")).toBeInTheDocument();
  });
});
