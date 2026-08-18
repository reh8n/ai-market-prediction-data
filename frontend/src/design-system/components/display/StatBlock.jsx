import React from "react";

/** Big-number metric with uppercase overline, optional meter bar and caption. */
export function StatBlock({ label, value, caption, meter, tone = "ink", size = "md", style }) {
  const color = tone === "accent" ? "var(--blue-600)" : tone === "muted" ? "var(--text-muted)" : "var(--text-strong)";
  const fs = size === "lg" ? "var(--size-metric-lg)" : size === "sm" ? "var(--size-h1)" : "var(--size-metric)";
  return (
    <div style={{ minWidth: 0, ...style }}>
      <div
        style={{
          font: "var(--text-label)",
          letterSpacing: "var(--track-label)",
          textTransform: "uppercase",
          color: "var(--text-muted)",
          marginBottom: "var(--space-2)",
        }}
      >
        {label}
      </div>
      <div style={{ fontFamily: "var(--font-mono)", fontWeight: "var(--weight-bold)", fontSize: fs, lineHeight: 1, color, letterSpacing: "var(--track-tight)" }}>
        {value}
      </div>
      {meter !== undefined && meter !== null ? (
        <div style={{ height: 4, marginTop: "var(--space-3)", background: "var(--surface-fill)", borderRadius: "var(--radius-pill)", overflow: "hidden" }}>
          <div style={{ width: Math.max(0, Math.min(100, meter)) + "%", height: "100%", background: "var(--ink-700)" }} />
        </div>
      ) : null}
      {caption ? (
        <div style={{ marginTop: "var(--space-2)", fontFamily: "var(--font-mono)", fontSize: "var(--size-small)", color: "var(--text-muted)", lineHeight: "var(--lh-snug)" }}>
          {caption}
        </div>
      ) : null}
    </div>
  );
}
