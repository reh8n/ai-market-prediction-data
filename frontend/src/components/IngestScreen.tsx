import { useState, type FormEvent } from "react";
import {
  Annotation,
  Badge,
  Button,
  Input,
  SketchPanel,
  StatusDot,
} from "../design-system";
import { api, type Source } from "../api";
import { PageHead } from "./AppShell";
import { statusTone } from "./DatasetScreen";

const STAGES = [
  ["01", "Parse video id", "Accepts full URL, short link, shorts or bare id."],
  ["02", "Fetch captions", "youtube-transcript-api. Free, no key, no audio download."],
  ["03", "Whisper fallback", "Only when captions are absent and the flag is enabled."],
  ["04", "AI extraction", "Structured facts against a fixed JSON schema."],
  ["05", "Persist", "Transcript to disk, company and event rows to the database."],
];

interface Props {
  sources: Source[];
  onQueued: (source: Source) => void;
  onOpenSource: (id: number) => void;
}

export default function IngestScreen({
  sources,
  onQueued,
  onOpenSource,
}: Props) {
  const [url, setUrl] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const queue = sources.filter(
    (s) => s.status === "pending" || s.status === "processing",
  );
  const recent = sources.slice(0, 8);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!url.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const source = await api.ingestYouTube(
        url.trim(),
        companyName.trim() || undefined,
      );
      setUrl("");
      setCompanyName("");
      onQueued(source);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PageHead overline="Ingest // Source submission" title="Queue a Source" />

      <div className="split">
        <div className="stack">
          <SketchPanel overline="New source // YouTube" tilt={false}>
            <form onSubmit={submit}>
              <div style={{ display: "grid", gap: "var(--space-4)" }}>
                <Input
                  id="url"
                  label="Source URL"
                  hint="required"
                  placeholder="https://www.youtube.com/watch?v=…"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  error={error ?? undefined}
                />
                <Input
                  id="company"
                  label="Company hint"
                  hint="optional"
                  placeholder="Extraction infers this when omitted"
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                />
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "var(--space-4)",
                  }}
                >
                  <Button type="submit" disabled={busy || !url.trim()}>
                    {busy ? "Queuing…" : "Queue scrape"}
                  </Button>
                  <span
                    style={{
                      fontSize: "var(--size-small)",
                      color: "var(--text-muted)",
                    }}
                  >
                    Runs as a background job · returns immediately
                  </span>
                </div>
              </div>
            </form>
          </SketchPanel>

          <SketchPanel overline="Pipeline // Processing stages" tilt={false}>
            <div style={{ display: "grid", gap: "var(--space-4)" }}>
              {STAGES.map(([n, name, detail]) => (
                <div
                  key={n}
                  style={{ display: "flex", gap: "var(--space-4)" }}
                >
                  <span
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: "var(--size-micro)",
                      letterSpacing: "var(--track-micro)",
                      color: "var(--text-faint)",
                      paddingTop: 3,
                    }}
                  >
                    {n}
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
                      {name}
                    </div>
                    <div
                      style={{
                        marginTop: "var(--space-1)",
                        fontSize: "var(--size-small)",
                        color: "var(--text-muted)",
                        lineHeight: "var(--lh-snug)",
                      }}
                    >
                      {detail}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </SketchPanel>
        </div>

        <div className="stack">
          <SketchPanel
            overline="Queue // In flight"
            tilt={false}
            actions={
              <StatusDot
                state={queue.length ? "warn" : "idle"}
                label={`${queue.length} active`}
                pulse={queue.length > 0}
              />
            }
          >
            {queue.length === 0 ? (
              <div
                style={{
                  fontSize: "var(--size-small)",
                  color: "var(--text-faint)",
                }}
              >
                Queue is empty.
              </div>
            ) : (
              <div style={{ display: "grid", gap: "var(--space-3)" }}>
                {queue.map((s) => (
                  <div
                    key={s.id}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "var(--space-3)",
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
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {s.title || s.url}
                    </span>
                    <Badge tone={statusTone(s.status)}>{s.status}</Badge>
                  </div>
                ))}
              </div>
            )}
            <div
              style={{
                marginTop: "var(--space-5)",
                paddingTop: "var(--space-4)",
                borderTop: "1px solid var(--border-hairline)",
              }}
            >
              <Annotation arrow="↘">duplicate urls return the existing row</Annotation>
            </div>
          </SketchPanel>

          <SketchPanel overline="History // Recent submissions" tilt={false}>
            <div style={{ display: "grid", gap: "var(--space-3)" }}>
              {recent.length === 0 && (
                <div
                  style={{
                    fontSize: "var(--size-small)",
                    color: "var(--text-faint)",
                  }}
                >
                  No submissions yet.
                </div>
              )}
              {recent.map((s) => (
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
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {s.title || s.url}
                  </span>
                  <Badge tone={statusTone(s.status)}>{s.status}</Badge>
                </div>
              ))}
            </div>
          </SketchPanel>
        </div>
      </div>
    </>
  );
}
