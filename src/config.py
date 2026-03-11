"""Configuration de l'application via variables d'environnement."""
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Paramètres chargés depuis .env ou variables d'environnement."""

    # Mercator CMDB
    mercator_base_url: str = "http://localhost:8080"
    mercator_login: str = "admin@admin.com"
    mercator_password: str = "password"

    # App
    debug: bool = False
    secret_key: str = "change-me"
    max_export_rows: int = 10000

    # Cache
    cache_ttl_seconds: int = 300  # 5 minutes

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    """Retourne les settings (singleton mis en cache)."""
    return Settings()