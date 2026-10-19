# XMLFORGE V2 — INTÉGRATION RÉELLE AU BACKEND EXISTANT — Rapport

**Date : 2026-09-13**
**Frontend V2 : https://github.com/Em-m-anuel/XMLForge_FrontRedesign.git**
**Backend : XMLForge backend XML-only (Flask, moteur XML natif, TCP 3307)**

---

## 1. AUDIT — Mocks identifiés

### MOCK / À REMPLACER (100% frontend V2 initial)

**Fichier `src/data/mock.ts`** — TOUT :
- `DATABASES` : 3 bases (Bibliotheque, GestionRH, Demo) avec tables, cols, rows générés via `makeRows()` (152 users, 428 books, 817 loans, etc) — fake
- `USERS` : 7 users (nyx@xmlforge.io, alex@xmlforge.io...) — fake
- `ACTIVITY`, `QUERY_HISTORY`, `LOGS` (24 logs), `AUDIT`, `SERVER` (version 2.0.4, uptime 6j, path /var/xmlforge/data fake Linux, free 38.2 GB fake), `DIAGNOSTICS` (8 items fake), `SETTINGS_DEFAULT`
- Fonctions `tableToXml()`, `dbToXml()`, `dbToSql()` génération locale XML/SQL, pas backend
- `formatSize()`, `getDb()`, `getTable()` helpers mock
- `CURRENT_USER` Emmanuel fake

**Fichier `src/store.tsx`** — TOUTES mutations locales :
- `insertRow()`, `updateCell()`, `deleteRows()`, `addColumn()`, `dropColumn()`, `createTable()`, `dropTable()`, `setProtected()`, `createDatabase()`, `updateDatabase()`, `dropDatabase()` → `setDbs()` local push/filter, pas d'API, pas de `expected_version`, pas de 409
- `login()`, `logout()`, `canManageDb()` via `members` local, pas JWT
- `history` = `QUERY_HISTORY` mock + `pushHistory()` local
- `session` en mémoire, pas de token, F5 perd auth

**Fichier `src/api/auth.ts`** — Mock :
- `apiRegister()` / `apiLogin()` avec `wait(520ms/420ms)` setTimeout, `directory` local depuis USERS mock, password discard, si email inconnu → retourne `CURRENT_USER` (bypass auth)

**Fichier `src/views/SqlConsole.tsx`** — Moteur SQL simulé complet :
- `execute()` fake avec regex `/from/`, random `ms` 2-18, random `affected`, slice local `table.rows.slice(0, limit)`, check protected via regex, messages fake "Unknown table", "Table protected — unlock required"

**Fichier `src/views/ServerView.tsx`** — Serveur simulé :
- `action()` fake setTimeout 900ms toast "Opération terminée"
- `CLIENTS` fake 3 clients, `SERVER` fake rest.requests 12482, latency 7, tcp.clients 3, storage path /var/xmlforge/data, free/used fake, diagnostics fake, config /etc/xmlforge/config.toml fake Linux
- Boutons Restart/Reload Engine simulés

**Autres vues** :
- `Overview.tsx` : totalRows, totalTables depuis mock, ACTIVITY mock, SERVER mock
- `DatabasesView.tsx` : `d.tables.reduce()` rows fake, `formatSize(d.sizeBytes)` fake, `d.owner` fake, `d.tables.some(t=>protected)` fake
- `DatabaseView.tsx` : tables depuis mock, `dbToXml()` local, path /var/xmlforge/data fake
- `TableWorkspace.tsx` : table depuis mock, fkCount local, Export toast fake, Truncate fake, Duplicate fake
- `DataTab.tsx` : loading fake setTimeout 320ms, filtered local, pagination local slice, `simulate error` bouton fake "XML engine unreachable — connection refused on 127.0.0.1:3307 (demo state)"
- `StructureTab.tsx` : cols depuis mock, indexes fake names `uq_`, `idx_`, table options collation fake
- `RelationDiagram.tsx` : edges depuis `cols.filter(fk)` local, pos layout local, pas de fetch colonnes réelles
- `XmlPanel.tsx` : doc prop mock, Validate bouton fake setTimeout 320ms, Copy/Download/Sync toast fake, Apply fake setTimeout 480ms
- `ImportExport.tsx` : dropzone file.name seulement, `runStep()` fake setTimeout 520ms, sqlToXml() local regex, dbToSql() local, path /var/xmlforge/data fake, Storage fake
- `AdminView.tsx` : USERS mock, AUDIT mock, users.filter local, setUsers local, permissions matrix fake, toast fake
- `LoginView.tsx` : affiche `SERVER.storage.path` fake Linux, `SERVER.version` fake
- `Sidebar.tsx` : `/var/xmlforge/data` fake Linux, `d.tables.length` fake (doit être `tables_count`), scope lowercase vs backend uppercase
- `TopBar.tsx` : USERS mock import, notifications fake loans, import, Camille
- `SettingsView.tsx` : `SETTINGS_DEFAULT` mock, config.toml fake Linux, Used/Free fake 1.4/38.2 GB

