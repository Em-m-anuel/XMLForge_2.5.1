# FRONTEND / BACKEND INTEGRATION — XMLForge V2

**Date : 2026-09-13**
**Frontend : https://github.com/Em-m-anuel/XMLForge_FrontRedesign.git (V2 redesign)**
**Backend : /home/user/XMLForge/backend (XML-only, moteur XML natif)**

---

## 1. Base URL & Client centralisé

**Fichier** : `src/api/client.ts`

- Base URL : `import.meta.env.VITE_API_URL || '/api'` → `/api` par défaut (même origine, Flask sert frontend en prod)
- JWT : `localStorage.getItem('xmlforge_token')` → header `Authorization: Bearer <token>`
- Expiration : décodage payload `exp`, si expiré → `clearSession('expired')` + event `xmlforge:unauthorized`
- 401 → clear session + redirect login
- Erreurs : `ApiError` avec `status`, `code`, `details`, `isConflict` (409)
- Blob download : `apiClient.download(path, filename)` pour exports XML/SQL
- FormData support pour imports
- Friendly messages FR pour 401/403/404/409/400/500

```ts
export const apiClient = {
  get, post, put, delete, blob, download, getToken, isTokenExpired, clearSession, apiUrl
}
```

---

## 2. Authentification réelle

**Fichier** : `src/api/auth.ts`

| Opération | Endpoint réel | Payload | Réponse |
|---|---|---|---|
| Register | POST /api/register | {full_name, email, password} | 201 {data: user.to_dict()} |
| Login | POST /api/login | {email, password} | 200 {data: {user, access_token}} |
| Me | GET /api/me | JWT | 200 {data: user.to_dict()} |
| Logout | POST /api/logout | JWT | 200 + revoke jti + clear unlocks |

- Stockage : `xmlforge_token` (JWT), `xmlforge_user` (user + initials)
- Session persistante : au mount, si token présent → `apiMe()` → restaure session
- Logout : efface token, user, unlocks (sessionStorage)
- Pas de bypass demo : unknown email → 401, pas CURRENT_USER

**Store** : `src/store.tsx` gère `session: {user, authenticated}`, `login(email,password)`, `logout()`, `register()`, `isAdmin`

---

## 3. Bases de données

**Fichier** : `src/api/databases.ts`

| Opération | Endpoint | Réponse |
|---|---|---|
| Liste | GET /api/databases?include_archived | [DatabaseView + access + is_owner] |
| Détail | GET /api/databases/{id} | DatabaseView |
| Création | POST /api/databases {name, description, scope, common_permission} | 201 Database |
| Modification | PUT /api/databases/{id} {name, description, expected_version} | 200 Database, 409 conflit |
| Suppression | DELETE /api/databases/{id} | 200 |
| Archive/Restore | POST /api/databases/{id}/archive/restore | Database |

**Modèle Database** (backend `DatabaseView.to_dict()` + `access`) :
```ts
id, uuid, name, description, creator_id, creator_name, owner_id, owner_name,
scope: PERSONAL|COMMON, common_permission: VIEW|EDIT|MANAGE|null,
document_version, sync_status, created_at, updated_at, comment, status,
tables_count, key_identifier?, access: {can_read, can_write, can_ddl, can_admin, level}
```

- UI `DatabasesView.tsx` : utilise `tables_count`, `owner_name`, `document_version`, `status`, pas de `sizeBytes` fake ni `/var/xmlforge` path
- Modification base : utilise `document_version` comme `expected_version` → gère 409
- PERSONAL/COMMON : affiche badges réels, COMMON visible à tous si VIEW (backend `accessible_databases`)

---

## 4. Tables

**Fichier** : `src/api/tables.ts`

| Opération | Endpoint | Réponse |
|---|---|---|
| Liste par base | GET /api/tables/{database_id}?include_archived | [TableView + access] |
| Détail | GET /api/tables/{id}/detail | TableView |
| Création | POST /api/tables {name, database_id, is_protected, file_identifier, description, expected_version} | 201 Table |
| Modification | PUT /api/tables/{id} {name, description, is_protected, file_identifier, expected_version} | 200 Table |
| Suppression | DELETE /api/tables/{id} + If-Match | 200, 403 protection, 400 FK block, 409 |
| Archive/Restore | POST /api/tables/{id}/archive/restore | Table |
| Unlock | POST /api/unlock-table {table_id, key_identifier} | {unlocked:true} |
| Export XML | GET /api/export/table-xml/{id} | {xml, document_version} |
| Export SQL | GET /api/export/table-sql/{id} | {sql} |
| Sync XML | POST /api/tables/{id}/sync-xml {xml, expected_version} | {xml, sql, table, document_version} |

