import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Organization, Project } from "./types";
import {
  readWorkspacePreference,
  reconcileWorkspacePreference,
  workspacePreferenceKey,
  writeWorkspacePreference,
} from "./workspacePersistence";

const organizations: Organization[] = [
  { id: "empty", slug: "empty", name: "Empty", role: "owner", created_at: "", updated_at: "" },
  { id: "first", slug: "first", name: "First", role: "viewer", created_at: "", updated_at: "" },
  { id: "second", slug: "second", name: "Second", role: "owner", created_at: "", updated_at: "" },
];
const projects: Project[] = [
  { id: "first-a", organization_id: "first", slug: "a", name: "A", created_by: 1, created_at: "", updated_at: "" },
  { id: "first-b", organization_id: "first", slug: "b", name: "B", created_by: 1, created_at: "", updated_at: "" },
  { id: "second-a", organization_id: "second", slug: "a", name: "A", created_by: 1, created_at: "", updated_at: "" },
];

beforeEach(() => { localStorage.clear(); sessionStorage.clear(); });
afterEach(() => { vi.unstubAllGlobals(); });

describe("workspace persistence", () => {
  it("defaults to the first authorized organization with a project and its first project", () => {
    expect(reconcileWorkspacePreference(organizations, projects, {
      organizationId: "", projectId: "", stale: false,
    })).toEqual({ organizationId: "first", projectId: "first-a", stale: false });
  });

  it("keeps a valid remembered project and marks missing or mismatched IDs stale", () => {
    expect(reconcileWorkspacePreference(organizations, projects, {
      organizationId: "first", projectId: "first-b", stale: false,
    })).toEqual({ organizationId: "first", projectId: "first-b", stale: false });
    expect(reconcileWorkspacePreference(organizations, projects, {
      organizationId: "first", projectId: "second-a", stale: false,
    })).toEqual({ organizationId: "first", projectId: "first-a", stale: true });
    expect(reconcileWorkspacePreference(organizations, projects, {
      organizationId: "revoked", projectId: "old", stale: false,
    })).toEqual({ organizationId: "first", projectId: "first-a", stale: true });
  });

  it("handles an empty catalog and honors an explicitly selected organization without projects", () => {
    expect(reconcileWorkspacePreference([], [], {
      organizationId: "gone", projectId: "gone", stale: false,
    })).toEqual({ organizationId: "", projectId: "", stale: true });
    expect(reconcileWorkspacePreference(organizations, projects, {
      organizationId: "empty", projectId: "", stale: false,
    })).toEqual({ organizationId: "empty", projectId: "", stale: false });
  });

  it("persists only IDs and a stale flag in user-scoped versioned localStorage", () => {
    writeWorkspacePreference(1, { organizationId: "first", projectId: "first-b", stale: true });
    expect(JSON.parse(localStorage.getItem(workspacePreferenceKey(1)) ?? "null")).toEqual({
      version: 1, organizationId: "first", projectId: "first-b", stale: true,
    });
    expect(readWorkspacePreference(1)).toEqual({
      organizationId: "first", projectId: "first-b", stale: true,
    });
    expect(readWorkspacePreference(2)).toEqual({
      organizationId: "", projectId: "", stale: false,
    });
  });

  it("migrates the older session-scoped choice when no local preference exists", () => {
    sessionStorage.setItem("sentrix.workspace.1", JSON.stringify({
      organizationId: "second", projectId: "second-a",
    }));
    expect(readWorkspacePreference(1)).toEqual({
      organizationId: "second", projectId: "second-a", stale: false,
    });
  });

  it("treats corrupted saved data as stale without throwing", () => {
    localStorage.setItem(workspacePreferenceKey(1), "{invalid");
    expect(readWorkspacePreference(1)).toEqual({
      organizationId: "", projectId: "", stale: true,
    });
  });

  it("tolerates browser storage failures", () => {
    vi.stubGlobal("localStorage", {
      getItem: () => { throw new Error("blocked"); },
      setItem: () => { throw new Error("blocked"); },
    });
    expect(() => writeWorkspacePreference(1, {
      organizationId: "first", projectId: "first-a", stale: false,
    })).not.toThrow();
    expect(readWorkspacePreference(1).organizationId).toBe("");
  });
});
