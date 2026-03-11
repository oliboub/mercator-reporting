# Documentation des Tests — Mercator Reporting
*Phase 1 & Phase 2 — 133 tests*

---

## 1. Prérequis et Installation

### Installer les dépendances de développement

Avec **uv** (recommandé — lit `[tool.uv] dev-dependencies` dans `pyproject.toml`) :

```bash
# Depuis la racine du projet mercator_reporting/
uv sync
```

C'est la seule commande nécessaire. Elle crée `.venv/` et installe prod + dev.

> **Pourquoi `uv sync` et pas `uv pip install` ?**
> `uv sync` est la commande native uv. Elle lit `[tool.uv] dev-dependencies`
> où sont déclarés pytest et ses plugins. `uv pip install -e ".[dev]"` lit
> `[project.optional-dependencies]` — les deux sections sont synchronisées
> dans notre `pyproject.toml` mais `uv sync` est plus simple.

### Vérifier que pytest est disponible

```bash
uv run pytest --version
# → pytest 7.x.x
```

---

## 2. Structure des tests

```
tests/
├── conftest.py                      # Fixtures globales et données mock
├── test_phase1_api.py               # Tests routes HTTP — US2 (35 tests)       ✅ Phase 1
├── test_phase1_mercator_client.py   # Tests unitaires MercatorClient (23 tests) ✅ Phase 1
├── test_phase2_models.py            # Tests modèles Pydantic ReportEngine (33 tests) ✅ Phase 2
├── test_phase2_filters.py           # Tests moteur de filtres (42 tests)            ✅ Phase 2
├── test_phase2_query.py             # Tests Query Builder (stub — Étape 4)
└── run_tests.sh                     # Raccourcis par phase
```

**Fichiers source associés (Phase 2) :**
```
src/
├── models/
│   └── report.py          # FilterDefinition, ReportQuery, ReportResult, ...
└── reporting/
    └── filters.py         # apply_filters(), apply_sort(), apply_projection()
```

### Marqueurs pytest disponibles

| Marqueur | Contenu | Commande |
|----------|---------|---------|
| `phase1` | Tests API routes + MercatorClient | `uv run pytest -m phase1` |
| `phase2` | Tests modèles Pydantic + filtres dynamiques (75 tests) | `uv run pytest -m phase2` |
| `integration` | Tests avec Mercator réel (réseau) | `uv run pytest -m integration` |
| `slow` | Tests lents (export volumineux) | `uv run pytest -m slow` |

---

## 3. Lancer les tests

### Commandes de base

```bash
# Tous les tests
uv run pytest

# Phase 1 uniquement (routes API + MercatorClient — US2)
uv run pytest -m phase1 -v

# Phase 2 uniquement (modèles Pydantic + filtres — 75 tests)
uv run pytest -m phase2 -v

# Toutes les phases
uv run pytest -m "phase1 or phase2" -v

# Un fichier spécifique
uv run pytest tests/test_phase1_api.py -v
uv run pytest tests/test_phase1_mercator_client.py -v
uv run pytest tests/test_phase2_models.py -v
uv run pytest tests/test_phase2_filters.py -v

# Une classe de tests spécifique
uv run pytest tests/test_phase2_filters.py::TestNullFilters -v
uv run pytest tests/test_phase2_filters.py::TestNumericFilters -v
uv run pytest tests/test_phase1_api.py::TestEndpointList -v

# Un test spécifique
uv run pytest tests/test_phase2_filters.py::TestNullFilters::test_bia_filter_activities_with_rto -v
```

### Avec couverture de code

```bash
# Rapport dans le terminal
uv run pytest --cov=src --cov-report=term-missing

# Rapport HTML (ouvrir htmlcov/index.html)
uv run pytest --cov=src --cov-report=html
```

### En mode watch (relance à chaque modification)

```bash
# Installer pytest-watch si besoin : uv pip install pytest-watch
uv run ptw -- -m phase1 -v
```

