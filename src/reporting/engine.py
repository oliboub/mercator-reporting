"""ReportEngine — Moteur de rapports dynamiques Mercator.

Pipeline d'exécution d'une ReportQuery :
    1. Fetch         — récupère les données depuis MercatorClient (avec cache)
    2. Filter        — applique les FilterDefinition (AND)
    3. Enrich        — jointures avec d'autres endpoints (JoinDefinition)
    4. Sort          — tri multi-champs
    5. Paginate      — limit / offset
    6. Project       — projection des colonnes demandées

Usage :
    engine = ReportEngine(mercator_client)

    result = engine.execute(ReportQuery(
        endpoint="activities",
        columns=[
            ColumnDefinition(field="name", label="Activité"),
            ColumnDefinition(field="recovery_time_objective", label="RTO (h)"),
        ],
        filters=[
            FilterDefinition(field="recovery_time_objective", operator=FilterOperator.IS_NOT_NULL)
        ],
        sort=[SortDefinition(field="recovery_time_objective")],
    ))
"""
import logging
from datetime import datetime, timezone
from typing import Any

from src.core.mercator_client import MercatorClient, MercatorAPIError, MERCATOR_ENDPOINTS
from src.models.report import (
    ReportQuery, ReportResult, ReportRow, ReportMetadata,
    JoinDefinition, ColumnDefinition,
)
from src.reporting.filters import apply_filters, apply_sort, apply_projection

logger = logging.getLogger(__name__)


class ReportEngineError(Exception):
    """Erreur levée par le ReportEngine."""


