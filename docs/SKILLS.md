# SKILLS.md — Compétences Techniques du Projet

> Document de référence pour l'onboarding des développeurs sur **Mercator BI Explorer**.
> Décrit les patterns, conventions et décisions techniques du projet.

---

## 1. Stack & Environnement

### Gestion des paquets Python
```bash
# Toujours utiliser uv, jamais pip directement
uv sync                          # installer les dépendances
uv run pytest                    # lancer les tests
uv run uvicorn src.main:app      # lancer le backend
```

### Docker Compose — workflow quotidien
```bash
# Copier un fichier modifié sans rebuild
docker cp src/reporting/engine.py mercator-reporting:/app/src/reporting/engine.py

# Rebuild d'un seul container
docker compose build --no-cache mercator-frontend
docker compose up -d mercator-frontend

# Rebuild complet
docker compose down && docker compose build --no-cache && docker compose up -d

# Logs en temps réel
docker logs mercator-reporting -f --tail 50
```

### Nginx — rechargement à chaud (sans rebuild)
```bash
docker cp frontend/nginx.conf mercator-frontend:/etc/nginx/conf.d/default.conf
docker exec mercator-frontend nginx -s reload
```

---

## 2. Architecture Backend

### Pattern d'injection de dépendances (FastAPI)
```python
# dependencies.py — singleton MercatorClient
from functools import lru_cache

@lru_cache
def get_mercator_client() -> MercatorClient:
    return MercatorClient(settings)

# Dans les routes :
def my_route(client: MercatorClient = Depends(get_mercator_client)):
    ...
```

### Ordre des routes FastAPI — règle critique
Les routes avec paramètres variables DOIVENT être déclarées après les routes fixes :
```python
# ✅ Correct
@router.post("/interpret")       # route fixe EN PREMIER
@router.post("/interpret/debug") # route fixe EN SECOND
@router.get("/{id}")             # paramètre variable EN DERNIER

# ❌ Incorrect — /{id} capturerait "debug" avant la route fixe
@router.get("/{id}")
@router.get("/debug")
```

### Modèles Pydantic v2
```python
from pydantic import BaseModel, Field
from enum import Enum

class FilterOperator(str, Enum):
    EQ = "eq"
    NEQ = "neq"
    CONTAINS = "contains"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    IN = "in"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"
    NOT_CONTAINS = "not_contains"   # non supporté API serveur → fallback Python
    STARTS_WITH = "starts_with"     # non supporté API serveur → fallback Python
```

---

## 3. MercatorClient — Comportement de l'API

### Deux niveaux d'appel obligatoires
```
GET /api/applications          → liste d'IDs seulement
GET /api/applications/{id}     → objet complet + relations (encore des IDs)
GET /api/logical-servers/{id}  → résolution des IDs de relations
```

### Relations retournées comme IDs, pas comme objets
```json
// GET /api/applications/5
{
  "name": "RH-Solution",
  "logical_servers": [4],    ← IDs, pas des objets !
  "databases": [2]
}
```

La résolution est faite par `_resolve_ids()` dans le ReportEngine.

### API Advanced Mercator — Filtres côté serveur
```python
# Paramètres de filtre
params = {
    "filter[name]": "RH-Solution",          # EQ / LIKE auto (name, description)
    "filter[type_not]": "opensource",        # NEQ
    "filter[rto_gte]": "4",                  # GTE
    "filter[id_in]": "1,2,3",               # IN
    "filter[description_null]": "true",      # IS_NULL
    "sort": "name",                          # ASC
    "sort": "-created_at",                   # DESC
    "include": "logical_servers,databases",  # eager loading
}
```

### Cache mémoire
```python
# Le cache est appliqué sur get_endpoint() et get_endpoint_detail()
# PAS sur get_endpoint_filtered() (résultats variables selon les filtres)
@lru_cache(maxsize=128)
def get_endpoint(self, endpoint: str) -> list[dict]: ...
```

---

## 4. ReportEngine — Pipeline

