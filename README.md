# AI Market Prediction Data

Builds a training corpus for a market-prediction model by joining three views of
the same company: **what people say** (YouTube transcripts), **what the company
actually is** (SEC filings), and **what the market thinks it's worth** (price
history).

```
Topic/channel ─► video search ─► screened ─┐
YouTube URL  ──────────────────────────────┴► transcript ─► classify ─┬─► company facts ─┐
                                                                      └─► trading setups │
Failure sites ─► scraped pages ─► rules + AI ─► businesses ────────────────────────────  ┤
                                                                                         ├─► /dataset/*
SEC EDGAR    ─► filed financials ────────────────────────────────────────────────────────┤   training.jsonl
yfinance     ─► daily price bars ────────────────────────────────────────────────────────┘
```

**Private failures have no ticker.** None of the scraped companies do — they
never listed. Market data only exists for public companies, so the corpus has
two shapes on purpose: failures teach *why businesses die*, tickers teach *price
versus filed finances*. A handful of records are both (23andMe listed, then went
bankrupt), and those are the most valuable rows in the set.

Nothing but the AI extraction step needs an API key.

## Quick start (local, no Docker)

Needs **Python 3.11+** and **Node 18+**. Nothing else — no database server, no
API key to get it running.

### Windows (PowerShell)

Backend:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
.venv\Scripts\uvicorn app.main:app --port 8000 --reload
```

Frontend, in a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

> If PowerShell blocks the activation script, you do not need to activate at
> all — calling `.venv\Scripts\uvicorn` directly (as above) sidesteps the
> execution policy entirely.

### macOS / Linux

```bash
cd backend
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cp .env.example .env
./.venv/bin/uvicorn app.main:app --port 8000 --reload
```

```bash
cd frontend
npm install
npm run dev
```

### Then

Dashboard: http://localhost:5173 — API docs: http://localhost:8000/docs

First run creates `backend/data/` and an empty SQLite database, and registers
the three built-in scraper sites. **You start with no data** — that is expected.
Go to **Businesses**, pick a site, and collect some; or **Discover** to pull
video transcripts. `docker-compose.yml` swaps in Postgres when you want it.

The `.env` file is optional. Every setting has a working default, so the app
runs with no configuration at all; copy the example only when you want to change
something.

## Enabling AI extraction

Out of the box `EXTRACTION_PROVIDER=null`, so transcripts are collected but no
structured company data is produced. To turn extraction on, set in `backend/.env`:

```
EXTRACTION_PROVIDER=anthropic     # or: openai
EXTRACTION_API_KEY=sk-...
```

`anthropic` is already installed. The provider lives behind the `Extractor`
interface in [extractor.py](backend/app/pipeline/extractor.py) — adding another
means a subclass and a line in `get_extractor()`; nothing else changes.

**A key set later does not touch existing records.** Extraction runs inline
during a scrape or ingest, so everything collected beforehand stays as it was.
`GET /enrich/status` reports the gap, and a backfill closes it:

```bash
curl localhost:8000/enrich/status
curl -X POST "localhost:8000/enrich/run?target=pages"    # scraped businesses
curl -X POST "localhost:8000/enrich/run?target=sources"  # video transcripts
```

Backfill re-reads saved page text and stored transcripts — sites are never
re-crawled for bytes already on disk. Both buttons live on the **Training**
screen and stay disabled until a key is configured.

> Rows written by the null provider are placeholders, not extractions. The
> backfill treats `provider='null'` as unread, otherwise every video would look
> already-processed and be skipped forever.

## Videos without captions

Caption scraping is free and needs no API key, but only works when the video has
captions. For videos without them, enable the Whisper fallback:

```
ENABLE_WHISPER_FALLBACK=true
```

and `pip install faster-whisper` (plus `ffmpeg` on the host). It downloads audio
via yt-dlp and transcribes locally — much slower, so it stays off by default.

## Two kinds of video, auto-routed

Transcripts are classified before extraction, because trading-education content
and company analysis contain completely different facts:

| Classified as | Example channel | Extracted into |
|---|---|---|
| `company_analysis` | business post-mortems, earnings commentary | companies, outcomes, ROI, causes |
| `trading_technique` | TJR Boot Camp and similar | setups: trigger, entry, stop, target, risk rule |
| `mixed` | both in one video | both schemas run |
| `other` | neither | nothing, recorded with a reason |

The router is why a day-trading video does not get forced through a
company-outcome schema and come back empty.

## Video auto-discovery

Finding videos, rather than being handed URLs. Run it from the **Discover**
screen or `POST /discover/run`. No YouTube API key: yt-dlp can run a search and
list a channel's uploads unauthenticated.

Pick a topic instead of writing query strings — each expands into several
phrasings, because YouTube's ranking is wording-sensitive and one phrasing
misses obvious videos:

| Topic | Finds |
|---|---|
| `business_failure` | Post-mortems: FTX, SVB, Boeing, BYJU'S |
| `company_analysis` | Fundamentals, earnings, valuation breakdowns |
| `trading_technique` | Setups, entries, stops — the TJR Boot Camp shape |
| `market_events` | Crashes, short squeezes, sector moves |

Free-text terms work too, as does a channel handle (`@GaryVee`).

**Rejecting is most of the job.** A raw search for "why startups fail" returns
AI-narrated slideshows with 11 views next to real post-mortems. Every candidate
is screened on view count, duration, and — the important one — whether captions
actually exist, checked before queueing rather than discovered after. A typical
run finds 16 and keeps 3; that ratio is health, not failure, so the job records
each rejection reason.

`POST /discover/preview` runs the same search and shows what would be kept
without saving anything. It skips the caption check, which is the slow step, so
it answers "are my filters sane?" in seconds.

With `auto_ingest` (the default) each kept video is scraped and extracted in the
same run — subject in, transcripts out, no URLs typed.

```bash
curl -X POST localhost:8000/discover/run \
  -H 'Content-Type: application/json' \
  -d '{"topics": ["trading_technique"], "limit": 10, "min_views": 200000}'
