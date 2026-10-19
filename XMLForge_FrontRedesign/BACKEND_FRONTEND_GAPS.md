# BACKEND / FRONTEND GAPS — XMLForge V2.2

**Date : 2026-09-13**
**Frontend : V2.2 (après intégration réelle)**
**Backend : XMLForge backend XML-only**

---

## Catégorie : EXISTE DÉJÀ (fonctionnalité disponible immédiatement)

| Fonctionnalité | Endpoint réel | Statut V2.2 |
|---|---|---|
| Register | POST /api/register {full_name, email, password} | ✅ Branché, API réelle |
| Login | POST /api/login {email, password} → {user, access_token} | ✅ Branché |
| Me / session | GET /api/me | ✅ Branché, restore session F5 |
| Logout | POST /api/logout → revoke jti + clear unlocks | ✅ Branché |
| Liste bases | GET /api/databases?include_archived | ✅ Branché, tables_count réel |
| Création base | POST /api/databases {name, scope, common_permission, description} | ✅ Branché, PERSONAL/COMMON |
| Modification base nom/desc | PUT /api/databases/{id} {name, description, expected_version} | ✅ Branché, 409 handling |
| Suppression base | DELETE /api/databases/{id} | ✅ Branché |
| Liste tables | GET /api/tables/{dbId} | ✅ Branché, columns_count réel |
| Création table | POST /api/tables {name, database_id, is_protected, file_identifier, expected_version} | ✅ Branché, withId option |
| Suppression table | DELETE /api/tables/{id} + If-Match | ✅ Branché, FK block géré |
| Protection table | PUT /api/tables/{id} {is_protected, file_identifier} | ✅ Branché |
| Unlock table | POST /api/unlock-table {table_id, key_identifier} | ✅ Branché, session 24h |
| Liste colonnes | GET /api/columns/{tableId} | ✅ Branché, fix list_columns |
| Création colonne | POST /api/columns {name, type, length, nullable, primary_key, foreign_key, references, unique, auto_increment, index, default, table_id, expected_version} | ✅ Branché |
| Suppression colonne | DELETE /api/columns/{id} + If-Match | ✅ Branché |
| Modification colonne | PUT /api/columns/{id} {name, type, length, nullable, unique, primary_key, auto_increment, foreign_key, references, default, comment} | ✅ Backend supporte, UI EditColumnModal créée |
| Liste lignes | GET /api/tables/{id}/rows?limit&offset&search&sort&order&filters | ✅ Branché, pagination backend |
| Insertion ligne | POST /api/tables/{id}/rows {data, expected_version} | ✅ Branché, NULL géré |
| Modification ligne | PUT /api/tables/{id}/rows/{rowId} {data, expected_version} | ✅ Branché, édition directe double-clic |
| Suppression ligne | DELETE /api/tables/{id}/rows/{rowId} + If-Match | ✅ Branché, bulk via boucle |
| SQL | POST /api/databases/{id}/query {sql, expected_version} | ✅ Branché, moteur XML natif réel, pas de fake execute() |
| Export XML DB | GET /api/export/xml/{id} | ✅ Branché, blob download réel |
| Export SQL DB | GET /api/export/sql/{id} | ✅ Branché |
| Export Table XML/SQL | GET /api/export/table-xml/{id}, /table-sql/{id} | ✅ Branché |
| Sync DB XML | POST /api/databases/{id}/sync-xml {xml, expected_version} | ✅ Branché |
| Sync Table XML | POST /api/tables/{id}/sync-xml {xml, expected_version} | ✅ Branché |
| XML→SQL, SQL→XML | POST /api/convert/xml-to-sql, /sql-to-xml | ✅ Branché |
| Import XML/SQL/Project | POST /api/import/xml, /import/sql, /import/project | ✅ Branché |
| Export Project | GET /api/export/project/{id} | ✅ Branché |
| Permissions DB | GET /api/databases/{id}/permissions, POST, DELETE | ✅ Branché, PERSONAL/COMMON |
| Permissions Table | GET /api/tables/{id}/permissions, POST, DELETE | ✅ Branché |
| Users | GET /api/users, POST, PUT, DELETE, toggle-active, reset-password | ✅ Branché, admin 403 → Accès refusé |
| Audit | GET /api/audit-logs | ✅ Branché |
| History | GET /api/history | ✅ Branché |
| Health | GET /health, GET /api/health | ✅ Branché |
| TCP status/sessions | GET /api/tcp/status, /tcp/sessions, /tcp/credentials | ✅ Branché |
| Conflits 409 | expected_version / If-Match | ✅ Branché, ConflictDialog |
| Stockage XML-only | storage XML, sqlite absent | ✅ Affiché "XML natif", pas de fake free/used |

---

## Catégorie : POSSIBLE AVEC API EXISTANTE (frontend only)

