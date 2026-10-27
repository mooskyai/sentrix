import { describe, expect, it } from "vitest";

import { integrationRecipe } from "./guidedIntegration";

describe("M7.3.2 server-side OTLP wire protocol", () => {
  it("uses the binary protobuf Node trace exporter supported by Sentrix", () => {
    const recipe = integrationRecipe("node", "http://api:8000", "checkout-node", "integration");
    expect(recipe.install).toContain("@opentelemetry/exporter-trace-otlp-proto");
    expect(recipe.configure).toContain('require("@opentelemetry/exporter-trace-otlp-proto")');
    expect(recipe.install).not.toContain("exporter-trace-otlp-http");
    expect(recipe.configure).not.toContain("exporter-trace-otlp-http");
    expect(recipe.configure).toContain("/v1/traces");
    expect(recipe.configure).toContain("<SET_IN_SERVER_TERMINAL_ONLY>");
  });
});
