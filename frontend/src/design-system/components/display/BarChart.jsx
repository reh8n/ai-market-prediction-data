import React from "react";

/** Outlined bar chart: pale fill, 1px ink stroke, rotated x labels — matches the reference schematic. */
export function BarChart({ data = [], max, height = 300, ticks = 5, yUnit = "", labelHeight = 84, style }) {
  const top = max ?? Math.ceil(Math.max(1, ...data.map((d) => d.value)) / 20) * 20;
  const rows = Array.from({ length: ticks + 1 }, (_, i) => Math.round((top / ticks) * (ticks - i)));
  return (
    <div style={{ fontFamily: "var(--font-mono)", ...style }}>
      <div style={{ display: "flex", gap: "var(--space-2)" }}>
        <div style={{ width: 34, height, position: "relative", flex: "0 0 auto" }}>
          {rows.map((r, i) => (
            <span
              key={r + "-" + i}
              style={{
                position: "absolute",
                right: 0,
                top: (i / ticks) * 100 + "%",
                transform: "translateY(-50%)",
                fontSize: "var(--size-micro)",
                color: "var(--chart-label)",
              }}
            >
              {r}
              {yUnit}
            </span>
          ))}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ position: "relative", height, borderLeft: "1px solid var(--chart-stroke)", borderBottom: "1px solid var(--chart-stroke)" }}>
            {rows.slice(0, -1).map((r, i) => (
              <span key={"g" + i} style={{ position: "absolute", left: 0, right: 0, top: (i / ticks) * 100 + "%", borderTop: "1px solid var(--chart-axis)" }} />
            ))}
            <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "flex-end", justifyContent: "space-around", padding: "0 10px" }}>
              {data.map((d) => (
                <div
                  key={d.label}
                  title={d.label + ": " + d.value}
                  style={{
                    width: "62%",
                    maxWidth: 46,
                    height: Math.max(1, (d.value / top) * 100) + "%",
                    background: d.tone === "accent" ? "var(--blue-100)" : "var(--chart-fill)",
                    borderTop: "1px solid var(--chart-stroke)",
                    borderLeft: "1px solid var(--chart-stroke)",
                    borderRight: "1px solid var(--chart-stroke)",
                  }}
                />
              ))}
            </div>
          </div>
          <div style={{ display: "flex", justifyContent: "space-around", padding: "0 10px", height: labelHeight }}>
            {data.map((d) => (
              <span key={d.label + "-l"} style={{ width: "62%", maxWidth: 46, position: "relative" }}>
                <span
                  title={d.label}
                  style={{
                    position: "absolute",
                    right: "50%",
                    top: 10,
                    fontSize: "var(--size-micro)",
                    lineHeight: 1,
                    color: "var(--chart-label)",
                    whiteSpace: "nowrap",
                    textAlign: "right",
                    transform: "rotate(-40deg)",
                    transformOrigin: "right top",
                  }}
                >
                  {d.label}
                </span>
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
