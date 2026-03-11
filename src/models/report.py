"""Modèles de données pour le ReportEngine.

Contrat entre le Query Builder, le moteur de rapports et l'Export Service.
Tous les types sont validés par Pydantic.
"""
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class FilterOperator(str, Enum):
    """Opérateurs de filtre disponibles."""
    EQ = "eq"           # égal (==)
    NEQ = "neq"         # différent (!=)
    GT = "gt"           # supérieur (>)
    GTE = "gte"         # supérieur ou égal (>=)
    LT = "lt"           # inférieur (<)
    LTE = "lte"         # inférieur ou égal (<=)
    CONTAINS = "contains"       # contient (case-insensitive)
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    IS_NULL = "is_null"         # champ absent ou None
    IS_NOT_NULL = "is_not_null" # champ présent et non None
    IN = "in"                   # dans une liste de valeurs


class SortDirection(str, Enum):
    ASC = "asc"
    DESC = "desc"


class ExportFormat(str, Enum):
    JSON = "json"
    CSV = "csv"
    EXCEL = "xlsx"
    PDF = "pdf"
    MARKDOWN = "md"


# ---------------------------------------------------------------------------
# Blocs de base
# ---------------------------------------------------------------------------

class FilterDefinition(BaseModel):
    """Un filtre sur un champ d'un endpoint.

    Exemples :
        FilterDefinition(field="security_need_c", operator=FilterOperator.GTE, value=3)
        FilterDefinition(field="rto", operator=FilterOperator.IS_NOT_NULL)
        FilterDefinition(field="name", operator=FilterOperator.CONTAINS, value="SAP")
        FilterDefinition(field="type", operator=FilterOperator.IN, value=["ERP", "Web"])
    """
    field: str = Field(..., description="Nom du champ Mercator à filtrer")
    operator: FilterOperator = Field(default=FilterOperator.EQ)
    value: Any = Field(default=None, description="Valeur de comparaison (None pour IS_NULL/IS_NOT_NULL)")

    @field_validator("value")
    @classmethod
    def validate_value_for_operator(cls, v, info):
        op = info.data.get("operator")
        if op in (FilterOperator.IS_NULL, FilterOperator.IS_NOT_NULL):
            return None  # valeur ignorée
        if op == FilterOperator.IN and v is not None and not isinstance(v, list):
            raise ValueError("L'opérateur 'in' requiert une liste de valeurs")
        return v


class SortDefinition(BaseModel):
    """Tri sur un champ."""
    field: str
    direction: SortDirection = SortDirection.ASC


class ColumnDefinition(BaseModel):
    """Colonne à inclure dans le rapport.

    Permet de renommer un champ Mercator pour l'affichage.
    Exemple : ColumnDefinition(field="recovery_time_objective", label="RTO (h)")
    """
    field: str = Field(..., description="Nom du champ Mercator source")
    label: str | None = Field(default=None, description="Libellé affiché (None = utiliser field)")

    @property
    def display_label(self) -> str:
        return self.label or self.field


# ---------------------------------------------------------------------------
# Jointure
# ---------------------------------------------------------------------------

class JoinDefinition(BaseModel):
    """Jointure entre l'endpoint principal et un endpoint secondaire.

    Mercator stocke les relations dans les réponses détaillées sous forme
    de listes d'objets imbriqués. JoinDefinition décrit comment enrichir
    chaque ligne principale avec des champs de ces objets liés.

    Exemples :
        # Applications → serveurs logiques
        JoinDefinition(
            relation_key="logical_servers",     # champ dans l'objet application
            fields=["name", "operating_system"],
            prefix="server_",
        )
        # Résultat : chaque application aura server_name, server_operating_system

        # Applications → entité responsable (relation 1-1 via entity_resp_id)
        JoinDefinition(
            endpoint="entities",
            foreign_key="entity_resp_id",
            fields=["name"],
            prefix="entity_",
        )
    """
    # Mode 1 — relation imbriquée (champ déjà présent dans l'objet avec include_relations)
    relation_key: str | None = Field(
        default=None,
        description="Clé de la relation imbriquée dans l'objet principal (ex: 'logical_servers')",
    )

    # Mode 2 — jointure par clé étrangère (nécessite un appel séparé)
    endpoint: str | None = Field(
        default=None,
        description="Endpoint Mercator à joindre (ex: 'entities')",
    )
    foreign_key: str | None = Field(
        default=None,
        description="Champ de l'objet principal contenant l'ID de l'objet lié (ex: 'entity_resp_id')",
    )

    # Champs à extraire de l'objet lié
    fields: list[str] = Field(
        default_factory=list,
        description="Champs à extraire de l'objet lié. Vide = tous les champs.",
    )

    # Valeur par défaut si la jointure ne trouve pas de correspondance
    default: dict[str, Any] | None = Field(
        default=None,
        description="Valeurs par défaut si la jointure échoue (ex: {'name': 'Non classé'})",
    )

    # Préfixe pour éviter les collisions de noms
    prefix: str = Field(
        default="",
        description="Préfixe ajouté aux champs extraits (ex: 'server_' → server_name)",
    )


