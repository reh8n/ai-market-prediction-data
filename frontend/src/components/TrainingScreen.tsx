import { useCallback, useEffect, useState } from "react";
import {
  Annotation,
  Badge,
  Button,
  SketchPanel,
  StatBlock,
  Tag,
} from "../design-system";
import {
  api,
  type EnrichJob,
  type EnrichStatus,
  type ExampleKind,
  type TrainingPreview,
} from "../api";
import { PageHead } from "./AppShell";

const KINDS: { id: ExampleKind; label: string; blurb: string }[] = [
  {
    id: "company_outcome",
    label: "Company outcome",
    blurb: "Filings + price action + commentary → outcome judgment.",
  },
  {
    id: "market_vs_finances",
    label: "Market vs finances",
    blurb:
      "Filings + price action → realized forward return. Label is measured, not judged.",
  },
  {
    id: "trading_setup",
    label: "Trading setup",
    blurb: "Taught rules → executable trigger, entry, stop, target.",
  },
  {
    id: "business_failure",
    label: "Business failure",
    blurb:
      "Scraped company profile → why it failed. Cause written by the source, not inferred.",
  },
];

interface Props {
  /** Shared with the Analyst tab; empty until the operator types one there. */
  apiKey: string;
  onNotify: (title: string, body: string, tone: "info" | "alert") => void;
}

