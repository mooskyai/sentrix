import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getServiceCatalog, getServiceDetail } from "../api/resources";
import type { ServiceCatalogResponse } from "../types";
import { ServicesWorkspace } from "./ServicesWorkspace";

vi.mock("../api/resources", () => ({ getServiceCatalog: vi.fn(), getServiceDetail: vi.fn() }));
const mockedCatalog = vi.mocked(getServiceCatalog);
const mockedDetail = vi.mocked(getServiceDetail);

const catalog: ServiceCatalogResponse = {
  project_id: "project-a", start: "2026-10-19T00:00:00Z", end: "2026-10-19T06:00:00Z",
  limit: 500, truncated: false,
  services: [
    { service_name: "checkout", environment: "production", first_seen: "2026-10-19T01:00:00Z", last_seen: "2026-10-19T05:00:00Z", metric_points: 8, log_records: 2, span_records: 3, signals: ["metrics", "logs", "traces"] },
    { service_name: "worker", environment: "", first_seen: "2026-10-19T02:00:00Z", last_seen: "2026-10-19T03:00:00Z", metric_points: 0, log_records: 1, span_records: 0, signals: ["logs"] },
  ],
};

function renderServices(projectId = "project-a") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(
    <MemoryRouter initialEntries={["/orgs/alpha/projects/shop/services"]}>
      <QueryClientProvider client={client}>
        <ServicesWorkspace
          projectId={projectId}
          metricsPath="/orgs/alpha/projects/shop/metrics"
          logsPath="/orgs/alpha/projects/shop/logs"
          tracesPath="/orgs/alpha/projects/shop/traces"
        />
      </QueryClientProvider>
    </MemoryRouter>,
  );
  return { ...view, client };
}

