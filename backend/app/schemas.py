from __future__ import annotations

from datetime import date as date_type
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import (
    ContentKind,
    JobStatus,
    Outcome,
    SourceType,
    TranscriptMethod,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- companies ----------


class CompanyCreate(BaseModel):
    name: str
    ticker: str | None = None
    industry: str | None = None
    outcome: Outcome = Outcome.unknown
    notes: str | None = None


class EventOut(ORMModel):
    id: int
    company_id: int
    type: Outcome
    roi_percent: float | None
    timeframe_start: str | None
    timeframe_end: str | None
    summary: str | None
    confidence_score: float | None
    source_id: int | None


class CompanyOut(ORMModel):
    id: int
    name: str
    ticker: str | None
    industry: str | None
    outcome: Outcome
    notes: str | None
    created_at: datetime


class CompanyDetail(CompanyOut):
    events: list[EventOut] = []


# ---------- sources ----------


class YouTubeIngestRequest(BaseModel):
    url: str = Field(..., description="Full YouTube URL or bare video id")
    company_name: str | None = Field(
        None, description="Optional hint; extraction can also infer the company"
    )


class TranscriptOut(ORMModel):
    id: int
    source_id: int
    raw_text_path: str
    language: str | None
    duration_seconds: float | None
    transcript_method: TranscriptMethod
    char_count: int | None


class ExtractionOut(ORMModel):
    id: int
    source_id: int
    content_kind: ContentKind | None
    extracted_json: dict
    summary: str | None
    model_used: str | None
    provider: str | None
    reviewed: bool
    extracted_at: datetime


class TradingSetupOut(ORMModel):
    id: int
    source_id: int
    name: str
    market: str | None
    instrument_hint: str | None
    timeframe: str | None
    direction: str | None
    trigger: str | None
    entry_rule: str | None
    stop_rule: str | None
    target_rule: str | None
    risk_rule: str | None
    invalidation: str | None
    confidence_score: float | None


class SourceOut(ORMModel):
    id: int
    company_id: int | None
    type: SourceType
    url: str
    external_id: str | None
    title: str | None
    channel: str | None
    published_at: str | None
    status: JobStatus
    content_kind: ContentKind | None
    error: str | None
    raw_file_path: str | None
    fetched_at: datetime | None
    created_at: datetime


class SourceDetail(SourceOut):
    transcript: TranscriptOut | None = None
    extractions: list[ExtractionOut] = []
    setups: list[TradingSetupOut] = []
    transcript_text: str | None = None


# ---------- scraping ----------


class ScrapeSiteOut(ORMModel):
    id: int
    key: str
    name: str
    base_url: str
    sitemap_url: str
    url_pattern: str
    exclude_pattern: str | None
    notes: str | None
    built_in: bool
    enabled: bool
    last_run_at: datetime | None


class ScrapeSiteCreate(BaseModel):
    name: str
    base_url: str
    key: str | None = None
    sitemap_url: str | None = Field(None, description="Defaults to /sitemap.xml")
    url_pattern: str | None = Field(
        None, description="Regex a URL must match to count as a company page"
    )
    exclude_pattern: str | None = None


class ScrapeRunRequest(BaseModel):
    site_key: str
    limit: int = Field(25, ge=1, le=500, description="How many businesses to save")
    industry: str | None = None
    year_min: int | None = Field(None, description="Earliest shutdown year")
    year_max: int | None = None
    funding_min: float | None = Field(None, description="Minimum raised, in USD")
    funding_max: float | None = None
    use_ai: bool = Field(True, description="Fill gaps with AI when a key is set")


class ScrapeJobOut(ORMModel):
    id: int
    site_id: int | None
    status: JobStatus
    requested: int
    discovered: int
    fetched: int
    saved: int
    skipped: int
    failed: int
    ai_calls: int
    filters: dict
    error: str | None
    started_at: datetime
    finished_at: datetime | None


# ---------- video discovery ----------


class DiscoverRunRequest(BaseModel):
    topics: list[str] = Field(
        default_factory=list, description="Topic keys from GET /discover/topics"
    )
    terms: list[str] = Field(
        default_factory=list,
        description="Free-text searches, or a channel handle/URL like @TJR_Trades",
    )
    limit: int = Field(20, ge=1, le=200, description="How many videos to keep")
    per_query: int = Field(15, ge=1, le=50, description="Results pulled per search")
    min_views: int = Field(1000, ge=0, description="Reject videos below this")
    min_duration_seconds: int = Field(240, ge=0, description="Reject clips shorter")
    max_duration_seconds: int = Field(10800, ge=60, description="Reject livestreams")
    require_captions: bool = Field(
        True, description="Verify captions exist before queueing"
    )
    title_must_match: str | None = Field(
        None, description="Keep only titles containing this text"
    )
    auto_ingest: bool = Field(
        True, description="Scrape and extract each video after queueing"
    )


class DiscoverPreviewRequest(DiscoverRunRequest):
    """Same knobs, but nothing is saved - used to sanity-check filters."""


class DiscoverCandidate(BaseModel):
    video_id: str
    url: str
    title: str | None
    channel: str | None
    duration_seconds: float | None
    view_count: int | None
    query: str | None
    reject_reason: str | None = None


class DiscoverPreviewResponse(BaseModel):
    searched: list[str]
    kept: list[DiscoverCandidate]
    rejected: list[DiscoverCandidate]
    reject_reasons: dict[str, int]
    errors: list[str]


class DiscoveryJobOut(ORMModel):
    id: int
    status: JobStatus
    topics: list
    terms: list
    filters: dict
    found: int
    rejected: int
    duplicates: int
    queued: int
    ingested: int
    failed: int
    reject_reasons: dict
    error: str | None
    started_at: datetime
    finished_at: datetime | None


class TopicOut(BaseModel):
    key: str
    label: str
    blurb: str
    queries: list[str]


class ScrapedPageOut(ORMModel):
    id: int
    site_id: int | None
    company_id: int | None
    url: str
    name: str | None
    description: str | None
    cause: str | None
    industry: str | None
    country: str | None
    founded_year: int | None
    shutdown_year: int | None
    funding_usd: float | None
    status: str | None
    rule_fields: list
    ai_fields: list
    scraped_at: datetime


# ---------- market ----------


class TickerSyncRequest(BaseModel):
    ticker: str = Field(..., description="Exchange ticker, e.g. AAPL")
    period: str | None = Field(
        None, description="yfinance period shorthand: 1y, 5y, max. Defaults to config."
    )


class PriceBarOut(ORMModel):
    day: date_type
    open: float
    high: float
    low: float
    close: float
    volume: float


class FinancialOut(ORMModel):
    metric: str
    concept: str
    value: float
    unit: str
    period_end: str
    fiscal_year: int | None
    fiscal_period: str | None
    form: str | None


class InstrumentOut(ORMModel):
    id: int
    ticker: str
    cik: int | None
    name: str | None
    sector: str | None
    industry: str | None
    exchange: str | None
    currency: str | None
    market_cap: float | None
    prices_synced_at: datetime | None
    financials_synced_at: datetime | None
    sync_error: str | None


class InstrumentDetail(InstrumentOut):
    bars: list[PriceBarOut] = []
    financials: list[FinancialOut] = []
    return_1m: float | None = None
    return_3m: float | None = None
    return_1y: float | None = None
    volatility: float | None = None
    latest_period: str | None = None
    latest_metrics: dict[str, float] = {}
    latest_ratios: dict[str, float] = {}
    revenue_growth: float | None = None


# ---------- search ----------


class SearchHit(BaseModel):
    kind: str  # "company" | "event" | "source" | "extraction"
    id: int
    title: str
    snippet: str | None = None
    company_id: int | None = None
    source_id: int | None = None


class SearchResponse(BaseModel):
    query: str
    total: int
    hits: list[SearchHit]


# ---------- export (what the prediction model consumes) ----------


class ExportEvent(BaseModel):
    event_id: int
    type: Outcome
    roi_percent: float | None
    timeframe_start: str | None
    timeframe_end: str | None
    summary: str | None
    confidence_score: float | None
    source_url: str | None


class ExportCompany(BaseModel):
    company_id: int
    name: str
    ticker: str | None
    industry: str | None
    outcome: Outcome
    events: list[ExportEvent]


class ExportResponse(BaseModel):
    generated_at: datetime
    count: int
    companies: list[ExportCompany]
