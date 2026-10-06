import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createProjectApiKey,
  getProjectApiKeys,
  revokeProjectApiKey,
} from "../api/resources";
import type { ProjectApiKey, ProjectApiKeyCreateResult } from "../types";
import { ProjectApiKeysPanel } from "./ProjectApiKeysPanel";

vi.mock("../api/resources", () => ({
  createProjectApiKey: vi.fn(),
  getProjectApiKeys: vi.fn(),
  revokeProjectApiKey: vi.fn(),
}));

const mockedCreateProjectApiKey = vi.mocked(createProjectApiKey);
const mockedGetProjectApiKeys = vi.mocked(getProjectApiKeys);
const mockedRevokeProjectApiKey = vi.mocked(revokeProjectApiKey);

function renderPanel(canManage = true) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ProjectApiKeysPanel projectId="project-a" canManage={canManage} />
    </QueryClientProvider>,
  );
}

const activeKey: ProjectApiKey = {
  id: "key-a",
  project_id: "project-a",
  name: "Production collector",
  prefix: "abc123",
  scopes: ["telemetry:write"],
  created_by: 1,
  expires_at: null,
  last_used_at: null,
  revoked_at: null,
  created_at: "2026-10-06T10:00:00Z",
};

describe("ProjectApiKeysPanel", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.clearAllMocks();
    mockedGetProjectApiKeys.mockResolvedValue([]);
    mockedRevokeProjectApiKey.mockResolvedValue(undefined);
  });

  it("does not request API-key metadata for a viewer", () => {
    renderPanel(false);

    expect(screen.getByText(/requires project write access/i)).toBeInTheDocument();
    expect(mockedGetProjectApiKeys).not.toHaveBeenCalled();
  });

  it("lists safe credential metadata without a raw secret", async () => {
    mockedGetProjectApiKeys.mockResolvedValue([activeKey]);

    renderPanel();

    expect(await screen.findByText("Production collector")).toBeInTheDocument();
    expect(screen.getByText("sentrix_pk_abc123_••••")).toBeInTheDocument();
    expect(screen.getAllByText("telemetry:write").length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText(/sentrix_pk_abc123_secret/i)).not.toBeInTheDocument();
  });

  it("reveals a newly created raw secret only in the one-time result state", async () => {
    const created: ProjectApiKeyCreateResult = {
      ...activeKey,
      id: "key-created",
      name: "New collector",
      secret: "sentrix_pk_newprefix_supersecret",
    };
    mockedCreateProjectApiKey.mockResolvedValue(created);

    renderPanel();

    fireEvent.change(screen.getByLabelText("Key name"), { target: { value: "New collector" } });
    fireEvent.click(screen.getByRole("button", { name: "Create API key" }));

    expect(await screen.findByText("sentrix_pk_newprefix_supersecret")).toBeInTheDocument();
    expect(screen.getByText(/will not show the raw credential again/i)).toBeInTheDocument();
    expect(mockedCreateProjectApiKey).toHaveBeenCalledWith("project-a", {
      name: "New collector",
      expires_at: null,
    });
  });
});
