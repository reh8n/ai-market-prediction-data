import { useMemo, useState, type FormEvent } from "react";
import {
  Annotation,
  Badge,
  Button,
  DataTable,
  Input,
  Select,
  SketchPanel,
  StatBlock,
} from "../design-system";
import type { SearchHit, Source } from "../api";
import { PageHead } from "./AppShell";

type StatusFilter = "all" | "done" | "processing" | "pending" | "failed";

function statusTone(status: Source["status"]) {
  if (status === "done") return "success" as const;
  if (status === "failed") return "alert" as const;
  if (status === "processing" || status === "pending") return "warn" as const;
  return "neutral" as const;
}

function duration(seconds: number | null | undefined) {
  if (seconds == null) return "—";
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}m ${String(s).padStart(2, "0")}s`;
}

interface Props {
  sources: Source[];
  hits: SearchHit[] | null;
  onSearch: (query: string) => void;
  onClearSearch: () => void;
  onOpenSource: (id: number) => void;
  onNav: (view: "ingest") => void;
}

export default function DatasetScreen({
  sources,
  hits,
  onSearch,
  onClearSearch,
  onOpenSource,
  onNav,
}: Props) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<StatusFilter>("all");

  const rows = useMemo(
    () => sources.filter((s) => status === "all" || s.status === status),
    [sources, status],
  );

  const stats = useMemo(() => {
    const done = sources.filter((s) => s.status === "done").length;
    const failed = sources.filter((s) => s.status === "failed").length;
    const running = sources.filter(
      (s) => s.status === "pending" || s.status === "processing",
    ).length;
    return { done, failed, running, total: sources.length };
  }, [sources]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (query.trim()) onSearch(query.trim());
    else onClearSearch();
  };

  return (
    <>
      <PageHead
        overline="Dataset // Collected sources"
        title="Research Dataset"
        right={<Button onClick={() => onNav("ingest")}>Add source</Button>}
      />

      <div className="split">
        <div className="stack">
          <SketchPanel overline="Search // Companies, events & sources" tilt={false}>
            <form onSubmit={submit}>
              <div
                style={{
                  display: "flex",
                  gap: "var(--space-3)",
                  alignItems: "flex-end",
                }}
              >
                <Input
                  id="q"
                  label="Query"
                  placeholder="company, ticker, industry, channel…"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  prefix={<span aria-hidden="true">⌕</span>}
                />
                <div style={{ width: 180 }}>
                  <Select
                    id="status"
                    label="Job status"
                    value={status}
                    onChange={(e) =>
                      setStatus(e.target.value as StatusFilter)
                    }
                    options={[
                      { value: "all", label: "all" },
                      "done",
                      "processing",
                      "pending",
                      "failed",
                    ]}
                  />
                </div>
                <Button type="submit" style={{ flex: "0 0 auto" }}>
                  Search
                </Button>
              </div>
            </form>

            {hits !== null && (
              <div style={{ marginTop: "var(--space-5)" }}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "baseline",
                    justifyContent: "space-between",
                    marginBottom: "var(--space-3)",
                  }}
                >
                  <span
                    style={{
                      font: "var(--text-label)",
                      letterSpacing: "var(--track-label)",
                      textTransform: "uppercase",
                      color: "var(--text-muted)",
                    }}
                  >
                    Matches [{hits.length}]
                  </span>
                  <Button size="sm" variant="ghost" onClick={onClearSearch}>
                    Clear
                  </Button>
                </div>
                <DataTable
                  rows={hits}
                  onRowClick={(r) => r.source_id && onOpenSource(r.source_id)}
                  columns={[
                    { key: "kind", label: "Kind", render: (r) => <Badge>{r.kind}</Badge> },
                    { key: "title", label: "Match", strong: true },
                    {
                      key: "snippet",
                      label: "Context",
                      render: (r) => r.snippet || "—",
                    },
                  ]}
                  empty="No records match that query"
                />
              </div>
            )}

            <div style={{ marginTop: "var(--space-6)" }}>
              <DataTable
                rows={rows}
                onRowClick={(r) => onOpenSource(r.id)}
                columns={[
                  { key: "id", label: "#", width: 44 },
                  {
                    key: "title",
                    label: "Source",
                    strong: true,
                    render: (r) => r.title || r.url,
                  },
                  { key: "channel", label: "Channel", render: (r) => r.channel || "—" },
                  {
                    key: "published_at",
                    label: "Published",
                    render: (r) => r.published_at || "—",
                  },
                  {
                    key: "status",
                    label: "State",
                    render: (r) => (
                      <Badge tone={statusTone(r.status)}>{r.status}</Badge>
                    ),
                  },
                ]}
                empty="No sources attached yet"
              />
            </div>

            <div
              style={{
                marginTop: "var(--space-4)",
                fontSize: "var(--size-micro)",
                letterSpacing: "var(--track-label)",
                textTransform: "uppercase",
                color: "var(--text-faint)",
              }}
            >
              {rows.length} of {sources.length} sources · ilike substring match
            </div>
          </SketchPanel>
        </div>

        <div className="stack">
          <SketchPanel overline="Pipeline // System metrics" tilt={false}>
            <div className="split-even" style={{ gap: "var(--space-6)" }}>
              <StatBlock
                label="Sources processed"
                value={String(stats.done)}
                meter={stats.total ? (stats.done / stats.total) * 100 : 0}
              />
              <StatBlock
                label="In flight"
                value={String(stats.running)}
                caption="Queued or scraping"
              />
              <StatBlock
                label="Failed"
                value={String(stats.failed)}
                caption="Requires operator review"
              />
              <StatBlock
                label="Total sources"
                value={String(stats.total)}
                caption="All ingest attempts"
              />
            </div>

            <div
              style={{
                marginTop: "var(--space-6)",
                paddingTop: "var(--space-4)",
                borderTop: "1px solid var(--border-hairline)",
              }}
            >
              <Annotation arrow="→">captions first — whisper is expensive</Annotation>
            </div>
          </SketchPanel>

          <SketchPanel overline="Transcripts // Recent captures" tilt={false}>
            <div style={{ display: "grid", gap: "var(--space-3)" }}>
              {sources.filter((s) => s.status === "done").length === 0 && (
                <div
                  style={{
                    fontSize: "var(--size-small)",
                    color: "var(--text-faint)",
                  }}
                >
                  No transcripts captured yet.
                </div>
              )}
              {sources
                .filter((s) => s.status === "done")
                .slice(0, 6)
                .map((s) => (
                  <div
                    key={s.id}
                    onClick={() => onOpenSource(s.id)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "var(--space-3)",
                      paddingBottom: "var(--space-3)",
                      borderBottom: "1px solid var(--border-hairline)",
                      cursor: "pointer",
                    }}
                  >
                    <span
                      style={{
                        fontSize: "var(--size-micro)",
                        color: "var(--text-faint)",
                        width: 34,
                      }}
                    >
                      #{s.id}
                    </span>
                    <span
                      style={{
                        flex: 1,
                        minWidth: 0,
                        fontSize: "var(--size-small)",
                        color: "var(--text-body)",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {s.title || s.url}
                    </span>
                    <span
                      style={{
                        fontSize: "var(--size-micro)",
                        color: "var(--text-faint)",
                      }}
                    >
                      {s.published_at || "—"}
                    </span>
                  </div>
                ))}
            </div>
          </SketchPanel>
        </div>
      </div>
    </>
  );
}

export { statusTone, duration };