---

## 4. Architecture des tests — Phase 1 (58 tests)

### 4.1 `tests/conftest.py` — Fixtures et données mock

Les mocks sont construits à partir des **données réelles** de `dump_standard.json`.
Pas de données inventées — les tests reflètent ce que Mercator retourne vraiment.

**Données mock disponibles :**

| Variable | Contenu | Basé sur |
|----------|---------|---------|
| `MOCK_APPLICATIONS` | 3 apps (SAP ASCS, SAP ECC, PORTAIL-RH) | dump réel |
| `MOCK_ACTIVITIES` | 2 activités dont 1 avec RTO/RPO renseignés | dump réel |
| `MOCK_LOGICAL_SERVERS` | 2 serveurs (Ubuntu, Windows Server) | dump réel |
| `MOCK_DATA_PROCESSINGS` | 1 traitement RGPD Article 30 | dump réel |
| `MOCK_ENTITIES` | 2 entités (LOGISTIX + partenaire) | dump réel |

**Fixtures disponibles dans les tests :**

```python
def test_mon_test(client):
    # client = TestClient FastAPI avec MercatorClient mocké
    # Aucun appel réseau réel

def test_integration(real_mercator_client):
    # real_mercator_client = client HTTP vers Mercator réel
    # Nécessite --mercator-url, --mercator-login, --mercator-password
```

### 4.2 `test_phase1_api.py` — 35 tests sur les routes HTTP

Ce fichier teste les routes FastAPI **sans appel réseau réel** (MercatorClient est mocké).

**Classes de tests :**

#### `TestSystemEndpoints` — Health checks
```
test_health_ok                    → GET /health retourne 200 + status:ok
test_root_returns_links           → GET / retourne les liens docs/health/endpoints
test_openapi_schema_accessible    → GET /openapi.json disponible
```

#### `TestMercatorHealth` — Connectivité Mercator
```
test_mercator_health_ok           → GET /api/mercator/health retourne status:ok
test_mercator_health_auth_error   → Retourne 503 si credentials invalides
```

#### `TestEndpointDiscovery` — Découverte des endpoints
```
test_list_endpoints_returns_all   → GET /api/mercator/endpoints liste les 50 endpoints
test_unknown_endpoint_returns_404 → Endpoint inconnu → 404 avec message explicite
```

#### `TestEndpointList` — Listing des objets (US2)
```
test_get_applications             → Liste 3 applications
test_get_activities_with_bia_fields → Champs RTO/RPO présents
test_get_logical_servers          → Liste 2 serveurs logiques
test_get_data_processings_rgpd    → Champs RGPD présents
test_get_empty_endpoint_returns_empty_list → Endpoint vide → [] pas d'erreur
test_response_structure_is_consistent → Structure {endpoint, total, data, limit, offset}
```

#### `TestFilteringAndPagination` — Filtres et pagination
```
test_search_filter_by_name        → ?search=SAP → retourne SAP ASCS + SAP ECC
test_search_filter_case_insensitive → sap == SAP
test_search_no_result             → Recherche sans résultat → total:0
test_pagination_limit             → ?limit=2 → count:2, total:3
test_pagination_offset            → ?offset=1 → items décalés
test_pagination_limit_max         → ?limit=9999 → 422 (validation)
test_pagination_limit_min         → ?limit=0 → 422 (validation)
```

#### `TestObjectDetail` — Détail par ID
```
test_get_application_by_id        → GET /api/mercator/applications/1 → SAP ASCS
test_get_object_includes_relations_by_default → relations_included:true par défaut
test_get_object_without_relations → ?with_relations=false
test_get_activity_bia_values      → Activité GESTION-PAIE : RTO=4, RPO=24, MTD=8
test_object_not_found_returns_404 → ID inexistant → 404
test_object_on_unknown_endpoint_returns_404 → endpoint inconnu → 404
```

