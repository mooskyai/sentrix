import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getLogs } from "../api/resources";
import type { LogSearchResponse } from "../types";
import { LogsExplorer } from "./LogsExplorer";

vi.mock("../api/resources", () => ({
  getLogs: vi.fn(),
}));

const mockedGetLogs = vi.mocked(getLogs);

const logResponse: LogSearchResponse = {
  project_id: "project-a",
  start: "2026-10-09T07:00:00Z",
  end: "2026-10-09T08:00:00Z",
  filters: {
    service_name: null,
    environment: null,
    min_severity_number: null,
    body_contains: null,
    trace_id: null,
  },
  logs: [
    {
      timestamp: "2026-10-09T07:59:30Z",
      observed_timestamp: "2026-10-09T07:59:31Z",
      service_name: "checkout",
      environment: "production",
      scope_name: "checkout.logger",
      scope_version: "1.2.3",
      scope_attributes: { library: "checkout" },
      resource_attributes: { "service.name": "checkout", region: "ap-south-1" },
      severity_number: 17,
      severity_text: "ERROR",
      body: "payment authorization failed",
      event_name: "payment.failure",
      trace_id: "0123456789abcdef0123456789abcdef",
      span_id: "0123456789abcdef",
      flags: 1,
      dropped_attributes_count: 0,
      attributes: { route: "/pay", tenant: "a" },
    },
    {
      timestamp: "2026-10-09T07:58:00Z",
      observed_timestamp: null,
      service_name: "worker",
      environment: "production",
      scope_name: "",
      scope_version: "",
      scope_attributes: {},
      resource_attributes: { "service.name": "worker" },
      severity_number: 9,
      severity_text: "INFO",
      body: "retry scheduled",
      event_name: "",
      trace_id: null,
      span_id: null,
      flags: 0,
      dropped_attributes_count: 1,
      attributes: {},
    },
  ],
  truncated: false,
};

function renderExplorer() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <LogsExplorer projectId="project-a" />
    </QueryClientProvider>,
  );
}

describe("LogsExplorer", () => {
  afterEach(() => cleanup());

  beforeEach(() => {
    vi.clearAllMocks();
    mockedGetLogs.mockResolvedValue(logResponse);
  });

  it("renders real project logs with raw correlation and attributes", async () => {
    renderExplorer();

    expect(await screen.findByText("payment authorization failed")).toBeInTheDocument();
    expect(screen.getByText("ERROR (17)")).toBeInTheDocument();
    expect(screen.getByText("0123456789abcdef0123456789abcdef")).toBeInTheDocument();
    expect(screen.getByText("route=/pay, tenant=a")).toBeInTheDocument();
    expect(screen.getByText(/Trace navigation is added in M4.3/i)).toBeInTheDocument();
  });

  it("applies the bounded M4.1 log filters without querying on each keystroke", async () => {
    renderExplorer();
    await screen.findByText("payment authorization failed");
    expect(mockedGetLogs).toHaveBeenCalledTimes(1);

    fireEvent.change(screen.getByLabelText("Log service"), { target: { value: "checkout" } });
    fireEvent.change(screen.getByLabelText("Log environment"), { target: { value: "production" } });
    fireEvent.change(screen.getByLabelText("Minimum log severity"), { target: { value: "17" } });
    fireEvent.change(screen.getByLabelText("Log body contains"), { target: { value: "authorization" } });
    fireEvent.change(screen.getByLabelText("Log trace ID"), {
      target: { value: "ABCDEFABCDEFABCDEFABCDEFABCDEFAB" },
    });

    expect(mockedGetLogs).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Apply filters" }));

    await waitFor(() => {
      expect(mockedGetLogs).toHaveBeenLastCalledWith(
        "project-a",
        expect.objectContaining({
          limit: 200,
          service_name: "checkout",
          environment: "production",
          min_severity_number: 17,
          body_contains: "authorization",
          trace_id: "abcdefabcdefabcdefabcdefabcdefab",
        }),
      );
    });
  });

  it("shows a healthy empty result separately from a query failure", async () => {
    mockedGetLogs.mockResolvedValue({ ...logResponse, logs: [] });

    renderExplorer();

    expect(await screen.findByText(/No logs matched this query/i)).toBeInTheDocument();
    expect(screen.queryByText(/Unable to load logs/i)).not.toBeInTheDocument();
  });

  it("warns when the server reports a truncated result", async () => {
    mockedGetLogs.mockResolvedValue({ ...logResponse, truncated: true });

    renderExplorer();

    expect(await screen.findByText(/reached the selected row limit/i)).toBeInTheDocument();
  });

  it("surfaces query failure instead of presenting it as empty telemetry", async () => {
    mockedGetLogs.mockRejectedValue(new Error("Telemetry query service is unavailable."));

    renderExplorer();

    expect(
      await screen.findByText(/Telemetry query service is unavailable/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/No logs matched this query/i)).not.toBeInTheDocument();
  });
});
