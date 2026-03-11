"""Tests Phase 1 — US2 : Appel des endpoints Mercator.

Valide :
- Health checks système et Mercator
- Listing de tous les endpoints connus
- Récupération de données par endpoint
- Filtrage et pagination
- Détail d'un objet avec relations
- Export JSON
- Gestion des erreurs (endpoint inconnu, objet introuvable)
"""
import pytest
from src.core.mercator_client import MERCATOR_ENDPOINTS


# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------

@pytest.mark.phase1
class TestSystemEndpoints:
    """Tests des endpoints système de l'API."""

    def test_health_ok(self, client):
        """L'API répond 200 sur /health."""
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["service"] == "mercator-reporting"

    def test_root_returns_links(self, client):
        """Le root retourne les liens utiles."""
        r = client.get("/")
        assert r.status_code == 200
        body = r.json()
        assert "docs" in body
        assert "mercator_health" in body
        assert "endpoints" in body

    def test_openapi_schema_accessible(self, client):
        """Le schema OpenAPI est disponible."""
        r = client.get("/openapi.json")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Mercator Health
# ---------------------------------------------------------------------------

@pytest.mark.phase1
class TestMercatorHealth:
    """Tests de connectivité Mercator."""

    def test_mercator_health_ok(self, client):
        """Mercator est joignable et authentifié."""
        r = client.get("/api/mercator/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["authenticated"] is True

    def test_mercator_health_auth_error(self, client, mock_mercator_client):
        """Retourne 503 si les credentials sont invalides."""
        from src.core.mercator_client import MercatorAuthError
        mock_mercator_client.check_connection.side_effect = None
        mock_mercator_client.check_connection.return_value = {
            "status": "auth_error",
            "error": "Credentials invalides",
            "authenticated": False,
        }
        r = client.get("/api/mercator/health")
        assert r.status_code == 503


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

@pytest.mark.phase1
class TestEndpointDiscovery:
    """Tests de découverte des endpoints."""

    def test_list_endpoints_returns_all(self, client):
        """Retourne la liste complète des endpoints Mercator."""
        r = client.get("/api/mercator/endpoints")
        assert r.status_code == 200
        body = r.json()
        assert "endpoints" in body
        assert body["total"] == len(MERCATOR_ENDPOINTS)
        assert "applications" in body["endpoints"]
        assert "logical-servers" in body["endpoints"]
        assert "data-processings" in body["endpoints"]

    def test_unknown_endpoint_returns_404(self, client):
        """Un endpoint inconnu retourne 404."""
        r = client.get("/api/mercator/unknown-endpoint-xyz")
        assert r.status_code == 404
        assert "inconnu" in r.json()["detail"]


# ---------------------------------------------------------------------------
# US2 — Liste des objets par endpoint
# ---------------------------------------------------------------------------

@pytest.mark.phase1
class TestEndpointList:
    """Tests de listing des objets par endpoint."""

    def test_get_applications(self, client):
        """Récupère la liste des applications."""
        r = client.get("/api/mercator/applications")
        assert r.status_code == 200
        body = r.json()
        assert body["endpoint"] == "applications"
        assert body["total"] == 3
        assert len(body["data"]) == 3

    def test_get_activities_with_bia_fields(self, client):
        """Les activités contiennent les champs BIA (RTO/RPO)."""
        r = client.get("/api/mercator/activities")
        assert r.status_code == 200
        data = r.json()["data"]
        assert len(data) >= 1
        # Vérification des champs BIA présents
        fields = data[0].keys()
        assert "recovery_time_objective" in fields
        assert "recovery_point_objective" in fields
        assert "maximum_tolerable_downtime" in fields

    def test_get_logical_servers(self, client):
        """Récupère la liste des serveurs logiques."""
        r = client.get("/api/mercator/logical-servers")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 2
        assert body["data"][0]["name"] == "LOGICAL-P11-SRV001"

    def test_get_data_processings_rgpd(self, client):
        """Récupère les traitements RGPD."""
        r = client.get("/api/mercator/data-processings")
        assert r.status_code == 200
        data = r.json()["data"]
        assert len(data) >= 1
        assert "legal_basis" in data[0]
        assert "retention" in data[0]

    def test_get_empty_endpoint_returns_empty_list(self, client):
        """Un endpoint sans données retourne une liste vide (pas une erreur)."""
        r = client.get("/api/mercator/tasks")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 0
        assert body["data"] == []

    def test_response_structure_is_consistent(self, client):
        """Toutes les réponses ont la même structure."""
        for endpoint in ["applications", "activities", "entities", "processes"]:
            r = client.get(f"/api/mercator/{endpoint}")
            assert r.status_code == 200
            body = r.json()
            assert "endpoint" in body
            assert "total" in body
            assert "data" in body
            assert "limit" in body
            assert "offset" in body
            assert body["endpoint"] == endpoint


# ---------------------------------------------------------------------------
# Filtrage et pagination
# ---------------------------------------------------------------------------

@pytest.mark.phase1
class TestFilteringAndPagination:
    """Tests de filtrage et pagination."""

    def test_search_filter_by_name(self, client):
        """Le filtre search retourne uniquement les objets correspondants."""
        r = client.get("/api/mercator/applications?search=SAP")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 2  # SAP ASCS + SAP ECC
        for item in body["data"]:
            assert "SAP" in item["name"].upper()

    def test_search_filter_case_insensitive(self, client):
        """La recherche est insensible à la casse."""
        r_upper = client.get("/api/mercator/applications?search=sap")
        r_lower = client.get("/api/mercator/applications?search=SAP")
        assert r_upper.json()["total"] == r_lower.json()["total"]

    def test_search_no_result(self, client):
        """Une recherche sans résultat retourne une liste vide."""
        r = client.get("/api/mercator/applications?search=XXXXNOTFOUND")
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_pagination_limit(self, client):
        """Le paramètre limit fonctionne."""
        r = client.get("/api/mercator/applications?limit=2")
        assert r.status_code == 200
        body = r.json()
        assert body["count"] == 2
        assert body["total"] == 3  # total reste 3

    def test_pagination_offset(self, client):
        """Le paramètre offset fonctionne."""
        r_full = client.get("/api/mercator/applications")
        r_offset = client.get("/api/mercator/applications?offset=1")
        full_ids = [item["id"] for item in r_full.json()["data"]]
        offset_ids = [item["id"] for item in r_offset.json()["data"]]
        assert offset_ids == full_ids[1:]

    def test_pagination_limit_max(self, client):
        """La limite max est respectée (1000)."""
        r = client.get("/api/mercator/applications?limit=9999")
        assert r.status_code == 422  # Validation FastAPI

    def test_pagination_limit_min(self, client):
        """La limite min est respectée (1)."""
        r = client.get("/api/mercator/applications?limit=0")
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# US2 — Détail d'un objet
# ---------------------------------------------------------------------------

@pytest.mark.phase1
class TestObjectDetail:
    """Tests de récupération d'un objet par ID."""

    def test_get_application_by_id(self, client):
        """Récupère le détail d'une application par ID."""
        r = client.get("/api/mercator/applications/1")
        assert r.status_code == 200
        body = r.json()
        assert body["endpoint"] == "applications"
        assert body["id"] == 1
        assert body["data"]["name"] == "SAP ASCS"

    def test_get_object_includes_relations_by_default(self, client):
        """Le détail inclut les relations par défaut."""
        r = client.get("/api/mercator/applications/1")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data.get("relations_included") is True

    def test_get_object_without_relations(self, client):
        """On peut désactiver les relations."""
        r = client.get("/api/mercator/applications/1?with_relations=false")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data.get("relations_included") is False

    def test_get_activity_bia_values(self, client):
        """Le détail d'une activité contient les valeurs BIA réelles."""
        r = client.get("/api/mercator/activities/2")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["name"] == "GESTION-PAIE"
        assert data["recovery_time_objective"] == 4
        assert data["recovery_point_objective"] == 24
        assert data["maximum_tolerable_downtime"] == 8

    def test_object_not_found_returns_404(self, client):
        """Un ID inexistant retourne 404."""
        r = client.get("/api/mercator/applications/99999")
        assert r.status_code == 404
        assert "introuvable" in r.json()["detail"]

    def test_object_on_unknown_endpoint_returns_404(self, client):
        """Un endpoint inconnu avec ID retourne 404."""
        r = client.get("/api/mercator/not-an-endpoint/1")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Export JSON (US2 — critère "Export des données en JSON")
# ---------------------------------------------------------------------------

@pytest.mark.phase1
class TestExportJSON:
    """Tests d'export JSON."""

    def test_export_applications_json(self, client):
        """Export JSON des applications."""
        r = client.get("/api/mercator/applications/export/json")
        assert r.status_code == 200
        body = r.json()
        assert body["endpoint"] == "applications"
        assert body["total"] == 3
        assert isinstance(body["data"], list)
        assert body["with_relations"] is False

    def test_export_activities_json_contains_bia_fields(self, client):
        """Export JSON des activités contient les champs BIA."""
        r = client.get("/api/mercator/activities/export/json")
        assert r.status_code == 200
        data = r.json()["data"]
        for activity in data:
            assert "recovery_time_objective" in activity
            assert "recovery_point_objective" in activity

    def test_export_content_type_is_json(self, client):
        """Le Content-Type de l'export est application/json."""
        r = client.get("/api/mercator/applications/export/json")
        assert "application/json" in r.headers["content-type"]

    def test_export_with_relations_flag(self, client):
        """L'export avec with_relations=true est indiqué dans la réponse."""
        r = client.get("/api/mercator/applications/export/json?with_relations=true")
        assert r.status_code == 200
        assert r.json()["with_relations"] is True