#### `TestExportJSON` — Export (US2 critère "Export en JSON")
```
test_export_applications_json     → GET /api/mercator/applications/export/json
test_export_activities_json_contains_bia_fields → Champs BIA dans l'export
test_export_content_type_is_json  → Content-Type: application/json
test_export_with_relations_flag   → ?with_relations=true indiqué dans réponse
```

### 4.3 `test_phase1_mercator_client.py` — 23 tests unitaires MercatorClient

Tests **purement unitaires** — aucun appel réseau, tout est mocké avec `unittest.mock`.

#### `TestAuthentication` — Auth Bearer
```
test_authenticate_success         → Token stocké dans self._token
test_authenticate_401_raises_auth_error → MercatorAuthError levée
test_authenticate_missing_token_raises_error → Réponse sans token → erreur
test_authenticate_connection_error → Réseau KO → MercatorAuthError
test_get_headers_triggers_auth_if_no_token → Auto-auth si pas de token
test_get_headers_reuses_existing_token → Token existant réutilisé sans re-auth
test_token_refresh_on_401         → 401 sur GET → re-auth automatique + retry
```

#### `TestGetEndpoint` — get_endpoint()
```
test_get_endpoint_returns_list    → Retourne une liste d'objets
test_get_endpoint_unwraps_data_envelope → Désenveloppe {"data": [...]}
test_get_endpoint_returns_empty_list_if_none → [] si réponse vide
test_get_endpoint_404_raises_api_error → MercatorAPIError(status_code=404)
```

#### `TestGetObject` — get_object()
```
test_get_object_returns_dict      → Retourne un dict
test_get_object_with_relations_sends_include_param → Param include envoyé
test_get_object_without_relations_no_include → Pas de param include
```

#### `TestCache` — Cache mémoire TTL
```
test_cache_entry_valid_within_ttl → Valide avant expiration
test_cache_entry_expired_after_ttl → Invalide après expiration
test_get_endpoint_uses_cache_on_second_call → 1 seule requête réseau sur 2 appels
test_invalidate_cache_clears_endpoint → Force nouvel appel réseau
test_invalidate_all_cache         → Vide tout le cache
test_no_cache_when_ttl_zero       → ttl=0 → toujours requête réseau
```

#### `TestCheckConnection` — check_connection()
```
test_check_connection_ok          → status:ok
test_check_connection_auth_error  → status:auth_error
test_check_connection_network_error → status:connection_error
```

#### `TestFullDump` + `TestEndpointsList`
```
test_full_dump_returns_all_endpoints      → Dict avec 50 endpoints
test_full_dump_skips_404_endpoints_gracefully → Endpoints vides → []
test_full_dump_with_custom_endpoints      → Liste personnalisée d'endpoints
test_all_known_endpoints_present          → 10 endpoints clés présents
test_no_duplicate_endpoints               → Pas de doublons
```

---

## 5. Architecture des tests — Phase 2 (75 tests)

### 5.1 `src/models/report.py` — Modèles Pydantic

Contrat de données entre le Query Builder, le ReportEngine et l'ExportService.

| Classe | Rôle |
|--------|------|
| `FilterDefinition` | Un filtre : champ + opérateur + valeur |
| `FilterOperator` | Enum des opérateurs : `eq`, `gte`, `contains`, `is_null`, `in`… |
| `ColumnDefinition` | Une colonne : champ source + libellé d'affichage |
| `SortDefinition` | Tri : champ + direction (asc/desc) |
| `ReportQuery` | Requête complète : endpoint + colonnes + filtres + tri + pagination |
| `ReportResult` | Résultat : métadonnées + lignes de données |
| `ExportFormat` | Enum des formats : `json`, `csv`, `xlsx`, `pdf` |

### 5.2 `src/reporting/filters.py` — Moteur de filtres

Logique Python pure — aucune dépendance réseau, testable sans Mercator.

