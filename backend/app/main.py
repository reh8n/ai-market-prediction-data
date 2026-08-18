import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import init_db
from app.routers import (
    chat,
    companies,
    dataset,
    discover,
    enrich,
    export,
    market,
    scrape,
    search,
    sources,
    training,
)

logging.basicConfig(level=logging.INFO)

settings = get_settings()

app = FastAPI(
    title="AI Market Prediction Data",
    description="Collects and structures company success/failure research for a "
    "stock-prediction model.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sources.router)
app.include_router(companies.router)
app.include_router(search.router)
app.include_router(export.router)
app.include_router(market.router)
app.include_router(training.router)
app.include_router(scrape.router)
app.include_router(dataset.router)
app.include_router(discover.router)
app.include_router(enrich.router)
app.include_router(chat.router)


@app.on_event("startup")
def on_startup() -> None:
    init_db()

    from app.db import SessionLocal
    from app.scrapers.run import seed_builtin_sites

    db = SessionLocal()
    try:
        seed_builtin_sites(db)
    finally:
        db.close()


@app.get("/health", tags=["meta"])
def health():
    return {
        "status": "ok",
        "database": settings.database_url.split("://", 1)[0],
        "extraction_provider": settings.extraction_provider,
        "whisper_fallback": settings.enable_whisper_fallback,
    }
