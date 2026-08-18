import type { ReactNode } from "react";
import { PanelLabel, StatusDot, Tag } from "../design-system";

export type View =
  | "dataset"
  | "discover"
  | "ingest"
  | "scrape"
  | "records"
  | "market"
  | "training"
  | "analyst";

const NAV: { id: View; label: string }[] = [
  { id: "dataset", label: "Dataset" },
  { id: "discover", label: "Discover" },
  { id: "ingest", label: "Videos" },
  { id: "scrape", label: "Businesses" },
  { id: "records", label: "Records" },
  { id: "market", label: "Market" },
  { id: "training", label: "Training" },
  { id: "analyst", label: "Analyst" },
];

interface Props {
  view: View;
  onNav: (view: View) => void;
  apiOnline: boolean;
  children: ReactNode;
  toast?: ReactNode;
}

export default function AppShell({
  view,
  onNav,
  apiOnline,
  children,
  toast,
}: Props) {
  return (
    <div style={{ minHeight: "100%", background: "var(--grid-bg)" }}>
      <header
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--space-8)",
          padding: "0 var(--page-pad)",
          height: 62,
          background: "var(--paper-000)",
          borderBottom: "1px solid var(--border-hairline)",
          position: "sticky",
          top: 0,
          zIndex: 20,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--space-3)",
          }}
        >
          <img
            src="/logo-emboss.png"
            alt=""
            style={{
              width: 30,
              height: 30,
              objectFit: "cover",
              borderRadius: "50%",
            }}
          />
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontWeight: "var(--weight-bold)",
              fontSize: "var(--size-h3)",
              color: "var(--text-strong)",
              letterSpacing: "var(--track-tight)",
            }}
          >
            Market Signal Research
          </span>
        </div>

        <nav
          style={{
            display: "flex",
            gap: "var(--space-5)",
            marginLeft: "auto",
          }}
        >
          {NAV.map((n) => (
            <button
              key={n.id}
              type="button"
              onClick={() => onNav(n.id)}
              style={{
                appearance: "none",
                background: "none",
                border: "none",
                borderBottom:
                  "2px solid " +
                  (view === n.id ? "var(--ink-800)" : "transparent"),
                padding: "20px 0 18px",
                font: "var(--text-label)",
                letterSpacing: "var(--track-label)",
                textTransform: "uppercase",
                color:
                  view === n.id ? "var(--text-strong)" : "var(--text-muted)",
                cursor: "pointer",
              }}
            >
              {n.label}
            </button>
          ))}
        </nav>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--space-4)",
          }}
        >
          <StatusDot
            state={apiOnline ? "ok" : "alert"}
            label={apiOnline ? "API 8000" : "API DOWN"}
            pulse={apiOnline}
          />
          <Tag>local</Tag>
        </div>
      </header>

      <main
        style={{ padding: "var(--page-pad)", maxWidth: 1240, margin: "0 auto" }}
      >
        {children}
      </main>

      <div
        style={{
          position: "fixed",
          right: "var(--page-pad)",
          bottom: "var(--page-pad)",
          display: "grid",
          gap: "var(--space-2)",
          zIndex: 40,
        }}
      >
        {toast}
      </div>
    </div>
  );
}

export function PageHead({
  overline,
  title,
  right,
}: {
  overline: string;
  title: string;
  right?: ReactNode;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-end",
        justifyContent: "space-between",
        gap: "var(--space-6)",
        marginBottom: "var(--panel-gap)",
      }}
    >
      <div>
        <PanelLabel>{overline}</PanelLabel>
        <h1
          style={{
            margin: "4px 0 0",
            fontFamily: "var(--font-mono)",
            fontWeight: "var(--weight-bold)",
            fontSize: "var(--size-display)",
            color: "var(--text-strong)",
            letterSpacing: "var(--track-tight)",
          }}
        >
          {title}
        </h1>
      </div>
      {right}
    </div>
  );
}
