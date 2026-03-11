"""Client HTTP pour l'API Mercator CMDB.

Gère :
- Authentification Bearer (login/password → token, refresh automatique)
- Cache mémoire TTL par endpoint
- Retry automatique sur erreurs réseau
- Récupération détaillée par ID avec includes
"""
import logging
import time
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

# Endpoints disponibles dans Mercator CMDB (exhaustif)
MERCATOR_ENDPOINTS = [
    # Sécurité & Conformité
    "data-processings", "security-controls", "information", "relations",
    # Processus Métier
    "macro-processuses", "processes", "activities", "operations", "tasks", "actors",
    # Entités
    "entities",
    # Applicatif
    "application-blocks", "applications", "application-services",
    "application-modules", "databases", "fluxes",
    # Administration & Annuaire
    "zone-admins", "annuaires", "forest-ads", "domaine-ads", "admin-users",
    # Réseau Logique
    "networks", "subnetworks", "gateways", "external-connected-entities",
    "network-switches", "routers", "security-devices", "clusters",
    "logical-servers", "logical-flows", "containers", "certificates", "vlans",
    # Infrastructure Physique
    "sites", "buildings", "bays", "physical-servers", "workstations",
    "storage-devices", "peripherals", "phones", "physical-switches",
    "physical-routers", "wifi-terminals", "physical-security-devices",
    "physical-links",
    # Réseau Etendu
    "wans", "mans", "lans",
]

# Champs include pour récupérer les relations lors d'un appel /endpoint/{id}
INCLUDE_FIELDS = [
    "actors", "processes", "activities", "logical_servers",
    "databases", "clusters", "applications", "physical_servers", "containers",
]

# Durée du cache en secondes par endpoint (0 = pas de cache)
DEFAULT_CACHE_TTL = 300  # 5 minutes


class MercatorAuthError(Exception):
    """Erreur d'authentification Mercator."""


