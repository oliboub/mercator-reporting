# PRD — Mercator BI Explorer — Reporting Intelligent pour Mercator CMDB
**Version 4.0 — Phases 1, 2, 3 & 4 Terminées**

---

## 1. Résumé Exécutif

**Objectif Business :** Fournir un outil intelligent de reporting utilisant les API de Mercator CMDB pour permettre aux utilisateurs de créer, personnaliser et exporter leurs propres rapports sans dépendre de l'équipe de développement.

**Vision :** Recréer l'approche flexible de reporting qui faisait le succès d'Isiparc dans les années 2000 (via Cognos Impromptu), en adaptant cette philosophie aux technologies modernes et aux besoins actuels de gestion de CMDB. L'ajout d'un LLM local (Ollama) permet d'aller plus loin : l'utilisateur interroge la CMDB en langage naturel.

**Références :**
- Mercator GitHub : https://github.com/dbarzin/mercator
- Mercator Documentation : https://dbarzin.github.io/mercator/
- Mercator APIs : https://dbarzin.github.io/mercator/api/
- Mercator API Advanced (filtres) : https://dbarzin.github.io/mercator/apifilters/
- Mercator Data Model : https://dbarzin.github.io/mercator/model/

---

## 2. Historique et Contexte

### 2.1 Contexte Historique
Dans les années 2000, il existait des logiciels de gestion de parc micro-informatique. Entre autres, un outil qui se nommait **Isiparc** de la société **Isilog** avait la particularité d'avoir un modèle de données extrêmement bien fait, permettant de gérer n'importe quel parc, que ce soit des PCs ou des bâtiments.

### 2.2 L'Approche Isiparc pour le Reporting
Un des avantages majeurs de ce logiciel était l'approche pour le reporting :
- **Pas de rapports intégrés directement dans l'outil**
- **Fourniture d'une interface pour Cognos Impromptu**
- **Permettait aux utilisateurs de réaliser leurs propres rapports** selon leurs besoins spécifiques

### 2.3 Cognos Impromptu — Référence Technique
**Cognos Impromptu** était un outil de requêtage et de reporting d'IBM qui permettait :
- La création de requêtes sans connaissance SQL approfondie
- La génération de rapports personnalisés via une interface graphique
- L'export vers de multiples formats (PDF, Excel, HTML)
- La connexion à diverses sources de données via des catalogues métier

**Leçon Apprise :** Cette approche "self-service" donnait l'autonomie aux utilisateurs finaux tout en réduisant la charge sur les équipes techniques.

---

## 3. Objectifs du Projet

### 3.1 Objectifs Principaux

| Objectif | Description | Priorité | Statut |
|----------|-------------|----------|--------|
| Autonomie utilisateur | Permettre aux utilisateurs de créer leurs rapports sans développeur | Haute | ✅ MVP |
| Flexibilité | Adapter les rapports à tous types de besoins métier | Haute | ✅ MVP |
| Pérennité | Possibilité de sauvegarder les requêtes et templates de rapports | Haute | ✅ MVP |
| Performance | Temps de génération de rapports < 30 secondes (hors Ollama) | Moyenne | ✅ API filtrée |
| Sécurité | Respect des rôles et permissions CMDB | Haute | 🔲 Phase 5 |
| Export multi-format | PDF, CSV, Markdown (Excel Phase 5) | Moyenne | ✅ PDF+CSV+MD |
| LLM local | Requêtes en langage naturel via Ollama | Haute | ✅ Phase 4 |

### 3.2 Périmètre

**Inclus (MVP réalisé) :**
- Connexion aux API Mercator CMDB avec authentification Bearer
- 5 templates de rapports prédéfinis (CIAT, BIA, RGPD, Inventaire applicatif, Inventaire serveurs)
- Query Builder en langage naturel via Ollama (LLM local)
- Templates personnels sauvegardés (CRUD JSON)
- Export PDF (thème clair impression), CSV (Excel-compatible), Markdown
- Interface React dark theme avec prévisualisation
- Filtrage côté serveur via API Advanced Mercator (prioritaire) + fallback Python

