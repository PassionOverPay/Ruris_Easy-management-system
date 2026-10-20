from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    PROJECT_NAME: str = "Supply Chain Management API"
    API_V1_PREFIX: str = "/api/v1"
    DATABASE_URL: str = "sqlite:///./supply_chain.db"
    JWT_SECRET_KEY: str | None = None
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    SMTP_HOST: str | None = None
    SMTP_PORT: str | None = None
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    model_config = SettingsConfigDict(
        env_file=REPOSITORY_ROOT / ".env.local",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
