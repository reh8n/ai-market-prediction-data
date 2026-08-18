const BASE = "/api";

export type Outcome = "success" | "failure" | "unknown";
export type JobStatus = "pending" | "processing" | "done" | "failed";
export type ContentKind =
  | "company_analysis"
  | "trading_technique"
  | "mixed"
  | "other";

export interface Source {
  id: number;
  company_id: number | null;
  type: string;
  url: string;
  external_id: string | null;
  title: string | null;
  channel: string | null;
  published_at: string | null;
  status: JobStatus;
  content_kind: ContentKind | null;
  error: string | null;
  raw_file_path: string | null;
  fetched_at: string | null;
  created_at: string;
}

export interface Transcript {
  id: number;
  source_id: number;
  raw_text_path: string;
  language: string | null;
  duration_seconds: number | null;
  transcript_method: "captions" | "whisper";
  char_count: number | null;
}

export interface Extraction {
  id: number;
  source_id: number;
  content_kind: ContentKind | null;
  extracted_json: Record<string, unknown>;
  summary: string | null;
  model_used: string | null;
  provider: string | null;
  reviewed: boolean;
  extracted_at: string;
}

export interface TradingSetup {
  id: number;
  source_id: number;
  name: string;
  market: string | null;
  instrument_hint: string | null;
  timeframe: string | null;
  direction: string | null;
  trigger: string | null;
  entry_rule: string | null;
  stop_rule: string | null;
  target_rule: string | null;
  risk_rule: string | null;
  invalidation: string | null;
  confidence_score: number | null;
}

export interface SourceDetail extends Source {
  transcript: Transcript | null;
  extractions: Extraction[];
  setups: TradingSetup[];
  transcript_text: string | null;
}

export interface Instrument {
  id: number;
  ticker: string;
  cik: number | null;
  name: string | null;
  sector: string | null;
  industry: string | null;
  exchange: string | null;
  currency: string | null;
  market_cap: number | null;
  prices_synced_at: string | null;
  financials_synced_at: string | null;
  sync_error: string | null;
}

