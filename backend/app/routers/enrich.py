"""Backfill AI extraction over data collected before a key was configured."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import EnrichJob, Extraction, JobStatus, ScrapedPage, TradingSetup
from app.pipeline import enrich_run
from app.pipeline.extractor import NullExtractor, get_extractor

router = APIRouter(prefix="/enrich", tags=["enrich"])

settings = get_settings()


@router.get("/status")
def status(
    db: Session = Depends(get_db),
    # A header, not a query parameter: query strings land in access logs,
    # proxy logs and browser history. A key must not.
    api_key: str | None = Header(None, alias="X-Extraction-Key"),
):
    """What extraction is configured, and what turning it on would gain.

    Answerable with no key set - the point is to show the cost of the gap
    before asking anyone to pay for it.
    """
    configured = False
    detail = ""
    try:
        extractor = get_extractor(api_key)
        configured = not isinstance(extractor, NullExtractor)
        if not configured:
            detail = "EXTRACTION_PROVIDER is 'null' - extraction is off."
    except Exception as exc:
        detail = str(exc)

    pages = enrich_run.page_candidates(db)
    field_gaps: dict[str, int] = {}
    for page in pages:
        for name in enrich_run.missing_fields(page):
            field_gaps[name] = field_gaps.get(name, 0) + 1

    return {
        "configured": configured,
        "provider": settings.extraction_provider,
        "model": settings.extraction_model or None,
        "detail": detail,
        "pages_total": db.query(ScrapedPage).count(),
        "pages_missing_fields": len(pages),
        "field_gaps": field_gaps,
        "sources_awaiting_extraction": len(enrich_run.source_candidates(db)),
        "extractions": db.query(Extraction).count(),
        "trading_setups": db.query(TradingSetup).count(),
        "note": (
            "Extraction runs inline during a scrape or ingest, so a key set "
            "later does not touch existing records. Run a backfill to catch up."
        ),
    }


@router.post("/run", status_code=202)
def run(
    background_tasks: BackgroundTasks,
    target: str = Query("pages", pattern="^(pages|sources)$"),
    limit: int | None = Query(None, ge=1, description="Cap records this pass"),
    db: Session = Depends(get_db),
    api_key: str | None = Header(None, alias="X-Extraction-Key"),
):
    """Start a backfill. Returns immediately; poll the job."""
    try:
        enrich_run._require_extractor(api_key)
    except enrich_run.NoExtractor as exc:
        # Refuse up front rather than queueing a job that cannot do anything.
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    job = EnrichJob(target=target)
    db.add(job)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(enrich_run.run_enrich_job, job.id, limit, api_key)
    return _job_out(job)


@router.get("/jobs")
def list_jobs(limit: int = 20, db: Session = Depends(get_db)):
    jobs = db.scalars(
        select(EnrichJob).order_by(desc(EnrichJob.started_at)).limit(limit)
    ).all()
    return [_job_out(j) for j in jobs]


@router.get("/jobs/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(EnrichJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_out(job)


def _job_out(job: EnrichJob) -> dict:
    return {
        "id": job.id,
        "target": job.target,
        "status": job.status.value if isinstance(job.status, JobStatus) else job.status,
        "candidates": job.candidates,
        "processed": job.processed,
        "updated": job.updated,
        "unchanged": job.unchanged,
        "failed": job.failed,
        "fields_filled": job.fields_filled or {},
        "error": job.error,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
    }