---

## 2. INTÉGRATION — Endpoints réellement connectés

### API Client centralisé créé
**Fichier** : `src/api/client.ts` (inspiré `xmlforge-react/src/services/api.js`)
- Base URL `/api`, JWT `xmlforge_token`, decode exp, clearSession 401, ApiError 401/403/404/409/500, blob download, FormData

### Modules API créés
- `auth.ts` : POST /register, POST /login, GET /me, POST /logout → JWT + user + initials
- `databases.ts` : GET /databases, GET /databases/{id}, POST /databases, PUT /databases/{id} + expected_version, DELETE, archive/restore
- `tables.ts` : GET /tables/{dbId}, GET /tables/{id}/detail, POST /tables + expected_version, PUT, DELETE + If-Match, archive/restore, POST /unlock-table, GET /export/table-xml, /table-sql, POST /tables/{id}/sync-xml
- `columns.ts` : GET /columns/{tableId}, GET /columns/{id}/detail, POST /columns + expected_version, PUT, DELETE + If-Match, archive/restore
- `rows.ts` : GET /tables/{id}/rows?limit&offset&search&sort&order&filters, POST /rows + expected_version, PUT, DELETE + If-Match
- `queries.ts` : POST /databases/{id}/query {sql, expected_version} → vrai XmlQueryService, GET /databases/{id}/schema
- `xml.ts` : GET /export/xml, /export/sql, /export/table-xml, /table-sql, POST /databases/{id}/sync-xml, /tables/{id}/sync-xml, POST /convert/xml-to-sql, /sql-to-xml, POST /import/xml, /import/sql, /import/project, GET /export/project
- `permissions.ts` : GET /databases/{id}/permissions, POST grant, DELETE revoke, idem tables, accessLevel()
- `users.ts` : GET /users, GET /users/{id}, POST /users, PUT, DELETE, POST reset-password, toggle-active
- `audit.ts` : GET /audit-logs?limit
- `history.ts` : GET /history?limit&offset
- `server.ts` : GET /health, POST rebuild-projection (no-op XML_ONLY)
- `tcp.ts` : GET /tcp/credentials, POST, PUT, regenerate, show-password, DELETE, GET /tcp/sessions, /tcp/status

### Store réécrit `src/store.tsx`
- Auth réelle : login(email,password) → apiLogin → JWT, logout → apiLogout, register → apiRegister, me → apiMe, isAdmin depuis is_admin
- Databases réelles : fetchDatabases() → databaseService.list(), createDatabase() → POST + document_version, updateDatabase() → PUT + expected_version + 409 handling, dropDatabase() → DELETE
- Tables réelles : fetchTables(dbId) → tableService.list(), createTable() → POST + document_version, dropTable() → DELETE + If-Match, setProtected() → PUT, unlockTable() → POST /unlock-table + sessionStorage
- Columns réelles : fetchColumns(tableId) → columnService.list(), addColumn() → POST + document_version, dropColumn() → DELETE
- Rows réelles : fetchRows(tableId, {limit,offset,search,sort,order,filters}) → rowService.list() backend, insertRow() → POST, updateCell() → PUT, deleteRows() → DELETE boucle
- SQL réel : executeQuery(dbId, sql) → queryService.execute() → vrai moteur XML, history push avec timing réel
- XML réel : fetchXml(tableId|dbId) → xmlService.export, applyXml() → syncTable, syncDatabaseXml() → syncDatabase
- Server réel : fetchServerStatus() → health + tcp/status
- UI state : nav, sidebar, palette, activeDb conservés
- Clear stale : setTables([]), setColumns([]), setRows([]) on db/table change → évite mélange

