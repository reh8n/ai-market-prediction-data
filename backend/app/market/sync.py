"""Persisting market data: instrument, daily bars, filed financials.

Kept separate from the fetch modules so the network shape and the DB shape can
change independently.
"""

from __future__ import annotations

import logging

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.market import financials as fin
from app.market import prices as px
from app.market import tickers
from app.models import Company, Financial, Instrument, PriceBar, utcnow

logger = logging.getLogger(__name__)
settings = get_settings()


def get_or_create_instrument(db: Session, ticker: str) -> Instrument:
    symbol = ticker.strip().upper()
    instrument = db.scalar(select(Instrument).where(Instrument.ticker == symbol))
    if instrument is not None:
        return instrument

    record = tickers.lookup_ticker(symbol)
    instrument = Instrument(
        ticker=symbol,
        cik=record.cik if record else None,
        name=record.title if record else None,
    )
    db.add(instrument)
    db.commit()
    db.refresh(instrument)
    return instrument


def sync_prices(db: Session, instrument: Instrument, period: str | None = None) -> int:
    """Replace stored bars for an instrument. Returns the row count."""
    bars = px.fetch_daily_bars(
        instrument.ticker, period=period or settings.price_history_period
    )

    db.execute(delete(PriceBar).where(PriceBar.instrument_id == instrument.id))
    db.add_all(
        PriceBar(
            instrument_id=instrument.id,
            day=bar.day,
            open=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            volume=bar.volume,
        )
        for bar in bars
    )
    instrument.prices_synced_at = utcnow()
    db.commit()
    return len(bars)


def sync_quote(db: Session, instrument: Instrument) -> None:
    quote = px.fetch_quote(instrument.ticker)
    instrument.name = quote.name or instrument.name
    instrument.sector = quote.sector
    instrument.industry = quote.industry
    instrument.exchange = quote.exchange
    instrument.currency = quote.currency
    instrument.market_cap = quote.market_cap
    db.commit()


def sync_financials(db: Session, instrument: Instrument) -> int:
    """Replace stored financials from SEC filings. Returns the row count."""
    if instrument.cik is None:
        record = tickers.lookup_ticker(instrument.ticker)
        if record is None:
            raise fin.FinancialsError(
                f"{instrument.ticker} is not in the SEC ticker list "
                "(non-US listing, ETF, or index)."
            )
        instrument.cik = record.cik
        db.commit()

    facts = fin.fetch_financials(instrument.cik, annual_only=False)

    db.execute(delete(Financial).where(Financial.instrument_id == instrument.id))
    # The API can repeat a (metric, period, form) triple across amended
    # filings; the unique constraint rejects duplicates, so dedupe here.
    seen: set[tuple[str, str, str | None]] = set()
    rows = []
    for fact in facts:
        key = (fact.metric, fact.period_end, fact.form)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            Financial(
                instrument_id=instrument.id,
                metric=fact.metric,
                concept=fact.concept,
                value=fact.value,
                unit=fact.unit,
                period_end=fact.period_end,
                fiscal_year=fact.fiscal_year,
                fiscal_period=fact.fiscal_period,
                form=fact.form,
                filed=fact.filed,
            )
        )
    db.add_all(rows)
    instrument.financials_synced_at = utcnow()
    db.commit()
    return len(rows)


def sync_all(db: Session, ticker: str, period: str | None = None) -> dict:
    """Full sync for one ticker. Partial success is reported, not raised."""
    instrument = get_or_create_instrument(db, ticker)
    report: dict = {"ticker": instrument.ticker, "instrument_id": instrument.id}
    errors: list[str] = []

    try:
        sync_quote(db, instrument)
        report["quote"] = "ok"
    except Exception as exc:
        errors.append(f"quote: {exc}")
        report["quote"] = "failed"

    try:
        report["price_bars"] = sync_prices(db, instrument, period)
    except Exception as exc:
        errors.append(f"prices: {exc}")
        report["price_bars"] = 0

    try:
        report["financial_rows"] = sync_financials(db, instrument)
    except Exception as exc:
        errors.append(f"financials: {exc}")
        report["financial_rows"] = 0

    instrument.sync_error = " | ".join(errors) if errors else None
    db.commit()
    report["errors"] = errors
    return report


def link_company(db: Session, company: Company) -> Instrument | None:
    """Attach a listed instrument to a company, if one can be identified.

    Resolution is conservative on purpose - a wrong ticker would silently
    attach another company's financials to this company's training rows.
    """
    record = None
    if company.ticker:
        record = tickers.lookup_ticker(company.ticker)
    if record is None:
        record = tickers.resolve_company(company.name)
    if record is None:
        return None

    instrument = get_or_create_instrument(db, record.ticker)

    # First link triggers the data pull; later links reuse what is stored.
    if instrument.prices_synced_at is None:
        try:
            sync_quote(db, instrument)
            sync_prices(db, instrument)
        except Exception as exc:
            logger.warning("Price sync failed for %s: %s", instrument.ticker, exc)
    if instrument.financials_synced_at is None:
        try:
            sync_financials(db, instrument)
        except Exception as exc:
            logger.warning("Financial sync failed for %s: %s", instrument.ticker, exc)

    return instrument