class ReportEngine:
    """Moteur d'exécution de rapports Mercator.

    Prend une ReportQuery, orchestre les étapes du pipeline,
    et retourne un ReportResult prêt pour l'export.
    """

    def __init__(self, client: MercatorClient):
        self._client = client

    # -------------------------------------------------------------------------
    # Point d'entrée public
    # -------------------------------------------------------------------------

    def execute(self, query: ReportQuery) -> ReportResult:
        """Exécute une ReportQuery et retourne un ReportResult.

        Args:
            query: requête de rapport (endpoint, filtres, jointures, tri, colonnes)

        Returns:
            ReportResult avec métadonnées et lignes projetées.

        Raises:
            ReportEngineError: si l'endpoint est inconnu ou si une erreur Mercator survient.
        """
        logger.info("ReportEngine.execute — endpoint=%s filters=%d joins=%d",
                    query.endpoint, len(query.filters), len(query.joins))

        # 1. Validation de l'endpoint
        self._validate_endpoint(query.endpoint)

        # 2. Fetch
        items = self._fetch(query)
        total_fetched = len(items)

        # 3. Filter
        items = apply_filters(items, query.filters)
        total_filtered = len(items)

        # 4. Enrich (jointures)
        if query.joins:
            items = self._enrich(items, query.joins)

        # 5. Sort
        for sort_def in reversed(query.sort):
            items = apply_sort(
                items,
                sort_field=sort_def.field,
                ascending=(sort_def.direction.value == "asc"),
            )

        # 6. Paginate
        total_after_filter = len(items)
        paginated = items[query.offset: query.offset + query.limit]

        # 7. Project colonnes
        columns = query.columns
        rows = [
            ReportRow(data=self._project_row(obj, columns))
            for obj in paginated
        ]

        # Métadonnées
        column_labels = (
            [c.display_label for c in columns]
            if columns
            else (list(paginated[0].keys()) if paginated else [])
        )

        metadata = ReportMetadata(
            endpoint=query.endpoint,
            total_items=total_after_filter,
            returned_items=len(rows),
            offset=query.offset,
            limit=query.limit,
            filters_applied=len(query.filters),
            columns=column_labels,
            title=query.title,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

        logger.info(
            "ReportEngine.execute — %d/%d objets retournés (fetched=%d, filtered=%d)",
            len(rows), total_after_filter, total_fetched, total_filtered,
        )

        return ReportResult(metadata=metadata, rows=rows)

    # -------------------------------------------------------------------------
    # Étape 1 — Fetch
    # -------------------------------------------------------------------------

    def _fetch(self, query: ReportQuery) -> list[dict[str, Any]]:
        """Récupère les données depuis MercatorClient.

        Si include_relations=True, appelle get_object() pour chaque item
        afin d'obtenir les relations imbriquées (actors, logical_servers, etc.)
        Sinon, appelle get_endpoint() (plus rapide, utilise le cache).
        """
        try:
            if query.include_relations:
                logger.debug("Fetch avec relations — endpoint=%s", query.endpoint)
                return self._client.get_endpoint_detail(query.endpoint)
            else:
                logger.debug("Fetch sans relations — endpoint=%s", query.endpoint)
                return self._client.get_endpoint(query.endpoint)
        except MercatorAPIError as e:
            raise ReportEngineError(
                f"Impossible de récupérer les données de '{query.endpoint}' : {e}"
            ) from e

    # -------------------------------------------------------------------------
    # Étape 3 — Enrich (jointures)
    # -------------------------------------------------------------------------

    def _enrich(
        self,
        items: list[dict[str, Any]],
        joins: list[JoinDefinition],
    ) -> list[dict[str, Any]]:
        """Enrichit chaque objet avec les données des jointures définies.

        Deux modes :
        - Mode relation imbriquée (relation_key) : la donnée est déjà dans l'objet
          sous forme de liste (retournée par get_object avec include=...).
          On extrait les champs demandés du premier élément (ou de tous).

        - Mode clé étrangère (endpoint + foreign_key) : on récupère l'endpoint
          cible et on joint par ID. Ex: entity_resp_id → entities[id].
        """
        # Pré-charger les endpoints nécessaires pour les jointures par FK
        endpoint_cache: dict[str, dict[int, dict]] = {}
        for join in joins:
            if join.endpoint and join.foreign_key and join.endpoint not in endpoint_cache:
                endpoint_cache[join.endpoint] = self._load_endpoint_as_dict(join.endpoint)

        enriched = []
        for obj in items:
            enriched_obj = dict(obj)
            for join in joins:
                enriched_obj = self._apply_join(enriched_obj, join, endpoint_cache)
            enriched.append(enriched_obj)

        return enriched

    def _apply_join(
        self,
        obj: dict[str, Any],
        join: JoinDefinition,
        endpoint_cache: dict[str, dict[int, dict]],
    ) -> dict[str, Any]:
        """Applique une jointure sur un objet et retourne l'objet enrichi."""

        # Mode 1 — relation imbriquée (ex: obj["logical_servers"] = [{...}, {...}])
        if join.relation_key:
            related = obj.get(join.relation_key)
            if related and isinstance(related, list) and len(related) > 0:
                first = related[0] if isinstance(related[0], dict) else {}
                extracted = apply_projection(first, join.fields)
                for k, v in extracted.items():
                    obj[f"{join.prefix}{k}"] = v
            elif related and isinstance(related, dict):
                extracted = apply_projection(related, join.fields)
                for k, v in extracted.items():
                    obj[f"{join.prefix}{k}"] = v
            else:
                defaults = join.default or {}
                for field in join.fields:
                    obj[f"{join.prefix}{field}"] = defaults.get(field)
            return obj

        # Mode 2 — clé étrangère (ex: obj["entity_resp_id"] → entities[id])
        if join.endpoint and join.foreign_key:
            fk_value = obj.get(join.foreign_key)
            related_index = endpoint_cache.get(join.endpoint, {})
            related_obj = related_index.get(fk_value) if fk_value is not None else None

            if related_obj:
                extracted = apply_projection(related_obj, join.fields)
                for k, v in extracted.items():
                    obj[f"{join.prefix}{k}"] = v
            else:
                defaults = join.default or {}
                for field in join.fields:
                    obj[f"{join.prefix}{field}"] = defaults.get(field)
            return obj

        logger.warning("JoinDefinition invalide : ni relation_key ni (endpoint + foreign_key)")
        return obj

    def _load_endpoint_as_dict(self, endpoint: str) -> dict[int, dict]:
        """Charge un endpoint et l'indexe par ID pour les jointures FK.

        Returns:
            Dict {id: objet} pour accès O(1) lors de la jointure.
        """
        try:
            items = self._client.get_endpoint(endpoint)
            return {item["id"]: item for item in items if "id" in item}
        except MercatorAPIError as e:
            logger.warning("Impossible de charger l'endpoint '%s' pour jointure : %s", endpoint, e)
            return {}

    # -------------------------------------------------------------------------
    # Étape 6 — Projection
    # -------------------------------------------------------------------------

    @staticmethod
    def _project_row(
        obj: dict[str, Any],
        columns: list[ColumnDefinition],
    ) -> dict[str, Any]:
        """Projette un objet sur les colonnes demandées avec leurs labels.

        Si columns est vide, retourne l'objet complet.
        Sinon, retourne {label: valeur} pour chaque colonne.
        """
        if not columns:
            return obj
        return {col.display_label: obj.get(col.field) for col in columns}

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    @staticmethod
    def _validate_endpoint(endpoint: str) -> None:
        """Vérifie que l'endpoint est connu dans Mercator."""
        if endpoint not in MERCATOR_ENDPOINTS:
            raise ReportEngineError(
                f"Endpoint inconnu : '{endpoint}'. "
                f"Endpoints disponibles : {', '.join(MERCATOR_ENDPOINTS[:5])}…"
            )