from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", env_prefix="AGRISENSE_", extra="ignore")

    database_url: str = "postgresql+psycopg://agrisense:agrisense@localhost:5432/agrisense"

    # Chemins des datasets : configurables, aucun nom n'est imposé au code métier.
    catalog_dir: Path = ROOT_DIR / "data" / "catalog"
    crop_catalog_file: str = "catalogue_cultures_v6.csv"
    crop_calendar_file: str = "calendrier_FAO_Tunisie.csv"
    catalog_sources_file: str = "sources.csv"

    nasa_power_base_url: str = "https://power.larc.nasa.gov/api/temporal/daily/point"
    soilgrids_base_url: str = "https://rest.isric.org/soilgrids/v2.0/properties/query"
    http_timeout_seconds: float = 30.0

    # Extraction PDF/image -> JSON (Gemini)
    gemini_api_key: str | None = None
    extractor_model: str = "gemini-3.6-flash"

    climate_start_year: int = 2015
    climate_end_year: int = 2024

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


settings = Settings()
