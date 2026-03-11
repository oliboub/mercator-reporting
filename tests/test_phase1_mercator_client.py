"""Tests Phase 1 — MercatorClient : auth, cache, retry, erreurs.

Tests unitaires du client HTTP Mercator — sans appel réseau réel.
"""
import time
import pytest
from unittest.mock import patch, MagicMock
import httpx

from src.core.mercator_client import (
    MercatorClient,
    MercatorAuthError,
    MercatorAPIError,
    _CacheEntry,
    MERCATOR_ENDPOINTS,
)


# ---------------------------------------------------------------------------
# Fixtures locales
# ---------------------------------------------------------------------------

@pytest.fixture
def client_instance():
    """Instance MercatorClient sans cache pour les tests unitaires."""
    return MercatorClient(
        base_url="http://mercator-test:8080",
        login="admin@test.com",
        password="test-password",
        cache_ttl=0,  # pas de cache
    )


@pytest.fixture
def client_with_cache():
    """Instance MercatorClient avec cache activé."""
    return MercatorClient(
        base_url="http://mercator-test:8080",
        login="admin@test.com",
        password="test-password",
        cache_ttl=60,
    )


def _mock_response(status_code: int, json_data: dict | list) -> MagicMock:
    """Helper — crée un mock httpx.Response."""
    mock = MagicMock(spec=httpx.Response)
    mock.status_code = status_code
    mock.json.return_value = json_data
    return mock


# ---------------------------------------------------------------------------
# Authentification
# ---------------------------------------------------------------------------

@pytest.mark.phase1
class TestAuthentication:
    """Tests d'authentification Mercator."""

    def test_authenticate_success(self, client_instance):
        """Authentification réussie → token stocké."""
        mock_resp = _mock_response(200, {"access_token": "tok-abc123"})
        with patch("httpx.post", return_value=mock_resp):
            token = client_instance.authenticate()
        assert token == "tok-abc123"
        assert client_instance._token == "tok-abc123"

    def test_authenticate_401_raises_auth_error(self, client_instance):
        """HTTP 401 → MercatorAuthError."""
        mock_resp = _mock_response(401, {"error": "unauthorized"})
        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(MercatorAuthError, match="401"):
                client_instance.authenticate()

    def test_authenticate_missing_token_raises_error(self, client_instance):
        """Réponse sans access_token → MercatorAuthError."""
        mock_resp = _mock_response(200, {"user": "admin"})  # pas de token
        with patch("httpx.post", return_value=mock_resp):
            with pytest.raises(MercatorAuthError, match="Token absent"):
                client_instance.authenticate()

    def test_authenticate_connection_error(self, client_instance):
        """Connexion impossible → MercatorAuthError."""
        with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            with pytest.raises(MercatorAuthError, match="Impossible de joindre"):
                client_instance.authenticate()

    def test_get_headers_triggers_auth_if_no_token(self, client_instance):
        """_get_headers() appelle authenticate() si pas de token."""
        mock_resp = _mock_response(200, {"access_token": "tok-new"})
        with patch("httpx.post", return_value=mock_resp):
            headers = client_instance._get_headers()
        assert headers["Authorization"] == "Bearer tok-new"

    def test_get_headers_reuses_existing_token(self, client_instance):
        """_get_headers() réutilise le token existant sans re-authentifier."""
        client_instance._token = "tok-existing"
        with patch("httpx.post") as mock_post:
            headers = client_instance._get_headers()
            mock_post.assert_not_called()
        assert headers["Authorization"] == "Bearer tok-existing"

    def test_token_refresh_on_401(self, client_instance):
        """Un 401 sur un GET déclenche une re-authentification."""
        client_instance._token = "tok-expired"

        resp_401 = _mock_response(401, {"error": "token expired"})
        resp_auth = _mock_response(200, {"access_token": "tok-fresh"})
        resp_ok = _mock_response(200, [{"id": 1, "name": "App1"}])

        with patch("httpx.post", return_value=resp_auth):
            with patch("httpx.get", side_effect=[resp_401, resp_ok]):
                result = client_instance.get_endpoint("applications")

        assert result == [{"id": 1, "name": "App1"}]
        assert client_instance._token == "tok-fresh"


# ---------------------------------------------------------------------------
# get_endpoint
# ---------------------------------------------------------------------------

