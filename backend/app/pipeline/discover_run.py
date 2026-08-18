"""Discovery job orchestration.

Search, screen, queue, and (optionally) ingest end-to-end. This is the piece
that makes the video side automatic: the operator picks a subject, not URLs.
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from app.db import SessionLocal
from app.models import DiscoveryJob, JobStatus, Source, SourceType, utcnow
from app.pipeline import discovery
from app.pipeline.run import process_youtube_source

logger = logging.getLogger(__name__)


def run_discovery_job(job_id: int, auto_ingest: bool = True) -> None:
    """Execute one discovery job. Never raises - failures land on the job row."""
    db = SessionLocal()
    queued_ids: list[int] = []
    try:
        job = db.get(DiscoveryJob, job_id)
        if job is None:
            logger.error("Discovery job %s vanished", job_id)
            return

        # `job.filters` also carries run options like auto_ingest, which are
        # not Filters fields - keep only the keys the dataclass accepts.
        defaults = discovery.Filters().as_dict()
        stored = {k: v for k, v in (job.filters or {}).items() if k in defaults}
        filters = discovery.Filters(**{**defaults, **stored})
        terms = list(job.terms or [])
        if not terms:
            job.status = JobStatus.failed
            job.error = "No topics or search terms given."
            job.finished_at = utcnow()
            db.commit()
            return

        job.status = JobStatus.processing
        db.commit()

        # Every YouTube source ever ingested, so re-running a topic tops up
        # instead of re-queueing the same videos.
        known = {
            row[0]
            for row in db.execute(
                select(Source.external_id).where(
                    Source.type == SourceType.youtube, Source.external_id.isnot(None)
                )
            ).all()
        }

        # Release the write lock before the network work starts - a discovery
        # run is minutes of HTTP, and other jobs must not block on it.
        db.commit()

        result = discovery.discover(terms, filters=filters, known_ids=known)

        job.found = len(result.candidates) + len(result.rejected)
        job.rejected = len(result.rejected)
        job.duplicates = len(known & {c.video_id for c in result.candidates})
        reasons: dict[str, int] = {}
        for candidate in result.rejected:
            key = candidate.reject_reason or "unknown"
            reasons[key] = reasons.get(key, 0) + 1
        job.reject_reasons = reasons
        if result.errors:
            job.error = "; ".join(result.errors[:3])
        db.commit()

        for candidate in result.candidates:
            existing = db.scalar(
                select(Source).where(
                    Source.external_id == candidate.video_id,
                    Source.type == SourceType.youtube,
                )
            )
            if existing is not None:
                job.duplicates += 1
                continue

            source = Source(
                type=SourceType.youtube,
                url=candidate.url,
                external_id=candidate.video_id,
                title=candidate.title,
                channel=candidate.channel,
            )
            db.add(source)
            db.commit()  # per record: progress survives a crash mid-run
            db.refresh(source)
            queued_ids.append(source.id)
            job.queued += 1
            db.commit()

        # Only finish here when nothing else follows. With auto-ingest the run
        # is still working, and reporting `done` early makes the UI show a
        # finished job whose `ingested` count then climbs from zero.
        if not auto_ingest or not queued_ids:
            job.status = JobStatus.done
            job.finished_at = utcnow()
        db.commit()
        logger.info(
            "Discovery job %s: found %s, rejected %s, queued %s",
            job_id,
            job.found,
            job.rejected,
            job.queued,
        )
    except Exception as exc:
        logger.exception("Discovery job %s crashed", job_id)
        job = db.get(DiscoveryJob, job_id)
        if job is not None:
            job.status = JobStatus.failed
            job.error = str(exc)
            job.finished_at = utcnow()
            db.commit()
        return
    finally:
        db.close()

    if not auto_ingest:
        return

    # Ingest outside the job's own session, and one at a time: each call opens
    # its own session, and serial requests keep us from hammering YouTube.
    for source_id in queued_ids:
        try:
            process_youtube_source(source_id)
        except Exception:
            logger.exception("Ingest failed for source %s", source_id)

    tally = SessionLocal()
    try:
        job = tally.get(DiscoveryJob, job_id)
        if job is None:
            return
        rows = tally.scalars(select(Source).where(Source.id.in_(queued_ids))).all()
        job.ingested = sum(1 for s in rows if s.status == JobStatus.done)
        job.failed = sum(1 for s in rows if s.status == JobStatus.failed)
        # The run really is over now, so the counts and the status land together.
        job.status = JobStatus.done
        job.finished_at = utcnow()
        tally.commit()
    finally:
        tally.close()
