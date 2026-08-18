import React from "react";

const colors = { ok: "var(--status-ok)", warn: "var(--status-warn)", alert: "var(--status-alert)", idle: "var(--ink-300)" };

export function StatusDot({ state = "ok", label, pulse = false, style }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "var(--space-2)",
        font: "var(--text-label)",
        fontSize: "var(--size-micro)",
        letterSpacing: "var(--track-micro)",
        textTransform: "uppercase",
        color: "var(--text-muted)",
        ...style,
      }}
    >
      <span
        style={{
          width: 7,
          height: 7,
          borderRadius: "var(--radius-pill)",
          background: colors[state] || colors.idle,
          boxShadow: pulse ? "0 0 0 3px color-mix(in oklab, " + (colors[state] || colors.idle) + " 22%, transparent)" : "none",
        }}
      />
      {label}
    </span>
  );
}
