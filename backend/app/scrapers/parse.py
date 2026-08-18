"""Turn a scraped HTML page into fields.

Order matters. JSON-LD is the site's own machine-readable summary, so it is
tried first and is far more stable than CSS selectors. Meta tags come next,
then visible headings and body text. Regex picks the numbers out of prose.
Anything still missing is left as None for the AI pass to fill.
"""

from __future__ import annotations

import html as html_lib
import json
import re
from dataclasses import asdict, dataclass, field

# --------------------------------------------------------------------------
# HTML helpers
# --------------------------------------------------------------------------

_SCRIPT_STYLE = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.S | re.I)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def visible_text(html: str) -> str:
    stripped = _SCRIPT_STYLE.sub(" ", html)
    stripped = re.sub(r"<br\s*/?>|</p>|</div>|</li>|</h[1-6]>", "\n", stripped, flags=re.I)
    text = html_lib.unescape(_TAG.sub(" ", stripped))
    lines = [_WS.sub(" ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _meta(html: str, key: str) -> str | None:
    pattern = rf'<meta[^>]+(?:property|name)=["\']{re.escape(key)}["\'][^>]+content=["\']([^"\']*)["\']'
    match = re.search(pattern, html, re.I)
    if not match:
        pattern = rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:property|name)=["\']{re.escape(key)}["\']'
        match = re.search(pattern, html, re.I)
    return html_lib.unescape(match.group(1)).strip() if match else None


def _json_ld(html: str) -> list[dict]:
    blocks: list[dict] = []
    for raw in re.findall(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.S | re.I
    ):
        try:
            parsed = json.loads(raw.strip())
        except json.JSONDecodeError:
            continue
        items = parsed if isinstance(parsed, list) else [parsed]
        for item in items:
            if not isinstance(item, dict):
                continue
            blocks.append(item)
            # Schema.org allows nesting the real content under @graph.
            for node in item.get("@graph", []) or []:
                if isinstance(node, dict):
                    blocks.append(node)
    return blocks


def _headings(html: str) -> list[str]:
    found = []
    for raw in re.findall(r"<h[1-3][^>]*>(.*?)</h[1-3]>", html, re.S | re.I):
        text = _WS.sub(" ", html_lib.unescape(_TAG.sub("", raw))).strip()
        if text:
            found.append(text)
    return found


# --------------------------------------------------------------------------
# Field extraction
# --------------------------------------------------------------------------

_MULTIPLIER = {"k": 1e3, "m": 1e6, "b": 1e9, "bn": 1e9, "t": 1e12}

_MONEY = re.compile(
    r"(?:[$£€]|\bUSD\s*)\s?([\d,]+(?:\.\d+)?)\s*(k|m|b|bn|t|thousand|million|billion|trillion)?\b",
    re.IGNORECASE,
)

# Only treat a figure as funding when the surrounding words say so.
_FUNDING_CUE = re.compile(
    r"\b(rais(?:ed|ing)|funding|burn(?:ed|ing|t)?|inves(?:ted|tment)|backed with|"
    r"capital|valuation|valued at)\b",
    re.IGNORECASE,
)

_SHUTDOWN_YEAR = re.compile(
    r"\b(?:shut\s*down|shutdown|closed|ceased|folded|died|failed|dissolved|"
    r"went out of business|bankrupt\w*|acquired|wound down)\b[^.]{0,60}?\b(19|20)(\d{2})\b",
    re.IGNORECASE,
)
_YEAR_SHUTDOWN = re.compile(
    r"\b(?:in|by|during)\s+((?:19|20)\d{2})\b[^.]{0,40}?\b(?:shut\s*down|closed|ceased|"
    r"folded|failed|bankrupt\w*)\b",
    re.IGNORECASE,
)
_FOUNDED_YEAR = re.compile(r"\b(?:founded|started|launched|established)\b[^.]{0,40}?\b((?:19|20)\d{2})\b", re.IGNORECASE)

_COUNTRY_HINT = re.compile(
    r"\\?\s*(USA|United States|UK|United Kingdom|Canada|Germany|France|India|China|"
    r"Australia|Spain|Netherlands|Sweden|Singapore|Israel|Brazil|Japan|Ireland)\b"
)

_YC_BATCH = re.compile(r"\b([SWF])(?:ummer|inter|all)?\s?[' ]?(\d{2})\b")

_STATUS = re.compile(r"\b(acquired|shut ?down|dead|closed|active|operating|bankrupt\w*)\b", re.IGNORECASE)


def parse_money(text: str) -> float | None:
    """First money figure that sits near funding language."""
    for match in _MONEY.finditer(text):
        window = text[max(0, match.start() - 90) : match.end() + 60]
        if not _FUNDING_CUE.search(window):
            continue
        amount = float(match.group(1).replace(",", ""))
        unit = (match.group(2) or "").lower()
        if unit.startswith("thousand"):
            unit = "k"
        elif unit.startswith("million"):
            unit = "m"
        elif unit.startswith("billion"):
            unit = "b"
        elif unit.startswith("trillion"):
            unit = "t"
        return amount * _MULTIPLIER.get(unit, 1.0)
    return None


def parse_shutdown_year(text: str) -> int | None:
    for pattern in (_SHUTDOWN_YEAR, _YEAR_SHUTDOWN):
        match = pattern.search(text)
        if match:
            groups = [g for g in match.groups() if g]
            year = "".join(groups[-2:]) if len(groups[-1]) == 2 else groups[-1]
            try:
                value = int(year)
            except ValueError:
                continue
            if 1980 <= value <= 2100:
                return value
    return None


@dataclass
class ParsedPage:
    url: str
    name: str | None = None
    description: str | None = None
    cause: str | None = None
    industry: str | None = None
    country: str | None = None
    founded_year: int | None = None
    shutdown_year: int | None = None
    funding_usd: float | None = None
    status: str | None = None
    batch: str | None = None
    text: str = ""
    fields_from_rules: list[str] = field(default_factory=list)
    needs_ai: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data.pop("text", None)
        return data


# Sections that state the reason, in the wording these sites actually use.
_CAUSE_HEADINGS = re.compile(
    r"(why (?:did |does )?.{0,40}?(?:fail|shut ?down|die)|failure analysis|reason[s]? for failure|"
    r"what went wrong|cause of (?:death|failure)|post[- ]?mortem)",
    re.IGNORECASE,
)

# Site furniture that sits under a matching heading but says nothing useful.
_CAUSE_NOISE = re.compile(
    r"(this report was generated|did we get something wrong|subscribe|newsletter|"
    r"cookie|sign in|more unicorn|read more|share this|advertisement)",
    re.IGNORECASE,
)

# Headings that begin the *next* section - the cause text stops here.
_NEXT_SECTION = re.compile(
    r"^(market analysis|startup learnings?|market potential|difficulty|scalability|"
    r"timeline|what they built|founding story|overview|company facts|sources|"
    r"actionable insights|go on reading|related|more from|lessons learned)\b",
    re.IGNORECASE,
)


def _cause_from_text(text: str) -> str | None:
    lines = text.split("\n")
    best: str | None = None
    for index, line in enumerate(lines):
        if len(line) > 120 or not _CAUSE_HEADINGS.search(line):
            continue
        body: list[str] = []
        for following in lines[index + 1 : index + 12]:
            # Stop at the next section, or at any heading-looking line.
            if _NEXT_SECTION.match(following.strip()):
                break
            if len(following) < 60 and following.endswith(("?", ":")):
                break
            body.append(following)
            if sum(len(b) for b in body) > 900:
                break
        joined = " ".join(body).strip()
        if len(joined) < 100 or _CAUSE_NOISE.search(joined[:200]):
            continue
        # Keep the richest qualifying section.
        if best is None or len(joined) > len(best):
            best = joined
    return best[:1500] if best else None


_GENERIC_NAME = re.compile(
    r"^(startups?\.rip|failory|loot ?drop|home|untitled|404|not found)$", re.IGNORECASE
)


def _clean_name(raw: str) -> str:
    """Strip the site furniture sites append to titles."""
    cleaned = re.split(r"\s*[|·—–]\s*", raw)[0]
    cleaned = re.sub(
        r"\s*[-–—]\s*(why this startup failed|failed startup case study|startup cemetery|"
        r"startups\.rip|failory|loot drop).*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s*\((?:[SWF]\d{2})\)\s*$", "", cleaned)  # YC batch suffix
    cleaned = re.sub(r"\s*\\\s*[A-Z]{2,}\s*$", "", cleaned)  # "Plenty Unlimited \USA"
    return cleaned.strip(" -–—:|")


def parse_page(url: str, html: str) -> ParsedPage:
    result = ParsedPage(url=url)
    text = visible_text(html)
    result.text = text
    used: list[str] = []

    headings = _headings(html)

    # Name: gather every candidate, then take the tightest sensible one. Sites
    # disagree about which slot holds the company vs the article title -
    # Failory's JSON-LD headline is "What Happened to Wesabe and Why...", while
    # its <h1> is simply "Wesabe".
    candidates: list[tuple[str, str]] = []
    for block in _json_ld(html):
        block_type = str(block.get("@type", ""))
        if block_type in ("Article", "BlogPosting", "NewsArticle", "Organization", "Product"):
            headline = block.get("headline") or block.get("name")
            if headline:
                candidates.append((str(headline), "json-ld"))
            if not result.description and block.get("description"):
                result.description = str(block["description"])
                used.append("description:json-ld")

    for key in ("og:title", "twitter:title"):
        value = _meta(html, key)
        if value:
            candidates.append((value, "meta"))
    if headings:
        candidates.append((headings[0], "h1"))

    scored: list[tuple[int, str, str]] = []
    for raw, origin in candidates:
        cleaned = _clean_name(raw)
        if len(cleaned) < 2 or _GENERIC_NAME.match(cleaned):
            continue
        scored.append((len(cleaned), cleaned, origin))
    if scored:
        scored.sort(key=lambda item: item[0])
        _, result.name, origin = scored[0]
        used.append(f"name:{origin}")

    if not result.description:
        description = _meta(html, "description") or _meta(html, "og:description")
        if description:
            result.description = description
            used.append("description:meta")

    haystack = "\n".join(filter(None, [result.description, text]))

    result.funding_usd = parse_money(haystack)
    if result.funding_usd is not None:
        used.append("funding:regex")

    result.shutdown_year = parse_shutdown_year(haystack)
    if result.shutdown_year:
        used.append("shutdown_year:regex")

    founded = _FOUNDED_YEAR.search(haystack)
    if founded:
        result.founded_year = int(founded.group(1))
        used.append("founded_year:regex")

    country = _COUNTRY_HINT.search("\n".join(headings[:3]) or haystack[:600])
    if country:
        result.country = country.group(1)
        used.append("country:regex")

    batch = _YC_BATCH.search(" ".join(headings[:3]))
    if batch:
        result.batch = f"{batch.group(1).upper()}{batch.group(2)}"
        used.append("batch:regex")

    status = _STATUS.search(" ".join(headings[:6]))
    if status:
        result.status = status.group(1).lower().replace(" ", "")
        used.append("status:regex")

    result.cause = _cause_from_text(text)
    if result.cause:
        used.append("cause:headings")

    # A company cannot shut down before it was founded. When the regexes
    # disagree, drop the shutdown year rather than publish an impossible span.
    if (
        result.founded_year
        and result.shutdown_year
        and result.shutdown_year < result.founded_year
    ):
        result.shutdown_year = None
        used = [f for f in used if f != "shutdown_year:regex"]

    result.fields_from_rules = used

    # What the AI pass should be asked for. Name is excluded: if rules could
    # not find a name the page is almost certainly not a company page.
    missing = []
    if not result.cause:
        missing.append("cause")
    if not result.industry:
        missing.append("industry")
    if result.funding_usd is None:
        missing.append("funding_usd")
    if result.shutdown_year is None:
        missing.append("shutdown_year")
    result.needs_ai = missing

    return result


def looks_like_company_page(parsed: ParsedPage) -> bool:
    """Filter out round-ups and index pages that slipped through the URL rules."""
    if not parsed.name:
        return False
    name = parsed.name.lower()
    if re.search(r"^\s*(top|best|the full list|\d+\s+\w+\s+startups)\b", name):
        return False
    if re.search(r"\b(not found|404|error)\b", name):
        return False
    return len(parsed.text) > 400
