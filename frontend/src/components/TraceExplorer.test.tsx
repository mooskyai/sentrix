import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getTrace } from "../api/resources";
import type { TraceDetailResponse } from "../types";
import { TraceExplorer } from "./TraceExplorer";

vi.mock("../api/resources", () => ({
  getTrace: vi.fn(),
}));

const mockedGetTrace = vi.mocked(getTrace);
const traceId = "0123456789abcdef0123456789abcdef";
const rootSpanId = "0123456789abcdef";

const traceResponse: TraceDetailResponse = {
  project_id: "project-a",
  trace_id: traceId,
  start: "2026-10-09T07:00:00Z",
  end: "2026-10-09T08:00:00Z",
  spans: [
    {
      start_time: "2026-10-09T07:59:30.000Z",
      end_time: "2026-10-09T07:59:30.020Z",
      duration_ns: 20_000_000,
      service_name: "checkout",
      environment: "production",
      scope_name: "checkout.tracer",
      scope_version: "1.2.3",
      scope_attributes: { library: "checkout" },
      resource_attributes: { "service.name": "checkout", region: "ap-south-1" },
      trace_id: traceId,
      span_id: rootSpanId,
      parent_span_id: null,
      trace_state: "vendor=value",
      span_name: "POST /checkout",
      span_kind: 2,
      status_code: 0,
      status_message: "",
      flags: 1,
      dropped_attributes_count: 0,
      dropped_events_count: 0,
      dropped_links_count: 0,
      attributes: { "http.route": "/checkout" },
      events_json: "[]",
      links_json: "[]",
    },
    {
      start_time: "2026-10-09T07:59:30.004Z",
      end_time: "2026-10-09T07:59:30.012Z",
      duration_ns: 8_000_000,
      service_name: "payments",
      environment: "production",
      scope_name: "payments.tracer",
      scope_version: "2.0",
      scope_attributes: {},
      resource_attributes: { "service.name": "payments" },
      trace_id: traceId,
      span_id: "fedcba9876543210",
      parent_span_id: rootSpanId,
      trace_state: "",
      span_name: "authorize payment",
      span_kind: 3,
      status_code: 2,
      status_message: "declined",
      flags: 1,
      dropped_attributes_count: 0,
      dropped_events_count: 0,
      dropped_links_count: 0,
      attributes: { "payment.provider": "test" },
      events_json: '[{"name":"exception"}]',
      links_json: "[]",
    },
  ],
  truncated: false,
};

function renderExplorer(initialEntry = "/traces") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <QueryClientProvider client={queryClient}>
        <TraceExplorer projectId="project-a" />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

describe("TraceExplorer", () => {
  afterEach(() => cleanup());

  beforeEach(() => {
    vi.clearAllMocks();
    mockedGetTrace.mockResolvedValue(traceResponse);
  });

  it("loads a linked trace window and renders raw parentage, timing, status, and attributes", async () => {
    renderExplorer(
      `/traces?trace_id=${traceId}&start=2026-10-09T07%3A00%3A00Z&end=2026-10-09T08%3A00%3A00Z`,
    );

    expect(await screen.findByText("POST /checkout")).toBeInTheDocument();
    expect(screen.getByText("authorize payment")).toBeInTheDocument();
    expect(screen.getByText("20.00 ms")).toBeInTheDocument();
    expect(screen.getByText("root")).toBeInTheDocument();
    expect(screen.getAllByText(rootSpanId).length).toBeGreaterThan(0);
    expect(screen.getByText("payment.provider=test")).toBeInTheDocument();
    expect(screen.getByText('[{"name":"exception"}]')).toBeInTheDocument();
    expect(screen.getByText("declined")).toBeInTheDocument();

    expect(mockedGetTrace).toHaveBeenCalledWith("project-a", traceId, {
      start: "2026-10-09T07:00:00Z",
      end: "2026-10-09T08:00:00Z",
      limit: 500,
    });
  });

  it("validates lookup input before querying and queries only after submit", async () => {
    renderExplorer();
    expect(mockedGetTrace).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText("Trace ID"), { target: { value: "not-a-trace" } });
    fireEvent.click(screen.getByRole("button", { name: "Lookup trace" }));
    expect(await screen.findByText(/non-zero 32-character hexadecimal/i)).toBeInTheDocument();
    expect(mockedGetTrace).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText("Trace ID"), { target: { value: traceId.toUpperCase() } });
    fireEvent.click(screen.getByRole("button", { name: "Lookup trace" }));

    await waitFor(() => expect(mockedGetTrace).toHaveBeenCalledTimes(1));
    expect(mockedGetTrace).toHaveBeenCalledWith(
      "project-a",
      traceId,
      expect.objectContaining({ limit: 500 }),
    );
  });

  it("shows a healthy empty trace separately from a query failure", async () => {
    mockedGetTrace.mockResolvedValue({ ...traceResponse, spans: [] });
    renderExplorer(`/traces?trace_id=${traceId}`);

    expect(await screen.findByText(/No spans matched this trace/i)).toBeInTheDocument();
    expect(screen.queryByText(/Unable to load trace/i)).not.toBeInTheDocument();
  });

  it("warns when the bounded trace response is truncated", async () => {
    mockedGetTrace.mockResolvedValue({ ...traceResponse, truncated: true });
    renderExplorer(`/traces?trace_id=${traceId}`);

    expect(await screen.findByText(/500-span browser limit/i)).toBeInTheDocument();
  });

  it("marks a missing parent honestly and surfaces query failure", async () => {
    mockedGetTrace.mockResolvedValueOnce({
      ...traceResponse,
      spans: [{ ...traceResponse.spans[1], parent_span_id: "aaaaaaaaaaaaaaaa" }],
    });
    renderExplorer(`/traces?trace_id=${traceId}`);

    expect(await screen.findByText(/aaaaaaaaaaaaaaaa \(parent not returned\)/i)).toBeInTheDocument();
    cleanup();

    mockedGetTrace.mockRejectedValueOnce(new Error("Telemetry query service is unavailable."));
    renderExplorer(`/traces?trace_id=${traceId}`);
    expect(
      await screen.findByText(/Telemetry query service is unavailable/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/No spans matched this trace/i)).not.toBeInTheDocument();
  });
});