export default function TrainingScreen({ apiKey, onNotify }: Props) {
  const [selected, setSelected] = useState<ExampleKind[]>([]);
  const [preview, setPreview] = useState<TrainingPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [shown, setShown] = useState(0);
  const [enrich, setEnrich] = useState<EnrichStatus | null>(null);
  const [enrichJob, setEnrichJob] = useState<EnrichJob | null>(null);
  const [enriching, setEnriching] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      setPreview(await api.trainingPreview(selected, 4));
    } catch (err) {
      onNotify("Preview failed", String(err), "alert");
    } finally {
      setBusy(false);
    }
  }, [selected, onNotify]);

  const loadEnrich = useCallback(async () => {
    try {
      setEnrich(await api.enrichStatus(apiKey || undefined));
      const jobs = await api.listEnrichJobs();
      setEnrichJob(jobs[0] ?? null);
    } catch {
      // Status is advisory - a failure here must not blank the screen.
    }
  }, [apiKey]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    void loadEnrich();
  }, [loadEnrich]);

  // Poll while a backfill is in flight, then refresh the corpus counts.
  useEffect(() => {
    const running =
      enrichJob?.status === "pending" || enrichJob?.status === "processing";
    if (!running) return;
    const timer = setInterval(() => {
      void loadEnrich();
      void load();
    }, 4000);
    return () => clearInterval(timer);
  }, [enrichJob?.status, loadEnrich, load]);

  const runBackfill = async (target: "pages" | "sources") => {
    setEnriching(true);
    try {
      const job = await api.runEnrich(target, undefined, apiKey || undefined);
      setEnrichJob(job);
      onNotify(
        "Backfill started",
        `Job ${job.id} · ${target === "pages" ? "scraped businesses" : "video transcripts"}`,
        "info",
      );
    } catch (err) {
      onNotify("Backfill unavailable", String(err), "alert");
    } finally {
      setEnriching(false);
    }
  };

  const toggle = (kind: ExampleKind) =>
    setSelected((current) =>
      current.includes(kind)
        ? current.filter((k) => k !== kind)
        : [...current, kind],
    );

  const counts = preview?.counts;
  const example = preview?.examples[shown];

  return (
    <>
      <PageHead
        overline="Training // Fine-tuning corpus"
        title="Model Training Data"
        right={
          <Button
            onClick={() => {
              // Anchor download: the browser handles the file, no blob juggling.
              const link = document.createElement("a");
              link.href = api.trainingExportUrl(selected);
              link.download = "training_data.jsonl";
              link.click();
              onNotify(
                "Export started",
                `${counts?.total ?? 0} examples · training_data.jsonl`,
                "info",
              );
            }}
            disabled={!counts?.total}
          >
            Download .jsonl
          </Button>
        }
      />

      <div className="split">
        <div className="stack">
          <SketchPanel overline="Corpus // Example types" tilt={false}>
            <div
              style={{
                display: "flex",
                gap: "var(--space-2)",
                flexWrap: "wrap",
                marginBottom: "var(--space-5)",
              }}
            >
              {KINDS.map((kind) => (
                <Tag
                  key={kind.id}
                  active={selected.includes(kind.id)}
                  onClick={() => toggle(kind.id)}
                >
                  {kind.label}
                </Tag>
              ))}
              {selected.length > 0 && (
                <Button size="sm" variant="ghost" onClick={() => setSelected([])}>
                  All
                </Button>
              )}
            </div>

            <div style={{ display: "grid", gap: "var(--space-4)" }}>
              {KINDS.map((kind) => (
                <div key={kind.id} style={{ display: "flex", gap: "var(--space-4)" }}>
                  <span
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontWeight: "var(--weight-bold)",
                      fontSize: "var(--size-h2)",
                      color: "var(--text-strong)",
                      width: 52,
                      textAlign: "right",
                    }}
                  >
                    {counts?.[kind.id] ?? 0}
                  </span>
                  <div>
                    <div
                      style={{
                        font: "var(--text-label)",
                        letterSpacing: "var(--track-label)",
                        textTransform: "uppercase",
                        color: "var(--text-strong)",
                      }}
                    >
                      {kind.label}
                    </div>
                    <div
                      style={{
                        marginTop: "var(--space-1)",
                        fontSize: "var(--size-small)",
                        color: "var(--text-muted)",
                        lineHeight: "var(--lh-snug)",
                      }}
                    >
                      {kind.blurb}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </SketchPanel>

          <SketchPanel
            overline="Sample // Rendered example"
            title={
              example
                ? `Example ${shown + 1} of ${preview?.examples.length ?? 0}`
                : "No examples"
            }
            tilt={false}
            actions={
              preview && preview.examples.length > 1 ? (
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() =>
                    setShown((n) => (n + 1) % preview.examples.length)
                  }
                >
                  Next
                </Button>
              ) : null
            }
          >
            {example ? (
              <div style={{ display: "grid", gap: "var(--space-4)" }}>
                <div
                  style={{
                    display: "flex",
                    gap: "var(--space-2)",
                    flexWrap: "wrap",
                  }}
                >
                  <Badge tone="accent">
                    {String(example.metadata.example_type)}
                  </Badge>
                  {example.metadata.ticker ? (
                    <Badge>{String(example.metadata.ticker)}</Badge>
                  ) : null}
                  {/* Without this, several rows for one company at different
                      quarters look like exact duplicates. */}
                  {example.metadata.period_end ? (
                    <Badge>{String(example.metadata.period_end)}</Badge>
                  ) : null}
                  {example.metadata.label_source ? (
                    <Badge tone="success">
                      {String(example.metadata.label_source)}
                    </Badge>
                  ) : null}
                </div>
                {example.messages.map((message, i) => (
                  <div key={i}>
                    <div
                      style={{
                        font: "var(--text-label)",
                        letterSpacing: "var(--track-label)",
                        textTransform: "uppercase",
                        color: "var(--text-muted)",
                        marginBottom: "var(--space-2)",
                      }}
                    >
                      {message.role}
                    </div>
                    <pre className="code" style={{ maxHeight: 260 }}>
                      {message.content}
                    </pre>
                  </div>
                ))}
              </div>
            ) : (
              <div
                style={{
                  fontSize: "var(--size-small)",
                  color: "var(--text-faint)",
                }}
              >
                {busy ? "Building…" : "No examples for the selected types."}
              </div>
            )}
          </SketchPanel>
        </div>

        <div className="stack">
          <SketchPanel overline="Corpus // Totals" tilt={false}>
            <StatBlock
              label="Training examples"
              value={String(counts?.total ?? 0)}
              caption="Rows in the exported .jsonl"
            />
            <div style={{ marginTop: "var(--space-6)" }}>
              <StatBlock
                label="Skipped records"
                value={String(preview?.skipped_total ?? 0)}
                caption="Insufficient context to train on"
                size="sm"
              />
            </div>

            <div
              style={{
                marginTop: "var(--space-6)",
                paddingTop: "var(--space-4)",
                borderTop: "1px solid var(--border-hairline)",
              }}
            >
              <Annotation arrow="→">one json object per line</Annotation>
              <div
                style={{
                  marginTop: "var(--space-3)",
                  fontSize: "var(--size-small)",
                  color: "var(--text-muted)",
                  lineHeight: "var(--lh-snug)",
                }}
              >
                Each row carries system, user and assistant turns — the format
                Anthropic, OpenAI and most open-weight fine-tuners accept.
              </div>
            </div>
          </SketchPanel>

          <SketchPanel
            overline="Extraction // AI enrichment"
            title={enrich?.configured ? "Enabled" : "Off"}
            tilt={false}
          >
            <div
              style={{
                display: "flex",
                gap: "var(--space-2)",
                flexWrap: "wrap",
                marginBottom: "var(--space-4)",
              }}
            >
              <Badge tone={enrich?.configured ? "success" : "neutral"}>
                {enrich?.provider ?? "—"}
              </Badge>
              {enrich?.trading_setups === 0 && (
                <Badge tone="warn">0 trading setups</Badge>
              )}
            </div>

            {enrich && !enrich.configured ? (
              <div
                style={{
                  fontSize: "var(--size-small)",
                  color: "var(--text-muted)",
                  lineHeight: "var(--lh-snug)",
                }}
              >
                Transcripts and pages are stored, but nothing is being read out
                of them. Paste a key on the <strong>Analyst</strong> tab to enable
                this without restarting, or set it permanently in{" "}
                <code>backend/.env</code>:
                <pre className="code" style={{ marginTop: "var(--space-3)" }}>
                  {`EXTRACTION_PROVIDER=anthropic\nEXTRACTION_API_KEY=your-key-here`}
                </pre>
                Extraction only runs during a scrape or ingest, so a key added
                now leaves existing records untouched — run a backfill once it
                is set.
              </div>
            ) : (
              <div
                style={{
                  fontSize: "var(--size-small)",
                  color: "var(--text-muted)",
                  lineHeight: "var(--lh-snug)",
                }}
              >
                Backfill re-reads saved page text and stored transcripts. Sites
                are never re-crawled.
              </div>
            )}

            <div
              style={{
                display: "grid",
                gap: "var(--space-3)",
                marginTop: "var(--space-5)",
              }}
            >
              <div style={{ display: "flex", gap: "var(--space-2)" }}>
                <Button
                  size="sm"
                  onClick={() => void runBackfill("pages")}
                  disabled={enriching || !enrich?.configured}
                >
                  Backfill businesses
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => void runBackfill("sources")}
                  disabled={enriching || !enrich?.configured}
                >
                  Backfill videos
                </Button>
              </div>

              {enrich && (
                <div
                  style={{
                    fontSize: "var(--size-small)",
                    color: "var(--text-faint)",
                    lineHeight: "var(--lh-snug)",
                  }}
                >
                  {enrich.pages_missing_fields} businesses have gaps ·{" "}
                  {enrich.sources_awaiting_extraction} videos unread
                </div>
              )}

              {enrichJob && (
                <div
                  style={{
                    fontSize: "var(--size-small)",
                    color: "var(--text-body)",
                    lineHeight: "var(--lh-snug)",
                  }}
                >
                  Job #{enrichJob.id} · {enrichJob.status} ·{" "}
                  {enrichJob.updated} updated of {enrichJob.processed} read
                  {enrichJob.error ? ` · ${enrichJob.error}` : ""}
                </div>
              )}
            </div>
          </SketchPanel>

          {preview && preview.skipped.length > 0 && (
            <SketchPanel overline="Skipped // Reasons" tilt={false}>
              <ul
                style={{
                  margin: 0,
                  padding: 0,
                  listStyle: "none",
                  display: "grid",
                  gap: "var(--space-2)",
                  fontSize: "var(--size-small)",
                  lineHeight: "var(--lh-snug)",
                }}
              >
                {preview.skipped.map((reason, i) => (
                  <li
                    key={i}
                    style={{ display: "flex", gap: "var(--space-2)" }}
                  >
                    <span style={{ color: "var(--text-faint)" }}>·</span>
                    <span style={{ color: "var(--text-body)" }}>{reason}</span>
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
