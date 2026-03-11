# Mercator BI Explorer

> Outil de reporting self-service pour [Mercator CMDB](https://github.com/dbarzin/mercator) — inspiré de Cognos Impromptu.

Interrogez votre CMDB en langage naturel, visualisez les résultats et exportez en PDF, CSV ou Markdown.

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green?logo=fastapi)
![React](https://img.shields.io/badge/React-18-61dafb?logo=react)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ed?logo=docker)
![Ollama](https://img.shields.io/badge/Ollama-local_LLM-black)

---

## Sommaire

- [Fonctionnalités](#fonctionnalités)
- [Architecture](#architecture)
- [Prérequis](#prérequis)
- [Installation](#installation)
- [Configuration](#configuration)
- [Utilisation](#utilisation)
- [API Reference](#api-reference)
- [Développement](#développement)

---

## Fonctionnalités

### Templates prédéfinis
| Template | Description |
|----------|-------------|
| **CIAT** | Classification Sécurité (Confidentialité / Intégrité / Disponibilité / Traçabilité) |
| **BIA** | Analyse d'Impact Métier — activités avec RTO/RPO |
| **RGPD** | Registre des traitements de données personnelles |
| **Inventaire applicatif** | Applications avec leur bloc applicatif |
| **Inventaire serveurs** | Serveurs logiques actifs |

### Query Builder (Ollama)
- Saisie en **langage naturel** → traduction automatique en requête Mercator via un LLM local Ollama
- Prévisualisation live des résultats
- JSON de la requête généré visible et **éditable manuellement**
- Sauvegarde des requêtes comme **templates personnels** réutilisables sans Ollama
- Sélection du modèle Ollama depuis l'interface

### Export
- **PDF** — mise en page professionnelle, thème clair impression-friendly, barres CIAT colorées
- **CSV** — UTF-8 BOM, séparateur `;`, compatible Excel
- **Markdown** — tableaux GitHub/Obsidian

### Moteur de rapports
- Filtres côté serveur via l'**API Advanced Mercator** (filter[field_op]=value)
- Fallback filtrage Python pour les cas complexes
- Jointures Many-to-Many avec résolution d'IDs (`logical_servers`, `databases`, etc.)
- Jointures par clé étrangère (`application_block_id` → `application-blocks`)
- Expand automatique : 1 application avec N serveurs → N lignes

---

## Architecture

```
Navigateur
  ├── :3000 → mercator-frontend  (nginx + React)
  │              └── proxy /api/* → mercator-reporting:8000
  └── :8000 → mercator-reporting (FastAPI + Python)
                 ├── → Mercator CMDB  :8080
                 └── → Ollama         :11434
```

### Containers Docker

| Container | Image | Port | Rôle |
|-----------|-------|------|------|
| `mercator-reporting` | Python 3.11 + FastAPI | 8000 | Backend API, moteur de rapports, intégration Ollama |
| `mercator-frontend` | nginx:alpine + React 18 | 3000 | Interface web, proxy API |

### Stack technique

**Backend**
- Python 3.11 + FastAPI + Uvicorn
- Pydantic v2 pour la validation des modèles
- httpx pour les appels API Mercator et Ollama
- ReportLab pour la génération PDF
- Gestion de packages : `uv`

**Frontend**
- React 18 + Vite
- TailwindCSS (dark theme)
- React Router v6

---

## Prérequis

- Docker + Docker Compose
- [Mercator CMDB](https://github.com/dbarzin/mercator) en cours d'exécution (port 8080 par défaut)
- [Ollama](https://ollama.ai) installé et démarré sur la machine hôte (pour le Query Builder)

### Ollama — configuration requise

Ollama doit écouter sur toutes les interfaces (pas uniquement `localhost`) pour être accessible depuis Docker :

```bash
# Modifier le service systemd
sudo systemctl edit ollama

# Ajouter :
[Service]
Environment="OLLAMA_HOST=0.0.0.0"

sudo systemctl daemon-reload
sudo systemctl restart ollama
```

**Modèles recommandés** (selon vos ressources) :

| Modèle | RAM requise | Qualité JSON | Vitesse CPU |
|--------|-------------|--------------|-------------|
| `gemma3:4b` | 4 GB | Bonne | ~2 min |
| `gemma3:12b` | 10 GB | Très bonne | ~5 min |
| `qwen3.5:9b` | 8 GB | Excellente | ~4 min |
| `lfm2.5-thinking` | 1 GB | Correcte | ~1 min |

```bash
ollama pull gemma3:4b
```

---

## Installation

```bash
# Cloner le dépôt
git clone https://github.com/votre-org/mercator-reporting.git
cd mercator-reporting

# Copier et configurer les variables d'environnement
cp .env.example .env
# Éditer .env selon votre environnement

# Construire et démarrer les containers
docker compose up -d --build

# Vérifier que les services sont actifs
docker compose ps
```

### Vérification

```bash
# Backend — santé de l'API
curl http://localhost:8000/health

# Connexion Mercator
curl http://localhost:8000/api/mercator/status

# Connexion Ollama
curl http://localhost:8000/api/query/ollama/status

# Frontend
open http://localhost:3000
```

---

## Configuration

Toutes les variables sont dans `.env` :

```env
# Mercator CMDB
MERCATOR_BASE_URL=http://host.docker.internal:8080
MERCATOR_LOGIN=admin@admin.com
MERCATOR_PASSWORD=password

# Cache (secondes)
CACHE_TTL_SECONDS=300

# Ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=gemma3:4b
OLLAMA_TIMEOUT=2700          # 45 min — adapter selon votre matériel

# Application
DEBUG=false
MAX_EXPORT_ROWS=10000

# Stockage templates utilisateur
USER_TEMPLATES_PATH=/app/storage/user_templates.json
```

> **Note Linux** : `host.docker.internal` nécessite l'entrée `extra_hosts: ["host.docker.internal:host-gateway"]` dans `docker-compose.yml` (déjà configuré).

---

## Utilisation

### Interface web (port 3000)

#### Dashboard
Accédez à `http://localhost:3000` pour voir les 5 templates prédéfinis.
Cliquez sur un template pour l'exécuter et visualiser les résultats.

#### Exporter un rapport
Depuis la vue d'un rapport, utilisez les boutons :
- 📄 **PDF** — rapport mis en page, prêt à imprimer
- 📊 **CSV** — données brutes pour Excel
- 📝 **Markdown** — documentation technique

#### Query Builder (Requête libre)
1. Cliquez sur **Requête libre** dans la barre de navigation
2. Vérifiez que le badge **Ollama connecté** est vert
3. Sélectionnez le modèle souhaité
4. Décrivez votre besoin en français :
   - *"applications critiques avec leur bloc applicatif"*
   - *"serveurs logiques de l'application RH-Solution"*
   - *"traitements RGPD avec obligation légale"*
5. Cliquez sur **✨ Interpréter** ou `Ctrl+Entrée`
6. Modifiez le JSON généré si nécessaire, puis **▶ Ré-exécuter**
7. Cliquez sur **💾 Sauvegarder** pour réutiliser sans Ollama

### API REST (port 8000)

Documentation interactive Swagger : `http://localhost:8000/docs`

---

## API Reference

### Templates prédéfinis

```bash
# Lister les templates
GET /api/reports/templates

# Exécuter un template
POST /api/reports/templates/{id}

# Exporter un template
POST /api/reports/templates/{id}/export/{fmt}
# fmt : pdf | csv | md
```

### Query Builder

```bash
# Statut Ollama
GET /api/query/ollama/status

# Interpréter une demande en langage naturel
POST /api/query/interpret
{
  "request": "applications critiques avec leur bloc",
  "model": "gemma3:4b",   // optionnel
  "execute": true          // exécuter immédiatement
}

# Debug — voir la réponse brute Ollama
POST /api/query/interpret/debug

# Templates utilisateur
GET    /api/query/templates
POST   /api/query/templates
GET    /api/query/templates/{id}
PUT    /api/query/templates/{id}
DELETE /api/query/templates/{id}
POST   /api/query/templates/{id}/execute
```

### Requête libre

```bash
# Exécuter une ReportQuery
POST /api/reports/execute
{
  "endpoint": "applications",
  "filters": [{"field": "security_need_c", "operator": "gte", "value": 3}],
  "joins": [{"endpoint": "application-blocks", "foreign_key": "application_block_id",
             "fields": ["name"], "prefix": "block_"}],
  "sort": [{"field": "security_need_c", "direction": "desc"}],
  "limit": 100
}

# Exporter une ReportQuery
POST /api/reports/export/{fmt}
```

---

## Développement

### Structure du projet

```
mercator-reporting/
├── src/
│   ├── api/routes/
│   │   ├── mercator.py      # Proxy endpoints Mercator
│   │   ├── reports.py       # Templates + export
│   │   └── query.py         # Query Builder + Ollama
│   ├── core/
│   │   ├── mercator_client.py   # Client API Mercator (cache, filtres avancés)
│   │   └── dependencies.py
│   ├── models/
│   │   └── report.py        # ReportQuery, JoinDefinition, FilterDefinition...
│   ├── reporting/
│   │   ├── engine.py        # Pipeline Fetch→Filter→Enrich→Sort→Project
│   │   └── filters.py       # Filtres, tri, projection
│   ├── services/
│   │   ├── export.py        # PDF (ReportLab), CSV, Markdown
│   │   ├── ollama_service.py    # Intégration Ollama
│   │   └── user_templates.py   # CRUD templates JSON
│   ├── config.py
│   └── main.py
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx      # Liste des templates
│   │   │   ├── ReportView.jsx     # Vue rapport + export
│   │   │   └── QueryBuilder.jsx   # Requête libre Ollama
│   │   └── components/
│   │       ├── ReportTable.jsx    # Tableau avec rendu CIAT
│   │       ├── Navbar.jsx
│   │       └── TemplateCard.jsx
│   ├── nginx.conf           # Proxy /api/* → backend
│   └── Dockerfile.frontend
├── tests/
│   ├── test_phase1_api.py
│   ├── test_phase1_mercator_client.py
│   ├── test_phase2_models.py
│   ├── test_phase2_filters.py
│   └── test_phase2_engine.py
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── .env.example
```

### Lancer les tests

```bash
uv sync
uv run pytest -m phase1 -v        # 58 tests — API et client Mercator
uv run pytest -m phase2 -v        # 121 tests — modèles, filtres, moteur
uv run pytest -v                   # Tous les tests
```

### Rebuild

```bash
# Backend uniquement (hot-reload actif en dev)
docker cp src/ mercator-reporting:/app/src/

# Frontend (nécessite rebuild)
docker compose build --no-cache mercator-frontend
docker compose up -d mercator-frontend

# Rebuild complet
docker compose down
docker compose build --no-cache
docker compose up -d
```

---

## Roadmap

- [ ] Filtres API Mercator côté serveur (intégration complète)
- [ ] Export Excel (.xlsx)
- [ ] Authentification utilisateurs
- [ ] Historique des requêtes
- [ ] Partage de templates entre utilisateurs

---

## Licence

MIT — voir [LICENSE](LICENSE)

---

*Mercator BI Explorer n'est pas affilié au projet [Mercator](https://github.com/dbarzin/mercator) de dbarzin.*
