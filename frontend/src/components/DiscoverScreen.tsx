import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  Annotation,
  Badge,
  Button,
  DataTable,
  Input,
  SketchPanel,
  StatBlock,
  Tag,
} from "../design-system";
import {
  api,
  type DiscoverCandidate,
  type DiscoverPreview,
  type DiscoverStats,
  type DiscoveryJob,
  type Topic,
} from "../api";
import { PageHead } from "./AppShell";
import { statusTone } from "./DatasetScreen";

function views(value: number | null) {
  if (value == null) return "—";
  if (value >= 1e6) return `${(value / 1e6).toFixed(1)}M`;
  if (value >= 1e3) return `${(value / 1e3).toFixed(0)}K`;
  return String(value);
}

function runtime(seconds: number | null) {
  if (seconds == null) return "—";
  const total = Math.round(seconds);
  const mins = Math.floor(total / 60);
  return `${mins}:${String(total % 60).padStart(2, "0")}`;
}

// Plain-language names for the machine reasons the API returns.
const REJECT_LABELS: Record<string, string> = {
  too_few_views: "too few views",
  too_short: "too short",
  too_long: "too long",
  no_captions: "no captions",
  title_mismatch: "title mismatch",
};

interface Props {
  onNotify: (title: string, body: string, tone: "info" | "alert") => void;
}

