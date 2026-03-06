"""Application-level configuration loaded from environment variables / .env file."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central settings object — all values sourced from environment or .env."""

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/tmf_db"

    # Security
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Application
    app_env: str = "development"
    app_name: str = "TMF Service Layer"
    app_version: str = "0.1.0"
    debug: bool = False

    # Auth feature flag — set to False in non-dev environments to enforce real JWT
    auth_enabled: bool = False

    # CORS
    cors_origins: list[str] = ["http://localhost", "http://localhost:8080", "http://127.0.0.1:8080"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
