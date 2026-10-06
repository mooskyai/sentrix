export interface User {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
}

export type OrganizationRole = "owner" | "admin" | "editor" | "viewer";

export interface Organization {
  id: string;
  name: string;
  slug: string;
  role: OrganizationRole;
  created_at: string;
  updated_at: string;
}

export interface Project {
  id: string;
  organization_id: string;
  name: string;
  slug: string;
  created_by: number | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectApiKey {
  id: string;
  project_id: string;
  name: string;
  prefix: string;
  scopes: string[];
  created_by: number | null;
  expires_at: string | null;
  last_used_at: string | null;
  revoked_at: string | null;
  created_at: string;
}

export interface ProjectApiKeyCreateResult extends ProjectApiKey {
  secret: string;
}