```

> Regional English matters here. Plenty of finance YouTube is `en-IN`, and
> asking YouTube to translate `en-IN` into `en` fails — a regional English track
> cannot be translated to English. Those videos are fetched directly instead.
> Before that fix they reported "no captions" while plainly having them.

## Failed-business scraper

Finds companies that failed, and why, from public post-mortem sites. Run it from
the **Businesses** screen or `POST /scrape/run`.

| Site | Records | Company pages |
|---|---:|---|
| Failory Startup Cemetery | ~135 | `/cemetery/<slug>` |
| Loot Drop Startup Graveyard | ~1,000 | `/startup/<slug>` |
| Startups.RIP | ~1,000 | `/company/<slug>` |

> Failory's `/startups/` path looks right but is listicles ("Top 37 3D Printing
> Startups"). The real post-mortems are under `/cemetery/`. Verified against the
> live site — worth re-checking if you add a similar source.

**Filters:** how many to fetch, industry, shutdown year range, funding raised
range. `limit` counts records actually kept, not pages visited, so filters never
leave you short.

**Reading a page** is rules-first: JSON-LD (the site's own structured data) →
meta tags → headings → regex for money and years. An AI pass fills only the
fields the rules missed, and only when a key is set — so the scraper works with
no key at all, just with sparser records. Every record stores which fields came
from rules and which from AI, in `field_sources`.

**Being a good citizen:** robots.txt is checked before every request and its
`Crawl-delay` is honoured when longer than the local default (1.5s); `429`/`503`
back off; already-scraped URLs are skipped so re-running tops up rather than
repeats.

Adding a site is a form, not a code change — paste its address on the
**Businesses** screen. It reads that site's sitemap and applies the same rules.

```bash
curl -X POST localhost:8000/scrape/run \
  -H 'Content-Type: application/json' \
  -d '{"site_key": "loot_drop", "limit": 25, "funding_min": 50000000}'
