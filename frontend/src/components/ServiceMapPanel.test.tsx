import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getServiceMap } from "../api/resources";
import type { ServiceMapResponse } from "../types";
import { ServiceMapPanel } from "./ServiceMapPanel";

vi.mock("../api/resources", () => ({ getServiceMap: vi.fn() }));
const mockedMap = vi.mocked(getServiceMap);
const traceId = "a".repeat(32);
const response: ServiceMapResponse = {
  project_id: "project-a", start: "2026-10-24T01:00:00Z", end: "2026-10-24T03:00:00Z",
  limit: 100, truncated: false, span_scan_truncated: false, scanned_spans: 12,
  relationships: [{
    from_service: "gateway", from_environment: "production",
    to_service: "checkout", to_environment: "", span_pairs: 2, trace_ids: [traceId],
  }],
};

function renderPanel(projectId = "project-a") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const element = (id: string) => (
    <MemoryRouter>
      <QueryClientProvider client={client}>
        <ServiceMapPanel projectId={id} start="2026-10-24T01:00:00Z" end="2026-10-24T03:00:00Z"
          tracesPath="/projects/shop/traces" />
      </QueryClientProvider>
    </MemoryRouter>
  );
  const view = render(element(projectId));
  return { ...view, element };
}

describe("ServiceMapPanel", () => {
  afterEach(() => cleanup());
  beforeEach(() => { vi.clearAllMocks(); mockedMap.mockResolvedValue(response); });

  it("renders only returned relationships and links a real sample trace", async () => {
    renderPanel();
    expect(await screen.findByText("gateway")).toBeInTheDocument();
    expect(screen.getByText("checkout")).toBeInTheDocument();
    expect(screen.getByText(/2 observed span pairs/)).toBeInTheDocument();
    expect(screen.getByText(/Environment: \(empty\)/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Inspect trace aaaaaaaa/ })).toHaveAttribute(
      "href", expect.stringMatching(/trace_id=aaaaaaaa/),
    );
    expect(mockedMap).toHaveBeenCalledWith("project-a", expect.objectContaining({ limit: 100 }));
    expect(screen.getByText(/Missing links do not imply/i)).toBeInTheDocument();
  });

  it("reports scan truncation instead of presenting an authoritative topology", async () => {
    mockedMap.mockResolvedValue({ ...response, truncated: true, span_scan_truncated: true });
    renderPanel();
    expect(await screen.findByText(/span scan reached its safety cap/i)).toBeInTheDocument();
  });

  it("distinguishes healthy empty and API failures", async () => {
    mockedMap.mockResolvedValueOnce({ ...response, relationships: [] });
    const view = renderPanel();
    expect(await screen.findByText(/No cross-service parent\/child spans observed/i)).toBeInTheDocument();
    view.unmount();
    mockedMap.mockRejectedValueOnce(new Error("query unavailable"));
    renderPanel();
    expect(await screen.findByRole("alert")).toHaveTextContent("query unavailable");
  });

  it("does not reuse a previous project's cached relationships", async () => {
    const { rerender, element } = renderPanel();
    await screen.findByText("gateway");
    mockedMap.mockImplementation(async (id) => id === "project-b"
      ? { ...response, project_id: id, relationships: [{ ...response.relationships[0], from_service: "billing" }] }
      : response);
    rerender(element("project-b"));
    await waitFor(() => expect(screen.getByText("billing")).toBeInTheDocument());
    expect(screen.queryByText("gateway")).not.toBeInTheDocument();
  });
});
