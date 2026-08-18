"""Auto-discovery of YouTube videos.

The manual path is `POST /sources/youtube` with a URL you already found. This
router is the automatic one: give it a subject, it finds the videos itself.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import DiscoveryJob, JobStatus, Source, SourceType
from app.pipeline import discovery
from app.pipeline.discover_run import run_discovery_job
from app.schemas import (
    DiscoverCandidate,
    DiscoverPreviewRequest,
    DiscoverPreviewResponse,
    DiscoverRunRequest,
    DiscoveryJobOut,
    TopicOut,
)

router = APIRouter(prefix="/discover", tags=["discover"])


def _filters(payload: DiscoverRunRequest) -> discovery.Filters:
    return discovery.Filters(
        per_query=payload.per_query,
        min_views=payload.min_views,
        min_duration_seconds=payload.min_duration_seconds,
        max_duration_seconds=payload.max_duration_seconds,
        require_captions=payload.require_captions,
        title_must_match=payload.title_must_match,
        limit=payload.limit,
    )


def _as_candidate(item: discovery.Candidate) -> DiscoverCandidate:
    return DiscoverCandidate(
        video_id=item.video_id,
        url=item.url,
        title=item.title,
        channel=item.channel,
        duration_seconds=item.duration_seconds,
        view_count=item.view_count,
        query=item.query,
        reject_reason=item.reject_reason,
    )


@router.get("/topics", response_model=list[TopicOut])
def topics():
    """Curated subjects, so an operator picks a theme rather than query strings."""
    return [
        TopicOut(key=key, label=t["label"], blurb=t["blurb"], queries=t["queries"])
        for key, t in discovery.TOPICS.items()
    ]


@router.post("/preview", response_model=DiscoverPreviewResponse)
def preview(payload: DiscoverPreviewRequest, db: Session = Depends(get_db)):
    """Run the search and show what would be kept. Saves nothing.

    Caption checking is skipped here: it is the slow step and this endpoint is
    meant to answer "are my filters sane?" in a couple of seconds.
    """
    terms = discovery.terms_for(payload.topics, payload.terms)
    if not terms:
        raise HTTPException(status_code=400, detail="Pick a topic or enter a search term")

    known = {
        row[0]
        for row in db.execute(
            select(Source.external_id).where(
                Source.type == SourceType.youtube, Source.external_id.isnot(None)
            )
        ).all()
    }
    result = discovery.discover(
        terms, filters=_filters(payload), known_ids=known, caption_check=False
    )

    reasons: dict[str, int] = {}
    for item in result.rejected:
        key = item.reject_reason or "unknown"
        reasons[key] = reasons.get(key, 0) + 1

    return DiscoverPreviewResponse(
        searched=result.searched,
        kept=[_as_candidate(c) for c in result.candidates],
        rejected=[_as_candidate(c) for c in result.rejected[:50]],
        reject_reasons=reasons,
        errors=result.errors,
    )


@router.post("/run", response_model=DiscoveryJobOut, status_code=202)
def run(
    payload: DiscoverRunRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Find videos and queue them. Returns immediately; poll the job."""
    terms = discovery.terms_for(payload.topics, payload.terms)
    if not terms:
        raise HTTPException(status_code=400, detail="Pick a topic or enter a search term")

    job = DiscoveryJob(
        topics=payload.topics,
        terms=terms,
        filters={**_filters(payload).as_dict(), "auto_ingest": payload.auto_ingest},
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(run_discovery_job, job.id, payload.auto_ingest)
    return job


@router.get("/jobs", response_model=list[DiscoveryJobOut])
def list_jobs(limit: int = 20, db: Session = Depends(get_db)):
    return db.scalars(
        select(DiscoveryJob).order_by(desc(DiscoveryJob.started_at)).limit(limit)
    ).all()


@router.get("/jobs/{job_id}", response_model=DiscoveryJobOut)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(DiscoveryJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    videos = db.scalars(select(Source).where(Source.type == SourceType.youtube)).all()
    running = db.scalars(
        select(DiscoveryJob).where(
            DiscoveryJob.status.in_([JobStatus.pending, JobStatus.processing])
        )
    ).all()
    return {
        "videos": len(videos),
        "transcribed": sum(1 for v in videos if v.status == JobStatus.done),
        "failed": sum(1 for v in videos if v.status == JobStatus.failed),
        "channels": len({v.channel for v in videos if v.channel}),
        "jobs_running": len(running),
    }
