import { describe, expect, it } from "vitest";

import type { ServiceCatalogResponse } from "./types";
import {
  integrationRecipe, otlpOrigin, serviceEvidence, validResourceValue,
} from "./guidedIntegration";

const result: ServiceCatalogResponse = {
  project_id: "project-a", start: "2026-10-25T00:00:00Z", end: "2026-10-26T00:00:00Z",
  limit: 500, truncated: false, services: [{
    service_name: "node-api", environment: "development", first_seen: "2026-10-25T01:00:00Z",
    last_seen: "2026-10-25T02:00:00Z", metric_points: 0, log_records: 0,
    span_records: 3, signals: ["traces"],
  }],
};

describe("guided application integration templates", () => {
  it("only permits secure remote root origins without credentials", () => {
    expect(otlpOrigin("host", "")).toBe("http://localhost:8000");
    expect(otlpOrigin("compose", "")).toBe("http://api:8000");
    expect(otlpOrigin("remote", "https://telemetry.example.com/")).toBe("https://telemetry.example.com");
    for (const candidate of [
      "http://remote.example.com", "https://u:p@remote.example.com",
      "https://remote.example.com/v1/traces", "https://remote.example.com?key=a",
      "https://remote.example.com/#fragment", "not a URL",
    ]) {
      expect(otlpOrigin("remote", candidate)).toBeNull();
    }
  });

  it("rejects values that could inject commands into copied snippets", () => {
    expect(validResourceValue("checkout-api_v2/frontend")).toBe(true);
    expect(validResourceValue("x".repeat(129))).toBe(false);
    expect(validResourceValue("hello; rm -rf /")).toBe(false);
    expect(validResourceValue('a"\n$env:SECRET')).toBe(false);
    expect(() => integrationRecipe("node", "http://localhost:8000", "a;echo bad", "dev")).toThrow();
  });

  it("provides server-only OTLP/HTTP trace export for Django and Node", () => {
    const django = integrationRecipe("django", "http://localhost:8000", "django-api", "development");
    expect(django.install).toContain("opentelemetry-instrumentation-django");
    expect(django.launch).toContain("--noreload");
    expect(django.configure).toContain('OTEL_EXPORTER_OTLP_PROTOCOL = "http/protobuf"');
    expect(django.configure).toContain("Authorization=Bearer%20$env:SENTRIX_API_KEY");
    const node = integrationRecipe("node", "http://api:8000", "node-api", "production");
    expect(node.configure).toContain("OTLPTraceExporter");
    expect(node.launch).toContain("node --require ./instrumentation.cjs server.js");
    expect(node.configure).toContain("http://api:8000");
    for (const text of [django.configure, node.configure]) {
      expect(text).toContain("<SET_IN_SERVER_TERMINAL_ONLY>");
      expect(text).not.toContain("NEXT_PUBLIC_");
      expect(text).not.toContain("VITE_");
    }
  });

  it("only accepts the matching service, environment and project", () => {
    expect(serviceEvidence(result, "project-a", "node-api", "development").state).toBe("observed");
    expect(serviceEvidence(result, "project-b", "node-api", "development").state).toBe("inconclusive");
    expect(serviceEvidence(result, "project-a", "node-api", "production").state).toBe("not_observed");
    expect(serviceEvidence(result, "project-a", "other", "development").state).toBe("not_observed");
  });

  it("never treats an absent row in a truncated catalog as a definitive absence", () => {
    expect(serviceEvidence({ ...result, truncated: true }, "project-a", "other", "development").state).toBe("inconclusive");
  });
});
