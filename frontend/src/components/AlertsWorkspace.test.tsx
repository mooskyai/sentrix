import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createProjectAlertRule,
  deleteProjectAlertRule,
  getProjectAlertRules,
  updateProjectAlertRule,
} from "../api/resources";
import type { AlertRule } from "../types";
import { AlertsWorkspace } from "./AlertsWorkspace";

vi.mock("../api/resources", () => ({
  createProjectAlertRule: vi.fn(),
  deleteProjectAlertRule: vi.fn(),
  getProjectAlertRules: vi.fn(),
  updateProjectAlertRule: vi.fn(),
}));

const mockedCreateProjectAlertRule = vi.mocked(createProjectAlertRule);
const mockedDeleteProjectAlertRule = vi.mocked(deleteProjectAlertRule);
const mockedGetProjectAlertRules = vi.mocked(getProjectAlertRules);
const mockedUpdateProjectAlertRule = vi.mocked(updateProjectAlertRule);

const rule: AlertRule = {
  id: "rule-a",
  project_id: "project-a",
  name: "Checkout saturation",
  metric_name: "checkout.queue.depth",
  time_range: "1h",
  service_name: "checkout",
  environment: "production",
  comparator: "gte",
  threshold: 10,
  enabled: true,
  state: {
    status: "firing",
    evaluated_at: "2026-10-11T17:31:59Z",
    state_changed_at: "2026-10-11T17:30:00Z",
    source_timestamp: "2026-10-11T17:31:55Z",
    error_code: "",
    updated_at: "2026-10-11T17:31:59Z",
  },
  created_by: 1,
  created_at: "2026-10-11T17:00:00Z",
  updated_at: "2026-10-11T17:00:00Z",
};

function renderAlerts(canManage = true) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AlertsWorkspace projectId="project-a" canManage={canManage} />
    </QueryClientProvider>,
  );
}

describe("AlertsWorkspace", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  beforeEach(() => {
    vi.clearAllMocks();
    mockedGetProjectAlertRules.mockResolvedValue([rule]);
    mockedCreateProjectAlertRule.mockResolvedValue(rule);
    mockedUpdateProjectAlertRule.mockResolvedValue(rule);
    mockedDeleteProjectAlertRule.mockResolvedValue(undefined);
  });

  it("renders persisted current state without querying telemetry from the browser", async () => {
    renderAlerts();

    const card = (await screen.findByText("Checkout saturation")).closest("article");
    expect(card).not.toBeNull();
    expect(within(card as HTMLElement).getByText("firing")).toBeInTheDocument();
    expect(within(card as HTMLElement).getAllByText("checkout.queue.depth")).toHaveLength(2);
    expect(within(card as HTMLElement).getByText("service=checkout")).toBeInTheDocument();
    expect(within(card as HTMLElement).getByText("environment=production")).toBeInTheDocument();
    expect(mockedGetProjectAlertRules).toHaveBeenCalledWith("project-a");
  });

  it("keeps rule management read-only for viewers", async () => {
    renderAlerts(false);

    expect(await screen.findByText("Checkout saturation")).toBeInTheDocument();
    expect(screen.getByText(/Viewer access is read only/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Create rule" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Disable" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument();
  });

  it("creates a typed scalar threshold rule", async () => {
    mockedGetProjectAlertRules.mockResolvedValue([]);
    renderAlerts();

    fireEvent.change(screen.getByLabelText("Rule name"), { target: { value: "Queue depth" } });
    fireEvent.change(screen.getByLabelText("Metric name"), {
      target: { value: "checkout.queue.depth" },
    });
    fireEvent.change(screen.getByLabelText("Window"), { target: { value: "6h" } });
    fireEvent.change(screen.getByLabelText("Service (optional)"), {
      target: { value: "checkout" },
    });
    fireEvent.change(screen.getByLabelText("Environment (optional)"), {
      target: { value: "production" },
    });
    fireEvent.change(screen.getByLabelText("Comparator"), { target: { value: "gte" } });
    fireEvent.change(screen.getByLabelText("Threshold"), { target: { value: "10" } });
    fireEvent.click(screen.getByRole("button", { name: "Create rule" }));

    await waitFor(() => {
      expect(mockedCreateProjectAlertRule).toHaveBeenCalledWith("project-a", {
        name: "Queue depth",
        metric_name: "checkout.queue.depth",
        time_range: "6h",
        service_name: "checkout",
        environment: "production",
        comparator: "gte",
        threshold: 10,
        enabled: true,
      });
    });
  });

  it("rejects an empty or non-finite threshold before calling the API", async () => {
    mockedGetProjectAlertRules.mockResolvedValue([]);
    renderAlerts();

    fireEvent.change(screen.getByLabelText("Rule name"), { target: { value: "Queue depth" } });
    fireEvent.change(screen.getByLabelText("Metric name"), {
      target: { value: "checkout.queue.depth" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create rule" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/finite numeric threshold/i);
    expect(mockedCreateProjectAlertRule).not.toHaveBeenCalled();
  });

  it("enables and disables rules through the existing project-scoped patch API", async () => {
    renderAlerts();
    await screen.findByText("Checkout saturation");

    fireEvent.click(screen.getByRole("button", { name: "Disable" }));

    await waitFor(() => {
      expect(mockedUpdateProjectAlertRule).toHaveBeenCalledWith("project-a", "rule-a", {
        enabled: false,
      });
    });
  });

  it("loads a rule into the editor and saves the complete typed condition", async () => {
    renderAlerts();
    await screen.findByText("Checkout saturation");

    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    fireEvent.change(screen.getByLabelText("Threshold"), { target: { value: "12.5" } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => {
      expect(mockedUpdateProjectAlertRule).toHaveBeenCalledWith(
        "project-a",
        "rule-a",
        expect.objectContaining({
          name: "Checkout saturation",
          metric_name: "checkout.queue.depth",
          comparator: "gte",
          threshold: 12.5,
        }),
      );
    });
  });

  it("deletes a rule only after confirmation", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    renderAlerts();
    await screen.findByText("Checkout saturation");

    fireEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => {
      expect(mockedDeleteProjectAlertRule).toHaveBeenCalledWith("project-a", "rule-a");
    });
  });
});
