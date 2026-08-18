import React from "react";

export function FieldLabel({ children, htmlFor, hint }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: "var(--label-gap)" }}>
      <label
        htmlFor={htmlFor}
        style={{
          font: "var(--text-label)",
          letterSpacing: "var(--track-label)",
          textTransform: "uppercase",
          color: "var(--text-muted)",
        }}
      >
        {children}
      </label>
      {hint ? <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--size-micro)", color: "var(--text-faint)" }}>{hint}</span> : null}
    </div>
  );
}

export function Input({
  value,
  defaultValue,
  onChange,
  placeholder,
  label,
  hint,
  error,
  disabled = false,
  type = "text",
  size = "md",
  prefix = null,
  suffix = null,
  id,
  style,
  ...rest
}) {
  const [focus, setFocus] = React.useState(false);
  const h = size === "sm" ? "var(--control-h-sm)" : size === "lg" ? "var(--control-h-lg)" : "var(--control-h)";
  return (
    <div style={{ width: "100%", ...style }}>
      {label ? <FieldLabel htmlFor={id} hint={hint}>{label}</FieldLabel> : null}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--space-2)",
          height: h,
          padding: "0 var(--control-pad-x)",
          background: disabled ? "var(--surface-sunken)" : "var(--paper-000)",
          border: "1px solid",
          borderColor: error ? "var(--red-500)" : focus ? "var(--border-focus)" : "var(--border-default)",
          borderRadius: "var(--radius-sm)",
          boxShadow: focus ? "var(--focus-ring)" : "none",
          transition: "var(--transition-control)",
        }}
      >
        {prefix ? <span style={{ color: "var(--text-faint)", display: "inline-flex" }}>{prefix}</span> : null}
        <input
          id={id}
          type={type}
          value={value}
          defaultValue={defaultValue}
          onChange={onChange}
          placeholder={placeholder}
          disabled={disabled}
          onFocus={() => setFocus(true)}
          onBlur={() => setFocus(false)}
          style={{
            flex: 1,
            minWidth: 0,
            border: "none",
            outline: "none",
            background: "transparent",
            fontFamily: "var(--font-mono)",
            fontSize: "var(--size-body)",
            color: "var(--text-body)",
          }}
          {...rest}
        />
        {suffix ? <span style={{ color: "var(--text-faint)", display: "inline-flex" }}>{suffix}</span> : null}
      </div>
      {error ? (
        <div style={{ marginTop: "var(--space-1)", fontFamily: "var(--font-mono)", fontSize: "var(--size-micro)", color: "var(--red-500)" }}>{error}</div>
      ) : null}
    </div>
  );
}
