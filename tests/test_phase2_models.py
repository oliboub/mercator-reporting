"""Tests Phase 2 — Moteur de filtres dynamiques.

Teste apply_filters(), apply_sort() et apply_projection()
sur les données mock réelles (MOCK_APPLICATIONS, MOCK_ACTIVITIES, etc.)
pour garantir que les filtres BIA, CIAT et RGPD fonctionnent correctement.
"""
import pytest

from src.models.report import FilterDefinition, FilterOperator, SortDirection
from src.reporting.filters import apply_filters, apply_sort, apply_projection

# Données de test locales (reprises du conftest pour lisibilité)
APPLICATIONS = [
    {
        "id": 1, "name": "SAP ASCS", "type": "ERP",
        "security_need_c": 3, "security_need_i": 3, "security_need_a": 3,
        "rto": None, "rpo": None, "external": "1",
    },
    {
        "id": 2, "name": "SAP ECC", "type": "ERP",
        "security_need_c": 3, "security_need_i": 3, "security_need_a": 3,
        "rto": None, "rpo": None, "external": "0",
    },
    {
        "id": 3, "name": "PORTAIL-RH", "type": "Web",
        "security_need_c": 2, "security_need_i": 2, "security_need_a": 2,
        "rto": 4, "rpo": 24, "external": "0",
    },
]

ACTIVITIES = [
    {
        "id": 1, "name": "MAINTENANCE-TMA-ERP",
        "recovery_time_objective": None,
        "maximum_tolerable_downtime": None,
        "recovery_point_objective": None,
        "maximum_tolerable_data_loss": None,
        "drp": None,
    },
    {
        "id": 2, "name": "GESTION-PAIE",
        "recovery_time_objective": 4,
        "maximum_tolerable_downtime": 8,
        "recovery_point_objective": 24,
        "maximum_tolerable_data_loss": 48,
        "drp": True,
    },
]

DATA_PROCESSINGS = [
    {
        "id": 1, "name": "EU Article 30 - 1.a",
        "responsible": "DPO",
        "lawfulness_legal_obligation": True,
        "lawfulness_consent": False,
        "lawfulness_contract": False,
        "retention": "5 ans",
    },
]

LOGICAL_SERVERS = [
    {
        "id": 1, "name": "LOGICAL-P11-SRV001",
        "operating_system": "Ubuntu 20.04.6 LTS",
        "environment": "Production", "active": True,
    },
    {
        "id": 2, "name": "LOGICAL-P11-SRV002",
        "operating_system": "Windows Server 2019",
        "environment": "Production", "active": True,
    },
]


# ---------------------------------------------------------------------------
# Tests apply_filters — cas généraux
# ---------------------------------------------------------------------------

@pytest.mark.phase2
class TestApplyFiltersGeneral:

    def test_no_filters_returns_all(self):
        result = apply_filters(APPLICATIONS, [])
        assert result == APPLICATIONS

    def test_empty_list_returns_empty(self):
        result = apply_filters([], [
            FilterDefinition(field="name", operator=FilterOperator.EQ, value="SAP")
        ])
        assert result == []

    def test_single_eq_filter(self):
        result = apply_filters(APPLICATIONS, [
            FilterDefinition(field="type", operator=FilterOperator.EQ, value="ERP")
        ])
        assert len(result) == 2
        assert all(a["type"] == "ERP" for a in result)

    def test_neq_filter(self):
        result = apply_filters(APPLICATIONS, [
            FilterDefinition(field="type", operator=FilterOperator.NEQ, value="ERP")
        ])
        assert len(result) == 1
        assert result[0]["name"] == "PORTAIL-RH"

    def test_multiple_filters_combined_as_and(self):
        """ERP ET security_need_c >= 3 → SAP ASCS + SAP ECC."""
        result = apply_filters(APPLICATIONS, [
            FilterDefinition(field="type", operator=FilterOperator.EQ, value="ERP"),
            FilterDefinition(field="security_need_c", operator=FilterOperator.GTE, value=3),
        ])
        assert len(result) == 2
        names = [a["name"] for a in result]
        assert "SAP ASCS" in names
        assert "SAP ECC" in names

    def test_filters_no_result(self):
        result = apply_filters(APPLICATIONS, [
            FilterDefinition(field="type", operator=FilterOperator.EQ, value="inexistant")
        ])
        assert result == []

    def test_filter_on_unknown_field_returns_no_match(self):
        """Champ inconnu → field_value = None → IS_NOT_NULL échoue."""
        result = apply_filters(APPLICATIONS, [
            FilterDefinition(field="champ_inconnu", operator=FilterOperator.IS_NOT_NULL)
        ])
        assert result == []


