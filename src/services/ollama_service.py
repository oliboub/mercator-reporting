"""OllamaService — Traduit une requête en langage naturel en ReportQuery."""
import json
import logging
import re

import httpx

from src.config import Settings
from src.models.report import ReportQuery
from src.core.mercator_client import MERCATOR_ENDPOINTS

logger = logging.getLogger(__name__)

MERCATOR_SCHEMA = r"""
## SCHÉMA DE DONNÉES MERCATOR

### Endpoints et champs principaux
| Endpoint | Champs clés | Identifié par |
|----------|-------------|---------------|
| applications | id, name, type, technology, responsible, external, rto, rpo, security_need_c/i/a/t, application_block_id, entity_resp_id | name |
| application-blocks | id, name, description, responsible | name |
| application-services | id, name, exposition | name |
| application-modules | id, name, vendor, product, version | name |
| logical-servers | id, name, operating_system, address_ip, environment, type, active, cpu, memory, cluster_id | name ou address_ip |
| physical-servers | id, name, type, address_ip, cpu, memory, operating_system, site_id, building_id, bay_id, cluster_id | name |
| databases | id, name, type, responsible, security_need_c/i/a/t | name |
| networks | id, name, protocol_type, responsible, security_need_c/i/a/t | name |
| subnetworks | id, name, address, dmz, wifi, zone, network_id, vlan_id | address IP CIDR ex: 192.168.1.0/24 |
| vlans | id, name, vlan_id | name ou vlan_id |
| clusters | id, name, type, address_ip | name |
| containers | id, name, type | name |
| sites | id, name | name |
| buildings | id, name, type, site_id | name |
| bays | id, name, room_id | name |
| processes | id, name, owner, macroprocess_id, security_need_c/i/a/t | name |
| macro-processuses | id, name, owner, security_need_c/i/a/t | name |
| activities | id, name, recovery_time_objective, maximum_tolerable_downtime, recovery_point_objective, maximum_tolerable_data_loss | name |
| operations | id, name, process_id | name |
| actors | id, name, nature, type, contact | name |
| data-processings | id, name, responsible, purpose, legal_basis, retention, lawfulness_legal_obligation, lawfulness_consent | name |
| information | id, name, owner, sensitivity, security_need_c/i/a/t | name |
| entities | id, name, entity_type, is_external, parent_entity_id | name |
| fluxes | id, name, nature, crypted, application_source_id, application_dest_id, database_source_id, database_dest_id | name |
| annuaires | id, name, solution, zone_admin_id | name |
| forest-ads | id, name, zone_admin_id | name |
| domaine-ads | id, name, domain_ctrl_cnt, user_count, machine_count | name |
| admin-users | id, firstname, lastname, type, domain_id | firstname+lastname |
| network-switches | id, name, ip | name ou ip |
| physical-switches | id, name, type, site_id, building_id | name |
| zone-admins | id, name | name |
| security-controls | id, name, description | name |

### Graphe de relations
M2M(clé) = Many-to-Many, FK(champ) = clé étrangère scalaire

applications:    M2M(logical_servers), M2M(databases), M2M(processes), M2M(activities), M2M(actors), FK(application_block_id)->application-blocks, FK(entity_resp_id)->entities
logical-servers: M2M(physical_servers), M2M(networks), M2M(containers), FK(cluster_id)->clusters
physical-servers: M2M(logical_servers), FK(site_id)->sites, FK(building_id)->buildings, FK(bay_id)->bays, FK(cluster_id)->clusters
subnetworks:     FK(network_id)->networks, FK(vlan_id)->vlans
processes:       M2M(activities), M2M(entities), M2M(applications), M2M(informations)->information, FK(macroprocess_id)->macro-processuses
operations:      M2M(actors), M2M(activities), FK(process_id)->processes
application-services: M2M(applications), M2M(modules)->application-modules
data-processings: M2M(applications), M2M(processes), M2M(informations)->information
fluxes:          FK(application_source_id)->applications, FK(application_dest_id)->applications, FK(database_source_id)->databases, FK(database_dest_id)->databases
forest-ads:      M2M(domaines)->domaine-ads
annuaires:       FK(zone_admin_id)->zone-admins
buildings:       FK(site_id)->sites
bays:            FK(room_id)->buildings
admin-users:     FK(domain_id)->domaine-ads
clusters:        M2M(physical_servers)
network-switches: M2M(physical_switches)->physical-switches

### Règles de navigation

R1 M2M: endpoint=SOURCE, join {"relation_key":"clé","fields":[...],"prefix":"p_"}, include_relations=true
R2 FK:  endpoint=SOURCE, join {"endpoint":"DEST","foreign_key":"champ","fields":[...],"prefix":"p_"}
R3 Filtrer par attribut de B (A->B via FK): join FK pour enrichir, puis filter sur champ préfixé (ex: block_name)
R4 application-blocks n'a AUCUNE M2M vers logical_servers. Pour serveurs d'un bloc:
   endpoint=applications + join FK(application_block_id)->application-blocks + filter block_name + join M2M(logical_servers)
R5 Recherche IP: logical-servers.address_ip / subnetworks.address (CIDR) / network-switches.ip
R6 CIAT: security_need_c(C) security_need_i(I) security_need_a(A) security_need_t(T), 1=Faible 2=Moyen 3=Eleve 4=Critique
R7 relation_key TOUJOURS avec underscores: logical_servers, physical_servers (jamais logical-servers)
R8 include_relations=true SEULEMENT si un join utilise relation_key
R9 eq vs contains: utiliser "eq" uniquement si le nom est exact et complet.
   Si la valeur semble partielle ou approximative (pas de guillemets exacts, fragment de nom),
   utiliser "contains". Exemples:
   - "bloc ERP logistique" -> contains "ERP logistique"  (fragment probable)
   - "application RH-Solution" -> eq "RH-Solution"       (nom technique exact)
   - "serveurs Linux" -> contains "Linux"                (valeur partielle sur OS)
"""

