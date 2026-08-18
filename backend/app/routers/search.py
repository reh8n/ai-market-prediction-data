"""Search across collected data.

Portable ILIKE matching so the same code runs on SQLite and Postgres. The
upgrade path is Postgres `tsvector` (and later `pgvector` for semantic search);
both would slot in behind this same endpoint.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Company, Event, Source
from app.schemas import SearchHit, SearchResponse

router = APIRouter(tags=["search"])


def _snippet(text: str | None, limit: int = 220) -> str | None:
    if not text:
        return None
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit] + "..."


@router.get("/search", response_model=SearchResponse)
def search(
    q: str = Query(..., min_length=1),
    limit: int = 25,
    db: Session = Depends(get_db),
):
    pattern = f"%{q}%"
    hits: list[SearchHit] = []

    companies = db.scalars(
        select(Company)
        .where(
            or_(
                Company.name.ilike(pattern),
                Company.ticker.ilike(pattern),
                Company.industry.ilike(pattern),
                Company.notes.ilike(pattern),
            )
        )
        .limit(limit)
    ).all()
    for company in companies:
        hits.append(
            SearchHit(
                kind="company",
                id=company.id,
                title=company.name,
                snippet=_snippet(company.notes) or company.industry,
                company_id=company.id,
            )
        )

    events = db.scalars(
        select(Event).where(Event.summary.ilike(pattern)).limit(limit)
    ).all()
    for event in events:
        roi = f" (ROI {event.roi_percent}%)" if event.roi_percent is not None else ""
        hits.append(
            SearchHit(
                kind="event",
                id=event.id,
                title=f"{event.type.value}{roi}",
                snippet=_snippet(event.summary),
                company_id=event.company_id,
                source_id=event.source_id,
            )
        )

    sources = db.scalars(
        select(Source)
        .where(or_(Source.title.ilike(pattern), Source.channel.ilike(pattern)))
        .limit(limit)
    ).all()
    for source in sources:
        hits.append(
            SearchHit(
                kind="source",
                id=source.id,
                title=source.title or source.url,
                snippet=source.channel,
                company_id=source.company_id,
                source_id=source.id,
            )
        )

    return SearchResponse(query=q, total=len(hits), hits=hits[:limit])
