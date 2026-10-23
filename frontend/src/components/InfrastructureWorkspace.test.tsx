import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getInfrastructure } from "../api/resources";
import type { InfrastructureResponse } from "../types";
import { InfrastructureWorkspace } from "./InfrastructureWorkspace";

vi.mock("../api/resources", () => ({ getInfrastructure: vi.fn() }));
const mocked = vi.mocked(getInfrastructure);
const sample: InfrastructureResponse = {
  project_id: "project-a", start: "2026-10-22T00:00:00Z", end: "2026-10-23T00:00:00Z",
  limit: 200, truncated: false,
  observations: [{
    attributes: { "host.name": "host-01", "k8s.cluster.name": "cluster-a", "k8s.namespace.name": "payments", "k8s.pod.name": "checkout-01" },
    first_seen: "2026-10-22T10:00:00Z", last_seen: "2026-10-22T10:30:00Z",
    metric_points: 3, log_records: 1, span_records: 2,
  }],
};
function mount(projectId = "project-a", client = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
  return { ...render(<QueryClientProvider client={client}><InfrastructureWorkspace projectId={projectId} /></QueryClientProvider>), client };
}
describe("InfrastructureWorkspace", () => {
  beforeEach(() => { vi.clearAllMocks(); mocked.mockResolvedValue(sample); });
  afterEach(() => cleanup());

  it("shows only observed keys and signal counts, with no invented health", async () => {
    mount();
    expect(await screen.findByText("host-01")).toBeInTheDocument();
    expect(screen.getByText("payments")).toBeInTheDocument();
    expect(screen.getByText("checkout-01")).toBeInTheDocument();
    expect(screen.queryByText(/healthy|running/i)).not.toBeInTheDocument();
    expect(screen.getByText(/not a live host or Kubernetes inventory/i)).toBeInTheDocument();
    expect(mocked).toHaveBeenCalledWith("project-a", expect.objectContaining({ limit: 200 }));
  });

  it("distinguishes healthy empty from dependency failure", async () => {
    mocked.mockResolvedValueOnce({ ...sample, observations: [] });
    const view = mount();
    expect(await screen.findByText(/No infrastructure attributes observed/)).toBeInTheDocument();
    view.unmount();
    mocked.mockRejectedValueOnce(new Error("Telemetry query service is unavailable."));
    mount();
    expect(await screen.findByRole("alert")).toHaveTextContent(/unavailable/i);
  });

  it("shows truncation and refreshes bounded windows", async () => {
    mocked.mockResolvedValue({ ...sample, truncated: true });
    mount();
    expect(await screen.findByText(/Results truncated at 200/i)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Infrastructure observation window"), { target: { value: "1h" } });
    await waitFor(() => {
      const query = mocked.mock.lastCall?.[1];
      expect(query && Date.parse(query.end) - Date.parse(query.start)).toBe(3600000);
    });
  });

  it("never reuses a previous project's attribute sets as current data", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const view = mount("project-a", client);
    expect(await screen.findByText("host-01")).toBeInTheDocument();
    mocked.mockImplementation(async (projectId) => projectId === "project-b"
      ? { ...sample, project_id: "project-b", observations: [{ ...sample.observations[0], attributes: { "host.name": "host-b" } }] }
      : sample);
    view.rerender(<QueryClientProvider client={client}><InfrastructureWorkspace key="project-b" projectId="project-b" /></QueryClientProvider>);
    expect(await screen.findByText("host-b")).toBeInTheDocument();
    expect(screen.queryByText("host-01")).not.toBeInTheDocument();
  });
});
