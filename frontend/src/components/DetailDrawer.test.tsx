import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DetailDrawer } from "./DetailDrawer";

describe("DetailDrawer", () => {
  it("opens an accessible modal drawer and restores focus", () => {
    const close = vi.fn();
    const trigger = document.createElement("button");
    document.body.appendChild(trigger);
    trigger.focus();
    const view = render(<DetailDrawer title="Inspect log" onClose={close}><p>Record body</p></DetailDrawer>);
    const dialog = screen.getByRole("dialog", { name: "Inspect log" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveFocus();
    expect(screen.getByText("Record body")).toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(close).toHaveBeenCalledTimes(1);
    view.unmount();
    expect(trigger).toHaveFocus();
    trigger.remove();
  });

  it("closes from the backdrop", () => {
    const close = vi.fn();
    const view = render(<DetailDrawer title="Inspect span" onClose={close}>Span</DetailDrawer>);
    fireEvent.click(screen.getByRole("button", { name: "Close inspection" }));
    expect(close).toHaveBeenCalledTimes(1);
    view.unmount();
  });
});
