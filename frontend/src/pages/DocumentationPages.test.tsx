import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { ApiReferencePage, TelemetrySetupPage } from "./DocumentationPages";

describe("Documentation links and guides", () => {
  afterEach(() => cleanup());

  it("documents one-time project key and real protobuf OTLP export", () => {
    render(<MemoryRouter><TelemetrySetupPage /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: /Connect telemetry using a project API key/ })).toBeInTheDocument();
    expect(screen.getByText(/Copy the raw secret immediately/i)).toBeInTheDocument();
    expect(screen.getByText(/application\/x-protobuf/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /detailed Sentrix API reference/i })).toHaveAttribute("href", "/docs/api-reference");
    expect(screen.queryByText(/Paste your real secret here/)).not.toBeInTheDocument();
  });

  it("separates session management from machine ingestion and documents request limits", () => {
    render(<MemoryRouter><ApiReferencePage /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: "Sentrix API reference" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "API documentation" })).toHaveTextContent(/A project telemetry key does/);
    expect(screen.getByText(/seven days/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /project API-key setup guide/i })).toHaveAttribute("href", "/docs/telemetry-setup");
  });
});