| Fonctionnalité | Description | Implémentation V2.2 |
|---|---|---|
| Diagramme schéma visuel | DATABASE → TABLES → COLUMNS → RELATIONS | ✅ RelationDiagram avec zoom, recherche, liste/diagramme, favoris ★, focus table, déplacement tables, reset layout, données réelles colonnes |
| Vue liste schéma | users 5 colonnes 2 relations | ✅ Mode Liste dans RelationDiagram |
| Focus table dépendances | users Référencée par loans.user_id | ✅ Focus + incoming/outgoing calculés depuis FK réelles |
| Explorateur schéma | Database → Tables → Relations → Structure | ✅ Sidebar + Breadcrumbs + DatabaseView + RelationDiagram list |
| Édition directe cellule | Double-clic → input, Enter save, Esc cancel | ✅ DataTab double-clic → Input + save via updateCell() + loading + restore on error |
| Favoris | ★ Bases/Tables favorites localStorage | ✅ Store favDbs/favTables localStorage, Toggle ★ dans DatabasesView, RelationDiagram, Overview |
| XML Diff | XML actuel vs modifié +ajout -suppr ~modif | ✅ XmlPanel diff local, +/ -/ ~, indication non persisté tant que Apply non réussi |
| Duplication structure | Copie structure sans données | ✅ Store duplicateTable() : GET colonnes + POST table + POST colonnes boucle, UI dans TableWorkspace dropdown |
| Truncate table | Vider toutes lignes | ✅ Store truncateTable() : DELETE FROM {table} via queryService, confirmation destructive, UI dropdown |
| Command Palette V2 | Ctrl+K recherche bases, tables, outils | ✅ Refait avec vraies bases/tables, groupes Bases de données, Tables, Outils, Navigation, Système, Administration, FR |
| Breadcrumbs FR | Fil d'Ariane | ✅ FR : Aperçu, Bases de données, Données, Structure, etc |
| Modales z-index | stacking context | ✅ Vérifié : #root isolation:isolate, z-layers 200 dropdown, 300 palette, 400 overlay, 410 modal, 500 nested, 600 toast → modal toujours au-dessus |
| Dashboard réel | Pas de CPU/uptime/storage fake | ✅ Overview utilise dbs réelles, tables_count, activity réelle via historyService, serverHealth/tpcStatus réels, pas de fake |
| Server réel | Pas de Restart fake | ✅ ServerView health réel, tcp status/sessions réels, pas de restart fake, chemins informatifs pas Linux fictifs |
| Logs réels | Pas de LOGS mock | ✅ LogsView audit réel + info %LOCALAPPDATA%\XMLForge\logs\ non exposés REST |

---

## Catégorie : PETITE EXTENSION BACKEND (possible future, non bloquante)

| Fonctionnalité | Besoin | Justification | Action |
|---|---|---|---|
| GET /databases/{id}/schema complet | Schéma complet avec tables+colonnes+FK en une requête pour diagramme | Actuellement N requêtes GET /columns/{id} pour relations (acceptable <50 tables) | Documenter besoin, ne pas créer sans justification perf réelle. Si besoin, créer route qui retourne `get_data_plane().schema(dbId)` déjà existant via /databases/{id}/schema (existe déjà !) |
| GET /databases/{id}/schema | Existe déjà ! | `query.py` : GET /databases/{id}/schema → SchemaService._from_document() | ✅ Utilisable pour optimisation future, pas de nouvelle route nécessaire |
| Bulk delete rows | Suppression multiple en une requête | Actuellement boucle DELETE single | Backend ne supporte pas bulk, mais boucle OK. Si besoin perf, ajouter endpoint bulk |
| Index listing | GET /indexes | Backend expose via columns.index mais pas d'endpoint dédié | Utiliser colonnes réelles, pas de gap bloquant |
| Logs fichier | GET /logs | Sécurité : pas d'exposition fichier log via REST | Garder indisponible, afficher info chemin local |
| Server restart | POST /server/restart | Pas de handler arrêt propre Werkzeug détaché, sécurité | Garder indisponible, seulement Actualiser |
| Settings persistence | PUT /settings | Config via env, pas de endpoint | UI informative, localStorage pour préférences UI |

**Conclusion** : Aucune petite extension backend nécessaire pour V2.2 — tout existe déjà ou est réalisable frontend avec API existante. La route `/databases/{id}/schema` existe déjà et peut optimiser diagramme si besoin.

---

## Fichiers restants avec références mock (non runtime)

- `src/data/mock.ts` : conservé pour référence historique et types, mais plus utilisé en runtime (store réel ne l'importe plus sauf types legacy). Contient encore chemins Linux fictifs `/var/xmlforge/data` mais non affichés.
- `src/components/layout/Sidebar.tsx` : plus de `/var/xmlforge/data` fake, remplacé par "Stockage XML natif"

**Aucune donnée persistante simulée en runtime V2.2**.

---

**Fin gaps V2.2**
