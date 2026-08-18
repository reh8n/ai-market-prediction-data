import React from "react";

const base = {
  fontFamily: "var(--font-mono)",
  fontWeight: "var(--weight-semibold)",
  letterSpacing: "var(--track-label)",
  textTransform: "uppercase",
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  gap: "var(--space-2)",
  border: "1px solid transparent",
  borderRadius: "var(--radius-sm)",
  cursor: "pointer",
  transition: "var(--transition-control), transform var(--dur-fast) var(--ease-standard)",
  whiteSpace: "nowrap",
};

const sizes = {
  sm: { height: "var(--control-h-sm)", padding: "0 12px", fontSize: "var(--size-micro)" },
  md: { height: "var(--control-h)", padding: "0 var(--control-pad-x)", fontSize: "var(--size-label)" },
  lg: { height: "var(--control-h-lg)", padding: "0 20px", fontSize: "var(--size-small)" },
};

const variants = {
  primary: {
    background: "var(--ink-800)",
    color: "var(--text-inverse)",
    borderColor: "var(--ink-800)",
    boxShadow: "var(--shadow-panel)",
  },
  secondary: {
    background: "var(--paper-000)",
    color: "var(--text-body)",
    borderColor: "var(--border-default)",
  },
  ghost: { background: "transparent", color: "var(--text-muted)", borderColor: "transparent" },
  accent: {
    background: "var(--blue-100)",
    color: "var(--blue-600)",
    borderColor: "var(--blue-200)",
  },
  danger: { background: "var(--paper-000)", color: "var(--red-500)", borderColor: "var(--red-500)" },
};

const hovers = {
  primary: { background: "var(--ink-900)", boxShadow: "var(--shadow-panel-lift)" },
  secondary: { borderColor: "var(--ink-700)", color: "var(--text-strong)" },
  ghost: { color: "var(--text-strong)", background: "var(--surface-sunken)" },
  accent: { background: "var(--blue-200)" },
  danger: { background: "var(--red-100)" },
};

export function Button({
  children,
  variant = "primary",
  size = "md",
  disabled = false,
  fullWidth = false,
  icon = null,
  trailing = null,
  type = "button",
  onClick,
  style,
  ...rest
}) {
  const [hover, setHover] = React.useState(false);
  const [down, setDown] = React.useState(false);
  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => { setHover(false); setDown(false); }}
      onMouseDown={() => setDown(true)}
      onMouseUp={() => setDown(false)}
      style={{
        ...base,
        ...sizes[size],
        ...variants[variant],
        ...(hover && !disabled ? hovers[variant] : null),
        width: fullWidth ? "100%" : undefined,
        transform: disabled ? "none" : down ? "scale(var(--press-scale))" : hover ? "translateY(-1px)" : "translateY(0)",
        opacity: disabled ? 0.45 : 1,
        cursor: disabled ? "not-allowed" : "pointer",
        ...style,
      }}
      {...rest}
    >
      {icon}
      {children}
      {trailing}
    </button>
  );
}
