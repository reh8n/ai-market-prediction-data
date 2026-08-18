import React from "react";
import { SketchPanel } from "./SketchPanel.jsx";
import { IconButton } from "../core/IconButton.jsx";

export function Dialog({ open = true, title, overline, children, footer, onClose, width = 520 }) {
  if (!open) return null;
  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 60,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "var(--space-6)",
        background: "var(--overlay-scrim)",
        backdropFilter: "var(--blur-scrim)",
      }}
      onClick={onClose}
    >
      <div onClick={(e) => e.stopPropagation()} style={{ width, maxWidth: "100%" }}>
        <SketchPanel
          lifted
          overline={overline}
          title={title}
          actions={onClose ? <IconButton label="Close" onClick={onClose}>✕</IconButton> : null}
        >
          <div style={{ fontFamily: "var(--font-mono)", fontSize: "var(--size-body)", lineHeight: "var(--lh-body)", color: "var(--text-body)" }}>{children}</div>
          {footer ? (
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "var(--space-2)", marginTop: "var(--space-6)", paddingTop: "var(--space-4)", borderTop: "1px solid var(--border-hairline)" }}>
              {footer}
            </div>
          ) : null}
        </SketchPanel>
      </div>
    </div>
  );
}