### Sélection du mode fetch
```python
def _can_use_server_filters(query: ReportQuery) -> bool:
    """Mode API filtrée si : au moins 1 filtre/tri ET aucun opérateur non supporté."""
    UNSUPPORTED = {FilterOperator.NOT_CONTAINS, FilterOperator.STARTS_WITH}
    if not query.filters and not query.sort:
        return False
    return not any(f.operator in UNSUPPORTED for f in query.filters)
```

### Résolution des IDs Many-to-Many
```python
# RELATION_KEY_TO_ENDPOINT — mapping clé de relation → endpoint API
RELATION_KEY_TO_ENDPOINT = {
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
```

### Expand Many-to-Many
Une application avec N serveurs → N lignes dans le résultat :
```python
# join avec relation_key="logical_servers" sur applications
# [{"name": "RH-Solution", "logical_servers": [4]}]
# → [{"Application": "RH-Solution", "Serveur": "LOGICAL-SERVER-RH-11", ...}]
```

### Robustesse du tri
```python
def sort_key(obj):
    val = obj.get(sort_field)
    if val is None or isinstance(val, (list, dict)):
        return (1, 0)  # traiter comme None → en fin de liste
    try:
        return (0, float(val))
    except (TypeError, ValueError):
        return (0, str(val).lower())
```

### Appel correct de apply_sort
```python
# ✅ Correct — itérer sur les SortDefinition
for sort_def in reversed(query.sort):
    ascending = sort_def.direction == SortDirection.ASC
    sorted_items = apply_sort(sorted_items, sort_def.field, ascending=ascending)

# ❌ Incorrect — passe une liste au lieu d'un str
sorted_items = apply_sort(cleaned, query.sort)
```

---

## 5. OllamaService — Intégration LLM

### Normalisation automatique des relation_key
Ollama peut générer des tirets (`logical-servers`) alors que le ReportEngine attend des underscores (`logical_servers`) :
```python
def _normalize_relation_key(key: str) -> str:
    return key.replace("-", "_")
```

### Timeout CPU sans GPU
```
OLLAMA_TIMEOUT=2700   # 45 minutes — gemma3:4b sur CPU ~2 min, prévoir large
```

### Structure du prompt système
Le prompt inclut :
- Schéma JSON attendu avec exemples concrets
- Règles critiques : relations portées par l'application (pas le serveur)
- Filtrer par `name` pas par `id`
- Exemples : "serveurs d'une app", "apps critiques", "serveurs Linux"

### Fallback si JSON invalide
```python
try:
    query = ReportQuery.model_validate(json.loads(content))
except Exception:
    return InterpretResult(query=None, raw="[Non interprété]", error=str(e))
```

---

## 6. ExportService — PDF

### Thème clair impression-friendly
```python
# Palette PDF (thème clair)
BG_HEADER = colors.HexColor("#0f172a")   # bandeau titre noir
BG_ROW_ODD = colors.white
BG_ROW_EVEN = colors.HexColor("#f8fafc") # gris très clair
BORDER_COL = colors.HexColor("#e2e8f0")
TEXT_DARK = colors.HexColor("#0f172a")
TEXT_LIGHT = colors.white
```

### Barres CIAT dans le PDF
```python
CIAT_BARS   = {1: "█░░░", 2: "██░░", 3: "███░", 4: "████"}
CIAT_LABELS = {1: "Faible", 2: "Moyen", 3: "Élevé", 4: "Critique"}
CIAT_COLORS = {1: "#059669", 2: "#d97706", 3: "#dc2626", 4: "#7c3aed"}
```

### Nom de fichier ASCII-safe
```python
# Évite les erreurs Content-Disposition avec les tirets cadratins et accents
import unicodedata, re
slug = unicodedata.normalize("NFKD", title).encode("ascii", errors="ignore").decode()
slug = re.sub(r"[^\w\s-]", "", slug).strip().replace(" ", "-").lower()
```

---

## 7. Frontend React

### Structure des appels API
```javascript
// api/reports.js — toujours préfixe /api/
const BASE = "/api";

export async function getTemplates() {
    const res = await fetch(`${BASE}/reports/templates`);
    return res.json();
}

export async function interpretQuery(request, model) {
    const res = await fetch(`${BASE}/query/interpret`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ request, model, execute: true })
    });
    return res.json();
}
```

