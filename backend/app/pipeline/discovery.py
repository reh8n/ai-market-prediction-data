"""Finding videos worth ingesting, without a YouTube API key.

yt-dlp can run a YouTube search and list a channel's uploads. Both work
unauthenticated, so discovery costs nothing and needs no quota.

The hard part is not finding videos - it is rejecting the bad ones. A raw
search for "why startups fail" returns AI-narrated slideshows with 11 views
alongside real post-mortems. Everything below exists to throw those away
before they reach the transcript pipeline.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field

logger = logging.getLogger(__name__)

# Curated searches, so the operator picks a subject rather than inventing
# query strings. Each topic maps to several phrasings because YouTube's
# ranking is query-sensitive - one wording alone misses obvious videos.
TOPICS: dict[str, dict] = {
    "business_failure": {
        "label": "Business failures",
        "blurb": "Post-mortems: what the company was, what killed it.",
        "queries": [
            "why this startup failed post mortem",
            "company bankruptcy explained what went wrong",
            "startup failure story founder interview",
            "business collapse case study analysis",
        ],
    },
    "company_analysis": {
        "label": "Company analysis",
        "blurb": "Fundamentals, earnings, valuation breakdowns.",
        "queries": [
            "stock deep dive fundamental analysis",
            "earnings call breakdown analysis",
            "is this stock a buy valuation analysis",
            "company financials explained balance sheet",
        ],
    },
    "trading_technique": {
        "label": "Trading technique",
        "blurb": "Setups, entries, stops - the TJR Boot Camp shape.",
        "queries": [
            "trading strategy explained entry stop loss",
            "price action trading setup tutorial",
            "day trading strategy backtested rules",
            "smart money concepts liquidity explained",
        ],
    },
    "market_events": {
        "label": "Market events",
        "blurb": "Crashes, short squeezes, sector moves.",
        "queries": [
            "stock market crash explained what happened",
            "short squeeze explained case study",
            "why did this stock drop analysis",
        ],
    },
}

# A channel handle/URL, versus a plain search phrase.
_CHANNEL_RE = re.compile(
    r"(?:youtube\.com/(?:@[\w.-]+|c/[\w.-]+|channel/[\w-]+|user/[\w.-]+))|^@[\w.-]+$",
    re.IGNORECASE,
)


@dataclass
class Filters:
    """Quality gates. Defaults are deliberately strict."""

    per_query: int = 15
    min_views: int = 1000
    min_duration_seconds: int = 240  # under 4 min is rarely substantive
    max_duration_seconds: int = 10800  # over 3 h is usually a livestream replay
    require_captions: bool = True
    title_must_match: str | None = None
    limit: int = 20

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class Candidate:
    video_id: str
    title: str | None = None
    channel: str | None = None
    duration_seconds: float | None = None
    view_count: int | None = None
    query: str | None = None
    reject_reason: str | None = None

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"


@dataclass
class DiscoveryResult:
    candidates: list[Candidate] = field(default_factory=list)
    rejected: list[Candidate] = field(default_factory=list)
    searched: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def is_channel(term: str) -> bool:
    return bool(_CHANNEL_RE.search(term.strip()))


def _channel_uploads_url(term: str) -> str:
    """Normalise a handle or channel URL to its uploads listing."""
    value = term.strip().rstrip("/")
    if value.startswith("@"):
        value = f"https://www.youtube.com/{value}"
    elif not value.startswith("http"):
        value = f"https://{value}"
    return value if value.endswith("/videos") else f"{value}/videos"


def _search_target(term: str, per_query: int) -> str:
    """yt-dlp accepts a URL or its own `ytsearchN:` pseudo-scheme."""
    if is_channel(term):
        return _channel_uploads_url(term)
    return f"ytsearch{per_query}:{term}"


class DiscoveryError(RuntimeError):
    pass


def _entries(target: str, per_query: int, is_channel_target: bool = False) -> list[dict]:
    """Flat extraction: metadata only, no per-video page loads. Fast."""
    from yt_dlp import YoutubeDL

    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        # Flat gives id/title/duration/view_count without fetching each watch
        # page. A full extract would be ~2 s per video instead of ~0 s.
        "extract_flat": True,
        "playlistend": per_query,
        # Tolerate one unavailable video in a listing. The cost is that a
        # bad *target* (a handle that does not exist) also comes back empty
        # instead of raising, which the channel check below turns back into
        # a real error - otherwise a typo looks like "no results".
        "ignoreerrors": True,
    }
    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(target, download=False)

    if not info:
        if is_channel_target:
            raise DiscoveryError(
                "Channel not found. Check the handle - it must match the URL "
                "exactly (youtube.com/@name)."
            )
        return []
    entries = info.get("entries") or []
    if is_channel_target and not entries:
        raise DiscoveryError("Channel found but it has no public videos listed.")
    channel = info.get("channel") or info.get("uploader") or info.get("title")
    rows = []
    for entry in entries:
        if not entry or not entry.get("id"):
            continue
        entry.setdefault("channel", channel)
        rows.append(entry)
    return rows


def has_captions(video_id: str) -> bool:
    """One light request. Cheaper than discovering the failure after ingest."""
    from youtube_transcript_api import CouldNotRetrieveTranscript, YouTubeTranscriptApi

    try:
        return any(True for _ in YouTubeTranscriptApi().list(video_id))
    except CouldNotRetrieveTranscript:
        return False
    except Exception as exc:  # network hiccup: don't reject on our own failure
        logger.debug("Caption check inconclusive for %s: %s", video_id, exc)
        return True


def _screen(candidate: Candidate, filters: Filters) -> str | None:
    """Return a rejection reason, or None to keep. Metadata checks only."""
    duration = candidate.duration_seconds
    if duration is not None:
        if duration < filters.min_duration_seconds:
            return "too_short"
        if duration > filters.max_duration_seconds:
            return "too_long"
    views = candidate.view_count
    if views is not None and filters.min_views and views < filters.min_views:
        return "too_few_views"
    if filters.title_must_match:
        title = (candidate.title or "").lower()
        if filters.title_must_match.lower() not in title:
            return "title_mismatch"
    return None


def discover(
    terms: list[str],
    filters: Filters | None = None,
    known_ids: set[str] | None = None,
    caption_check: bool = True,
) -> DiscoveryResult:
    """Search every term, screen the results, return what survives.

    `known_ids` are dropped silently as duplicates - re-running a topic tops up
    rather than repeating. Caption checking is the slow step (~1-2 s/video), so
    it runs last, only on candidates that already passed the cheap filters.
    """
    filters = filters or Filters()
    known = known_ids or set()
    result = DiscoveryResult()
    seen: set[str] = set()

    for term in terms:
        channel_target = is_channel(term)
        target = _search_target(term, filters.per_query)
        result.searched.append(term)
        try:
            entries = _entries(target, filters.per_query, channel_target)
        except Exception as exc:
            logger.warning("Search failed for %r: %s", term, exc)
            result.errors.append(f"{term}: {exc}")
            continue

        for entry in entries:
            video_id = entry["id"]
            if video_id in seen or video_id in known:
                continue
            seen.add(video_id)

            candidate = Candidate(
                video_id=video_id,
                title=entry.get("title"),
                channel=entry.get("channel") or entry.get("uploader"),
                duration_seconds=entry.get("duration"),
                view_count=entry.get("view_count"),
                query=term,
            )
            reason = _screen(candidate, filters)
            if reason:
                candidate.reject_reason = reason
                result.rejected.append(candidate)
                continue
            result.candidates.append(candidate)

    # Best first, so a small `limit` takes the strongest videos rather than
    # whatever the search happened to return first.
    result.candidates.sort(key=lambda c: c.view_count or 0, reverse=True)

    if caption_check and filters.require_captions:
        kept: list[Candidate] = []
        for candidate in result.candidates:
            if len(kept) >= filters.limit:
                break
            if has_captions(candidate.video_id):
                kept.append(candidate)
            else:
                candidate.reject_reason = "no_captions"
                result.rejected.append(candidate)
        result.candidates = kept
    else:
        result.candidates = result.candidates[: filters.limit]

    return result


def terms_for(topics: list[str] | None, extra: list[str] | None) -> list[str]:
    """Expand topic keys into their query sets, plus any free-text terms."""
    terms: list[str] = []
    for key in topics or []:
        topic = TOPICS.get(key)
        if topic:
            terms.extend(topic["queries"])
        else:
            logger.warning("Unknown topic %r, ignoring", key)
    terms.extend(t.strip() for t in (extra or []) if t.strip())
    # Preserve order, drop repeats.
    return list(dict.fromkeys(terms))