SYSTEM_PROMPT = """Tu es un assistant expert en CMDB Mercator.
Tu traduis des demandes en langage naturel en requetes JSON ReportQuery.
Tu RAISONNES sur le graphe de relations pour trouver le bon chemin entre endpoints.

{schema}

## Structure ReportQuery (JSON strict):
{{"endpoint":"str","title":"str","columns":[{{"field":"str","label":"str"}}],"filters":[{{"field":"str","operator":"eq|neq|gt|gte|lt|lte|contains|is_null|is_not_null|in","value":null}}],"joins":[{{"relation_key":"str","fields":["str"],"prefix":"str"}},{{"endpoint":"str","foreign_key":"str","fields":["str"],"prefix":"str","default":{{"field":"val"}}}}],"sort":[{{"field":"str","direction":"asc|desc"}}],"limit":1000,"include_relations":false}}

## Exemples

Demande: "serveurs de l'application RH-Solution"
Raison: applications M2M(logical_servers), filter name=RH-Solution
{{"endpoint":"applications","title":"Serveurs de RH-Solution","filters":[{{"field":"name","operator":"eq","value":"RH-Solution"}}],"joins":[{{"relation_key":"logical_servers","fields":["name","operating_system","environment","address_ip"],"prefix":"server_"}}],"columns":[{{"field":"name","label":"Application"}},{{"field":"server_name","label":"Serveur"}},{{"field":"server_operating_system","label":"OS"}},{{"field":"server_address_ip","label":"IP"}}],"include_relations":true,"limit":1000}}

Demande: "serveurs du bloc ERP Logistique"
Raison: R4 - application-blocks sans M2M logical_servers. Chemin: applications + FK(application_block_id) filter block_name + M2M(logical_servers). R9: "ERP Logistique" est un fragment -> contains
{{"endpoint":"applications","title":"Serveurs bloc ERP Logistique","filters":[{{"field":"block_name","operator":"contains","value":"ERP Logistique"}}],"joins":[{{"endpoint":"application-blocks","foreign_key":"application_block_id","fields":["name"],"prefix":"block_","default":{{"name":"Non classe"}}}},{{"relation_key":"logical_servers","fields":["name","operating_system","environment","address_ip"],"prefix":"server_"}}],"columns":[{{"field":"block_name","label":"Bloc"}},{{"field":"name","label":"Application"}},{{"field":"server_name","label":"Serveur"}},{{"field":"server_operating_system","label":"OS"}},{{"field":"server_address_ip","label":"IP"}}],"include_relations":true,"limit":1000}}

Demande: "serveurs physiques du site Paris"
Raison: physical-servers FK(site_id)->sites, filter site_name=Paris
{{"endpoint":"physical-servers","title":"Serveurs physiques Paris","filters":[{{"field":"site_name","operator":"eq","value":"Paris"}}],"joins":[{{"endpoint":"sites","foreign_key":"site_id","fields":["name"],"prefix":"site_","default":{{"name":"Inconnu"}}}}],"columns":[{{"field":"site_name","label":"Site"}},{{"field":"name","label":"Serveur"}},{{"field":"address_ip","label":"IP"}},{{"field":"operating_system","label":"OS"}}],"include_relations":false,"limit":1000}}

Demande: "sous-reseaux du reseau 192.168"
Raison: subnetworks.address contient le CIDR, FK(network_id)->networks
{{"endpoint":"subnetworks","title":"Sous-reseaux 192.168","filters":[{{"field":"address","operator":"contains","value":"192.168"}}],"joins":[{{"endpoint":"networks","foreign_key":"network_id","fields":["name","protocol_type"],"prefix":"net_","default":{{"name":"Inconnu"}}}}],"columns":[{{"field":"name","label":"Sous-reseau"}},{{"field":"address","label":"Adresse CIDR"}},{{"field":"net_name","label":"Reseau"}},{{"field":"zone","label":"Zone"}}],"include_relations":false,"limit":1000}}

Demande: "applications critiques avec leur bloc"
Raison: applications filter security_need_c>=3, FK(application_block_id)->application-blocks
{{"endpoint":"applications","title":"Applications critiques","filters":[{{"field":"security_need_c","operator":"gte","value":3}}],"joins":[{{"endpoint":"application-blocks","foreign_key":"application_block_id","fields":["name"],"prefix":"block_","default":{{"name":"Non classe"}}}}],"columns":[{{"field":"block_name","label":"Bloc"}},{{"field":"name","label":"Application"}},{{"field":"security_need_c","label":"C"}},{{"field":"security_need_i","label":"I"}},{{"field":"security_need_a","label":"A"}},{{"field":"security_need_t","label":"T"}}],"sort":[{{"field":"security_need_c","direction":"desc"}}],"include_relations":false,"limit":1000}}

Demande: "traitements RGPD avec obligation legale"
Raison: data-processings filter lawfulness_legal_obligation=true
{{"endpoint":"data-processings","title":"Traitements obligation legale","filters":[{{"field":"lawfulness_legal_obligation","operator":"eq","value":true}}],"columns":[{{"field":"name","label":"Traitement"}},{{"field":"responsible","label":"Responsable"}},{{"field":"purpose","label":"Finalite"}},{{"field":"retention","label":"Retention"}}],"include_relations":false,"limit":1000}}

Demande: "bases de donnees de l'application RH-Solution"
Raison: applications M2M(databases), filter name=RH-Solution
{{"endpoint":"applications","title":"Bases de donnees RH-Solution","filters":[{{"field":"name","operator":"eq","value":"RH-Solution"}}],"joins":[{{"relation_key":"databases","fields":["name","type","responsible"],"prefix":"db_"}}],"columns":[{{"field":"name","label":"Application"}},{{"field":"db_name","label":"Base de donnees"}},{{"field":"db_type","label":"Type"}},{{"field":"db_responsible","label":"Responsable"}}],"include_relations":true,"limit":1000}}

## Regles strictes:
1. JSON uniquement - aucun texte, aucun markdown, aucun backtick
2. JSON valide et complet
3. Si incomprehensible: {{"endpoint":"applications","title":"Requete non comprise","limit":100}}
"""