### Timeouts nginx — critique pour Ollama
```nginx
location /api/ {
    proxy_pass http://mercator-reporting:8000;
    proxy_read_timeout    2700s;   # Doit correspondre à OLLAMA_TIMEOUT
    proxy_connect_timeout 10s;
    proxy_send_timeout    2700s;
    proxy_buffering off;
}
```

---

## 8. Tests

### Markers pytest
```ini
# pytest.ini
[pytest]
markers =
    phase1: Tests Phase 1 (API routes + MercatorClient)
    phase2: Tests Phase 2 (modèles, filtres, engine)
    integration: Tests d'intégration (réseau requis)
```

### Lancer les tests
```bash
uv run pytest -m phase1 -v     # 58 tests
uv run pytest -m phase2 -v     # 121 tests
uv run pytest -v               # tous
uv run pytest --cov=src --cov-report=term-missing
```

### Pattern de mock MercatorClient
```python
# conftest.py
@pytest.fixture
def mock_client(monkeypatch):
    client = MagicMock(spec=MercatorClient)
    client.get_endpoint.return_value = load_fixture("applications.json")
    monkeypatch.setattr("src.core.dependencies.get_mercator_client", lambda: client)
    return client
```

---

## 9. Données Réelles — Instance de Test

| Endpoint | Volume | Notes |
|----------|--------|-------|
| `applications` | 7 | SAP P11, RH-Solution (id=5), docker, python, SCADA |
| `application-blocks` | 3 | Applications-RH (id=1), ERP Logistique (id=2), Industrielles (id=3) |
| `logical-servers` | 9 | LOGICAL-SERVER-RH-11 (id=4) lié à RH-Solution |
| `activities` | 8 | 0 avec RTO défini → BIA retourne 0 résultats |
| `data-processings` | 15 | Traitements RGPD |

**Requête de test validée :**
```bash
time curl -X POST http://localhost:8000/api/query/interpret \
  -H "Content-Type: application/json" \
  -d '{"request": "serveurs logiques de l'\''application RH-Solution"}'
# Résultat : RH-Solution → LOGICAL-SERVER-RH-11 (Windows Server 2025, 11.0.1.50)
# Durée : ~2 min (gemma3:4b, CPU)
```

---

## 10. Checklist Ajout d'un Nouveau Template

1. Définir la `ReportQuery` (endpoint, filters, joins, columns, sort)
2. Ajouter dans `reports.py` → `PREDEFINED_TEMPLATES` dict
3. Vérifier les jointures dans `RELATION_KEY_TO_ENDPOINT` (engine.py)
4. Tester avec curl : `POST /api/reports/templates/{id}`
5. Vérifier l'export PDF : `POST /api/reports/templates/{id}/export/pdf`
6. Ajouter une `TemplateCard` dans `Dashboard.jsx`

---

## 11. Checklist Débogage

| Symptôme | Cause probable | Fix |
|----------|---------------|-----|
| `TypeError: unhashable type: 'list'` dans sort | `apply_sort` reçoit `list[SortDefinition]` | Itérer sur `query.sort` |
| `obj.get()` sur une liste | `cleaned` contient des listes résiduelles | `_strip_raw_relations()` ou guard `isinstance` |
| Route 404 `/interpret` | Conflit avec `/interpret/debug` | Déclarer `/interpret` EN PREMIER |
| `AttributeError` sur OllamaService | Mauvais fichier copié dans le container | `docker cp` + vérifier avec `docker exec cat` |
| `relation_key` non résolu | Ollama génère `logical-servers` (tirets) | Normalisation auto `replace("-", "_")` |
| Gateway Timeout nginx | Timeout 60s par défaut | `proxy_read_timeout 2700s` dans nginx.conf |
| Ollama inaccessible depuis Docker | Écoute sur 127.0.0.1 | `OLLAMA_HOST=0.0.0.0` dans systemd |
| PDF 500 erreur couleur | Variable couleur non définie | Vérifier la palette dans export.py |
| PDF nom fichier 500 | Tiret cadratin non latin-1 | Slug ASCII-safe |
