"""Routes FastAPI — ReportEngine.

Expose :
  POST /api/reports/execute        → exécute une ReportQuery, retourne ReportResult
  POST /api/reports/export         → exécute une ReportQuery et retourne un fichier
  GET  /api/reports/templates      → liste des templates de rapports prédéfinis
  POST /api/reports/templates/{id} → exécute un template avec paramètres optionnels
  POST /api/reports/templates/{id}/export/{format} → export direct d'un template
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
import io

from src.core.mercator_client import MercatorClient
from src.core.dependencies import get_mercator_client
from src.models.report import (
    ReportQuery, FilterDefinition, FilterOperator,
    ColumnDefinition, SortDefinition, SortDirection, JoinDefinition,
    ExportFormat,
)
from src.reporting.engine import ReportEngine, ReportEngineError
from src.services.export import ExportService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/reports", tags=["Reporting"])


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def get_engine(client: MercatorClient = Depends(get_mercator_client)) -> ReportEngine:
    return ReportEngine(client)


# ---------------------------------------------------------------------------
# Exécution libre d'une ReportQuery
# ---------------------------------------------------------------------------

@router.post("/execute", summary="Exécute une ReportQuery")
async def execute_report(
    query: ReportQuery,
    engine: ReportEngine = Depends(get_engine),
):
    """Exécute une requête de rapport dynamique.

    Accepte une ReportQuery complète (endpoint, filtres, jointures, tri, colonnes)
    et retourne un ReportResult avec les données et les métadonnées.

    Exemple — Rapport BIA :
    ```json
    {
      "endpoint": "activities",
      "columns": [
        {"field": "name", "label": "Activité"},
        {"field": "recovery_time_objective", "label": "RTO (h)"},
        {"field": "recovery_point_objective", "label": "RPO (h)"}
      ],
      "filters": [
        {"field": "recovery_time_objective", "operator": "is_not_null"}
      ],
      "sort": [{"field": "recovery_time_objective", "direction": "asc"}]
    }
    ```
    """
    try:
        result = engine.execute(query)
    except ReportEngineError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Erreur inattendue dans ReportEngine")
        raise HTTPException(status_code=500, detail=f"Erreur interne : {e}")

    return result.model_dump()


# ---------------------------------------------------------------------------
# Export fichier
# ---------------------------------------------------------------------------

@router.post("/export/{fmt}", summary="Exécute une ReportQuery et retourne un fichier")
async def export_report(
    fmt: ExportFormat,
    query: ReportQuery,
    engine: ReportEngine = Depends(get_engine),
):
    """Exécute une ReportQuery et retourne directement le fichier exporté.

    Formats disponibles : pdf, csv, md

    Exemple :
        POST /api/reports/export/pdf
        POST /api/reports/export/csv
        POST /api/reports/export/md
    """
    try:
        result = engine.execute(query)
    except ReportEngineError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _stream_export(result, fmt)


@router.post("/templates/{template_id}/export/{fmt}", summary="Export direct d'un template")
async def export_template(
    template_id: str,
    fmt: ExportFormat,
    engine: ReportEngine = Depends(get_engine),
):
    """Exécute un template et retourne directement le fichier exporté.

    Exemple :
        POST /api/reports/templates/ciat/export/pdf
        POST /api/reports/templates/inventaire-applicatif/export/csv
    """
    if template_id not in REPORT_TEMPLATES:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' inconnu.")

    query = _build_template_query(template_id)
    try:
        result = engine.execute(query)
    except ReportEngineError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _stream_export(result, fmt)


def _stream_export(result, fmt: ExportFormat) -> StreamingResponse:
    """Génère la StreamingResponse selon le format demandé."""
    raw_title = result.metadata.title or result.metadata.endpoint
    # Remplacer les caractères non-ASCII (tirets cadratins, accents, etc.)
    slug = (
        raw_title
        .replace("—", "-").replace("–", "-")
        .encode("ascii", errors="ignore").decode("ascii")
        .replace(" ", "-").lower()
        .strip("-")
    )
    date_str = result.metadata.generated_at[:10] if result.metadata.generated_at else "export"
    filename_base = f"mercator-{slug}-{date_str}"

    if fmt == ExportFormat.PDF:
        content = ExportService.to_pdf(result)
        return StreamingResponse(
            io.BytesIO(content),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.pdf"'},
        )

    if fmt == ExportFormat.CSV:
        content = ExportService.to_csv(result)
        return StreamingResponse(
            io.StringIO(content),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.csv"'},
        )

    if fmt == ExportFormat.EXCEL:
        raise HTTPException(status_code=400, detail="Format xlsx non encore supporté. Utilisez csv ou pdf.")

    # Markdown
    content = ExportService.to_markdown(result)
    return StreamingResponse(
        io.StringIO(content),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename_base}.md"'},
    )

# ---------------------------------------------------------------------------
# Templates prédéfinis
# ---------------------------------------------------------------------------

REPORT_TEMPLATES: dict[str, dict] = {
    "bia": {
        "id": "bia",
        "title": "BIA — Analyse d'Impact Métier",
        "description": "Activités avec RTO/RPO/MTD renseignés, triées par RTO croissant",
        "endpoint": "activities",
    },
    "ciat": {
        "id": "ciat",
        "title": "CIAT — Classification Sécurité des Applications",
        "description": "Applications avec leurs niveaux de sécurité C/I/A/T",
        "endpoint": "applications",
    },
    "rgpd": {
        "id": "rgpd",
        "title": "RGPD — Registre des Traitements",
        "description": "Traitements de données avec base légale et durée de rétention",
        "endpoint": "data-processings",
    },
    "inventaire-applicatif": {
        "id": "inventaire-applicatif",
        "title": "Inventaire Applicatif",
        "description": "Applications avec leurs serveurs logiques associés",
        "endpoint": "applications",
    },
    "inventaire-serveurs": {
        "id": "inventaire-serveurs",
        "title": "Inventaire Serveurs",
        "description": "Serveurs logiques avec système d'exploitation et environnement",
        "endpoint": "logical-servers",
    },
}


@router.get("/templates", summary="Liste des templates de rapports prédéfinis")
async def list_templates():
    """Retourne la liste des templates de rapports disponibles."""
    return {
        "templates": list(REPORT_TEMPLATES.values()),
        "total": len(REPORT_TEMPLATES),
    }


@router.post("/templates/{template_id}", summary="Exécute un template de rapport")
async def execute_template(
    template_id: str,
    engine: ReportEngine = Depends(get_engine),
):
    """Exécute un template de rapport prédéfini.

    Les templates encapsulent des ReportQuery préconfigurées pour les
    cas d'usage métier courants (BIA, CIAT, RGPD, inventaires).
    """
    if template_id not in REPORT_TEMPLATES:
        raise HTTPException(
            status_code=404,
            detail=f"Template '{template_id}' inconnu. "
                   f"Templates disponibles : {list(REPORT_TEMPLATES.keys())}",
        )

    query = _build_template_query(template_id)

    try:
        result = engine.execute(query)
    except ReportEngineError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Erreur lors de l'exécution du template %s", template_id)
        raise HTTPException(status_code=500, detail=f"Erreur interne : {e}")

    return result.model_dump()


# ---------------------------------------------------------------------------
# Requêtes préconfigurées par template
# ---------------------------------------------------------------------------

def _build_template_query(template_id: str) -> ReportQuery:
    """Construit la ReportQuery associée à un template."""

    if template_id == "bia":
        return ReportQuery(
            endpoint="activities",
            title="BIA — Analyse d'Impact Métier",
            columns=[
                ColumnDefinition(field="name", label="Activité"),
                ColumnDefinition(field="recovery_time_objective", label="RTO (h)"),
                ColumnDefinition(field="maximum_tolerable_downtime", label="MTD (h)"),
                ColumnDefinition(field="recovery_point_objective", label="RPO (h)"),
                ColumnDefinition(field="maximum_tolerable_data_loss", label="MTDL (h)"),
                ColumnDefinition(field="drp", label="DRP"),
                ColumnDefinition(field="drp_link", label="Lien DRP"),
            ],
            filters=[
                FilterDefinition(
                    field="recovery_time_objective",
                    operator=FilterOperator.IS_NOT_NULL,
                )
            ],
            sort=[SortDefinition(field="recovery_time_objective", direction=SortDirection.ASC)],
            limit=1000,
        )

    if template_id == "ciat":
        return ReportQuery(
            endpoint="applications",
            title="CIAT — Classification Sécurité",
            columns=[
                ColumnDefinition(field="name", label="Application"),
                ColumnDefinition(field="type", label="Type"),
                ColumnDefinition(field="responsible", label="Responsable"),
                ColumnDefinition(field="security_need_c", label="Confidentialité"),
                ColumnDefinition(field="security_need_i", label="Intégrité"),
                ColumnDefinition(field="security_need_a", label="Disponibilité"),
                ColumnDefinition(field="security_need_t", label="Traçabilité"),
            ],
            sort=[
                SortDefinition(field="security_need_c", direction=SortDirection.DESC),
                SortDefinition(field="name", direction=SortDirection.ASC),
            ],
            limit=1000,
        )

    if template_id == "rgpd":
        return ReportQuery(
            endpoint="data-processings",
            title="RGPD — Registre des Traitements",
            columns=[
                ColumnDefinition(field="name", label="Traitement"),
                ColumnDefinition(field="responsible", label="Responsable"),
                ColumnDefinition(field="purpose", label="Finalité"),
                ColumnDefinition(field="legal_basis", label="Base légale"),
                ColumnDefinition(field="retention", label="Durée de conservation"),
                ColumnDefinition(field="lawfulness_legal_obligation", label="Obligation légale"),
                ColumnDefinition(field="lawfulness_consent", label="Consentement"),
            ],
            sort=[SortDefinition(field="name", direction=SortDirection.ASC)],
            limit=1000,
        )

    if template_id == "inventaire-applicatif":
        return ReportQuery(
            endpoint="applications",
            title="Inventaire Applicatif",
            columns=[
                ColumnDefinition(field="block_name", label="Bloc Applicatif"),
                ColumnDefinition(field="name", label="Application"),
                ColumnDefinition(field="type", label="Type"),
                ColumnDefinition(field="technology", label="Technologie"),
                ColumnDefinition(field="responsible", label="Responsable"),
                ColumnDefinition(field="rto", label="RTO (h)"),
                ColumnDefinition(field="rpo", label="RPO (h)"),
                ColumnDefinition(field="external", label="Externe"),
            ],
            joins=[
                JoinDefinition(
                    endpoint="application-blocks",
                    foreign_key="application_block_id",
                    fields=["name"],
                    prefix="block_",
                    default={"name": "Non classé"},
                )
            ],
            sort=[
                SortDefinition(field="block_name", direction=SortDirection.ASC),
                SortDefinition(field="name", direction=SortDirection.ASC),
            ],
            include_relations=False,
            limit=1000,
        )

    if template_id == "inventaire-serveurs":
        return ReportQuery(
            endpoint="logical-servers",
            title="Inventaire Serveurs Logiques",
            columns=[
                ColumnDefinition(field="name", label="Serveur"),
                ColumnDefinition(field="operating_system", label="OS"),
                ColumnDefinition(field="environment", label="Environnement"),
                ColumnDefinition(field="type", label="Type"),
                ColumnDefinition(field="address_ip", label="IP"),
                ColumnDefinition(field="cpu", label="CPU"),
                ColumnDefinition(field="memory", label="Mémoire"),
                ColumnDefinition(field="active", label="Actif"),
            ],
            filters=[
                FilterDefinition(field="active", operator=FilterOperator.EQ, value=True)
            ],
            sort=[SortDefinition(field="name", direction=SortDirection.ASC)],
            limit=1000,
        )

    # Fallback (ne devrait pas arriver — validé par la route)
    raise ReportEngineError(f"Template '{template_id}' non implémenté")