export interface PriceBar {
  day: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface FinancialRow {
  metric: string;
  concept: string;
  value: number;
  unit: string;
  period_end: string;
  fiscal_year: number | null;
  fiscal_period: string | null;
  form: string | null;
}

export interface InstrumentDetail extends Instrument {
  bars: PriceBar[];
  financials: FinancialRow[];
  return_1m: number | null;
  return_3m: number | null;
  return_1y: number | null;
  volatility: number | null;
  latest_period: string | null;
  latest_metrics: Record<string, number>;
  latest_ratios: Record<string, number>;
  revenue_growth: number | null;
}

export interface TickerSearchResult {
  ticker: string;
  cik: number;
  name: string;
}

export interface ScrapeSite {
  id: number;
  key: string;
  name: string;
  base_url: string;
  sitemap_url: string;
  url_pattern: string;
  exclude_pattern: string | null;
  notes: string | null;
  built_in: boolean;
  enabled: boolean;
  last_run_at: string | null;
}

export interface ScrapeJob {
  id: number;
  site_id: number | null;
  status: JobStatus;
  requested: number;
  discovered: number;
  fetched: number;
  saved: number;
  skipped: number;
  failed: number;
  ai_calls: number;
  filters: Record<string, unknown>;
  error: string | null;
  started_at: string;
  finished_at: string | null;
}

export interface ScrapedPage {
  id: number;
  site_id: number | null;
  company_id: number | null;
  url: string;
  name: string | null;
  description: string | null;
  cause: string | null;
  industry: string | null;
  country: string | null;
  founded_year: number | null;
  shutdown_year: number | null;
  funding_usd: number | null;
  status: string | null;
  rule_fields: string[];
  ai_fields: string[];
  scraped_at: string;
}

export interface ScrapeStats {
  pages: number;
  with_cause: number;
  with_funding: number;
  ai_assisted: number;
  jobs_running: number;
}

export interface Topic {
  key: string;
  label: string;
  blurb: string;
  queries: string[];
}

export interface DiscoverCandidate {
  video_id: string;
  url: string;
  title: string | null;
  channel: string | null;
  duration_seconds: number | null;
  view_count: number | null;
  query: string | null;
  reject_reason: string | null;
}

export interface DiscoverPreview {
  searched: string[];
  kept: DiscoverCandidate[];
  rejected: DiscoverCandidate[];
  reject_reasons: Record<string, number>;
  errors: string[];
}

export interface DiscoveryJob {
  id: number;
  status: JobStatus;
  topics: string[];
  terms: string[];
  filters: Record<string, unknown>;
  found: number;
  rejected: number;
  duplicates: number;
  queued: number;
  ingested: number;
  failed: number;
  reject_reasons: Record<string, number>;
  error: string | null;
  started_at: string;
  finished_at: string | null;
}

export interface DiscoverStats {
  videos: number;
  transcribed: number;
  failed: number;
  channels: number;
  jobs_running: number;
}

export interface DiscoverRequest {
  topics: string[];
  terms: string[];
  limit: number;
  per_query?: number;
  min_views?: number;
  min_duration_seconds?: number;
  max_duration_seconds?: number;
  require_captions?: boolean;
  auto_ingest?: boolean;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatToolCall {
  name: string;
  input: Record<string, unknown>;
  ok: boolean;
}

export interface ChatResponse {
  reply: string;
  tool_calls: ChatToolCall[];
  usage: { input_tokens?: number; output_tokens?: number };
  provider: string;
  model: string;
}

export interface ChatProvider {
  id: string;
  label: string;
  recommended: boolean;
  protocol: string;
  default_model: string;
  needs_base_url: boolean;
  key_hint: string;
}

export interface ChatCapabilities {
  key_handling: string;
  access: string;
  providers: ChatProvider[];
  tools: { name: string; description: string }[];
}

export interface ChatOptions {
  provider?: string;
  model?: string;
  baseUrl?: string;
}

export interface EnrichStatus {
  configured: boolean;
  provider: string;
  model: string | null;
  detail: string;
  pages_total: number;
  pages_missing_fields: number;
  field_gaps: Record<string, number>;
  sources_awaiting_extraction: number;
  extractions: number;
  trading_setups: number;
  note: string;
}

export interface EnrichJob {
  id: number;
  target: string;
  status: JobStatus;
  candidates: number;
  processed: number;
  updated: number;
  unchanged: number;
  failed: number;
  fields_filled: Record<string, number>;
  error: string | null;
  started_at: string;
  finished_at: string | null;
}

export interface ScrapeRunRequest {
  site_key: string;
  limit: number;
  industry?: string | null;
  year_min?: number | null;
  year_max?: number | null;
  funding_min?: number | null;
  funding_max?: number | null;
  use_ai?: boolean;
}

export type ExampleKind =
  | "company_outcome"
  | "market_vs_finances"
  | "trading_setup"
  | "business_failure";

export interface TrainingExample {
  messages: { role: string; content: string }[];
  metadata: Record<string, unknown>;
}

export interface TrainingPreview {
  counts: Record<ExampleKind | "total", number>;
  skipped: string[];
  skipped_total: number;
  examples: TrainingExample[];
}

export interface SearchHit {
  kind: string;
  id: number;
  title: string;
  snippet: string | null;
  company_id: number | null;
  source_id: number | null;
}

export interface SearchResponse {
  query: string;
  total: number;
  hits: SearchHit[];
}

export interface ExportEvent {
  event_id: number;
  type: Outcome;
  roi_percent: number | null;
  timeframe_start: string | null;
  timeframe_end: string | null;
  summary: string | null;
  confidence_score: number | null;
  source_url: string | null;
}

export interface ExportCompany {
  company_id: number;
  name: string;
  ticker: string | null;
  industry: string | null;
  outcome: Outcome;
  events: ExportEvent[];
}

export interface ExportResponse {
  generated_at: string;
  count: number;
  companies: ExportCompany[];
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    // Merge rather than spread-replace: a caller passing one header must not
    // silently drop Content-Type.
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${body}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<Record<string, unknown>>("/health"),
  search: (q: string) =>
    request<SearchResponse>(`/search?q=${encodeURIComponent(q)}`),
  listSources: () => request<Source[]>("/sources"),
  getSource: (id: number, includeTranscript = false) =>
    request<SourceDetail>(
      `/sources/${id}?include_transcript=${includeTranscript}`,
    ),
  ingestYouTube: (url: string, companyName?: string) =>
    request<Source>("/sources/youtube", {
      method: "POST",
      body: JSON.stringify({ url, company_name: companyName || null }),
    }),
  // The endpoint defaults to 500, which silently truncated the Records screen
  // and made its summary understate the dataset. Ask for the server maximum.
  exportData: (outcome?: Outcome, limit = 5000) =>
    request<ExportResponse>(
      `/export/data?limit=${limit}${outcome ? `&outcome=${outcome}` : ""}`,
    ),