class MercatorAPIError(Exception):
    """Erreur générique API Mercator."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class _CacheEntry:
    """Entrée de cache avec TTL."""

    def __init__(self, data: Any, ttl: int):
        self.data = data
        self.expires_at = time.monotonic() + ttl

    def is_valid(self) -> bool:
        return time.monotonic() < self.expires_at


class MercatorClient:
    """Client pour interagir avec l'API REST Mercator CMDB.

    Usage :
        client = MercatorClient(base_url="http://localhost:8080",
                                login="admin@admin.com",
                                password="password")

        # Liste des applications
        apps = client.get_endpoint("applications")

        # Détail d'une application avec ses relations
        app = client.get_object("applications", 1)

        # Dump complet (tous endpoints actifs)
        dump = client.full_dump()
    """

    def __init__(
        self,
        base_url: str,
        login: str,
        password: str,
        cache_ttl: int = DEFAULT_CACHE_TTL,
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self._login = login
        self._password = password
        self._cache_ttl = cache_ttl
        self._timeout = timeout
        self._token: str | None = None
        self._cache: dict[str, _CacheEntry] = {}

    # -------------------------------------------------------------------------
    # Authentification
    # -------------------------------------------------------------------------

    def authenticate(self) -> str:
        """Obtient un token Bearer depuis Mercator.

        Raises:
            MercatorAuthError: si les credentials sont invalides.
        """
        try:
            response = httpx.post(
                f"{self.base_url}/api/login",
                data={"login": self._login, "password": self._password},
                timeout=self._timeout,
            )
        except httpx.ConnectError as e:
            raise MercatorAuthError(
                f"Impossible de joindre Mercator à {self.base_url} : {e}"
            ) from e

        if response.status_code == 401:
            raise MercatorAuthError("Credentials Mercator invalides (401)")
        if response.status_code != 200:
            raise MercatorAuthError(
                f"Erreur d'authentification : HTTP {response.status_code}"
            )

        token = response.json().get("access_token")
        if not token:
            raise MercatorAuthError("Token absent dans la réponse de /api/login")

        self._token = token
        logger.info("Authentification Mercator réussie")
        return token

    def _get_headers(self) -> dict[str, str]:
        """Retourne les headers HTTP avec token (authentification si nécessaire)."""
        if not self._token:
            self.authenticate()
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    # -------------------------------------------------------------------------
    # Requêtes HTTP avec retry
    # -------------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=True,
    )
    def _get(self, url: str, params: dict | None = None) -> httpx.Response:
        """GET avec retry automatique sur erreurs réseau."""
        response = httpx.get(
            url,
            headers=self._get_headers(),
            params=params,
            timeout=self._timeout,
        )

        # Token expiré → re-authentification et retry unique
        if response.status_code == 401:
            logger.warning("Token expiré, re-authentification...")
            self._token = None
            response = httpx.get(
                url,
                headers=self._get_headers(),
                params=params,
                timeout=self._timeout,
            )

        if response.status_code == 404:
            raise MercatorAPIError(f"Endpoint non trouvé : {url}", status_code=404)

        if response.status_code != 200:
            raise MercatorAPIError(
                f"Erreur API Mercator : HTTP {response.status_code} sur {url}",
                status_code=response.status_code,
            )

        return response

    @staticmethod
    def _unwrap(data: Any) -> Any:
        """Extrait la donnée depuis l'enveloppe Mercator {'data': [...]}."""
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        return data

    # -------------------------------------------------------------------------
    # Cache
    # -------------------------------------------------------------------------

    def _cache_get(self, key: str) -> Any | None:
        entry = self._cache.get(key)
        if entry and entry.is_valid():
            logger.debug("Cache HIT : %s", key)
            return entry.data
        return None

    def _cache_set(self, key: str, data: Any) -> None:
        if self._cache_ttl > 0:
            self._cache[key] = _CacheEntry(data, self._cache_ttl)
            logger.debug("Cache SET : %s (%d objets)", key, len(data) if isinstance(data, list) else 1)

    def invalidate_cache(self, endpoint: str | None = None) -> None:
        """Invalide le cache d'un endpoint ou de tout le cache."""
        if endpoint:
            self._cache.pop(endpoint, None)
            self._cache.pop(f"{endpoint}/*", None)
            logger.info("Cache invalidé pour : %s", endpoint)
        else:
            self._cache.clear()
            logger.info("Cache global invalidé")

    # -------------------------------------------------------------------------
    # API publique
    # -------------------------------------------------------------------------

    def get_endpoint(self, endpoint: str) -> list[dict]:
        """Récupère la liste de tous les objets d'un endpoint Mercator.

        Args:
            endpoint: nom de l'endpoint (ex: "applications", "logical-servers")

        Returns:
            Liste de dicts représentant les objets Mercator.

        Raises:
            MercatorAPIError: si l'endpoint n'existe pas ou erreur HTTP.
        """
        cached = self._cache_get(endpoint)
        if cached is not None:
            return cached

        logger.info("GET endpoint : %s", endpoint)
        response = self._get(f"{self.base_url}/api/{endpoint}")
        items = self._unwrap(response.json())

        if not isinstance(items, list):
            items = []

        self._cache_set(endpoint, items)
        logger.info("  → %d objets récupérés", len(items))
        return items

    def get_object(self, endpoint: str, obj_id: int, with_relations: bool = True) -> dict:
        """Récupère un objet Mercator par son ID, avec ses relations.

        Args:
            endpoint: nom de l'endpoint (ex: "applications")
            obj_id: identifiant de l'objet
            with_relations: si True, inclut les relations (actors, processes, etc.)

        Returns:
            Dict représentant l'objet Mercator avec ses relations.
        """
        cache_key = f"{endpoint}/{obj_id}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        params = {}
        if with_relations:
            params["include"] = ",".join(INCLUDE_FIELDS)

        logger.debug("GET object : %s/%s", endpoint, obj_id)
        response = self._get(f"{self.base_url}/api/{endpoint}/{obj_id}", params=params)
        obj = self._unwrap(response.json())

        if not isinstance(obj, dict):
            raise MercatorAPIError(f"Réponse inattendue pour {endpoint}/{obj_id}")

        self._cache_set(cache_key, obj)
        return obj

    def get_endpoint_detail(self, endpoint: str) -> list[dict]:
        """Récupère la liste complète avec détails de chaque objet.

        Appelle d'abord get_endpoint() pour la liste, puis get_object()
        pour chaque item. Utilise le cache pour éviter les requêtes redondantes.

        Args:
            endpoint: nom de l'endpoint

        Returns:
            Liste d'objets enrichis avec leurs relations.
        """
        items = self.get_endpoint(endpoint)
        if not items:
            return []

        detailed = []
        for item in items:
            obj_id = item.get("id")
            if obj_id is None:
                detailed.append(item)
                continue
            try:
                detail = self.get_object(endpoint, obj_id)
                detailed.append(detail)
            except MercatorAPIError as e:
                logger.warning("Impossible de récupérer %s/%s : %s", endpoint, obj_id, e)
                detailed.append(item)  # fallback sur la donnée partielle

        return detailed

    def get_endpoint_filtered(
        self,
        endpoint: str,
        filters: list = None,
        sort: list = None,
        include: list[str] = None,
    ) -> list[dict]:
        """Récupère un endpoint avec filtres, tri et includes côté serveur Mercator.

        Utilise l'API Advanced Mercator (filter[field_op]=value, sort=field, include=rel).
        Plus efficace que get_endpoint() + filtrage Python pour les grandes collections.

        Args:
            endpoint: nom de l'endpoint (ex: "applications")
            filters: liste de FilterDefinition à convertir en params Mercator
            sort: liste de SortDefinition à convertir en params Mercator
            include: liste de relations à inclure (ex: ["logical_servers"])

        Returns:
            Liste d'objets filtrés par Mercator.
        """
        params = self._build_filter_params(filters or [], sort or [], include or [])

        # Pas de cache pour les requêtes filtrées (résultats variables)
        logger.debug("GET endpoint filtered : %s params=%s", endpoint, params)
        response = self._get(f"{self.base_url}/api/{endpoint}", params=params)
        data = response.json()

        # Unwrap pagination Mercator {data: [...], links: ..., meta: ...}
        if isinstance(data, dict) and "data" in data:
            items = data["data"]
        elif isinstance(data, list):
            items = data
        else:
            items = []

        return items if isinstance(items, list) else []

    @staticmethod
    def _build_filter_params(
        filters: list,
        sort: list,
        include: list[str],
    ) -> dict:
        """Convertit FilterDefinition[] + SortDefinition[] en query params Mercator."""
        from src.models.report import FilterOperator, SortDirection

        # Mapping opérateur → suffixe Mercator
        OP_MAP = {
            FilterOperator.EQ: "",          # filter[field]=value
            FilterOperator.NEQ: "_not",
            FilterOperator.GT: "_gt",
            FilterOperator.GTE: "_gte",
            FilterOperator.LT: "_lt",
            FilterOperator.LTE: "_lte",
            FilterOperator.CONTAINS: "",    # LIKE auto sur name/description
            FilterOperator.IN: "_in",
            FilterOperator.IS_NULL: "_null",
            FilterOperator.IS_NOT_NULL: "_null",
        }

        params = {}

        for f in filters:
            suffix = OP_MAP.get(f.operator, "")
            key = f"filter[{f.field}{suffix}]"

            if f.operator == FilterOperator.IS_NULL:
                params[key] = "true"
            elif f.operator == FilterOperator.IS_NOT_NULL:
                params[key] = "false"
            elif f.operator == FilterOperator.IN and isinstance(f.value, list):
                params[key] = ",".join(str(v) for v in f.value)
            else:
                params[key] = str(f.value) if f.value is not None else ""

        # Tri — Mercator supporte un seul champ sort (on prend le premier)
        if sort:
            first = sort[0]
            prefix = "" if first.direction == SortDirection.ASC else "-"
            params["sort"] = f"{prefix}{first.field}"

        # Relations à inclure
        if include:
            params["include"] = ",".join(include)

        return params
        """Vérifie la connectivité avec Mercator CMDB.

        Returns:
            Dict avec status, base_url, et nb d'endpoints testés.
        """
        try:
            self.authenticate()
            # Test rapide sur un endpoint léger
            self._get(f"{self.base_url}/api/entities")
            return {
                "status": "ok",
                "base_url": self.base_url,
                "authenticated": True,
            }
        except MercatorAuthError as e:
            return {"status": "auth_error", "error": str(e), "authenticated": False}
        except MercatorAPIError as e:
            return {"status": "api_error", "error": str(e), "authenticated": bool(self._token)}
        except Exception as e:
            return {"status": "connection_error", "error": str(e), "authenticated": False}

    def full_dump(self, endpoints: list[str] | None = None) -> dict[str, list]:
        """Dump complet de tous les endpoints actifs.

        Args:
            endpoints: liste d'endpoints à dumper (None = tous MERCATOR_ENDPOINTS)

        Returns:
            Dict {endpoint: [objets]} pour tous les endpoints.
        """
        targets = endpoints or MERCATOR_ENDPOINTS
        result: dict[str, list] = {}

        for ep in targets:
            try:
                items = self.get_endpoint(ep)
                result[ep] = items
                logger.info("Dump %s : %d objets", ep, len(items))
            except MercatorAPIError as e:
                if e.status_code == 404:
                    logger.debug("Endpoint non disponible : %s", ep)
                else:
                    logger.warning("Erreur sur %s : %s", ep, e)
                result[ep] = []

        return result
