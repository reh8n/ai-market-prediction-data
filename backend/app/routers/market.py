from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal, get_db
from app.market import financials as fin
from app.market import prices as px
from app.market import sync as market_sync
from app.market import tickers
from app.models import Financial, Instrument, PriceBar
from app.schemas import (
    FinancialOut,
    InstrumentDetail,
    InstrumentOut,
    PriceBarOut,
    TickerSyncRequest,
)

router = APIRouter(prefix="/market", tags=["market"])


def _sync_task(ticker: str, period: str | None) -> None:
    db = SessionLocal()
    try:
        market_sync.sync_all(db, ticker, period)
    finally:
        db.close()


@router.get("/instruments", response_model=list[InstrumentOut])
def list_instruments(db: Session = Depends(get_db)):
    return db.scalars(select(Instrument).order_by(Instrument.ticker)).all()


@router.post("/instruments", response_model=InstrumentOut, status_code=202)
def sync_instrument(
    payload: TickerSyncRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Pull quote, daily bars and SEC financials for a ticker."""
    symbol = payload.ticker.strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="Ticker is required")

    instrument = market_sync.get_or_create_instrument(db, symbol)
    background_tasks.add_task(_sync_task, symbol, payload.period)
    return instrument


@router.get("/search")
def search_tickers(q: str = Query(..., min_length=1), limit: int = 20):
    """Look up tickers in the SEC company list."""
    query = q.strip().lower()
    results = []
    for record in tickers.load_ticker_map().values():
        if query in record.ticker.lower() or query in record.title.lower():
            results.append(
                {"ticker": record.ticker, "cik": record.cik, "name": record.title}
            )
        if len(results) >= limit:
            break
    return {"query": q, "results": results}


@router.get("/instruments/{ticker}", response_model=InstrumentDetail)
def get_instrument(
    ticker: str, bars: int = Query(120, le=5000), db: Session = Depends(get_db)
):
    symbol = ticker.strip().upper()
    instrument = db.scalar(select(Instrument).where(Instrument.ticker == symbol))
    if instrument is None:
        raise HTTPException(status_code=404, detail=f"{symbol} has not been synced")

    recent = db.scalars(
        select(PriceBar)
        .where(PriceBar.instrument_id == instrument.id)
        .order_by(PriceBar.day.desc())
        .limit(bars)
    ).all()
    recent = list(reversed(recent))

    rows = db.scalars(
        select(Financial)
        .where(Financial.instrument_id == instrument.id, Financial.form == "10-K")
        .order_by(Financial.period_end.desc())
    ).all()

    detail = InstrumentDetail.model_validate(instrument)
    detail.bars = [PriceBarOut.model_validate(b) for b in recent]
    detail.financials = [FinancialOut.model_validate(f) for f in rows]

    series = [
        px.Bar(
            day=b.day, open=b.open, high=b.high, low=b.low, close=b.close, volume=b.volume
        )
        for b in recent
    ]
    detail.return_1m = px.trailing_return(series, 21)
    detail.return_3m = px.trailing_return(series, 63)
    detail.return_1y = px.trailing_return(series, 252)
    detail.volatility = px.realized_volatility(series)

    # Latest annual period with derived ratios, for the market-vs-finances view.
    table: dict[str, dict[str, float]] = {}
    for row in rows:
        table.setdefault(row.period_end, {})[row.metric] = row.value
    if table:
        latest = max(table)
        detail.latest_period = latest
        detail.latest_metrics = table[latest]
        detail.latest_ratios = fin.derive_ratios(table[latest])
        revenue_series = [
            (p, table[p]["revenue"]) for p in sorted(table) if "revenue" in table[p]
        ]
        detail.revenue_growth = fin.growth(revenue_series)

    return detail
