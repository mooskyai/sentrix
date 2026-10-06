import { describe, expect, it } from "vitest";

import type { Organization, Project } from "./types";
import { canWriteProjects, resolveWorkspace, workspacePath } from "./workspace";

const organizations: Organization[] = [
  {
    id: "org-a-id",
    name: "Org A",
    slug: "org-a",
    role: "owner",
    created_at: "2026-10-06T00:00:00Z",
    updated_at: "2026-10-06T00:00:00Z",
  },
  {
    id: "org-b-id",
    name: "Org B",
    slug: "org-b",
    role: "viewer",
    created_at: "2026-10-06T00:00:00Z",
    updated_at: "2026-10-06T00:00:00Z",
  },
];

const projects: Project[] = [
  {
    id: "project-a-id",
    organization_id: "org-a-id",
    name: "Project A",
    slug: "project-a",
    created_by: 1,
    created_at: "2026-10-06T00:00:00Z",
    updated_at: "2026-10-06T00:00:00Z",
  },
  {
    id: "project-b-id",
    organization_id: "org-b-id",
    name: "Project B",
    slug: "project-b",
    created_by: 2,
    created_at: "2026-10-06T00:00:00Z",
    updated_at: "2026-10-06T00:00:00Z",
  },
];

describe("workspace helpers", () => {
  it("builds canonical project workspace paths", () => {
    expect(workspacePath("org-a", "project-a")).toBe("/orgs/org-a/projects/project-a");
    expect(workspacePath("org-a", "project-a", "logs")).toBe(
      "/orgs/org-a/projects/project-a/logs",
    );
  });

  it("resolves only a project that belongs to the requested visible organization", () => {
    expect(resolveWorkspace(organizations, projects, "org-a", "project-a")?.project.id).toBe(
      "project-a-id",
    );
    expect(resolveWorkspace(organizations, projects, "org-a", "project-b")).toBeNull();
  });

  it("returns no workspace for unknown organization or project slugs", () => {
    expect(resolveWorkspace(organizations, projects, "missing", "project-a")).toBeNull();
    expect(resolveWorkspace(organizations, projects, "org-a", "missing")).toBeNull();
  });

  it("treats viewer membership as read-only", () => {
    expect(canWriteProjects("owner")).toBe(true);
    expect(canWriteProjects("admin")).toBe(true);
    expect(canWriteProjects("editor")).toBe(true);
    expect(canWriteProjects("viewer")).toBe(false);
  });
});