# ---------------------------------------------------------------------------
# Requête de rapport
# ---------------------------------------------------------------------------

class ReportQuery(BaseModel):
    """Requête de rapport — entrée du ReportEngine.

    Décrit quoi récupérer, comment filtrer, trier et présenter les données.

    Exemple — Rapport BIA (activités avec RTO/RPO renseignés) :
        ReportQuery(
            endpoint="activities",
            columns=[
                ColumnDefinition(field="name", label="Activité"),
                ColumnDefinition(field="recovery_time_objective", label="RTO (h)"),
                ColumnDefinition(field="recovery_point_objective", label="RPO (h)"),
                ColumnDefinition(field="maximum_tolerable_downtime", label="MTD (h)"),
            ],
            filters=[
                FilterDefinition(field="recovery_time_objective", operator=FilterOperator.IS_NOT_NULL)
            ],
            sort=[SortDefinition(field="recovery_time_objective", direction=SortDirection.ASC)],
            limit=100,
        )
    """
    # Source principale
    endpoint: str = Field(..., description="Endpoint Mercator source (ex: 'applications')")

    # Colonnes à projeter ([] = toutes les colonnes)
    columns: list[ColumnDefinition] = Field(
        default_factory=list,
        description="Colonnes à inclure. Vide = toutes les colonnes.",
    )

    # Filtres (combinés en AND)
    filters: list[FilterDefinition] = Field(
        default_factory=list,
        description="Filtres à appliquer (tous combinés en AND).",
    )

    # Tri
    sort: list[SortDefinition] = Field(default_factory=list)

    # Pagination
    limit: int = Field(default=100, ge=1, le=10000)
    offset: int = Field(default=0, ge=0)

    # Jointures avec d'autres endpoints
    joins: list[JoinDefinition] = Field(
        default_factory=list,
        description="Jointures avec d'autres endpoints Mercator.",
    )

    # Options
    include_relations: bool = Field(
        default=False,
        description="Si True, charge les relations de chaque objet (plus lent).",
    )
    title: str | None = Field(default=None, description="Titre du rapport (pour export)")

    @field_validator("endpoint")
    @classmethod
    def endpoint_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("L'endpoint ne peut pas être vide")
        return v.strip()


# ---------------------------------------------------------------------------
# Résultat de rapport
# ---------------------------------------------------------------------------

class ReportRow(BaseModel):
    """Une ligne du rapport — projection des colonnes demandées."""
    data: dict[str, Any] = Field(..., description="Données de la ligne {label: valeur}")


class ReportMetadata(BaseModel):
    """Méta-données du rapport généré."""
    endpoint: str
    total_items: int = Field(..., description="Nombre total avant pagination")
    returned_items: int = Field(..., description="Nombre de lignes retournées")
    offset: int
    limit: int
    filters_applied: int = Field(..., description="Nombre de filtres actifs")
    columns: list[str] = Field(..., description="Labels des colonnes dans l'ordre")
    title: str | None = None
    generated_at: str | None = None  # ISO 8601


class ReportResult(BaseModel):
    """Résultat complet d'un rapport — sortie du ReportEngine.

    Passé directement au ExportService pour générer PDF/Excel/CSV.
    """
    metadata: ReportMetadata
    rows: list[ReportRow]

    @property
    def is_empty(self) -> bool:
        return len(self.rows) == 0

    def to_records(self) -> list[dict[str, Any]]:
        """Retourne les données sous forme de liste de dicts plats.

        Utile pour l'export CSV/Excel.
        """
        return [row.data for row in self.rows]