describe("ServicesWorkspace", () => {
  afterEach(() => cleanup());
  beforeEach(() => {
    vi.clearAllMocks();
    mockedCatalog.mockResolvedValue(catalog);
    mockedDetail.mockResolvedValue({
      project_id: "project-a", service_name: "checkout", environment: "production",
      start: "2026-10-19T00:00:00Z", end: "2026-10-19T06:00:00Z",
      metric_names: [{ name: "requests", point_count: 8 }],
      error_logs: [{ timestamp: "2026-10-19T05:00:00Z", severity_number: 17,
        severity_text: "ERROR", body: "outage", trace_id: "a".repeat(32) }],
      trace_references: [{ trace_id: "a".repeat(32), span_records: 3,
        last_seen: "2026-10-19T05:00:00Z" }],
      truncated: { metric_names: false, error_logs: false, trace_references: false },
    });
  });

  it("renders observed identities, exact environment, UTC window and signal counts", async () => {
    renderServices();
    expect(await screen.findByText("checkout")).toBeInTheDocument();
    const toolbar = screen.getByText("Observed service catalog").closest(".services-toolbar");
    expect(toolbar).not.toHaveClass("border");
    expect(toolbar).not.toHaveClass("bg-canvas-soft");
    expect(screen.getByText("worker")).toBeInTheDocument();
    expect(screen.getByText("(empty)")).toBeInTheDocument();
    expect(screen.getByText("metrics, logs, traces")).toBeInTheDocument();
    expect(screen.getByText(/Catalog window:/i)).toHaveTextContent("UTC");
    expect(mockedCatalog).toHaveBeenCalledWith("project-a", expect.objectContaining({ limit: 500 }));
    const args = mockedCatalog.mock.calls[0][1];
    expect(Date.parse(args.end) - Date.parse(args.start)).toBe(24 * 3600 * 1000);
  });

  it("shows detail for exact service/environment without fabricating health", async () => {
    renderServices();
    fireEvent.click(
      await screen.findByRole(
        "button",
        { name: "Inspect checkout, environment production" },
        { timeout: 5000 },
      ),
    );
    const detail = await screen.findByRole("region", { name: "Service detail" });
    expect(detail).toBeInTheDocument();
    expect(detail).not.toHaveClass("alert-rule-card");
    expect(screen.getByRole("dialog", { name: "Service: checkout" })).toBeInTheDocument();
    expect(screen.getByText("First observed:", { exact: false })).toBeInTheDocument();
    expect(screen.getByText(/not health, ownership, SLO/i)).toBeInTheDocument();
    const metricsHref = screen.getByRole("link", { name: "Open Metrics" }).getAttribute("href") ?? "";
    const logsHref = screen.getByRole("link", { name: "Open Logs" }).getAttribute("href") ?? "";
    expect(metricsHref).toContain("service_name=checkout&environment=production&range=24h");
    expect(logsHref).toContain("service_name=checkout&environment=production&range=24h");
    expect(screen.getByText(/filters already applied/i)).toBeInTheDocument();
    expect(await screen.findByText(/requests: 8 points/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Traces" })).toHaveAttribute(
      "href", expect.stringContaining(`trace_id=${"a".repeat(32)}`),
    );
    expect(screen.getByRole("link", { name: "Open Metrics" })).toHaveAttribute(
      "href", expect.stringContaining("metric_name=requests"),
    );
    expect(screen.getByText(/outage/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "a".repeat(32) })).toHaveAttribute(
      "href", expect.stringMatching(/trace_id=aaaaaaaa/),
    );
    expect(mockedDetail).toHaveBeenCalledWith("project-a", expect.objectContaining({
      service_name: "checkout", environment: "production",
    }));
  });

  it("links empty-environment services without losing the exact identity", async () => {
    renderServices();
    fireEvent.click(await screen.findByRole("button", { name: "Inspect worker, environment empty" }));
    expect(screen.getByRole("link", { name: "Open Logs" })).toHaveAttribute(
      "href", expect.stringContaining("service_name=worker&environment=&range=24h"),
    );
  });

  it("distinguishes empty data from telemetry failure", async () => {
    mockedCatalog.mockResolvedValueOnce({ ...catalog, services: [] });
    const view = renderServices();
    expect(await screen.findByText(/No services observed in this window/i)).toBeInTheDocument();
    view.unmount();
    mockedCatalog.mockRejectedValueOnce(new Error("Telemetry query service is unavailable."));
    renderServices();
    expect(await screen.findByRole("alert")).toHaveTextContent(/unavailable/i);
    expect(screen.queryByText(/No services observed in this window/i)).not.toBeInTheDocument();
  });

  it("warns for truncated catalog and does not claim a missing detail is down", async () => {
    mockedCatalog.mockResolvedValue({ ...catalog, truncated: true });
    renderServices();
    expect(await screen.findByText(/Catalog truncated at 500/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Inspect worker, environment empty" }));
    expect(await screen.findByText(/Environment: \(empty\)/)).toBeInTheDocument();
  });

  it("passes exact empty environment to detail and isolates identity in the query key", async () => {
    renderServices();
    fireEvent.click(await screen.findByRole("button", { name: "Inspect worker, environment empty" }));
    await waitFor(() => expect(mockedDetail).toHaveBeenCalledWith("project-a", expect.objectContaining({
      service_name: "worker", environment: "",
    })));
  });

  it("shows bounded-detail failure separately from healthy catalog", async () => {
    mockedDetail.mockRejectedValueOnce(new Error("Telemetry query service is unavailable."));
    renderServices();
    fireEvent.click(await screen.findByRole("button", { name: "Inspect checkout, environment production" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/unavailable/i);
    expect(screen.getAllByText("checkout").length).toBeGreaterThan(0);
  });

  it("warns when detail references are truncated", async () => {
    mockedDetail.mockResolvedValueOnce({
      project_id: "project-a", service_name: "checkout", environment: "production",
      start: "2026-10-19T00:00:00Z", end: "2026-10-19T06:00:00Z",
      metric_names: [], error_logs: [], trace_references: [],
      truncated: { metric_names: true, error_logs: false, trace_references: false },
    });
    renderServices();
    fireEvent.click(await screen.findByRole("button", { name: "Inspect checkout, environment production" }));
    expect(await screen.findByText(/Detail references are truncated/i)).toBeInTheDocument();
  });

  it("requeries with a bounded changed window", async () => {
    renderServices();
    await screen.findByText("checkout");
    fireEvent.change(screen.getByLabelText("Service observation window"), { target: { value: "1h" } });
    await waitFor(() => {
      expect(mockedCatalog).toHaveBeenLastCalledWith("project-a", expect.objectContaining({ limit: 500 }));
      const calls = mockedCatalog.mock.calls;
      const args = calls[calls.length - 1][1];
      expect(Date.parse(args.end) - Date.parse(args.start)).toBe(3600 * 1000);
    });
  });

  it("keys cached catalog by project so a project switch cannot show another tenant's data", async () => {
    const { rerender, client } = renderServices();
    await screen.findByText("checkout");
    mockedCatalog.mockImplementation(async (projectId) => projectId === "project-b"
      ? { ...catalog, project_id: "project-b", services: [{ ...catalog.services[1], service_name: "billing" }] }
      : catalog);
    rerender(
      <MemoryRouter initialEntries={["/orgs/alpha/projects/shop/services"]}>
        <QueryClientProvider client={client}>
          <ServicesWorkspace projectId="project-b" metricsPath="/orgs/alpha/projects/shop/metrics" logsPath="/orgs/alpha/projects/shop/logs" tracesPath="/orgs/alpha/projects/shop/traces" />
        </QueryClientProvider>
      </MemoryRouter>,
    );
    expect(await screen.findByText("billing")).toBeInTheDocument();
    expect(screen.queryByText("checkout")).not.toBeInTheDocument();
    expect(mockedCatalog).toHaveBeenCalledWith("project-b", expect.any(Object));
  });
});
