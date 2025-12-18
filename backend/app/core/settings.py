from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Pointe toujours vers backend/.env
ENV_PATH = Path(__file__).resolve().parents[2] / ".env"  # backend/.env


class Settings(BaseSettings):
    # App
    APP_NAME: str = "SentinelAI API"
    ENV: str = "dev"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # DB
    # ✅ Async (pour l'app avec SQLAlchemy async)
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/sentinelai"

    # ✅ Sync (pour Alembic, qui tourne en sync)
    DATABASE_URL_SYNC: str = "postgresql+psycopg://postgres:postgres@localhost:5432/sentinelai"

    # Scoring
    ALERT_THRESHOLD: int = 70  # alerte si score >= 70

    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