**Exclus :**
- Modification des données de la CMDB
- Administration de la CMDB elle-même
- Export Excel .xlsx (Phase 5)
- Authentification utilisateurs (Phase 5)
- Intégration CVE/NVD (Backlog)

---

## 4. Architecture Technique

### 4.1 Architecture en Couches

```
+-------------------------------------------------------------+
|                    Couche Présentation                       |
|  +-----------------------------------------------------+    |
|  |   Frontend React 18 + Vite + TailwindCSS            |    |
|  |   (BI Explorer — dark theme)                        |    |
|  |   Dashboard | ReportView | QueryBuilder             |    |
|  +-----------------------------------------------------+    |
+-------------------------------------------------------------+
                              |  proxy /api/*
                              v
+-------------------------------------------------------------+
|                    Couche Métier                             |
|  +-------------+  +-------------+  +-------------------+   |
|  |  ReportEngine|  | OllamaService|  |  ExportService   |   |
|  |  (pipeline) |  | (LLM local) |  |  PDF/CSV/MD      |   |
|  +-------------+  +-------------+  +-------------------+   |
|         Backend Python + FastAPI                             |
+-------------------------------------------------------------+
                              |
              +---------------+---------------+
              v                               v
+---------------------+           +---------------------+
|   Mercator CMDB     |           |   Ollama (hôte)     |
|   API REST :8080    |           |   LLM local :11434  |
|   (filtres avancés) |           |   gemma3:4b / ...   |
+---------------------+           +---------------------+
```

### 4.2 Architecture Docker

```
Navigateur
  ├── :3000 → mercator-frontend  (nginx:alpine + React build)
  │              └── proxy /api/* → mercator-reporting:8000
  └── :8000 → mercator-reporting (python:3.11-slim + FastAPI)
                 ├── → Mercator CMDB  http://host.docker.internal:8080
                 └── → Ollama         http://host.docker.internal:11434
```

| Container | Base | Port | Rôle |
|-----------|------|------|------|
| `mercator-reporting` | python:3.11-slim | 8000 | Backend API, ReportEngine, Ollama |
| `mercator-frontend` | nginx:alpine | 3000 | React SPA, proxy API |

### 4.3 Stack Technique

| Couche | Technologie | Justification |
|--------|-------------|---------------|
| Frontend | React 18 + Vite + TailwindCSS | Moderne, dark theme, SPA |
| Backend | Python 3.11 + FastAPI + Uvicorn | Async, typage fort, docs auto |
| Modèles | Pydantic v2 | Validation + sérialisation |
| HTTP client | httpx[http2] | Async, retry, HTTP/2 |
| Export PDF | ReportLab | Génération native Python |
| LLM local | Ollama (gemma3:4b+) | Pas de dépendance cloud |
| Containerisation | Docker + Docker Compose | 2 containers, déploiement simple |
| Gestion paquets | uv + pyproject.toml | Moderne, pas de requirements.txt |

### 4.4 Pipeline ReportEngine

```
ReportQuery (Pydantic)
      │
      ├─ _can_use_server_filters() ?
      │     ├── OUI → MercatorClient.get_endpoint_filtered()   ← API Advanced Mercator
      │     │         (filter[field_op]=value, sort=field, include=relations)
      │     └── NON → get_endpoint() + apply_filters() Python  ← fallback
      │
      ├─ apply_filters()          ← filtres résiduels Python si besoin
      ├─ _enrich()                ← jointures FK + Many-to-Many
      │     ├─ _resolve_ids()     ← résolution IDs → objets complets
      │     └─ _expand_relation_keys() ← 1 app + N serveurs → N lignes
      ├─ _strip_raw_relations()   ← nettoyage listes résiduelles
      ├─ apply_sort()             ← tri multi-champs (robuste aux listes)
      ├─ apply_projection()       ← sélection + renommage colonnes
      └─ ReportResult
```

### 4.5 Pipeline Query Builder (Ollama)

```
Utilisateur (langage naturel)
      │
      POST /api/query/interpret
      │
      OllamaService.interpret()
      │  ├── Prompt système avec exemples concrets
      │  ├── Normalisation relation_key (tirets → underscores)
      │  └── Fallback [Non interprété] si JSON invalide
      │
      ReportQuery JSON
      │
      ReportEngine.execute()
      │
      ReportResult → prévisualisation frontend
      │
      [Optionnel] UserTemplateService.create()  ← sauvegarde sans Ollama
```

