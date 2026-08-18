import React from "react";

const tones = {
  neutral: { bg: "var(--surface-fill)", fg: "var(--text-muted)", bd: "var(--border-hairline)" },
  ink: { bg: "var(--ink-800)", fg: "var(--text-inverse)", bd: "var(--ink-800)" },
  accent: { bg: "var(--blue-100)", fg: "var(--blue-600)", bd: "var(--blue-200)" },
  success: { bg: "var(--green-100)", fg: "var(--green-500)", bd: "var(--green-100)" },
  warn: { bg: "var(--amber-100)", fg: "var(--amber-500)", bd: "var(--amber-100)" },
  alert: { bg: "var(--red-100)", fg: "var(--red-500)", bd: "var(--red-100)" },
};

export function Badge({ children, tone = "neutral", style }) {
  const t = tones[tone] || tones.neutral;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "var(--space-1)",
        height: 20,
        padding: "0 7px",
        background: t.bg,
        color: t.fg,
        border: "1px solid " + t.bd,
        borderRadius: "var(--radius-xs)",
        font: "var(--text-label)",
        fontSize: "var(--size-micro)",
        letterSpacing: "var(--track-micro)",
        textTransform: "uppercase",
        ...style,
      }}
    >
      {children}
    </span>
  );
}
