from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Company, Outcome
from app.schemas import CompanyCreate, CompanyDetail, CompanyOut

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", response_model=list[CompanyOut])
def list_companies(
    outcome: Outcome | None = Query(None),
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    stmt = select(Company).order_by(Company.created_at.desc())
    if outcome is not None:
        stmt = stmt.where(Company.outcome == outcome)
    return db.scalars(stmt.limit(limit).offset(offset)).all()


@router.post("", response_model=CompanyOut, status_code=201)
def create_company(payload: CompanyCreate, db: Session = Depends(get_db)):
    company = Company(**payload.model_dump())
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


@router.get("/{company_id}", response_model=CompanyDetail)
def get_company(company_id: int, db: Session = Depends(get_db)):
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return company