export default function DiscoverScreen({ onNotify }: Props) {
  const [topics, setTopics] = useState<Topic[]>([]);
  const [jobs, setJobs] = useState<DiscoveryJob[]>([]);
  const [stats, setStats] = useState<DiscoverStats | null>(null);
  const [preview, setPreview] = useState<DiscoverPreview | null>(null);

  const [picked, setPicked] = useState<string[]>([]);
  const [terms, setTerms] = useState("");
  const [limit, setLimit] = useState("10");
  const [minViews, setMinViews] = useState("10000");
  const [minMinutes, setMinMinutes] = useState("4");
  const [busy, setBusy] = useState<"preview" | "run" | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [t, j, s] = await Promise.all([
        api.listTopics(),
        api.listDiscoveryJobs(),
        api.discoverStats(),
      ]);
      setTopics(t);
      setJobs(j);
      setStats(s);
    } catch (err) {
      onNotify("Discovery unavailable", String(err), "alert");
    }
  }, [onNotify]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Poll only while a run is in flight.
  useEffect(() => {
    if (!stats?.jobs_running) return;
    const timer = setInterval(() => void refresh(), 4000);
    return () => clearInterval(timer);
  }, [stats?.jobs_running, refresh]);

  const payload = () => ({
    topics: picked,
    terms: terms
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean),
    limit: Number(limit) || 10,
    min_views: Number(minViews) || 0,
    min_duration_seconds: (Number(minMinutes) || 0) * 60,
    auto_ingest: true,
  });

  const nothingPicked = picked.length === 0 && !terms.trim();

  const doPreview = async () => {
    if (nothingPicked) return;
    setBusy("preview");
    try {
      const result = await api.previewDiscovery(payload());
      setPreview(result);
      // A bad channel handle is the common case here, and it is not the same
      // as "no results" - say so rather than blaming the filters.
      if (result.errors.length > 0) {
        onNotify("Search problem", result.errors[0], "alert");
      } else if (result.kept.length === 0) {
        onNotify("Nothing passed", "Loosen the filters and try again.", "info");
      }
    } catch (err) {
      onNotify("Preview failed", String(err), "alert");
    } finally {
      setBusy(null);
    }
  };

  const doRun = async (event: FormEvent) => {
    event.preventDefault();
    if (nothingPicked) return;
    setBusy("run");
    try {
      const job = await api.runDiscovery(payload());
      onNotify(
        "Discovery started",
        `Job ${job.id} · searching ${job.terms.length} queries`,
        "info",
      );
      void refresh();
    } catch (err) {
      onNotify("Discovery failed to start", String(err), "alert");
    } finally {
      setBusy(null);
    }
  };

  const toggle = (key: string) =>
    setPicked((current) =>
      current.includes(key)
        ? current.filter((k) => k !== key)
        : [...current, key],
    );

  const candidateColumns = [
    { key: "title" as const, label: "Video", strong: true },
    {
      key: "channel" as const,
      label: "Channel",
      render: (r: DiscoverCandidate) => r.channel || "—",
    },
    {
      key: "view_count" as const,
      label: "Views",
      align: "right" as const,
      render: (r: DiscoverCandidate) => views(r.view_count),
    },
    {
      key: "duration_seconds" as const,
      label: "Length",
      align: "right" as const,
      render: (r: DiscoverCandidate) => runtime(r.duration_seconds),
    },
  ];

  return (
    <>
      <PageHead
        overline="Discover // Automatic video search"
        title="Video Finder"
        right={
          <Button
            variant="secondary"
            onClick={doPreview}
            disabled={busy !== null || nothingPicked}
          >
            {busy === "preview" ? "Searching…" : "Preview"}
          </Button>
        }
      />

      <div className="split">
        <div className="stack">
          <SketchPanel overline="Subject // What to look for" tilt={false}>
            <form onSubmit={doRun}>
              <div
                style={{
                  display: "flex",
                  gap: "var(--space-2)",
                  flexWrap: "wrap",
                  marginBottom: "var(--space-5)",
                }}
              >
                {topics.map((topic) => (
                  <Tag
                    key={topic.key}
                    active={picked.includes(topic.key)}
                    onClick={() => toggle(topic.key)}
                  >
                    {topic.label}
                  </Tag>
                ))}
              </div>

              {picked.length > 0 && (
                <div
                  style={{
                    marginBottom: "var(--space-5)",
                    fontSize: "var(--size-small)",
                    color: "var(--text-muted)",
                    lineHeight: "var(--lh-snug)",
                  }}
                >
                  {topics
                    .filter((t) => picked.includes(t.key))
                    .map((t) => t.blurb)
                    .join(" ")}
                </div>
              )}

              <Input
                id="terms"
                label="Or search your own"
                hint="comma separated · a channel like @TJR_Trades also works"
                placeholder="tjr boot camp, @WSJ"
                value={terms}
                onChange={(e) => setTerms(e.target.value)}
              />

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr 1fr",
                  gap: "var(--space-3)",
                  marginTop: "var(--space-4)",
                }}
              >
                <Input
                  id="limit"
                  label="How many"
                  placeholder="10"
                  value={limit}
                  onChange={(e) => setLimit(e.target.value.replace(/\D/g, ""))}
                />
                <Input
                  id="views"
                  label="Min views"
                  placeholder="10000"
                  value={minViews}
                  onChange={(e) => setMinViews(e.target.value.replace(/\D/g, ""))}
                />
                <Input
                  id="minutes"
                  label="Min length"
                  hint="minutes"
                  placeholder="4"
                  value={minMinutes}
                  onChange={(e) =>
                    setMinMinutes(e.target.value.replace(/\D/g, ""))
                  }
                />
              </div>

              <div style={{ marginTop: "var(--space-5)" }}>
                <Button type="submit" disabled={busy !== null || nothingPicked}>
                  {busy === "run" ? "Starting…" : "Find and ingest videos"}
                </Button>
              </div>
            </form>

            <div
              style={{
                marginTop: "var(--space-5)",
                paddingTop: "var(--space-4)",
                borderTop: "1px solid var(--border-hairline)",
                fontSize: "var(--size-small)",
                color: "var(--text-muted)",
                lineHeight: "var(--lh-snug)",
              }}
            >
              Videos without captions are dropped before queueing — there is
              nothing to read on them. Preview searches without saving anything.
            </div>
          </SketchPanel>

          {preview && (
            <SketchPanel
              overline={`Preview // Would keep [${preview.kept.length}]`}
              title="Nothing saved yet"
              tilt={false}
              actions={
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setPreview(null)}
                >
                  Clear
                </Button>
              }
            >
              {preview.errors.length > 0 && (
                <ul
                  style={{
                    margin: "0 0 var(--space-4)",
                    padding: 0,
                    listStyle: "none",
                    display: "grid",
                    gap: "var(--space-2)",
                    fontSize: "var(--size-small)",
                    color: "var(--tone-alert, var(--text-strong))",
                    lineHeight: "var(--lh-snug)",
                  }}
                >
                  {preview.errors.map((message, i) => (
                    <li key={i}>{message}</li>
                  ))}
                </ul>
              )}
              <DataTable
                rows={preview.kept}
                columns={candidateColumns}
                empty="Nothing passed the filters"
              />
              {Object.keys(preview.reject_reasons).length > 0 && (
                <div
                  style={{
                    marginTop: "var(--space-4)",
                    display: "flex",
                    gap: "var(--space-2)",
                    flexWrap: "wrap",
                  }}
                >
                  {Object.entries(preview.reject_reasons).map(([key, n]) => (
                    <Badge key={key}>
                      {n} {REJECT_LABELS[key] ?? key}
                    </Badge>
                  ))}
                </div>
              )}
            </SketchPanel>
          )}

          <SketchPanel overline={`Runs // History [${jobs.length}]`} tilt={false}>
            <DataTable
              rows={jobs}
              columns={[
                {
                  key: "id",
                  label: "Job",
                  strong: true,
                  render: (r) => `#${r.id}`,
                },
                {
                  key: "topics",
                  label: "Looked for",
                  render: (r) =>
                    r.topics.length
                      ? r.topics
                          .map(
                            (k: string) =>
                              topics.find((t) => t.key === k)?.label ?? k,
                          )
                          .join(", ")
                      : `${r.terms.length} search${r.terms.length === 1 ? "" : "es"}`,
                },
                {
                  key: "found",
                  label: "Found",
                  align: "right",
                  render: (r) => r.found,
                },
                {
                  key: "queued",
                  label: "Kept",
                  align: "right",
                  render: (r) => r.queued,
                },
                {
                  key: "ingested",
                  label: "Read",
                  align: "right",
                  render: (r) => r.ingested,
                },
                {
                  key: "status",
                  label: "Status",
                  render: (r) => (
                    <Badge tone={statusTone(r.status)}>{r.status}</Badge>
                  ),
                },
              ]}
              empty="No discovery runs yet"
            />
          </SketchPanel>
        </div>

        <div className="stack">
          <SketchPanel overline="Library // Videos" tilt={false}>
            <div className="split-even" style={{ gap: "var(--space-6)" }}>
              <StatBlock
                label="Videos"
                value={String(stats?.videos ?? 0)}
                meter={
                  stats?.videos ? (stats.transcribed / stats.videos) * 100 : 0
                }
              />
              <StatBlock
                label="Transcribed"
                value={String(stats?.transcribed ?? 0)}
                caption="Text pulled and stored"
              />
              <StatBlock
                label="Channels"
                value={String(stats?.channels ?? 0)}
                caption="Distinct sources"
              />
              <StatBlock
                label="Failed"
                value={String(stats?.failed ?? 0)}
                caption="No captions or blocked"
              />
            </div>

            <div
              style={{
                marginTop: "var(--space-6)",
                paddingTop: "var(--space-4)",
                borderTop: "1px solid var(--border-hairline)",
              }}
            >
              <Annotation arrow="→">rejects are normal, not failures</Annotation>
              <div
                style={{
                  marginTop: "var(--space-3)",
                  fontSize: "var(--size-small)",
                  color: "var(--text-muted)",
                  lineHeight: "var(--lh-snug)",
                }}
              >
                A search returns far more videos than it keeps. Most are too
                short, too small, or have no captions to read.
              </div>
            </div>
          </SketchPanel>

          {preview && preview.rejected.length > 0 && (
            <SketchPanel
              overline={`Rejected // Sample [${preview.rejected.length}]`}
              tilt={false}
            >
              <ul
                style={{
                  margin: 0,
                  padding: 0,
                  listStyle: "none",
                  display: "grid",
                  gap: "var(--space-3)",
                  fontSize: "var(--size-small)",
                  lineHeight: "var(--lh-snug)",
                }}
              >
                {preview.rejected.slice(0, 8).map((item) => (
                  <li key={item.video_id}>
                    <div style={{ color: "var(--text-body)" }}>
                      {item.title || item.video_id}
                    </div>
                    <div style={{ color: "var(--text-faint)" }}>
                      {REJECT_LABELS[item.reject_reason ?? ""] ??
                        item.reject_reason}{" "}
                      · {views(item.view_count)} views ·{" "}
                      {runtime(item.duration_seconds)}
                    </div>
                  </li>
                ))}
              </ul>
            </SketchPanel>
          )}
        </div>
      </div>
    </>
  );
}