```

## The analyst

The **Analyst** tab is a chat that answers questions about your own data. It
has eight read-only tools, so it looks the numbers up before answering rather
than estimating them.

**Any provider works.** Anthropic and OpenAI are recommended — they handle tool
calling most reliably, which is the whole point. Everything else speaks the
OpenAI chat-completions protocol, so Groq, OpenRouter, Together, DeepSeek,
Mistral and any local server (Ollama, vLLM) work by supplying a base URL.

| Provider | Protocol | Default model |
|---|---|---|
| Anthropic **(recommended)** | native | `claude-opus-5` |
| OpenAI **(recommended)** | chat-completions | `gpt-4o` |
| Groq / OpenRouter / Together / DeepSeek / Mistral | chat-completions | per-vendor |
| Other (OpenAI-compatible) | chat-completions | you supply base URL + model |

Leave the provider on **auto** and it is inferred from the key's prefix —
`sk-ant-` is Anthropic, `gsk_` is Groq, `sk-or-` is OpenRouter, anything else
falls through to the OpenAI protocol.

```bash
curl localhost:8000/chat/capabilities        # model, key handling, tool list
```

**Read-only by design.** It can search businesses, read filed financials and
price history, count training examples, and inspect recent jobs. It cannot start
a scrape, sync a ticker, or change a setting — so no sentence it produces can
cost you a run.

**The key is per-request.** You type it into the browser; it is sent with each
question and used for that request only. Nothing writes it to disk or to the
database, and no code path logs it. Refreshing the page clears it.

The same key also enables the Training tab's backfill buttons, sent as an
`X-Extraction-Key` header rather than a query parameter — query strings end up
in access logs and browser history.

> A wrong key is rejected before a backfill job starts, via a token-free
> `models.list` probe. Without that check the job would run to completion and
> change nothing, because per-record enrichment swallows its own errors.

## Feeding another model

`GET /dataset/manifest` is the front door: it reports what is stored, every
endpoint, the filters each accepts, and where the data came from. A consuming
model can discover the whole shape from that one call.

| Endpoint | Returns |
|---|---|
| `/dataset/manifest` | Counts, endpoints, filters, provenance |
| `/dataset/records` | Business records, paginated (`total`, `next_offset`) |
| `/dataset/records.jsonl` | The same records, one JSON object per line |
| `/dataset/setups` | Trading setups from tutorial videos |
| `/training/export.jsonl` | Ready-to-train instruction pairs |

```bash
curl "localhost:8000/dataset/records?has_cause=true&funding_min=100000000"
curl "localhost:8000/dataset/records.jsonl" -o records.jsonl
```

Filters: `outcome`, `industry`, `country`, `year_min`, `year_max`,
`funding_min`, `funding_max`, `has_cause`, `source`.

## Training data

`GET /training/export.jsonl` is the deliverable. Each line is a
`{"messages": [system, user, assistant]}` object — the format Anthropic, OpenAI
and most open-weight fine-tuners accept. Three example types:

| Type | Input | Target | Label source |
|---|---|---|---|
| `business_failure` | scraped company profile | why it failed | **the source's own post-mortem** |
| `market_vs_finances` | filings + price action | 1-year forward return | **measured, not judged** |
| `company_outcome` | filings + price action + commentary | outcome, ROI, assessment | AI extraction |
| `trading_setup` | taught approach | executable rule set | AI extraction |

`market_vs_finances` needs no AI key at all — the label is the realized forward
return computed from stored bars, so those rows are ground truth rather than
model opinion.

**Skipped counts are per-subject, not per-builder.** Every builder runs over the
same records, so a private company with no ticker fails `company_outcome` while
succeeding as `business_failure`. Reporting both would claim hundreds of records
are untrainable when they are already in the corpus — a subject is only listed
as skipped when it produced no example of any kind.

```bash
curl "localhost:8000/training/export.jsonl?kinds=market_vs_finances" -o train.jsonl
```

Filter with repeated `kinds=`, and pass `include_metadata=false` for a bare
messages-only file.

## API

| Endpoint | Purpose |
|---|---|
| `POST /discover/run` | **Find videos by subject** and ingest them. |
| `POST /discover/preview` | Same search, saves nothing — check your filters. |
| `GET /discover/topics` | The curated subjects and their queries. |
| `GET /discover/jobs` | Discovery runs with found/kept/read counts. |
| `POST /sources/youtube` | Queue a video. Returns immediately with `status: pending`. |
| `GET /sources` / `GET /sources/{id}` | Job status; `?include_transcript=true` for raw text. |
| `GET /search?q=` | Search companies, events, and sources. |
| `GET /export/data` | Structured company records. Filters: `outcome`, `min_roi`, `company_id`. |
| `POST /market/instruments` | Sync a ticker: quote, 5y daily bars, all SEC figures. |
| `GET /market/instruments/{ticker}` | Price returns, volatility, filed financials, derived ratios. |
| `GET /market/search?q=` | Ticker lookup against the SEC company list. |
| `GET /training/preview` | Example counts plus rendered samples. |
| `GET /training/export.jsonl` | **The training file.** |
| `POST /chat` | Ask the analyst a question. Key in the body, per request. |
| `GET /chat/capabilities` | Model, key handling, and the analyst's tool list. |
| `GET /enrich/status` | Extraction config plus what a backfill would fill. |
| `POST /enrich/run` | Backfill extraction (`target=pages\|sources`). |
| `GET /health` | Config sanity check. |

```bash
curl -X POST localhost:8000/sources/youtube \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://www.youtube.com/watch?v=VIDEO_ID"}'

curl -X POST localhost:8000/market/instruments \
  -H 'Content-Type: application/json' \
  -d '{"ticker": "NKE"}'
