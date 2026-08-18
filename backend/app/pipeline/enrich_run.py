"""Backfill: run AI extraction over records that were stored before a key existed.

Extraction normally runs inline during a scrape or a video ingest. That means
setting `EXTRACTION_API_KEY` later changes nothing about data already collected
- the gap this closes.

Scraped pages are re-read from their saved text on disk, never re-fetched. The
sites were already crawled politely once; asking them again for bytes we still
have would be rude and slow.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal
from app.models import (
    EnrichJob,
    Event,
    Extraction,
    JobStatus,
    Outcome,
    ScrapedPage,
    Source,
    SourceType,
    utcnow,
)
from app.pipeline.extractor import NullExtractor, get_extractor
from app.pipeline.run import _build_context, _persist_companies, _persist_setups, _to_kind
from app.pipeline.youtube_scraper import read_transcript_text
from app.scrapers import enrich as enrichment

logger = logging.getLogger(__name__)

# Fields the page enricher can fill, in the order they matter for training.
PAGE_FIELDS = ["cause", "industry", "funding_usd", "shutdown_year", "founded_year", "country"]


class NoExtractor(RuntimeError):
    pass


def _require_extractor(api_key: str | None = None):
    """Fail loudly here rather than silently doing nothing for every record."""
    try:
        extractor = get_extractor(api_key)
    except Exception as exc:
        raise NoExtractor(str(exc)) from exc
    else:
        try:
            extractor.validate()
        except Exception as exc:
            raise NoExtractor(f"That API key was rejected: {exc}") from exc

    if isinstance(extractor, NullExtractor):
        raise NoExtractor(
            "Extraction is off. Either paste a key on the Analyst tab, or set "
            "EXTRACTION_PROVIDER and EXTRACTION_API_KEY in backend/.env and "
            "restart the API."
        )
    return extractor


def _page_text(page: ScrapedPage) -> str:
    if not page.raw_file_path:
        return ""
    path = Path(page.raw_file_path)
    if not path.exists():
        return ""
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("text") or ""
    except (json.JSONDecodeError, OSError):
        return ""


def missing_fields(page: ScrapedPage) -> list[str]:
    return [f for f in PAGE_FIELDS if getattr(page, f, None) in (None, "")]


def page_candidates(db) -> list[ScrapedPage]:
    pages = db.scalars(select(ScrapedPage).order_by(ScrapedPage.id)).all()
    return [p for p in pages if missing_fields(p)]


def source_candidates(db) -> list[Source]:
    """Videos with a transcript but no *real* extraction yet.

    The null provider still writes an Extraction row, so an existence check
    alone reports everything as done. Rows from `provider='null'` are
    placeholders and must not count as extracted.
    """
    sources = db.scalars(
        select(Source).where(
            Source.type == SourceType.youtube,
            Source.status == JobStatus.done,
            Source.raw_file_path.isnot(None),
        )
    ).all()
    done = {
        row[0]
        for row in db.execute(
            select(Extraction.source_id).where(Extraction.provider != "null")
        ).all()
        if row[0]
    }
    return [s for s in sources if s.id not in done]


def run_enrich_job(job_id: int, limit: int | None = None, api_key: str | None = None) -> None:
    """Execute one backfill. Never raises - failures land on the job row."""
    db = SessionLocal()
    try:
        job = db.get(EnrichJob, job_id)
        if job is None:
            logger.error("Enrich job %s vanished", job_id)
            return

        try:
            extractor = _require_extractor(api_key)
        except NoExtractor as exc:
            job.status = JobStatus.failed
            job.error = str(exc)
            job.finished_at = utcnow()
            db.commit()
            return

        job.status = JobStatus.processing
        db.commit()

        if job.target == "pages":
            _enrich_pages(db, job, extractor, limit)
        else:
            _enrich_sources(db, job, extractor, limit)

        job.status = JobStatus.done
        job.finished_at = utcnow()
        db.commit()
        logger.info(
            "Enrich job %s (%s): %s updated of %s processed",
            job_id,
            job.target,
            job.updated,
            job.processed,
        )
    except Exception as exc:
        logger.exception("Enrich job %s crashed", job_id)
        job = db.get(EnrichJob, job_id)
        if job is not None:
            job.status = JobStatus.failed
            job.error = str(exc)
            job.finished_at = utcnow()
            db.commit()
    finally:
        db.close()


def _enrich_pages(db, job: EnrichJob, extractor, limit: int | None) -> None:
    pages = page_candidates(db)
    job.candidates = len(pages)
    db.commit()

    filled: dict[str, int] = dict(job.fields_filled or {})
    for page in pages[:limit] if limit else pages:
        text = _page_text(page)
        if not text:
            job.failed += 1
            db.commit()
            continue

        wanted = missing_fields(page)
        try:
            result = enrichment.enrich(extractor, page.name, text, wanted)
        except Exception:
            logger.exception("Enrichment failed for page %s", page.id)
            job.failed += 1
            db.commit()
            continue

        job.processed += 1
        added: list[str] = []
        for key, value in (result or {}).items():
            if value in (None, "") or getattr(page, key, None) not in (None, ""):
                continue
            setattr(page, key, value)
            added.append(key)

        if added:
            page.ai_fields = list(page.ai_fields or []) + added
            for key in added:
                filled[key] = filled.get(key, 0) + 1
            _refresh_event(db, page)
            job.updated += 1
        else:
            job.unchanged += 1

        job.fields_filled = dict(filled)
        # Commit per record: an AI pass over hundreds of pages is long, and
        # progress must survive an interruption.
        db.commit()


def _refresh_event(db, page: ScrapedPage) -> None:
    """Keep the training-facing Event in step with the enriched page.

    The business_failure builder reads `cause` from the page, but the export
    and search paths read the Event summary - leaving it stale would make the
    same record say two different things.
    """
    if not page.company_id:
        return
    event = db.scalar(
        select(Event).where(Event.company_id == page.company_id, Event.type == Outcome.failure)
    )
    if event is None:
        return

    parts = [page.cause or page.description or ""]
    if page.funding_usd:
        parts.append(f"Raised approximately ${page.funding_usd:,.0f}.")
    if page.country:
        parts.append(f"Based in {page.country}.")
    summary = " ".join(p for p in parts if p).strip()
    if summary:
        event.summary = summary
        event.confidence_score = 0.75  # AI-assisted, so below a rules-only record


def _enrich_sources(db, job: EnrichJob, extractor, limit: int | None) -> None:
    sources = source_candidates(db)
    job.candidates = len(sources)
    db.commit()

    for source in sources[:limit] if limit else sources:
        text = read_transcript_text(source.raw_file_path) if source.raw_file_path else None
        if not text:
            job.failed += 1
            db.commit()
            continue

        try:
            result = extractor.extract(text, context=_build_context(source))
        except Exception as exc:
            logger.exception("Extraction failed for source %s", source.id)
            job.failed += 1
            source.error = f"Backfill extraction failed: {exc}"
            db.commit()
            continue

        job.processed += 1
        kind = _to_kind(result.content_kind)
        source.content_kind = kind
        source.error = None
        db.add(
            Extraction(
                source_id=source.id,
                content_kind=kind,
                extracted_json=result.data,
                summary=result.summary,
                model_used=result.model_used,
                provider=result.provider,
            )
        )
        _persist_companies(db, source, result.companies)
        _persist_setups(db, source, result.setups)
        job.updated += 1
        db.commit()
