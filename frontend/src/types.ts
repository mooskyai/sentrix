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