---

## 5. Arborescence du Projet

### 5.1 Arborescence locale (host)

```
mercator_reporting/
│
├── src/
│   ├── config.py                      ← Settings Pydantic (URLs, credentials, Ollama, TTL)
│   ├── main.py                        ← FastAPI app, 3 routers, CORS, logging
│   │
│   ├── api/routes/
│   │   ├── mercator.py                ← GET /api/mercator/* (debug, désactivé si DEBUG=false)
│   │   ├── reports.py                 ← POST /api/reports/* (templates + export)
│   │   └── query.py                   ← POST /api/query/* (Ollama + templates utilisateur)
│   │
│   ├── core/
│   │   ├── mercator_client.py         ← Client HTTP (Bearer, cache TTL, retry x3, filtres API)
│   │   └── dependencies.py            ← Injection FastAPI (singleton MercatorClient)
│   │
│   ├── models/
│   │   └── report.py                  ← ReportQuery, JoinDefinition, FilterDefinition,
│   │                                     SortDefinition, FilterOperator, SortDirection
│   │
│   ├── reporting/
│   │   ├── engine.py                  ← ReportEngine (pipeline complet)
│   │   └── filters.py                 ← apply_filters, apply_sort, apply_projection
│   │
│   └── services/
│       ├── export.py                  ← ExportService (PDF ReportLab, CSV, Markdown)
│       ├── ollama_service.py          ← OllamaService (interpret, interpret_raw)
│       └── user_templates.py          ← UserTemplateService (CRUD JSON local)
│
├── tests/
│   ├── conftest.py                    ← Fixtures + mocks (dump_standard.json)
│   ├── test_phase1_api.py             ← 35 tests routes HTTP
│   ├── test_phase1_mercator_client.py ← 23 tests unitaires MercatorClient
│   ├── test_phase2_models.py          ← Tests modèles Pydantic
│   ├── test_phase2_filters.py         ← Tests filtres, tri, projection
│   └── test_phase2_engine.py          ← Tests ReportEngine
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx                    ← Router React (/, /reports/:id, /query)
│   │   ├── api/reports.js             ← Appels API backend
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx          ← Liste templates prédéfinis
│   │   │   ├── ReportView.jsx         ← Vue rapport + export PDF/CSV/MD
│   │   │   └── QueryBuilder.jsx       ← Requête libre Ollama + templates perso
│   │   └── components/
│   │       ├── ReportTable.jsx        ← Tableau avec rendu CIAT (barres colorées)
│   │       ├── Navbar.jsx
│   │       └── TemplateCard.jsx
│   ├── nginx.conf                     ← proxy /api/*, timeouts Ollama (2700s)
│   ├── Dockerfile.frontend
│   └── package.json                   ← React 18 + Vite + TailwindCSS
│
├── docs/
│   ├── sources/
│   │   ├── mercator_backup_dump_v4.py ← Script de dump API Mercator
│   │   └── dump_standard.json         ← Données de référence (50 endpoints)
│   └── ANNEXE_A_mapping_mercator.md   ← Mapping endpoints/champs/relations/CIAT/BIA
│
├── storage/                           ← Volume Docker persistant
│   ├── reports/
│   ├── templates/
│   └── user_templates.json            ← Templates personnels (CRUD)
│
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml                     ← uv, dépendances (httpx[http2], reportlab, etc.)
├── pytest.ini
├── .env.example
└── README.md
```

### 5.2 Arborescence dans les containers Docker

**Container `mercator-reporting`** (python:3.11-slim)
```
/app/
├── pyproject.toml
├── src/                    ← code source
└── storage/                ← volume persistant (user_templates.json)
```

**Container `mercator-frontend`** (nginx:alpine)
```
/usr/share/nginx/html/      ← build React (Vite)
/etc/nginx/conf.d/
└── default.conf            ← nginx.conf (proxy + timeouts 2700s)
```

### 5.3 Variables d'environnement

