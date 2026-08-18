from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/market.db"
    data_dir: str = "./data"

    extraction_provider: str = "null"
    extraction_api_key: str = ""
    extraction_model: str = ""

    enable_whisper_fallback: bool = False
    whisper_model: str = "base"

    # The SEC blocks anonymous traffic; it wants an app name and contact address.
    sec_user_agent: str = "AI Market Prediction Data research@example.com"
    price_history_period: str = "5y"

    # Web scraping. Identify honestly and leave a gap between requests - the
    # delay is a floor, and a site's own Crawl-delay overrides it upward.
    scraper_user_agent: str = (
        "MarketSignalResearch/0.1 (+research contact: research@example.com)"
    )
    scraper_delay_seconds: float = 1.5
    scraper_max_pages: int = 500

    # Leave the read endpoints open (localhost only) or require a key.
    api_key: str = ""

    cors_origins: str = "http://localhost:5173"

    @property
    def data_path(self) -> Path:
        return Path(self.data_dir).resolve()

    @property
    def transcripts_path(self) -> Path:
        return self.data_path / "transcripts"

    @property
    def audio_path(self) -> Path:
        return self.data_path / "audio"

    @property
    def scraped_path(self) -> Path:
        return self.data_path / "scraped"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def ensure_dirs(self) -> None:
        self.transcripts_path.mkdir(parents=True, exist_ok=True)
        self.audio_path.mkdir(parents=True, exist_ok=True)
        self.scraped_path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