  listInstruments: () => request<Instrument[]>("/market/instruments"),
  getInstrument: (ticker: string, bars = 260) =>
    request<InstrumentDetail>(
      `/market/instruments/${encodeURIComponent(ticker)}?bars=${bars}`,
    ),
  syncInstrument: (ticker: string, period?: string) =>
    request<Instrument>("/market/instruments", {
      method: "POST",
      body: JSON.stringify({ ticker, period: period ?? null }),
    }),
  searchTickers: (q: string) =>
    request<{ query: string; results: TickerSearchResult[] }>(
      `/market/search?q=${encodeURIComponent(q)}`,
    ),

  listScrapeSites: () => request<ScrapeSite[]>("/scrape/sites"),
  addScrapeSite: (payload: {
    name: string;
    base_url: string;
    sitemap_url?: string | null;
    url_pattern?: string | null;
  }) =>
    request<ScrapeSite>("/scrape/sites", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  deleteScrapeSite: async (id: number) => {
    const response = await fetch(`${BASE}/scrape/sites/${id}`, {
      method: "DELETE",
    });
    if (!response.ok) throw new Error(await response.text());
  },
  runScrape: (payload: ScrapeRunRequest) =>
    request<ScrapeJob>("/scrape/run", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  listScrapeJobs: () => request<ScrapeJob[]>("/scrape/jobs"),
  listScrapedPages: (limit = 100) =>
    request<ScrapedPage[]>(`/scrape/pages?limit=${limit}`),
  scrapeStats: () => request<ScrapeStats>("/scrape/stats"),

  // The key is a request parameter, never persisted anywhere. It lives in
  // React state for the tab's lifetime and is gone on refresh.
  chat: (messages: ChatMessage[], apiKey: string, options: ChatOptions = {}) =>
    request<ChatResponse>("/chat", {
      method: "POST",
      body: JSON.stringify({
        messages,
        api_key: apiKey,
        provider: options.provider || null,
        model: options.model || null,
        base_url: options.baseUrl || null,
      }),
    }),
  chatCapabilities: () => request<ChatCapabilities>("/chat/capabilities"),

  // The key travels in a header, never the URL — query strings end up in
  // access logs and browser history.
  enrichStatus: (apiKey?: string) =>
    request<EnrichStatus>("/enrich/status", {
      headers: apiKey ? { "X-Extraction-Key": apiKey } : undefined,
    }),
  runEnrich: (target: "pages" | "sources", limit?: number, apiKey?: string) =>
    request<EnrichJob>(
      `/enrich/run?target=${target}${limit ? `&limit=${limit}` : ""}`,
      {
        method: "POST",
        headers: apiKey ? { "X-Extraction-Key": apiKey } : undefined,
      },
    ),
  listEnrichJobs: () => request<EnrichJob[]>("/enrich/jobs"),

  listTopics: () => request<Topic[]>("/discover/topics"),
  previewDiscovery: (payload: DiscoverRequest) =>
    request<DiscoverPreview>("/discover/preview", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  runDiscovery: (payload: DiscoverRequest) =>
    request<DiscoveryJob>("/discover/run", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  listDiscoveryJobs: () => request<DiscoveryJob[]>("/discover/jobs"),
  discoverStats: () => request<DiscoverStats>("/discover/stats"),

  trainingPreview: (kinds: ExampleKind[] = [], limit = 3) => {
    const params = new URLSearchParams({ limit: String(limit) });
    kinds.forEach((k) => params.append("kinds", k));
    return request<TrainingPreview>(`/training/preview?${params}`);
  },
  trainingExportUrl: (kinds: ExampleKind[] = [], includeMetadata = true) => {
    const params = new URLSearchParams({
      include_metadata: String(includeMetadata),
    });
    kinds.forEach((k) => params.append("kinds", k));
    return `${BASE}/training/export.jsonl?${params}`;
  },
};
