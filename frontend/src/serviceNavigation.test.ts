import { describe, expect, it } from "vitest";

import { linkedRange, linkedService, serviceExplorerHref } from "./serviceNavigation";

describe("service explorer context", () => {
  it("preserves exact service and an explicitly empty environment", () => {
    const href = serviceExplorerHref("/orgs/a/projects/b/logs", "worker / queue", "", "7d");
    const params = new URL(href, "http://local.test").searchParams;
    expect(linkedService(params)).toEqual({ service_name: "worker / queue", environment: "" });
    expect(linkedRange(params, "1h")).toBe("7d");
  });

  it("does not derive context from a partial, empty or oversized URL", () => {
    expect(linkedService(new URLSearchParams("service_name=a"))).toBeNull();
    expect(linkedService(new URLSearchParams("service_name=&environment=prod"))).toBeNull();
    expect(linkedService(new URLSearchParams({ service_name: "a".repeat(513), environment: "prod" }))).toBeNull();
    expect(linkedRange(new URLSearchParams("range=year"), "24h")).toBe("24h");
  });

  it("passes only explicit observed trace and metric hints", () => {
    const href = serviceExplorerHref("/traces", "gateway", "acceptance", "1h", {
      trace_id: "a".repeat(32),
      start: "2026-10-24T16:00:00Z",
      end: "2026-10-24T17:00:00Z",
    });
    const params = new URL(href, "http://local.test").searchParams;
    expect(params.get("trace_id")).toBe("a".repeat(32));
    expect(params.get("service_name")).toBe("gateway");
  });
});
