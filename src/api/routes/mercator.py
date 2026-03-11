"""Routes FastAPI — Accès aux données Mercator CMDB.

Expose :
  GET /api/mercator/endpoints          → liste des endpoints disponibles
  GET /api/mercator/{endpoint}         → liste des objets d'un endpoint
  GET /api/mercator/{endpoint}/{id}    → détail d'un objet avec relations
  GET /api/mercator/{endpoint}/export  → export JSON de l'endpoint complet
  GET /api/mercator/health             → statut de connexion Mercator
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from src.core.mercator_client import (
    MercatorClient,
    MercatorAPIError,
    MercatorAuthError,
    MERCATOR_ENDPOINTS,
)
from src.core.dependencies import get_mercator_client

router = APIRouter(prefix="/api/mercator", tags=["Mercator CMDB"])


# ---------------------------------------------------------------------------
# Health & Discovery
# ---------------------------------------------------------------------------

@router.get("/health", summary="Statut de connexion Mercator CMDB")
async def mercator_health(
    client: MercatorClient = Depends(get_mercator_client),
):
    """Vérifie que l'API Mercator est joignable et que les credentials sont valides."""
    result = client.check_connection()
    status_code = 200 if result["status"] == "ok" else 503
    return JSONResponse(content=result, status_code=status_code)


@router.get("/endpoints", summary="Liste de tous les endpoints Mercator disponibles")
async def list_endpoints():
    """Retourne la liste exhaustive des endpoints Mercator connus."""
    return {"endpoints": MERCATOR_ENDPOINTS, "total": len(MERCATOR_ENDPOINTS)}


# ---------------------------------------------------------------------------
# Liste + Filtrage
# ---------------------------------------------------------------------------

@router.get("/{endpoint}", summary="Liste des objets d'un endpoint Mercator")
async def get_endpoint_list(
    endpoint: str,
    search: str | None = Query(None, description="Filtre sur le champ 'name' (insensible à la casse)"),
    limit: int = Query(100, ge=1, le=1000, description="Nombre max d'objets retournés"),
    offset: int = Query(0, ge=0, description="Décalage pour la pagination"),
    client: MercatorClient = Depends(get_mercator_client),
):
    """Récupère la liste des objets d'un endpoint Mercator.

    Supporte :
    - Filtrage par nom (paramètre `search`)
    - Pagination (`limit` / `offset`)

    Exemples :
    - `/api/mercator/applications`
    - `/api/mercator/applications?search=SAP`
    - `/api/mercator/logical-servers?limit=20&offset=0`
    """
    _validate_endpoint(endpoint)

    try:
        items = client.get_endpoint(endpoint)
    except MercatorAuthError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except MercatorAPIError as e:
        raise HTTPException(status_code=e.status_code or 502, detail=str(e))

    # Filtrage par nom
    if search:
        search_lower = search.lower()
        items = [
            item for item in items
            if search_lower in str(item.get("name", "")).lower()
        ]

    total = len(items)
    paginated = items[offset: offset + limit]

    return {
        "endpoint": endpoint,
        "total": total,
        "limit": limit,
        "offset": offset,
        "count": len(paginated),
        "data": paginated,
    }


# ---------------------------------------------------------------------------
# Détail par ID
# ---------------------------------------------------------------------------

@router.get("/{endpoint}/{obj_id}", summary="Détail d'un objet Mercator avec ses relations")
async def get_object_detail(
    endpoint: str,
    obj_id: int,
    with_relations: bool = Query(True, description="Inclure les relations (actors, processes, etc.)"),
    client: MercatorClient = Depends(get_mercator_client),
):
    """Récupère le détail complet d'un objet Mercator par son ID.

    Inclut automatiquement les relations (actors, processes, logical_servers, etc.)
    sauf si `with_relations=false`.

    Exemples :
    - `/api/mercator/applications/1`
    - `/api/mercator/logical-servers/3?with_relations=false`
    """
    _validate_endpoint(endpoint)

    try:
        obj = client.get_object(endpoint, obj_id, with_relations=with_relations)
    except MercatorAuthError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except MercatorAPIError as e:
        if e.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail=f"Objet {endpoint}/{obj_id} introuvable dans Mercator",
            )
        raise HTTPException(status_code=e.status_code or 502, detail=str(e))

    return {"endpoint": endpoint, "id": obj_id, "data": obj}


# ---------------------------------------------------------------------------
# Export JSON complet
# ---------------------------------------------------------------------------

@router.get("/{endpoint}/export/json", summary="Export JSON complet d'un endpoint")
async def export_endpoint_json(
    endpoint: str,
    with_relations: bool = Query(False, description="Inclure les détails et relations (plus lent)"),
    client: MercatorClient = Depends(get_mercator_client),
):
    """Exporte tous les objets d'un endpoint au format JSON.

    Sans `with_relations` : export rapide de la liste brute.
    Avec `with_relations` : appel détaillé par objet (plus lent, plus complet).

    Exemples :
    - `/api/mercator/applications/export/json`
    - `/api/mercator/applications/export/json?with_relations=true`
    """
    _validate_endpoint(endpoint)

    try:
        if with_relations:
            items = client.get_endpoint_detail(endpoint)
        else:
            items = client.get_endpoint(endpoint)
    except MercatorAuthError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except MercatorAPIError as e:
        raise HTTPException(status_code=e.status_code or 502, detail=str(e))

    return JSONResponse(
        content={
            "endpoint": endpoint,
            "total": len(items),
            "with_relations": with_relations,
            "data": items,
        }
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_endpoint(endpoint: str) -> None:
    """Vérifie que l'endpoint est connu. Lève 404 sinon."""
    # On exclut le pseudo-endpoint "export" utilisé dans les routes imbriquées
    if endpoint not in MERCATOR_ENDPOINTS and endpoint != "export":
        raise HTTPException(
            status_code=404,
            detail=f"Endpoint '{endpoint}' inconnu. "
                   f"Consultez GET /api/mercator/endpoints pour la liste complète.",
        )