| Fonction | Rôle |
|----------|------|
| `apply_filters(items, filters)` | Applique une liste de filtres en AND sur une liste d'objets |
| `apply_sort(items, field, ascending, none_last)` | Trie les objets sur un champ (None en fin par défaut) |
| `apply_projection(obj, fields)` | Projette un objet sur un sous-ensemble de champs |

### 5.3 `test_phase2_models.py` — 33 tests modèles Pydantic

#### `TestFilterDefinition` — Validation des filtres
```
test_eq_filter_basic              → FilterDefinition valide avec opérateur EQ
test_default_operator_is_eq       → Opérateur par défaut = EQ
test_is_null_ignores_value        → IS_NULL force value à None
test_is_not_null_ignores_value    → IS_NOT_NULL force value à None
test_in_operator_requires_list    → IN avec valeur non-liste → ValidationError
test_in_operator_accepts_list     → IN avec ["ERP", "Web"] → OK
test_gte_numeric_filter           → GTE avec valeur numérique → OK
test_all_operators_are_valid      → Tous les opérateurs de l'enum acceptés
```

#### `TestColumnDefinition` — Colonnes de rapport
```
test_basic_column                 → Colonne sans label
test_column_with_label            → display_label retourne le label
test_display_label_defaults_to_field → Sans label → display_label = field
test_bia_columns                  → Colonnes RTO/RPO/MTD correctement labellisées
test_ciat_columns                 → Colonnes C/I/A/T correctement labellisées
```

#### `TestReportQuery` — Requête de rapport
```
test_minimal_query                → Seul l'endpoint est requis
test_endpoint_stripped            → Espaces en début/fin supprimés
test_empty_endpoint_raises        → endpoint="" → ValidationError
test_whitespace_endpoint_raises   → endpoint="   " → ValidationError
test_limit_validation_min         → limit=0 → ValidationError
test_limit_validation_max         → limit=10001 → ValidationError
test_offset_cannot_be_negative    → offset=-1 → ValidationError
test_bia_report_query             → Requête BIA complète (activités + RTO IS_NOT_NULL)
test_ciat_report_query            → Requête CIAT (applications + security_need_c >= 3)
test_rgpd_report_query            → Requête RGPD (traitements + obligation légale)
test_multiple_filters_allowed     → 3 filtres sur la même requête
test_sort_definition              → Tri ASC + DESC sur 2 champs
```

#### `TestReportResult` — Résultat de rapport
```
test_empty_result                 → is_empty=True, to_records()=[]
test_non_empty_result             → 2 lignes → is_empty=False
test_to_records_returns_flat_list → Liste de dicts plats pour export CSV/Excel
test_metadata_columns             → Colonnes correctement déclarées
test_metadata_filters_applied     → Compteur de filtres actifs
test_export_format_enum           → json/xlsx/pdf/csv valides
```

### 5.4 `test_phase2_filters.py` — 42 tests moteur de filtres

#### `TestApplyFiltersGeneral` — Comportements généraux
```
test_no_filters_returns_all       → [] filtres → liste complète inchangée
test_empty_list_returns_empty     → Liste vide → liste vide
test_single_eq_filter             → type=ERP → 2 apps sur 3
test_neq_filter                   → type≠ERP → PORTAIL-RH uniquement
test_multiple_filters_combined_as_and → ERP AND security_need_c>=3 → 2 apps
test_filters_no_result            → Filtre sans résultat → []
test_filter_on_unknown_field      → Champ inconnu → []
```

#### `TestNullFilters` — Filtres de nullité (IS_NULL / IS_NOT_NULL)
```
test_is_null_on_rto               → rto IS NULL → SAP ASCS + SAP ECC
test_is_not_null_on_rto           → rto IS NOT NULL → PORTAIL-RH
test_bia_filter_activities_with_rto   → recovery_time_objective IS NOT NULL → GESTION-PAIE
test_bia_filter_activities_without_rto → recovery_time_objective IS NULL → MAINTENANCE-TMA-ERP
```