| Variable | Défaut | Rôle |
|----------|--------|------|
| `MERCATOR_BASE_URL` | `http://host.docker.internal:8080` | URL Mercator |
| `MERCATOR_LOGIN` | `admin@admin.com` | Login Mercator |
| `MERCATOR_PASSWORD` | `password` | Mot de passe |
| `CACHE_TTL_SECONDS` | `300` | TTL cache mémoire |
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` | URL Ollama |
| `OLLAMA_MODEL` | `gemma3:4b` | Modèle LLM par défaut |
| `OLLAMA_TIMEOUT` | `2700` | Timeout Ollama (45 min, CPU sans GPU) |
| `USER_TEMPLATES_PATH` | `/app/storage/user_templates.json` | Templates personnels |
| `DEBUG` | `false` | Active /api/mercator/* si true |
| `MAX_EXPORT_ROWS` | `10000` | Limite export |

---

## 6. Templates de Rapports Prédéfinis

| ID | Nom | Endpoint | Jointures | Export |
|----|-----|----------|-----------|--------|
| `ciat` | Classification Sécurité CIAT | `applications` | `application-blocks` (FK) | PDF barres colorées |
| `bia` | Analyse d'Impact Métier | `activities` | — | PDF/CSV |
| `rgpd` | Registre des Traitements | `data-processings` | — | PDF/CSV |
| `inventaire-applicatif` | Inventaire Applicatif | `applications` | `application-blocks` (FK) | PDF/CSV |
| `inventaire-serveurs` | Inventaire Serveurs Logiques | `logical-servers` | — | PDF/CSV |

### Rendu CIAT (PDF & tableau)
Les niveaux de sécurité (1–4) sont visualisés avec des barres colorées :

| Niveau | Barre | Label | Couleur |
|--------|-------|-------|---------|
| 1 | `█░░░` | Faible | Vert `#059669` |
| 2 | `██░░` | Moyen | Orange `#d97706` |
| 3 | `███░` | Élevé | Rouge `#dc2626` |
| 4 | `████` | Critique | Violet `#7c3aed` |

---

## 7. API Advanced Mercator — Intégration

L'API Advanced Mercator (filtre côté serveur) est utilisée en priorité par le ReportEngine.

### Syntaxe des filtres
```
filter[<field>]=<value>              # Égalité / LIKE auto (name, description)
filter[<field>_<operator>]=<value>   # Avec opérateur
```

### Mapping opérateurs

| Notre FilterOperator | Suffixe Mercator | Exemple |
|---------------------|-----------------|---------|
| `EQ` | *(aucun)* | `filter[name]=RH-Solution` |
| `NEQ` | `_not` | `filter[type_not]=opensource` |
| `CONTAINS` | *(aucun)* | `filter[name]=backup` (LIKE auto) |
| `GT` / `GTE` | `_gt` / `_gte` | `filter[rto_gte]=4` |
| `LT` / `LTE` | `_lt` / `_lte` | `filter[rto_lte]=24` |
| `IN` | `_in` | `filter[id_in]=1,2,3` |
| `IS_NULL` | `_null=true` | `filter[description_null]=true` |
| `IS_NOT_NULL` | `_null=false` | `filter[description_null]=false` |

### Tri et include
```
sort=name          # ASC
sort=-created_at   # DESC
include=logical_servers,databases
```

### Logique de sélection dans le ReportEngine
```python
if _can_use_server_filters(query):
    # Filtres + tri + include → délégués à Mercator
    get_endpoint_filtered(endpoint, filters, sort, include)
else:
    # Fallback : charge tout, filtre en Python
    get_endpoint() + apply_filters()
```

**Conditions pour mode API filtrée :**
- Au moins un filtre ou un tri défini
- Aucun opérateur `NOT_CONTAINS` ou `STARTS_WITH` (non supportés côté serveur)

---

## 8. User Stories & Critères d'Acceptance

### US1 — Proposition d'Architecture ✅
**En tant que** Responsable Produit Mercator
**Je veux** disposer d'une approche innovante et documentée pour le reporting

**Critères d'acceptance :**
- [x] Solution proposée et validée
- [x] Critères définis et mesurables
- [x] Instructions de développement rédigées
- [x] Schéma d'architecture Mermaid présent
- [x] Stratégie agile avec étapes définies
- [x] Document complet en Markdown livré