**Modèle Table** :
```ts
id, uuid, name, description, database_id, creator_id, created_at, updated_at,
comment, status, is_protected, has_file_identifier, protected, archived,
columns_count, file_identifier?, access
```

- UI `DatabaseView.tsx` : liste tables réelles, `columns_count` réel, protection badge réel
- `TableWorkspace.tsx` : fetch columns/rows/xml au changement table.id, clear stale state

---

## 5. Colonnes / Structure

**Fichier** : `src/api/columns.ts`

| Opération | Endpoint | Réponse |
|---|---|---|
| Liste | GET /api/columns/{table_id}?include_archived | [ColumnView] |
| Détail | GET /api/columns/{id}/detail | ColumnView |
| Création | POST /api/columns {name, type, length, nullable, primary_key, foreign_key, references, unique, auto_increment, index, default, comment, table_id, expected_version} | 201 Column |
| Modification | PUT /api/columns/{id} | 200 Column |
| Suppression | DELETE /api/columns/{id} + If-Match | 200, 400 FK block |
| Archive/Restore | POST /api/columns/{id}/archive/restore | Column |

**Modèle Column** :
```ts
id, uuid, name, type, length, nullable, primary_key, foreign_key, unique,
auto_increment, default, references: "table.column"|null, on_delete, on_update,
index, comment, status, table_id
```

- Mapping : ancien `pk/ai/def/fk` → `primary_key/auto_increment/default/references`
- Types : backend sépare `type` et `length` (ex: VARCHAR + 150), pas `VARCHAR(150)`
- UI `StructureTab.tsx` : affiche badges PK, AI, NN, UNIQUE, INDEX, FK→references, défaut, commentaire, utilise `columns` réelles, erreur distincte vs vide

---

## 6. Lignes / Data Grid

**Fichier** : `src/api/rows.ts`

| Opération | Endpoint | Réponse |
|---|---|---|
| Liste | GET /api/tables/{id}/rows?limit&offset&search&sort&order&filters | {rows:[{id, uuid, table_id, data}], total, limit, offset} |
| Création | POST /api/tables/{id}/rows {data, expected_version} | 201 Row |
| Modification | PUT /api/tables/{id}/rows/{row_id} {data, expected_version} | 200 Row |
| Suppression | DELETE /api/tables/{id}/rows/{row_id} + If-Match | 200 |

- `Row.data` = dict colonne→valeur, `null` réel
- Pagination backend via `limit/offset`, total réel
- Recherche backend `search` param
- Filtres backend `filters` JSON
- Tri backend `sort` + `order`
- UI `DataTab.tsx` : utilise `fetchRows(tableId, {limit, offset, search, sort, order, filters})`, pas de slice local, affiche badge NULL, FK cliquable → navigation vers table référencée, pagination Page X/Y, loading/error/empty distincts

**Édition directe cellule** : non encore implémentée double-clic → input (gap documenté), mais RowModal existe avec gestion NULL

---

## 7. Console SQL

**Fichier** : `src/api/queries.ts` + `src/views/SqlConsole.tsx`

- Ancien moteur simulé `execute()` supprimé
- Flux réel :
```
SQL Editor → POST /api/databases/{id}/query {sql, expected_version} → XmlQueryService → XmlDataPlane.execute() → XmlNativeEngine → Result
```
- Supporté (selon `xml_query_service.py`, `xml_native.py`, tests) :
  - SELECT, SELECT COUNT, INSERT, UPDATE, DELETE
  - CREATE TABLE, DROP TABLE, ADD COLUMN, DROP COLUMN, MODIFY COLUMN, RENAME TABLE, CREATE/DROP INDEX
  - JOIN, LEFT JOIN, GROUP BY, HAVING, ORDER BY, LIMIT, OFFSET, DISTINCT, WHERE, transactions BEGIN/COMMIT/ROLLBACK, USE/DROP DATABASE via TCP
