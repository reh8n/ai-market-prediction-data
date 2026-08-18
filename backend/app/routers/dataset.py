"""The endpoint an external model pulls from.

One stable, paginated, filterable door onto everything collected, plus a
self-describing manifest so a consumer can discover the shape without reading
this source.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import (
    Company,
    Event,
    Instrument,
    Outcome,
    ScrapedPage,
    Source,
    TradingSetup,
    utcnow,
)
from app.training import builder

router = APIRouter(prefix="/dataset", tags=["dataset"])

VERSION = "1.0"


@router.get("/manifest")
def manifest(db: Session = Depends(get_db)):
    """What is in here and how to fetch it. Start here."""
    counts = {
        "companies": db.scalar(select(func.count()).select_from(Company)) or 0,
        "events": db.scalar(select(func.count()).select_from(Event)) or 0,
        "scraped_pages": db.scalar(select(func.count()).select_from(ScrapedPage)) or 0,
        "video_sources": db.scalar(select(func.count()).select_from(Source)) or 0,
        "trading_setups": db.scalar(select(func.count()).select_from(TradingSetup)) or 0,
        "instruments": db.scalar(select(func.count()).select_from(Instrument)) or 0,
    }
    return {
        "version": VERSION,
        "generated_at": utcnow(),
        "counts": counts,
        "endpoints": {
            "records": {
                "path": "/dataset/records",
                "description": "Paginated business records with cause of failure, "
                "funding, financials and price returns where known.",
                "filters": [
                    "outcome", "industry", "country", "year_min", "year_max",
                    "funding_min", "funding_max", "has_cause", "source",
                ],
                "paging": "limit (max 500) and offset; `total` and `next_offset` returned",
            },
            "training_jsonl": {
                "path": "/training/export.jsonl",
                "description": "Fine-tuning file, one JSON object per line with "
                "system/user/assistant turns.",
                "filters": ["kinds", "include_metadata"],
            },
            "setups": {
                "path": "/dataset/setups",
                "description": "Trading setups extracted from tutorial videos.",
            },
        },
        "provenance": {
            "failed_businesses": "scraped from public startup post-mortem sites",
            "video_commentary": "YouTube captions",
            "financials": "SEC EDGAR XBRL company facts",
            "prices": "Yahoo Finance daily bars",
        },
        "notes": [
            "Fields are null when a source did not state them; nulls are never guessed.",
            "`field_sources` shows which values came from page rules vs an AI pass.",
        ],
    }


def _collect_records(
    db: Session,
    outcome: Outcome | None = None,
    industry: str | None = None,
    country: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    funding_min: float | None = None,
    funding_max: float | None = None,
    has_cause: bool | None = None,
    source: str | None = None,
) -> list[dict]:
    """Plain function so other endpoints can reuse it.

    Deliberately not the route handler: calling a FastAPI route directly leaves
    `Query(...)` objects as the defaults, and those are truthy, which silently
    filters everything out.
    """
    stmt = (
        select(Company)
        .options(selectinload(Company.events), selectinload(Company.instrument))
        .order_by(Company.id)
    )
    if outcome is not None:
        stmt = stmt.where(Company.outcome == outcome)
    if industry:
        stmt = stmt.where(Company.industry.ilike(f"%{industry}%"))

    companies = db.scalars(stmt).all()

    # Scraped detail keyed by company, for the fields that only exist there.
    pages = {
        page.company_id: page
        for page in db.scalars(select(ScrapedPage).where(ScrapedPage.company_id.isnot(None))).all()
    }

    rows: list[dict] = []
    for company in companies:
        page = pages.get(company.id)

        if country and not (page and page.country and country.lower() in page.country.lower()):
            continue
        shutdown = page.shutdown_year if page else None
        if year_min and (shutdown or 0) < year_min:
            continue
        if year_max and (shutdown or 9999) > year_max:
            continue
        funding = page.funding_usd if page else None
        if funding_min and (funding or 0) < funding_min:
            continue
        if funding_max and (funding or 0) > funding_max:
            continue

        cause = page.cause if page else None
        if not cause:
            cause = next(
                (e.summary for e in company.events if e.summary and e.type == Outcome.failure),
                None,
            )
        if has_cause and not cause:
            continue

        origin = "scraped" if page else "video"
        if source and source != origin:
            continue

        instrument = company.instrument
        rows.append(
            {
                "company_id": company.id,
                "name": company.name,
                "ticker": company.ticker,
                "industry": company.industry or (page.industry if page else None),
                "country": page.country if page else None,
                "outcome": company.outcome.value,
                "founded_year": page.founded_year if page else None,
                "shutdown_year": shutdown,
                "funding_usd": funding,
                "cause_of_failure": cause,
                "description": (page.description if page else None) or company.notes,
                "events": [
                    {
                        "type": e.type.value,
                        "roi_percent": e.roi_percent,
                        "timeframe_start": e.timeframe_start,
                        "timeframe_end": e.timeframe_end,
                        "summary": e.summary,
                        "confidence": e.confidence_score,
                    }
                    for e in company.events
                ],
                "market": (
                    {
                        "ticker": instrument.ticker,
                        "sector": instrument.sector,
                        "market_cap": instrument.market_cap,
                        "cik": instrument.cik,
                    }
                    if instrument
                    else None
                ),
                "origin": origin,
                "source_url": page.url if page else None,
                "field_sources": (
                    {"rules": page.rule_fields, "ai": page.ai_fields} if page else None
                ),
            }
        )

    return rows


@router.get("/records")
def records(
    outcome: Outcome | None = None,
    industry: str | None = None,
    country: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    funding_min: float | None = None,
    funding_max: float | None = None,
    has_cause: bool | None = Query(None, description="Only records with a stated cause"),
    source: str | None = Query(None, description="'scraped' or 'video'"),
    limit: int = Query(100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """Business records, joined across every source. Built for machine consumption."""
    rows = _collect_records(
        db,
        outcome=outcome,
        industry=industry,
        country=country,
        year_min=year_min,
        year_max=year_max,
        funding_min=funding_min,
        funding_max=funding_max,
        has_cause=has_cause,
        source=source,
    )
    total = len(rows)
    window = rows[offset : offset + limit]
    return {
        "version": VERSION,
        "generated_at": utcnow(),
        "total": total,
        "count": len(window),
        "offset": offset,
        "limit": limit,
        "next_offset": offset + limit if offset + limit < total else None,
        "records": window,
    }


@router.get("/setups")
def setups(limit: int = Query(200, le=1000), offset: int = 0, db: Session = Depends(get_db)):
    rows = db.scalars(select(TradingSetup).order_by(TradingSetup.id)).all()
    window = rows[offset : offset + limit]
    return {
        "version": VERSION,
        "total": len(rows),
        "count": len(window),
        "next_offset": offset + limit if offset + limit < len(rows) else None,
        "setups": [
            {
                "id": s.id,
                "name": s.name,
                "market": s.market,
                "instrument": s.instrument_hint,
                "timeframe": s.timeframe,
                "direction": s.direction,
                "trigger": s.trigger,
                "entry_rule": s.entry_rule,
                "stop_rule": s.stop_rule,
                "target_rule": s.target_rule,
                "risk_rule": s.risk_rule,
                "invalidation": s.invalidation,
                "confidence": s.confidence_score,
                "source_id": s.source_id,
            }
            for s in window
        ],
    }


@router.get("/records.jsonl", response_class=PlainTextResponse)
def records_jsonl(
    outcome: Outcome | None = None,
    industry: str | None = None,
    country: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    funding_min: float | None = None,
    has_cause: bool | None = None,
    source: str | None = None,
    db: Session = Depends(get_db),
):
    """Same records, one JSON object per line, for streaming into a data pipeline."""
    import json

    rows = _collect_records(
        db,
        outcome=outcome,
        industry=industry,
        country=country,
        year_min=year_min,
        year_max=year_max,
        funding_min=funding_min,
        has_cause=has_cause,
        source=source,
    )
    body = "\n".join(json.dumps(r, default=str, ensure_ascii=False) for r in rows)
    return PlainTextResponse(
        body + ("\n" if body else ""),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": 'attachment; filename="records.jsonl"'},
    )