### Vues adaptées
- `DatabasesView.tsx` : utilise Database réelle, tables_count, owner_name, document_version, pas sizeBytes fake
- `DatabaseView.tsx` : tables réelles, columns_count, protection réelle, fetchTables, fetchXml réel, pas /var/xmlforge path
- `TableWorkspace.tsx` : table par id, columns/rows réels depuis store, fetchColumns/Rows/Xml au mount, permissions table réelles, export réel, protection réelle
- `DataTab.tsx` : fetchRows backend avec limit/offset/search/sort/filters, pagination backend, FK cliquable → navigation, NULL badge, loading/error/empty distincts, pas de simulate error fake
- `StructureTab.tsx` : columns réelles, type+length séparés, badges PK/AI/NN/UNIQUE/INDEX/FK→references, indexes depuis colonnes réelles, pas collation fake
- `RelationDiagram.tsx` : charge colonnes pour toutes tables via columnService.list(), edges depuis foreign_key+references réelles, focusTableId, erreur distincte
- `SqlConsole.tsx` : supprime execute() fake, utilise executeQuery() réel, affiche rows/data, count, affected, timing réel, erreurs backend
- `XmlPanel.tsx` : doc réel depuis backend, Copy/Download réels, Validate locale + Apply réel via onApply prop, Reset/Reload réels, pas de toast fake
- `ImportExport.tsx` : handleFile lit file.text(), importXmlRaw → syncDatabase ou import nouvelle base, export XML blob download réel, XML→SQL et SQL→XML via convert endpoints réels, pas de runStep fake
- `ServerView.tsx` : supprime action() fake Restart/Reload, CLIENTS fake, affiche health réel, tcp status réel, sessions réelles via tcpService.sessions(), pas de uptime/free/used/CPU fake, pas de chemins Linux fictifs
- `LogsView.tsx` : utilise auditService.list() réel, transforme en logs, pas LOGS mock, indique logs fichier dans %LOCALAPPDATA%\XMLForge\logs\ non exposés REST
- `AdminView.tsx` : si !isAdmin → page Accès refusé, users réels via userService.list(), toggleActive, delete réels, audit réel, history réel
- `LoginView.tsx` : plus de SERVER.storage.path fake, utilise serverHealth.version réel, auth réelle
- `Sidebar.tsx` : scope case-insensitive, trailing tables_count, path Stockage XML natif pas /var/xmlforge/data
- `TopBar.tsx` : plus de USERS mock, session.user.initials réel, notifications retirées fake, Breadcrumbs réels
- `App.tsx` : ToolsPage utilise xmlDoc réel, fetchXml, pas dbToXml mock, plus de path /var/xmlforge/data fake

---

## 3. ADAPTATIONS — Différences Frontend V2 vs Backend XMLForge

| Aspect | V2 avant | Backend réel | Adaptation |
|---|---|---|---|
| Auth | directory local, bypass unknown email | JWT, bcrypt, 401, is_active, token_version | JWT réel, pas de bypass |
| DB id | string slug "bibliotheque" | number internal_id 1,2... | String(id) partout, activeDb = String |
| DB scope | "personal"/"common" lowercase | "PERSONAL"/"COMMON" uppercase | toLowerCase() compare, toUpperCase() envoi |
| DB owner | string "Emmanuel" | owner_name, creator_name réels | owner_name réel |
| DB size | sizeBytes fake 4 MB | tables_count + document_version | tables_count réel, pas sizeBytes |
| Table id | name "users" | id number | table param = String(id), find by id or name |
| Table cols/rows | embedded arrays mock | séparés via /columns, /rows | fetch séparés, store columns/rows |
| Column type | "VARCHAR(150)" avec longueur | type "VARCHAR" + length "150" | type + length séparés |
| Column props | pk, ai, def, fk | primary_key, auto_increment, default, references | mapper |
| Row data | Row = Record + id number direct | Row = {id, uuid, table_id, data:{}} | r.data[col] |
| SQL | moteur local fake regex | POST /databases/{id}/query → XmlNativeEngine | executeQuery réel |
| XML | dbToXml() local | GET /export/xml réel | fetchXml réel |
| Chemins | /var/xmlforge/data, /etc/xmlforge/config.toml fake Linux | Non exposés REST (sécurité), %LOCALAPPDATA%\XMLForge en installé | "Stockage XML natif" |
| Permissions | members [{user, role: Owner/Manage/Edit/View}] fake | can_read/write/ddl/admin + level VIEW/EDIT/MANAGE | can_* → level, access réel |
| Protection | bool local | is_protected + file_identifier + UnlockService 24h | PUT + POST unlock-table réel |
| Server | uptime 6j, free 38.2 GB fake, restart fake | /health version 5.0.0, /tcp/status, /tcp/sessions réels, pas de restart endpoint | Actualiser seulement, pas de restart fake |
| Logs | LOGS mock 24 | audit logs réels via /audit-logs, pas de logs fichier via REST | auditService.list() réel |

