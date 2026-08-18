import { useMemo, useState } from "react";
import {
  Annotation,
  Badge,
  BarChart,
  Button,
  DataTable,
  Select,
  SketchPanel,
  StatBlock,
} from "../design-system";
import type { ExportResponse, Outcome } from "../api";
import { PageHead } from "./AppShell";

function outcomeTone(outcome: Outcome) {
  if (outcome === "success") return "success" as const;
  if (outcome === "failure") return "alert" as const;
  return "neutral" as const;
}

function signedPercent(value: number | null) {
  if (value == null) return "—";
  return `${value > 0 ? "+" : ""}${value}%`;
}

interface Props {
  data: ExportResponse | null;
  // Returns a promise so the refresh button can show progress and settle.
  onFilter: (outcome: Outcome | undefined) => void | Promise<void>;
}

export default function RecordsScreen({ data, onFilter }: Props) {
  const [outcome, setOutcome] = useState<"all" | Outcome>("all");
  const [refreshing, setRefreshing] = useState(false);

  const companies = data?.companies ?? [];

  const stats = useMemo(() => {
    const events = companies.flatMap((c) => c.events);
    const withRoi = events.filter((e) => e.roi_percent != null);
    const confidences = events
      .map((e) => e.confidence_score)
      .filter((c): c is number => c != null);
    const avgConfidence = confidences.length
      ? confidences.reduce((a, b) => a + b, 0) / confidences.length
      : null;
    return {
      records: companies.length,
      events: events.length,
      success: companies.filter((c) => c.outcome === "success").length,
      failure: companies.filter((c) => c.outcome === "failure").length,
      unknown: companies.filter((c) => c.outcome === "unknown").length,
      avgConfidence,
      topRoi: withRoi.length
        ? Math.max(...withRoi.map((e) => e.roi_percent as number))
        : null,
    };
  }, [companies]);

  // Highest-ROI records make the profile chart; the brand highlights by
  // swapping one bar's fill, never by colour-coding a series.
  const chartData = useMemo(() => {
    const points = companies
      .map((c) => {
        const best = c.events
          .map((e) => e.roi_percent)
          .filter((r): r is number => r != null);
        return {
          label: c.name,
          value: best.length ? Math.max(...best) : 0,
        };
      })
      .filter((p) => p.value > 0)
      .sort((a, b) => b.value - a.value)
      .slice(0, 8);
    if (!points.length) return [];
    return points.map((p, i) => ({
      ...p,
      tone: i === 0 ? ("accent" as const) : ("default" as const),
    }));
  }, [companies]);

  const applyFilter = (next: "all" | Outcome) => {
    setOutcome(next);
    onFilter(next === "all" ? undefined : next);
  };

  // The screen loads its export once on entry, so anything scraped or
  // discovered afterwards is missing until this is clicked. Re-fetching under
  // the current filter is the whole job - the deck is derived from `data`.
  const refresh = async () => {
    setRefreshing(true);
    try {
      await onFilter(outcome === "all" ? undefined : outcome);
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <>
      <PageHead
        overline="Records // Labeled outcomes"
        title="Extracted Dataset"
        right={
          <div style={{ width: 190 }}>
            <Select
              id="outcome"
              label="Outcome"
              value={outcome}
              onChange={(e) => applyFilter(e.target.value as "all" | Outcome)}
              options={[
                { value: "all", label: "all" },
                "success",
                "failure",
                "unknown",
              ]}
            />
          </div>
        }
      />

      <div className="split">
        <div className="stack">
          <SketchPanel
            overline="Dataset // GET /export/data"
            title="Model-Facing Records"
            tilt={false}
          >
            <DataTable
              rows={companies}
              columns={[
                { key: "name", label: "Company", strong: true },
                { key: "ticker", label: "Ticker", render: (r) => r.ticker || "—" },
                {
                  key: "industry",
                  label: "Industry",
                  render: (r) => r.industry || "—",
                },
                {
                  key: "outcome",
                  label: "Outcome",
                  render: (r) => (
                    <Badge tone={outcomeTone(r.outcome)}>{r.outcome}</Badge>
                  ),
                },
                {
                  key: "events",
                  label: "Events",
                  align: "right",
                  render: (r) => r.events.length,
                },
              ]}
              empty="No records extracted yet"
            />
            {companies.length === 0 && (
              <div
                style={{
                  marginTop: "var(--space-4)",
                  fontSize: "var(--size-small)",
                  color: "var(--text-muted)",
                  lineHeight: "var(--lh-snug)",
                }}
              >
                Extraction is disabled. Set EXTRACTION_PROVIDER and
                EXTRACTION_API_KEY, then re-queue a source.
              </div>
            )}
          </SketchPanel>

          {chartData.length > 0 && (
            <SketchPanel
              overline="Dataset profile // Visual schematic"
              title="Active Profile: [Peak ROI]"
              tilt={false}
            >
              <BarChart height={230} data={chartData} yUnit="%" />
            </SketchPanel>
          )}

          <SketchPanel overline="Events // Extracted facts" tilt={false}>
            <div style={{ display: "grid", gap: "var(--space-5)" }}>
              {companies.length === 0 && (
                <div
                  style={{
                    fontSize: "var(--size-small)",
                    color: "var(--text-faint)",
                  }}
                >
                  No events extracted yet.
                </div>
              )}
              {companies.map((company) => (
                <div key={company.company_id}>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "var(--space-3)",
                      marginBottom: "var(--space-3)",
                    }}
                  >
                    <span
                      style={{
                        font: "var(--text-label)",
                        letterSpacing: "var(--track-label)",
                        textTransform: "uppercase",
                        color: "var(--text-strong)",
                      }}
                    >
                      {company.name}
                    </span>
                    <Badge tone={outcomeTone(company.outcome)}>
                      {company.outcome}
                    </Badge>
                  </div>
                  <div style={{ display: "grid", gap: "var(--space-3)" }}>
                    {company.events.map((event) => (
                      <div
                        key={event.event_id}
                        style={{
                          borderLeft: "var(--rail-w) solid var(--rail-accent)",
                          paddingLeft: "var(--space-4)",
                        }}
                      >
                        <div
                          style={{
                            display: "flex",
                            gap: "var(--space-4)",
                            flexWrap: "wrap",
                            fontSize: "var(--size-micro)",
                            letterSpacing: "var(--track-micro)",
                            textTransform: "uppercase",
                            color: "var(--text-muted)",
                          }}
                        >
                          <span>ROI {signedPercent(event.roi_percent)}</span>
                          <span>
                            {event.timeframe_start || "—"}
                            {event.timeframe_end ? ` → ${event.timeframe_end}` : ""}
                          </span>
                          <span>
                            confidence{" "}
                            {event.confidence_score != null
                              ? event.confidence_score.toFixed(2)
                              : "—"}
                          </span>
                          {event.source_url && (
                            <a
                              href={event.source_url}
                              target="_blank"
                              rel="noreferrer"
                            >
                              source ↗
                            </a>
                          )}
                        </div>
                        {event.summary && (
                          <div
                            style={{
                              marginTop: "var(--space-2)",
                              fontSize: "var(--size-small)",
                              lineHeight: "var(--lh-snug)",
                              color: "var(--text-body)",
                              whiteSpace: "pre-wrap",
                            }}
                          >
                            {event.summary}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </SketchPanel>
        </div>

        <div className="stack">
          <SketchPanel
            overline="Executive summary // System metrics"
            tilt={false}
            actions={
              <Button
                size="sm"
                variant="secondary"
                onClick={() => void refresh()}
                disabled={refreshing}
              >
                {refreshing ? "Updating…" : "Update"}
              </Button>
            }
          >
            <div className="split-even" style={{ gap: "var(--space-6)" }}>
              <StatBlock
                label="Model confidence"
                value={
                  stats.avgConfidence != null
                    ? stats.avgConfidence.toFixed(2)
                    : "—"
                }
                meter={
                  stats.avgConfidence != null ? stats.avgConfidence * 100 : 0
                }
              />
              <StatBlock
                label="Labeled records"
                value={String(stats.records)}
                caption={`${stats.success} success · ${stats.failure} failure · ${stats.unknown} unknown`}
              />
              <StatBlock
                label="Extracted events"
                value={String(stats.events)}
                caption="Company-level datapoints"
              />
              <StatBlock
                label="Peak ROI"
                value={signedPercent(stats.topRoi)}
                caption="Highest stated return"
              />
            </div>

            <div
              style={{
                marginTop: "var(--space-6)",
                paddingTop: "var(--space-4)",
                borderTop: "1px solid var(--border-hairline)",
              }}
            >
              <Annotation arrow="→">Analytical Summary Deck</Annotation>
              <div
                style={{
                  marginTop: "var(--space-3)",
                  fontSize: "var(--size-small)",
                  color: "var(--text-muted)",
                  lineHeight: "var(--lh-snug)",
                }}
              >
                The numbers above, written out in plain sentences — what the
                dataset currently holds, how much of it an AI judged rather than
                read, and when the snapshot was taken. Press{" "}
                <strong>Update</strong> after a scrape or discovery run to pull a
                fresh snapshot.
              </div>
              <ul
                style={{
                  margin: "var(--space-4) 0 0",
                  padding: 0,
                  listStyle: "none",
                  display: "grid",
                  gap: "var(--space-2)",
                  fontSize: "var(--size-small)",
                  lineHeight: "var(--lh-snug)",
                }}
              >
                {[
                  outcome === "all"
                    ? `Dataset holds ${stats.records} labeled records across ${stats.events} extracted events.`
                    : `Showing ${stats.records} records filtered to "${outcome}", across ${stats.events} events — not the whole dataset.`,
                  stats.failure > 0 || stats.success > 0
                    ? `Split: ${stats.failure} failure, ${stats.success} success, ${stats.unknown} unknown.`
                    : "No outcomes labeled yet.",
                  stats.avgConfidence != null
                    ? `Mean extraction confidence is ${stats.avgConfidence.toFixed(2)} across all events.`
                    : "No confidence scores recorded — extraction has not run.",
                  data
                    ? `Snapshot generated ${new Date(data.generated_at).toLocaleString()}.`
                    : "Awaiting export snapshot.",
                  ...(stats.records >= 5000
                    ? ["Server page limit reached — counts are a page, not the total."]
                    : []),
                ].map((line, i) => (
                  <li
                    key={i}
                    style={{
                      display: "flex",
                      gap: "var(--space-2)",
                      color: "var(--text-body)",
                    }}
                  >
                    <span style={{ color: "var(--text-faint)" }}>·</span>
                    <span>{line}</span>
                  </li>
                ))}
              </ul>
            </div>
          </SketchPanel>
        </div>
      </div>
    </>
  );
}