# ---------------------------------------------------------------------------
# Tests apply_filters — opérateurs de nullité (IS_NULL / IS_NOT_NULL)
# ---------------------------------------------------------------------------

@pytest.mark.phase2
class TestNullFilters:

    def test_is_null_on_rto(self):
        """Applications sans RTO → SAP ASCS + SAP ECC."""
        result = apply_filters(APPLICATIONS, [
            FilterDefinition(field="rto", operator=FilterOperator.IS_NULL)
        ])
        assert len(result) == 2
        assert all(a["rto"] is None for a in result)

    def test_is_not_null_on_rto(self):
        """Applications avec RTO renseigné → PORTAIL-RH uniquement."""
        result = apply_filters(APPLICATIONS, [
            FilterDefinition(field="rto", operator=FilterOperator.IS_NOT_NULL)
        ])
        assert len(result) == 1
        assert result[0]["name"] == "PORTAIL-RH"

    def test_bia_filter_activities_with_rto(self):
        """Cas réel BIA : activités avec RTO renseigné → GESTION-PAIE."""
        result = apply_filters(ACTIVITIES, [
            FilterDefinition(field="recovery_time_objective", operator=FilterOperator.IS_NOT_NULL)
        ])
        assert len(result) == 1
        assert result[0]["name"] == "GESTION-PAIE"
        assert result[0]["recovery_time_objective"] == 4

    def test_bia_filter_activities_without_rto(self):
        """Activités sans RTO → MAINTENANCE-TMA-ERP."""
        result = apply_filters(ACTIVITIES, [
            FilterDefinition(field="recovery_time_objective", operator=FilterOperator.IS_NULL)
        ])
        assert len(result) == 1
        assert result[0]["name"] == "MAINTENANCE-TMA-ERP"


# ---------------------------------------------------------------------------
# Tests apply_filters — comparaisons numériques (BIA/CIAT)
# ---------------------------------------------------------------------------

@pytest.mark.phase2
class TestNumericFilters:

    def test_gte_filter_security_need(self):
        """CIAT : applications avec security_need_c >= 3."""
        result = apply_filters(APPLICATIONS, [
            FilterDefinition(field="security_need_c", operator=FilterOperator.GTE, value=3)
        ])
        assert len(result) == 2
        assert all(a["security_need_c"] >= 3 for a in result)

    def test_lte_filter_security_need(self):
        """CIAT : applications avec security_need_a <= 2."""
        result = apply_filters(APPLICATIONS, [
            FilterDefinition(field="security_need_a", operator=FilterOperator.LTE, value=2)
        ])
        assert len(result) == 1
        assert result[0]["name"] == "PORTAIL-RH"

    def test_gt_filter(self):
        result = apply_filters(APPLICATIONS, [
            FilterDefinition(field="security_need_c", operator=FilterOperator.GT, value=2)
        ])
        assert len(result) == 2

    def test_lt_filter(self):
        result = apply_filters(APPLICATIONS, [
            FilterDefinition(field="security_need_c", operator=FilterOperator.LT, value=3)
        ])
        assert len(result) == 1
        assert result[0]["name"] == "PORTAIL-RH"

    def test_eq_numeric_filter(self):
        result = apply_filters(ACTIVITIES, [
            FilterDefinition(field="recovery_time_objective", operator=FilterOperator.EQ, value=4)
        ])
        assert len(result) == 1
        assert result[0]["name"] == "GESTION-PAIE"

    def test_bia_rto_gte_filter(self):
        """BIA : activités avec RTO >= 4h."""
        result = apply_filters(ACTIVITIES, [
            FilterDefinition(field="recovery_time_objective", operator=FilterOperator.GTE, value=4)
        ])
        assert len(result) == 1
        assert result[0]["recovery_time_objective"] == 4

    def test_bia_mtd_gte_filter(self):
        """BIA : activités avec MTD >= 8h."""
        result = apply_filters(ACTIVITIES, [
            FilterDefinition(
                field="maximum_tolerable_downtime",
                operator=FilterOperator.GTE,
                value=8
            )
        ])
        assert len(result) == 1
        assert result[0]["maximum_tolerable_downtime"] == 8


