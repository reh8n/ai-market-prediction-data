import React from "react";

/** The hand-drawn panel: uneven radius, hairline border, a faint offset second stroke, soft paper lift. */
export function SketchPanel({ children, title, overline, actions, padding, tilt = true, lifted = false, rail = null, style, ...rest }) {
  const railColor = rail === "user" ? "var(--rail-user)" : rail === "accent" ? "var(--rail-accent)" : null;
  return (
    <div
      style={{
        position: "relative",
        background: "var(--surface-panel)",
        border: "1px solid var(--border-hairline)",
        borderRadius: "var(--radius-sketch)",
        boxShadow: lifted ? "var(--shadow-panel-lift)" : "var(--shadow-panel)",
        transform: tilt ? "rotate(var(--rotate-sketch))" : "none",
        borderLeft: railColor ? "var(--rail-w) solid " + railColor : undefined,
        padding: padding || "var(--panel-pad)",
        ...style,
      }}
      {...rest}
    >
      <span
        aria-hidden="true"
        style={{
          position: "absolute",
          inset: 2,
          border: "1px solid var(--ink-050)",
          borderRadius: "var(--radius-sketch-sm)",
          transform: "rotate(0.35deg)",
          pointerEvents: "none",
          opacity: 0.9,
        }}
      />
      {(overline || title || actions) && (
        <div style={{ position: "relative", marginBottom: "var(--space-4)" }}>
          {overline ? <PanelLabel>{overline}</PanelLabel> : null}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "var(--space-4)", marginTop: overline ? "var(--space-1)" : 0 }}>
            {title ? (
              <h2 style={{ margin: 0, font: "var(--text-heading)", color: "var(--text-strong)", letterSpacing: "var(--track-tight)" }}>{title}</h2>
            ) : <span />}
            {actions ? <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>{actions}</div> : null}
          </div>
        </div>
      )}
      <div style={{ position: "relative" }}>{children}</div>
    </div>
  );
}

/** Uppercase letterspaced overline. Segments are joined with " // " by convention. */
export function PanelLabel({ children, tone = "muted", style }) {
  const color = tone === "accent" ? "var(--text-accent)" : tone === "strong" ? "var(--text-body)" : "var(--text-muted)";
  return (
    <div
      style={{
        font: "var(--text-label)",
        letterSpacing: "var(--track-label)",
        textTransform: "uppercase",
        color,
        ...style,
      }}
    >
      {children}
    </div>
  );
}
