import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getConnectionDiagnostics } from "../api/resources";
import type { ConnectionDiagnosticsResponse } from "../types";
import { ConnectionDiagnosticsPanel } from "./ConnectionDiagnosticsPanel";

vi.mock("../api/resources", () => ({ getConnectionDiagnostics: vi.fn() }));
const diagnostic = vi.mocked(getConnectionDiagnostics);

const result: ConnectionDiagnosticsResponse = {
  project_id: "project-a",
  start: "2026-10-24T12:00:00Z",
  end: "2026-10-25T12:00:00Z",
  observation_state: "observed",
  signals: {
    metrics: { observed: true, count: 2, last_seen: "2026-10-25T11:00:00Z" },
    logs: { observed: true, count: 1, last_seen: "2026-10-25T11:00:00Z" },
    traces: { observed: false, count: 0, last_seen: null },
  },
};

function renderPanel(projectId = "project-a") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ConnectionDiagnosticsPanel projectId={projectId} />
    </QueryClientProvider>,
  );
}

describe("ConnectionDiagnosticsPanel", () => {
  beforeEach(() => { vi.clearAllMocks(); });
  afterEach(() => { cleanup(); });

  it("displays only observed project signals without implying service health", async () => {
    diagnostic.mockResolvedValue(result);
    renderPanel();
    expect(await screen.findByText("Telemetry observed in the last 24 hours.")).toBeInTheDocument();
    expect(screen.getByText(/2 records/)).toBeInTheDocument();
    expect(screen.getByText(/No observations/)).toBeInTheDocument();
    expect(screen.getByText(/does not test live exporter connectivity or service health/)).toBeInTheDocument();
    expect(diagnostic).toHaveBeenCalledWith("project-a");
  });

  it("shows an honest empty state", async () => {
    diagnostic.mockResolvedValue({
      ...result, observation_state: "not_observed",
      signals: Object.fromEntries(Object.keys(result.signals).map((name) =>
        [name, { observed: false, count: 0, last_seen: null }])) as ConnectionDiagnosticsResponse["signals"],
    });
    renderPanel();
    expect(await screen.findByText(/No telemetry observed in the last 24 hours/)).toBeInTheDocument();
  });

  it("shows dependency failures instead of zero data", async () => {
    diagnostic.mockRejectedValue(new Error("503"));
    renderPanel();
    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to query stored telemetry");
    expect(screen.queryByText(/No telemetry observed in the last 24 hours/)).not.toBeInTheDocument();
  });

  it("does not keep displaying old observations after a failed refresh", async () => {
    diagnostic.mockResolvedValueOnce(result).mockRejectedValueOnce(new Error("503"));
    renderPanel();
    expect(await screen.findByText("Telemetry observed in the last 24 hours.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Check again" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to query stored telemetry");
    expect(screen.queryByText("Telemetry observed in the last 24 hours.")).not.toBeInTheDocument();
  });

  it("refreshes on demand using the current authorized project", async () => {
    diagnostic.mockResolvedValue(result);
    renderPanel("project-b");
    expect(await screen.findByText("Telemetry observed in the last 24 hours.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Check again" }));
    expect(diagnostic).toHaveBeenCalledWith("project-b");
    expect(diagnostic.mock.calls.length).toBeGreaterThanOrEqual(2);
  });
});
