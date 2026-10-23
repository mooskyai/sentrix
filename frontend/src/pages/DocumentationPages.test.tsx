import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiReferencePage, TelemetrySetupPage } from "./DocumentationPages";

describe("Documentation links and guides", () => {
  afterEach(() => cleanup());

  it("offers beginner-friendly framework choices without exposing browser keys", () => {
    render(<MemoryRouter><TelemetrySetupPage /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: "Documentation" })).toBeInTheDocument();
    expect(screen.getByText(/Copy the raw secret immediately/i)).toBeInTheDocument();
    expect(screen.getByText(/application\/x-protobuf/i)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /API reference/i })).not.toBeInTheDocument();
    const react = screen.getByRole("button", { name: /React \(Vite\)/i });
    fireEvent.click(react);
    const panel = screen.getByRole("region", { name: /React \(Vite\) setup instructions/i });
    expect(within(panel).getByText(/Never put a Sentrix project API key in VITE_/)).toBeInTheDocument();
    expect(within(panel).getByText(/backend your React app already calls/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Laravel \(PHP\)/i }));
    expect(screen.getByRole("region", { name: /Laravel \(PHP\) setup instructions/i })).toHaveTextContent("open-telemetry/opentelemetry-auto-laravel");
    fireEvent.click(screen.getByRole("button", { name: /Next\.js/i }));
    expect(screen.getByRole("region", { name: /Next\.js setup instructions/i })).toHaveTextContent("NEXT_RUNTIME");
    fireEvent.click(screen.getByRole("button", { name: /^Node\.js/i }));
    expect(screen.getByRole("region", { name: /Node\.js setup instructions/i })).toHaveTextContent("instrumentation.cjs");
    expect(screen.queryByText(/Paste your real secret here/)).not.toBeInTheDocument();
  });

  it("copies the selected framework recipe without a raw credential", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
    render(<MemoryRouter><TelemetrySetupPage /></MemoryRouter>);
    fireEvent.click(screen.getAllByRole("button", { name: "Copy" })[0]);
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(expect.stringContaining("@opentelemetry/sdk-node")));
    expect(screen.getByRole("button", { name: "Copied" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Laravel \(PHP\)/i }));
    expect(screen.queryByRole("button", { name: "Copied" })).not.toBeInTheDocument();
  });

  it("separates session management from machine ingestion and documents request limits", () => {
    render(<MemoryRouter><ApiReferencePage /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: "Sentrix API reference" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "API documentation" })).toHaveTextContent(/A project telemetry key does/);
    expect(screen.getByText(/seven days/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /project API-key setup guide/i })).toHaveAttribute("href", "/docs/telemetry-setup");
  });
});
