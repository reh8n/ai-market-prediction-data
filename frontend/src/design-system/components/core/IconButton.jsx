import React from "react";

const sizes = { sm: 28, md: 34, lg: 40 };

export function IconButton({ children, label, size = "md", variant = "ghost", disabled = false, onClick, style, ...rest }) {
  const [hover, setHover] = React.useState(false);
  const [down, setDown] = React.useState(false);
  const px = sizes[size];
  const skin =
    variant === "solid"
      ? { background: "var(--ink-800)", color: "var(--text-inverse)", borderColor: "var(--ink-800)" }
      : variant === "outline"
      ? { background: "var(--paper-000)", color: "var(--text-body)", borderColor: "var(--border-default)" }
      : { background: hover ? "var(--surface-sunken)" : "transparent", color: "var(--text-muted)", borderColor: "transparent" };
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => { setHover(false); setDown(false); }}
      onMouseDown={() => setDown(true)}
      onMouseUp={() => setDown(false)}
      style={{
        width: px,
        height: px,
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        border: "1px solid",
        borderRadius: "var(--radius-sm)",
        fontFamily: "var(--font-mono)",
        fontSize: "var(--size-small)",
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.45 : 1,
        transition: "var(--transition-control), transform var(--dur-fast) var(--ease-standard)",
        transform: disabled ? "none" : down ? "scale(var(--press-scale))" : hover ? "translateY(-1px)" : "translateY(0)",
        ...skin,
        ...style,
      }}
      {...rest}
    >
      {children}
    </button>
  );
}
