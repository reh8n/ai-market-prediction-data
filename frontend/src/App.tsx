import { useCallback, useEffect, useRef, useState } from "react";
import { Toast } from "./design-system";
import {
  api,
  type ExportResponse,
  type Outcome,
  type SearchHit,
  type Source,
  type SourceDetail,
} from "./api";
import AnalystScreen from "./components/AnalystScreen";
import AppShell, { type View } from "./components/AppShell";
import DatasetScreen from "./components/DatasetScreen";
import DiscoverScreen from "./components/DiscoverScreen";
import IngestScreen from "./components/IngestScreen";
import MarketScreen from "./components/MarketScreen";
import RecordsScreen from "./components/RecordsScreen";
import ScrapeScreen from "./components/ScrapeScreen";
import SourceScreen from "./components/SourceScreen";
import TrainingScreen from "./components/TrainingScreen";

interface Notice {
  id: number;
  tone: "info" | "success" | "warn" | "alert";
  title: string;
  body?: string;
}

export default function App() {
  const [view, setView] = useState<View>("dataset");
  const [sources, setSources] = useState<Source[]>([]);
  const [selected, setSelected] = useState<SourceDetail | null>(null);
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [exported, setExported] = useState<ExportResponse | null>(null);
  const [apiOnline, setApiOnline] = useState(true);
  // Held here, not in the Analyst tab, so the Training tab can reuse the same
  // key for backfills. Deliberately not persisted anywhere.
  const [apiKey, setApiKey] = useState("");
  const [notices, setNotices] = useState<Notice[]>([]);

  // Job terminal states are announced once, so a scrape finishing while the
  // operator is on another screen still surfaces.
  const seenTerminal = useRef<Map<number, Source["status"]>>(new Map());

  const notify = useCallback((notice: Omit<Notice, "id">) => {
    const id = Date.now() + Math.random();
    setNotices((current) => [...current, { ...notice, id }]);
    setTimeout(
      () => setNotices((current) => current.filter((n) => n.id !== id)),
      6000,
    );
  }, []);

  const refreshSources = useCallback(async () => {
    try {
      const next = await api.listSources();
      setApiOnline(true);

      for (const source of next) {
        const previous = seenTerminal.current.get(source.id);
        if (previous === source.status) continue;
        seenTerminal.current.set(source.id, source.status);
        if (previous === undefined) continue; // first sighting, not a transition
        if (source.status === "done") {
          notify({
            tone: "success",
            title: "Scrape complete",
            body: `#${source.id} · ${source.title || source.url}`,
          });
        } else if (source.status === "failed") {
          notify({
            tone: "alert",
            title: "Scrape failed",
            body: source.error ?? `#${source.id}`,
          });
        }
      }

      setSources(next);
    } catch (err) {
      setApiOnline(false);
      notify({ tone: "alert", title: "API unreachable", body: String(err) });
    }
  }, [notify]);

  useEffect(() => {
    void refreshSources();
  }, [refreshSources]);

  // Poll only while a job is in flight.
  useEffect(() => {
    const busy = sources.some(
      (s) => s.status === "pending" || s.status === "processing",
    );
    if (!busy) return;
    const timer = setInterval(() => void refreshSources(), 3000);
    return () => clearInterval(timer);
  }, [sources, refreshSources]);

  const loadExport = useCallback(
    async (outcome?: Outcome) => {
      try {
        setExported(await api.exportData(outcome));
      } catch (err) {
        notify({ tone: "alert", title: "Export failed", body: String(err) });
      }
    },
    [notify],
  );

  useEffect(() => {
    if (view === "records") void loadExport();
  }, [view, loadExport]);

  const openSource = useCallback(
    async (id: number) => {
      try {
        setSelected(await api.getSource(id, true));
        setView("dataset");
      } catch (err) {
        notify({ tone: "alert", title: "Source unavailable", body: String(err) });
      }
    },
    [notify],
  );

  const search = useCallback(
    async (query: string) => {
      try {
        const response = await api.search(query);
        setHits(response.hits);
        if (response.hits.length === 0) {
          notify({ tone: "info", title: "No matches", body: `Query: ${query}` });
        }
      } catch (err) {
        notify({ tone: "alert", title: "Search failed", body: String(err) });
      }
    },
    [notify],
  );

  const toast = notices.map((notice) => (
    <Toast
      key={notice.id}
      tone={notice.tone}
      title={notice.title}
      onDismiss={() =>
        setNotices((current) => current.filter((n) => n.id !== notice.id))
      }
    >
      {notice.body}
    </Toast>
  ));

  return (
    <AppShell
      view={view}
      apiOnline={apiOnline}
      onNav={(next) => {
        setSelected(null);
        setView(next);
      }}
      toast={toast}
    >
      {view === "dataset" &&
        (selected ? (
          <SourceScreen source={selected} onBack={() => setSelected(null)} />
        ) : (
          <DatasetScreen
            sources={sources}
            hits={hits}
            onSearch={search}
            onClearSearch={() => setHits(null)}
            onOpenSource={openSource}
            onNav={setView}
          />
        ))}

      {view === "discover" && (
        <DiscoverScreen
          onNotify={(title, body, tone) => notify({ title, body, tone })}
        />
      )}

      {view === "ingest" && (
        <IngestScreen
          sources={sources}
          onQueued={(source) => {
            notify({
              tone: "info",
              title: "Source queued",
              body: `#${source.id} · scraping in background`,
            });
            void refreshSources();
            setView("dataset");
          }}
          onOpenSource={openSource}
        />
      )}

      {view === "records" && (
        <RecordsScreen data={exported} onFilter={loadExport} />
      )}

      {view === "scrape" && (
        <ScrapeScreen
          onNotify={(title, body, tone) => notify({ title, body, tone })}
        />
      )}

      {view === "market" && (
        <MarketScreen
          onNotify={(title, body, tone) => notify({ title, body, tone })}
        />
      )}

      {view === "training" && (
        <TrainingScreen
          apiKey={apiKey}
          onNotify={(title, body, tone) => notify({ title, body, tone })}
        />
      )}

      {view === "analyst" && (
        <AnalystScreen
          apiKey={apiKey}
          onKeyChange={setApiKey}
          onNotify={(title, body, tone) => notify({ title, body, tone })}
        />
      )}
    </AppShell>
  );
}
