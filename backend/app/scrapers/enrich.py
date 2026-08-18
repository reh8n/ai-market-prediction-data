"""The AI half of the hybrid parser.

Rules run first and are free. This is only called for the fields they could not
fill, and only when a provider key is configured - so the scraper works with no
key at all, just with sparser records.
"""

from __future__ import annotations

import logging

from app.pipeline.extractor import Extractor

logger = logging.getLogger(__name__)

MAX_CHARS = 12_000

SYSTEM = """\
You read a saved web page about a company that shut down and fill in only the \
fields you are asked for.

Answer strictly from the page text. Use null for anything the page does not \
state - a null is correct and useful, a guess is not. `cause` should be one or \
two plain sentences explaining why the business failed, in your own words.
"""

FIELD_SCHEMA = {
    "cause": {
        "type": ["string", "null"],
        "description": "Why the business failed, in one or two sentences.",
    },
    "industry": {
        "type": ["string", "null"],
        "description": "Sector, e.g. fintech, healthcare, consumer hardware.",
    },
    "funding_usd": {
        "type": ["number", "null"],
        "description": "Total raised or burnt, in US dollars, only if stated.",
    },
    "shutdown_year": {
        "type": ["integer", "null"],
        "description": "Year the business shut down or was acquired.",
    },
    "founded_year": {"type": ["integer", "null"]},
    "country": {"type": ["string", "null"]},
}


def build_schema(fields: list[str]) -> dict:
    properties = {name: FIELD_SCHEMA[name] for name in fields if name in FIELD_SCHEMA}
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def enrich(
    extractor: Extractor, name: str | None, text: str, missing: list[str]
) -> dict:
    """Ask the model for just the missing fields. Returns {} on any failure."""
    wanted = [f for f in missing if f in FIELD_SCHEMA]
    if not wanted:
        return {}

    prompt = (
        f"Company: {name or 'unknown'}\n"
        f"Fill in only these fields: {', '.join(wanted)}.\n\n"
        f"<page>\n{text[:MAX_CHARS]}\n</page>"
    )
    try:
        return extractor.complete_json(
            SYSTEM, prompt, build_schema(wanted), "page_enrichment"
        )
    except Exception as exc:
        logger.warning("Enrichment failed for %s: %s", name, exc)
        return {}
