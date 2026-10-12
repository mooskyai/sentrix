import { type FormEvent, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createProjectAlertRule,
  deleteProjectAlertRule,
  getProjectAlertRules,
  updateProjectAlertRule,
} from "../api/resources";
import type {
  AlertRule,
  AlertRuleComparator,
  AlertRuleTimeRange,
  AlertRuleWriteInput,
} from "../types";

interface AlertsWorkspaceProps {
  projectId: string;
  canManage: boolean;
}

interface AlertFormState {
  name: string;
  metricName: string;
  timeRange: AlertRuleTimeRange;
  serviceName: string;
  environment: string;
  comparator: AlertRuleComparator;
  threshold: string;
  enabled: boolean;
}

const EMPTY_FORM: AlertFormState = {
  name: "",
  metricName: "",
  timeRange: "1h",
  serviceName: "",
  environment: "",
  comparator: "gt",
  threshold: "",
  enabled: true,
};

const TIME_RANGE_LABEL: Record<AlertRuleTimeRange, string> = {
  "1h": "Last 1 hour",
  "6h": "Last 6 hours",
  "24h": "Last 24 hours",
  "7d": "Last 7 days",
};

const COMPARATOR_LABEL: Record<AlertRuleComparator, string> = {
  gt: ">",
  gte: "≥",
  lt: "<",
  lte: "≤",
};

function formatTimestamp(value: string | null): string {
  if (!value) return "Not yet";
  return new Date(value).toLocaleString();
}

function formFromRule(rule: AlertRule): AlertFormState {
  return {
    name: rule.name,
    metricName: rule.metric_name,
    timeRange: rule.time_range,
    serviceName: rule.service_name,
    environment: rule.environment,
    comparator: rule.comparator,
    threshold: String(rule.threshold),
    enabled: rule.enabled,
  };
}

function toWriteInput(form: AlertFormState): AlertRuleWriteInput | null {
  const name = form.name.trim();
  const metricName = form.metricName.trim();
  const thresholdText = form.threshold.trim();
  const threshold = Number(thresholdText);
  if (!name || !metricName || !thresholdText || !Number.isFinite(threshold)) return null;

  return {
    name,
    metric_name: metricName,
    time_range: form.timeRange,
    service_name: form.serviceName.trim(),
    environment: form.environment.trim(),
    comparator: form.comparator,
    threshold,
    enabled: form.enabled,
  };
}

