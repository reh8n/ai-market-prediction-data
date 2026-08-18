import React from "react";

export function Tabs({ tabs = [], value, defaultValue, onChange, style }) {
  const first = tabs.length ? (typeof tabs[0] === "string" ? tabs[0] : tabs[0].value) : null;
  const [inner, setInner] = React.useState(defaultValue ?? first);
  const active = value === undefined ? inner : value;
  return (
    <div style={{ display: "flex", gap: "var(--space-5)", borderBottom: "1px solid var(--border-hairline)", ...style }}>
      {tabs.map((t) => {
        const tab = typeof t === "string" ? { value: t, label: t } : t;
        const on = tab.value === active;
        return (
          <button
            key={tab.value}
            type="button"
            onClick={() => { if (value === undefined) setInner(tab.value); onChange && onChange(tab.value); }}
            style={{
              appearance: "none",
              background: "none",
              border: "none",
              borderBottom: "2px solid " + (on ? "var(--ink-800)" : "transparent"),
              padding: "0 0 9px",
              marginBottom: -1,
              font: "var(--text-label)",
              letterSpacing: "var(--track-label)",
              textTransform: "uppercase",
              color: on ? "var(--text-strong)" : "var(--text-muted)",
              cursor: "pointer",
              transition: "var(--transition-control)",
              display: "inline-flex",
              alignItems: "center",
              gap: "var(--space-2)",
            }}
          >
            {tab.label}
            {tab.count !== undefined ? (
              <span style={{ fontSize: "var(--size-micro)", color: "var(--text-faint)" }}>[{tab.count}]</span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
