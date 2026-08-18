"""Ticker -> CIK resolution using the SEC's own company list.

The SEC publishes the authoritative ticker/CIK mapping as a single JSON file.
It changes rarely, so it is fetched once and cached on disk.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

TICKER_URL = "https://www.sec.gov/files/company_tickers.json"
CACHE_TTL_SECONDS = 7 * 24 * 3600

# The SEC requires a descriptive User-Agent with contact details on every
# request; anonymous traffic gets blocked.
SEC_HEADERS = {
    "User-Agent": settings.sec_user_agent,
    "Accept-Encoding": "gzip, deflate",
}


@dataclass
class TickerRecord:
    ticker: str
    cik: int
    title: str

    @property
    def cik_padded(self) -> str:
        return f"CIK{self.cik:010d}"


_cache: dict[str, TickerRecord] | None = None


def _cache_path():
    return settings.data_path / "sec_company_tickers.json"


def _load_raw() -> dict:
    path = _cache_path()
    if path.exists() and (time.time() - path.stat().st_mtime) < CACHE_TTL_SECONDS:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("Corrupt ticker cache at %s; refetching", path)

    response = httpx.get(TICKER_URL, headers=SEC_HEADERS, timeout=30)
    response.raise_for_status()
    payload = response.json()
    path.write_text(json.dumps(payload), encoding="utf-8")
    return payload


def load_ticker_map() -> dict[str, TickerRecord]:
    global _cache
    if _cache is not None:
        return _cache

    raw = _load_raw()
    records: dict[str, TickerRecord] = {}
    for entry in raw.values():
        ticker = str(entry["ticker"]).upper()
        records[ticker] = TickerRecord(
            ticker=ticker, cik=int(entry["cik_str"]), title=str(entry["title"])
        )
    _cache = records
    logger.info("Loaded %s SEC ticker records", len(records))
    return records


def lookup_ticker(ticker: str) -> TickerRecord | None:
    return load_ticker_map().get(ticker.strip().upper())


_SUFFIXES = re.compile(
    r"\b(inc|incorporated|corp|corporation|co|company|ltd|limited|plc|llc|lp|holdings|group|the)\b\.?",
    re.IGNORECASE,
)


def _normalize(name: str) -> str:
    cleaned = _SUFFIXES.sub(" ", name.lower())
    return re.sub(r"[^a-z0-9 ]+", " ", cleaned).strip()


def resolve_company(name: str) -> TickerRecord | None:
    """Best-effort company name -> ticker.

    Deliberately conservative: an exact or clean prefix match only. A fuzzy
    match here would silently attach the wrong company's financials to a
    transcript, which is worse than leaving it unlinked.
    """
    target = _normalize(name)
    if not target:
        return None

    records = load_ticker_map()

    # A bare ticker in the name field is the common case for market commentary.
    direct = records.get(name.strip().upper())
    if direct is not None:
        return direct

    exact: list[TickerRecord] = []
    prefix: list[TickerRecord] = []
    for record in records.values():
        normalized = _normalize(record.title)
        if normalized == target:
            exact.append(record)
        elif normalized.startswith(target + " ") and len(target) >= 4:
            prefix.append(record)

    if len(exact) == 1:
        return exact[0]
    if not exact and len(prefix) == 1:
        return prefix[0]
    # Ambiguous or unknown - leave it to a human rather than guessing.
    return None
