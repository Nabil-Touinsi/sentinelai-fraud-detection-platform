from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

"""
Core Settings.

Rôle (fonctionnel) :
- Centralise la configuration de l’application via variables d’environnement (Pydantic Settings).
- Charge un fichier .env (par défaut backend/.env) pour faciliter le dev/local.
- Fournit un objet global `settings` importable dans tout le projet.

Organisation :
- App : nom, env, debug, niveau de log.
- CORS : origines autorisées (front).
- Auth (démo) : API_KEY.
- Rate limit : activation + RPM.
- DB : URL async (runtime) + URL sync (migrations Alembic).
- Scoring : seuil d’alerte.
"""

# Pointe toujours vers backend/.env (racine backend/)
ENV_PATH = Path(__file__).resolve().parents[2] / ".env"  # backend/.env


class Settings(BaseSettings):
    # --- App ---
    APP_NAME: str = "SentinelAI API"
    ENV: str = "dev"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # --- CORS ---
    # Liste CSV des origines autorisées (ex: front Vite)
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- Auth (démo) ---
    # Clé API optionnelle. Si vide : bypass en dev (voir core/security.py).
    API_KEY: str = ""

    # --- Rate limit (optionnel) ---
    RATE_LIMIT_ENABLED: bool = False
    RATE_LIMIT_RPM: int = 120

    # --- DB ---
    # Async : utilisé par l’app (SQLAlchemy async)
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/sentinelai"

    # Sync : utilisé par Alembic (migrations en mode sync)
    DATABASE_URL_SYNC: str = "postgresql+psycopg://postgres:postgres@localhost:5432/sentinelai"

    # --- Scoring ---
    # Déclenchement d’alerte si score >= threshold
    ALERT_THRESHOLD: int = 70  # alerte si score >= 70

    # Config Pydantic Settings
    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Instance globale importable
settings = Settings()
