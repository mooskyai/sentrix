import { useEffect, useId, useRef, type PropsWithChildren } from "react";
import { createPortal } from "react-dom";

interface DetailDrawerProps extends PropsWithChildren {
  title: string;
  onClose: () => void;
}

/** One modal inspection surface for project-scoped telemetry. */
export function DetailDrawer({ title, onClose, children }: DetailDrawerProps) {
  const titleId = useId();
  const panel = useRef<HTMLElement>(null);
  const onCloseRef = useRef(onClose);

  useEffect(() => { onCloseRef.current = onClose; }, [onClose]);

  useEffect(() => {
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    panel.current?.focus();

    function keydown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current();
      }
      if (event.key !== "Tab" || !panel.current) return;
      const controls = Array.from(panel.current.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex="0"]',
      ));
      if (controls.length === 0) {
        event.preventDefault();
        return;
      }
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (event.shiftKey && (document.activeElement === first || document.activeElement === panel.current)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", keydown);
    return () => {
      document.removeEventListener("keydown", keydown);
      document.body.style.overflow = previousOverflow;
      previousFocus?.focus();
    };
  }, []);

  return createPortal(
    <div className="detail-drawer-layer">
      <button type="button" className="detail-drawer-backdrop" aria-label="Close inspection" onClick={onClose} />
      <aside ref={panel} tabIndex={-1} className="detail-drawer" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <div className="detail-drawer-header">
          <h2 id={titleId}>{title}</h2>
          <button className="button secondary" type="button" onClick={onClose} aria-label="Close drawer">Close</button>
        </div>
        <div className="detail-drawer-content">{children}</div>
      </aside>
    </div>,
    document.body,
  );
}
