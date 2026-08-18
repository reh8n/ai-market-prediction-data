import React from "react";

const tones = {
  info: { bd: "var(--border-default)", accent: "var(--ink-700)" },
  success: { bd: "var(--green-100)", accent: "var(--green-500)" },
  warn: { bd: "var(--amber-100)", accent: "var(--amber-500)" },
  alert: { bd: "var(--red-100)", accent: "var(--red-500)" },
};

/** Transient pipeline notice. Rendered inline; position it yourself (fixed bottom-right in app shells). */
export function Toast({ title, children, tone = "info", onDismiss, style }) {
  const t = tones[tone] || tones.info;
  return (
    <div
      role="status"
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: "var(--space-3)",
        minWidth: 260,
        maxWidth: 380,
        padding: "var(--space-3) var(--space-4)",
        background: "var(--paper-000)",
        border: "1px solid " + t.bd,
        borderLeft: "var(--rail-w) solid " + t.accent,
        borderRadius: "var(--radius-sketch-sm)",
        boxShadow: "var(--shadow-panel-lift)",
        ...style,
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ font: "var(--text-label)", fontSize: "var(--size-micro)", letterSpacing: "var(--track-micro)", textTransform: "uppercase", color: t.accent }}>{title}</div>
        {children ? (
          <div style={{ marginTop: "var(--space-1)", fontFamily: "var(--font-mono)", fontSize: "var(--size-small)", lineHeight: "var(--lh-snug)", color: "var(--text-body)" }}>{children}</div>
        ) : null}
      </div>
      {onDismiss ? (
        <span role="button" aria-label="Dismiss" onClick={onDismiss} style={{ cursor: "pointer", color: "var(--text-faint)", fontSize: "var(--size-small)" }}>✕</span>
      ) : null}
    </div>
  );
}
