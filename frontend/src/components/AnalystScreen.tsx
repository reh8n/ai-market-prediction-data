import { useCallback, useEffect, useRef, useState } from "react";
import {
  Annotation,
  Badge,
  Button,
  Input,
  Select,
  SketchPanel,
  StatBlock,
} from "../design-system";
import {
  api,
  type ChatCapabilities,
  type ChatMessage,
  type ChatProvider,
  type ChatToolCall,
} from "../api";
import { PageHead } from "./AppShell";

interface Turn extends ChatMessage {
  tools?: ChatToolCall[];
}

const STARTERS = [
  "What is in this dataset right now?",
  "What do the failures have in common?",
  "Which businesses raised the most before dying?",
  "Is this corpus ready to train on?",
];

interface Props {
  apiKey: string;
  onKeyChange: (key: string) => void;
  onNotify: (title: string, body: string, tone: "info" | "alert") => void;
}

export default function AnalystScreen({ apiKey, onKeyChange, onNotify }: Props) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [caps, setCaps] = useState<ChatCapabilities | null>(null);
  // Empty means "work it out from the key's prefix", which is right most of
  // the time — the picker is for overriding that, not a required first step.
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [lastUsed, setLastUsed] = useState<{ provider: string; model: string } | null>(
    null,
  );
  const endRef = useRef<HTMLDivElement>(null);

  const chosen: ChatProvider | undefined = caps?.providers.find(
    (p) => p.id === provider,
  );

  useEffect(() => {
    api.chatCapabilities().then(setCaps).catch(() => {
      // Advisory only — the tab still works without it.
    });
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, busy]);

  const send = useCallback(
    async (text: string) => {
      const question = text.trim();
      if (!question || busy) return;
      if (!apiKey.trim()) {
        onNotify("Key needed", "Paste an API key above to use the analyst.", "alert");
        return;
      }

      const history: Turn[] = [...turns, { role: "user", content: question }];
      setTurns(history);
      setDraft("");
      setBusy(true);
      try {
        const response = await api.chat(
          history.map(({ role, content }) => ({ role, content })),
          apiKey,
          { provider, model, baseUrl },
        );
        setLastUsed({ provider: response.provider, model: response.model });
        setTurns([
          ...history,
          {
            role: "assistant",
            content: response.reply,
            tools: response.tool_calls,
          },
        ]);
      } catch (err) {
        // Keep the question in the thread so the user can retry it verbatim.
        setTurns([
          ...history,
          { role: "assistant", content: `Could not answer: ${String(err)}` },
        ]);
      } finally {
        setBusy(false);
      }
    },
    [apiKey, busy, turns, onNotify, provider, model, baseUrl],
  );

  return (
    <>
      <PageHead
        overline="Analyst // Ask the dataset"
        title="Data Analyst"
        right={
          turns.length > 0 ? (
            <Button size="sm" variant="secondary" onClick={() => setTurns([])}>
              New conversation
            </Button>
          ) : null
        }
      />

      <div className="split">
        <div className="stack">
          <SketchPanel overline="Conversation // Ask anything" tilt={false}>
            {turns.length === 0 ? (
              <div>
                <div
                  style={{
                    fontSize: "var(--size-small)",
                    color: "var(--text-muted)",
                    lineHeight: "var(--lh-snug)",
                    marginBottom: "var(--space-5)",
                  }}
                >
                  Ask about the data in plain English. The analyst reads the live
                  dataset before answering, so its numbers are the real ones — not
                  a guess.
                </div>
                <div
                  style={{
                    display: "grid",
                    gap: "var(--space-2)",
                  }}
                >
                  {STARTERS.map((starter) => (
                    <button
                      key={starter}
                      type="button"
                      onClick={() => void send(starter)}
                      style={{
                        textAlign: "left",
                        padding: "var(--space-3) var(--space-4)",
                        border: "1px solid var(--border-hairline)",
                        borderRadius: 6,
                        background: "transparent",
                        cursor: "pointer",
                        font: "inherit",
                        fontSize: "var(--size-small)",
                        color: "var(--text-body)",
                      }}
                    >
                      {starter}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div style={{ display: "grid", gap: "var(--space-5)" }}>
                {turns.map((turn, i) => (
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
                      {turn.role === "user" ? "You" : "Analyst"}
                    </div>

                    {turn.tools && turn.tools.length > 0 && (
                      <div
                        style={{
                          display: "flex",
                          gap: "var(--space-2)",
                          flexWrap: "wrap",
                          marginBottom: "var(--space-3)",
                        }}
                      >
                        {turn.tools.map((tool, t) => (
                          <Badge key={t} tone={tool.ok ? "neutral" : "warn"}>
                            {tool.name}
                          </Badge>
                        ))}
                      </div>
                    )}

                    <div
                      style={{
                        fontSize: "var(--size-body)",
                        lineHeight: "var(--lh-normal)",
                        color:
                          turn.role === "user"
                            ? "var(--text-strong)"
                            : "var(--text-body)",
                        whiteSpace: "pre-wrap",
                      }}
                    >
                      {turn.content}
                    </div>
                  </div>
                ))}

                {busy && (
                  <div
                    style={{
                      fontSize: "var(--size-small)",
                      color: "var(--text-faint)",
                    }}
                  >
                    Reading the dataset…
                  </div>
                )}
                <div ref={endRef} />
              </div>
            )}

            <div
              style={{
                display: "flex",
                gap: "var(--space-2)",
                marginTop: "var(--space-6)",
                paddingTop: "var(--space-4)",
                borderTop: "1px solid var(--border-hairline)",
              }}
            >
              <div style={{ flex: 1 }}>
                <Input
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  placeholder="Ask about the data…"
                  disabled={busy}
                />
              </div>
              <Button onClick={() => void send(draft)} disabled={busy || !draft.trim()}>
                {busy ? "Thinking…" : "Ask"}
              </Button>
            </div>
          </SketchPanel>
        </div>

        <div className="stack">
          <SketchPanel
            overline="Access // API key"
            title={apiKey ? "Connected" : "Key required"}
            tilt={false}
          >
            <Input
              type="password"
              value={apiKey}
              onChange={(e) => onKeyChange(e.target.value)}
              placeholder={chosen?.key_hint ?? "sk-…"}
              label="API key"
              hint="session only"
            />

            <div style={{ marginTop: "var(--space-4)" }}>
              <Select
                id="provider"
                label="Provider"
                value={provider}
                onChange={(e) => {
                  setProvider(e.target.value);
                  setModel("");
                }}
                options={[
                  { value: "", label: "auto — detect from key" },
                  ...(caps?.providers ?? []).map((p) => ({
                    value: p.id,
                    label: p.recommended ? `${p.label} — recommended` : p.label,
                  })),
                ]}
              />
            </div>

            {chosen?.needs_base_url && (
              <div style={{ marginTop: "var(--space-3)" }}>
                <Input
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                  placeholder="http://localhost:11434/v1"
                  label="Base URL"
                />
              </div>
            )}

            {provider && (
              <div style={{ marginTop: "var(--space-3)" }}>
                <Input
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  placeholder={chosen?.default_model || "model name"}
                  label="Model"
                  hint="optional"
                />
              </div>
            )}

            {lastUsed && (
              <div
                style={{
                  display: "flex",
                  gap: "var(--space-2)",
                  flexWrap: "wrap",
                  marginTop: "var(--space-4)",
                }}
              >
                <Badge tone="success">{lastUsed.provider}</Badge>
                <Badge>{lastUsed.model}</Badge>
              </div>
            )}

            <div
              style={{
                marginTop: "var(--space-4)",
                fontSize: "var(--size-small)",
                color: "var(--text-muted)",
                lineHeight: "var(--lh-snug)",
              }}
            >
              Any provider works. Anthropic and OpenAI are recommended — they
              handle tool calling most reliably, which is what lets the analyst
              look things up instead of guessing. Anything OpenAI-compatible
              (Groq, OpenRouter, Together, DeepSeek, Mistral, or a local server)
              works too.
            </div>
            <div
              style={{
                marginTop: "var(--space-3)",
                fontSize: "var(--size-small)",
                color: "var(--text-muted)",
                lineHeight: "var(--lh-snug)",
              }}
            >
              The key stays in this browser tab. It is sent with each question,
              never written to disk or saved in the database, and is gone when you
              refresh. The same key also enables the backfill buttons on the
              Training tab.
            </div>
          </SketchPanel>

          <SketchPanel overline="Analyst // What it can see" tilt={false}>
            <StatBlock
              label="Reads"
              value={String(caps?.tools.length ?? 0)}
              caption="Live views of your data"
              size="sm"
            />
            <div
              style={{
                marginTop: "var(--space-5)",
                paddingTop: "var(--space-4)",
                borderTop: "1px solid var(--border-hairline)",
              }}
            >
              <Annotation arrow="→">reads only, never writes</Annotation>
              <div
                style={{
                  marginTop: "var(--space-3)",
                  fontSize: "var(--size-small)",
                  color: "var(--text-muted)",
                  lineHeight: "var(--lh-snug)",
                }}
              >
                It can look up businesses, market data, video coverage, training
                counts and recent jobs. It cannot start a scrape, sync a ticker or
                change a setting — so nothing it says can cost you a run.
              </div>
              {caps && (
                <ul
                  style={{
                    margin: "var(--space-4) 0 0",
                    padding: 0,
                    listStyle: "none",
                    display: "grid",
                    gap: "var(--space-2)",
                    fontSize: "var(--size-small)",
                    color: "var(--text-faint)",
                  }}
                >
                  {caps.tools.map((tool) => (
                    <li key={tool.name} style={{ display: "flex", gap: "var(--space-2)" }}>
                      <span>·</span>
                      <span>{tool.name.replace(/_/g, " ")}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </SketchPanel>
        </div>
      </div>
    </>
  );
}