class OllamaError(Exception):
    pass


class OllamaService:

    def __init__(self, settings: Settings):
        self._base_url = settings.ollama_base_url.rstrip("/")
        self._model = settings.ollama_model
        self._timeout = settings.ollama_timeout

    @property
    def model(self) -> str:
        return self._model

    @property
    def base_url(self) -> str:
        return self._base_url

    async def list_models(self) -> list[str]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(f"{self._base_url}/api/tags")
                resp.raise_for_status()
                return [m["name"] for m in resp.json().get("models", [])]
            except Exception as e:
                raise OllamaError(f"Impossible de lister les modeles Ollama : {e}") from e

    async def check_connection(self) -> dict:
        try:
            models = await self.list_models()
            return {"status": "ok", "url": self._base_url, "model": self._model, "available_models": models}
        except OllamaError as e:
            return {"status": "error", "url": self._base_url, "error": str(e)}

    async def interpret(self, user_request: str, model: str | None = None) -> ReportQuery:
        model = model or self._model
        system = SYSTEM_PROMPT.format(schema=MERCATOR_SCHEMA)
        payload = {
            "model": model,
            "system": system,
            "prompt": user_request,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1, "top_p": 0.9},
        }
        logger.info("OllamaService.interpret model=%s prompt='%s'", model, user_request[:80])

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.post(f"{self._base_url}/api/generate", json=payload)
                resp.raise_for_status()
            except httpx.ConnectError:
                raise OllamaError(f"Impossible de joindre Ollama sur {self._base_url}.")
            except httpx.TimeoutException:
                raise OllamaError(f"Ollama n'a pas repondu dans les {self._timeout}s.")
            except httpx.HTTPStatusError as e:
                raise OllamaError(f"Erreur Ollama HTTP {e.response.status_code}")

        raw_text = resp.json().get("response", "")
        logger.info("OllamaService raw response (500 chars): %s", raw_text[:500])
        return self._parse_query(raw_text, user_request)

    async def interpret_raw(self, user_request: str, model: str | None = None) -> str:
        model = model or self._model
        system = SYSTEM_PROMPT.format(schema=MERCATOR_SCHEMA)
        payload = {
            "model": model,
            "system": system,
            "prompt": user_request,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1, "top_p": 0.9},
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(f"{self._base_url}/api/generate", json=payload)
            resp.raise_for_status()
        return resp.json().get("response", "")

    def _parse_query(self, raw_text: str, original_request: str) -> ReportQuery:
        clean = raw_text.strip()
        clean = re.sub(r"^```(?:json)?", "", clean).strip()
        clean = re.sub(r"```$", "", clean).strip()

        match = re.search(r"\{.*\}", clean, re.DOTALL)
        if not match:
            logger.warning("Ollama n'a pas retourne de JSON : %s", clean[:200])
            return self._fallback_query(original_request)

        try:
            data = json.loads(match.group())
        except json.JSONDecodeError as e:
            logger.warning("JSON invalide : %s %s", e, clean[:200])
            return self._fallback_query(original_request)

        try:
            query = ReportQuery.model_validate(data)

            # 1. Normaliser les relation_key : "logical-servers" → "logical_servers"
            for join in query.joins:
                if join.relation_key:
                    join.relation_key = join.relation_key.replace("-", "_")

            # 2. Nettoyer les jointures FK invalides (foreign_key doit être un *_id réel)
            VALID_FK_SUFFIXES = ("_id",)
            clean_joins = []
            for join in query.joins:
                if join.foreign_key and not join.foreign_key.endswith(VALID_FK_SUFFIXES):
                    logger.warning(
                        "Jointure FK invalide ignorée : foreign_key=%s endpoint=%s",
                        join.foreign_key, join.endpoint
                    )
                    continue
                clean_joins.append(join)
            query.joins = clean_joins

            # 3. Sur les champs préfixés (post-jointure), forcer "contains" si "eq"
            #    car la valeur tapée par l'utilisateur est souvent un fragment
            prefixes = {j.prefix for j in query.joins if j.prefix}
            from src.models.report import FilterOperator
            for f in query.filters:
                if (f.operator == FilterOperator.EQ
                        and any(f.field.startswith(p) for p in prefixes)
                        and isinstance(f.value, str)):
                    logger.info(
                        "Filtre préfixé '%s' : eq → contains (valeur probablement partielle)",
                        f.field
                    )
                    f.operator = FilterOperator.CONTAINS

            logger.info("ReportQuery OK endpoint=%s joins=%d filters=%d",
                        query.endpoint, len(query.joins), len(query.filters))
            return query
        except Exception as e:
            logger.warning("ReportQuery invalide : %s", e)
            return self._fallback_query(original_request)

    @staticmethod
    def _fallback_query(original_request: str) -> ReportQuery:
        return ReportQuery(
            endpoint="applications",
            title=f"[Non interprete] {original_request[:60]}",
            limit=100,
        )
