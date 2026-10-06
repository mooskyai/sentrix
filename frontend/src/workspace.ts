import type { Organization, OrganizationRole, Project } from "./types";

export const WORKSPACE_SECTIONS = [
  "overview",
  "metrics",
  "logs",
  "traces",
  "dashboards",
  "alerts",
  "settings",
] as const;

export type WorkspaceSection = (typeof WORKSPACE_SECTIONS)[number];

const WRITE_ROLES: ReadonlySet<OrganizationRole> = new Set(["owner", "admin", "editor"]);

export interface ResolvedWorkspace {
  organization: Organization;
  project: Project;
}

export function canWriteProjects(role: OrganizationRole): boolean {
  return WRITE_ROLES.has(role);
}

export function isWorkspaceSection(value: string | undefined): value is WorkspaceSection {
  return WORKSPACE_SECTIONS.includes(value as WorkspaceSection);
}

export function workspacePath(
  organizationSlug: string,
  projectSlug: string,
  section: WorkspaceSection = "overview",
): string {
  const base = `/orgs/${encodeURIComponent(organizationSlug)}/projects/${encodeURIComponent(projectSlug)}`;
  return section === "overview" ? base : `${base}/${section}`;
}

export function resolveWorkspace(
  organizations: Organization[],
  projects: Project[],
  organizationSlug: string,
  projectSlug: string,
): ResolvedWorkspace | null {
  const organization = organizations.find((candidate) => candidate.slug === organizationSlug);
  if (!organization) return null;

  const project = projects.find(
    (candidate) =>
      candidate.organization_id === organization.id && candidate.slug === projectSlug,
  );
  if (!project) return null;

  return { organization, project };
}
