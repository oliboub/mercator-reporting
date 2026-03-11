"""UserTemplateService — Gestion des templates utilisateur.

Les templates sont sauvegardés dans un fichier JSON local
(/app/storage/user_templates.json par défaut).

Un template = une ReportQuery + un nom + une description optionnelle + un ID.
"""
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from src.models.report import ReportQuery

logger = logging.getLogger(__name__)


class UserTemplate(BaseModel):
    """Un template utilisateur sauvegardé."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str
    description: str = ""
    query: ReportQuery
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    created_from: str = ""  # requête originale en langage naturel


class UserTemplateService:
    """Service CRUD pour les templates utilisateur."""

    def __init__(self, storage_path: str):
        self._path = storage_path
        self._ensure_storage()

    def _ensure_storage(self):
        """Crée le dossier et le fichier de stockage si nécessaire."""
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        if not os.path.exists(self._path):
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump([], f)

    def _load(self) -> list[dict]:
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _save(self, templates: list[dict]):
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(templates, f, ensure_ascii=False, indent=2)

    def list_all(self) -> list[UserTemplate]:
        """Retourne tous les templates triés par date de création décroissante."""
        raw = self._load()
        templates = []
        for item in raw:
            try:
                templates.append(UserTemplate.model_validate(item))
            except Exception as e:
                logger.warning("Template invalide ignoré : %s — %s", item.get("id"), e)
        return sorted(templates, key=lambda t: t.created_at, reverse=True)

    def get(self, template_id: str) -> UserTemplate | None:
        """Retourne un template par son ID."""
        for item in self._load():
            if item.get("id") == template_id:
                try:
                    return UserTemplate.model_validate(item)
                except Exception:
                    return None
        return None

    def create(self, template: UserTemplate) -> UserTemplate:
        """Sauvegarde un nouveau template."""
        raw = self._load()
        raw.append(template.model_dump())
        self._save(raw)
        logger.info("Template créé : %s (%s)", template.id, template.name)
        return template

    def delete(self, template_id: str) -> bool:
        """Supprime un template. Retourne True si trouvé et supprimé."""
        raw = self._load()
        new_raw = [t for t in raw if t.get("id") != template_id]
        if len(new_raw) == len(raw):
            return False
        self._save(new_raw)
        logger.info("Template supprimé : %s", template_id)
        return True

    def update(self, template_id: str, name: str, description: str) -> UserTemplate | None:
        """Met à jour le nom et la description d'un template."""
        raw = self._load()
        for item in raw:
            if item.get("id") == template_id:
                item["name"] = name
                item["description"] = description
                self._save(raw)
                return UserTemplate.model_validate(item)
        return None