- Ne pas supposer MySQL complet : utiliser erreurs backend réelles
- UI affiche `rows`, `columns`, `count`, `affected`, `timing.ms` réel, erreurs backend

---

## 8. XML Editor

**Fichier** : `src/api/xml.ts` + `src/views/XmlPanel.tsx`

| Opération | Endpoint | Réponse |
|---|---|---|
| Export DB XML | GET /api/export/xml/{id} | {xml, document_version} |
| Export DB SQL | GET /api/export/sql/{id} | {sql} |
| Export Table XML | GET /api/export/table-xml/{id} | {xml, document_version} |
| Export Table SQL | GET /api/export/table-sql/{id} | {sql} |
| Sync DB | POST /api/databases/{id}/sync-xml {xml, expected_version} | {document_version, ...} |
| Sync Table | POST /api/tables/{id}/sync-xml {xml, expected_version} | {xml, sql, table, document_version} |
| XML→SQL | POST /api/convert/xml-to-sql {xml, database_name} | {sql} |
| SQL→XML | POST /api/convert/sql-to-xml {sql, database_name} | {xml} |

- Chargement XML réel depuis backend, pas `dbToXml()` local
- Validation locale simple + validation backend XSD via lxml (erreurs 400)
- Apply → POST sync-xml avec expected_version, gère 409 conflit
- Reset → reload depuis export
- Téléchargement/Copie réels
- Pas de chemins Linux fictifs `/var/xmlforge/data`

---

## 9. Import / Export

**Fichier** : `src/api/xml.ts` + `src/views/ImportExport.tsx`

- Import XML : `importXmlRaw(xml)` → POST /api/import/xml {xml, name} ou FormData file → ImportService
- Import SQL : POST /api/import/sql FormData
- Import Project : POST /api/import/project FormData + GET /api/export/project/{id}
- Export : GET blob + download via `apiClient.download()`, pas toast fake
- Aperçu : XmlPanel avec doc réel
- Options : includeData, pretty, conflict (merge/replace/skip/error) documentés mais backend gère via sync (pas de faux)

---

## 10. Permissions / Partage

**Fichier** : `src/api/permissions.ts`

| Opération | Endpoint | Réponse |
|---|---|---|
| Liste DB perms | GET /api/databases/{id}/permissions | [DatabasePermissionView + user_email] |
| Grant DB | POST /api/databases/{id}/permissions {email, can_read, can_write, can_ddl, can_admin} | 201 Permission |
| Revoke DB | DELETE /api/databases/{id}/permissions/{user_id} | 200 |
| Liste Table perms | GET /api/tables/{id}/permissions | [TablePermissionView] |
| Grant Table | POST /api/tables/{id}/permissions | 201 |
| Revoke Table | DELETE /api/tables/{id}/permissions/{user_id} | 200 |

- `accessLevel()` = `access.level` ou `is_owner ? MANAGE : NONE`
- PERSONAL : permissions individuelles explicites
- COMMON : `common_permission` VIEW/EDIT/MANAGE, visible à tous si VIEW, pas de partage individuel VIEW requis
- UI `ShareModal` : liste perms réelles, grant par email avec VIEW/EDIT/MANAGE → can_* mapping, revoke réel
- Frontend jamais autorité : boutons désactivés selon `access.can_*`, mais backend reste garde

---

## 11. Protection table

- `setProtected(dbId, tableId, value, key)` → PUT /api/tables/{id} {is_protected, file_identifier}
- `unlockTable(tableId, key)` → POST /api/unlock-table {table_id, key_identifier} → session 24h
- Lecture possible même protégée, écriture bloquée (backend `UnlockService.check_protection()`)
- UI badge Protégée/Modifiable, banner warn avec bouton Unlock, sessionStorage `xmlforge_unlocks` pour compat

---

## 12. Administration

**Fichiers** : `src/api/users.ts`, `audit.ts`, `history.ts` + `src/views/AdminView.tsx`