@pytest.mark.phase1
class TestGetEndpoint:
    """Tests de get_endpoint()."""

    def test_get_endpoint_returns_list(self, client_instance):
        """get_endpoint() retourne une liste d'objets."""
        client_instance._token = "tok"
        data = [{"id": 1, "name": "SAP ASCS"}, {"id": 2, "name": "SAP ECC"}]
        with patch.object(client_instance, "_get", return_value=_mock_response(200, data)):
            result = client_instance.get_endpoint("applications")
        assert result == data

    def test_get_endpoint_unwraps_data_envelope(self, client_instance):
        """get_endpoint() extrait les données depuis {'data': [...]}."""
        client_instance._token = "tok"
        wrapped = {"data": [{"id": 1, "name": "App"}], "meta": {"total": 1}}
        with patch.object(client_instance, "_get", return_value=_mock_response(200, wrapped)):
            result = client_instance.get_endpoint("applications")
        assert result == [{"id": 1, "name": "App"}]

    def test_get_endpoint_returns_empty_list_if_none(self, client_instance):
        """get_endpoint() retourne [] si la réponse est None ou vide."""
        client_instance._token = "tok"
        with patch.object(client_instance, "_get", return_value=_mock_response(200, [])):
            result = client_instance.get_endpoint("tasks")
        assert result == []

    def test_get_endpoint_404_raises_api_error(self, client_instance):
        """Un endpoint 404 lève MercatorAPIError."""
        client_instance._token = "tok"
        with patch.object(
            client_instance, "_get",
            side_effect=MercatorAPIError("Not found", status_code=404)
        ):
            with pytest.raises(MercatorAPIError) as exc:
                client_instance.get_endpoint("unknown-ep")
            assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# get_object
# ---------------------------------------------------------------------------

@pytest.mark.phase1
class TestGetObject:
    """Tests de get_object()."""

    def test_get_object_returns_dict(self, client_instance):
        """get_object() retourne un dict."""
        client_instance._token = "tok"
        obj = {"id": 1, "name": "SAP ASCS", "type": "ERP", "logical_servers": []}
        with patch.object(client_instance, "_get", return_value=_mock_response(200, obj)):
            result = client_instance.get_object("applications", 1)
        assert result["name"] == "SAP ASCS"

    def test_get_object_with_relations_sends_include_param(self, client_instance):
        """get_object() avec with_relations=True envoie le param include."""
        client_instance._token = "tok"
        with patch.object(
            client_instance, "_get", return_value=_mock_response(200, {"id": 1})
        ) as mock_get:
            client_instance.get_object("applications", 1, with_relations=True)
            call_kwargs = mock_get.call_args
            params = call_kwargs[1].get("params") or call_kwargs[0][1]
            assert "include" in params

    def test_get_object_without_relations_no_include(self, client_instance):
        """get_object() avec with_relations=False n'envoie pas include."""
        client_instance._token = "tok"
        with patch.object(
            client_instance, "_get", return_value=_mock_response(200, {"id": 1})
        ) as mock_get:
            client_instance.get_object("applications", 1, with_relations=False)
            call_kwargs = mock_get.call_args
            params = call_kwargs[1].get("params") or call_kwargs[0][1] if len(call_kwargs[0]) > 1 else {}
            assert not params or "include" not in params


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

@pytest.mark.phase1
class TestCache:
    """Tests du cache mémoire TTL."""

    def test_cache_entry_valid_within_ttl(self):
        """Une entrée de cache est valide avant l'expiration."""
        entry = _CacheEntry(data=[1, 2, 3], ttl=60)
        assert entry.is_valid() is True

    def test_cache_entry_expired_after_ttl(self):
        """Une entrée de cache est invalide après l'expiration."""
        entry = _CacheEntry(data=[1, 2, 3], ttl=0)
        time.sleep(0.01)
        assert entry.is_valid() is False

    def test_get_endpoint_uses_cache_on_second_call(self, client_with_cache):
        """Le second appel utilise le cache (pas de requête réseau)."""
        client_with_cache._token = "tok"
        data = [{"id": 1, "name": "App"}]
        with patch.object(
            client_with_cache, "_get", return_value=_mock_response(200, data)
        ) as mock_get:
            result1 = client_with_cache.get_endpoint("applications")
            result2 = client_with_cache.get_endpoint("applications")

        assert mock_get.call_count == 1  # UNE seule requête réseau
        assert result1 == result2

    def test_invalidate_cache_clears_endpoint(self, client_with_cache):
        """invalidate_cache() force un nouvel appel réseau."""
        client_with_cache._token = "tok"
        data = [{"id": 1, "name": "App"}]
        with patch.object(
            client_with_cache, "_get", return_value=_mock_response(200, data)
        ) as mock_get:
            client_with_cache.get_endpoint("applications")
            client_with_cache.invalidate_cache("applications")
            client_with_cache.get_endpoint("applications")

        assert mock_get.call_count == 2  # deux requêtes réseau

    def test_invalidate_all_cache(self, client_with_cache):
        """invalidate_cache() sans argument vide tout le cache."""
        client_with_cache._cache["applications"] = _CacheEntry([], 60)
        client_with_cache._cache["entities"] = _CacheEntry([], 60)
        client_with_cache.invalidate_cache()
        assert len(client_with_cache._cache) == 0

    def test_no_cache_when_ttl_zero(self, client_instance):
        """Avec cache_ttl=0, chaque appel fait une requête réseau."""
        client_instance._token = "tok"
        data = [{"id": 1}]
        with patch.object(
            client_instance, "_get", return_value=_mock_response(200, data)
        ) as mock_get:
            client_instance.get_endpoint("applications")
            client_instance.get_endpoint("applications")
        assert mock_get.call_count == 2


