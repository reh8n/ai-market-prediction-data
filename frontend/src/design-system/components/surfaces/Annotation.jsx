import React from "react";

/** Handwritten margin note — the brand's one non-mono voice. Used for analyst asides and chart callouts. */
export function Annotation({ children, size = "md", tone = "ink", arrow = null, style }) {
  const fs = size === "sm" ? 16 : size === "lg" ? 24 : "var(--size-hand)";
  const color = tone === "accent" ? "var(--blue-600)" : tone === "muted" ? "var(--text-muted)" : "var(--text-body)";
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "var(--space-2)",
        fontFamily: "var(--font-hand)",
        fontSize: fs,
        lineHeight: 1.25,
        color,
        transform: "rotate(-1.2deg)",
        ...style,
      }}
    >
      {children}
      {arrow ? <span aria-hidden="true" style={{ fontFamily: "var(--font-mono)", fontSize: "var(--size-small)", opacity: 0.7 }}>{arrow}</span> : null}
    </span>
  );
}
