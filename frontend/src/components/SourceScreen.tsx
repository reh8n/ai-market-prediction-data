import {
  Annotation,
  Badge,
  Button,
  SketchPanel,
  StatBlock,
} from "../design-system";
import type { SourceDetail } from "../api";
import { PageHead } from "./AppShell";
import { duration, statusTone } from "./DatasetScreen";

interface Props {
  source: SourceDetail;
  onBack: () => void;
}

export default function SourceScreen({ source, onBack }: Props) {
  const transcript = source.transcript;
  const extraction = source.extractions[0];
  const companies =
    (extraction?.extracted_json?.companies as unknown[] | undefined) ?? [];

  return (
    <>
      <PageHead
        overline={`Source // #${source.id} · ${source.type}`}
        title={source.title || `Source #${source.id}`}
        right={
          <Button variant="secondary" onClick={onBack}>
            ← Dataset
          </Button>
        }
      />

      <div className="stack">
        <SketchPanel overline="Capture // Job record" tilt={false}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--space-4)",
              flexWrap: "wrap",
              marginBottom: "var(--space-5)",
            }}
          >
            <Badge tone={statusTone(source.status)}>{source.status}</Badge>
            {source.content_kind && (
              <Badge tone="accent">
                {source.content_kind.replace(/_/g, " ")}
              </Badge>
            )}
            {source.channel && (
              <span
                style={{
                  fontSize: "var(--size-small)",
                  color: "var(--text-muted)",
                }}
              >
                {source.channel}
              </span>
            )}
            {source.published_at && (
              <span
                style={{
                  fontSize: "var(--size-small)",
                  color: "var(--text-muted)",
                }}
              >
                {source.published_at}
              </span>
            )}
            <a href={source.url} target="_blank" rel="noreferrer">
              open on youtube ↗
            </a>
          </div>

          {source.error && (
            <div
              style={{
                marginBottom: "var(--space-5)",
                padding: "var(--space-3) var(--space-4)",
                borderLeft: "var(--rail-w) solid var(--status-alert)",
                background: "var(--red-100)",
                borderRadius: "var(--radius-sketch-sm)",
                fontSize: "var(--size-small)",
                lineHeight: "var(--lh-snug)",
                color: "var(--text-body)",
              }}
            >
              {source.error}
            </div>
          )}

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(4, 1fr)",
              gap: "var(--space-6)",
            }}
          >
            <StatBlock
              label="Method"
              value={transcript?.transcript_method ?? "—"}
              size="sm"
              caption="Caption pull or whisper"
            />
            <StatBlock
              label="Language"
              value={transcript?.language ?? "—"}
              size="sm"
              caption="Detected track"
            />
            <StatBlock
              label="Duration"
              value={duration(transcript?.duration_seconds)}
              size="sm"
              caption="Source runtime"
            />
            <StatBlock
              label="Transcript"
              value={
                transcript?.char_count != null
                  ? `${transcript.char_count.toLocaleString()}`
                  : "—"
              }
              size="sm"
              caption="Characters captured"
            />
          </div>
        </SketchPanel>

        <div className="split-even">
          <SketchPanel
            overline="Transcript // Raw capture"
            title="Source Text"
            tilt={false}
          >
            {source.transcript_text ? (
              <pre className="code">{source.transcript_text}</pre>
            ) : (
              <div
                style={{
                  fontSize: "var(--size-small)",
                  color: "var(--text-faint)",
                }}
              >
                No transcript stored.
              </div>
            )}
          </SketchPanel>

          <SketchPanel
            overline={`Extraction // ${extraction?.provider ?? "not run"}`}
            title="Structured Facts"
            tilt={false}
            actions={
              extraction?.model_used ? (
                <Badge tone="accent">{extraction.model_used}</Badge>
              ) : null
            }
          >
            {extraction ? (
              <>
                {extraction.summary && (
                  <div
                    style={{
                      marginBottom: "var(--space-4)",
                      paddingLeft: "var(--space-4)",
                      borderLeft: "var(--rail-w) solid var(--rail-accent)",
                      fontSize: "var(--size-small)",
                      lineHeight: "var(--lh-snug)",
                      color: "var(--text-body)",
                    }}
                  >
                    {extraction.summary}
                  </div>
                )}
                <div
                  style={{
                    marginBottom: "var(--space-3)",
                    font: "var(--text-label)",
                    letterSpacing: "var(--track-label)",
                    textTransform: "uppercase",
                    color: "var(--text-muted)",
                  }}
                >
                  Companies identified [{companies.length}]
                </div>
                <pre className="code">
                  {JSON.stringify(extraction.extracted_json, null, 2)}
                </pre>
              </>
            ) : (
              <div
                style={{
                  fontSize: "var(--size-small)",
                  color: "var(--text-faint)",
                }}
              >
                No extraction recorded for this source.
              </div>
            )}
            <div style={{ marginTop: "var(--space-4)" }}>
              <Annotation arrow="↘">
                transcript survives even when extraction fails
              </Annotation>
            </div>
          </SketchPanel>
        </div>

        {source.setups.length > 0 && (
          <SketchPanel
            overline={`Setups // Extracted rules [${source.setups.length}]`}
            title="Trading Setups"
            tilt={false}
          >
            <div style={{ display: "grid", gap: "var(--space-5)" }}>
              {source.setups.map((setup) => (
                <div
                  key={setup.id}
                  style={{
                    borderLeft: "var(--rail-w) solid var(--rail-accent)",
                    paddingLeft: "var(--space-4)",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "var(--space-3)",
                      flexWrap: "wrap",
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
                      {setup.name}
                    </span>
                    {setup.direction && <Badge>{setup.direction}</Badge>}
                    {setup.timeframe && <Badge>{setup.timeframe}</Badge>}
                    {setup.instrument_hint && (
                      <Badge tone="accent">{setup.instrument_hint}</Badge>
                    )}
                    {setup.confidence_score != null && (
                      <span
                        style={{
                          fontSize: "var(--size-micro)",
                          letterSpacing: "var(--track-micro)",
                          textTransform: "uppercase",
                          color: "var(--text-faint)",
                        }}
                      >
                        confidence {setup.confidence_score.toFixed(2)}
                      </span>
                    )}
                  </div>
                  <div style={{ display: "grid", gap: "var(--space-2)" }}>
                    {(
                      [
                        ["Trigger", setup.trigger],
                        ["Entry", setup.entry_rule],
                        ["Stop", setup.stop_rule],
                        ["Target", setup.target_rule],
                        ["Risk", setup.risk_rule],
                        ["Invalidation", setup.invalidation],
                      ] as const
                    ).map(([label, value]) => (
                      <div
                        key={label}
                        style={{
                          display: "grid",
                          gridTemplateColumns: "110px 1fr",
                          gap: "var(--space-3)",
                          fontSize: "var(--size-small)",
                          lineHeight: "var(--lh-snug)",
                        }}
                      >
                        <span
                          style={{
                            fontSize: "var(--size-micro)",
                            letterSpacing: "var(--track-micro)",
                            textTransform: "uppercase",
                            color: "var(--text-muted)",
                            paddingTop: 2,
                          }}
                        >
                          {label}
                        </span>
                        <span style={{ color: "var(--text-body)" }}>
                          {value || "—"}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </SketchPanel>
        )}
      </div>
    </>
  );
}
