"""Provider backends for the analyst chat.

Two wire protocols cover essentially every hosted model worth pointing at:

  * Anthropic's Messages API.
  * OpenAI's chat-completions API - which Groq, Together, OpenRouter, DeepSeek,
    Mistral, Fireworks, vLLM and Ollama all speak. Any of those works by
    supplying a base URL, so "any API key" is one code path, not one per vendor.

Both loops execute the same read-only tools against the same session. Only the
message shapes differ, which is why each provider owns its own loop rather than
sharing one behind a lossy abstraction.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.analyst import tools as analyst_tools

MAX_TOKENS = 16000
MAX_TOOL_ROUNDS = 8

ANTHROPIC_DEFAULT_MODEL = "claude-opus-5"
OPENAI_DEFAULT_MODEL = "gpt-4o"

# Endpoints that speak OpenAI chat-completions. Listed so the UI can offer them
# and so a user does not have to hunt for the base URL.
KNOWN_ENDPOINTS: dict[str, dict] = {
    "anthropic": {
        "label": "Anthropic",
        "recommended": True,
        "protocol": "anthropic",
        "base_url": None,
        "default_model": ANTHROPIC_DEFAULT_MODEL,
        "key_hint": "sk-ant-…",
    },
    "openai": {
        "label": "OpenAI",
        "recommended": True,
        "protocol": "openai",
        "base_url": None,
        "default_model": OPENAI_DEFAULT_MODEL,
        "key_hint": "sk-…",
    },
    "groq": {
        "label": "Groq",
        "recommended": False,
        "protocol": "openai",
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
        "key_hint": "gsk_…",
    },
    "openrouter": {
        "label": "OpenRouter",
        "recommended": False,
        "protocol": "openai",
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "anthropic/claude-sonnet-4.5",
        "key_hint": "sk-or-…",
    },
    "together": {
        "label": "Together AI",
        "recommended": False,
        "protocol": "openai",
        "base_url": "https://api.together.xyz/v1",
        "default_model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "key_hint": "…",
    },
    "deepseek": {
        "label": "DeepSeek",
        "recommended": False,
        "protocol": "openai",
        "base_url": "https://api.deepseek.com",
        "default_model": "deepseek-chat",
        "key_hint": "sk-…",
    },
    "mistral": {
        "label": "Mistral",
        "recommended": False,
        "protocol": "openai",
        "base_url": "https://api.mistral.ai/v1",
        "default_model": "mistral-large-latest",
        "key_hint": "…",
    },
    "custom": {
        "label": "Other (OpenAI-compatible)",
        "recommended": False,
        "protocol": "openai",
        "base_url": None,  # supplied by the caller
        "default_model": "",
        "key_hint": "any key your endpoint accepts",
    },
}


class BackendError(RuntimeError):
    pass


@dataclass
class Resolved:
    provider: str
    protocol: str
    model: str
    base_url: str | None


def detect_provider(api_key: str) -> str:
    """Guess the provider from the key's prefix.

    Only Anthropic's prefix is distinctive enough to be reliable. Everything
    else falls through to the OpenAI protocol, which is the right default:
    a bare `sk-` could be OpenAI or DeepSeek, and both speak it.
    """
    key = (api_key or "").strip()
    if key.startswith("sk-ant-"):
        return "anthropic"
    if key.startswith("gsk_"):
        return "groq"
    if key.startswith("sk-or-"):
        return "openrouter"
    return "openai"


def resolve(
    api_key: str,
    provider: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
) -> Resolved:
    name = (provider or "").strip().lower() or detect_provider(api_key)
    spec = KNOWN_ENDPOINTS.get(name)
    if spec is None:
        raise BackendError(
            f"Unknown provider {name!r}. Pick one of: {', '.join(KNOWN_ENDPOINTS)}."
        )

    url = (base_url or "").strip() or spec["base_url"]
    chosen = (model or "").strip() or spec["default_model"]

    if name == "custom" and not url:
        raise BackendError("A custom provider needs a base URL, e.g. http://localhost:11434/v1")
    if not chosen:
        raise BackendError(
            "This provider has no default model - enter the model name to use."
        )

    return Resolved(provider=name, protocol=spec["protocol"], model=chosen, base_url=url)


# --------------------------------------------------------------------------
# Anthropic
# --------------------------------------------------------------------------


def _anthropic_client(api_key: str, base_url: str | None):
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - pinned dependency
        raise BackendError("The `anthropic` package is not installed.") from exc
    kwargs = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return anthropic.Anthropic(**kwargs)


def run_anthropic(db: Session, system: str, convo: list[dict], cfg: Resolved, api_key: str):
    import anthropic

    client = _anthropic_client(api_key, cfg.base_url)
    messages = [dict(m) for m in convo]
    calls: list[tuple[str, dict, bool]] = []
    usage = {"input_tokens": 0, "output_tokens": 0}

    for _ in range(MAX_TOOL_ROUNDS):
        try:
            response = client.messages.create(
                model=cfg.model,
                max_tokens=MAX_TOKENS,
                system=system,
                # Thinking stays on: with it disabled this model family can
                # write a tool call as plain text, which would never run.
                thinking={"type": "adaptive"},
                output_config={"effort": "medium"},
                tools=analyst_tools.TOOLS,
                messages=messages,
            )
        except anthropic.AuthenticationError as exc:
            raise BackendError("That API key was rejected. Check it and try again.") from exc
        except anthropic.NotFoundError as exc:
            raise BackendError(f"Model {cfg.model!r} was not found for this key.") from exc
        except anthropic.RateLimitError as exc:
            raise BackendError("Rate limited by the provider. Wait and retry.") from exc
        except anthropic.APIStatusError as exc:
            raise BackendError(f"API error {exc.status_code}: {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise BackendError("Could not reach the provider. Check the network.") from exc

        usage["input_tokens"] += response.usage.input_tokens
        usage["output_tokens"] += response.usage.output_tokens

        if response.stop_reason == "refusal":
            raise BackendError("The model declined to answer that request.")

        if response.stop_reason != "tool_use":
            text = "\n".join(b.text for b in response.content if b.type == "text").strip()
            return text, calls, usage

        # Echo the assistant turn back whole - thinking blocks included, since
        # editing or dropping them breaks the next request.
        messages.append({"role": "assistant", "content": response.content})

        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            payload = dict(block.input or {})
            output = analyst_tools.run_tool(db, block.name, payload)
            calls.append((block.name, payload, '"error"' not in output[:40]))
            results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": output}
            )
        messages.append({"role": "user", "content": results})

    return None, calls, usage


# --------------------------------------------------------------------------
# OpenAI protocol (OpenAI, Groq, OpenRouter, Together, DeepSeek, local, ...)
# --------------------------------------------------------------------------


def _openai_tools() -> list[dict]:
    """Same tools, in the shape the chat-completions API expects."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": {
                    "type": "object",
                    "properties": tool["input_schema"].get("properties", {}),
                    "required": tool["input_schema"].get("required", []),
                },
            },
        }
        for tool in analyst_tools.TOOLS
    ]


