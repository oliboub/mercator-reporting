"""ReportEngine — Moteur de rapports dynamiques Mercator.

Pipeline : Fetch → Filter → Enrich → Sort → Paginate → Project
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

# Mapping relation_key → endpoint pour résoudre les IDs
RELATION_KEY_TO_ENDPOINT: dict[str, str] = {
    "logical_servers": "logical-servers",
    "physical_servers": "physical-servers",
    "applications": "applications",
    "databases": "databases",
    "actors": "actors",
    "processes": "processes",
    "activities": "activities",
    "clusters": "clusters",
    "containers": "containers",
    "modules": "application-modules",
}


class ReportEngineError(Exception):
    pass


class ReportEngine:

    def __init__(self, client: MercatorClient):
        self._client = client

    def execute(self, query: ReportQuery) -> ReportResult:
        items = self._fetch(query)
        total_fetched = len(items)

        # Séparer les filtres : natifs (avant enrichissement) vs préfixés (après)
        prefixes = {j.prefix for j in query.joins if j.prefix}
        native_filters = [
            f for f in query.filters
            if not any(f.field.startswith(p) for p in prefixes)
        ]
        post_filters = [
            f for f in query.filters
            if any(f.field.startswith(p) for p in prefixes)
        ]

        filtered = apply_filters(items, native_filters)
        total_filtered = len(filtered)

        enriched = self._enrich(filtered, query.joins)

        # Filtres post-enrichissement (sur champs préfixés ex: block_name)
        if post_filters:
            enriched = apply_filters(enriched, post_filters)

        # Nettoyer les relations brutes (listes d'IDs) après enrichissement
        cleaned = [self._strip_raw_relations(obj, query.joins) for obj in enriched]

        # Tri multi-champs (appliqué en ordre inverse pour stabilité)
        sorted_items = cleaned
        for sort_def in reversed(query.sort):
            from src.models.report import SortDirection
            ascending = sort_def.direction == SortDirection.ASC
            sorted_items = apply_sort(sorted_items, sort_def.field, ascending=ascending)

        total_after_sort = len(sorted_items)
        paginated = sorted_items[query.offset: query.offset + query.limit]

        rows = [ReportRow(data=self._project_row(obj, query.columns)) for obj in paginated]

        col_labels = (
            [c.label for c in query.columns]
            if query.columns
            else (list(rows[0].data.keys()) if rows else [])
        )

        return ReportResult(
            metadata=ReportMetadata(
                endpoint=query.endpoint,
                total_items=total_after_sort,
                returned_items=len(rows),
                offset=query.offset,
                limit=query.limit,
                filters_applied=len([f for f in query.filters if f.value is not None
                                     or f.operator.value in ("is_null", "is_not_null")]),
                columns=col_labels,
                title=query.title or query.endpoint,
                generated_at=datetime.now(timezone.utc).isoformat(),
            ),
            rows=rows,
        )

    # -------------------------------------------------------------------------
    # Étape 1 — Fetch
    # -------------------------------------------------------------------------

    def _fetch(self, query: ReportQuery) -> list[dict[str, Any]]:
        """Récupère les données depuis MercatorClient.

        Mode API filtrée (prioritaire) : délègue au serveur les filtres natifs uniquement.
        Les filtres sur champs préfixés (ex: block_name) sont réservés au post-traitement.

        Mode Python (fallback) : charge tout et filtre en mémoire.
        """
        # Identifier les préfixes de jointures → champs préfixés non natifs
        prefixes = {j.prefix for j in query.joins if j.prefix}

        # Séparer filtres natifs (champs de l'endpoint) vs post-jointure (champs préfixés)
        native_filters = [
            f for f in query.filters
            if not any(f.field.startswith(p) for p in prefixes)
        ]

        try:
            if self._can_use_server_filters(native_filters, query.sort):
                logger.debug("Fetch mode API filtrée — endpoint=%s", query.endpoint)
                rk_includes = [j.relation_key for j in query.joins if j.relation_key]
                return self._client.get_endpoint_filtered(
                    query.endpoint,
                    filters=native_filters,
                    sort=query.sort if query.sort else [],
                    include=rk_includes,
                )
            elif query.include_relations:
                logger.debug("Fetch mode relations — endpoint=%s", query.endpoint)
                return self._client.get_endpoint_detail(query.endpoint)
            else:
                logger.debug("Fetch mode Python — endpoint=%s", query.endpoint)
                return self._client.get_endpoint(query.endpoint)
        except MercatorAPIError as e:
            raise ReportEngineError(f"Impossible de récupérer '{query.endpoint}' : {e}") from e

    @staticmethod
    def _can_use_server_filters(native_filters: list, sort: list) -> bool:
        """Détermine si on peut déléguer filtres natifs+tri à l'API Mercator.

        Conditions :
        - Au moins un filtre natif ou un tri défini
        - Aucun opérateur non supporté côté serveur
        """
        from src.models.report import FilterOperator
        UNSUPPORTED = {FilterOperator.NOT_CONTAINS, FilterOperator.STARTS_WITH}

        if not native_filters and not sort:
            return False

        for f in native_filters:
            if f.operator in UNSUPPORTED:
                return False

        return True

    # -------------------------------------------------------------------------
    # Étape 3 — Enrich (jointures)
    # -------------------------------------------------------------------------

    def _enrich(self, items: list[dict], joins: list[JoinDefinition]) -> list[dict]:
        if not joins:
            return items

        # Pré-charger les endpoints FK
        endpoint_cache: dict[str, dict[int, dict]] = {}
        for join in joins:
            if join.endpoint and join.foreign_key and join.endpoint not in endpoint_cache:
                endpoint_cache[join.endpoint] = self._load_endpoint_as_dict(join.endpoint)

        enriched = []
        for obj in items:
            expanded = self._expand_relation_keys(obj, joins, endpoint_cache)
            enriched.extend(expanded)
        return enriched

    def _expand_relation_keys(
        self,
        obj: dict[str, Any],
        joins: list[JoinDefinition],
        endpoint_cache: dict[str, dict[int, dict]],
    ) -> list[dict[str, Any]]:
        """Expand les jointures relation_key en N lignes si la relation a N éléments."""
        rk_joins = [j for j in joins if j.relation_key]
        fk_joins = [j for j in joins if not j.relation_key]

        if not rk_joins:
            row = dict(obj)
            for join in fk_joins:
                row = self._apply_fk_join(row, join, endpoint_cache)
            return [row]

        primary_rk = rk_joins[0]
        other_rk = rk_joins[1:]

        related_list = obj.get(primary_rk.relation_key)

        # Résoudre les IDs si la relation retourne des entiers
        if related_list and isinstance(related_list, list) and len(related_list) > 0:
            if isinstance(related_list[0], int):
                related_list = self._resolve_ids(primary_rk.relation_key, related_list)

        result_rows = []
        if related_list and isinstance(related_list, list) and len(related_list) > 0:
            for related_item in related_list:
                row = dict(obj)
                if isinstance(related_item, dict):
                    extracted = apply_projection(related_item, primary_rk.fields)
                    for k, v in extracted.items():
                        row[f"{primary_rk.prefix}{k}"] = v
                for other_join in other_rk:
                    row = self._apply_join(row, other_join, endpoint_cache)
                for join in fk_joins:
                    row = self._apply_fk_join(row, join, endpoint_cache)
                result_rows.append(row)
        else:
            row = dict(obj)
            defaults = primary_rk.default or {}
            for field in primary_rk.fields:
                row[f"{primary_rk.prefix}{field}"] = defaults.get(field)
            for join in fk_joins:
                row = self._apply_fk_join(row, join, endpoint_cache)
            result_rows.append(row)

        return result_rows

    def _resolve_ids(self, relation_key: str, ids: list[int]) -> list[dict]:
        """Résout une liste d'IDs en objets complets via l'endpoint correspondant."""
        endpoint = RELATION_KEY_TO_ENDPOINT.get(relation_key)
        if not endpoint:
            logger.warning("Pas d'endpoint connu pour relation_key='%s'", relation_key)
            return []
        try:
            all_items = self._client.get_endpoint(endpoint)
            index = {item["id"]: item for item in all_items if "id" in item}
            resolved = [index[i] for i in ids if i in index]
            logger.debug("_resolve_ids %s: %d/%d résolus", relation_key, len(resolved), len(ids))
            return resolved
        except MercatorAPIError as e:
            logger.warning("Impossible de résoudre les IDs pour '%s' : %s", relation_key, e)
            return []

    def _apply_join(
        self,
        obj: dict[str, Any],
        join: JoinDefinition,
        endpoint_cache: dict[str, dict[int, dict]],
    ) -> dict[str, Any]:
        """Mode first pour relation_key secondaire."""
        if join.relation_key:
            related = obj.get(join.relation_key)
            # Résoudre les IDs si besoin
            if related and isinstance(related, list) and len(related) > 0:
                if isinstance(related[0], int):
                    related = self._resolve_ids(join.relation_key, related)
            if related and isinstance(related, list) and len(related) > 0:
                first = related[0] if isinstance(related[0], dict) else {}
                extracted = apply_projection(first, join.fields)
                for k, v in extracted.items():
                    obj[f"{join.prefix}{k}"] = v
            else:
                defaults = join.default or {}
                for field in join.fields:
                    obj[f"{join.prefix}{field}"] = defaults.get(field)
            return obj
        return self._apply_fk_join(obj, join, endpoint_cache)

    def _apply_fk_join(
        self,
        obj: dict[str, Any],
        join: JoinDefinition,
        endpoint_cache: dict[str, dict[int, dict]],
    ) -> dict[str, Any]:
        """Jointure par clé étrangère."""
        if not (join.endpoint and join.foreign_key):
            return obj
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

    def _load_endpoint_as_dict(self, endpoint: str) -> dict[int, dict]:
        try:
            items = self._client.get_endpoint(endpoint)
            return {item["id"]: item for item in items if "id" in item}
        except MercatorAPIError as e:
            logger.warning("Impossible de charger '%s' pour jointure : %s", endpoint, e)
            return {}

    # -------------------------------------------------------------------------
    # Étape 6 — Projection
    # -------------------------------------------------------------------------

    @staticmethod
    def _strip_raw_relations(obj: dict[str, Any], joins: list[JoinDefinition]) -> dict[str, Any]:
        """Supprime les champs de relations brutes (listes d'IDs/objets) après enrichissement.

        Garde uniquement les champs scalaires et les champs préfixés générés par les jointures.
        """
        # Clés de relations brutes à supprimer (relation_key utilisées)
        rk_keys = {j.relation_key for j in joins if j.relation_key}
        # Supprimer aussi toutes les listes/dicts non préfixés résiduels
        result = {}
        for k, v in obj.items():
            if k in rk_keys:
                continue  # relation déjà traitée
            if isinstance(v, list):
                continue  # liste résiduelle (activities, services, etc.)
            result[k] = v
        return result

    @staticmethod
    def _project_row(obj: dict[str, Any], columns: list[ColumnDefinition]) -> dict[str, Any]:
        if not columns:
            return obj
        result = {}
        for col in columns:
            result[col.label] = obj.get(col.field)
        return result

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    @staticmethod
    def _validate_endpoint(endpoint: str) -> None:
        if endpoint not in MERCATOR_ENDPOINTS:
            raise ReportEngineError(
                f"Endpoint '{endpoint}' inconnu. "
                f"Endpoints disponibles : {', '.join(MERCATOR_ENDPOINTS)}"
            )
