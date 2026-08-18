"""Extraction schemas, one per content kind.

Both providers emit exactly these shapes, so downstream code never has to care
which model produced a row.
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# Company analysis: outcomes, ROI, causes. Joins to filings and price history.
# --------------------------------------------------------------------------

COMPANY_SCHEMA = {
    "type": "object",
    "properties": {
        "companies": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "ticker": {
                        "type": ["string", "null"],
                        "description": "Exchange ticker if stated or unambiguous, else null.",
                    },
                    "industry": {"type": ["string", "null"]},
                    "outcome": {
                        "type": "string",
                        "enum": ["success", "failure", "unknown"],
                    },
                    "roi_percent": {
                        "type": ["number", "null"],
                        "description": "Return on investment as a percentage, only if stated.",
                    },
                    "timeframe_start": {"type": ["string", "null"]},
                    "timeframe_end": {"type": ["string", "null"]},
                    "causes": {"type": "array", "items": {"type": "string"}},
                    "summary": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": [
                    "name",
                    "ticker",
                    "industry",
                    "outcome",
                    "roi_percent",
                    "timeframe_start",
                    "timeframe_end",
                    "causes",
                    "summary",
                    "confidence",
                ],
                "additionalProperties": False,
            },
        },
        "overall_summary": {"type": "string"},
    },
    "required": ["companies", "overall_summary"],
    "additionalProperties": False,
}

COMPANY_SYSTEM = """\
You extract structured facts about company outcomes from transcripts of market \
and business commentary, for a dataset that trains a stock-prediction model.

Extract only what the transcript actually supports. If a figure is not stated, \
use null rather than estimating. Set `outcome` to "unknown" when the transcript \
discusses a company without indicating whether it succeeded or failed. Set a low \
`confidence` when the speaker is speculating, and a high one when they cite \
concrete figures or events.
"""

# --------------------------------------------------------------------------
# Trading technique: reusable setups. This is what day-trading education
# content (TJR Boot Camp and similar) actually contains.
# --------------------------------------------------------------------------

SETUP_SCHEMA = {
    "type": "object",
    "properties": {
        "setups": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Short label, e.g. 'liquidity sweep reversal'.",
                    },
                    "market": {
                        "type": ["string", "null"],
                        "description": "equities, futures, forex, crypto, options, or null.",
                    },
                    "instrument_hint": {
                        "type": ["string", "null"],
                        "description": "Ticker or symbol named, e.g. SPY, ES, EURUSD.",
                    },
                    "timeframe": {
                        "type": ["string", "null"],
                        "description": "Chart timeframe, e.g. '5m', '1h', 'daily'.",
                    },
                    "direction": {
                        "type": ["string", "null"],
                        "enum": ["long", "short", "both", None],
                    },
                    "trigger": {
                        "type": ["string", "null"],
                        "description": "Market condition that arms the setup.",
                    },
                    "entry_rule": {"type": ["string", "null"]},
                    "stop_rule": {"type": ["string", "null"]},
                    "target_rule": {"type": ["string", "null"]},
                    "risk_rule": {
                        "type": ["string", "null"],
                        "description": "Position sizing or risk-per-trade guidance.",
                    },
                    "invalidation": {
                        "type": ["string", "null"],
                        "description": "What makes the setup void.",
                    },
                    "confidence": {"type": "number"},
                },
                "required": [
                    "name",
                    "market",
                    "instrument_hint",
                    "timeframe",
                    "direction",
                    "trigger",
                    "entry_rule",
                    "stop_rule",
                    "target_rule",
                    "risk_rule",
                    "invalidation",
                    "confidence",
                ],
                "additionalProperties": False,
            },
        },
        "concepts": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Named techniques or jargon taught, e.g. 'order block'.",
        },
        "overall_summary": {"type": "string"},
    },
    "required": ["setups", "concepts", "overall_summary"],
    "additionalProperties": False,
}

SETUP_SYSTEM = """\
You extract reusable trading setups from transcripts of trading education \
content, for a dataset that trains a trade-signal model.

A setup is a conditional rule about price action: when X happens, enter at Y, \
stop at Z. Capture the speaker's rules as taught, without improving or \
completing them. Use null for any part of a setup the speaker never specifies - \
an incomplete rule recorded honestly is more useful than an invented one. \
Set a low `confidence` when the speaker is loose or anecdotal, high when the \
rule is stated precisely. Do not extract market predictions or hype as setups.
"""

# --------------------------------------------------------------------------
# Router: decides which of the two schemas applies.
# --------------------------------------------------------------------------

CLASSIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "content_kind": {
            "type": "string",
            "enum": [
                "company_analysis",
                "trading_technique",
                "mixed",
                "other",
            ],
        },
        "reason": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": ["content_kind", "reason", "confidence"],
    "additionalProperties": False,
}

CLASSIFY_SYSTEM = """\
You route transcripts to the correct extractor for a market-research dataset.

- `company_analysis`: discusses specific companies, their performance, failures, \
returns, or business decisions.
- `trading_technique`: teaches how to trade - chart setups, entries, stops, risk \
management, indicators. Day-trading education belongs here even when it names \
tickers as examples.
- `mixed`: substantial amounts of both.
- `other`: neither, e.g. unrelated content or an empty transcript.

Judge by what the transcript is mostly about, not by isolated mentions.
"""
