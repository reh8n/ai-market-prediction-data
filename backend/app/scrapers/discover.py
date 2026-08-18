"""Finding company pages on a site.

Sitemaps are the polite route: the site publishes them precisely so crawlers
don't have to guess at URLs or spider every link.
"""

from __future__ import annotations

import gzip
import logging
import re

from app.scrapers.fetcher import Blocked, FetchError, PoliteFetcher
from app.scrapers.profiles import SiteProfile

logger = logging.getLogger(__name__)

_LOC = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.I | re.S)
_SITEMAPINDEX = re.compile(r"<sitemapindex", re.I)


def _fetch_xml(fetcher: PoliteFetcher, url: str) -> str:
    page = fetcher.get(url)
    body = page.html
    if url.endswith(".gz"):
        try:
            body = gzip.decompress(body.encode("latin-1")).decode("utf-8", "ignore")
        except Exception:
            pass
    return body


def sitemap_urls(fetcher: PoliteFetcher, sitemap_url: str, depth: int = 0) -> list[str]:
    """All page URLs in a sitemap, following one level of sitemap index."""
    try:
        body = _fetch_xml(fetcher, sitemap_url)
    except (FetchError, Blocked) as exc:
        logger.warning("Sitemap unavailable %s: %s", sitemap_url, exc)
        return []

    found = _LOC.findall(body)
    if _SITEMAPINDEX.search(body) and depth < 2:
        nested: list[str] = []
        for child in found[:25]:
            nested.extend(sitemap_urls(fetcher, child, depth + 1))
        return nested
    return found


def discover(
    fetcher: PoliteFetcher, profile: SiteProfile, limit: int | None = None
) -> list[str]:
    """Company-page URLs for a site, in sitemap order."""
    candidates = sitemap_urls(fetcher, profile.sitemap_url)
    matched = [url for url in candidates if profile.matches(url)]

    # Fall back to crawling seed pages only when the sitemap yields nothing.
    if not matched and profile.seed_urls:
        for seed in profile.seed_urls:
            try:
                page = fetcher.get(seed)
            except (FetchError, Blocked):
                continue
            for href in re.findall(r'href="([^"]+)"', page.html):
                absolute = href if href.startswith("http") else profile.base_url + href
                if profile.matches(absolute):
                    matched.append(absolute)

    seen: set[str] = set()
    unique: list[str] = []
    for url in matched:
        normalized = url.split("#")[0].rstrip("/")
        if normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)

    return unique[:limit] if limit else unique