| Opération | Endpoint | Accès |
|---|---|---|
| Liste users | GET /api/users?search&include_inactive | Admin only 403 sinon |
| Détail user | GET /api/users/{id} | Admin |
| Création user | POST /api/users {full_name, email, password, is_active, role} | Admin |
| Modification | PUT /api/users/{id} | Admin |
| Suppression | DELETE /api/users/{id} | Admin |
| Reset pwd | POST /api/users/{id}/reset-password {new_password} | Admin |
| Toggle active | POST /api/users/{id}/toggle-active | Admin |
| Audit | GET /api/audit-logs?limit | Admin |
| History | GET /api/history?limit&offset | Admin |

- UI AdminView : si !isAdmin → page "Accès refusé" avec bouton retour, pas page vide
- Users : liste réelle, toggle active, suppression avec confirm, erreurs 403 affichées
- Audit : timestamp réel, user_name, action, element_name, ip_address
- History : created_at réel, user_name, action_type, element_name

---

## 13. Serveur / TCP

**Fichiers** : `src/api/server.ts`, `tcp.ts` + `src/views/ServerView.tsx`

| Endpoint | Réponse |
|---|---|
| GET /health | {status, service, version, storage:{control_plane, data_plane, sqlite:absent}} |
| GET /api/tcp/status | {tcp_enabled, host, port, running} |
| GET /api/tcp/sessions | [{id, host, port, user_name, database}] admin |
| GET /api/tcp/credentials | {tcp_username, tcp_host, tcp_port, is_active} |
| POST /api/tcp/credentials | création |
| etc | - |

- Page Server : affiche version réelle, bases count, stockage XML-only, SQLite absent, REST localhost:5000, TCP localhost:3307, sessions réelles, pas de fake uptime/free/used/CPU, pas de boutons Restart/Reload simulés (retirés, seulement Actualiser)
- Chemins Linux fictifs `/var/xmlforge/data`, `/etc/xmlforge/config.toml` retirés → remplacés par "Stockage XML natif" et "%LOCALAPPDATA%\XMLForge\data\" informatif

---

## 14. Gestion erreurs, Loading, Empty

- `apiClient` : 401 → session expirée, 403 → droits insuffisants, 404 → introuvable, 409 → conflit version, 400/422 → validation, 500 → erreur serveur, 0 → impossible joindre backend
- Chaque vue : `LoadingState`, `EmptyState`, `ErrorState` distincts
- Exemples :
  - Colonnes : `Impossible de charger les colonnes.` vs `Aucune colonne`
  - Relations : `Impossible de charger les relations.` vs `Aucune FK`
  - Lignes : `rowsError` danger-box vs `Aucune donnée`
- Pas de faux succès : si HTTP 4xx/5xx → toast error, pas success

---

## 15. Store — Source de vérité

**Fichier** : `src/store.tsx` (réécrit)

- UI state : nav, sidebar, palette, activeDb
- Auth : session réelle JWT
- Données persistantes : dbs (Database[]), tables (Table[]), columns (Column[]), rows (Row[]), queryResult, xmlDoc, serverHealth, tcpStatus, history
- Plus de `push()` local sans API : chaque mutation passe par API → réponse → maj cache → UI
- Effets : `fetchDatabases()` au login, `fetchTables(activeDb)` au changement base, `fetchColumns(tableId)` + `fetchRows()` + `fetchXml()` au changement table, clear stale state pour éviter mélange
- `isAdmin` depuis `session.user.is_admin`

---

## 16. Variables d'environnement

- `VITE_API_URL` : `/api` par défaut (même origine, Flask sert frontend en prod) ou URL absolue
- `VITE_SOCKET_URL` : pour SocketIO si activé
- Backend fournit `FRONTEND_DIST_FOLDER` via `paths.frontend_dist_folder()` → `xmlforge-react/dist` ou `frontend/` en bundle

---

## 17. Tests

- Frontend V2 : `npm run build` → 440 KB singlefile OK (après suppression mocks)
- Backend : 350 passed, packaging 16 passed (inchangé)
- E2E manuel : Login réel, création base, tables, colonnes, lignes, FK, recherche/tri/pagination, protection/unlock, partage, import/export, SQL, XML, audit/history, server status → cohérent

---

**Fin documentation intégration — Prêt pour polish UX**
