import React from "react";
import { FieldLabel } from "./Input.jsx";

export function Select({ value, defaultValue, onChange, options = [], label, hint, disabled = false, size = "md", id, style, ...rest }) {
  const [focus, setFocus] = React.useState(false);
  const h = size === "sm" ? "var(--control-h-sm)" : size === "lg" ? "var(--control-h-lg)" : "var(--control-h)";
  return (
    <div style={{ width: "100%", ...style }}>
      {label ? <FieldLabel htmlFor={id} hint={hint}>{label}</FieldLabel> : null}
      <div style={{ position: "relative" }}>
        <select
          id={id}
          value={value}
          defaultValue={defaultValue}
          onChange={onChange}
          disabled={disabled}
          onFocus={() => setFocus(true)}
          onBlur={() => setFocus(false)}
          style={{
            width: "100%",
            height: h,
            padding: "0 34px 0 var(--control-pad-x)",
            appearance: "none",
            background: disabled ? "var(--surface-sunken)" : "var(--paper-000)",
            border: "1px solid",
            borderColor: focus ? "var(--border-focus)" : "var(--border-default)",
            borderRadius: "var(--radius-sm)",
            boxShadow: focus ? "var(--focus-ring)" : "none",
            fontFamily: "var(--font-mono)",
            fontSize: "var(--size-body)",
            color: "var(--text-body)",
            outline: "none",
            cursor: disabled ? "not-allowed" : "pointer",
            transition: "var(--transition-control)",
          }}
          {...rest}
        >
          {options.map((o) => {
            const opt = typeof o === "string" ? { value: o, label: o } : o;
            return (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            );
          })}
        </select>
        <span
          aria-hidden="true"
          style={{
            position: "absolute",
            right: 12,
            top: "50%",
            transform: "translateY(-50%)",
            color: "var(--text-faint)",
            fontFamily: "var(--font-mono)",
            fontSize: "var(--size-small)",
            pointerEvents: "none",
          }}
        >
          ▾
        </span>
      </div>
    </div>
  );
}
