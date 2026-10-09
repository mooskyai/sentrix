import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createProjectDashboardPanel, getMetricCatalog, getMetricSeries } from "../api/resources";
import type { MetricCatalogResponse, MetricSeriesResponse, ProjectDashboardPanel } from "../types";
import { MetricsExplorer } from "./MetricsExplorer";

vi.mock("../api/resources", () => ({
  createProjectDashboardPanel: vi.fn(),
  getMetricCatalog: vi.fn(),
  getMetricSeries: vi.fn(),
}));

const mockedCreateProjectDashboardPanel = vi.mocked(createProjectDashboardPanel);
const mockedGetMetricCatalog = vi.mocked(getMetricCatalog);
const mockedGetMetricSeries = vi.mocked(getMetricSeries);

const catalog: MetricCatalogResponse = {
  project_id: "project-a",
  start: "2026-10-09T04:00:00Z",
  end: "2026-10-09T05:00:00Z",
  metrics: [
    {
      name: "http.server.duration",
      description: "Request duration",
      unit: "ms",
      metric_types: ["gauge"],
      value_types: ["double"],
      supports_numeric_series: true,
      point_count: 2,
      last_seen_at: "2026-10-09T04:59:00Z",
    },
    {
      name: "http.server.duration.histogram",
      description: "Request duration histogram",
      unit: "ms",
      metric_types: ["histogram"],
      value_types: ["histogram"],
      supports_numeric_series: false,
      point_count: 5,
      last_seen_at: "2026-10-09T04:58:00Z",
    },
  ],
};

const series: MetricSeriesResponse = {
  project_id: "project-a",
  metric_name: "http.server.duration",
  start: "2026-10-09T04:00:00Z",
  end: "2026-10-09T05:00:00Z",
  filters: { service_name: null, environment: null },
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
      attributes: { route: "/pay" },
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
      attributes: { route: "/pay" },
    },
  ],
  truncated: false,
};

const pinnedPanel: ProjectDashboardPanel = {
  id: "panel-a",
  project_id: "project-a",
  title: "http.server.duration",
  metric_name: "http.server.duration",
  time_range: "1h",
  service_name: "checkout",
  environment: "production",
  position: 0,
  created_by: 1,
  created_at: "2026-10-09T05:00:00Z",
  updated_at: "2026-10-09T05:00:00Z",
};

function renderExplorer(canManageDashboard = false) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MetricsExplorer projectId="project-a" canManageDashboard={canManageDashboard} />
    </QueryClientProvider>,
  );
}

describe("MetricsExplorer", () => {
  afterEach(() => cleanup());

  beforeEach(() => {
    vi.clearAllMocks();
    mockedCreateProjectDashboardPanel.mockResolvedValue(pinnedPanel);
    mockedGetMetricCatalog.mockResolvedValue(catalog);
    mockedGetMetricSeries.mockResolvedValue(series);
  });

  it("loads a numeric catalog metric and renders real series points", async () => {
    renderExplorer();

    expect(await screen.findByText("Request duration")).toBeInTheDocument();
    expect(await screen.findByRole("img", { name: /showing 2 observed points/i })).toBeInTheDocument();
    expect(screen.getByText("20.5 ms")).toBeInTheDocument();
    expect(screen.getAllByText("route=/pay")).toHaveLength(2);
    expect(screen.getByText(/does not derive rates, deltas, or histogram statistics/i)).toBeInTheDocument();
  });

  it("marks non-scalar metrics unavailable without querying a fake numeric series", async () => {
    mockedGetMetricCatalog.mockResolvedValue({
      ...catalog,
      metrics: [catalog.metrics[1]],
    });

    renderExplorer();

    expect(await screen.findByText(/none have scalar number points/i)).toBeInTheDocument();
    expect(mockedGetMetricSeries).not.toHaveBeenCalled();
  });

  it("applies exact service and environment filters", async () => {
    renderExplorer();
    await screen.findByRole("img", { name: /showing 2 observed points/i });

    fireEvent.change(screen.getByLabelText("Service"), { target: { value: "checkout" } });
    fireEvent.change(screen.getByLabelText("Environment"), { target: { value: "production" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply filters" }));

    await waitFor(() => {
      expect(mockedGetMetricSeries).toHaveBeenLastCalledWith(
        "project-a",
        expect.objectContaining({
          metric_name: "http.server.duration",
          service_name: "checkout",
          environment: "production",
        }),
      );
    });
  });

  it("pins the current numeric query to the project dashboard for writers", async () => {
    renderExplorer(true);
    await screen.findByRole("img", { name: /showing 2 observed points/i });

    fireEvent.change(screen.getByLabelText("Service"), { target: { value: "checkout" } });
    fireEvent.change(screen.getByLabelText("Environment"), { target: { value: "production" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply filters" }));
    fireEvent.click(screen.getByRole("button", { name: /Pin current query to dashboard/i }));

    await waitFor(() => {
      expect(mockedCreateProjectDashboardPanel).toHaveBeenCalledWith("project-a", {
        title: "http.server.duration",
        metric_name: "http.server.duration",
        time_range: "1h",
        service_name: "checkout",
        environment: "production",
      });
    });
    expect(await screen.findByText(/Pinned “http.server.duration” to Dashboards/i)).toBeInTheDocument();
  });

  it("surfaces query failure instead of presenting it as an empty result", async () => {
    mockedGetMetricSeries.mockRejectedValue(new Error("Telemetry query service is unavailable."));

    renderExplorer();

    expect(
      await screen.findByText(/Telemetry query service is unavailable/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/No numeric points matched/i)).not.toBeInTheDocument();
  });
});
