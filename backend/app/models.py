from __future__ import annotations

import enum
from datetime import date as date_type
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Outcome(str, enum.Enum):
    success = "success"
    failure = "failure"
    unknown = "unknown"


class SourceType(str, enum.Enum):
    youtube = "youtube"
    article = "article"
    filing = "filing"


class JobStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    done = "done"
    failed = "failed"


class TranscriptMethod(str, enum.Enum):
    captions = "captions"
    whisper = "whisper"


class ContentKind(str, enum.Enum):
    """What a transcript is actually about, which decides how it is extracted."""

    company_analysis = "company_analysis"  # outcomes, ROI, causes
    trading_technique = "trading_technique"  # setups, entries, risk rules
    mixed = "mixed"
    other = "other"


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    ticker: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    industry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    outcome: Mapped[Outcome] = mapped_column(
        Enum(Outcome, native_enum=False), default=Outcome.unknown
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    instrument_id: Mapped[int | None] = mapped_column(
        ForeignKey("instruments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    events: Mapped[list[Event]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    sources: Mapped[list[Source]] = relationship(back_populates="company")
    instrument: Mapped[Instrument | None] = relationship(back_populates="companies")


class Event(Base):
    """A single success/failure datapoint about a company, with ROI where known."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[Outcome] = mapped_column(Enum(Outcome, native_enum=False))
    roi_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    timeframe_start: Mapped[str | None] = mapped_column(String(32), nullable=True)
    timeframe_end: Mapped[str | None] = mapped_column(String(32), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    company: Mapped[Company] = relationship(back_populates="events")


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    type: Mapped[SourceType] = mapped_column(Enum(SourceType, native_enum=False))
    url: Mapped[str] = mapped_column(String(1024), index=True)
    external_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )  # YouTube video id
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    channel: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, native_enum=False), default=JobStatus.pending, index=True
    )
    content_kind: Mapped[ContentKind | None] = mapped_column(
        Enum(ContentKind, native_enum=False), nullable=True, index=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    company: Mapped[Company | None] = relationship(back_populates="sources")
    transcript: Mapped[Transcript | None] = relationship(
        back_populates="source", cascade="all, delete-orphan", uselist=False
    )
    extractions: Mapped[list[Extraction]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )
    setups: Mapped[list[TradingSetup]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), unique=True, index=True
    )
    raw_text_path: Mapped[str] = mapped_column(String(1024))
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    transcript_method: Mapped[TranscriptMethod] = mapped_column(
        Enum(TranscriptMethod, native_enum=False)
    )
    char_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    source: Mapped[Source] = relationship(back_populates="transcript")


class Extraction(Base):
    __tablename__ = "extractions"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), index=True
    )
    content_kind: Mapped[ContentKind | None] = mapped_column(
        Enum(ContentKind, native_enum=False), nullable=True
    )
    extracted_json: Mapped[dict] = mapped_column(JSON)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    source: Mapped[Source] = relationship(back_populates="extractions")


class TradingSetup(Base):
    """A reusable trade pattern taught in a transcript.

    Deliberately separate from Event: an Event is a claim about a company, a
    setup is a conditional rule about price action with no company attached.
    """

    __tablename__ = "trading_setups"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    market: Mapped[str | None] = mapped_column(String(64), nullable=True)
    instrument_hint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    timeframe: Mapped[str | None] = mapped_column(String(64), nullable=True)
    direction: Mapped[str | None] = mapped_column(String(16), nullable=True)
    trigger: Mapped[str | None] = mapped_column(Text, nullable=True)
    entry_rule: Mapped[str | None] = mapped_column(Text, nullable=True)
    stop_rule: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_rule: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_rule: Mapped[str | None] = mapped_column(Text, nullable=True)
    invalidation: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    source: Mapped[Source] = relationship(back_populates="setups")


class ScrapeSite(Base):
    """A website the scraper knows how to read.

    Built-in sites are seeded on startup; anything else the user adds from the
    dashboard is stored here too, which is what makes new sites a config change
    rather than a code change.
    """

    __tablename__ = "scrape_sites"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    base_url: Mapped[str] = mapped_column(String(512))
    sitemap_url: Mapped[str] = mapped_column(String(512))
    url_pattern: Mapped[str] = mapped_column(String(255))
    exclude_pattern: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    built_in: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    jobs: Mapped[list[ScrapeJob]] = relationship(back_populates="site")
    pages: Mapped[list[ScrapedPage]] = relationship(back_populates="site")


class ScrapeJob(Base):
    """One run of the scraper, with the filters it was given."""

    __tablename__ = "scrape_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int | None] = mapped_column(
        ForeignKey("scrape_sites.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, native_enum=False), default=JobStatus.pending, index=True
    )
    requested: Mapped[int] = mapped_column(Integer, default=0)
    discovered: Mapped[int] = mapped_column(Integer, default=0)
    fetched: Mapped[int] = mapped_column(Integer, default=0)
    saved: Mapped[int] = mapped_column(Integer, default=0)
    skipped: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    ai_calls: Mapped[int] = mapped_column(Integer, default=0)
    filters: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    site: Mapped[ScrapeSite | None] = relationship(back_populates="jobs")


class ScrapedPage(Base):
    """One company page, with where every field came from.

    `rule_fields` and `ai_fields` record provenance so a later reviewer can see
    which numbers were read off the page and which an AI inferred.
    """

    __tablename__ = "scraped_pages"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int | None] = mapped_column(
        ForeignKey("scrape_sites.id", ondelete="SET NULL"), nullable=True, index=True
    )
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    url: Mapped[str] = mapped_column(String(1024), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    industry: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    country: Mapped[str | None] = mapped_column(String(64), nullable=True)
    founded_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shutdown_year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    funding_usd: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    raw_file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    rule_fields: Mapped[list] = mapped_column(JSON, default=list)
    ai_fields: Mapped[list] = mapped_column(JSON, default=list)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    site: Mapped[ScrapeSite | None] = relationship(back_populates="pages")


class DiscoveryJob(Base):
    """One run of YouTube auto-discovery.

    Counters are split finely because "found 60, queued 4" is the normal and
    healthy outcome - most search results are rejected on quality, and the
    operator needs to see that rather than assume discovery is broken.
    """

    __tablename__ = "discovery_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, native_enum=False), default=JobStatus.pending, index=True
    )
    topics: Mapped[list] = mapped_column(JSON, default=list)
    terms: Mapped[list] = mapped_column(JSON, default=list)
    filters: Mapped[dict] = mapped_column(JSON, default=dict)
    found: Mapped[int] = mapped_column(Integer, default=0)  # raw search hits
    rejected: Mapped[int] = mapped_column(Integer, default=0)  # failed quality gates
    duplicates: Mapped[int] = mapped_column(Integer, default=0)  # already stored
    queued: Mapped[int] = mapped_column(Integer, default=0)  # new sources created
    ingested: Mapped[int] = mapped_column(Integer, default=0)  # transcripts saved
    failed: Mapped[int] = mapped_column(Integer, default=0)
    reject_reasons: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class EnrichJob(Base):
    """One backfill pass of AI extraction over data already stored.

    Extraction normally runs during a scrape or ingest, which means turning a
    key on later does nothing for records collected before it. This is the
    catch-up path, and it re-reads saved page text rather than re-crawling.
    """

    __tablename__ = "enrich_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    target: Mapped[str] = mapped_column(String(32))  # "pages" | "sources"
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, native_enum=False), default=JobStatus.pending, index=True
    )
    candidates: Mapped[int] = mapped_column(Integer, default=0)
    processed: Mapped[int] = mapped_column(Integer, default=0)
    updated: Mapped[int] = mapped_column(Integer, default=0)
    unchanged: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    fields_filled: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Instrument(Base):
    """A listed security: the join point between filings and market prices."""

    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    cik: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sector: Mapped[str | None] = mapped_column(String(128), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(128), nullable=True)
    exchange: Mapped[str | None] = mapped_column(String(64), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    market_cap: Mapped[float | None] = mapped_column(Float, nullable=True)
    prices_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    financials_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    companies: Mapped[list[Company]] = relationship(back_populates="instrument")
    bars: Mapped[list[PriceBar]] = relationship(
        back_populates="instrument", cascade="all, delete-orphan"
    )
    financials: Mapped[list[Financial]] = relationship(
        back_populates="instrument", cascade="all, delete-orphan"
    )


class PriceBar(Base):
    __tablename__ = "price_bars"
    __table_args__ = (UniqueConstraint("instrument_id", "day", name="uq_bar_day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id", ondelete="CASCADE"), index=True
    )
    day: Mapped[date_type] = mapped_column(Date, index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float)

    instrument: Mapped[Instrument] = relationship(back_populates="bars")


class Financial(Base):
    """One reported metric for one period, as filed with the SEC."""

    __tablename__ = "financials"
    __table_args__ = (
        UniqueConstraint(
            "instrument_id", "metric", "period_end", "form", name="uq_financial_period"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id", ondelete="CASCADE"), index=True
    )
    metric: Mapped[str] = mapped_column(String(64), index=True)
    concept: Mapped[str] = mapped_column(String(128))
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(16))
    period_end: Mapped[str] = mapped_column(String(16), index=True)
    fiscal_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fiscal_period: Mapped[str | None] = mapped_column(String(8), nullable=True)
    form: Mapped[str | None] = mapped_column(String(16), nullable=True)
    filed: Mapped[str | None] = mapped_column(String(16), nullable=True)

    instrument: Mapped[Instrument] = relationship(back_populates="financials")
