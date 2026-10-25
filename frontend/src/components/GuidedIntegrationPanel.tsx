import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { getServiceCatalog } from "../api/resources";
import {
  DEFAULT_SERVICE, integrationRecipe, otlpOrigin, serviceEvidence, validResourceValue,
  type ExporterNetwork, type IntegrationFramework,
} from "../guidedIntegration";

interface VerificationRequest {
  projectId: string;
  serviceName: string;
  environment: string;
  start: string;
  end: string;
  serial: number;
}

function CopyableStep({ title, content }: { title: string; content: string }) {
  const [status, setStatus] = useState("Copy");
  async function copy() {
    try {
      await navigator.clipboard.writeText(content);
      setStatus("Copied");
    } catch {
      setStatus("Copy unavailable");
    }
  }
  return (
    <div className="docs-snippet">
      <div className="docs-snippet-toolbar">
        <strong>{title}</strong>
        <button className="button secondary" type="button" onClick={() => void copy()}>{status}</button>
      </div>
      <pre><code>{content}</code></pre>
    </div>
  );
}

/** Project-session-only onboarding; never reads or transmits an ingestion secret. */
export function GuidedIntegrationPanel({ projectId }: { projectId: string }) {
  const sequence = useRef(0);
  const [framework, setFramework] = useState<IntegrationFramework>("node");
  const [network, setNetwork] = useState<ExporterNetwork>("host");
  const [remoteOrigin, setRemoteOrigin] = useState("");
  const [serviceName, setServiceName] = useState(DEFAULT_SERVICE.node);
  const [environment, setEnvironment] = useState("development");
  const [requested, setRequested] = useState<VerificationRequest | null>(null);
  const active = requested?.projectId === projectId ? requested : null;
  const origin = otlpOrigin(network, remoteOrigin);
  const validIdentity = validResourceValue(serviceName) && validResourceValue(environment);
  const recipe = origin && validIdentity
    ? integrationRecipe(framework, origin, serviceName, environment)
    : null;

  const observations = useQuery({
    queryKey: ["guided-integration-service", projectId, active?.serial],
    queryFn: () => getServiceCatalog(projectId, {
      start: active!.start, end: active!.end, limit: 500,
    }),
    enabled: active !== null,
    retry: false,
  });

  function selectFramework(value: IntegrationFramework) {
    setFramework(value);
    setServiceName(DEFAULT_SERVICE[value]);
    setRequested(null);
  }

  function verify() {
    if (!recipe) return;
    const now = Date.now();
    sequence.current += 1;
    setRequested({
      projectId, serviceName, environment,
      start: new Date(now - 24 * 60 * 60 * 1000).toISOString(),
      end: new Date(now).toISOString(),
      serial: sequence.current,
    });
  }

  const evidence = active && observations.isSuccess
    ? serviceEvidence(observations.data, projectId, active.serviceName, active.environment)
    : null;

  return (
    <section className="api-key-panel" aria-label="Guided application integration">
      <div className="api-key-header">
        <div>
          <h3>Connect an application</h3>
          <p className="muted">Guided server-side OpenTelemetry setup. The browser never asks for or copies your key.</p>
        </div>
      </div>
      <div className="grid gap-3">
        <div>
          <label htmlFor="guided-framework">Server framework</label>
          <select id="guided-framework" value={framework} onChange={(event) => selectFramework(event.target.value as IntegrationFramework)}>
            <option value="node">Node.js / Express</option>
            <option value="django">Django / Python</option>
          </select>
        </div>
        <div>
          <label htmlFor="guided-network">Exporter location</label>
          <select id="guided-network" value={network} onChange={(event) => { setNetwork(event.target.value as ExporterNetwork); setRequested(null); }}>
            <option value="host">Windows host (localhost:8000)</option>
            <option value="compose">Sentrix Compose network (api:8000)</option>
            <option value="remote">Remote application (HTTPS)</option>
          </select>
          {network === "remote" ? (
            <>
              <label htmlFor="guided-remote">Reachable Sentrix HTTPS origin</label>
              <input id="guided-remote" type="url" value={remoteOrigin} placeholder="https://telemetry.example.com" onChange={(event) => { setRemoteOrigin(event.target.value); setRequested(null); }} />
              {!origin ? <p className="error" role="alert">Enter an HTTPS origin without a path, query, fragment or credentials.</p> : null}
            </>
          ) : null}
          <p className="muted">Choose the network from which your server process exports. A separate container cannot reach Sentrix through its own localhost.</p>
        </div>
        <div>
          <label htmlFor="guided-service">Exact service.name</label>
          <input id="guided-service" value={serviceName} maxLength={128} onChange={(event) => { setServiceName(event.target.value); setRequested(null); }} />
          <label htmlFor="guided-environment">Exact deployment.environment.name</label>
          <input id="guided-environment" value={environment} maxLength={128} onChange={(event) => { setEnvironment(event.target.value); setRequested(null); }} />
          {!validIdentity ? <p className="error" role="alert">Use 1–128 characters: letters, numbers, dot, underscore, slash or hyphen; start with a letter or number.</p> : null}
        </div>
        {recipe ? (
          <>
            <p className="muted">Create a temporary project key in Settings using a write role, then set it <strong>only in your application's server environment</strong>. The following are templates, not proof of an installed SDK.</p>
            <CopyableStep key={`${framework}-install`} title="1. Install exporter" content={recipe.install} />
            <CopyableStep key={`${framework}-${network}-${origin}-${serviceName}-${environment}-config`} title="2. Configure on the server" content={recipe.configure} />
            <CopyableStep key={`${framework}-launch`} title="3. Start and send a real request" content={recipe.launch} />
            <p className="muted">These examples emit <strong>traces only</strong>. Metrics and logs need separate exporters. OTLP/HTTP binary protobuf is supported; gRPC and OTLP JSON are not. Only use reachable, protected HTTPS for external deployments.</p>
          </>
        ) : null}
        <div>
          <h4>4. Check this exact service</h4>
          <p className="muted">After a server request, search this project's stored Services catalog for the exact service and environment within 24 hours. This does not probe the exporter or validate its credential.</p>
          <button className="button secondary" type="button" disabled={!recipe || observations.isFetching} onClick={verify}>
            {observations.isFetching ? "Checking…" : "Check service"}
          </button>
          {active && observations.isPending ? <p role="status">Checking stored service observations…</p> : null}
          {active && observations.isError ? (
            <p className="error" role="alert">Service catalog unavailable. Check API/ClickHouse and try again; no connection result can be inferred.</p>
          ) : null}
          {active && evidence ? (
            <div aria-live="polite" role="status">
              <p>Checked service <strong>{active.serviceName}</strong> in environment <strong>{active.environment}</strong>.</p>
              {evidence.state === "observed" ? (
                <p>Stored observations found: {evidence.service.metric_points} metric points, {evidence.service.log_records} logs, {evidence.service.span_records} spans. This is historical telemetry, not live connection health.</p>
              ) : evidence.state === "inconclusive" ? (
                <p>Inconclusive: the catalog was truncated or returned an unexpected project. Narrow the service set or inspect Services directly.</p>
              ) : (
                <p>No matching service observed in this 24-hour window. Check exporter origin, server activity, key scope, flush and resource attributes; this does not prove the exporter is disconnected.</p>
              )}
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
