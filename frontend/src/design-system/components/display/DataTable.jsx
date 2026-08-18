import React from "react";

/** Hairline data table: uppercase column heads, 1px row rules, no zebra striping. */
export function DataTable({ columns = [], rows = [], onRowClick, empty = "No records", style }) {
  const [hover, setHover] = React.useState(-1);
  return (
    <div style={{ width: "100%", overflowX: "auto", ...style }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: "var(--font-mono)", fontSize: "var(--size-small)" }}>
        <thead>
          <tr>
            {columns.map((c) => (
              <th
                key={c.key}
                style={{
                  textAlign: c.align || "left",
                  padding: "0 var(--space-4) var(--space-2) 0",
                  borderBottom: "1px solid var(--border-default)",
                  font: "var(--text-label)",
                  fontSize: "var(--size-micro)",
                  letterSpacing: "var(--track-micro)",
                  textTransform: "uppercase",
                  color: "var(--text-muted)",
                  whiteSpace: "nowrap",
                  width: c.width,
                }}
              >
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} style={{ padding: "var(--space-6) 0", color: "var(--text-faint)", textAlign: "center" }}>
                {empty}
              </td>
            </tr>
          ) : (
            rows.map((r, i) => (
              <tr
                key={r.id ?? i}
                onClick={() => onRowClick && onRowClick(r)}
                onMouseEnter={() => setHover(i)}
                onMouseLeave={() => setHover(-1)}
                style={{
                  background: hover === i && onRowClick ? "var(--surface-sunken)" : "transparent",
                  cursor: onRowClick ? "pointer" : "default",
                  transition: "background-color var(--dur-fast) var(--ease-standard)",
                }}
              >
                {columns.map((c) => (
                  <td
                    key={c.key}
                    style={{
                      textAlign: c.align || "left",
                      padding: "var(--space-3) var(--space-4) var(--space-3) 0",
                      borderBottom: "1px solid var(--border-hairline)",
                      color: c.strong ? "var(--text-strong)" : "var(--text-body)",
                      fontWeight: c.strong ? "var(--weight-semibold)" : "var(--weight-regular)",
                      verticalAlign: "middle",
                    }}
                  >
                    {c.render ? c.render(r) : r[c.key]}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
