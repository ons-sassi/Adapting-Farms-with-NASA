from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "Adapting Farms API"
    app_version: str = "1.0.0"
    api_v1_prefix: str = "/api/v1"

    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_database: str = "agrisense"
    mysql_user: str = "root"
    mysql_password: str = ""

    jwt_secret_key: str = "CHANGE_THIS_TO_A_LONG_RANDOM_SECRET"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Groq : utilisé uniquement pour rédiger les explications des résultats.
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    groq_timeout_seconds: int = Field(
        default=30,
        ge=1,
        le=300,
        validation_alias=AliasChoices("GROQ_TIMEOUT", "GROQ_TIMEOUT_SECONDS"),
    )
    groq_max_completion_tokens: int = 1800
    groq_max_input_chars: int = 30000

    # Extraction PDF/image -> JSON (frontend : import d'un rapport de sol)
    gemini_api_key: str = Field(default="", validation_alias=AliasChoices("GEMINI_API_KEY", "AGRISENSE_GEMINI_API_KEY"))
    extractor_model: str = Field(default="gemini-3.6-flash", validation_alias=AliasChoices("GEMINI_MODEL", "EXTRACTOR_MODEL"))

    gee_project: str = Field(default="", validation_alias="GEE_PROJECT")
    gee_service_account: str = Field(default="", validation_alias="GEE_SERVICE_ACCOUNT")
    gee_key_file: str = Field(default="", validation_alias="GEE_KEY_FILE")

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        from urllib.parse import quote_plus
        password = quote_plus(self.mysql_password)
        return (
            f"mysql+pymysql://{self.mysql_user}:{password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            "?charset=utf8mb4"
        )

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
