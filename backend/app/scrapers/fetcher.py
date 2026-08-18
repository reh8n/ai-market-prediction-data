"""Polite HTTP fetching.

Every outbound request passes through here so the rules are enforced in one
place: check robots.txt first, identify ourselves honestly, wait between hits
on the same host, and never hammer a site that is failing.
"""

from __future__ import annotations

import logging
import threading
import time
import urllib.robotparser as robotparser
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class Blocked(RuntimeError):
    """Raised when robots.txt disallows a URL. Never retried."""


class FetchError(RuntimeError):
    pass


@dataclass
class Page:
    url: str
    status: int
    html: str

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300


class PoliteFetcher:
    """One instance per scrape job. Not shared across threads."""

    def __init__(
        self,
        user_agent: str | None = None,
        delay_seconds: float | None = None,
        timeout: float = 30.0,
    ):
        self.user_agent = user_agent or settings.scraper_user_agent
        self.delay = (
            delay_seconds if delay_seconds is not None else settings.scraper_delay_seconds
        )
        self.client = httpx.Client(
            headers={
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
            timeout=timeout,
            follow_redirects=True,
        )
        self._robots: dict[str, robotparser.RobotFileParser | None] = {}
        self._last_hit: dict[str, float] = {}
        self._lock = threading.Lock()

    # -- robots ---------------------------------------------------------

    def _robots_for(self, url: str) -> robotparser.RobotFileParser | None:
        host = urlparse(url).netloc
        if host in self._robots:
            return self._robots[host]

        scheme = urlparse(url).scheme or "https"
        parser: robotparser.RobotFileParser | None = robotparser.RobotFileParser()
        try:
            response = self.client.get(f"{scheme}://{host}/robots.txt", timeout=15)
            if response.status_code >= 400:
                # No robots file published means no restrictions stated.
                parser.parse([])
            else:
                parser.parse(response.text.splitlines())
        except Exception as exc:
            logger.warning("robots.txt unreadable for %s (%s); treating as open", host, exc)
            parser.parse([])

        self._robots[host] = parser
        return parser

    def allowed(self, url: str) -> bool:
        parser = self._robots_for(url)
        if parser is None:
            return True
        return parser.can_fetch(self.user_agent, url)

    def crawl_delay(self, url: str) -> float:
        """Honour a site's own Crawl-delay when it asks for more than ours."""
        parser = self._robots_for(url)
        if parser is None:
            return self.delay
        try:
            declared = parser.crawl_delay(self.user_agent)
        except Exception:
            declared = None
        return max(self.delay, float(declared)) if declared else self.delay

    # -- fetching -------------------------------------------------------

    def _wait_turn(self, url: str) -> None:
        host = urlparse(url).netloc
        needed = self.crawl_delay(url)
        with self._lock:
            last = self._last_hit.get(host)
            if last is not None:
                elapsed = time.monotonic() - last
                if elapsed < needed:
                    time.sleep(needed - elapsed)
            self._last_hit[host] = time.monotonic()

    def get(self, url: str, retries: int = 2) -> Page:
        if not self.allowed(url):
            raise Blocked(f"robots.txt disallows {url}")

        last_error: Exception | None = None
        for attempt in range(retries + 1):
            self._wait_turn(url)
            try:
                response = self.client.get(url)
            except Exception as exc:
                last_error = exc
                time.sleep(1.5 * (attempt + 1))
                continue

            # Back off when asked to, rather than retrying immediately.
            if response.status_code in (429, 503):
                retry_after = response.headers.get("retry-after")
                pause = float(retry_after) if (retry_after or "").isdigit() else 5.0
                logger.warning("%s returned %s; pausing %.1fs", url, response.status_code, pause)
                time.sleep(min(pause, 30))
                last_error = FetchError(f"HTTP {response.status_code}")
                continue

            if response.status_code >= 500:
                last_error = FetchError(f"HTTP {response.status_code}")
                time.sleep(1.5 * (attempt + 1))
                continue

            return Page(url=str(response.url), status=response.status_code, html=response.text)

        raise FetchError(f"{url}: {last_error}")

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> PoliteFetcher:
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()