---

### US2 — Appel des Endpoints Mercator ✅
**En tant que** Product Owner Mercator CMDB
**Je veux** consulter chaque asset par catégorie via les API Mercator

**Critères d'acceptance :**
- [x] Liste filtrable de tous les équipements par catégorie
- [x] Détails des informations par équipement
- [x] Export des données en JSON
- [x] Mise à jour en temps réel depuis la CMDB
- [x] Cache mémoire TTL configurable (défaut 300s)
- [x] Retry automatique x3 sur erreur réseau

---

### US3 — Inventaire et Configuration ✅
**En tant que** Gestionnaire de parc informatique
**Je veux** consulter l'inventaire complet des équipements et de leurs liens

**Critères d'acceptance :**
- [x] 5 templates prédéfinis (CIAT, BIA, RGPD, applicatif, serveurs)
- [x] Jointures Many-to-Many avec résolution d'IDs
- [x] Jointures par clé étrangère FK
- [x] Expand automatique (1 app + N serveurs → N lignes)
- [x] Export PDF impression-friendly, CSV UTF-8 BOM, Markdown
- [x] Interface React avec prévisualisation

---

### US4 — Reporting Intelligent Self-Service ✅
**En tant que** Utilisateur métier ou Gestionnaire de CMDB
**Je veux** créer mes propres rapports en langage naturel

**Critères d'acceptance :**
- [x] Interface Query Builder intuitive
- [x] Requête en langage naturel → ReportQuery via Ollama
- [x] Prévisualisation live des résultats
- [x] JSON de la requête visible et éditable manuellement
- [x] Sauvegarde des templates personnels (sans Ollama)
- [x] Sélection du modèle Ollama depuis l'interface
- [ ] Partage de templates entre utilisateurs (Phase 5)
- [ ] Drag & drop pour construire les requêtes manuellement (Backlog)

---

### Backlog — User Stories Métier Avancées

#### US5.1 — BIA — Besoins de Sécurité 🔲
- [ ] Tableau des RTO/RPO par application
- [ ] Classification des niveaux de criticité
- [ ] Export pour documentation de continuité

#### US5.2 — Impacts sur la Continuité d'Activité 🔲
- [ ] Calcul d'impact par heure d'indisponibilité
- [ ] Cartographie des dépendances entre services
- [ ] Rapports d'impact visuels (graphiques)

#### US5.3 — CVE / Vulnérabilités 🔲
- [ ] Recherche de CVE via CPE des applications
- [ ] Intégration NVD/MITRE
- [ ] Alertes sur vulnérabilités critiques

#### US5.4 — RGPD avancé 🔲
- [ ] Mapping données sensibles par application
- [ ] Durées de conservation configurables
- [ ] Rapports de conformité RGPD

---

## 9. Plan d'Implémentation Agile

### Phase 1 — Analyse & Conception ✅ TERMINÉE
```
├── Audit des API Mercator CMDB
├── Mapping données → ANNEXE_A_mapping_mercator.md
├── Architecture technique → PRD v2.0
└── Environnement de développement
```
**Livrable :** PRD v2.0 + Annexe A + pyproject.toml + Dockerfile + docker-compose

---

### Phase 2 — Socle Technique ✅ TERMINÉE
```
├── MercatorClient (Bearer, cache TTL, retry x3)     src/core/mercator_client.py
├── Routes FastAPI /api/mercator/*                    src/api/routes/mercator.py
├── Injection de dépendances (singleton)              src/core/dependencies.py
└── 58 tests unitaires + HTTP (pytest)
```
**Livrable :** Backend opérationnel, 5 routes API, 58 tests

```bash
uv run pytest -m phase1 -v
uv run pytest tests/test_phase1_mercator_client.py -v
uv run pytest tests/test_phase1_api.py -v
```

---

