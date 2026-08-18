from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Source, SourceType
from app.pipeline.run import process_youtube_source
from app.pipeline.youtube_scraper import ScrapeError, parse_video_id, read_transcript_text
from app.schemas import SourceDetail, SourceOut, YouTubeIngestRequest

router = APIRouter(prefix="/sources", tags=["sources"])


@router.post("/youtube", response_model=SourceOut, status_code=202)
def ingest_youtube(
    payload: YouTubeIngestRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Queue a YouTube video for scraping + extraction. Returns immediately."""
    try:
        video_id = parse_video_id(payload.url)
    except ScrapeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    existing = db.scalar(
        select(Source).where(
            Source.external_id == video_id, Source.type == SourceType.youtube
        )
    )
    if existing is not None:
        return existing

    source = Source(
        type=SourceType.youtube,
        url=f"https://www.youtube.com/watch?v={video_id}",
        external_id=video_id,
        title=payload.company_name,
    )
    db.add(source)
    db.commit()
    db.refresh(source)

    background_tasks.add_task(process_youtube_source, source.id)
    return source


@router.get("", response_model=list[SourceOut])
def list_sources(limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    return db.scalars(
        select(Source).order_by(Source.created_at.desc()).limit(limit).offset(offset)
    ).all()


@router.get("/{source_id}", response_model=SourceDetail)
def get_source(
    source_id: int, include_transcript: bool = False, db: Session = Depends(get_db)
):
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")

    detail = SourceDetail.model_validate(source)
    if include_transcript and source.raw_file_path:
        detail.transcript_text = read_transcript_text(source.raw_file_path)
    return detail
