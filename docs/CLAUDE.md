# CLAUDE.md — Contexte Projet pour Assistant IA

> Ce fichier fournit le contexte complet du projet **Mercator BI Explorer** à un assistant IA (Claude ou autre).
> À lire en début de session pour reprendre le travail sans perdre de contexte.

---

## Projet

**Mercator BI Explorer** — Outil de reporting self-service pour [Mercator CMDB](https://github.com/dbarzin/mercator).

Inspiré de Cognos Impromptu / Isiparc : les utilisateurs interrogent la CMDB sans dépendre des développeurs. Un LLM local (Ollama) permet les requêtes en langage naturel.

---

## État d'Avancement

| Phase | Statut | Description |
|-------|--------|-------------|
| Phase 1 — Analyse & Conception | ✅ Terminée | PRD, Annexe A, architecture |
| Phase 2 — Socle Technique | ✅ Terminée | MercatorClient, FastAPI, 58 tests |
| Phase 3 — Core Reporting | ✅ Terminée | ReportEngine, 5 templates, frontend, export PDF/CSV/MD |
| Phase 4 — Query Builder Ollama | ✅ Terminée | Langage naturel, templates personnels, API filtrée Mercator |
| Phase 5 — Production | 🔲 À planifier | Auth, Excel, historique, partage |

---

## Stack Technique (DÉCISIONS FIGÉES — ne pas modifier)

| Composant | Technologie |
|-----------|-------------|
| Backend | Python 3.11 + FastAPI + Uvicorn |
| Frontend | React 18 + Vite + TailwindCSS |
| HTTP client | httpx[http2] |
| Export PDF | ReportLab |
| LLM local | Ollama (gemma3:4b par défaut) |
| Gestion paquets | uv + pyproject.toml (jamais pip) |
| Containers | Docker Compose (2 containers) |
| Stockage | API Mercator + cache mémoire (pas de BDD additionnelle) |

---

## Architecture Docker

```
Navigateur
  ├── :3000 → mercator-frontend  (nginx:alpine + React)
  │              └── proxy /api/* → mercator-reporting:8000
  └── :8000 → mercator-reporting (python:3.11-slim + FastAPI)
                 ├── → Mercator CMDB  http://host.docker.internal:8080
                 └── → Ollama         http://host.docker.internal:11434
```

---

## Fichiers Clés

```
src/
├── config.py                     # Settings (URLs, credentials, Ollama, timeouts)
├── main.py                       # FastAPI app + 3 routers
├── api/routes/
│   ├── mercator.py               # Debug uniquement (désactivé si DEBUG=false)
│   ├── reports.py                # Templates prédéfinis + export
│   └── query.py                  # Query Builder Ollama + templates perso
├── core/
│   ├── mercator_client.py        # Client API Mercator (cache, retry, filtres avancés)
│   └── dependencies.py           # Injection FastAPI
├── models/report.py              # ReportQuery, JoinDefinition, FilterDefinition...
├── reporting/
│   ├── engine.py                 # Pipeline complet (fetch → filter → enrich → sort → project)
│   └── filters.py                # apply_filters, apply_sort, apply_projection
└── services/
    ├── export.py                 # PDF (ReportLab thème clair), CSV, Markdown
    ├── ollama_service.py         # Interprétation langage naturel → ReportQuery
    └── user_templates.py         # CRUD templates JSON (/app/storage/user_templates.json)

frontend/
├── src/pages/
│   ├── Dashboard.jsx             # Liste templates prédéfinis
│   ├── ReportView.jsx            # Vue rapport + export
│   └── QueryBuilder.jsx          # Requête libre Ollama
└── nginx.conf                    # proxy_read_timeout 2700s (Ollama CPU)
```

---

## Variables d'Environnement (.env)

```env
MERCATOR_BASE_URL=http://host.docker.internal:8080
MERCATOR_LOGIN=admin@admin.com
MERCATOR_PASSWORD=password
CACHE_TTL_SECONDS=300

OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=gemma3:4b
OLLAMA_TIMEOUT=2700

USER_TEMPLATES_PATH=/app/storage/user_templates.json
DEBUG=false
MAX_EXPORT_ROWS=10000
```

---

## Comportement de l'API Mercator — Point Critique

L'API Mercator retourne les **relations comme des listes d'IDs**, pas comme des objets :

```json
// GET /api/applications/5
{ "name": "RH-Solution", "logical_servers": [4] }
```

La résolution se fait dans `engine.py` → `_resolve_ids()` qui charge l'endpoint correspondant et indexe par ID.

**API Advanced Mercator (filtres côté serveur) :**
```
filter[name]=RH-Solution        → LIKE / égalité exacte
filter[rto_gte]=4               → >= 4
filter[id_in]=1,2,3             → IN liste
sort=name / sort=-name          → tri ASC/DESC
include=logical_servers         → eager loading (retourne encore des IDs cependant)
```

Le ReportEngine utilise l'API filtrée en priorité via `_can_use_server_filters()`, avec fallback Python si opérateurs non supportés.

---

## Données Réelles — Instance de Test

| Endpoint | Données notables |
|----------|-----------------|
| `applications` | 7 apps — RH-Solution (id=5, logical_servers=[4]) |
| `application-blocks` | 3 blocs — Applications-RH (id=1) |
| `logical-servers` | 9 serveurs — LOGICAL-SERVER-RH-11 (id=4, IP 11.0.1.50) |
| `activities` | 8 activités — 0 avec RTO défini |

**Requête de validation :**
```bash
curl -X POST http://localhost:8000/api/query/interpret \
  -H "Content-Type: application/json" \
  -d '{"request": "serveurs logiques de l'\''application RH-Solution"}'
# Attendu : 1 ligne — RH-Solution / LOGICAL-SERVER-RH-11 / Windows Server 2025 / 11.0.1.50
```

---

## Bugs Résolus — Ne Pas Réintroduire

| Bug | Cause | Fix |
|-----|-------|-----|
| `TypeError: unhashable type: 'list'` dans sort | `apply_sort` recevait `list[SortDefinition]` (pas un `str`) | Itérer sur `query.sort` dans engine.py |
| `obj.get()` sur une liste | `cleaned` contenait des listes résiduelles | Guard `isinstance(val, (list, dict))` dans `sort_key` + `_strip_raw_relations()` |
| Route `/interpret` Not Found | Décorateur écrasé OU ordre FastAPI incorrect | Déclarer `/interpret` AVANT `/interpret/debug` |
| `Serveur=null` dans les résultats | Mercator retourne `[4]` pas un objet | `_resolve_ids()` dans engine.py |
| `relation_key` non résolu | Ollama génère `logical-servers` (tirets) | Normalisation auto `replace("-", "_")` |
| Gateway Timeout frontend | nginx timeout 60s par défaut | `proxy_read_timeout 2700s` dans nginx.conf |
| Ollama inaccessible Docker | Écoute sur 127.0.0.1 seulement | `OLLAMA_HOST=0.0.0.0` dans systemd ollama |
| PDF 500 couleur | Variable `DARK_3` non définie | Remplacée par `BORDER_COL` |
| PDF nom fichier 500 | Tiret cadratin `—` non latin-1 | Slug ASCII-safe (encode ascii errors=ignore) |

---

## Commandes Fréquentes

```bash
# Copier des fichiers modifiés sans rebuild
docker cp src/reporting/engine.py mercator-reporting:/app/src/reporting/engine.py
docker cp src/reporting/filters.py mercator-reporting:/app/src/reporting/filters.py
docker cp src/core/mercator_client.py mercator-reporting:/app/src/core/mercator_client.py
docker cp src/services/ollama_service.py mercator-reporting:/app/src/services/ollama_service.py
docker cp src/api/routes/query.py mercator-reporting:/app/src/api/routes/query.py

# Recharger nginx sans rebuild
docker cp frontend/nginx.conf mercator-frontend:/etc/nginx/conf.d/default.conf
docker exec mercator-frontend nginx -s reload

# Rebuild complet
docker compose down && docker compose build --no-cache && docker compose up -d

# Tests
uv run pytest -m "phase1 or phase2" -v

# Vérifier les logs
docker logs mercator-reporting --tail 30

# Statut Ollama
curl http://localhost:8000/api/query/ollama/status

# Test query builder
time curl -X POST http://localhost:8000/api/query/interpret \
  -H "Content-Type: application/json" \
  -d '{"request": "serveurs logiques de l'\''application RH-Solution", "model": "gemma3:4b"}'
```

---

## Prochaines Tâches (Phase 5)

- [ ] Authentification JWT ou SSO (respecter les rôles CMDB)
- [ ] Export Excel .xlsx (openpyxl — déjà dans pyproject.toml)
- [ ] Historique des requêtes utilisateur
- [ ] Partage de templates entre utilisateurs
- [ ] Désactiver `/api/mercator/*` si `DEBUG=false`
- [ ] Tests d'acceptance complets (US1 à US4)
- [ ] Documentation utilisateur

---

## Ollama — Configuration Hôte

```bash
# Obligatoire pour accès depuis Docker
sudo systemctl edit ollama
# [Service]
# Environment="OLLAMA_HOST=0.0.0.0"
sudo systemctl daemon-reload && sudo systemctl restart ollama

# Modèles disponibles
ollama list
ollama pull gemma3:4b
```

| Modèle | RAM | Qualité JSON | Vitesse CPU |
|--------|-----|--------------|-------------|
| `gemma3:4b` | 4 GB | Bonne | ~2 min |
| `gemma3:12b` | 10 GB | Très bonne | ~5 min |
| `qwen3.5:9b` | 8 GB | Excellente | ~4 min |

---

## Documents de Référence

| Document | Chemin | Description |
|----------|--------|-------------|
| PRD v4.0 | `PRD_mercator_reporting_v4.md` | Product Requirements Document complet |
| Annexe A | `docs/ANNEXE_A_mapping_mercator.md` | Mapping endpoints Mercator, champs, relations |
| README | `README.md` | Guide installation GitHub |
| SKILLS | `SKILLS.md` | Patterns et conventions techniques |
