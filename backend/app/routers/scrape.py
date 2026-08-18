import re

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import JobStatus, ScrapedPage, ScrapeJob, ScrapeSite
from app.schemas import (
    ScrapedPageOut,
    ScrapeJobOut,
    ScrapeRunRequest,
    ScrapeSiteCreate,
    ScrapeSiteOut,
)
from app.scrapers.profiles import generic_profile
from app.scrapers.run import run_scrape_job

router = APIRouter(prefix="/scrape", tags=["scrape"])


@router.get("/sites", response_model=list[ScrapeSiteOut])
def list_sites(db: Session = Depends(get_db)):
    return db.scalars(select(ScrapeSite).order_by(ScrapeSite.name)).all()


@router.post("/sites", response_model=ScrapeSiteOut, status_code=201)
def add_site(payload: ScrapeSiteCreate, db: Session = Depends(get_db)):
    """Register any site. Defaults are guessed from the URL and can be overridden."""
    key = payload.key or re.sub(r"[^a-z0-9]+", "_", payload.name.lower()).strip("_")
    if db.scalar(select(ScrapeSite).where(ScrapeSite.key == key)):
        raise HTTPException(status_code=409, detail=f"Site '{key}' already exists")

    profile = generic_profile(
        key=key,
        name=payload.name,
        base_url=payload.base_url,
        sitemap_url=payload.sitemap_url,
        url_pattern=payload.url_pattern,
        exclude_pattern=payload.exclude_pattern,
    )
    site = ScrapeSite(
        key=profile.key,
        name=profile.name,
        base_url=profile.base_url,
        sitemap_url=profile.sitemap_url,
        url_pattern=profile.url_pattern,
        exclude_pattern=profile.exclude_pattern,
        notes=profile.notes,
        built_in=False,
    )
    db.add(site)
    db.commit()
    db.refresh(site)
    return site


@router.delete("/sites/{site_id}", status_code=204)
def delete_site(site_id: int, db: Session = Depends(get_db)):
    site = db.get(ScrapeSite, site_id)
    if site is None:
        raise HTTPException(status_code=404, detail="Site not found")
    if site.built_in:
        raise HTTPException(status_code=400, detail="Built-in sites cannot be deleted")
    db.delete(site)
    db.commit()


@router.post("/run", response_model=ScrapeJobOut, status_code=202)
def run(
    payload: ScrapeRunRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Start a scrape. Returns immediately; poll the job for progress."""
    site = db.scalar(select(ScrapeSite).where(ScrapeSite.key == payload.site_key))
    if site is None:
        raise HTTPException(status_code=404, detail=f"Unknown site '{payload.site_key}'")
    if not site.enabled:
        raise HTTPException(status_code=400, detail=f"Site '{site.key}' is disabled")

    job = ScrapeJob(
        site_id=site.id,
        requested=payload.limit,
        filters={
            "limit": payload.limit,
            "industry": payload.industry,
            "year_min": payload.year_min,
            "year_max": payload.year_max,
            "funding_min": payload.funding_min,
            "funding_max": payload.funding_max,
            "use_ai": payload.use_ai,
        },
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(run_scrape_job, job.id)
    return job


@router.get("/jobs", response_model=list[ScrapeJobOut])
def list_jobs(limit: int = 20, db: Session = Depends(get_db)):
    return db.scalars(
        select(ScrapeJob).order_by(desc(ScrapeJob.started_at)).limit(limit)
    ).all()


@router.get("/jobs/{job_id}", response_model=ScrapeJobOut)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(ScrapeJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/pages", response_model=list[ScrapedPageOut])
def list_pages(
    site_key: str | None = None,
    industry: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    funding_min: float | None = None,
    limit: int = Query(100, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    stmt = select(ScrapedPage).order_by(desc(ScrapedPage.scraped_at))
    if site_key:
        site = db.scalar(select(ScrapeSite).where(ScrapeSite.key == site_key))
        if site is None:
            raise HTTPException(status_code=404, detail=f"Unknown site '{site_key}'")
        stmt = stmt.where(ScrapedPage.site_id == site.id)
    if industry:
        stmt = stmt.where(ScrapedPage.industry.ilike(f"%{industry}%"))
    if year_min:
        stmt = stmt.where(ScrapedPage.shutdown_year >= year_min)
    if year_max:
        stmt = stmt.where(ScrapedPage.shutdown_year <= year_max)
    if funding_min:
        stmt = stmt.where(ScrapedPage.funding_usd >= funding_min)

    return db.scalars(stmt.limit(limit).offset(offset)).all()


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    pages = db.scalars(select(ScrapedPage)).all()
    running = db.scalars(
        select(ScrapeJob).where(
            ScrapeJob.status.in_([JobStatus.pending, JobStatus.processing])
        )
    ).all()
    with_cause = sum(1 for p in pages if p.cause)
    with_funding = sum(1 for p in pages if p.funding_usd)
    return {
        "pages": len(pages),
        "with_cause": with_cause,
        "with_funding": with_funding,
        "ai_assisted": sum(1 for p in pages if p.ai_fields),
        "jobs_running": len(running),
    }
