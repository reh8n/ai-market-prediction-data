"""The endpoint the prediction model pulls from."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import Company, Outcome, Source, utcnow
from app.schemas import ExportCompany, ExportEvent, ExportResponse

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/data", response_model=ExportResponse)
def export_data(
    outcome: Outcome | None = Query(None, description="Filter by company outcome"),
    min_roi: float | None = Query(None, description="Only events with ROI >= this"),
    company_id: int | None = Query(None),
    limit: int = Query(500, le=5000),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    stmt = (
        select(Company)
        .options(selectinload(Company.events))
        .order_by(Company.id)
        .limit(limit)
        .offset(offset)
    )
    if outcome is not None:
        stmt = stmt.where(Company.outcome == outcome)
    if company_id is not None:
        stmt = stmt.where(Company.id == company_id)

    companies = db.scalars(stmt).all()

    # One lookup for every source referenced, instead of one per event.
    source_ids = {e.source_id for c in companies for e in c.events if e.source_id}
    source_urls = (
        {
            s.id: s.url
            for s in db.scalars(select(Source).where(Source.id.in_(source_ids))).all()
        }
        if source_ids
        else {}
    )

    payload = []
    for company in companies:
        events = [
            ExportEvent(
                event_id=event.id,
                type=event.type,
                roi_percent=event.roi_percent,
                timeframe_start=event.timeframe_start,
                timeframe_end=event.timeframe_end,
                summary=event.summary,
                confidence_score=event.confidence_score,
                source_url=source_urls.get(event.source_id),
            )
            for event in company.events
            if min_roi is None
            or (event.roi_percent is not None and event.roi_percent >= min_roi)
        ]
        if min_roi is not None and not events:
            continue
        payload.append(
            ExportCompany(
                company_id=company.id,
                name=company.name,
                ticker=company.ticker,
                industry=company.industry,
                outcome=company.outcome,
                events=events,
            )
        )

    return ExportResponse(
        generated_at=utcnow(), count=len(payload), companies=payload
    )