# ---------------------------------------------------------------------------
# Tests apply_filters — comparaisons sur chaînes
# ---------------------------------------------------------------------------

@pytest.mark.phase2
class TestStringFilters:

    def test_contains_filter(self):
        result = apply_filters(APPLICATIONS, [
            FilterDefinition(field="name", operator=FilterOperator.CONTAINS, value="SAP")
        ])
        assert len(result) == 2
        assert all("SAP" in a["name"] for a in result)

    def test_contains_case_insensitive(self):
        result = apply_filters(APPLICATIONS, [
            FilterDefinition(field="name", operator=FilterOperator.CONTAINS, value="sap")
        ])
        assert len(result) == 2

    def test_not_contains_filter(self):
        result = apply_filters(APPLICATIONS, [
            FilterDefinition(field="name", operator=FilterOperator.NOT_CONTAINS, value="SAP")
        ])
        assert len(result) == 1
        assert result[0]["name"] == "PORTAIL-RH"

    def test_starts_with_filter(self):
        result = apply_filters(APPLICATIONS, [
            FilterDefinition(field="name", operator=FilterOperator.STARTS_WITH, value="SAP")
        ])
        assert len(result) == 2

    def test_starts_with_no_match(self):
        result = apply_filters(APPLICATIONS, [
            FilterDefinition(field="name", operator=FilterOperator.STARTS_WITH, value="ORACLE")
        ])
        assert result == []

    def test_contains_on_os(self):
        result = apply_filters(LOGICAL_SERVERS, [
            FilterDefinition(field="operating_system", operator=FilterOperator.CONTAINS, value="Ubuntu")
        ])
        assert len(result) == 1
        assert result[0]["name"] == "LOGICAL-P11-SRV001"


# ---------------------------------------------------------------------------
# Tests apply_filters — opérateur IN
# ---------------------------------------------------------------------------

@pytest.mark.phase2
class TestInFilter:

    def test_in_filter_types(self):
        result = apply_filters(APPLICATIONS, [
            FilterDefinition(field="type", operator=FilterOperator.IN, value=["ERP", "Web"])
        ])
        assert len(result) == 3

    def test_in_filter_partial(self):
        result = apply_filters(APPLICATIONS, [
            FilterDefinition(field="type", operator=FilterOperator.IN, value=["ERP"])
        ])
        assert len(result) == 2
        assert all(a["type"] == "ERP" for a in result)

    def test_in_filter_no_match(self):
        result = apply_filters(APPLICATIONS, [
            FilterDefinition(field="type", operator=FilterOperator.IN, value=["CRM", "BI"])
        ])
        assert result == []

    def test_in_filter_on_none_value(self):
        """Champ None n'est jamais dans une liste."""
        result = apply_filters(ACTIVITIES, [
            FilterDefinition(field="drp", operator=FilterOperator.IN, value=[True])
        ])
        assert len(result) == 1
        assert result[0]["name"] == "GESTION-PAIE"


# ---------------------------------------------------------------------------
# Tests apply_filters — RGPD
# ---------------------------------------------------------------------------

