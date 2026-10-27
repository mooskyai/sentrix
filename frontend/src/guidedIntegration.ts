import type { ObservedService, ServiceCatalogResponse } from "./types";

export type IntegrationFramework = "django" | "node";
export type ExporterNetwork = "host" | "compose" | "remote";

export const DEFAULT_SERVICE: Record<IntegrationFramework, string> = {
  django: "django-api",
  node: "node-api",
};

/** Do not interpolate untrusted input into copied shell and JavaScript snippets. */
export function validResourceValue(value: string): boolean {
  return /^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$/.test(value);
}

export function otlpOrigin(network: ExporterNetwork, remoteOrigin: string): string | null {
  if (network === "host") return "http://localhost:8000";
  if (network === "compose") return "http://api:8000";
  try {
    const candidate = new URL(remoteOrigin.trim());
    if (
      candidate.protocol !== "https:" || !candidate.hostname || candidate.username ||
      candidate.password || candidate.pathname !== "/" || candidate.search || candidate.hash
    ) return null;
    return candidate.origin;
  } catch {
    return null;
  }
}

export interface IntegrationRecipe {
  install: string;
  configure: string;
  launch: string;
}

/** Read-only, literal templates. Never accept or include a raw project key. */
export function integrationRecipe(
  framework: IntegrationFramework,
  origin: string,
  serviceName: string,
  environment: string,
): IntegrationRecipe {
  if (!validResourceValue(serviceName) || !validResourceValue(environment)) {
    throw new Error("Service and environment must contain safe resource characters.");
  }
  if (origin !== "http://localhost:8000" && origin !== "http://api:8000" && otlpOrigin("remote", origin) !== origin) {
    throw new Error("An exporter origin is required.");
  }
  const configure = [
    "# Set SENTRIX_API_KEY in the application's PRIVATE server process; do not copy a real key into ChatGPT, Git or a browser.",
    '$env:SENTRIX_API_KEY = "<SET_IN_SERVER_TERMINAL_ONLY>"',
    `$env:SENTRIX_OTLP_BASE_URL = "${origin}"`,
    `$env:OTEL_SERVICE_NAME = "${serviceName}"`,
    `$env:OTEL_RESOURCE_ATTRIBUTES = "deployment.environment.name=${environment}"`,
  ].join("\n");
  if (framework === "django") {
    return {
      install: "pip install opentelemetry-distro opentelemetry-exporter-otlp-proto-http opentelemetry-instrumentation-django\nopentelemetry-bootstrap -a install",
      configure: [
        configure,
        '$env:OTEL_EXPORTER_OTLP_ENDPOINT = $env:SENTRIX_OTLP_BASE_URL',
        '$env:OTEL_EXPORTER_OTLP_PROTOCOL = "http/protobuf"',
        '$env:OTEL_EXPORTER_OTLP_HEADERS = "Authorization=Bearer%20$env:SENTRIX_API_KEY"',
        '$env:OTEL_TRACES_EXPORTER = "otlp"',
        '$env:OTEL_METRICS_EXPORTER = "none"',
        '$env:OTEL_LOGS_EXPORTER = "none"',
      ].join("\n"),
      launch: "# In the Django application directory; --noreload avoids dev autoreloader duplication.\nopentelemetry-instrument python manage.py runserver --noreload\n# Send a real HTTP request to a Django route, then check the exact service below.",
    };
  }
  return {
    install: "npm install @opentelemetry/sdk-node @opentelemetry/auto-instrumentations-node @opentelemetry/exporter-trace-otlp-proto",
    configure: [
      configure,
      "# Save the following as instrumentation.cjs in the SERVER project:",
      'const { NodeSDK } = require("@opentelemetry/sdk-node");',
      'const { OTLPTraceExporter } = require("@opentelemetry/exporter-trace-otlp-proto");',
      'const { getNodeAutoInstrumentations } = require("@opentelemetry/auto-instrumentations-node");',
      "const sdk = new NodeSDK({",
      '  serviceName: process.env.OTEL_SERVICE_NAME || "node-api",',
      "  traceExporter: new OTLPTraceExporter({",
      '    url: `${process.env.SENTRIX_OTLP_BASE_URL}/v1/traces`,',
      '    headers: { Authorization: `Bearer ${process.env.SENTRIX_API_KEY}` },',
      "  }),",
      "  instrumentations: [getNodeAutoInstrumentations()],",
      "});",
      "sdk.start();",
    ].join("\n"),
    launch: "# Import instrumentation before server.js loads the framework.\nnode --require ./instrumentation.cjs server.js\n# Replace server.js with your server entry point and generate a real HTTP request.",
  };
}

export type ServiceEvidence =
  | { state: "observed"; service: ObservedService }
  | { state: "not_observed" }
  | { state: "inconclusive" };

export function serviceEvidence(
  result: ServiceCatalogResponse,
  expectedProjectId: string,
  serviceName: string,
  environment: string,
): ServiceEvidence {
  if (result.project_id !== expectedProjectId) return { state: "inconclusive" };
  const found = result.services.find(
    (item) => item.service_name === serviceName && item.environment === environment,
  );
  if (found) return { state: "observed", service: found };
  return { state: result.truncated ? "inconclusive" : "not_observed" };
}