#### `TestNumericFilters` — Comparaisons numériques (BIA / CIAT)
```
test_gte_filter_security_need     → security_need_c >= 3 → 2 apps
test_lte_filter_security_need     → security_need_a <= 2 → PORTAIL-RH
test_gt_filter                    → security_need_c > 2 → 2 apps
test_lt_filter                    → security_need_c < 3 → PORTAIL-RH
test_eq_numeric_filter            → recovery_time_objective = 4 → GESTION-PAIE
test_bia_rto_gte_filter           → RTO >= 4h → GESTION-PAIE
test_bia_mtd_gte_filter           → MTD >= 8h → GESTION-PAIE
```

#### `TestStringFilters` — Comparaisons sur chaînes
```
test_contains_filter              → name CONTAINS "SAP" → 2 apps
test_contains_case_insensitive    → "sap" == "SAP" → 2 apps
test_not_contains_filter          → name NOT CONTAINS "SAP" → PORTAIL-RH
test_starts_with_filter           → name STARTS WITH "SAP" → 2 apps
test_starts_with_no_match         → "ORACLE" → []
test_contains_on_os               → os CONTAINS "Ubuntu" → SRV001
```

#### `TestInFilter` — Opérateur IN
```
test_in_filter_types              → type IN [ERP, Web] → 3 apps
test_in_filter_partial            → type IN [ERP] → 2 apps
test_in_filter_no_match           → type IN [CRM, BI] → []
test_in_filter_on_none_value      → drp IN [True] → GESTION-PAIE seulement
```

#### `TestRGPDFilters` — Filtres RGPD
```
test_rgpd_filter_legal_obligation → lawfulness_legal_obligation=True → EU Article 30
test_rgpd_filter_no_consent       → lawfulness_consent=False → 1 traitement
test_rgpd_responsible_dpo         → responsible=DPO → 1 traitement
```

#### `TestApplySort` — Tri
```
test_sort_ascending_by_name       → Ordre alphabétique ASC
test_sort_descending_by_name      → Ordre alphabétique DESC
test_sort_by_security_need_asc    → PORTAIL-RH (2) avant SAP (3)
test_sort_none_last               → Activités sans RTO en fin de liste
test_sort_none_first              → Activités sans RTO en début de liste
test_sort_does_not_modify_original → Liste originale inchangée (nouvelle liste)
```

#### `TestApplyProjection` — Projection des colonnes
```
test_project_subset_of_fields     → ["name", "type"] → 2 clés seulement
test_project_empty_returns_all    → [] → objet complet
test_project_bia_columns          → name + RTO + RPO → GESTION-PAIE correct
test_project_ciat_columns         → security_need_* → SAP ASCS correct
test_project_missing_field_returns_none → Champ absent → None (pas d'erreur)
```

---

## 6. Tests avec Mercator réel (intégration)

Ces tests appellent **la vraie API Mercator** — ils ne sont pas lancés par défaut.

```bash
# Lancer les tests d'intégration avec les credentials réels
uv run pytest -m integration -v \
  --mercator-url http://localhost:8080 \
  --mercator-login admin@admin.com \
  --mercator-password password
```

> **Note :** Les tests unitaires (Phase 1) fonctionnent sans Mercator grâce aux mocks.
> Seuls les tests marqués `integration` nécessitent une instance Mercator active.

---

## 7. Tests depuis Docker

Pour lancer les tests **à l'intérieur du container** :

```bash
# Entrer dans le container
docker exec -it mercator-reporting bash

# Lancer les tests (uv est disponible dans le container)
cd /app
uv run pytest -m phase1 -v
uv run pytest -m phase2 -v
```

> **Attention :** Les dépendances de dev (`pytest`, `pytest-mock`…) ne sont pas
> installées dans le container de production (le Dockerfile fait `uv pip install -e .`
> sans `[dev]`). Pour les tests dans Docker, installer les deps de dev d'abord :
>
> ```bash
> docker exec -it mercator-reporting uv pip install -e ".[dev]"
> uv run pytest -m phase1 -v
> ```

