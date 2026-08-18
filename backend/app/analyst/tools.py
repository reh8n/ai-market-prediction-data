"""Read-only tools the analyst can call to answer questions with real numbers.

Every tool here reads. Nothing writes, scrapes, or spends money - the analyst
is a lens over collected data, not another way to run the pipeline. That is a
deliberate boundary: the chat key is typed into a browser, and a tool surface
that could trigger jobs would let a stray sentence start real work.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Company,
    DiscoveryJob,
    Event,
    Extraction,
    Financial,
    Instrument,
    Outcome,
    PriceBar,
    ScrapedPage,
    ScrapeJob,
    ScrapeSite,
    Source,
    SourceType,
    TradingSetup,
)

# Bounded so one call cannot dump the whole database into the context window.
MAX_ROWS = 40


def _overview(db: Session, **_: Any) -> dict:
    """Counts across everything, plus the health signals worth volunteering."""
    companies = db.scalar(select(func.count()).select_from(Company)) or 0
    pages = db.scalars(select(ScrapedPage)).all()
    videos = db.scalars(select(Source).where(Source.type == SourceType.youtube)).all()
    real_extractions = (
        db.scalar(
            select(func.count()).select_from(Extraction).where(Extraction.provider != "null")
        )
        or 0
    )
    return {
        "companies": companies,
        "scraped_businesses": len(pages),
        "businesses_with_stated_cause": sum(1 for p in pages if p.cause),
        "businesses_with_funding": sum(1 for p in pages if p.funding_usd),
        "businesses_ai_assisted": sum(1 for p in pages if p.ai_fields),
        "videos": len(videos),
        "videos_transcribed": sum(1 for v in videos if v.status.value == "done"),
        "videos_failed": sum(1 for v in videos if v.status.value == "failed"),
        "distinct_channels": len({v.channel for v in videos if v.channel}),
        "instruments": db.scalar(select(func.count()).select_from(Instrument)) or 0,
        "price_bars": db.scalar(select(func.count()).select_from(PriceBar)) or 0,
        "trading_setups": db.scalar(select(func.count()).select_from(TradingSetup)) or 0,
        "real_extractions": real_extractions,
        "extraction_enabled": real_extractions > 0,
    }


def _search_companies(
    db: Session,
    query: str | None = None,
    industry: str | None = None,
    outcome: str | None = None,
    country: str | None = None,
    min_funding_usd: float | None = None,
    shutdown_year_min: int | None = None,
    shutdown_year_max: int | None = None,
    limit: int = 20,
    **_: Any,
) -> dict:
    stmt = select(ScrapedPage).order_by(ScrapedPage.id)
    if query:
        like = f"%{query}%"
        stmt = stmt.where(
            ScrapedPage.name.ilike(like)
            | ScrapedPage.description.ilike(like)
            | ScrapedPage.cause.ilike(like)
        )
    if industry:
        stmt = stmt.where(ScrapedPage.industry.ilike(f"%{industry}%"))
    if country:
        stmt = stmt.where(ScrapedPage.country.ilike(f"%{country}%"))
    if min_funding_usd:
        stmt = stmt.where(ScrapedPage.funding_usd >= min_funding_usd)
    if shutdown_year_min:
        stmt = stmt.where(ScrapedPage.shutdown_year >= shutdown_year_min)
    if shutdown_year_max:
        stmt = stmt.where(ScrapedPage.shutdown_year <= shutdown_year_max)

    rows = db.scalars(stmt.limit(min(limit, MAX_ROWS))).all()
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    if outcome:  # lives on Company, not the page
        wanted = outcome.lower()
        keep = []
        for page in rows:
            company = db.get(Company, page.company_id) if page.company_id else None
            if company and company.outcome.value == wanted:
                keep.append(page)
        rows = keep

    return {
        "total_matching": total,
        "returned": len(rows),
        "companies": [
            {
                "id": p.company_id,
                "name": p.name,
                "industry": p.industry,
                "country": p.country,
                "founded_year": p.founded_year,
                "shutdown_year": p.shutdown_year,
                "funding_usd": p.funding_usd,
                "cause": (p.cause[:400] if p.cause else None),
                "source_url": p.url,
            }
            for p in rows
        ],
    }


def _get_company(db: Session, name: str | None = None, company_id: int | None = None, **_: Any) -> dict:
    company = None
    if company_id:
        company = db.get(Company, company_id)
    elif name:
        company = db.scalar(
            select(Company).options(selectinload(Company.events)).where(Company.name.ilike(f"%{name}%"))
        )
    if company is None:
        return {"found": False, "reason": "No company matched. Try search_companies first."}

    page = db.scalar(select(ScrapedPage).where(ScrapedPage.company_id == company.id))
    events = db.scalars(select(Event).where(Event.company_id == company.id)).all()
    return {
        "found": True,
        "id": company.id,
        "name": company.name,
        "ticker": company.ticker,
        "industry": company.industry or (page.industry if page else None),
        "outcome": company.outcome.value,
        "country": page.country if page else None,
        "founded_year": page.founded_year if page else None,
        "shutdown_year": page.shutdown_year if page else None,
        "funding_usd": page.funding_usd if page else None,
        "cause": page.cause if page else None,
        "description": (page.description if page else None) or company.notes,
        "source_url": page.url if page else None,
        "field_provenance": (
            {"from_page_rules": page.rule_fields, "from_ai": page.ai_fields} if page else None
        ),
        "events": [
            {
                "type": e.type.value,
                "roi_percent": e.roi_percent,
                "from": e.timeframe_start,
                "to": e.timeframe_end,
                "summary": e.summary,
                "confidence": e.confidence_score,
            }
            for e in events
        ],
    }


def _industry_breakdown(db: Session, top: int = 15, **_: Any) -> dict:
    """Grouped counts - answers 'which sectors fail most' without dumping rows."""
    pages = db.scalars(select(ScrapedPage)).all()
    by_industry: dict[str, dict] = {}
    by_country: dict[str, int] = {}
    by_year: dict[int, int] = {}
    for page in pages:
        key = (page.industry or "unstated").strip().lower()
        bucket = by_industry.setdefault(key, {"count": 0, "funding_usd": 0.0, "with_cause": 0})
        bucket["count"] += 1
        bucket["funding_usd"] += page.funding_usd or 0
        if page.cause:
            bucket["with_cause"] += 1
        if page.country:
            by_country[page.country] = by_country.get(page.country, 0) + 1
        if page.shutdown_year:
            by_year[page.shutdown_year] = by_year.get(page.shutdown_year, 0) + 1

    ranked = sorted(by_industry.items(), key=lambda kv: kv[1]["count"], reverse=True)
    return {
        "total_businesses": len(pages),
        "by_industry": [{"industry": k, **v} for k, v in ranked[:top]],
        "by_country": dict(sorted(by_country.items(), key=lambda kv: -kv[1])[:top]),
        "by_shutdown_year": dict(sorted(by_year.items())),
        "note": "'unstated' means the source page never named an industry, not that it is unknown to research.",
    }


def _training_stats(db: Session, **_: Any) -> dict:
    from app.training import builder

    examples, report = builder.build_examples(db, None)
    return {
        "total_examples": report.total,
        "by_type": {
            "company_outcome": report.company_outcome,
            "market_vs_finances": report.market_vs_finances,
            "trading_setup": report.trading_setup,
            "business_failure": report.business_failure,
        },
        "skipped": len(report.skipped),
        "skip_reasons": report.skipped[:10],
        "note": (
            "A subject is only counted as skipped when it produced no example of "
            "any type. Most scraped companies fail company_outcome (no ticker, so "
            "no financials or prices) while succeeding as business_failure."
        ),
    }


def _market_data(db: Session, ticker: str | None = None, **_: Any) -> dict:
    if not ticker:
        rows = db.scalars(select(Instrument)).all()
        return {
            "instruments": [
                {"ticker": i.ticker, "name": i.name, "sector": i.sector, "market_cap": i.market_cap}
                for i in rows
            ]
        }

    instrument = db.scalar(select(Instrument).where(Instrument.ticker == ticker.upper()))
    if instrument is None:
        return {"found": False, "reason": f"{ticker} is not synced. Sync it on the Market tab first."}

    bars = db.scalars(
        select(PriceBar).where(PriceBar.instrument_id == instrument.id).order_by(PriceBar.day)
    ).all()
    financials = db.scalars(
        select(Financial)
        .where(Financial.instrument_id == instrument.id, Financial.form == "10-K")
        .order_by(Financial.period_end)
    ).all()

    latest: dict[str, dict] = {}
    for row in financials:
        latest.setdefault(row.period_end, {})[row.metric] = row.value

    return {
        "found": True,
        "ticker": instrument.ticker,
        "name": instrument.name,
        "sector": instrument.sector,
        "market_cap": instrument.market_cap,
        "cik": instrument.cik,
        "price_bars": len(bars),
        "first_bar": bars[0].day.isoformat() if bars else None,
        "last_bar": bars[-1].day.isoformat() if bars else None,
        "last_close": bars[-1].close if bars else None,
        "financial_rows": len(financials),
        "filed_by_period": {p: latest[p] for p in sorted(latest)[-5:]},
        "note": "Financials are as filed with the SEC. Prices are Yahoo daily bars.",
    }


def _list_videos(db: Session, limit: int = 20, **_: Any) -> dict:
    rows = db.scalars(
        select(Source).where(Source.type == SourceType.youtube).order_by(Source.id.desc())
    ).all()
    return {
        "total": len(rows),
        "videos": [
            {
                "id": s.id,
                "title": s.title,
                "channel": s.channel,
                "published": s.published_at,
                "status": s.status.value,
                "classified_as": s.content_kind.value if s.content_kind else None,
                "error": s.error,
                "url": s.url,
            }
            for s in rows[: min(limit, MAX_ROWS)]
        ],
        "note": (
            "classified_as is 'other' for every video until extraction is enabled - "
            "the null provider cannot classify, it only records a placeholder."
        ),
    }


def _recent_activity(db: Session, limit: int = 10, **_: Any) -> dict:
    scrapes = db.scalars(select(ScrapeJob).order_by(ScrapeJob.id.desc()).limit(limit)).all()
    discoveries = db.scalars(select(DiscoveryJob).order_by(DiscoveryJob.id.desc()).limit(limit)).all()
    sites = db.scalars(select(ScrapeSite)).all()
    return {
        "sites_available": [{"key": s.key, "name": s.name, "enabled": s.enabled} for s in sites],
        "scrape_jobs": [
            {
                "id": j.id,
                "status": j.status.value,
                "requested": j.requested,
                "saved": j.saved,
                "skipped": j.skipped,
                "failed": j.failed,
                "filters": j.filters,
            }
            for j in scrapes
        ],
        "discovery_jobs": [
            {
                "id": j.id,
                "status": j.status.value,
                "topics": j.topics,
                "found": j.found,
                "rejected": j.rejected,
                "queued": j.queued,
                "ingested": j.ingested,
                "reject_reasons": j.reject_reasons,
            }
            for j in discoveries
        ],
    }


TOOLS: list[dict] = [
    {
        "name": "get_overview",
        "description": (
            "Counts across the whole dataset: businesses, videos, instruments, "
            "training setups, and whether AI extraction is switched on. Call this "
            "first for any 'how much data do we have' or 'what state is this in' "
            "question, and before making any claim about totals."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "search_companies",
        "description": (
            "Find failed businesses by free text, industry, country, funding, or "
            "shutdown year. Use when the user names a company or asks for a slice "
            "('fintech failures', 'ones that raised over $100M'). Returns the total "
            "match count alongside a capped sample."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Free text over name, description and cause"},
                "industry": {"type": "string"},
                "country": {"type": "string"},
                "outcome": {"type": "string", "enum": ["success", "failure", "unknown"]},
                "min_funding_usd": {"type": "number"},
                "shutdown_year_min": {"type": "integer"},
                "shutdown_year_max": {"type": "integer"},
                "limit": {"type": "integer", "description": "Max rows, capped at 40"},
            },
        },
    },
    {
        "name": "get_company",
        "description": (
            "Everything stored about one company: cause of failure, funding, dates, "
            "events, and which fields came from page rules versus an AI pass. Use "
            "after search_companies, or when the user names a company directly."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "company_id": {"type": "integer"},
            },
        },
    },
    {
        "name": "industry_breakdown",
        "description": (
            "Grouped counts by industry, country and shutdown year across all "
            "scraped businesses. Use for 'what patterns are in this data', 'which "
            "sector fails most', or any question needing aggregates rather than rows."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"top": {"type": "integer", "description": "How many groups to return"}},
        },
    },
    {
        "name": "get_training_stats",
        "description": (
            "The training corpus: example counts by type, how many subjects were "
            "skipped, and why. Use for questions about the .jsonl export, what the "
            "model would be trained on, or why a record is missing."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_market_data",
        "description": (
            "Filed SEC financials and stored price history for a synced ticker. "
            "Omit ticker to list which tickers are synced. Use for any question "
            "about stock prices, revenue, or how the market compares to filings."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"ticker": {"type": "string", "description": "e.g. AAPL"}},
        },
    },
    {
        "name": "list_videos",
        "description": (
            "YouTube sources with channel, status, and how each was classified. "
            "Use for questions about video coverage, failed ingests, or which "
            "channels the corpus draws on."
        ),
        "input_schema": {"type": "object", "properties": {"limit": {"type": "integer"}}},
    },
    {
        "name": "get_recent_activity",
        "description": (
            "Recent scrape and discovery jobs with their filters and outcomes, plus "
            "the sites available to scrape. Use for 'what happened recently', 'why "
            "did that run find so little', or debugging a job."
        ),
        "input_schema": {"type": "object", "properties": {"limit": {"type": "integer"}}},
    },
]

EXECUTORS: dict[str, Callable[..., dict]] = {
    "get_overview": _overview,
    "search_companies": _search_companies,
    "get_company": _get_company,
    "industry_breakdown": _industry_breakdown,
    "get_training_stats": _training_stats,
    "get_market_data": _market_data,
    "list_videos": _list_videos,
    "get_recent_activity": _recent_activity,
}


def run_tool(db: Session, name: str, payload: dict) -> str:
    """Execute one tool. Errors come back as text so the model can recover."""
    executor = EXECUTORS.get(name)
    if executor is None:
        return json.dumps({"error": f"Unknown tool {name!r}"})
    try:
        return json.dumps(executor(db, **(payload or {})), default=str)
    except Exception as exc:  # a tool failure must not end the conversation
        return json.dumps({"error": f"{type(exc).__name__}: {exc}"})
