"""Moteur de filtres dynamiques pour le ReportEngine.

Applique des FilterDefinition sur une liste d'objets Mercator (dicts).
Aucune dépendance externe — logique Python pure, entièrement testable sans réseau.

Usage :
    from src.reporting.filters import apply_filters
    from src.models.report import FilterDefinition, FilterOperator

    items = [{"name": "SAP ECC", "security_need_c": 3, "rto": None}, ...]

    filtered = apply_filters(items, [
        FilterDefinition(field="security_need_c", operator=FilterOperator.GTE, value=3),
        FilterDefinition(field="rto", operator=FilterOperator.IS_NOT_NULL),
    ])
"""
import logging
from typing import Any

from src.models.report import FilterDefinition, FilterOperator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Évaluation d'un filtre sur une valeur
# ---------------------------------------------------------------------------

def _evaluate(field_value: Any, operator: FilterOperator, filter_value: Any) -> bool:
    """Évalue un opérateur de filtre sur une valeur de champ.

    Args:
        field_value: valeur extraite de l'objet Mercator
        operator: opérateur de comparaison
        filter_value: valeur du filtre (peut être None pour IS_NULL/IS_NOT_NULL)

    Returns:
        True si la condition est satisfaite, False sinon.
    """
    # Opérateurs de nullité — indépendants du type
    if operator == FilterOperator.IS_NULL:
        return field_value is None or field_value == ""
    if operator == FilterOperator.IS_NOT_NULL:
        return field_value is not None and field_value != ""

    # Si la valeur du champ est None, les comparaisons suivantes échouent
    # sauf IS_NULL déjà traité — on retourne False pour tous les autres
    if field_value is None:
        return False

    # Opérateur IN — teste l'appartenance à une liste
    if operator == FilterOperator.IN:
        if not isinstance(filter_value, list):
            return False
        return field_value in filter_value

    # Comparaisons sur chaînes (case-insensitive)
    if operator in (FilterOperator.CONTAINS, FilterOperator.NOT_CONTAINS,
                    FilterOperator.STARTS_WITH):
        str_field = str(field_value).lower()
        str_filter = str(filter_value).lower() if filter_value is not None else ""

        if operator == FilterOperator.CONTAINS:
            return str_filter in str_field
        if operator == FilterOperator.NOT_CONTAINS:
            return str_filter not in str_field
        if operator == FilterOperator.STARTS_WITH:
            return str_field.startswith(str_filter)

    # Comparaisons numériques et d'égalité
    try:
        if operator == FilterOperator.EQ:
            # Comparaison souple : "3" == 3
            return str(field_value) == str(filter_value) or field_value == filter_value
        if operator == FilterOperator.NEQ:
            return str(field_value) != str(filter_value) and field_value != filter_value
        if operator == FilterOperator.GT:
            return float(field_value) > float(filter_value)
        if operator == FilterOperator.GTE:
            return float(field_value) >= float(filter_value)
        if operator == FilterOperator.LT:
            return float(field_value) < float(filter_value)
        if operator == FilterOperator.LTE:
            return float(field_value) <= float(filter_value)
    except (TypeError, ValueError):
        # Conversion numérique impossible (ex: "N/A" > 3)
        logger.debug(
            "Impossible de comparer '%s' avec opérateur %s sur valeur '%s'",
            field_value, operator, filter_value
        )
        return False

    return False


# ---------------------------------------------------------------------------
# Évaluation d'un filtre sur un objet
# ---------------------------------------------------------------------------

def _matches_filter(obj: dict[str, Any], f: FilterDefinition) -> bool:
    """Teste si un objet Mercator satisfait un FilterDefinition.

    Supporte les champs imbriqués via la notation pointée :
        "logical_servers.operating_system" → obj["logical_servers"][0]["operating_system"]
    """
    # Champ simple
    if "." not in f.field:
        field_value = obj.get(f.field)
        return _evaluate(field_value, f.operator, f.value)

    # Champ imbriqué (ex: "logical_servers.operating_system")
    parts = f.field.split(".", 1)
    parent_key, child_key = parts[0], parts[1]
    parent_value = obj.get(parent_key)

    if parent_value is None:
        return f.operator == FilterOperator.IS_NULL

    # Si le parent est une liste (relations Mercator), on teste sur chaque élément
    if isinstance(parent_value, list):
        return any(
            _evaluate(item.get(child_key) if isinstance(item, dict) else None,
                      f.operator, f.value)
            for item in parent_value
        )

    # Si le parent est un dict
    if isinstance(parent_value, dict):
        return _evaluate(parent_value.get(child_key), f.operator, f.value)

    return False


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------

def apply_filters(
    items: list[dict[str, Any]],
    filters: list[FilterDefinition],
) -> list[dict[str, Any]]:
    """Applique une liste de filtres sur une liste d'objets Mercator.

    Les filtres sont combinés en AND — un objet doit satisfaire TOUS les filtres.

    Args:
        items: liste d'objets Mercator (dicts)
        filters: liste de FilterDefinition à appliquer

    Returns:
        Sous-liste des objets satisfaisant tous les filtres.
    """
    if not filters:
        return items

    result = []
    for obj in items:
        if all(_matches_filter(obj, f) for f in filters):
            result.append(obj)

    logger.debug(
        "apply_filters : %d/%d objets après %d filtres",
        len(result), len(items), len(filters)
    )
    return result


def apply_sort(
    items: list[dict[str, Any]],
    sort_field: str,
    ascending: bool = True,
    none_last: bool = True,
) -> list[dict[str, Any]]:
    """Trie une liste d'objets Mercator sur un champ.

    Args:
        items: liste d'objets Mercator
        sort_field: nom du champ sur lequel trier
        ascending: True = ASC, False = DESC
        none_last: si True, les valeurs None sont placées en fin de liste

    Returns:
        Liste triée (nouvelle liste, items non modifiés).
    """
    def sort_key(obj: dict[str, Any]):
        val = obj.get(sort_field)
        if val is None:
            return (1, 0) if none_last else (-1, 0)
        # Ignorer les listes et dicts — les traiter comme None
        if isinstance(val, (list, dict)):
            return (1, 0) if none_last else (-1, 0)
        try:
            return (0, float(val))
        except (TypeError, ValueError):
            return (0, str(val).lower())

    return sorted(items, key=sort_key, reverse=not ascending)


def apply_projection(
    obj: dict[str, Any],
    fields: list[str],
) -> dict[str, Any]:
    """Projette un objet Mercator sur un sous-ensemble de champs.

    Args:
        obj: objet Mercator complet
        fields: liste des champs à conserver ([] = tous)

    Returns:
        Dict avec seulement les champs demandés.
        Si fields est vide, retourne l'objet complet.
    """
    if not fields:
        return obj
    return {field: obj.get(field) for field in fields}
