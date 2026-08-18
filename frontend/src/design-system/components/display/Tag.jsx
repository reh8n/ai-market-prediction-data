import React from "react";

export function Tag({ children, active = false, onClick, onRemove, icon = null, style }) {
  const [hover, setHover] = React.useState(false);
  const interactive = !!onClick;
  return (
    <span
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "var(--space-2)",
        height: 26,
        padding: "0 10px",
        background: active ? "var(--ink-800)" : hover && interactive ? "var(--surface-sunken)" : "var(--paper-000)",
        color: active ? "var(--text-inverse)" : "var(--text-body)",
        border: "1px solid",
        borderColor: active ? "var(--ink-800)" : "var(--border-default)",
        borderRadius: "var(--radius-sketch-sm)",
        fontFamily: "var(--font-mono)",
        fontSize: "var(--size-small)",
        cursor: interactive ? "pointer" : "default",
        transition: "var(--transition-control)",
        ...style,
      }}
    >
      {icon}
      {children}
      {onRemove ? (
        <span
          role="button"
          aria-label="Remove"
          onClick={(e) => { e.stopPropagation(); onRemove(); }}
          style={{ cursor: "pointer", opacity: 0.55, fontSize: "var(--size-micro)" }}
        >
          ✕
        </span>
      ) : null}
    </span>
  );
}
