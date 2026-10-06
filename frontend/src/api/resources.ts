import { api, ensureCsrf } from "./client";
import type { Organization, Project, User } from "../types";

export async function login(username: string, password: string): Promise<User> {
  await ensureCsrf();
  return api<User>("/auth/login/", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export function logout(): Promise<void> {
  return api<void>("/auth/logout/", { method: "POST" });
}

export function getMe(): Promise<User> {
  return api<User>("/auth/me/");
}

export function getOrganizations(): Promise<Organization[]> {
  return api<Organization[]>("/organizations/");
}

export function createOrganization(input: { name: string; slug: string }): Promise<Organization> {
  return api<Organization>("/organizations/", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getProjects(): Promise<Project[]> {
  return api<Project[]>("/projects/");
}

export function createProject(input: {
  organization_id: string;
  name: string;
  slug: string;
}): Promise<Project> {
  return api<Project>("/projects/", {
    method: "POST",
    body: JSON.stringify(input),
  });
}