export function AlertsWorkspace({ projectId, canManage }: AlertsWorkspaceProps) {
  const queryClient = useQueryClient();
  const queryKey = ["alert-rules", projectId] as const;
  const [form, setForm] = useState<AlertFormState>(EMPTY_FORM);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [actionId, setActionId] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const rules = useQuery({
    queryKey,
    queryFn: () => getProjectAlertRules(projectId),
    retry: false,
  });

  function resetForm() {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setFormError(null);
  }

  async function refreshRules() {
    setActionError(null);
    await queryClient.invalidateQueries({ queryKey });
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const input = toWriteInput(form);
    if (!input) {
      setFormError("Rule name, metric name, and a finite numeric threshold are required.");
      return;
    }

    setSaving(true);
    setFormError(null);
    setActionError(null);
    try {
      if (editingId) {
        await updateProjectAlertRule(projectId, editingId, input);
      } else {
        await createProjectAlertRule(projectId, input);
      }
      resetForm();
      await queryClient.invalidateQueries({ queryKey });
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Unable to save alert rule.");
    } finally {
      setSaving(false);
    }
  }

  async function toggleRule(rule: AlertRule) {
    if (!canManage || actionId) return;
    setActionId(rule.id);
    setActionError(null);
    try {
      await updateProjectAlertRule(projectId, rule.id, { enabled: !rule.enabled });
      await queryClient.invalidateQueries({ queryKey });
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Unable to update alert rule.");
    } finally {
      setActionId(null);
    }
  }

  async function removeRule(rule: AlertRule) {
    if (!canManage || actionId) return;
    if (!window.confirm(`Delete alert rule “${rule.name}”?`)) return;

    setActionId(rule.id);
    setActionError(null);
    try {
      await deleteProjectAlertRule(projectId, rule.id);
      if (editingId === rule.id) resetForm();
      await queryClient.invalidateQueries({ queryKey });
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Unable to delete alert rule.");
    } finally {
      setActionId(null);
    }
  }

  return (
    <div className="alerts-workspace">
      <div className="alerts-toolbar">
        <div>
          <h3>Project alert rules</h3>
          <p className="muted">
            Rules and current evaluation state come from the project control plane. Browser requests do
            not run alert evaluation or query ClickHouse directly.
          </p>
        </div>
        <button className="button secondary" type="button" onClick={() => void refreshRules()}>
          Refresh state
        </button>
      </div>

      {canManage ? (
        <section className="alert-editor" aria-labelledby="alert-editor-heading">
          <div className="alert-editor-header">
            <div>
              <h3 id="alert-editor-heading">{editingId ? "Edit alert rule" : "Create alert rule"}</h3>
              <p className="muted">
                The V1 condition compares one unique latest scalar point with a fixed threshold.
              </p>
            </div>
            {editingId ? (
              <button className="button secondary" type="button" onClick={resetForm}>
                Cancel edit
              </button>
            ) : null}
          </div>

          <form className="alert-form" onSubmit={(event) => void handleSubmit(event)}>
            <label>
              <span>Rule name</span>
              <input
                maxLength={160}
                onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                placeholder="High checkout latency"
                value={form.name}
              />
            </label>
            <label>
              <span>Metric name</span>
              <input
                maxLength={512}
                onChange={(event) =>
                  setForm((current) => ({ ...current, metricName: event.target.value }))
                }
                placeholder="checkout.duration"
                value={form.metricName}
              />
            </label>
            <label>
              <span>Window</span>
              <select
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    timeRange: event.target.value as AlertRuleTimeRange,
                  }))
                }
                value={form.timeRange}
              >
                {Object.entries(TIME_RANGE_LABEL).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>Service (optional)</span>
              <input
                maxLength={512}
                onChange={(event) =>
                  setForm((current) => ({ ...current, serviceName: event.target.value }))
                }
                placeholder="checkout"
                value={form.serviceName}
              />
            </label>
            <label>
              <span>Environment (optional)</span>
              <input
                maxLength={512}
                onChange={(event) =>
                  setForm((current) => ({ ...current, environment: event.target.value }))
                }
                placeholder="production"
                value={form.environment}
              />
            </label>
            <label>
              <span>Comparator</span>
              <select
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    comparator: event.target.value as AlertRuleComparator,
                  }))
                }
                value={form.comparator}
              >
                <option value="gt">Greater than (&gt;)</option>
                <option value="gte">Greater than or equal (≥)</option>
                <option value="lt">Less than (&lt;)</option>
                <option value="lte">Less than or equal (≤)</option>
              </select>
            </label>
            <label>
              <span>Threshold</span>
              <input
                inputMode="decimal"
                onChange={(event) =>
                  setForm((current) => ({ ...current, threshold: event.target.value }))
                }
                placeholder="100"
                type="number"
                value={form.threshold}
              />
            </label>
            <label className="alert-enabled">
              <span>Enabled</span>
              <input
                checked={form.enabled}
                onChange={(event) =>
                  setForm((current) => ({ ...current, enabled: event.target.checked }))
                }
                type="checkbox"
              />
            </label>
            <div className="alert-form-actions">
              <button className="button" disabled={saving} type="submit">
                {saving ? "Saving…" : editingId ? "Save changes" : "Create rule"}
              </button>
            </div>
          </form>
          {formError ? (
            <p className="error" role="alert">
              {formError}
            </p>
          ) : null}
        </section>
      ) : (
        <p className="notice alert-read-only">
          Viewer access is read only. Owners, admins, and editors can create or change alert rules.
        </p>
      )}

      {actionError ? (
        <p className="error" role="alert">
          {actionError}
        </p>
      ) : null}
      {rules.isPending ? <p className="muted alert-state-line">Loading alert rules…</p> : null}
      {rules.isError ? (
        <p className="error" role="alert">
          {rules.error instanceof Error ? rules.error.message : "Unable to load alert rules."}
        </p>
      ) : null}

      {rules.data?.length === 0 ? (
        <div className="empty-feature alert-state-line">
          <strong>No alert rules configured.</strong>
          <p className="muted">
            {canManage
              ? "Create a scalar metric threshold rule above. Evaluation runs independently of this page."
              : "A project editor can configure scalar metric threshold rules."}
          </p>
        </div>
      ) : null}

      {rules.data?.length ? (
        <div className="alert-rule-list">
          {rules.data.map((rule) => {
            const status = rule.state?.status ?? "unavailable";
            return (
              <article className="alert-rule-card" key={rule.id}>
                <header className="alert-rule-header">
                  <div>
                    <div className="alert-rule-title">
                      <h3>{rule.name}</h3>
                      <span className={`alert-status ${status}`}>{status.replace("_", " ")}</span>
                    </div>
                    <p className="mono muted">{rule.metric_name}</p>
                  </div>
                  {canManage ? (
                    <div className="alert-rule-actions">
                      <button
                        className="button secondary"
                        disabled={actionId === rule.id}
                        onClick={() => {
                          setEditingId(rule.id);
                          setForm(formFromRule(rule));
                          setFormError(null);
                        }}
                        type="button"
                      >
                        Edit
                      </button>
                      <button
                        className="button secondary"
                        disabled={actionId === rule.id}
                        onClick={() => void toggleRule(rule)}
                        type="button"
                      >
                        {rule.enabled ? "Disable" : "Enable"}
                      </button>
                      <button
                        className="button danger"
                        disabled={actionId === rule.id}
                        onClick={() => void removeRule(rule)}
                        type="button"
                      >
                        Delete
                      </button>
                    </div>
                  ) : null}
                </header>

                <div className="alert-condition">
                  <strong className="mono">{rule.metric_name}</strong>
                  <span>{COMPARATOR_LABEL[rule.comparator]}</span>
                  <strong>{rule.threshold}</strong>
                </div>

                <div className="alert-rule-query">
                  <span className="metric-pill">{TIME_RANGE_LABEL[rule.time_range]}</span>
                  {rule.service_name ? (
                    <span className="metric-pill">service={rule.service_name}</span>
                  ) : null}
                  {rule.environment ? (
                    <span className="metric-pill">environment={rule.environment}</span>
                  ) : null}
                  <span className="metric-pill">{rule.enabled ? "enabled" : "disabled"}</span>
                </div>

                {rule.state ? (
                  <dl className="alert-state-meta">
                    <div>
                      <dt>Evaluated</dt>
                      <dd>{formatTimestamp(rule.state.evaluated_at)}</dd>
                    </div>
                    <div>
                      <dt>State changed</dt>
                      <dd>{formatTimestamp(rule.state.state_changed_at)}</dd>
                    </div>
                    <div>
                      <dt>Source point</dt>
                      <dd>{formatTimestamp(rule.state.source_timestamp)}</dd>
                    </div>
                    <div>
                      <dt>Error code</dt>
                      <dd>{rule.state.error_code || "None"}</dd>
                    </div>
                  </dl>
                ) : (
                  <p className="notice alert-state-line">
                    Current evaluation state is unavailable. This page does not fabricate a replacement.
                  </p>
                )}
              </article>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
