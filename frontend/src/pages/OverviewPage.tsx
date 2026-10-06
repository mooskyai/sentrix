import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createOrganization,
  createProject,
  getOrganizations,
  getProjects,
} from "../api/resources";

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
    if (!effectiveOrgId) return;
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
          <p className="eyebrow">Platform foundation</p>
          <h1>Workspace</h1>
          <p className="muted">Create the tenant boundary before connecting telemetry.</p>
        </div>
      </div>

      <div className="grid two">
        <section className="panel">
          <h2>Organizations</h2>
          <form onSubmit={submitOrganization} className="stack">
            <input placeholder="Organization name" value={orgName} onChange={(e) => setOrgName(e.target.value)} required />
            <input placeholder="organization-slug" value={orgSlug} onChange={(e) => setOrgSlug(e.target.value)} required />
            <button className="button" disabled={createOrg.isPending} type="submit">Create organization</button>
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
                <span>{organization.name}</span><small>{organization.role}</small>
              </button>
            ))}
            {!organizations.isPending && organizations.data?.length === 0 && (
              <p className="muted">No organizations yet.</p>
            )}
          </div>
        </section>

        <section className="panel">
          <h2>Projects</h2>
          <form onSubmit={submitProject} className="stack">
            <input placeholder="Project name" value={projectName} onChange={(e) => setProjectName(e.target.value)} required />
            <input placeholder="project-slug" value={projectSlug} onChange={(e) => setProjectSlug(e.target.value)} required />
            <button className="button" disabled={!effectiveOrgId || createProjectMutation.isPending} type="submit">Create project</button>
            {createProjectMutation.error && <div className="error">{createProjectMutation.error.message}</div>}
          </form>
          <div className="list">
            {visibleProjects.map((project) => (
              <div className="list-item" key={project.id}><span>{project.name}</span><small>{project.slug}</small></div>
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