def _openai_client(api_key: str, base_url: str | None):
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - pinned dependency
        raise BackendError("The `openai` package is not installed.") from exc
    kwargs = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def run_openai(db: Session, system: str, convo: list[dict], cfg: Resolved, api_key: str):
    import openai

    client = _openai_client(api_key, cfg.base_url)
    messages: list[dict] = [{"role": "system", "content": system}]
    messages.extend({"role": m["role"], "content": m["content"]} for m in convo)

    calls: list[tuple[str, dict, bool]] = []
    usage = {"input_tokens": 0, "output_tokens": 0}
    tool_defs = _openai_tools()

    for _ in range(MAX_TOOL_ROUNDS):
        try:
            response = client.chat.completions.create(
                model=cfg.model,
                messages=messages,
                tools=tool_defs,
                max_tokens=MAX_TOKENS,
            )
        except openai.AuthenticationError as exc:
            raise BackendError("That API key was rejected. Check it and try again.") from exc
        except openai.NotFoundError as exc:
            raise BackendError(
                f"Model {cfg.model!r} was not found at this endpoint."
            ) from exc
        except openai.RateLimitError as exc:
            raise BackendError("Rate limited by the provider. Wait and retry.") from exc
        except openai.APIStatusError as exc:
            raise BackendError(f"API error {exc.status_code}: {exc.message}") from exc
        except openai.APIConnectionError as exc:
            raise BackendError(
                "Could not reach the provider. Check the base URL and network."
            ) from exc

        if response.usage:
            usage["input_tokens"] += response.usage.prompt_tokens or 0
            usage["output_tokens"] += response.usage.completion_tokens or 0

        message = response.choices[0].message
        if not message.tool_calls:
            return (message.content or "").strip(), calls, usage

        messages.append(
            {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in message.tool_calls
                ],
            }
        )

        for call in message.tool_calls:
            try:
                payload = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                # Smaller models sometimes emit malformed argument JSON. Tell
                # the model rather than crashing the turn.
                payload = {}
            output = analyst_tools.run_tool(db, call.function.name, payload)
            calls.append((call.function.name, payload, '"error"' not in output[:40]))
            messages.append(
                {"role": "tool", "tool_call_id": call.id, "content": output}
            )

    return None, calls, usage


def validate(api_key: str, cfg: Resolved) -> None:
    """Check the credentials before a long run. Costs no tokens."""
    if cfg.protocol == "anthropic":
        _anthropic_client(api_key, cfg.base_url).models.list(limit=1)
    else:
        _openai_client(api_key, cfg.base_url).models.list()
