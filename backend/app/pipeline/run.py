"""Orchestration: scrape -> transcribe -> classify -> extract -> link -> persist.

Runs on a BackgroundTasks worker thread, so it opens its own DB session
rather than reusing the request's.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.market import sync as market_sync
from app.models import (
    Company,
    ContentKind,
    Event,
    Extraction,
    JobStatus,
    Outcome,
    Source,
    TradingSetup,
    Transcript,
    TranscriptMethod,
    utcnow,
)
from app.pipeline import youtube_scraper
from app.pipeline.extractor import get_extractor

logger = logging.getLogger(__name__)


def process_youtube_source(source_id: int) -> None:
    """Full pipeline for one YouTube source. Never raises - records failures."""
    db = SessionLocal()
    try:
        source = db.get(Source, source_id)
        if source is None:
            logger.error("Source %s disappeared before processing", source_id)
            return

        source.status = JobStatus.processing
        db.commit()

        try:
            result = youtube_scraper.scrape_youtube(source.url)
        except Exception as exc:
            logger.exception("Scrape failed for source %s", source_id)
            source.status = JobStatus.failed
            source.error = str(exc)
            db.commit()
            return

        path = youtube_scraper.write_transcript_file(source.id, result)

        source.external_id = result.video_id
        source.raw_file_path = str(path)
        source.fetched_at = utcnow()
        if result.meta:
            source.title = source.title or result.meta.title
            source.channel = result.meta.channel
            source.published_at = result.meta.published_at

        db.add(
            Transcript(
                source_id=source.id,
                raw_text_path=str(path),
                language=result.language,
                duration_seconds=result.duration_seconds,
                transcript_method=TranscriptMethod(result.method),
                char_count=len(result.text),
            )
        )
        db.commit()

        # Extraction is best-effort: a transcript with no extraction is still
        # useful data, so an extraction failure doesn't fail the whole source.
        try:
            extractor = get_extractor()
            extraction_result = extractor.extract(
                result.text, context=_build_context(source)
            )
        except Exception as exc:
            logger.exception("Extraction failed for source %s", source_id)
            source.status = JobStatus.done
            source.error = f"Transcript saved, extraction failed: {exc}"
            db.commit()
            return

        kind = _to_kind(extraction_result.content_kind)
        source.content_kind = kind

        db.add(
            Extraction(
                source_id=source.id,
                content_kind=kind,
                extracted_json=extraction_result.data,
                summary=extraction_result.summary,
                model_used=extraction_result.model_used,
                provider=extraction_result.provider,
            )
        )

        _persist_companies(db, source, extraction_result.companies)
        _persist_setups(db, source, extraction_result.setups)

        source.status = JobStatus.done
        source.error = None
        db.commit()
        logger.info("Source %s processed as %s", source_id, kind.value)
    finally:
        db.close()


def _to_kind(value: str | None) -> ContentKind:
    try:
        return ContentKind(value)
    except (ValueError, TypeError):
        return ContentKind.other


def _build_context(source: Source) -> str:
    bits = [f"YouTube video: {source.url}"]
    if source.title:
        bits.append(f"Title: {source.title}")
    if source.channel:
        bits.append(f"Channel: {source.channel}")
    if source.published_at:
        bits.append(f"Published: {source.published_at}")
    return " | ".join(bits)


def _persist_companies(db: Session, source: Source, entries: list[dict]) -> None:
    """Upsert companies by name, attach an event, and link a market instrument."""
    for entry in entries:
        name = (entry.get("name") or "").strip()
        if not name:
            continue

        company = db.scalar(select(Company).where(Company.name.ilike(name)))
        if company is None:
            company = Company(
                name=name,
                ticker=entry.get("ticker"),
                industry=entry.get("industry"),
                outcome=_to_outcome(entry.get("outcome")),
            )
            db.add(company)
            db.flush()  # assign company.id
        else:
            # Fill gaps without overwriting curated values.
            company.ticker = company.ticker or entry.get("ticker")
            company.industry = company.industry or entry.get("industry")
            if company.outcome == Outcome.unknown:
                company.outcome = _to_outcome(entry.get("outcome"))

        # Attach market data when the company is publicly listed. Private
        # companies simply stay unlinked.
        if company.instrument_id is None:
            try:
                instrument = market_sync.link_company(db, company)
                if instrument is not None:
                    company.instrument_id = instrument.id
            except Exception:
                logger.warning("Instrument link failed for %s", name, exc_info=True)

        causes = entry.get("causes") or []
        summary = entry.get("summary") or ""
        if causes:
            summary = f"{summary}\n\nCauses: " + "; ".join(causes)

        db.add(
            Event(
                company_id=company.id,
                type=_to_outcome(entry.get("outcome")),
                roi_percent=entry.get("roi_percent"),
                timeframe_start=entry.get("timeframe_start"),
                timeframe_end=entry.get("timeframe_end"),
                summary=summary.strip(),
                confidence_score=entry.get("confidence"),
                source_id=source.id,
            )
        )

        if source.company_id is None:
            source.company_id = company.id

    db.commit()


def _persist_setups(db: Session, source: Source, entries: list[dict]) -> None:
    for entry in entries:
        name = (entry.get("name") or "").strip()
        if not name:
            continue
        db.add(
            TradingSetup(
                source_id=source.id,
                name=name,
                market=entry.get("market"),
                instrument_hint=entry.get("instrument_hint"),
                timeframe=entry.get("timeframe"),
                direction=entry.get("direction"),
                trigger=entry.get("trigger"),
                entry_rule=entry.get("entry_rule"),
                stop_rule=entry.get("stop_rule"),
                target_rule=entry.get("target_rule"),
                risk_rule=entry.get("risk_rule"),
                invalidation=entry.get("invalidation"),
                confidence_score=entry.get("confidence"),
            )
        )
    db.commit()


def _to_outcome(value: str | None) -> Outcome:
    try:
        return Outcome(value)
    except (ValueError, TypeError):
        return Outcome.unknown