### Phase 3 — Core Reporting ✅ TERMINÉE
```
├── Modèles Pydantic (ReportQuery, JoinDefinition...)   src/models/report.py
├── ReportEngine (pipeline Fetch→Filter→Enrich→Sort)    src/reporting/engine.py
├── Filtres Python (apply_filters, apply_sort...)        src/reporting/filters.py
├── 5 templates prédéfinis                              src/api/routes/reports.py
├── ExportService (PDF ReportLab, CSV, Markdown)        src/services/export.py
├── Frontend React (Dashboard, ReportView, Navbar)
└── 121 tests
```
**Livrable :** Interface self-service fonctionnelle, export PDF/CSV/MD

```bash
uv run pytest -m phase2 -v
```

**Points techniques résolus :**
- Résolution d'IDs Mercator (`logical_servers: [4]` → objets complets via `_resolve_ids`)
- Expand Many-to-Many (1 app → N lignes serveurs via `_expand_relation_keys`)
- PDF thème clair impression-friendly (fond blanc, barres CIAT colorées)
- Nom fichier PDF ASCII-safe (tirets cadratins encodés)

---

### Phase 4 — Query Builder Ollama ✅ TERMINÉE
```
├── OllamaService (interpret, interpret_raw, normalisation)   src/services/ollama_service.py
├── UserTemplateService (CRUD JSON)                           src/services/user_templates.py
├── Routes Query Builder (/api/query/*)                       src/api/routes/query.py
├── Filtrage côté serveur API Advanced Mercator               src/core/mercator_client.py
├── Robustesse apply_sort (listes, SortDefinition[])          src/reporting/filters.py
└── Frontend QueryBuilder.jsx
```
**Livrable :** Requête en langage naturel fonctionnelle, templates personnels, filtres API Mercator

**Configuration Ollama requise :**
```bash
# Ollama doit écouter sur toutes les interfaces (accessible depuis Docker)
sudo systemctl edit ollama
# Ajouter :
[Service]
Environment="OLLAMA_HOST=0.0.0.0"
sudo systemctl daemon-reload && sudo systemctl restart ollama
```

**Modèles recommandés :**

| Modèle | RAM | Qualité JSON | Vitesse CPU |
|--------|-----|--------------|-------------|
| `gemma3:4b` | 4 GB | Bonne | ~2 min |
| `gemma3:12b` | 10 GB | Très bonne | ~5 min |
| `qwen3.5:9b` | 8 GB | Excellente | ~4 min |

**Points techniques résolus :**
- `apply_sort` recevait `list[SortDefinition]` au lieu d'un `str` → itération corrigée
- `obj.get()` sur une liste → guard `isinstance(val, (list, dict))` dans `sort_key`
- Normalisation `relation_key` : tirets → underscores (Ollama génère `logical-servers`)
- Timeout nginx porté à 2700s (`proxy_read_timeout`) pour Ollama sur CPU sans GPU
- Ordre des routes FastAPI : `/interpret` déclaré avant `/interpret/debug`

**Routes Query Builder :**

| Route | Méthode | Description |
|-------|---------|-------------|
| `/api/query/ollama/status` | GET | Statut + modèles disponibles |
| `/api/query/interpret` | POST | Langage naturel → ReportQuery + exécution |
| `/api/query/interpret/debug` | POST | Réponse brute Ollama |
| `/api/query/templates` | GET/POST | Liste + création templates |
| `/api/query/templates/{id}` | GET/PUT/DELETE | CRUD template |
| `/api/query/templates/{id}/execute` | POST | Exécuter sans Ollama |

---

### Phase 5 — Production 🔲 À PLANIFIER
```
├── Authentification utilisateurs (JWT ou SSO)
├── Export Excel .xlsx (openpyxl)
├── Historique des requêtes
├── Partage de templates entre utilisateurs
├── Désactivation routes /api/mercator/* (DEBUG=false)
├── Tests d'acceptance complets
└── Documentation utilisateur
```

---

## 10. Critères de Succès

### 10.1 Métriques de Performance

| Métrique | Cible | Statut |
|----------|-------|--------|
| Temps génération rapport (templates) | < 30 secondes | ✅ < 5s (API filtrée) |
| Temps Query Builder (Ollama CPU) | < 5 minutes | ✅ ~2 min gemma3:4b |
| Disponibilité du service | 99.5% | 🔲 À mesurer |
| Satisfaction utilisateur | > 8/10 | 🔲 À mesurer |

### 10.2 Critères de Qualité

