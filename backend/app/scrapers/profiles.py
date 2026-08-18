"""Site definitions.

A profile says where a site lists its companies and how to tell a real
post-mortem from a listicle. The three built-in profiles were verified against
the live sites; `generic_profile()` covers any site added later from the UI.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse


@dataclass
class SiteProfile:
    key: str
    name: str
    base_url: str
    sitemap_url: str
    # Only sitemap URLs matching this are treated as company pages.
    url_pattern: str
    # Slugs matching these are round-ups and comparison posts, not companies.
    exclude_pattern: str | None = None
    notes: str = ""
    seed_urls: list[str] = field(default_factory=list)

    def matches(self, url: str) -> bool:
        if not re.search(self.url_pattern, url):
            return False
        if self.exclude_pattern and re.search(self.exclude_pattern, url, re.IGNORECASE):
            return False
        # A bare section index ("/cemetery") is not a company page.
        path = urlparse(url).path.rstrip("/")
        return bool(path.rsplit("/", 1)[-1])


# Verified live: /startups/ on Failory is listicles ("Top 37 3D Printing
# Startups"), the actual post-mortems live under /cemetery/.
FAILORY = SiteProfile(
    key="failory",
    name="Failory Startup Cemetery",
    base_url="https://www.failory.com",
    sitemap_url="https://www.failory.com/sitemap.xml",
    url_pattern=r"/cemetery/[^/]+$",
    notes="Post-mortems with an explicit 'Why did X fail?' section.",
)

LOOT_DROP = SiteProfile(
    key="loot_drop",
    name="Loot Drop Startup Graveyard",
    base_url="https://www.loot-drop.io",
    sitemap_url="https://www.loot-drop.io/sitemap.xml",
    url_pattern=r"/startup/[^/]+$",
    notes="Case studies carrying JSON-LD plus funding burnt in the description.",
)

STARTUPS_RIP = SiteProfile(
    key="startups_rip",
    name="Startups.RIP",
    base_url="https://startups.rip",
    sitemap_url="https://startups.rip/sitemap.xml",
    url_pattern=r"/company/[^/]+$",
    notes="Y Combinator companies, dead or acquired, with batch labels.",
)

BUILT_IN: dict[str, SiteProfile] = {
    profile.key: profile for profile in (FAILORY, LOOT_DROP, STARTUPS_RIP)
}


def generic_profile(
    key: str,
    name: str,
    base_url: str,
    sitemap_url: str | None = None,
    url_pattern: str | None = None,
    exclude_pattern: str | None = None,
) -> SiteProfile:
    """Profile for a site the user adds later.

    Defaults assume the common shape: a sitemap at the root, and company pages
    one level deep. Both are overridable from the dashboard.
    """
    parsed = urlparse(base_url)
    root = f"{parsed.scheme or 'https'}://{parsed.netloc}"
    return SiteProfile(
        key=key,
        name=name,
        base_url=root,
        sitemap_url=sitemap_url or f"{root}/sitemap.xml",
        url_pattern=url_pattern or r"/[^/]+/[^/]+$",
        exclude_pattern=exclude_pattern
        or r"(top-\d|best-|list|guide|accelerators|incubators|vs-|\bhow-to\b)",
        notes="User-added site.",
    )
