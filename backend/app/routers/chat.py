"""The analyst chat endpoint.

The API key arrives on each request and is used for that request only. It is
never written to disk, never stored in the database, and never logged - the
error paths below deliberately surface the model's message, not the request.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.analyst import agent, backends
from app.analyst.tools import TOOLS
from app.db import get_db

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1)
    api_key: str = Field(description="Used for this request only; never stored.")
    provider: str | None = Field(
        None, description="Omit to detect from the key's prefix."
    )
    model: str | None = Field(None, description="Overrides the provider's default.")
    base_url: str | None = Field(
        None, description="Required for a custom OpenAI-compatible endpoint."
    )


class ToolCallOut(BaseModel):
    name: str
    input: dict
    ok: bool


class ChatResponse(BaseModel):
    reply: str
    tool_calls: list[ToolCallOut]
    usage: dict
    provider: str
    model: str


@router.get("/capabilities")
def capabilities():
    """What the analyst can see, so the UI can say so without guessing."""
    return {
        "key_handling": "per-request; never stored on the server or in the database",
        "access": "read-only — it cannot start jobs, sync tickers, or change settings",
        "providers": [
            {
                "id": key,
                "label": spec["label"],
                "recommended": spec["recommended"],
                "protocol": spec["protocol"],
                "default_model": spec["default_model"],
                "needs_base_url": key == "custom",
                "key_hint": spec["key_hint"],
            }
            for key, spec in backends.KNOWN_ENDPOINTS.items()
        ],
        "tools": [{"name": t["name"], "description": t["description"]} for t in TOOLS],
    }


@router.post("", response_model=ChatResponse)
def send(payload: ChatRequest, db: Session = Depends(get_db)):
    if not payload.api_key.strip():
        raise HTTPException(status_code=400, detail="Enter an API key to use the analyst.")

    try:
        result = agent.chat(
            db,
            [m.model_dump() for m in payload.messages],
            payload.api_key.strip(),
            provider=payload.provider,
            model=payload.model,
            base_url=payload.base_url,
        )
    except agent.AnalystError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ChatResponse(
        reply=result.reply,
        tool_calls=[ToolCallOut(name=c.name, input=c.input, ok=c.ok) for c in result.tool_calls],
        usage=result.usage,
        provider=result.provider,
        model=result.model,
    )