- [x] US1, US2, US3, US4 implémentées et testées
- [x] 133+ tests pytest (phase1 + phase2)
- [x] Export PDF/CSV/MD fonctionnel
- [x] Query Builder Ollama fonctionnel
- [ ] Couverture tests > 80%
- [ ] Authentification (Phase 5)
- [ ] Documentation utilisateur complète

---

## 11. Risques et Mitigations

| Risque | Probabilité | Impact | Mitigation | Statut |
|--------|-------------|--------|------------|--------|
| API Mercator IDs vs objets | ~~Haute~~ | ~~Élevé~~ | `_resolve_ids()` implémenté | ✅ Résolu |
| Timeout Ollama sur CPU | Haute | Moyen | Timeout 2700s, nginx 2700s | ✅ Résolu |
| Qualité JSON Ollama | Moyenne | Moyen | Normalisation + fallback | ✅ Résolu |
| Performance gros volumes | Moyenne | Moyen | API filtrée côté serveur | ✅ Résolu |
| Adoption utilisateur faible | Moyenne | Élevé | UX soignée, LLM naturel | En cours |
| Évolution RGPD | Faible | Moyen | Architecture extensible | 🔲 Backlog |

---

## 12. Gouvernance et Suivi

### 12.1 Parties Prenantes

| Rôle | Nom | Responsabilités |
|------|-----|-----------------|
| Product Owner | [À définir] | Priorisation, validation US |
| Lead Tech | [À définir] | Architecture, code review |
| RSSI | [À définir] | Validation sécurité |
| DPO | [À définir] | Validation conformité RGPD |
| Utilisateurs clés | [À définir] | Tests, feedback |

---

## 13. Annexes

### 13.1 Glossaire

| Terme | Définition |
|-------|------------|
| CMDB | Configuration Management Database |
| BIA | Business Impact Analysis |
| RTO | Recovery Time Objective |
| RPO | Recovery Point Objective |
| CIAT | Confidentialité / Intégrité / Disponibilité / Traçabilité |
| CVE | Common Vulnerabilities and Exposures |
| CPE | Common Platform Enumeration |
| RGPD | Règlement Général sur la Protection des Données |
| LLM | Large Language Model |
| FK | Foreign Key (clé étrangère) |

### 13.2 Documents Annexes

| Annexe | Fichier | Description |
|--------|---------|-------------|
| Annexe A | `ANNEXE_A_mapping_mercator.md` | Mapping complet endpoints, champs, relations, CIAT, BIA, graphe de dépendances |
| README | `README.md` | Guide d'installation et d'utilisation GitHub |
| SKILLS | `SKILLS.md` | Compétences techniques du projet (pour onboarding) |
| CLAUDE | `CLAUDE.md` | Contexte projet pour assistant IA |

### 13.3 Références

- Documentation API Mercator CMDB : https://dbarzin.github.io/mercator/api/
- API Advanced Mercator (filtres) : https://dbarzin.github.io/mercator/apifilters/
- Modèle de données Mercator : https://dbarzin.github.io/mercator/model/
- Standard ISO 22301 (Continuité d'activité)
- Règlement RGPD (UE 2016/679)
- Base NVD pour les CVE : https://nvd.nist.gov/

---

## 14. Historique des Versions

| Version | Date | Modifications |
|---------|------|---------------|
| 1.0 | 2026 | Version initiale |
| 1.1 | 2026 | Ajout section Cognos Impromptu |
| 1.2 | 2026 | Complétion user stories et plan d'implémentation |
| 2.0 | Mars 2026 | Consolidation : architecture, risques, gouvernance, backlog Phase 2 |
| 3.0 | Mars 2026 | Phases 1 & 2 terminées : arborescences, livrables réels, commandes curl |
| 4.0 | Mars 2026 | Phases 3 & 4 terminées : ReportEngine, QueryBuilder Ollama, API filtrée Mercator, corrections techniques |

---

**Document approuvé par :**

| Rôle | Nom | Date |
|------|-----|------|
| Product Owner | | |
| Directeur Technique | | |
| RSSI | | |

---

> **Note :** Ce PRD est un document vivant. Toute modification significative doit être validée par le comité de pilotage.
