"""Point d'entrée FastAPI — Mercator Reporting."""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import mercator as mercator_router
from src.api.routes import reports as reports_router   # ← ajouter cette ligne

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)

app = FastAPI(
    title="Mercator Reporting API",
    description=(
        "Outil de reporting intelligent pour Mercator CMDB. "
        "Recréation moderne de l'approche Cognos Impromptu / Isiparc."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(mercator_router.router)
app.include_router(reports_router.router)   

@app.get("/health", tags=["System"])
async def health_check():
    """Health check de l'application (hors Mercator)."""
    return {"status": "ok", "service": "mercator-reporting", "version": "0.1.0"}


@app.get("/", tags=["System"])
async def root():
    """Root — liens utiles."""
    return {
        "service": "Mercator Reporting API",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
        "mercator_health": "/api/mercator/health",
        "endpoints": "/api/mercator/endpoints",
    }