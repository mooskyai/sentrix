import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getServiceCatalog } from "../api/resources";
import type { ServiceCatalogResponse } from "../types";
import { GuidedIntegrationPanel } from "./GuidedIntegrationPanel";

vi.mock("../api/resources", () => ({ getServiceCatalog: vi.fn() }));
const catalog = vi.mocked(getServiceCatalog);

const observed: ServiceCatalogResponse = {
  project_id: "project-a", start: "2026-10-25T00:00:00Z", end: "2026-10-26T00:00:00Z",
  limit: 500, truncated: false, services: [{
    service_name: "node-api", environment: "development", first_seen: "2026-10-25T01:00:00Z",
    last_seen: "2026-10-25T02:00:00Z", metric_points: 0, log_records: 0,
    span_records: 1, signals: ["traces"],
  }],
};

function renderPanel(projectId = "project-a") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <GuidedIntegrationPanel projectId={projectId} />
    </QueryClientProvider>,
  );
}

describe("GuidedIntegrationPanel", () => {
  beforeEach(() => { vi.clearAllMocks(); catalog.mockResolvedValue(observed); });
  afterEach(() => cleanup());

  it("does not call the catalog or request a secret before explicit verification", () => {
    renderPanel();
    expect(screen.getByRole("region", { name: "Guided application integration" })).toBeInTheDocument();
    expect(screen.getByText(/browser never asks for or copies your key/i)).toBeInTheDocument();
    expect(screen.getByText(/traces only/i)).toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: /api key/i })).not.toBeInTheDocument();
    expect(catalog).not.toHaveBeenCalled();
  });

  it("verifies only an exact observed service via a bounded project-scoped catalog query", async () => {
    renderPanel();
    fireEvent.click(screen.getByRole("button", { name: "Check service" }));
    expect(await screen.findByText(/1 spans/)).toBeInTheDocument();
    expect(screen.getByText(/historical telemetry, not live connection health/)).toBeInTheDocument();
    expect(catalog).toHaveBeenCalledWith("project-a", expect.objectContaining({ limit: 500 }));
    const [, window] = catalog.mock.calls[0];
    expect(Date.parse(window.end) - Date.parse(window.start)).toBe(24 * 3600 * 1000);
  });

  it("does not report an unrelated service as connected", async () => {
    catalog.mockResolvedValue({ ...observed, services: [] });
    renderPanel();
    fireEvent.click(screen.getByRole("button", { name: "Check service" }));
    expect(await screen.findByText(/No matching service observed/)).toBeInTheDocument();
  });

  it("treats a truncated catalog as inconclusive", async () => {
    catalog.mockResolvedValue({ ...observed, services: [], truncated: true });
    renderPanel();
    fireEvent.click(screen.getByRole("button", { name: "Check service" }));
    expect(await screen.findByText(/catalog was truncated/)).toBeInTheDocument();
  });

  it("hides prior results and shows query failure when refresh fails", async () => {
    catalog.mockResolvedValueOnce(observed).mockRejectedValueOnce(new Error("503"));
    renderPanel();
    fireEvent.click(screen.getByRole("button", { name: "Check service" }));
    expect(await screen.findByText(/1 spans/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Check service" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/Service catalog unavailable/);
    expect(screen.queryByText(/1 spans/)).not.toBeInTheDocument();
  });

  it("rejects insecure external endpoints and disallows verification", () => {
    renderPanel();
    fireEvent.change(screen.getByLabelText("Exporter location"), { target: { value: "remote" } });
    fireEvent.change(screen.getByLabelText("Reachable Sentrix HTTPS origin"), {
      target: { value: "http://remote.example.com" },
    });
    expect(screen.getByRole("alert")).toHaveTextContent(/Enter an HTTPS origin/);
    expect(screen.getByRole("button", { name: "Check service" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Reachable Sentrix HTTPS origin"), {
      target: { value: "https://telemetry.example.com" },
    });
    expect(screen.getByRole("button", { name: "Check service" })).toBeEnabled();
  });

  it("switches guide and clears previously observed service evidence", async () => {
    renderPanel();
    fireEvent.click(screen.getByRole("button", { name: "Check service" }));
    expect(await screen.findByText(/1 spans/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Server framework"), { target: { value: "django" } });
    expect(screen.getByLabelText("Exact service.name")).toHaveValue("django-api");
    expect(screen.getByText(/opentelemetry-instrumentation-django/)).toBeInTheDocument();
    expect(screen.queryByText(/1 spans/)).not.toBeInTheDocument();
  });


  it("does not reuse a previous successful query after switching the framework", async () => {
    renderPanel();
    fireEvent.click(screen.getByRole("button", { name: "Check service" }));
    expect(await screen.findByText(/1 spans/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Server framework"), { target: { value: "django" } });
    fireEvent.click(screen.getByRole("button", { name: "Check service" }));
    expect(await screen.findByText(/No matching service observed/)).toBeInTheDocument();
    expect(screen.queryByText(/1 spans/)).not.toBeInTheDocument();
  });

  it("clears current-project evidence immediately when project context changes", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const tree = (projectId: string) => (
      <QueryClientProvider client={client}>
        <GuidedIntegrationPanel projectId={projectId} />
      </QueryClientProvider>
    );
    const view = render(tree("project-a"));
    fireEvent.click(screen.getByRole("button", { name: "Check service" }));
    expect(await screen.findByText(/1 spans/)).toBeInTheDocument();
    view.rerender(tree("project-b"));
    expect(screen.queryByText(/1 spans/)).not.toBeInTheDocument();
    expect(catalog).toHaveBeenCalledTimes(1);
    catalog.mockResolvedValue({ ...observed, project_id: "project-b", services: [] });
    fireEvent.click(screen.getByRole("button", { name: "Check service" }));
    expect(await screen.findByText(/No matching service observed/)).toBeInTheDocument();
    expect(catalog).toHaveBeenLastCalledWith("project-b", expect.any(Object));
  });

  it("copies only placeholder-based server configuration", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
    renderPanel();
    const copyButtons = screen.getAllByRole("button", { name: "Copy" });
    fireEvent.click(copyButtons[1]);
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(expect.stringContaining("<SET_IN_SERVER_TERMINAL_ONLY>")));
    expect(writeText.mock.calls[0][0]).not.toContain("sentrix_pk_");
  });
});
