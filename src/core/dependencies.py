"""Dépendances FastAPI — injection du MercatorClient."""
from functools import lru_cache
from src.config import get_settings
from src.core.mercator_client import MercatorClient


@lru_cache
def get_mercator_client() -> MercatorClient:
    """Retourne le client Mercator (singleton par process)."""
    s = get_settings()
    return MercatorClient(
        base_url=s.mercator_base_url,
        login=s.mercator_login,
        password=s.mercator_password,
        cache_ttl=s.cache_ttl_seconds,
    )