---

## 8. Commandes curl de test rapide (sans pytest)

Pour tester les endpoints directement depuis le terminal :

```bash
BASE="http://localhost:8000"

# --- Système ---
curl -s $BASE/health | python3 -m json.tool
curl -s $BASE/ | python3 -m json.tool

# --- Mercator ---
curl -s $BASE/api/mercator/health | python3 -m json.tool
curl -s $BASE/api/mercator/endpoints | python3 -m json.tool

# --- Endpoints (listing) ---
curl -s "$BASE/api/mercator/applications" | python3 -m json.tool
curl -s "$BASE/api/mercator/activities" | python3 -m json.tool
curl -s "$BASE/api/mercator/logical-servers" | python3 -m json.tool
curl -s "$BASE/api/mercator/data-processings" | python3 -m json.tool

# --- Filtrage ---
curl -s "$BASE/api/mercator/applications?search=SAP" | python3 -m json.tool
curl -s "$BASE/api/mercator/applications?limit=2&offset=0" | python3 -m json.tool

# --- Détail par ID ---
curl -s "$BASE/api/mercator/applications/1" | python3 -m json.tool
curl -s "$BASE/api/mercator/activities/1" | python3 -m json.tool

# --- Export JSON ---
curl -s "$BASE/api/mercator/applications/export/json" | python3 -m json.tool

# --- BIA : activités avec RTO/RPO ---
curl -s "$BASE/api/mercator/activities/export/json" \
  | python3 -c "
import json,sys
data = json.load(sys.stdin)
for a in data['data']:
    if a.get('recovery_time_objective'):
        print(f\"  {a['name']}: RTO={a['recovery_time_objective']}h, RPO={a['recovery_point_objective']}h\")
"

# --- Endpoint inconnu → doit retourner 404 ---
curl -s "$BASE/api/mercator/unknown" | python3 -m json.tool
```

---

## 9. Résolution des problèmes courants

| Erreur | Cause | Solution |
|--------|-------|---------|
| `Failed to spawn: pytest` | pytest non installé dans le venv | `uv sync` |
| `No such file or directory (os error 2)` | Même cause | `uv sync` |
| `ModuleNotFoundError: src` | Pas dans la racine du projet | `cd mercator_reporting/` |
| `Connection refused` sur `/api/mercator/health` | Mercator non démarré | Vérifier `http://localhost:8080` |
| `host.docker.internal not known` | Linux Docker Engine | Vérifier `extra_hosts` dans `docker-compose.yml` |
| `401 Unauthorized` | Mauvais credentials | Vérifier `.env` MERCATOR_LOGIN / MERCATOR_PASSWORD |
| `422 Unprocessable Entity` | Paramètre invalide (ex: limit=0) | Comportement attendu — validation FastAPI |
| `TypeError: '<' not supported` | Comparaison float vs str dans apply_sort | Vérifier la version de `filters.py` (bug corrigé) |
| `ValidationError: liste` | Opérateur `IN` avec valeur non-liste | Passer une liste : `value=["ERP", "Web"]` |

---

## 10. Résumé des commandes essentielles

```bash
# 1. Installer les dépendances (une seule fois)
uv sync

# 2. Lancer tous les tests Phase 1 (58 tests)
uv run pytest -m phase1 -v

# 3. Lancer tous les tests Phase 2 (75 tests)
uv run pytest -m phase2 -v

# 4. Lancer toutes les phases (133 tests)
uv run pytest -m "phase1 or phase2" -v

# 5. Lancer un fichier spécifique
uv run pytest tests/test_phase2_filters.py -v

# 6. Avec couverture
uv run pytest --cov=src --cov-report=term-missing

# 7. Test rapide santé API
curl http://localhost:8000/health
curl http://localhost:8000/api/mercator/health
```