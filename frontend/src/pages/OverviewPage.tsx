import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import {
  createOrganization,
  createProject,
  getOrganizations,
  getProjects,
} from "../api/resources";
import { canWriteProjects, workspacePath } from "../workspace";

export function OverviewPage() {
  const queryClient = useQueryClient();
  const organizations = useQuery({ queryKey: ["organizations"], queryFn: getOrganizations });
  const projects = useQuery({ queryKey: ["projects"], queryFn: getProjects });
  const [selectedOrgId, setSelectedOrgId] = useState("");
  const [orgName, setOrgName] = useState("");
  const [orgSlug, setOrgSlug] = useState("");
  const [projectName, setProjectName] = useState("");
  const [projectSlug, setProjectSlug] = useState("");

  const effectiveOrgId = selectedOrgId || organizations.data?.[0]?.id || "";
  const selectedOrganization = (organizations.data ?? []).find(
    (organization) => organization.id === effectiveOrgId,
  );
  const visibleProjects = useMemo(
    () => (projects.data ?? []).filter((project) => project.organization_id === effectiveOrgId),
    [projects.data, effectiveOrgId],
  );

  const createOrg = useMutation({
    mutationFn: createOrganization,
    onSuccess: async (organization) => {
      setSelectedOrgId(organization.id);
      setOrgName("");
      setOrgSlug("");
      await queryClient.invalidateQueries({ queryKey: ["organizations"] });
    },
  });

  const createProjectMutation = useMutation({
    mutationFn: createProject,
    onSuccess: async () => {
      setProjectName("");
      setProjectSlug("");
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  function submitOrganization(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    createOrg.mutate({ name: orgName, slug: orgSlug });
  }

  function submitProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!effectiveOrgId || !selectedOrganization) return;
    createProjectMutation.mutate({
      organization_id: effectiveOrgId,
      name: projectName,
      slug: projectSlug,
    });
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Control plane</p>
          <h1>Organizations & projects</h1>
          <p className="muted">
            Select a tenant, create projects when your role allows it, then enter a project workspace.
          </p>
        </div>
      </div>

      <div className="grid two">
        <section className="panel">
          <h2>Organizations</h2>
          <form onSubmit={submitOrganization} className="stack">
            <input
              placeholder="Organization name"
              value={orgName}
              onChange={(event) => setOrgName(event.target.value)}
              required
            />
            <input
              placeholder="organization-slug"
              value={orgSlug}
              onChange={(event) => setOrgSlug(event.target.value)}
              required
            />
            <button className="button" disabled={createOrg.isPending} type="submit">
              Create organization
            </button>
            {createOrg.error && <div className="error">{createOrg.error.message}</div>}
          </form>
          <div className="list">
            {(organizations.data ?? []).map((organization) => (
              <button
                key={organization.id}
                className={`list-item ${effectiveOrgId === organization.id ? "selected" : ""}`}
                type="button"
                onClick={() => setSelectedOrgId(organization.id)}
              >
                <span>{organization.name}</span>
                <small>{organization.role}</small>
              </button>
            ))}
            {!organizations.isPending && organizations.data?.length === 0 && (
              <p className="muted">No organizations yet.</p>
            )}
          </div>
        </section>

        <section className="panel">
          <h2>Projects</h2>
          {selectedOrganization && canWriteProjects(selectedOrganization.role) ? (
            <form onSubmit={submitProject} className="stack">
              <input
                placeholder="Project name"
                value={projectName}
                onChange={(event) => setProjectName(event.target.value)}
                required
              />
              <input
                placeholder="project-slug"
                value={projectSlug}
                onChange={(event) => setProjectSlug(event.target.value)}
                required
              />
              <button className="button" disabled={createProjectMutation.isPending} type="submit">
                Create project
              </button>
              {createProjectMutation.error && (
                <div className="error">{createProjectMutation.error.message}</div>
              )}
            </form>
          ) : selectedOrganization ? (
            <div className="notice">
              Your <strong>{selectedOrganization.role}</strong> role is read-only for project changes.
            </div>
          ) : (
            <p className="muted">Create or select an organization before creating a project.</p>
          )}

          <div className="list">
            {visibleProjects.map((project) => (
              <Link
                className="list-item workspace-link"
                key={project.id}
                to={workspacePath(selectedOrganization?.slug ?? "", project.slug)}
              >
                <span>{project.name}</span>
                <span className="list-meta">
                  <small>{project.slug}</small>
                  <span aria-hidden="true">→</span>
                </span>
              </Link>
            ))}
            {!!effectiveOrgId && !projects.isPending && visibleProjects.length === 0 && (
              <p className="muted">No projects in this organization yet.</p>
            )}
          </div>
        </section>
      </div>
    </>
  );
}