```

## Market data sources

| Source | Gives | Key | Caveat |
|---|---|---|---|
| SEC EDGAR XBRL | Audited figures as filed in 10-K/10-Q | none | US registrants only — no ETFs, indices, or foreign listings |
| yfinance | Daily OHLCV, sector, market cap | none | Unofficial Yahoo endpoints; can break without notice |

Financials are the authoritative side of the comparison; prices are enrichment.
A price-sync failure never fails a company record.

Ticker resolution is deliberately strict — exact or single clean prefix match
only. A fuzzy match would silently attach the wrong company's financials to a
transcript, which is worse than leaving it unlinked.

## Layout

```
backend/app/
  models.py            companies, events, sources, transcripts, extractions,
                       trading setups, instruments, price bars, financials
  routers/             sources, companies, search, export, market, training
  analyst/
    tools.py           eight read-only views the chat analyst can call
    agent.py           system prompt + provider dispatch
    backends.py        Anthropic and OpenAI-protocol tool loops
  pipeline/
    enrich_run.py      backfill extraction over already-stored records
    discovery.py       yt-dlp search + channel feeds, quality screening
    discover_run.py    discovery job: search -> queue -> ingest
    youtube_scraper.py captions first, Whisper fallback
    schemas.py         the three extraction schemas + the router prompt
    extractor.py       classify, then run the matching schema
    run.py             scrape -> transcribe -> classify -> extract -> link
  scrapers/
    fetcher.py         robots gate, per-host rate limit, backoff
    profiles.py        the three verified sites + user-added ones
    discover.py        sitemap -> company page URLs
    parse.py           JSON-LD -> meta -> headings -> regex
    enrich.py          the AI pass, for missed fields only
    run.py             job orchestration and filtering
  market/
    tickers.py         SEC ticker/CIK map, name resolution
    prices.py          yfinance bars, returns, volatility
    financials.py      EDGAR XBRL facts, ratios, growth
    sync.py            persistence for all of the above
  training/
    builder.py         joins everything into fine-tuning examples
frontend/src/
  design-system/       vendored Market Signal Research kit (see below)
  components/          AppShell + the six screens
  api.ts               typed client for the FastAPI endpoints
backend/data/
  transcripts/{id}.json  raw transcript + segments + metadata
  audio/                 only used by the Whisper fallback
```

## Design system

The UI is built on the supplied **Market Signal Research** design system, vendored
into [frontend/src/design-system](frontend/src/design-system). Its rules live in
[BRAND.md](frontend/src/design-system/BRAND.md) — read that before changing any
UI, since the look is load-bearing rather than decorative.

The short version: blueprint grid page, white `SketchPanel` containers with
uneven hand-drawn radii, IBM Plex Mono throughout, one navy ink ramp plus a
single blue accent, and status colour confined to badges and dots. Section
labels are `UPPERCASE // JOINED WITH SLASHES`; copy is terse and impersonal;
numbers always carry their unit and `—` stands in for null. Caveat handwriting
is for margin asides only.

**Treat `design-system/` as read-only** — re-drop the folder to update it rather
than editing components in place. App-specific styling goes in
[styles.css](frontend/src/styles.css) or the screen components.

Screens include **Analyst** (chat over your own data) alongside **Dataset** (search + source table + pipeline metrics), **Discover**
(topic picker, filters, preview, run history), **Ingest**
(submission form + queue + pipeline stages), **Records** (`/export/data` as the
model sees it), **Market** (price action beside filed revenue), **Training**
(corpus counts, rendered samples, `.jsonl` download), and the source detail view
(transcript vs extracted JSON, plus any trading setups).

Two substitutions carried over from the kit, both flagged in BRAND.md: the fonts
are Google Fonts stand-ins (no binaries were supplied) and "Market Signal
Research" is a placeholder product name.

## Notes / next steps

- Search is portable `ILIKE`. Postgres full-text (`tsvector`) is the next step,
  then `pgvector` for semantic search over transcripts.
- Jobs run on FastAPI `BackgroundTasks` — fine for one server, no queue needed.
  Move to Celery + Redis if volume outgrows it.
- **No auth, by choice.** Every read endpoint is open, so anything that can reach
  the address can pull the whole dataset. Fine on localhost, unsafe anywhere
  else. `API_KEY` exists in config for when that changes.
- **SQLite runs in WAL mode.** Without it, concurrent scrape jobs deadlocked —
  each held a write transaction across slow network calls. The runner also
  commits per record so no write lock spans a fetch.
- Extraction failures don't fail a source: the transcript is still saved and the
  error recorded, since a transcript without extraction is still useful data.
- The schema changed when market data landed. There are no migrations yet, so a
  dev database is rebuilt rather than migrated — add Alembic before this holds
  data you care about.
- Intraday bars are not stored. yfinance serves roughly 60 days of 1-minute
  history, which is too shallow to backfill setup labels; daily is the honest
  granularity today.
- **Discovery finds videos, not tickers.** There is no auto-scan of the whole
  market; syncing an instrument is still a deliberate call, because a wrong
  ticker match staples the wrong company's financials to a record.
- Ideas not built yet: news/RSS ingestion, source reliability weighting, entity
  dedup across videos, human review UI before rows reach the training export,
  and backtesting extracted setups against stored bars.