# ---------------------------------------------------------------------------
# check_connection
# ---------------------------------------------------------------------------

@pytest.mark.phase1
class TestCheckConnection:
    """Tests de check_connection()."""

    def test_check_connection_ok(self, client_instance):
        """check_connection() retourne status=ok si tout va bien."""
        with patch.object(client_instance, "authenticate", return_value="tok"):
            with patch.object(client_instance, "_get", return_value=_mock_response(200, [])):
                result = client_instance.check_connection()
        assert result["status"] == "ok"
        assert result["authenticated"] is True

    def test_check_connection_auth_error(self, client_instance):
        """check_connection() retourne status=auth_error si credentials invalides."""
        with patch.object(
            client_instance, "authenticate",
            side_effect=MercatorAuthError("Credentials invalides")
        ):
            result = client_instance.check_connection()
        assert result["status"] == "auth_error"
        assert result["authenticated"] is False

    def test_check_connection_network_error(self, client_instance):
        """check_connection() retourne status=connection_error si réseau KO."""
        with patch.object(
            client_instance, "authenticate",
            side_effect=Exception("Connection refused")
        ):
            result = client_instance.check_connection()
        assert result["status"] == "connection_error"


# ---------------------------------------------------------------------------
# full_dump
# ---------------------------------------------------------------------------

@pytest.mark.phase1
class TestFullDump:
    """Tests de full_dump()."""

    def test_full_dump_returns_all_endpoints(self, client_instance):
        """full_dump() retourne un dict avec tous les endpoints."""
        client_instance._token = "tok"
        with patch.object(client_instance, "get_endpoint", return_value=[{"id": 1}]):
            result = client_instance.full_dump()
        assert set(result.keys()) == set(MERCATOR_ENDPOINTS)

    def test_full_dump_skips_404_endpoints_gracefully(self, client_instance):
        """full_dump() continue sur les endpoints 404 (liste vide)."""
        client_instance._token = "tok"

        def _side_effect(ep):
            if ep in ("tasks", "gateways"):
                raise MercatorAPIError("Not found", status_code=404)
            return [{"id": 1}]

        with patch.object(client_instance, "get_endpoint", side_effect=_side_effect):
            result = client_instance.full_dump()

        assert result["tasks"] == []
        assert result["gateways"] == []
        assert result["applications"] == [{"id": 1}]

    def test_full_dump_with_custom_endpoints(self, client_instance):
        """full_dump() accepte une liste personnalisée d'endpoints."""
        client_instance._token = "tok"
        with patch.object(client_instance, "get_endpoint", return_value=[{"id": 1}]):
            result = client_instance.full_dump(endpoints=["applications", "entities"])
        assert list(result.keys()) == ["applications", "entities"]


# ---------------------------------------------------------------------------
# MERCATOR_ENDPOINTS constant
# ---------------------------------------------------------------------------

@pytest.mark.phase1
class TestEndpointsList:
    """Tests de la liste des endpoints."""

    def test_all_known_endpoints_present(self):
        """Les endpoints clés sont dans la liste."""
        required = [
            "applications", "logical-servers", "physical-servers",
            "data-processings", "activities", "processes", "entities",
            "databases", "networks", "sites",
        ]
        for ep in required:
            assert ep in MERCATOR_ENDPOINTS, f"'{ep}' manquant dans MERCATOR_ENDPOINTS"

    def test_no_duplicate_endpoints(self):
        """Pas de doublons dans la liste des endpoints."""
        assert len(MERCATOR_ENDPOINTS) == len(set(MERCATOR_ENDPOINTS))