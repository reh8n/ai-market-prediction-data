from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.training import builder

router = APIRouter(prefix="/training", tags=["training"])

KINDS = list(builder.BUILDERS)


@router.get("/preview")
def preview(
    kinds: list[str] | None = Query(None, description=f"Any of: {KINDS}"),
    limit: int = Query(5, le=50),
    db: Session = Depends(get_db),
):
    """Counts plus a few full examples, for eyeballing before you export."""
    examples, report = builder.build_examples(db, kinds)
    return {
        "counts": {
            "company_outcome": report.company_outcome,
            "market_vs_finances": report.market_vs_finances,
            "trading_setup": report.trading_setup,
            "business_failure": report.business_failure,
            "total": report.total,
        },
        "skipped": report.skipped[:25],
        "skipped_total": len(report.skipped),
        "examples": _spread(examples, limit),
    }


def _spread(examples: list[dict], limit: int) -> list[dict]:
    """Take one example per type in turn, rather than the first N.

    Examples are built grouped by type, so a plain slice returns several rows
    of whatever type happens to be first - often the same company at different
    quarters, which reads as duplicates and hides the other types entirely.
    """
    buckets: dict[str, list[dict]] = {}
    for example in examples:
        key = str(example.get("metadata", {}).get("example_type", "other"))
        buckets.setdefault(key, []).append(example)

    picked: list[dict] = []
    while len(picked) < limit and any(buckets.values()):
        for queue in buckets.values():
            if not queue:
                continue
            picked.append(queue.pop(0))
            if len(picked) >= limit:
                break
    return picked


@router.get("/export.jsonl", response_class=PlainTextResponse)
def export_jsonl(
    kinds: list[str] | None = Query(None, description=f"Any of: {KINDS}"),
    include_metadata: bool = Query(
        True, description="Set false for a bare messages-only file."
    ),
    db: Session = Depends(get_db),
):
    """The training file. One JSON object per line."""
    examples, _ = builder.build_examples(db, kinds)
    body = builder.to_jsonl(examples, include_metadata=include_metadata)
    return PlainTextResponse(
        body,
        media_type="application/x-ndjson",
        headers={
            "Content-Disposition": 'attachment; filename="training_data.jsonl"'
        },
    )
