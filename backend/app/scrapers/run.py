"""Scrape job orchestration.

Discover URLs, fetch politely, parse with rules, top up with AI where the rules
came up short, then save. Filters that need page content are applied after
parsing, so `limit` counts records actually kept rather than pages visited.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.models import (
    Company,
    Event,
    JobStatus,
    Outcome,
    ScrapedPage,
    ScrapeJob,
    ScrapeSite,
    utcnow,
)
from app.pipeline.extractor import NullExtractor, get_extractor
from app.scrapers import discover as discovery
from app.scrapers import enrich as enrichment
from app.scrapers.fetcher import Blocked, FetchError, PoliteFetcher
from app.scrapers.parse import looks_like_company_page, parse_page
from app.scrapers.profiles import SiteProfile

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class Filters:
    limit: int = 25
    industry: str | None = None
    year_min: int | None = None
    year_max: int | None = None
    funding_min: float | None = None
    funding_max: float | None = None
    use_ai: bool = True

    def as_dict(self) -> dict:
        return {
            "limit": self.limit,
            "industry": self.industry,
            "year_min": self.year_min,
            "year_max": self.year_max,
            "funding_min": self.funding_min,
            "funding_max": self.funding_max,
            "use_ai": self.use_ai,
        }


def profile_from_site(site: ScrapeSite) -> SiteProfile:
    return SiteProfile(
        key=site.key,
        name=site.name,
        base_url=site.base_url,
        sitemap_url=site.sitemap_url,
        url_pattern=site.url_pattern,
        exclude_pattern=site.exclude_pattern,
        notes=site.notes or "",
    )


def _passes(page, filters: Filters) -> tuple[bool, str]:
    """Filters that can only be judged once the page has been read."""
    if filters.industry:
        haystack = " ".join(
            filter(None, [page.industry, page.description, page.name])
        ).lower()
        if filters.industry.lower() not in haystack:
            return False, "industry"
    if filters.year_min and (page.shutdown_year or 0) < filters.year_min:
        return False, "year_min"
    if filters.year_max and (page.shutdown_year or 9999) > filters.year_max:
        return False, "year_max"
    if filters.funding_min and (page.funding_usd or 0) < filters.funding_min:
        return False, "funding_min"
    if filters.funding_max and (page.funding_usd or 0) > filters.funding_max:
        return False, "funding_max"
    return True, ""


def run_scrape_job(job_id: int) -> None:
    """Execute one scrape job. Never raises - failures are recorded on the job."""
    db = SessionLocal()
    fetcher: PoliteFetcher | None = None
    try:
        job = db.get(ScrapeJob, job_id)
        if job is None:
            logger.error("Scrape job %s vanished", job_id)
            return

        site = db.get(ScrapeSite, job.site_id) if job.site_id else None
        if site is None:
            job.status = JobStatus.failed
            job.error = "Site no longer exists"
            job.finished_at = utcnow()
            db.commit()
            return

        filters = Filters(**{**Filters().as_dict(), **(job.filters or {})})
        job.status = JobStatus.processing
        db.commit()

        profile = profile_from_site(site)
        fetcher = PoliteFetcher()

        # Cap discovery generously: content filters reject many pages, so we
        # need a bigger candidate pool than the requested count.
        ceiling = min(filters.limit * 12 + 40, settings.scraper_max_pages)
        urls = discovery.discover(fetcher, profile, limit=ceiling)
        job.discovered = len(urls)
        db.commit()

        if not urls:
            job.status = JobStatus.failed
            job.error = "No company pages found in the sitemap for this site."
            job.finished_at = utcnow()
            db.commit()
            return

        # Skip anything already stored so re-running tops up rather than repeats.
        known = {
            row[0]
            for row in db.execute(
                select(ScrapedPage.url).where(ScrapedPage.url.in_(urls))
            ).all()
        }

        extractor = None
        if filters.use_ai:
            try:
                candidate = get_extractor()
                extractor = None if isinstance(candidate, NullExtractor) else candidate
            except Exception as exc:
                logger.info("AI enrichment unavailable: %s", exc)

        settings.scraped_path.mkdir(parents=True, exist_ok=True)

        # Nothing below may hold a write transaction across a network call:
        # concurrent jobs would block each other for the whole fetch.
        db.commit()

        for url in urls:
            if job.saved >= filters.limit:
                break
            if url in known:
                job.skipped += 1
                continue

            try:
                response = fetcher.get(url)
            except Blocked as exc:
                logger.info("Skipping blocked URL: %s", exc)
                job.skipped += 1
                continue
            except FetchError as exc:
                logger.warning("Fetch failed %s: %s", url, exc)
                job.failed += 1
                continue

            job.fetched += 1
            if not response.ok:
                job.failed += 1
                continue

            parsed = parse_page(response.url, response.html)
            if not looks_like_company_page(parsed):
                job.skipped += 1
                continue

            ai_fields: list[str] = []
            if extractor is not None and parsed.needs_ai:
                filled = enrichment.enrich(
                    extractor, parsed.name, parsed.text, parsed.needs_ai
                )
                job.ai_calls += 1
                for key, value in (filled or {}).items():
                    if value in (None, "") or getattr(parsed, key, None) not in (None, ""):
                        continue
                    setattr(parsed, key, value)
                    ai_fields.append(key)

            keep, reason = _passes(parsed, filters)
            if not keep:
                job.skipped += 1
                logger.debug("Filtered out %s (%s)", url, reason)
                continue

            _save(db, site, parsed, ai_fields)
            job.saved += 1
            # Commit per record so the write lock is released before the next
            # fetch, and so progress survives a crash mid-run.
            db.commit()

        site.last_run_at = utcnow()
        job.status = JobStatus.done
        job.finished_at = utcnow()
        db.commit()
        logger.info(
            "Scrape job %s finished: %s saved, %s skipped, %s failed",
            job_id,
            job.saved,
            job.skipped,
            job.failed,
        )
    except Exception as exc:
        logger.exception("Scrape job %s crashed", job_id)
        job = db.get(ScrapeJob, job_id)
        if job is not None:
            job.status = JobStatus.failed
            job.error = str(exc)
            job.finished_at = utcnow()
            db.commit()
    finally:
        if fetcher is not None:
            fetcher.close()
        db.close()


def _save(db: Session, site: ScrapeSite, parsed, ai_fields: list[str]) -> None:
    """Store the page, and mirror it into companies/events for the exports."""
    path = settings.scraped_path / f"{site.key}_{abs(hash(parsed.url)) % 10**10}.json"
    path.write_text(
        json.dumps(
            {"url": parsed.url, "site": site.key, **parsed.to_dict(), "text": parsed.text},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    record = ScrapedPage(
        site_id=site.id,
        url=parsed.url,
        name=parsed.name,
        description=parsed.description,
        cause=parsed.cause,
        industry=parsed.industry,
        country=parsed.country,
        founded_year=parsed.founded_year,
        shutdown_year=parsed.shutdown_year,
        funding_usd=parsed.funding_usd,
        status=parsed.status,
        raw_file_path=str(path),
        rule_fields=parsed.fields_from_rules,
        ai_fields=ai_fields,
    )
    db.add(record)

    # These are failed businesses, so they belong in the same company/event
    # tables the YouTube pipeline writes to - one export serves both.
    company = db.scalar(select(Company).where(Company.name.ilike(parsed.name)))
    if company is None:
        company = Company(
            name=parsed.name,
            industry=parsed.industry,
            outcome=Outcome.failure,
            notes=parsed.description,
        )
        db.add(company)
        db.flush()
    else:
        company.industry = company.industry or parsed.industry
        if company.outcome == Outcome.unknown:
            company.outcome = Outcome.failure

    record.company_id = company.id

    summary_parts = [parsed.cause or parsed.description or ""]
    if parsed.funding_usd:
        summary_parts.append(f"Raised approximately ${parsed.funding_usd:,.0f}.")
    if parsed.country:
        summary_parts.append(f"Based in {parsed.country}.")

    db.add(
        Event(
            company_id=company.id,
            type=Outcome.failure,
            roi_percent=None,
            timeframe_start=str(parsed.founded_year) if parsed.founded_year else None,
            timeframe_end=str(parsed.shutdown_year) if parsed.shutdown_year else None,
            summary=" ".join(p for p in summary_parts if p).strip(),
            confidence_score=0.9 if not ai_fields else 0.75,
        )
    )
    db.flush()


def seed_builtin_sites(db: Session) -> None:
    """Make the three verified sites available on first boot."""
    from app.scrapers.profiles import BUILT_IN

    for profile in BUILT_IN.values():
        existing = db.scalar(select(ScrapeSite).where(ScrapeSite.key == profile.key))
        if existing is not None:
            continue
        db.add(
            ScrapeSite(
                key=profile.key,
                name=profile.name,
                base_url=profile.base_url,
                sitemap_url=profile.sitemap_url,
                url_pattern=profile.url_pattern,
                exclude_pattern=profile.exclude_pattern,
                notes=profile.notes,
                built_in=True,
            )
        )
    db.commit()