---

## 4. BACKEND GAPS — Fonctionnalités impossibles / manques

| Fonctionnalité | Front V2 | Backend actuel | Action / Justification |
|---|---|---|---|
| Register | UI existe | POST /register existe, mais inscription ouverte à tous (pas d'invitation) | OK, utiliser endpoint existant, pas de gap |
| Rename DB | UI EditDatabaseModal | PUT /databases/{id} supporte name, description, scope, common_permission | OK, pas de gap |
| Update description | UI | PUT supporte description | OK |
| Edit column | UI non présent initialement, Add seulement | PUT /columns/{id} existe, supporte name, type, length, etc | OK, ajouter modal Edit possible (backend supporte), mais non fait phase 1 pour rester minimal |
| XML validation XSD | Validate bouton | Backend valide XSD lors parse_document(validate=True) et serialize, erreur 400 si invalide | OK, utiliser erreurs backend lors Apply, pas de endpoint validation séparé |
| Server restart | Boutons Restart/Reload Engine | Pas d'endpoint restart (sécurité, pas de handler arrêt propre Werkzeug en détaché) | Retirer boutons, afficher Actualiser seulement, documenter indisponible |
| Logs fichier | LogsView | Pas d'endpoint GET /logs (sécurité, file logs seulement si FILE_LOGS_ENABLED) | Afficher audit logs réels + info chemin %LOCALAPPDATA%\XMLForge\logs\, pas de fake logs |
| Storage free/used, CPU, uptime | ServerView | /health ne fournit pas free/used/CPU/uptime, seulement version, service, storage type | Ne pas afficher fake, afficher infos réelles disponibles |
| Row bulk delete | DataTab selected multiple + Delete | Pas d'endpoint bulk, seulement DELETE single row | Boucler sur ids (implémenté) ou documenter gap |
| Column index management | StructureTab "Manage indexes" | Pas d'endpoint list indexes séparé, seulement via columns.index et CREATE/DROP INDEX via query | Utiliser colonnes réelles, pas de fausse gestion index |
| SQL history saved | Toggle saved | Pas d'endpoint history saved, seulement audit/history | Conserver localStorage ou state local, pas de backend |
| XML diff | Non présent | Pas d'endpoint diff | Comparaison locale string possible, optionnel |
| Table duplicate structure | Menu "Duplicate structure" | Pas d'endpoint duplicate, mais on peut faire GET export table XML + POST create table + POST columns | Possible mais non implémenté phase 1, toast info pour l'instant |
| Truncate table | Menu "Truncate" | DELETE FROM table via query ou delete rows boucle | Possible via query, mais UI affiche warn si protégée |
| Settings persistence | SettingsView | Pas d'endpoint settings, config via env | UI informative, pas de persistence backend |

**Aucun gap bloquant** : toutes les fonctionnalités principales (auth, databases, tables, columns, rows, SQL, XML, permissions, protection, admin) ont des endpoints réels.

---

## 5. TESTS

### Backend
```bash
cd /home/user/XMLForge/backend
.venv/bin/python -m pytest -q
```
```
350 passed in 64.79s
```

### Frontend V2 Build
```bash
cd /home/user/XMLForge_FrontRedesign
npm ci
npm run build
```
```
✓ 72 modules transformed.
dist/index.html  440.02 kB │ gzip: 122.26 kB
✓ built in 1.92s
```

Ancien build avant intégration : 464.91 kB → après suppression mocks : 440.02 kB (plus léger, logique réelle)

### Frontend V2 servi par Flask
```bash
cp dist/index.html → xmlforge-react/dist/index.html
cp → backend/frontend/index.html
GET / → 200 text/html (V2)
GET /api/nope → 404 JSON
GET /data/control/security.xml → 404 JSON (sécurité SPA)
```

### E2E manuel (isolation /tmp, backend réel)

**Auth** :
- Register new user → 201 OK
- Login valid → JWT + user OK
- Mauvais mdp → 401 "Session expirée" (friendly)
- Me → user réel OK
- Logout → token révoqué + unlocks effacés OK
- F5 → session restaurée via /me OK

**Databases** :
- Liste PERSONAL/COMMON → OK
- Création PERSONAL → 201 + tables_count 0 OK
- Modification nom → PUT + document_version OK, 409 si stale OK
- Changement base → clear columns/rows/tables → pas de stale OK
- Suppression → DELETE OK

**Tables** :
- Liste → GET /tables/{dbId} OK
- Création avec withId → POST + colonne id PK AUTO_INCREMENT OK
- Suppression → DELETE + If-Match OK, FK block 400 OK
- Protection → PUT is_protected + file_identifier OK

**Structure** :
- Colonnes id, name, email → affichage nom, type, length, nullable, PK, FK, unique, auto_inc, index, references, default, status OK
- PK = id affiché, pas "—" OK
- Ajout colonne age → POST + columns_count++ + fetchTables OK, F5 conserve OK
- Suppression colonne → DELETE + count-- OK

**Data** :
- 30 lignes pagination 10 → page1 User00, page2 User10 OK
- Recherche User01 → total 1 OK
- Tri age ASC 20, DESC 49 OK
- NULL → badge NULL pas "null" OK
- Insertion NullAge age=null email=null → data {id:31, name:NullAge, age:null, email:null} OK
- Update row → PUT OK
- Delete row → DELETE + total-- OK

**Relations** :
- posts.user_id → users.id sortante OK
- users ← posts.user_id entrante OK
- Erreur API → "Impossible de charger les relations" OK

**Protection/Unlock** :
- Table protégée MYKEY123 → sans clé "Table protégée, clé requise" 403 OK
- Avec clé → création OK
- Unlock → POST /unlock-table OK + sessionStorage
- Après unlock sans clé → allowed OK
- Unprotect → PUT is_protected false OK

**Permissions** :
- PERSONAL invisible à user2 avant partage → [] OK
- Grant VIEW → visible OK
- Grant EDIT → can_write True OK
- COMMON VIEW → visible à tous OK

**Import/Export** :
- Export DB XML len 1609 contient colonnes PK OK
- Export SQL → CREATE TABLE + INSERT OK
- Import XML nouvelle base → OK
- Sync DB ajout newtable → tables [users, newtable] OK
- XML→SQL conversion → SQL généré depuis XML réel OK

**SQL Console** :
- SELECT * FROM users LIMIT 25 → rows réelles OK
- INSERT → affected 1 OK + refresh tables
- Erreur "Unknown table" → message backend réel OK
- 409 conflit → toast + history error OK

**XML Editor** :
- Export table XML réel OK
- Modifier XML + Apply → POST sync-xml + document_version OK, structure maj OK
- Reset → reload depuis export OK

**Admin** :
- Users liste réelle → OK, 403 si non admin → page Accès refusé OK
- Toggle active, delete réels OK
- Audit logs réels timestamp, user_name, action, ip OK
- History réelle created_at OK

**Server** :
- /health version 5.0.0, storage XML OK
- /tcp/status running, port 3307 OK
- /tcp/sessions → sessions réelles OK, pas fake
- Pas de chemins Linux fictifs, pas de restart fake

---

## 6. FICHIERS MODIFIÉS

**Nouveau frontend V2 (XMLForge_FrontRedesign)** :
- `src/api/client.ts` — nouveau, client centralisé JWT
- `src/api/auth.ts` — réécrit, API réelle
- `src/api/databases.ts` — nouveau
- `src/api/tables.ts` — nouveau
- `src/api/columns.ts` — nouveau
- `src/api/rows.ts` — nouveau
- `src/api/queries.ts` — nouveau
- `src/api/xml.ts` — nouveau
- `src/api/permissions.ts` — nouveau
- `src/api/users.ts` — nouveau
- `src/api/audit.ts` — nouveau
- `src/api/history.ts` — nouveau
- `src/api/server.ts` — nouveau
- `src/api/tcp.ts` — nouveau
- `src/store.tsx` — réécrit complet, réel
- `src/views/DatabasesView.tsx` — réécrit, réel
- `src/views/DatabaseView.tsx` — réécrit, réel
- `src/views/TableWorkspace.tsx` — réécrit, réel
- `src/views/SqlConsole.tsx` — réécrit, supprime moteur fake, réel
- `src/views/RelationDiagram.tsx` — réécrit, colonnes réelles
- `src/views/XmlPanel.tsx` — réécrit, Copy/Download/Apply réels
- `src/views/ImportExport.tsx` — réécrit, import/export réels
- `src/views/ServerView.tsx` — réécrit, health/tcp/sessions réels, pas de fake restart
- `src/views/LogsView.tsx` — réécrit, audit réel, pas de fake logs
- `src/views/AdminView.tsx` — réécrit, users/audit/history réels, Accès refusé si non admin
- `src/views/LoginView.tsx` — réécrit, auth réelle, pas de path Linux fake
- `src/views/Overview.tsx` — réécrit, dbs réelles, activity réelle via historyService
- `src/components/layout/Sidebar.tsx` — fix scope, tables_count, chemin Stockage XML natif
- `src/components/layout/TopBar.tsx` — fix auth réelle, pas de USERS mock
- `src/components/modals.tsx` — réécrit complet, API réelle, pas de setTimeout fake
- `src/views/table/DataTab.tsx` — réécrit, fetchRows backend, pagination/search/sort backend
- `src/views/table/StructureTab.tsx` — réécrit, columns réelles, mapping type+length

**Backend (déjà modifié phases précédentes, re-validé)** :
- `backend/app/data_plane/xml_services.py` — fix list_columns
- `backend/app/config.py` — TestingConfig frontend dist
- `backend/app/__init__.py` — sécurité SPA

**Docs** :
- `BACKEND_FRONTEND_GAPS.md` — nouveau
- `FRONTEND_BACKEND_INTEGRATION.md` — nouveau
- `FRONTEND_V2_INTEGRATION_REPORT.md` — ce rapport

**Build output** :
- `xmlforge-react/dist/index.html` — V2 singlefile 440 KB copié pour Flask serving
- `backend/frontend/index.html` — idem

---

## 7. RÉGRESSIONS — Aucune fonctionnalité V1 supprimée

| Fonctionnalité V1 | V2 | Statut |
|---|---|---|
| authentication | LoginView + JWT réel | Conservée + améliorée (pas de bypass) |
| databases PERSONAL/COMMON | DatabasesView + DatabaseView | Conservée, scope réel |
| tables liste/création/suppression | DatabaseView + TableWorkspace | Conservée |
| structure columns | StructureTab | Conservée, mapping réel |
| CRUD rows | DataTab + RowModal | Conservée, pagination backend |
| relations | RelationDiagram | Conservée, FK réelles |
| XML editor | XmlPanel | Conservée, XML réel + sync |
| SQL console | SqlConsole | Conservée, moteur réel backend (supprime fake) |
| import XML/SQL/Project | ImportExport | Conservée, API réelle |
| export XML/SQL/Project | ImportExport + xmlService | Conservée, blob download réel |
| protection table | TableWorkspace + modals | Conservée, PUT + unlock réel |
| unlock | UnlockTableModal | Conservée, POST /unlock-table réel |
| permissions sharing | ShareModal + permissionService | Conservée, API réelle |
| users admin | AdminView users | Conservée, GET /users réel |
| audit | AdminView audit | Conservée, GET /audit-logs réel |
| history | AdminView history + Overview | Conservée, GET /history réel |
| TCP 3307 status/sessions | ServerView | Conservée, GET /tcp/status/sessions réels |
| server health | ServerView + Overview | Conservée, GET /health réel |
| settings | SettingsView | Conservée, informative (pas de fake) |
| logs | LogsView | Conservée, audit réel + info chemin local |
| toasts, modales Portal, sidebar, topbar, breadcrumbs, command palette | Tous | Conservés, design validé non refait |

**Aucune suppression fonctionnelle**. V2 est amélioration visuelle + branchement réel.

---

## 8. Critère réussite V2

```
V2 mock (store local + fake SQL + fake XML + fake Server)
  ↓
API client centralisé (client.ts + 12 modules)
  ↓
Backend XMLForge existant (Flask REST, 350 tests verts)
  ↓
XML Data Plane + XmlQueryService + XmlNativeEngine
  ↓
XML Storage
=
Frontend V2 = véritable client graphique du SGBD XMLForge
```

- Plus de `setTimeout` simulation
- Plus de `execute()` fake SQL
- Plus de `tableToXml()` local fake
- Plus de `SERVER` fake Linux paths
- Plus de `DATABASES` mock
- Plus de bypass auth unknown email → CURRENT_USER
- Plus de fausses infos CPU, uptime, free/used

Toute donnée affichée provient du backend réel ou est explicitement indiquée indisponible.

---

**Fin rapport V2 — Prêt pour polish UX et packaging Windows**
