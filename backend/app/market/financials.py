"""Audited financials from the SEC's XBRL company-facts API.

This is the ground truth the market gets compared against: figures as filed in
10-K/10-Q, not a vendor's derived estimate. Free, official, no API key.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from app.market.tickers import SEC_HEADERS

logger = logging.getLogger(__name__)

FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

# Companies tag the same idea with different concepts depending on their
# filing history, so each metric lists candidates in order of preference.
CONCEPTS: dict[str, list[str]] = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "operating_income": ["OperatingIncomeLoss"],
    "gross_profit": ["GrossProfit"],
    "assets": ["Assets"],
    "liabilities": ["Liabilities"],
    "equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "research_development": ["ResearchAndDevelopmentExpense"],
    "eps_diluted": ["EarningsPerShareDiluted"],
}


class FinancialsError(RuntimeError):
    pass


@dataclass
class FinancialFact:
    metric: str
    concept: str
    value: float
    unit: str
    period_end: str
    fiscal_year: int | None
    fiscal_period: str | None
    form: str | None
    filed: str | None


def fetch_company_facts(cik: int) -> dict:
    response = httpx.get(FACTS_URL.format(cik=cik), headers=SEC_HEADERS, timeout=60)
    if response.status_code == 404:
        raise FinancialsError(f"No XBRL facts filed for CIK {cik}")
    response.raise_for_status()
    return response.json()


def extract_facts(payload: dict, annual_only: bool = True) -> list[FinancialFact]:
    """Flatten company-facts JSON into one row per metric per period."""
    gaap = payload.get("facts", {}).get("us-gaap", {})
    dei = payload.get("facts", {}).get("dei", {})
    facts: list[FinancialFact] = []

    for metric, candidates in CONCEPTS.items():
        for concept in candidates:
            node = gaap.get(concept) or dei.get(concept)
            if not node:
                continue

            units = node.get("units", {})
            unit_key = next(
                (u for u in ("USD", "USD/shares", "shares") if u in units),
                next(iter(units), None),
            )
            if unit_key is None:
                continue

            seen: dict[str, FinancialFact] = {}
            for entry in units[unit_key]:
                form = entry.get("form")
                if annual_only and form != "10-K":
                    continue
                if not annual_only and form not in ("10-K", "10-Q"):
                    continue
                end = entry.get("end")
                if end is None:
                    continue

                fact = FinancialFact(
                    metric=metric,
                    concept=concept,
                    value=float(entry["val"]),
                    unit=unit_key,
                    period_end=end,
                    fiscal_year=entry.get("fy"),
                    fiscal_period=entry.get("fp"),
                    form=form,
                    filed=entry.get("filed"),
                )
                # Restatements repeat a period; the latest filing wins.
                previous = seen.get(end)
                if previous is None or (fact.filed or "") >= (previous.filed or ""):
                    seen[end] = fact

            if seen:
                facts.extend(seen.values())
                break  # first concept that yielded data wins for this metric

    facts.sort(key=lambda f: (f.period_end, f.metric))
    return facts


def fetch_financials(cik: int, annual_only: bool = True) -> list[FinancialFact]:
    return extract_facts(fetch_company_facts(cik), annual_only=annual_only)


def to_period_table(facts: list[FinancialFact]) -> dict[str, dict[str, float]]:
    """Reshape flat facts into {period_end: {metric: value}} for prompt building."""
    table: dict[str, dict[str, float]] = {}
    for fact in facts:
        table.setdefault(fact.period_end, {})[fact.metric] = fact.value
    return dict(sorted(table.items()))


def derive_ratios(period: dict[str, float]) -> dict[str, float]:
    """Margins and returns a model can use directly, where inputs allow."""
    ratios: dict[str, float] = {}
    revenue = period.get("revenue")
    net_income = period.get("net_income")
    assets = period.get("assets")
    equity = period.get("equity")
    gross_profit = period.get("gross_profit")
    operating_income = period.get("operating_income")

    if revenue:
        if net_income is not None:
            ratios["net_margin_pct"] = round(net_income / revenue * 100, 2)
        if gross_profit is not None:
            ratios["gross_margin_pct"] = round(gross_profit / revenue * 100, 2)
        if operating_income is not None:
            ratios["operating_margin_pct"] = round(operating_income / revenue * 100, 2)
    if assets and net_income is not None:
        ratios["return_on_assets_pct"] = round(net_income / assets * 100, 2)
    if equity and net_income is not None:
        ratios["return_on_equity_pct"] = round(net_income / equity * 100, 2)
    if assets and period.get("liabilities") is not None:
        ratios["liabilities_to_assets"] = round(period["liabilities"] / assets, 3)
    return ratios


def growth(series: list[tuple[str, float]]) -> float | None:
    """Percent change between the two most recent periods."""
    if len(series) < 2:
        return None
    previous, current = series[-2][1], series[-1][1]
    if not previous:
        return None
    return round((current - previous) / abs(previous) * 100, 2)
