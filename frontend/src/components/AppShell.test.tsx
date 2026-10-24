import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getOrganizations, getProjects } from "../api/resources";
import { AppShell } from "./AppShell";
import { workspacePreferenceKey } from "../workspacePersistence";

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
function mount(path = "/", userId = 1) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <AppShell user={{ ...user, id: userId }} onLogout={vi.fn()}>
          <div>Workspace content</div>
        </AppShell>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function preference(userId = 1) {
  return JSON.parse(localStorage.getItem(workspacePreferenceKey(userId)) ?? "null") as {
    version: number; organizationId: string; projectId: string; stale: boolean;
  } | null;
}

describe("AppShell", () => {
  beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
    vi.mocked(getOrganizations).mockResolvedValue([...orgs]);
    vi.mocked(getProjects).mockResolvedValue(projects);
  });
  afterEach(() => { cleanup(); vi.clearAllMocks(); });

  it("shows project links only after loading and selects the first authorized pair", async () => {
    mount();
    expect(screen.getByText("Sentrix")).toBeInTheDocument();
    expect(screen.getByText("udit")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Services" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Documentation" })).toHaveAttribute("href", "/docs/telemetry-setup");
    expect(screen.queryByRole("link", { name: "API reference" })).not.toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Metrics" })).toHaveAttribute(
      "href", "/orgs/acme/projects/api/metrics",
    );
    expect(screen.getByLabelText("Organization")).toHaveValue("org-a");
    expect(screen.getByLabelText("Project")).toHaveValue("project-a");
    await waitFor(() => expect(preference()).toEqual({
      version: 1, organizationId: "org-a", projectId: "project-a", stale: false,
    }));
    fireEvent.change(screen.getByLabelText("Organization"), { target: { value: "org-b" } });
    expect(screen.getByLabelText("Project")).toHaveValue("project-b");
    expect(screen.getByRole("link", { name: "Services" })).toHaveAttribute(
      "href", "/orgs/beta/projects/store/services",
    );
    expect(screen.queryByRole("option", { name: "API" })).not.toBeInTheDocument();
    await waitFor(() => expect(preference()).toMatchObject({
      organizationId: "org-b", projectId: "project-b", stale: false,
    }));
  });

  it("uses authorized deep links and saves their choice to localStorage", async () => {
    mount("/orgs/acme/projects/api/logs");
    expect(await screen.findByRole("link", { name: "Logs" })).toHaveClass("active");
    expect(screen.getByLabelText("Organization")).toHaveValue("org-a");
    expect(screen.getByLabelText("Project")).toHaveValue("project-a");
    await waitFor(() => expect(preference()).toMatchObject({
      organizationId: "org-a", projectId: "project-a", stale: false,
    }));
  });

  it("remembers a valid manually selected project after navigating to overview", async () => {
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
    await waitFor(() => expect(preference()?.projectId).toBe("project-worker"));
  });

  it("restores a valid localStorage choice rather than overriding it with first", async () => {
    localStorage.setItem(workspacePreferenceKey(1), JSON.stringify({
      version: 1, organizationId: "org-b", projectId: "project-b", stale: false,
    }));
    mount();
    expect(await screen.findByRole("link", { name: "Services" })).toHaveAttribute(
      "href", "/orgs/beta/projects/store/services",
    );
    expect(screen.getByLabelText("Organization")).toHaveValue("org-b");
    expect(screen.getByLabelText("Project")).toHaveValue("project-b");
  });

  it("flags a removed saved workspace stale, falls back and clears on manual selection", async () => {
    localStorage.setItem(workspacePreferenceKey(1), JSON.stringify({
      version: 1, organizationId: "org-removed", projectId: "project-removed", stale: false,
    }));
    mount();
    expect(await screen.findByRole("link", { name: "Services" })).toHaveAttribute(
      "href", "/orgs/acme/projects/api/services",
    );
    expect(screen.getByRole("status")).toHaveTextContent(/saved workspace was unavailable/i);
    await waitFor(() => expect(preference()).toMatchObject({
      organizationId: "org-a", projectId: "project-a", stale: true,
    }));
    fireEvent.change(screen.getByLabelText("Organization"), { target: { value: "org-b" } });
    await waitFor(() => expect(preference()).toMatchObject({
      organizationId: "org-b", projectId: "project-b", stale: false,
    }));
    expect(screen.queryByText(/saved workspace was unavailable/i)).not.toBeInTheDocument();
  });

  it("migrates the existing sessionStorage selection", async () => {
    sessionStorage.setItem("sentrix.workspace.1", JSON.stringify({
      organizationId: "org-a", projectId: "project-worker",
    }));
    mount();
    expect(await screen.findByRole("link", { name: "Services" })).toHaveAttribute(
      "href", "/orgs/acme/projects/worker/services",
    );
    await waitFor(() => expect(preference()?.projectId).toBe("project-worker"));
  });

  it("does not show project links or overwrite saved choice for an unauthorized URL", async () => {
    localStorage.setItem(workspacePreferenceKey(1), JSON.stringify({
      version: 1, organizationId: "org-b", projectId: "project-b", stale: false,
    }));
    mount("/orgs/unknown/projects/no-access/logs");
    await screen.findByRole("option", { name: "Acme" });
    expect(screen.queryByRole("link", { name: "Logs" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Organization")).toHaveValue("");
    expect(screen.getByLabelText("Project")).toHaveValue("");
    expect(preference()?.projectId).toBe("project-b");
  });

  it("has no project links when there are no projects and never invents one", async () => {
    vi.mocked(getProjects).mockResolvedValueOnce([]);
    mount();
    await screen.findByRole("option", { name: "Acme" });
    await waitFor(() => expect(screen.getByLabelText("Organization")).toHaveValue("org-a"));
    expect(screen.getByLabelText("Project")).toHaveValue("");
    expect(screen.queryByRole("link", { name: "Services" })).not.toBeInTheDocument();
  });

  it("isolates localStorage preferences by signed-in user", async () => {
    localStorage.setItem(workspacePreferenceKey(1), JSON.stringify({
      version: 1, organizationId: "org-b", projectId: "project-b", stale: false,
    }));
    mount("/", 2);
    expect(await screen.findByRole("link", { name: "Services" })).toHaveAttribute(
      "href", "/orgs/acme/projects/api/services",
    );
    await waitFor(() => expect(preference(2)?.projectId).toBe("project-a"));
    expect(preference(1)?.projectId).toBe("project-b");
  });
});
