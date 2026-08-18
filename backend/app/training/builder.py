"""Turn collected data into fine-tuning examples.

Three example types come out of here:

  company_outcome     filings + price action + commentary -> outcome judgment
  market_vs_finances  filings + price action              -> is the market's
                                                             pricing supported
  trading_setup       taught rules                        -> structured setup

Each row is a `{"messages": [...]}` object, the shape Anthropic, OpenAI and
most open-weight fine-tuners accept.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.market import financials as fin
from app.market import prices as px
from app.models import (
    Company,
    Event,
    Financial,
    Instrument,
    PriceBar,
    ScrapedPage,
    Source,
    TradingSetup,
)
from app.pipeline.youtube_scraper import read_transcript_text

# Keep transcript excerpts bounded so one long video cannot dominate a
# training file or blow a context window.
TRANSCRIPT_EXCERPT_CHARS = 6_000

COMPANY_SYSTEM = (
    "You are a market analyst. Given a company's filed financials, its market "
    "price action, and commentary about it, judge the outcome and explain what "
    "drove it. Ground every claim in the figures provided."
)

MARKET_SYSTEM = (
    "You are a market analyst. Given a company's filed financials and its market "
    "price action over the same period, assess whether the price move is "
    "supported by the fundamentals."
)

SETUP_SYSTEM = (
    "You are a trading assistant. Given a description of a trading approach, "
    "produce the setup as an explicit, executable rule set."
)


@dataclass
class BuildReport:
    company_outcome: int = 0
    market_vs_finances: int = 0
    trading_setup: int = 0
    business_failure: int = 0

    # Every builder runs over the same subjects, so a company that has no
    # financials still fails `company_outcome` while succeeding as
    # `business_failure`. Recording the subject alongside the reason lets the
    # covered ones drop out - otherwise the report claims hundreds of records
    # are untrainable when they are already in the corpus.
    _skips: list[tuple[str, str]] = field(default_factory=list)
    _covered: set[str] = field(default_factory=set)

    def skip(self, subject: str, reason: str) -> None:
        self._skips.append((subject, reason))

    def cover(self, subject: str) -> None:
        self._covered.add(subject)

    @property
    def skipped(self) -> list[str]:
        """Only subjects that produced no example of any kind."""
        seen: set[str] = set()
        out: list[str] = []
        for subject, reason in self._skips:
            if subject in self._covered or subject in seen:
                continue
            seen.add(subject)
            out.append(reason)
        return out

    @property
    def total(self) -> int:
        return (
            self.company_outcome
            + self.market_vs_finances
            + self.trading_setup
            + self.business_failure
        )


def _example(system: str, user: str, assistant: str, meta: dict) -> dict:
    return {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ],
        "metadata": meta,
    }


# --------------------------------------------------------------------------
# Context rendering
# --------------------------------------------------------------------------


def _financial_block(db: Session, instrument: Instrument, limit: int = 4) -> str:
    rows = db.scalars(
        select(Financial)
        .where(Financial.instrument_id == instrument.id, Financial.form == "10-K")
        .order_by(Financial.period_end)
    ).all()
    if not rows:
        return ""

    table: dict[str, dict[str, float]] = {}
    for row in rows:
        table.setdefault(row.period_end, {})[row.metric] = row.value

    periods = sorted(table)[-limit:]
    lines = ["FILED FINANCIALS (SEC 10-K, USD):"]
    for period in periods:
        values = table[period]
        parts = []
        for metric in (
            "revenue",
            "net_income",
            "operating_income",
            "assets",
            "liabilities",
            "equity",
        ):
            if metric in values:
                parts.append(f"{metric}={values[metric]:,.0f}")
        ratios = fin.derive_ratios(values)
        for key, value in ratios.items():
            parts.append(f"{key}={value}")
        lines.append(f"  FY ending {period}: " + ", ".join(parts))

    revenue_series = [(p, table[p]["revenue"]) for p in periods if "revenue" in table[p]]
    revenue_growth = fin.growth(revenue_series)
    if revenue_growth is not None:
        lines.append(f"  Revenue growth, latest period: {revenue_growth:+.2f}%")
    return "\n".join(lines)


def _bars(db: Session, instrument: Instrument) -> list[px.Bar]:
    rows = db.scalars(
        select(PriceBar)
        .where(PriceBar.instrument_id == instrument.id)
        .order_by(PriceBar.day)
    ).all()
    return [
        px.Bar(
            day=r.day, open=r.open, high=r.high, low=r.low, close=r.close, volume=r.volume
        )
        for r in rows
    ]


def _price_block(bars: list[px.Bar], as_of: date | None = None) -> str:
    if not bars:
        return ""

    window = [b for b in bars if as_of is None or b.day <= as_of] or bars
    last = window[-1]
    lines = [
        "MARKET PRICE ACTION:",
        f"  As of {last.day.isoformat()}: close={last.close:.2f}",
    ]
    for label, days in (("1M", 21), ("3M", 63), ("1Y", 252)):
        value = px.trailing_return(window, days)
        if value is not None:
            lines.append(f"  {label} return: {value:+.2f}%")
    volatility = px.realized_volatility(window)
    if volatility is not None:
        lines.append(f"  Annualized volatility: {volatility:.2f}%")
    return "\n".join(lines)


def _forward_return(bars: list[px.Bar], start: date, days: int) -> float | None:
    """Return over the `days` calendar days following `start`."""
    future = [b for b in bars if b.day >= start]
    if len(future) < 2:
        return None
    cutoff = start + timedelta(days=days)
    window = [b for b in future if b.day <= cutoff]
    if len(window) < 2:
        return None
    first, last = window[0].close, window[-1].close
    if not first:
        return None
    return round((last - first) / first * 100, 2)


def _transcript_excerpt(source: Source) -> str:
    if not source.raw_file_path:
        return ""
    text = read_transcript_text(source.raw_file_path)
    if not text:
        return ""
    excerpt = text[:TRANSCRIPT_EXCERPT_CHARS]
    if len(text) > TRANSCRIPT_EXCERPT_CHARS:
        excerpt += " […]"
    return excerpt


def _parse_published(source: Source) -> date | None:
    if not source.published_at:
        return None
    try:
        return datetime.strptime(source.published_at, "%Y-%m-%d").date()
    except ValueError:
        return None


# --------------------------------------------------------------------------
# Example builders
# --------------------------------------------------------------------------


def _company_examples(db: Session, report: BuildReport) -> list[dict]:
    companies = db.scalars(
        select(Company).options(
            selectinload(Company.events), selectinload(Company.instrument)
        )
    ).all()

    examples: list[dict] = []
    for company in companies:
        events = [e for e in company.events if e.summary]
        if not events:
            report.skip(f"company:{company.id}", f"{company.name}: no events with a summary")
            continue

        instrument = company.instrument
        bars = _bars(db, instrument) if instrument else []
        financial_block = _financial_block(db, instrument) if instrument else ""

        for event in events:
            source = db.get(Source, event.source_id) if event.source_id else None
            published = _parse_published(source) if source else None

            context = [
                f"COMPANY: {company.name}"
                + (f" ({company.ticker})" if company.ticker else "")
            ]
            if company.industry:
                context.append(f"INDUSTRY: {company.industry}")
            if financial_block:
                context.append(financial_block)
            price_block = _price_block(bars, as_of=published)
            if price_block:
                context.append(price_block)

            excerpt = _transcript_excerpt(source) if source else ""
            if excerpt:
                context.append(f"COMMENTARY TRANSCRIPT:\n{excerpt}")

            # Nothing but a bare company name teaches the model nothing.
            if not financial_block and not price_block and not excerpt:
                report.skip(
                    f"company:{company.id}", f"{company.name}: no context available"
                )
                continue

            answer = {
                "outcome": event.type.value,
                "roi_percent": event.roi_percent,
                "timeframe": {
                    "start": event.timeframe_start,
                    "end": event.timeframe_end,
                },
                "assessment": event.summary,
                "confidence": event.confidence_score,
            }

            meta = {
                "example_type": "company_outcome",
                "company_id": company.id,
                "event_id": event.id,
                "source_id": event.source_id,
                "ticker": company.ticker or (instrument.ticker if instrument else None),
                "has_financials": bool(financial_block),
                "has_prices": bool(price_block),
            }

            examples.append(
                _example(
                    COMPANY_SYSTEM,
                    "\n\n".join(context)
                    + "\n\nAssess the outcome for this company. Respond as JSON.",
                    json.dumps(answer, indent=2),
                    meta,
                )
            )
            report.company_outcome += 1
            report.cover(f"company:{company.id}")

    return examples


def _market_examples(db: Session, report: BuildReport) -> list[dict]:
    """Filings vs price action, independent of any transcript.

    This is the 'how does the business do on the market relative to its actual
    finances' comparison, and it is label-free: the forward return is the
    label, so these rows need no human judgement.
    """
    instruments = db.scalars(select(Instrument)).all()
    examples: list[dict] = []

    for instrument in instruments:
        financial_block = _financial_block(db, instrument)
        bars = _bars(db, instrument)
        if not financial_block or len(bars) < 30:
            report.skip(
                f"instrument:{instrument.id}",
                f"{instrument.ticker}: insufficient market data",
            )
            continue

        rows = db.scalars(
            select(Financial)
            .where(
                Financial.instrument_id == instrument.id,
                Financial.form == "10-K",
                Financial.metric == "revenue",
            )
            .order_by(Financial.period_end)
        ).all()

        for row in rows[-4:]:
            try:
                period_end = datetime.strptime(row.period_end, "%Y-%m-%d").date()
            except ValueError:
                continue

            forward = _forward_return(bars, period_end, days=365)
            if forward is None:
                continue

            context = [
                f"COMPANY: {instrument.name or instrument.ticker} ({instrument.ticker})",
            ]
            if instrument.sector:
                context.append(f"SECTOR: {instrument.sector}")
            context.append(financial_block)
            price_block = _price_block(bars, as_of=period_end)
            if price_block:
                context.append(price_block)
            context.append(f"FISCAL PERIOD UNDER REVIEW: ending {row.period_end}")

            answer = {
                "forward_return_1y_pct": forward,
                "direction": "up" if forward > 0 else "down",
                "period_end": row.period_end,
            }

            examples.append(
                _example(
                    MARKET_SYSTEM,
                    "\n\n".join(context)
                    + "\n\nBased on the filed financials and the price action to this "
                    "date, state the likely one-year forward return and direction. "
                    "Respond as JSON.",
                    json.dumps(answer, indent=2),
                    {
                        "example_type": "market_vs_finances",
                        "instrument_id": instrument.id,
                        "ticker": instrument.ticker,
                        "period_end": row.period_end,
                        "label_source": "realized_forward_return",
                    },
                )
            )
            report.market_vs_finances += 1
            report.cover(f"instrument:{instrument.id}")

    return examples


def _setup_examples(db: Session, report: BuildReport) -> list[dict]:
    setups = db.scalars(select(TradingSetup)).all()
    examples: list[dict] = []

    for setup in setups:
        if not setup.trigger and not setup.entry_rule:
            report.skip(f"setup:{setup.id}", f"setup {setup.id}: no trigger or entry rule")
            continue

        source = db.get(Source, setup.source_id)
        context = [f"TRADING APPROACH: {setup.name}"]
        if setup.market:
            context.append(f"MARKET: {setup.market}")
        if setup.instrument_hint:
            context.append(f"INSTRUMENT: {setup.instrument_hint}")
        if setup.timeframe:
            context.append(f"TIMEFRAME: {setup.timeframe}")
        if source:
            excerpt = _transcript_excerpt(source)
            if excerpt:
                context.append(f"SOURCE TRANSCRIPT:\n{excerpt}")

        answer = {
            "name": setup.name,
            "direction": setup.direction,
            "timeframe": setup.timeframe,
            "trigger": setup.trigger,
            "entry_rule": setup.entry_rule,
            "stop_rule": setup.stop_rule,
            "target_rule": setup.target_rule,
            "risk_rule": setup.risk_rule,
            "invalidation": setup.invalidation,
        }

        examples.append(
            _example(
                SETUP_SYSTEM,
                "\n\n".join(context)
                + "\n\nState this setup as an executable rule set. Respond as JSON.",
                json.dumps(answer, indent=2),
                {
                    "example_type": "trading_setup",
                    "setup_id": setup.id,
                    "source_id": setup.source_id,
                    "confidence": setup.confidence_score,
                },
            )
        )
        report.trading_setup += 1
        report.cover(f"setup:{setup.id}")

    return examples


FAILURE_SYSTEM = (
    "You are a business analyst. Given a company's profile - what it did, when it "
    "operated, and how much it raised - explain why it failed. Ground the answer in "
    "the facts provided."
)


def _failure_examples(db: Session, report: BuildReport) -> list[dict]:
    """Scraped post-mortems. The cause is the label, written by the source."""
    pages = db.scalars(select(ScrapedPage).order_by(ScrapedPage.id)).all()
    examples: list[dict] = []

    for page in pages:
        if not page.cause or len(page.cause) < 80:
            report.skip(
                f"company:{page.company_id}" if page.company_id else f"page:{page.id}",
                f"{page.name or page.url}: no usable cause text",
            )
            continue

        context = [f"COMPANY: {page.name}"]
        if page.industry:
            context.append(f"INDUSTRY: {page.industry}")
        if page.country:
            context.append(f"COUNTRY: {page.country}")
        if page.founded_year or page.shutdown_year:
            context.append(
                f"OPERATED: {page.founded_year or 'unknown'} to "
                f"{page.shutdown_year or 'unknown'}"
            )
        if page.funding_usd:
            context.append(f"CAPITAL RAISED: ${page.funding_usd:,.0f}")
        if page.description:
            context.append(f"WHAT IT DID: {page.description}")

        answer = {
            "outcome": "failure",
            "cause_of_failure": page.cause,
            "shutdown_year": page.shutdown_year,
            "capital_raised_usd": page.funding_usd,
        }

        examples.append(
            _example(
                FAILURE_SYSTEM,
                "\n".join(context)
                + "\n\nWhy did this business fail? Respond as JSON.",
                json.dumps(answer, indent=2),
                {
                    "example_type": "business_failure",
                    "scraped_page_id": page.id,
                    "company_id": page.company_id,
                    "source_url": page.url,
                    "label_source": "source_post_mortem",
                    "ai_assisted_fields": page.ai_fields or [],
                },
            )
        )
        report.business_failure += 1
        report.cover(
            f"company:{page.company_id}" if page.company_id else f"page:{page.id}"
        )

    return examples


BUILDERS = {
    "company_outcome": _company_examples,
    "market_vs_finances": _market_examples,
    "trading_setup": _setup_examples,
    "business_failure": _failure_examples,
}


def build_examples(
    db: Session, kinds: list[str] | None = None
) -> tuple[list[dict], BuildReport]:
    report = BuildReport()
    selected = kinds or list(BUILDERS)
    examples: list[dict] = []
    for kind in selected:
        builder = BUILDERS.get(kind)
        if builder is None:
            continue
        examples.extend(builder(db, report))
    return examples, report


def to_jsonl(examples: list[dict], include_metadata: bool = True) -> str:
    lines = []
    for example in examples:
        row = example if include_metadata else {"messages": example["messages"]}
        lines.append(json.dumps(row, ensure_ascii=False))
    return "\n".join(lines) + ("\n" if lines else "")
