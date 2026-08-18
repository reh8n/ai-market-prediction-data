# Handoff

Read this before changing anything. It is written for whoever picks the project
up next — human or AI assistant — and covers what the system is, what is real
versus not yet wired, and the traps that cost time here.

---

## What this is

A platform that builds **training data for a stock-market prediction model**. It
collects three views of business outcomes and joins them into one fine-tuning
file:

1. **Failed businesses** scraped from public post-mortem sites — what a company
   was and why it died.
2. **YouTube transcripts** — market commentary and trading-technique videos.
3. **Market data** — what a public company filed with the SEC, next to what its
   stock actually did.

The deliverable is `GET /training/export.jsonl`: one training example per line,
each a `{"messages": [system, user, assistant]}` object. Everything else feeds
that file.

**Stack:** FastAPI + SQLAlchemy 2.0 + SQLite (Postgres optional) on the backend;
React 18 + Vite + TypeScript on the frontend. Background jobs run on FastAPI
`BackgroundTasks` — no Celery, no Redis.

---

## First run

Follow the Quick start in [README.md](README.md). Two things to expect:

- **You start with zero data.** The database ships empty by design (`backend/data/`
  is gitignored). Collect some from the **Businesses** tab before judging
  anything.
- **AI extraction is off** until a key is supplied. Transcripts and pages are
  still collected and stored; nothing is *read out* of them.

Verify the install in one call:

```bash
curl localhost:8000/health
```

---

## Ground truth you must not get wrong

These four facts explain most of what looks like a bug but is not.

**1. Failed startups have no ticker.** They are private and never listed, so SEC
financials and stock prices *cannot exist* for them. This is not missing data.
Any plan to "fill in the market data for the failures" is based on a
misunderstanding — the correct move is to sync public tickers separately.

**2. The corpus therefore has two shapes on purpose.** Private failures teach
*why businesses die*; public tickers teach *price versus filed finances*. A
record that is both (23andMe listed, then went bankrupt) is rare and the most
valuable kind.

**3. "Skipped" counts are per-subject, not per-builder.** Every training builder
runs over every record, so a private company fails `company_outcome` while
succeeding as `business_failure`. A subject is only reported skipped when it
produced **no** example of any type. If you change this, do not reintroduce the
double-count — it made the UI claim 541 records were unusable when only 5 were.

**4. Extraction rows written by the null provider are placeholders.** They have
`provider='null'`. Anything checking "has this been extracted?" must exclude
them, or every video looks processed and is skipped forever.

---

## Architecture map

```
backend/app/
  main.py              app + router registration
  config.py            every setting, with working defaults
  db.py                engine + SQLite WAL setup  ← see Traps
  models.py            all tables
  routers/             one file per endpoint group
  scrapers/            failed-business scraping
    fetcher.py         robots.txt gate, per-host rate limit, backoff
    profiles.py        the three verified sites + user-added ones
    discover.py        sitemap → company page URLs
    parse.py           JSON-LD → meta → headings → regex
    run.py             job orchestration and filtering
  pipeline/            YouTube + AI extraction
    discovery.py       yt-dlp search / channel feeds, quality screening
    youtube_scraper.py captions first, Whisper fallback
    extractor.py       provider-agnostic structured extraction
    enrich_run.py      backfill extraction over already-stored records
  market/              tickers, prices, SEC financials
  training/builder.py  joins everything into fine-tuning examples
  analyst/             the in-app chat analyst
    tools.py           eight read-only views it can call
    backends.py        Anthropic + OpenAI-protocol tool loops
frontend/src/
  design-system/       vendored kit — treat as READ-ONLY, re-drop to update
  components/          AppShell + one file per screen
  api.ts               typed client
```

---

## Traps that will cost you time

**SQLite must stay in WAL mode.** `db.py` sets `journal_mode=WAL`,
`busy_timeout=30000`, and commits per record. Without this, concurrent scrape
jobs deadlock: each holds a write transaction across slow network calls and the
others block forever. It presents as jobs stuck at `fetched=0` while one
completes — it looks like a network problem and is not.

**Never call a FastAPI route as a plain Python function.** Unset `Query(...)`
defaults stay as `Query` objects, which are *truthy*. A filter like
`if source and source != origin` then rejects every row and the endpoint returns
empty with no error. Extract shared logic into a plain helper — see
`_collect_records()` in `routers/dataset.py`.

**Failory's `/startups/` path is listicles, not failures.** The real post-mortems
are under `/cemetery/`. The obvious-looking path yields 1,243 articles like "Top
37 3D Printing Startups".

**`youtube-transcript-api` must stay on 1.x.** The 0.6.x API is different and
breaks against current YouTube with a bare XML parse error.

**Discovery rejects most of what it finds, and that is correct.** A run finding
16 videos and keeping 3 is healthy — raw YouTube search returns AI-narrated
slideshows with 11 views. Rejection reasons are recorded on the job.

**Nothing holds a database write lock across a network call.** If you add a job
runner, keep that property.

---

## Current state

**Works and verified end to end:**

- Failed-business scraping from three sites, with filters
- YouTube auto-discovery (no API key — yt-dlp searches unauthenticated) and
  transcript ingestion
- SEC financials + daily price history per ticker
- Training export, four example types
- The analyst chat, across Anthropic and OpenAI-compatible providers
- The dataset endpoints an external model pulls from

**Deliberately not done:**

- **No authentication.** Every read endpoint is open, by the owner's explicit
  choice. Fine on localhost, unsafe anywhere else. `API_KEY` exists in config
  for when that changes — wire it before any deployment.
- **No database migrations.** Schema changes currently mean rebuilding a dev
  database. Add Alembic before this holds data anyone cares about.
- **No tests.** Verification so far has been live runs against real sites and
  stubbed API clients.
- **No intraday price bars.** yfinance serves ~60 days of 1-minute history,
  too shallow to backfill setup labels; daily is the honest granularity.

**Known-thin data:** the `industry` field is empty on every scraped record —
the source sites rarely state it. Country and funding are well populated.
Running an extraction backfill fills industry in.

---

## If you are an AI assistant working on this

- **Read [README.md](README.md) first** — it documents each subsystem and why it
  is built the way it is.
- **Check the four ground-truth facts above** before "fixing" a data gap. Most
  apparent gaps are real-world constraints, not defects.
- **The design system is vendored and read-only.** Its rules are in
  `frontend/src/design-system/BRAND.md`. Read that before any UI change — the
  look is load-bearing. App-specific styling goes in `styles.css` or the screen
  components.
- **Verify against live data, not assumptions.** Every count in this project was
  wrong at least once before it was checked. `GET /dataset/manifest` and the
  Analyst tab both report real state.
- **Do not commit `.env` or `backend/data/`.** Both are gitignored; keep it that
  way. API keys in this system travel per-request and are never persisted —
  preserve that property if you touch the chat or extraction paths.
- **Prefer adding a provider to `analyst/backends.py`** over a new integration:
  anything OpenAI-compatible is a dictionary entry, not new code.

---

## Where to start

| Goal | Do this |
|---|---|
| See it working | Businesses tab → Loot Drop → 25 records |
| Get real training data | Collect businesses, then Training → Download .jsonl |
| Turn on AI extraction | Paste a key on the Analyst tab, then Training → Backfill |
| Add market data | Market tab → sync a ticker (try `AAPL`) |
| Understand the data | Analyst tab → "What is in this dataset right now?" |
| Feed another model | `GET /dataset/manifest` — self-describing |
