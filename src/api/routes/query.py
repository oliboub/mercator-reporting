"""Routes FastAPI — Query Builder."""
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.config import Settings, get_settings
from src.core.dependencies import get_mercator_client
from src.core.mercator_client import MercatorClient
from src.models.report import ReportQuery
from src.reporting.engine import ReportEngine, ReportEngineError
from src.services.ollama_service import OllamaService, OllamaError
from src.services.user_templates import UserTemplateService, UserTemplate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/query", tags=["Query Builder"])


def get_ollama_service(settings: Settings = Depends(get_settings)) -> OllamaService:
    return OllamaService(settings)

def get_template_service(settings: Settings = Depends(get_settings)) -> UserTemplateService:
    return UserTemplateService(settings.user_templates_path)

def get_engine(client: MercatorClient = Depends(get_mercator_client)) -> ReportEngine:
    return ReportEngine(client)


class InterpretRequest(BaseModel):
    request: str = Field(..., min_length=3)
    model: str | None = Field(default=None)
    execute: bool = Field(default=True)

class SaveTemplateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = Field(default="")
    query: ReportQuery
    created_from: str = Field(default="")

class UpdateTemplateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = Field(default="")


@router.get("/ollama/status", summary="Statut du serveur Ollama")
async def ollama_status(service: OllamaService = Depends(get_ollama_service)):
    return await service.check_connection()


@router.post("/interpret", summary="Traduit une demande en ReportQuery via Ollama")
async def interpret_request(
    body: InterpretRequest,
    service: OllamaService = Depends(get_ollama_service),
    engine: ReportEngine = Depends(get_engine),
):
    try:
        query = await service.interpret(body.request, model=body.model)
    except OllamaError as e:
        raise HTTPException(status_code=503, detail=str(e))

    response = {"query": query.model_dump(), "result": None}

    if body.execute:
        try:
            result = engine.execute(query)
            response["result"] = result.model_dump()
        except ReportEngineError as e:
            response["error"] = str(e)

    return response


@router.post("/interpret/debug", summary="Réponse brute Ollama (debug)")
async def interpret_debug(
    body: InterpretRequest,
    service: OllamaService = Depends(get_ollama_service),
):
    try:
        raw = await service.interpret_raw(body.request, model=body.model)
        return {"raw_response": raw}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/templates", summary="Liste des templates utilisateur")
async def list_user_templates(service: UserTemplateService = Depends(get_template_service)):
    templates = service.list_all()
    return {"templates": [t.model_dump() for t in templates], "total": len(templates)}


@router.post("/templates", summary="Sauvegarde un template", status_code=201)
async def save_template(body: SaveTemplateRequest, service: UserTemplateService = Depends(get_template_service)):
    template = UserTemplate(name=body.name, description=body.description, query=body.query, created_from=body.created_from)
    return service.create(template).model_dump()


@router.get("/templates/{template_id}", summary="Récupère un template par ID")
async def get_template(template_id: str, service: UserTemplateService = Depends(get_template_service)):
    t = service.get(template_id)
    if not t:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' introuvable")
    return t.model_dump()


@router.put("/templates/{template_id}", summary="Renomme un template")
async def update_template(template_id: str, body: UpdateTemplateRequest, service: UserTemplateService = Depends(get_template_service)):
    t = service.update(template_id, body.name, body.description)
    if not t:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' introuvable")
    return t.model_dump()


@router.delete("/templates/{template_id}", summary="Supprime un template", status_code=204)
async def delete_template(template_id: str, service: UserTemplateService = Depends(get_template_service)):
    if not service.delete(template_id):
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' introuvable")


@router.post("/templates/{template_id}/execute", summary="Exécute un template utilisateur")
async def execute_user_template(
    template_id: str,
    template_service: UserTemplateService = Depends(get_template_service),
    engine: ReportEngine = Depends(get_engine),
):
    t = template_service.get(template_id)
    if not t:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' introuvable")
    try:
        result = engine.execute(t.query)
    except ReportEngineError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result.model_dump()
