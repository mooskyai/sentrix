import type { Organization, Project } from "./types";

export interface WorkspacePreference {
  organizationId: string;
  projectId: string;
  // Sticky until a user explicitly chooses a workspace or follows an authorized deep link.
  stale: boolean;
}

const STORAGE_VERSION = 1;
const EMPTY_SELECTION: WorkspacePreference = {
  organizationId: "",
  projectId: "",
  stale: false,
};

export function workspacePreferenceKey(userId: number): string {
  return `sentrix.workspace.v2.${userId}`;
}

function asPreference(value: unknown, legacy = false): WorkspacePreference | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const record = value as Record<string, unknown>;
  if (!legacy && record.version !== STORAGE_VERSION) return null;
  if (typeof record.organizationId !== "string" || typeof record.projectId !== "string") {
    return null;
  }
  return {
    organizationId: record.organizationId,
    projectId: record.projectId,
    stale: !legacy && record.stale === true,
  };
}

export function readWorkspacePreference(userId: number): WorkspacePreference {
  try {
    const current = localStorage.getItem(workspacePreferenceKey(userId));
    if (current !== null) {
      try {
        return asPreference(JSON.parse(current) as unknown) ?? { ...EMPTY_SELECTION, stale: true };
      } catch {
        return { ...EMPTY_SELECTION, stale: true };
      }
    }
    // One-time migration from the existing per-user tab-scoped selection.
    const legacy = sessionStorage.getItem(`sentrix.workspace.${userId}`);
    if (legacy !== null) {
      try {
        return asPreference(JSON.parse(legacy) as unknown, true) ?? {
          ...EMPTY_SELECTION, stale: true,
        };
      } catch {
        return { ...EMPTY_SELECTION, stale: true };
      }
    }
  } catch {
    // Storage can be blocked, disabled, corrupt or unavailable.
  }
  return { ...EMPTY_SELECTION };
}

export function writeWorkspacePreference(userId: number, selection: WorkspacePreference): void {
  try {
    localStorage.setItem(workspacePreferenceKey(userId), JSON.stringify({
      version: STORAGE_VERSION,
      organizationId: selection.organizationId,
      projectId: selection.projectId,
      stale: selection.stale,
    }));
  } catch {
    // A blocked/quota-limited localStorage must not prevent using the workspace.
  }
}

export function reconcileWorkspacePreference(
  organizations: Organization[], projects: Project[], saved: WorkspacePreference,
): WorkspacePreference {
  const preferredOrg = organizations.find((organization) => organization.id === saved.organizationId);
  // Prefer a usable workspace on first load, otherwise allow an org without projects.
  const organization = preferredOrg ?? organizations.find(
    (candidate) => projects.some((project) => project.organization_id === candidate.id),
  ) ?? organizations[0];
  const preferredProject = projects.find(
    (candidate) => candidate.id === saved.projectId && candidate.organization_id === organization?.id,
  );
  const project = preferredProject ?? projects.find(
    (candidate) => candidate.organization_id === organization?.id,
  );
  const removedSelection = Boolean(
    (saved.organizationId && !preferredOrg) || (saved.projectId && !preferredProject),
  );
  return {
    organizationId: organization?.id ?? "",
    projectId: project?.id ?? "",
    stale: saved.stale || removedSelection,
  };
}
