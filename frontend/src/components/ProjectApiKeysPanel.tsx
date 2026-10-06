import { type FormEvent, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createProjectApiKey,
  getProjectApiKeys,
  revokeProjectApiKey,
} from "../api/resources";
import type { ProjectApiKey } from "../types";

interface ProjectApiKeysPanelProps {
  projectId: string;
  canManage: boolean;
}

interface CreatedSecret {
  name: string;
  secret: string;
}

function formatTimestamp(value: string | null): string {
  if (!value) return "Never";
  return new Date(value).toLocaleString();
}

function keyStatus(apiKey: ProjectApiKey): "active" | "expired" | "revoked" {
  if (apiKey.revoked_at) return "revoked";
  if (apiKey.expires_at && new Date(apiKey.expires_at).getTime() <= Date.now()) return "expired";
  return "active";
}

export function ProjectApiKeysPanel({ projectId, canManage }: ProjectApiKeysPanelProps) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  const [creating, setCreating] = useState(false);
  const [revokingId, setRevokingId] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [createdSecret, setCreatedSecret] = useState<CreatedSecret | null>(null);
  const [copied, setCopied] = useState(false);
  const queryKey = ["project-api-keys", projectId] as const;

  const apiKeys = useQuery({
    queryKey,
    queryFn: () => getProjectApiKeys(projectId),
    enabled: canManage,
    retry: false,
  });

  if (!canManage) {
    return (
      <div className="empty-feature">
        <strong>API-key management requires project write access.</strong>
        <p className="muted">
          Owners, admins, and editors can manage telemetry credentials. Your viewer access remains
          read only, and Sentrix does not request key metadata for this project.
        </p>
      </div>
    );
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName) {
      setCreateError("Key name is required.");
      return;
    }

    let expiry: string | null = null;
    if (expiresAt) {
      const parsedExpiry = new Date(expiresAt);
      if (Number.isNaN(parsedExpiry.getTime()) || parsedExpiry.getTime() <= Date.now()) {
        setCreateError("Expiry must be in the future.");
        return;
      }
      expiry = parsedExpiry.toISOString();
    }

    setCreating(true);
    setCreateError(null);
    setActionError(null);
    setCopied(false);
    try {
      const created = await createProjectApiKey(projectId, {
        name: trimmedName,
        expires_at: expiry,
      });
      setCreatedSecret({ name: created.name, secret: created.secret });
      setName("");
      setExpiresAt("");
      await queryClient.invalidateQueries({ queryKey });
    } catch (error) {
      setCreateError(error instanceof Error ? error.message : "Unable to create API key.");
    } finally {
      setCreating(false);
    }
  }

  async function handleCopySecret() {
    if (!createdSecret) return;
    if (!navigator.clipboard) {
      setActionError("Clipboard access is unavailable. Copy the secret manually before dismissing it.");
      return;
    }

    try {
      await navigator.clipboard.writeText(createdSecret.secret);
      setCopied(true);
      setActionError(null);
    } catch {
      setActionError("Unable to copy the secret. Copy it manually before dismissing it.");
    }
  }

  async function handleRevoke(apiKey: ProjectApiKey) {
    if (apiKey.revoked_at || revokingId) return;
    const confirmed = window.confirm(
      `Revoke “${apiKey.name}”? Collectors using this credential will stop authenticating.`,
    );
    if (!confirmed) return;

    setRevokingId(apiKey.id);
    setActionError(null);
    try {
      await revokeProjectApiKey(projectId, apiKey.id);
      await queryClient.invalidateQueries({ queryKey });
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Unable to revoke API key.");
    } finally {
      setRevokingId(null);
    }
  }

  return (
    <div className="settings-layout">
      <section className="api-key-panel" aria-labelledby="api-key-create-heading">
        <div className="api-key-header">
          <div>
            <h3 id="api-key-create-heading">Create telemetry credential</h3>
            <p className="muted">
              New credentials receive the <span className="mono">telemetry:write</span> scope.
            </p>
          </div>
        </div>

        <form className="api-key-form" onSubmit={(event) => void handleCreate(event)}>
          <label>
            <span>Key name</span>
            <input
              autoComplete="off"
              maxLength={160}
              onChange={(event) => setName(event.target.value)}
              placeholder="Production collector"
              value={name}
            />
          </label>
          <label>
            <span>Expiry (optional)</span>
            <input
              onChange={(event) => setExpiresAt(event.target.value)}
              type="datetime-local"
              value={expiresAt}
            />
          </label>
          <button className="button" disabled={creating} type="submit">
            {creating ? "Creating…" : "Create API key"}
          </button>
        </form>

        {createError ? <p className="error" role="alert">{createError}</p> : null}

        {createdSecret ? (
          <div className="api-key-secret" aria-live="polite">
            <div>
              <strong>Copy this secret now.</strong>
              <p className="muted">
                Sentrix will not show the raw credential again after you dismiss this message or leave
                the project.
              </p>
            </div>
            <code className="secret-value">{createdSecret.secret}</code>
            <div className="api-key-actions">
              <button className="button secondary" onClick={() => void handleCopySecret()} type="button">
                {copied ? "Copied" : "Copy secret"}
              </button>
              <button
                className="button secondary"
                onClick={() => {
                  setCreatedSecret(null);
                  setCopied(false);
                }}
                type="button"
              >
                Dismiss
              </button>
            </div>
          </div>
        ) : null}
      </section>

      <section className="api-key-panel" aria-labelledby="api-key-list-heading">
        <div className="api-key-header">
          <div>
            <h3 id="api-key-list-heading">Project API keys</h3>
            <p className="muted">Only safe metadata is returned after a credential is created.</p>
          </div>
          <span className="scope-badge">telemetry:write</span>
        </div>

        {actionError ? <p className="error" role="alert">{actionError}</p> : null}
        {apiKeys.isPending ? <p className="muted">Loading API keys…</p> : null}
        {apiKeys.isError ? (
          <p className="error" role="alert">
            {apiKeys.error instanceof Error ? apiKeys.error.message : "Unable to load API keys."}
          </p>
        ) : null}

        {apiKeys.data?.length === 0 ? (
          <div className="empty-feature">
            <strong>No project API keys yet.</strong>
            <p className="muted">Create a credential when you are ready to connect a collector.</p>
          </div>
        ) : null}

        {apiKeys.data?.length ? (
          <div className="api-key-list">
            {apiKeys.data.map((apiKey) => {
              const status = keyStatus(apiKey);
              return (
                <article className="api-key-row" key={apiKey.id}>
                  <div className="api-key-main">
                    <div className="api-key-title">
                      <strong>{apiKey.name}</strong>
                      <span className={`key-status ${status}`}>{status}</span>
                    </div>
                    <code className="mono">sentrix_pk_{apiKey.prefix}_••••</code>
                    <div className="scope-list" aria-label={`Scopes for ${apiKey.name}`}>
                      {apiKey.scopes.map((scope) => (
                        <span className="scope-badge" key={scope}>
                          {scope}
                        </span>
                      ))}
                    </div>
                  </div>
                  <dl className="api-key-meta">
                    <div>
                      <dt>Created</dt>
                      <dd>{formatTimestamp(apiKey.created_at)}</dd>
                    </div>
                    <div>
                      <dt>Expires</dt>
                      <dd>{apiKey.expires_at ? formatTimestamp(apiKey.expires_at) : "No expiry"}</dd>
                    </div>
                    <div>
                      <dt>Last used</dt>
                      <dd>{formatTimestamp(apiKey.last_used_at)}</dd>
                    </div>
                  </dl>
                  <div className="api-key-actions">
                    {apiKey.revoked_at ? (
                      <span className="muted">Revoked {formatTimestamp(apiKey.revoked_at)}</span>
                    ) : (
                      <button
                        className="button danger"
                        disabled={revokingId === apiKey.id}
                        onClick={() => void handleRevoke(apiKey)}
                        type="button"
                      >
                        {revokingId === apiKey.id ? "Revoking…" : "Revoke"}
                      </button>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        ) : null}
      </section>
    </div>
  );
}
