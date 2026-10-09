import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  deleteProjectDashboardPanel,
  getMetricSeries,
  getProjectDashboardPanels,
} from "../api/resources";
import type { MetricSeriesResponse, ProjectDashboardPanel } from "../types";
import { DashboardPanels } from "./DashboardPanels";

vi.mock("../api/resources", () => ({
  deleteProjectDashboardPanel: vi.fn(),
  getMetricSeries: vi.fn(),
  getProjectDashboardPanels: vi.fn(),
}));

const mockedDeleteProjectDashboardPanel = vi.mocked(deleteProjectDashboardPanel);
const mockedGetMetricSeries = vi.mocked(getMetricSeries);
const mockedGetProjectDashboardPanels = vi.mocked(getProjectDashboardPanels);

const panel: ProjectDashboardPanel = {
  id: "panel-a",
  project_id: "project-a",
  title: "Checkout latency",
  metric_name: "checkout.duration",
  time_range: "6h",
  service_name: "checkout",
  environment: "production",
  position: 0,
  created_by: 1,
  created_at: "2026-10-09T05:00:00Z",
  updated_at: "2026-10-09T05:00:00Z",
};

const series: MetricSeriesResponse = {
  project_id: "project-a",
  metric_name: "checkout.duration",
  start: "2026-10-08T23:00:00Z",
  end: "2026-10-09T05:00:00Z",
  filters: { service_name: "checkout", environment: "production" },
  points: [
    {
      timestamp: "2026-10-09T04:58:00Z",
      service_name: "checkout",
      environment: "production",
      metric_type: "gauge",
      aggregation_temporality: "",
      is_monotonic: false,
      value_type: "double",
      value: 18.25,
      attributes: {},
    },
    {
      timestamp: "2026-10-09T04:59:00Z",
      service_name: "checkout",
      environment: "production",
      metric_type: "gauge",
      aggregation_temporality: "",
      is_monotonic: false,
      value_type: "double",
      value: 20.5,
      attributes: {},
    },
  ],
  truncated: false,
};

function renderDashboard(canManage = true) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <DashboardPanels projectId="project-a" canManage={canManage} />
    </QueryClientProvider>,
  );
}

describe("DashboardPanels", () => {
  afterEach(() => cleanup());

  beforeEach(() => {
    vi.clearAllMocks();
    mockedGetProjectDashboardPanels.mockResolvedValue([panel]);
    mockedGetMetricSeries.mockResolvedValue(series);
    mockedDeleteProjectDashboardPanel.mockResolvedValue(undefined);
  });

  it("renders configured project panels from the metrics query boundary", async () => {
    renderDashboard();

    expect(await screen.findByText("Checkout latency")).toBeInTheDocument();
    expect(await screen.findByRole("img", { name: /showing 2 observed points/i })).toBeInTheDocument();
    const summary = screen.getByLabelText("Checkout latency summary");
    const latestStat = within(summary).getByText("Latest").parentElement;
    expect(latestStat).not.toBeNull();
    expect(within(latestStat as HTMLElement).getByText("20.5")).toBeInTheDocument();
    expect(screen.getByText("service=checkout")).toBeInTheDocument();
    expect(screen.getByText("environment=production")).toBeInTheDocument();
    expect(mockedGetMetricSeries).toHaveBeenCalledWith(
      "project-a",
      expect.objectContaining({
        metric_name: "checkout.duration",
        service_name: "checkout",
        environment: "production",
        limit: 500,
      }),
    );
  });

  it("keeps dashboard configuration read-only for viewers", async () => {
    renderDashboard(false);

    expect(await screen.findByText("Checkout latency")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Remove" })).not.toBeInTheDocument();
  });

  it("shows a truthful empty dashboard without querying telemetry", async () => {
    mockedGetProjectDashboardPanels.mockResolvedValue([]);

    renderDashboard();

    expect(await screen.findByText(/No dashboard panels configured/i)).toBeInTheDocument();
    expect(mockedGetMetricSeries).not.toHaveBeenCalled();
  });

  it("removes a panel only after confirmation", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    renderDashboard();
    await screen.findByText("Checkout latency");

    fireEvent.click(screen.getByRole("button", { name: "Remove" }));

    await waitFor(() => {
      expect(mockedDeleteProjectDashboardPanel).toHaveBeenCalledWith("project-a", "panel-a");
    });
  });
});
