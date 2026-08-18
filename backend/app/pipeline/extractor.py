"""Provider-agnostic structured extraction with content routing.

The pipeline calls `extract_transcript()` and gets back a classified, schema-
shaped result. Which provider ran is a runtime detail decided by
EXTRACTION_PROVIDER, so swapping providers touches nothing downstream.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.config import get_settings
from app.pipeline.schemas import (
    CLASSIFY_SCHEMA,
    CLASSIFY_SYSTEM,
    COMPANY_SCHEMA,
    COMPANY_SYSTEM,
    SETUP_SCHEMA,
    SETUP_SYSTEM,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# Extraction quality does not improve much past this, and long transcripts get
# expensive fast.
MAX_TRANSCRIPT_CHARS = 200_000
# Classification only needs a sample - the opening minutes reveal the format.
CLASSIFY_SAMPLE_CHARS = 6_000


@dataclass
class ExtractionResult:
    content_kind: str
    data: dict
    model_used: str | None
    provider: str
    classification: dict = field(default_factory=dict)

    @property
    def summary(self) -> str | None:
        return self.data.get("overall_summary")

    @property
    def companies(self) -> list[dict]:
        return self.data.get("companies") or []

    @property
    def setups(self) -> list[dict]:
        return self.data.get("setups") or []


def build_prompt(transcript_text: str, context: str = "") -> str:
    text = transcript_text[:MAX_TRANSCRIPT_CHARS]
    parts = []
    if context:
        parts.append(f"Context about this source: {context}")
    parts.append(f"<transcript>\n{text}\n</transcript>")
    return "\n\n".join(parts)


class Extractor(ABC):
    """One method per provider: run a JSON-schema-constrained completion."""

    provider_name: str = "unknown"
    model_name: str | None = None

    @abstractmethod
    def complete_json(self, system: str, user: str, schema: dict, name: str) -> dict:
        """Return JSON conforming to `schema`."""

    def validate(self) -> None:
        """Raise if the credentials are unusable.

        Worth a round trip before a long backfill: enrichment swallows
        per-record errors by design, so an unauthenticated run would otherwise
        finish "successfully" having changed nothing, with no reason given.
        """
        return None

    def classify(self, transcript_text: str, context: str = "") -> dict:
        sample = transcript_text[:CLASSIFY_SAMPLE_CHARS]
        return self.complete_json(
            CLASSIFY_SYSTEM,
            build_prompt(sample, context),
            CLASSIFY_SCHEMA,
            "content_classification",
        )

    def extract(self, transcript_text: str, context: str = "") -> ExtractionResult:
        if not transcript_text.strip():
            return ExtractionResult(
                content_kind="other",
                data={"companies": [], "setups": [], "overall_summary": "Empty transcript."},
                model_used=self.model_name,
                provider=self.provider_name,
            )

        classification = self.classify(transcript_text, context)
        kind = classification.get("content_kind", "other")
        prompt = build_prompt(transcript_text, context)

        data: dict = {}
        if kind in ("company_analysis", "mixed"):
            data.update(
                self.complete_json(
                    COMPANY_SYSTEM, prompt, COMPANY_SCHEMA, "company_extraction"
                )
            )
        if kind in ("trading_technique", "mixed"):
            setups = self.complete_json(
                SETUP_SYSTEM, prompt, SETUP_SCHEMA, "setup_extraction"
            )
            # On `mixed` both schemas run; keep the company summary as primary.
            summary = data.get("overall_summary")
            data.update(setups)
            if summary:
                data["overall_summary"] = summary
        if kind == "other":
            data = {
                "companies": [],
                "setups": [],
                "overall_summary": classification.get(
                    "reason", "Content is neither company analysis nor trading technique."
                ),
            }

        data.setdefault("companies", [])
        data.setdefault("setups", [])
        return ExtractionResult(
            content_kind=kind,
            data=data,
            model_used=self.model_name,
            provider=self.provider_name,
            classification=classification,
        )


class NullExtractor(Extractor):
    """No-op so the pipeline runs end-to-end without any API key."""

    provider_name = "null"

    def complete_json(self, system: str, user: str, schema: dict, name: str) -> dict:
        raise RuntimeError("NullExtractor does not call a model")

    def extract(self, transcript_text: str, context: str = "") -> ExtractionResult:
        return ExtractionResult(
            content_kind="other",
            data={
                "companies": [],
                "setups": [],
                "overall_summary": (
                    "Extraction skipped: EXTRACTION_PROVIDER is 'null'. Set it to "
                    "'anthropic' or 'openai' and supply EXTRACTION_API_KEY to "
                    "populate structured data."
                ),
            },
            model_used=None,
            provider=self.provider_name,
        )


class AnthropicExtractor(Extractor):
    provider_name = "anthropic"
    default_model = "claude-opus-5"

    def __init__(self, api_key: str, model: str | None = None):
        import anthropic

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model_name = model or self.default_model

    def validate(self) -> None:
        # Listing models authenticates without generating any tokens.
        self.client.models.list(limit=1)

    def complete_json(self, system: str, user: str, schema: dict, name: str) -> dict:
        response = self.client.messages.create(
            model=self.model_name,
            max_tokens=16000,
            system=system,
            output_config={"format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": user}],
        )

        if response.stop_reason == "refusal":
            category = getattr(response.stop_details, "category", None)
            raise RuntimeError(f"Extraction refused ({name}): {category}")

        text = next(b.text for b in response.content if b.type == "text")
        return json.loads(text)


class OpenAIExtractor(Extractor):
    provider_name = "openai"
    default_model = "gpt-4o"

    def __init__(self, api_key: str, model: str | None = None):
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key)
        self.model_name = model or self.default_model

    def validate(self) -> None:
        self.client.models.list()

    def complete_json(self, system: str, user: str, schema: dict, name: str) -> dict:
        response = self.client.chat.completions.create(
            model=self.model_name,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": name, "schema": schema, "strict": True},
            },
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return json.loads(response.choices[0].message.content)


def get_extractor(api_key: str | None = None) -> Extractor:
    """Build the configured extractor.

    `api_key` lets a caller supply a key for one operation without it ever
    reaching `.env` or the database - that is how the key typed into the
    analyst chat can also drive a backfill. A supplied key implies Anthropic
    when no provider is configured, since that is the only provider the chat
    itself can use.
    """
    provider = settings.extraction_provider.lower().strip()
    key = (api_key or settings.extraction_api_key or "").strip()

    if api_key and provider in ("", "null", "none", "disabled"):
        # Infer from the key rather than assuming Anthropic - the same key the
        # operator typed into the analyst chat drives this.
        from app.analyst.backends import KNOWN_ENDPOINTS, detect_provider

        detected = detect_provider(api_key)
        provider = KNOWN_ENDPOINTS.get(detected, {}).get("protocol", "openai")

    if provider in ("", "null", "none", "disabled"):
        return NullExtractor()

    if not key:
        raise RuntimeError(
            f"EXTRACTION_PROVIDER is '{provider}' but EXTRACTION_API_KEY is empty."
        )

    model = settings.extraction_model or None
    if provider == "anthropic":
        return AnthropicExtractor(key, model)
    if provider == "openai":
        return OpenAIExtractor(key, model)

    raise RuntimeError(f"Unknown EXTRACTION_PROVIDER: {provider!r}")
