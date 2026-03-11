"""Fixtures pytest globales — Mercator Reporting.

Les mocks sont construits à partir des données réelles du dump_standard.json
pour garantir des tests représentatifs.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from src.main import app
from src.core.mercator_client import MercatorClient, MercatorAuthError, MercatorAPIError
from src.core.dependencies import get_mercator_client

# ---------------------------------------------------------------------------
# Données de test basées sur dump_standard.json (données réelles)
# ---------------------------------------------------------------------------

MOCK_APPLICATIONS = [
    {
        "id": 1, "name": "SAP ASCS", "type": "ERP", "technology": "SAP S/4HANA",
        "responsible": "LOGISTIX-PARTNER", "security_need_c": 3, "security_need_i": 3,
        "security_need_a": 3, "security_need_t": None, "rto": None, "rpo": None,
        "external": "1", "application_block_id": 2,
        "created_at": "2026-03-08T16:12:09.000000Z", "updated_at": "2026-03-08T16:14:43.000000Z",
    },
    {
        "id": 2, "name": "SAP ECC", "type": "ERP", "technology": "SAP S/4HANA",
        "responsible": "LOGISTIX-PARTNER", "security_need_c": 3, "security_need_i": 3,
        "security_need_a": 3, "security_need_t": None, "rto": None, "rpo": None,
        "external": "0", "application_block_id": 2,
        "created_at": "2026-03-08T16:12:09.000000Z", "updated_at": "2026-03-08T16:12:09.000000Z",
    },
    {
        "id": 3, "name": "PORTAIL-RH", "type": "Web", "technology": "React",
        "responsible": "RH-TEAM", "security_need_c": 2, "security_need_i": 2,
        "security_need_a": 2, "security_need_t": None, "rto": 4, "rpo": 24,
        "external": "0", "application_block_id": 1,
        "created_at": "2026-03-08T16:12:09.000000Z", "updated_at": "2026-03-08T16:12:09.000000Z",
    },
]

MOCK_ACTIVITIES = [
    {
        "id": 1, "name": "MAINTENANCE-TMA-ERP", "description": None,
        "recovery_time_objective": None, "maximum_tolerable_downtime": None,
        "recovery_point_objective": None, "maximum_tolerable_data_loss": None,
        "drp": None, "drp_link": None,
        "created_at": "2026-03-08T16:12:17.000000Z",
    },
    {
        "id": 2, "name": "GESTION-PAIE", "description": "Traitement de la paie mensuelle",
        "recovery_time_objective": 4, "maximum_tolerable_downtime": 8,
        "recovery_point_objective": 24, "maximum_tolerable_data_loss": 48,
        "drp": True, "drp_link": "https://wiki/drp-paie",
        "created_at": "2026-03-08T16:12:17.000000Z",
    },
]

MOCK_LOGICAL_SERVERS = [
    {
        "id": 1, "name": "LOGICAL-P11-SRV001", "operating_system": "Ubuntu 20.04.6 LTS",
        "address_ip": "12.0.1.5", "cpu": "8 vCPU", "memory": "16 GB",
        "environment": "Production", "type": "VM", "active": True,
        "cluster_id": 1, "domain_id": None,
        "created_at": "2026-03-08T16:12:04.000000Z",
    },
    {
        "id": 2, "name": "LOGICAL-P11-SRV002", "operating_system": "Windows Server 2019",
        "address_ip": "12.0.1.6", "cpu": "4 vCPU", "memory": "8 GB",
        "environment": "Production", "type": "VM", "active": True,
        "cluster_id": 1, "domain_id": None,
        "created_at": "2026-03-08T16:12:04.000000Z",
    },
]

MOCK_DATA_PROCESSINGS = [
    {
        "id": 1, "name": "EU Article 30 - 1.a", "responsible": "DPO",
        "purpose": "Registre des traitements RGPD",
        "legal_basis": "legal_obligation", "retention": "5 ans",
        "lawfulness_consent": False, "lawfulness_contract": False,
        "lawfulness_legal_obligation": True,
        "created_at": "2026-03-08T16:12:00.000000Z",
    },
]

MOCK_ENTITIES = [
    {"id": 1, "name": "LOGISTIX", "entity_type": "company", "is_external": False,
     "security_level": None, "contact_point": None, "parent_entity_id": None},
    {"id": 2, "name": "LOGISTIX-PARTNER", "entity_type": "partner", "is_external": True,
     "security_level": None, "contact_point": None, "parent_entity_id": 1},
]

# Mapping endpoint → données mock
MOCK_DATA: dict[str, list] = {
    "applications": MOCK_APPLICATIONS,
    "activities": MOCK_ACTIVITIES,
    "logical-servers": MOCK_LOGICAL_SERVERS,
    "data-processings": MOCK_DATA_PROCESSINGS,
    "entities": MOCK_ENTITIES,
    "processes": [
        {"id": 1, "name": "GESTION-COMMANDES", "owner": None,
         "security_need_c": 3, "security_need_i": 3, "security_need_a": 3,
         "macroprocess_id": None},
    ],
    "physical-servers": [
        {"id": 1, "name": "PHYSICAL-SERVER-111", "type": "Dell PowerEdge R740",
         "address_ip": None, "cpu": None, "memory": None,
         "site_id": 1, "building_id": 3, "bay_id": 1},
    ],
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_mercator_client() -> MagicMock:
    """Mock du MercatorClient avec données réelles du dump."""
    mock = MagicMock(spec=MercatorClient)

    def _get_endpoint(endpoint: str) -> list:
        return MOCK_DATA.get(endpoint, [])

    def _get_object(endpoint: str, obj_id: int, with_relations: bool = True) -> dict:
        items = MOCK_DATA.get(endpoint, [])
        for item in items:
            if item.get("id") == obj_id:
                return {**item, "relations_included": with_relations}
        raise MercatorAPIError(f"Objet {endpoint}/{obj_id} introuvable", status_code=404)

    def _check_connection() -> dict:
        return {"status": "ok", "base_url": "http://localhost:8080", "authenticated": True}

    mock.get_endpoint.side_effect = _get_endpoint
    mock.get_object.side_effect = _get_object
    mock.check_connection.side_effect = _check_connection
    mock.get_endpoint_detail.side_effect = _get_endpoint
    mock.full_dump.return_value = MOCK_DATA

    return mock


@pytest.fixture
def client(mock_mercator_client) -> TestClient:
    """Client de test FastAPI avec MercatorClient mocké."""
    app.dependency_overrides[get_mercator_client] = lambda: mock_mercator_client
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def client_no_mock() -> TestClient:
    """Client de test FastAPI SANS mock — pour tests d'intégration réels."""
    return TestClient(app)


@pytest.fixture
def real_mercator_client(mercator_url, mercator_login, mercator_password) -> MercatorClient:
    """Client Mercator réel — uniquement pour tests d'intégration."""
    return MercatorClient(
        base_url=mercator_url,
        login=mercator_login,
        password=mercator_password,
        cache_ttl=0,  # pas de cache pendant les tests
    )


def pytest_addoption(parser):
    parser.addoption("--mercator-url", default="http://localhost:8080")
    parser.addoption("--mercator-login", default="admin@admin.com")
    parser.addoption("--mercator-password", default="password")


@pytest.fixture
def mercator_url(request):
    return request.config.getoption("--mercator-url")


@pytest.fixture
def mercator_login(request):
    return request.config.getoption("--mercator-login")


@pytest.fixture
def mercator_password(request):
    return request.config.getoption("--mercator-password")