@pytest.mark.phase2
class TestRGPDFilters:

    def test_rgpd_filter_legal_obligation(self):
        """RGPD : traitements avec base légale = obligation légale."""
        result = apply_filters(DATA_PROCESSINGS, [
            FilterDefinition(
                field="lawfulness_legal_obligation",
                operator=FilterOperator.EQ,
                value=True,
            )
        ])
        assert len(result) == 1
        assert result[0]["name"] == "EU Article 30 - 1.a"

    def test_rgpd_filter_no_consent(self):
        result = apply_filters(DATA_PROCESSINGS, [
            FilterDefinition(
                field="lawfulness_consent",
                operator=FilterOperator.EQ,
                value=False,
            )
        ])
        assert len(result) == 1

    def test_rgpd_responsible_dpo(self):
        result = apply_filters(DATA_PROCESSINGS, [
            FilterDefinition(
                field="responsible",
                operator=FilterOperator.EQ,
                value="DPO",
            )
        ])
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Tests apply_sort
# ---------------------------------------------------------------------------

@pytest.mark.phase2
class TestApplySort:

    def test_sort_ascending_by_name(self):
        result = apply_sort(APPLICATIONS, "name", ascending=True)
        names = [a["name"] for a in result]
        assert names == sorted(names)

    def test_sort_descending_by_name(self):
        result = apply_sort(APPLICATIONS, "name", ascending=False)
        names = [a["name"] for a in result]
        assert names == sorted(names, reverse=True)

    def test_sort_by_security_need_asc(self):
        result = apply_sort(APPLICATIONS, "security_need_c", ascending=True)
        values = [a["security_need_c"] for a in result]
        # PORTAIL-RH (2) avant SAP (3)
        assert values[0] == 2
        assert values[-1] == 3

    def test_sort_none_last(self):
        """Les activités sans RTO doivent être placées en fin."""
        result = apply_sort(ACTIVITIES, "recovery_time_objective", ascending=True, none_last=True)
        last = result[-1]
        assert last["recovery_time_objective"] is None

    def test_sort_none_first(self):
        result = apply_sort(ACTIVITIES, "recovery_time_objective", ascending=True, none_last=False)
        first = result[0]
        assert first["recovery_time_objective"] is None

    def test_sort_does_not_modify_original(self):
        original = list(APPLICATIONS)
        apply_sort(APPLICATIONS, "name")
        assert APPLICATIONS == original


# ---------------------------------------------------------------------------
# Tests apply_projection
# ---------------------------------------------------------------------------

@pytest.mark.phase2
class TestApplyProjection:

    def test_project_subset_of_fields(self):
        obj = APPLICATIONS[0]
        result = apply_projection(obj, ["name", "type"])
        assert set(result.keys()) == {"name", "type"}
        assert result["name"] == "SAP ASCS"
        assert result["type"] == "ERP"

    def test_project_empty_returns_all(self):
        obj = APPLICATIONS[0]
        result = apply_projection(obj, [])
        assert result == obj

    def test_project_bia_columns(self):
        obj = ACTIVITIES[1]  # GESTION-PAIE
        result = apply_projection(obj, [
            "name", "recovery_time_objective", "recovery_point_objective"
        ])
        assert result["name"] == "GESTION-PAIE"
        assert result["recovery_time_objective"] == 4
        assert result["recovery_point_objective"] == 24

    def test_project_ciat_columns(self):
        obj = APPLICATIONS[0]  # SAP ASCS
        result = apply_projection(obj, [
            "name", "security_need_c", "security_need_i",
            "security_need_a", "security_need_t"
        ])
        assert result["security_need_c"] == 3
        assert "type" not in result

    def test_project_missing_field_returns_none(self):
        obj = APPLICATIONS[0]
        result = apply_projection(obj, ["name", "champ_inexistant"])
        assert result["name"] == "SAP ASCS"
        assert result["champ_inexistant"] is None