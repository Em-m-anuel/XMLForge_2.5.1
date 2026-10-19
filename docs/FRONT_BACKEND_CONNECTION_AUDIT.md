# XMLFORGE — FRONTEND / BACKEND CONNECTION AUDIT

**Date : 2026-09-15**
**Méthode : Inspection statique code réel + tests réels Flask test client + vérification build frontend, sans modification de code**
**Frontend audités** :
- `xmlforge-react/` (ancien, React/Vite, build multi-chunks)
- `XMLForge_FrontRedesign/` (nouveau V2.3, React 19 + TS + Tailwind, singlefile 461KB)
**Backend** : `backend/` Flask XML-only, 350 tests verts, TCP 3307

---

## 1. Résumé

La connexion Frontend ↔ Backend **fonctionne correctement en production (Flask sert dist)** et **fonctionne en développement pour l'ancien frontend** grâce au proxy Vite. **Un problème P1 a été introduit pendant les travaux packaging/V2** : le nouveau frontend `XMLForge_FrontRedesign` a perdu son proxy Vite `/api` dans `vite.config.ts`, ce qui casse la connexion en mode développement (`npm run dev` → `localhost:5173` → `/api` → 404 Vite au lieu de Flask :5000).

- **Production** : `Flask :5000` sert `dist/index.html` (old ou new V2.3), `/api/*` et `/socket.io/*` → 404 JSON (pas SPA), chemins sensibles `data/`, `control/`, `..` → 404 JSON → connexion OK, JWT OK, CORS inutile (même origine)
- **Développement old** : Vite `5173` proxy `/api` → `localhost:5000` → connexion OK
- **Développement new V2.3** : Vite `5173` **sans proxy** (fichier `vite.config.ts` ne contient que `react()`, `tailwindcss()`, `viteSingleFile()`) → fetch `/api/databases` → Vite dev server 404 → `Failed to fetch` → connexion **BROKEN en dev**
- **Aucune régression backend** : toutes les routes REST existent en `/` et `/api`, `success_response({success, data, message})`, JWT, 401/403/404/409/500 gérés, CORS configuré `localhost:5173,localhost:3000`
- **Aucun mock runtime** dans V2.3 après intégration (mock.ts non importé), 0 donnée fictive, SQL réel, XML réel, permissions réelles

**Verdict** : **FRONT/BACK CONNECTED WITH ISSUES** — connecté en prod, mais P1 majeur en dev pour nouveau frontend (proxy manquant).

---

## 2. Architecture détectée

```
Navigateur
  ├─ DEV old : http://localhost:5173 (Vite) → proxy /api → http://localhost:5000 (Flask)
  ├─ DEV new V2.3 : http://localhost:5173 (Vite) → PAS DE PROXY → /api → 404 Vite → BROKEN
  └─ PROD : http://localhost:5000 (Flask) sert dist/index.html → /api même origine → Flask

Backend Flask (backend/run.py → create_app(Config) → socketio.run 0.0.0.0:5000)
  ├── Config via paths.py : CONTROL_STORAGE_FOLDER, XML_STORAGE_FOLDER, UPLOAD_FOLDER, EXPORT_FOLDER, LOG_FOLDER, CONFIG_FOLDER, FRONTEND_DIST_FOLDER, FILE_LOGS_ENABLED
  ├── Control Plane XML : security.xml, catalog.xml, history.xml, audit/ (+ .lock) — 0700, validation XSD via lxml
  ├── Data Plane XML : data/xml/<id>_<slug>.xml (+ .lock) — atomic_write, database_lock
  ├── XML Native Engine : XmlNativeEngine, parse_document(validate=True), serialize_document()
  ├── PermissionService PERSONAL/COMMON VIEW/EDIT/MANAGE + UnlockService 24h personal
  ├── TCPServer 0.0.0.0:3307 thread daemon xmlforge-tcp, SO_REUSEADDR, listen 64, timeout 1s, buffer 8 MiB
  └── Frontend dist serving : si dist existe → / → index.html, /<path> fichier statique ou fallback SPA index.html, /api/*, /socket.io/*, data/, control/, config/, logs/, tmp/, backend/, .., %2e → 404 JSON

Client Python xmlforge/ stdlib pure → TCP 3307 [type:1][len:4 BE][JSON]
```

**Point d'entrée backend** : `backend/run.py` :
```python
flask_app = create_app(Config)
socketio.run(flask_app, host=flask_app.config.get('HTTP_HOST','0.0.0.0'), port=flask_app.config.get('HTTP_PORT',5000), ...)
```
`create_app()` → `os.makedirs(UPLOAD_FOLDER, EXPORT_FOLDER, XML_STORAGE_FOLDER)` + `ensure_dir(CONTROL_STORAGE_FOLDER, 0700)` + file logging si `FILE_LOGS_ENABLED` + `register_routes()` + fail-closed check `security.xml`, `catalog.xml`, `history.xml` via `read_validated()` sauf `xml-bootstrap`/`init-app` dans argv + `TCPServer(...).start()`

**Point d'entrée frontend** :
- old : `xmlforge-react/src/main.jsx` → Vite
- new V2.3 : `XMLForge_FrontRedesign/src/main.tsx` → Vite + singlefile plugin

---

## 3. Comment le frontend appelle actuellement le backend

**Ancien frontend `xmlforge-react/src/services/api.js`** :
- `apiClient.get/post/put/delete/blob/download` → `fetch(buildUrl(path), {method, headers, body})`
- `buildUrl(path)` → `${API_URL}${path}` où `API_URL = (VITE_API_URL || '/api').replace(/\/$/, '')` → `/api` par défaut
- Exemple : `apiClient.get('/databases')` → `/api/databases` → Flask
- Services : `databaseService.list()` → GET `/databases?include_archived`, `tableService.list(dbId)` → GET `/tables/{dbId}`, `columnService.list(tableId)` → GET `/columns/{tableId}`, `rowService.list(tableId, {limit,offset,search,sort,order,filters})` → GET `/tables/{id}/rows?limit&offset&search&sort&order&filters`, `queryService` → POST `/databases/{id}/query` {sql}, `xmlService` → GET `/export/xml/{id}`, POST `/databases/{id}/sync-xml`, etc — tous via `apiClient`

**Nouveau frontend V2.3 `XMLForge_FrontRedesign/src/api/client.ts`** :
- Même logique que old, en TS, même `API_URL = (VITE_API_URL || '/api').replace(/\/$/, '')`, même `buildUrl()`, même JWT handling, même `ApiError` 401/403/404/409/500
- Modules : `auth.ts` POST `/register`, `/login`, GET `/me`, POST `/logout`; `databases.ts` GET `/databases`, POST, PUT, DELETE, archive/restore; `tables.ts` GET `/tables/{dbId}`, GET detail, POST, PUT, DELETE + If-Match, unlock POST `/unlock-table`, export GET `/export/table-xml`, sync POST `/tables/{id}/sync-xml`; `columns.ts` GET `/columns/{tableId}`, POST, PUT, DELETE; `rows.ts` GET `/tables/{id}/rows?queryString`, POST, PUT, DELETE; `queries.ts` POST `/databases/{id}/query`, GET `/databases/{id}/schema`; `xml.ts` export/sync/convert/import/project; `permissions.ts` GET/POST/DELETE `/databases/{id}/permissions`, `/tables/{id}/permissions`; `users.ts` GET `/users`, POST, PUT, DELETE, reset-password, toggle-active; `audit.ts` GET `/audit-logs`; `history.ts` GET `/history`; `server.ts` GET `/health`, POST rebuild-projection; `tcp.ts` GET `/tcp/credentials`, `/tcp/status`, `/tcp/sessions`, etc

**Flux** :
```
React → apiClient → fetch(/api/...) → Flask → Services → XML Data Plane → XML Native Engine → XML
```

---

## 4. Base URL et résolution des URLs

**Fichier** : `src/api/client.ts` (new V2.3) ligne 1-2, `xmlforge-react/src/services/api.js` ligne 1-2

```ts
const configuredApiUrl = (import.meta.env.VITE_API_URL || '/api').trim()
const API_URL = configuredApiUrl.replace(/\/$/, '')
function buildUrl(path: string) {
  if (/^https?:\/\//i.test(path)) return path
  return `${API_URL}${path.startsWith('/') ? path : `/${path}`}`
}
```

- **Valeur actuelle** : Si `VITE_API_URL` non défini (cas dev et prod par défaut, vérifié `cat .env` vide) → `/api`
- **Type** : **Relative URL** `/api/...` — pas `http://localhost:5000/api/...`, pas `127.0.0.1:5000`, pas `window.location`, pas `location.origin` hardcodé
- **Résolution** :
  - DEV old avec proxy : `/api/databases` → Vite dev server (5173) → proxy `http://localhost:5000` → Flask → OK
  - DEV new V2.3 sans proxy : `/api/databases` → Vite dev server (5173) → 404 (Vite ne connaît pas /api) → `Failed to fetch` → BROKEN
  - PROD : Flask sert dist sur `localhost:5000` → `/api/databases` même origine → Flask → OK, pas de CORS nécessaire

**Vite config** :

- Old `xmlforge-react/vite.config.js` :
```js
server: {
  proxy: {
    '/api': { target: 'http://localhost:5000', changeOrigin: true },
    '/socket.io': { target: 'http://localhost:5000', ws: true, changeOrigin: true },
  }
}
```
→ Proxy présent ✅

- New V2.3 `XMLForge_FrontRedesign/vite.config.ts` :
```ts
export default defineConfig({
  plugins: [react(), tailwindcss(), viteSingleFile()],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
});
```
→ **Pas de proxy** ❌ — régression packaging/V2

**Conclusion** : Frontend utilise **A. `/api/...` relative** (bonne pour prod same-origin), mais **nécessite proxy Vite en dev** qui manque dans nouveau frontend.

---

## 5. API Client

**Fichier** : `src/api/client.ts` (new) et `xmlforge-react/src/services/api.js` (old) — quasi identiques

| Aspect | Implémentation actuelle | État |
|---|---|---|
| URL | `/api` relative via `VITE_API_URL` env ou `/api` défaut | OK prod, P1 dev new (proxy manquant) |
| Méthode HTTP | GET, POST, PUT, DELETE via `fetch` | OK |
| Headers | `Accept: application/json` ou `*/*` blob, `Content-Type: application/json` si pas FormData, custom headers supportés | OK |
| Authorization | `Bearer ${token}` si `getToken()` présent | OK |
| Bearer token | `localStorage.getItem('xmlforge_token')` | OK |
| Content-Type | `application/json` sauf FormData (import) | OK |
| FormData | `instanceof FormData` check → pas de Content-Type JSON, body = FormData | OK pour import XML/SQL/Project |
| Query params | `URLSearchParams` pour rows list (limit, offset, search, sort, order, filters JSON) | OK |
| Body JSON | `JSON.stringify(body)` si pas FormData | OK |
| Réponses | `response.json()` si ok, `response.blob()` si blob, 204 → null | OK, backend `success_response({success, data, message})` → `res.data` |
| Erreurs | `parseError()` → `ApiError(friendlyMessage(status, payload), status, payload)` | OK |
| 401 | `clearSession('unauthorized')` + event `xmlforge:unauthorized` + toast session expirée | OK, backend `token_verification_loader` check is_active, token_version, revoked |
| 403 | friendlyMessage "Vous ne disposez pas des droits" | OK |
| 404 | friendlyMessage "Ressource introuvable" | OK, backend sensitive paths → 404 JSON |
| 409 | `isConflict = status===409`, friendlyMessage "Cette base a été modifiée..." | OK, backend `ConflictError` via `mutate(expected_version)` |
| 400/422 | "Données invalides" | OK |
| 500 | "Serveur XMLForge a rencontré une erreur" | OK |
| Download | `downloadBlob()` via `URL.createObjectURL` + anchor click | OK pour export XML/SQL/Project |
| Timeout | Pas de timeout explicite, mais `signal` AbortSignal supporté, et `isTokenExpired()` check avant requête | INFORMATION — pas de timeout HTTP, mais backend a timeouts TCP 1s/2s |
| 0 / NetworkError | `Failed to fetch` → "Impossible de joindre le backend XMLForge" status 0 | OK |

**Modules vérifiés** : tous les 12 modules new + 15 old utilisent `apiClient.get/post/put/delete/blob/download` avec URLs `/databases`, `/tables/${id}`, `/columns/${id}`, `/tables/${id}/rows`, `/databases/${id}/query`, `/export/...`, `/sync-xml`, `/permissions`, `/users`, `/audit-logs`, `/history`, `/health`, `/tcp/...` — tous existent backend (voir matrice section 7).

**Aucun mock** dans client, aucun `setTimeout` fake loading (seulement focus 20ms, toast 4200ms, xf-new-row 60ms, validate 200ms — acceptables).

---

## 6. Authentification JWT

**Cycle complet vérifié via Flask test client** :

```
POST /api/register {full_name, email, password} → 201 {data: user.to_dict()}
  ↓
POST /api/login {email, password} → 200 {data: {user: {id, full_name, email, role, is_admin, is_active}, access_token: JWT}}
  ↓ JWT = header.payload.signature, payload contient sub=user_id, exp, jti, token_version, exp 24h
  ↓ Frontend : localStorage.setItem('xmlforge_token', token) + xmlforge_user = user + initialsOf(full_name)
  ↓ GET /api/me avec Authorization: Bearer <token> → 200 {data: user.to_dict()} (vérifié)
  ↓ Flask : @jwt_required() + token_verification_loader → get_backend().get_user(sub) + volatile.is_revoked(jti) + is_active + token_version check → True
  ↓ Store : session {user, authenticated:true}, isAdmin = user.is_admin || role admin
  ↓ F5 : token présent → apiMe() → GET /me → restaure session
  ↓ Logout : POST /api/logout → revoke jti + clear unlocks + audit log → frontend clear localStorage/sessionStorage
  ↓ Expiration : client decode exp, si exp*1000 <= Date.now() → clearSession('expired') + throw 401 avant requête
  ↓ 401 : response 401 → clearSession('unauthorized') + event xmlforge:unauthorized → redirect login
```

**Tests réels** :
- Register 201 OK
- Login 200 OK + token
- Me 200 OK email admin@test.local
- Databases list 200 OK avec auth, 401 sans auth
- Token expiré simulé → clearSession

**Pas de régression** : Auth mock avec bypass unknown email → CURRENT_USER a été supprimé dans V2.3 (remplacé par vraie API qui retourne 401).

---

## 7. Correspondance Frontend ↔ Backend — Matrice endpoints

| Frontend appelle (new V2.3) | Méthode | Backend existe ? | Fichier backend | Réponse attendue | État |
|---|---|---|---|---|---|
| `/register` | POST | OUI | `auth.py:19` `/api/register` | 201 user.to_dict() | OK |
| `/login` | POST | OUI | `auth.py:45` `/api/login` | 200 {user, access_token} | OK |
| `/me` | GET | OUI | `auth.py:72` `/api/me` | 200 user.to_dict() | OK |
| `/logout` | POST | OUI | `auth.py:84` `/api/logout` | 200 + revoke | OK |
| `/databases?include_archived` | GET | OUI | `databases.py:25` `/api/databases` | [DatabaseView+access] | OK |
| `/databases/{id}` | GET | OUI | `databases.py:124` `/api/databases/{id}` | DatabaseView | OK |
| `/databases` | POST | OUI | `databases.py:37` `/api/databases` | 201 Database | OK |
| `/databases/{id}` | PUT | OUI | `databases.py:73` `/api/databases/{id}` | 200 Database, 409 conflit | OK |
| `/databases/{id}` | DELETE | OUI | `databases.py:108` `/api/databases/{id}` | 200 | OK |
| `/databases/{id}/archive` | POST | OUI | `metadata.py:112` `/api/databases/{id}/archive` | Database | OK |
| `/databases/{id}/restore` | POST | OUI | `metadata.py:125` `/api/databases/{id}/restore` | Database | OK |
| `/tables/{database_id}?include_archived` | GET | OUI | `tables.py:24` `/api/tables/{db}` | [TableView+access] | OK |
| `/tables/{id}/detail` | GET | OUI | `tables.py:36` `/api/tables/{id}/detail` | TableView | OK |
| `/tables` | POST | OUI | `tables.py:48` `/api/tables` | 201 Table | OK |
| `/tables/{id}` | PUT | OUI | `tables.py:88` `/api/tables/{id}` | 200 Table | OK |
| `/tables/{id}` | DELETE | OUI | `tables.py:119` `/api/tables/{id}` | 200, If-Match | OK |
| `/tables/{id}/archive` | POST | OUI | `metadata.py:138` `/api/tables/{id}/archive` | Table | OK |
| `/tables/{id}/restore` | POST | OUI | `metadata.py:154` `/api/tables/{id}/restore` | Table | OK |
| `/unlock-table` | POST | OUI | `unlock.py:19` `/api/unlock-table` | {unlocked} | OK |
| `/export/table-xml/{id}` | GET | OUI | `exports.py:68` `/api/export/table-xml/{id}` | {xml, document_version} | OK |
| `/export/table-sql/{id}` | GET | OUI | `exports.py:97` `/api/export/table-sql/{id}` | {sql} | OK |
| `/tables/{id}/sync-xml` | POST | OUI | `sync.py:81` `/api/tables/{id}/sync-xml` | {xml, sql, table, document_version} | OK |
| `/columns/{table_id}?include_archived` | GET | OUI | `columns.py:17` `/api/columns/{table}` | [ColumnView] | OK (fix list_columns) |
| `/columns/{id}/detail` | GET | OUI | `columns.py:29` `/api/columns/{id}/detail` | ColumnView | OK (fix get_column) |
| `/columns` | POST | OUI | `columns.py:41` `/api/columns` | 201 Column | OK |
| `/columns/{id}` | PUT | OUI | `columns.py:69` `/api/columns/{id}` | 200 Column | OK |
| `/columns/{id}` | DELETE | OUI | `columns.py:94` `/api/columns/{id}` | 200, If-Match | OK |
| `/columns/{id}/archive` | POST | OUI | `metadata.py:170` `/api/columns/{id}/archive` | Column | OK |
| `/columns/{id}/restore` | POST | OUI | `metadata.py:187` `/api/columns/{id}/restore` | Column | OK |
| `/tables/{id}/rows?limit&offset&search&sort&order&filters` | GET | OUI | `rows.py:16` `/api/tables/{id}/rows` | {rows, total, limit, offset} | OK |
| `/tables/{id}/rows` | POST | OUI | `rows.py:35` `/api/tables/{id}/rows` | 201 Row {id, uuid, table_id, data} | OK |
| `/tables/{id}/rows/{row_id}` | PUT | OUI | `rows.py:70` `/api/tables/{id}/rows/{row}` | 200 Row | OK |
| `/tables/{id}/rows/{row_id}` | DELETE | OUI | `rows.py:105` `/api/tables/{id}/rows/{row}` | 200, If-Match | OK |
| `/databases/{id}/query` | POST | OUI | `query.py:11` `/api/databases/{id}/query` | {rows, columns, count, affected, timing} | OK, moteur XML natif réel |
| `/databases/{id}/schema` | GET | OUI | `query.py:31` `/api/databases/{id}/schema` | {database, tables:[{name, columns, foreign_keys, primary_key, row_count}]} | OK, optimisation diagramme |
| `/export/xml/{id}` | GET | OUI | `exports.py:16` `/api/export/xml/{id}` | {xml, document_version} ou blob | OK |
| `/export/sql/{id}` | GET | OUI | `exports.py:44` `/api/export/sql/{id}` | {sql} ou blob | OK |
| `/export/project/{id}` | GET/download | OUI | `projects.py:15` `/api/export/project/{id}` | blob XML | OK |
| `/databases/{id}/sync-xml` | POST | OUI | `sync.py:37` `/api/databases/{id}/sync-xml` | {document_version} | OK |
| `/convert/xml-to-sql` | POST | OUI | `converters.py:18` `/api/convert/xml-to-sql` | {sql} | OK |
| `/convert/sql-to-xml` | POST | OUI | `converters.py:66` `/api/convert/sql-to-xml` | {xml} | OK |
| `/import/xml` | POST | OUI | `imports.py:15` `/api/import/xml` | Database | OK, FormData ou JSON |
| `/import/sql` | POST | OUI | `imports.py:60` `/api/import/sql` | Database | OK |
| `/import/project` | POST | OUI | `projects.py:43` `/api/import/project` | Database | OK |
| `/databases/{id}/permissions` | GET/POST | OUI | `permissions.py:11,19` `/api/databases/{id}/permissions` | [PermissionView] | OK |
| `/databases/{id}/permissions/{user_id}` | DELETE | OUI | `permissions.py:34` | 200 | OK |
| `/tables/{id}/permissions` | GET/POST | OUI | `permissions.py:42,51` | [TablePermissionView] | OK |
| `/tables/{id}/permissions/{user_id}` | DELETE | OUI | `permissions.py:64` | 200 | OK |
| `/users?search&include_inactive` | GET | OUI | `users.py:40` `/api/users` | [UserView] admin 403 | OK |
| `/users/{id}` | GET/PUT/DELETE | OUI | `users.py:53,100,129` | UserView | OK |
| `/users/{id}/reset-password` | POST | OUI | `users.py:151` | UserView | OK |
| `/users/{id}/toggle-active` | POST | OUI | `users.py:180` | UserView | OK |
| `/audit-logs?limit` | GET | OUI | `audit.py:12` `/api/audit-logs` | [AuditView] | OK |
| `/history?limit&offset` | GET | OUI | `history.py:12` `/api/history` | [HistoryView] | OK |
| `/health` | GET | OUI | `__init__.py` `/health` | {status, service, version, storage} | OK |
| `/tcp/credentials` | GET/POST/PUT/DELETE | OUI | `tcp.py:13,36,62,106` `/api/credentials` etc | TcpCredentialView | OK |
| `/tcp/credentials/regenerate` | POST | OUI | `tcp.py:88` | new creds | OK |
| `/tcp/credentials/show-password` | POST | OUI | `tcp.py:124` | password | OK |
| `/tcp/sessions` | GET | OUI | `tcp.py:172` `/api/sessions` | sessions info | OK |
| `/tcp/status` | GET | OUI | `tcp.py:197` `/api/status` | {host, port, running} | OK |
| `/databases/{id}/rebuild-projection` | POST | OUI (no-op) | `sync.py:21` `/api/databases/{id}/rebuild-projection` | {projection:XML_ONLY} | OK, compat |
| `/unlocks` | GET/DELETE | OUI | `unlock.py:65,76` `/api/unlocks` | [UnlockView] | OK, old frontend only |

**Aucun endpoint manquant** — toutes les URLs frontend existent backend en `/` et `/api`.

---

## 8. Flask et service du frontend

**Fichier** : `backend/app/__init__.py` lignes 190-230

```python
_frontend_dist = flask_app.config.get('FRONTEND_DIST_FOLDER') or _paths.frontend_dist_folder()
if _frontend_dist and os.path.isdir(_frontend_dist):
    @flask_app.route('/', methods=['GET'])
    def frontend_index():
        return send_from_directory(_frontend_dist, 'index.html')

    @flask_app.route('/<path:path>', methods=['GET'])
    def frontend_assets(path):
        if path.split('/', 1)[0] in ('api', 'socket.io'):
            return error_response("Ressource introuvable", 404)
        lowered = path.lower()
        sensitive_prefixes = ('data/', 'control/', 'config/', 'logs/', 'tmp/', 'backend/')
        if lowered.startswith(sensitive_prefixes) or '..' in path or '%2e' in lowered:
            return error_response("Ressource introuvable", 404)
        target = os.path.join(_frontend_dist, path)
        if path and os.path.isfile(target):
            return send_from_directory(_frontend_dist, path)
        return send_from_directory(_frontend_dist, 'index.html')
else:
    @flask_app.route('/', methods=['GET'])
    def index():
        return {"service": "XMLForge Backend API (XML-only)", ...}
```

- **Host/Port** : `HTTP_HOST` env `XMLFORGE_HTTP_HOST` défaut `0.0.0.0`, `HTTP_PORT` env `XMLFORGE_HTTP_PORT` défaut 5000 (configurable, 5000 conservé)
- **Frontend dist détection** : `paths.frontend_dist_folder()` cherche env `XMLFORGE_FRONTEND_DIST`, sinon `<resources>/frontend` (bundle), sinon `<resources>/../xmlforge-react/dist` (dev) — robuste
- **Sécurité SPA** : `/api/*` et `/socket.io/*` → 404 JSON (pas index.html), `data/`, `control/`, etc, `..`, `%2e` → 404 JSON (fix sécurité, test `test_security_no_file_exposure` passe)
- **Tests réels Flask serving** :
  - Old `xmlforge-react/dist` : `/` → 200 text/html, `/assets/index-...js` → 200, `/api/databases` no auth → 401 (pas 200 SPA), `/data/control/security.xml` → 404 JSON ✅
  - New V2.3 `XMLForge_FrontRedesign/dist` singlefile 461KB : `/` → 200 text/html V2.3, `/api/databases` no auth → 401, sensitive → 404 ✅

**Verdict** : Flask sert correctement `dist`, fallback SPA OK, API routes protégées contre SPA fallback.

---

## 9. Vite DEV vs Flask PRODUCTION

| Mode | Frontend URL | API URL | Vite proxy | Flask serving | CORS | État |
|---|---|---|---|---|---|---|
| DEV old `xmlforge-react` | `localhost:5173` | `/api` relative → `localhost:5173/api` → proxy `localhost:5000` | OUI `/api` → `http://localhost:5000`, `/socket.io` → `localhost:5000` ws | NON (Vite sert) | OUI `CORS_ORIGINS` inclut `localhost:5173` | CONNECTED |
| DEV new V2.3 `XMLForge_FrontRedesign` | `localhost:5173` | `/api` relative → `localhost:5173/api` → **PAS DE PROXY** | **NON** — `vite.config.ts` contient seulement `react()`, `tailwindcss()`, `viteSingleFile()` | NON | OUI CORS Origins inclut 5173 mais requête n'atteint jamais Flask car Vite 404 | **BROKEN** — Failed to fetch |
| PROD old | `localhost:5000/` | `/api` même origine | NON (pas de Vite) | OUI `xmlforge-react/dist` → `/` index.html, assets, fallback SPA | NON nécessaire (même origine) | CONNECTED |
| PROD new V2.3 | `localhost:5000/` | `/api` même origine | NON | OUI `XMLForge_FrontRedesign/dist` singlefile ou `backend/frontend/` → 200 html, /api 401/200, sensitive 404 | NON nécessaire | CONNECTED |

**Risque packaging** : En application packagée, frontend servi par Flask même origine → `/api` relative fonctionne, pas de proxy, pas de CORS nécessaire → OK. Problème uniquement en DEV new V2.3.

**Recommandation** : Ajouter proxy `/api` et `/socket.io` dans `XMLForge_FrontRedesign/vite.config.ts` comme old frontend, ou documenter `VITE_API_URL=http://localhost:5000/api` pour dev.

---

## 10. CORS

**Fichier** : `backend/app/config.py:58` + `__init__.py:28`

```python
CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:5173,http://localhost:3000').split(',')
cors.init_app(flask_app, resources={r"/*": {"origins": CORS_ORIGINS}}, supports_credentials=True)
```

- **Valeur** : `localhost:5173` (Vite old et new), `localhost:3000` (tcp-tester)
- **Nécessaire en DEV** : OUI, car React Vite 5173 → Flask 5000 cross-origin → CORS doit autoriser 5173 → configuré ✅
- **Nécessaire en PROD packagée** : NON, frontend servi par Flask même origine `localhost:5000` → `/api` même origine → pas de CORS, mais config reste OK (pas bloquant)
- **SocketIO** : `socketio.init_app(flask_app, cors_allowed_origins=CORS_ORIGINS)` → idem

**Verdict** : CORS correctement configuré, nécessaire dev, inutile mais OK prod.

---

## 11. Frontend dist

**Vérification build** :

- Old `xmlforge-react` :
  - `npm run build` → `dist/` : `index.html` 0.75KB, `assets/Workspace-...js` 86KB gzip 18.96KB, `index-...js` 288KB gzip 91.72KB, CSS, favicon, icons.svg → OK
  - `dist/index.html` référence `/assets/...` relatifs? Vite build avec base `/` → `/assets/...` absolus depuis root Flask → `frontend_assets` sert fichier si existe dans dist → OK

- New V2.3 `XMLForge_FrontRedesign` :
  - `npm run build` → `dist/index.html` singlefile 461KB gzip 127KB (72 modules, vite-plugin-singlefile inlining JS+CSS) → OK
  - `dist/` contient seulement `index.html` (singlefile) → Flask sert `/` → index.html, pas d'assets séparés → OK
  - Code source `src/` ne contient plus de mocks runtime (grep `from.*mock` → seulement `mock.ts` fichier lui-même + commentaire store) → 0 donnée fictive runtime ✅
  - Pas de chemins Linux fictifs `/var/xmlforge/data` (fixés) → "Stockage XML natif" ✅

- **Flask sert bien CE dist** : testé via `TestConfig.FRONTEND_DIST_FOLDER` pointant vers `xmlforge-react/dist` et `XMLForge_FrontRedesign/dist` → GET `/` → 200 html correspondant, assets → 200, /api → 401 pas 200 SPA, sensitive → 404 → OK

- **Problème snapshot** : workspace snapshot exclut `dist/`, `node_modules/`, `.venv`, `__pycache__`, `build`, `coverage`, etc (cap 128MB) → après snapshot, `dist/` absent → `frontend_dist_folder()` retourne None → Flask sert JSON API pas SPA → INFORMATION, pas bloquant, mais en CI packaging il faut `npm run build` avant si on veut tester serving

---

## 12. Tests réels effectués

| Test | Commande / Méthode | Résultat |
|---|---|---|
| Backend packaging | `pytest tests/test_packaging.py -q` | 16 passed in 1.69s |
| Backend complet | `pytest -q` | 350 passed in 59.55s |
| Frontend old build | `cd xmlforge-react && npm run build` | OK 102 modules, Workspace 86KB |
| Frontend new V2.3 build | `cd XMLForge_FrontRedesign && npm run build` | OK 72 modules, 461KB singlefile |
| Flask serving old dist | test_client GET `/`, `/assets/...`, `/api/databases` no auth, `/data/control/security.xml` | / 200 html, asset 200, api 401, sensitive 404 ✅ |
| Flask serving new dist | test_client GET `/`, /api, sensitive | / 200 html V2.3, api 401, sensitive 404 ✅ |
| Auth cycle | test_client POST /api/register 201, POST /api/login 200 + JWT, GET /api/me 200 email, GET /api/databases 200 avec auth 0 bases, 401 sans auth, /health 200, /databases/{id}/schema 200 keys database, tables, version | Tous OK ✅ |
| E2E manuel complet V2.3 (script /tmp isolation) | Création DB PERSONAL/COMMON, tables users/posts avec PK/FK/AI/UNIQUE, colonnes, rows 30 pagination/search/sort/NULL, protection/unlock, permissions, import/export XML/SQL, sync, conversion, SQL, XML, audit/history, server health/TCP sessions, conflits 409, persistance restart | OK ✅ |
| Vite proxy check | grep vite.config.* | old OUI proxy /api, new NON proxy → P1 |
| CORS check | grep CORS_ORIGINS | localhost:5173,3000 OK |
| SQLite check | find *.db, grep sqlite | 0 fichier .db/.sqlite, runtime grep vide hors docs historiques ✅ |
| pip check | pip check | No broken requirements ✅ |

**Non vérifié** : Build EXE PyInstaller/Nuitka, installateur, service Windows, perf Windows réelle (sandbox Linux, mais simulation LOCALAPPDATA OK) → NON VÉRIFIÉ

---

## 13. Erreurs observées

- **Aucune erreur backend 500 en production** : tous les endpoints testés retournent 200/201/401/403/404/409 JSON avec `success` et `data`/`message`
- **Erreur P0 précédente fixée** : `list_columns_for_table` AttributeError (rapport V2) → fixée via `list_columns_for_table()` + `list_columns()` correcte → 16 packaging tests verts
- **Erreur dev new V2.3** : `Failed to fetch` / `NetworkError` / 404 Vite sur `/api/databases` en `npm run dev` (5173) car proxy manquant → cause exacte voir section 15
- **Erreur sécurité précédente fixée** : `/data/control/security.xml` → 200 index.html SPA fallback → maintenant 404 JSON grâce à blocage sensitive prefixes
- **Aucune erreur CORS** en dev old (proxy) et prod (même origine) — CORS configuré OK
- **Aucune erreur JWT** : 401 sans token, 200 avec token, expiration gérée client, 401 clear session

---

## 14. Régressions éventuelles

| Point V2.3 doit rester vrai | État actuel | Régression ? |
|---|---|---|
| frontend réel, 0 mock runtime | V2.3 store réel, mock.ts non importé runtime, 0 mock | NON |
| API REST réelle | Tous modules via apiClient /api | NON |
| JWT réel | login → JWT → localStorage + /me + Bearer | NON |
| CRUD réel bases/tables/colonnes/lignes | databaseService, tableService, columnService, rowService réels + expected_version/If-Match | NON |
| XML réel | export/sync/convert/import/project réels via xmlService | NON |
| permissions réelles PERSONAL/COMMON VIEW/EDIT/MANAGE | permissionService réel, access.level réel, COMMON collectif | NON |
| SQL console réelle | queryService.execute() POST /query → XmlNativeEngine, pas de fake execute() | NON |
| serveur réel health/TCP 3307 | serverService.health, tcpService.status/sessions réels, pas de fake uptime/free/used | NON |
| audit réel | auditService.list() /audit-logs réel | NON |
| historique réel | historyService.list() /history réel | NON |
| stockage XML-only | storage XML, sqlite absent, 0 .db | NON |
| modales Portal z-index | layers 200/300/400/410/500/600 + isolation:isolate #root → modal au-dessus dropdown | NON |
| design dark premium conservé | V2.3 design validé conservé, FR uniformisé | NON |
| **Vite proxy dev new** | **Manquant** dans `vite.config.ts` new V2.3 | **OUI — Régression P1** |

**Packaging** : Travaux packaging (paths.py, runtime.py, config, __init__.py serving frontend, secrets, init-app, logs, .gitignore, .env.example, pystray/pillow) **n'ont PAS cassé** connexion front/back prod, seulement dev new V2.3 proxy manquant (voir section 15).

---

## 15. Cause racine — OBLIGATOIRE

### Problème détecté : Connexion frontend → backend cassée en développement pour nouveau frontend V2.3

- **Fichier** : `XMLForge_FrontRedesign/vite.config.ts`
- **Fonction** : `defineConfig({ plugins, resolve })`
- **Lignes** : 1-20 (fichier actuel 20 lignes, pas de `server.proxy`)
- **Valeur actuelle** :
```ts
import path from "path";
import { fileURLToPath } from "url";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { viteSingleFile } from "vite-plugin-singlefile";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export default defineConfig({
  plugins: [react(), tailwindcss(), viteSingleFile()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
});
```
- **Valeur attendue** (comme old frontend `xmlforge-react/vite.config.js`) :
```ts
export default defineConfig({
  plugins: [react(), tailwindcss(), viteSingleFile()],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  server: {
    host: '0.0.0.0',
    allowedHosts: true,
    proxy: {
      '/api': { target: 'http://localhost:5000', changeOrigin: true },
      '/socket.io': { target: 'http://localhost:5000', ws: true, changeOrigin: true },
    },
  },
});
```
- **Conséquence** :
  - En `npm run dev` (Vite 5173), frontend appelle `/api/databases` (relative) → Vite dev server cherche `/api` en tant que fichier statique → 404 Vite → `fetch` échoue → `ApiError` "Impossible de joindre le backend XMLForge" status 0 → UI affiche "Impossible de charger les bases" + toast erreur, pas de données
  - En production packagée (Flask 5000 sert dist), `/api` même origine → Flask → fonctionne → pas de problème prod, mais dev cassé → gêne développement V2.3
  - Old frontend `xmlforge-react` a proxy → dev OK → pas de régression old

- **Autre fichier concerné** : `src/api/client.ts` ligne 1-2 utilise `/api` relative (bonne pratique prod), mais dépend proxy dev. Pas de bug client, seulement config Vite manquante.

- **Impact packaging** : Aucun impact packaging prod (Flask same-origin), mais si développeur lance new frontend en dev sans proxy, il croit que front/back cassé alors que c'est config Vite. À documenter comme régression packaging/V2.

---

## 16. Niveau de gravité

- **P0 BLOQUANT** : 0 — connexion prod OK, backend 350 verts, Flask serving OK
- **P1 MAJEUR** : 1 — `vite.config.ts` new V2.3 sans proxy `/api` → dev broken `Failed to fetch`
- **P2 MINEUR** : 0
- **P3 INFORMATION** : 2 — `dist/` non persisté snapshot (NON VÉRIFIÉ sans build), `pystray/pillow` hors runtime serveur mais dans requirements (pas de lien connexion)

**Gravité globale** : P1 MAJEUR (dev only), pas bloquant prod/packaging.

---

## 17. Corrections recommandées (décrire uniquement, NE PAS APPLIQUER)

### Correction P1-001 — Ajouter proxy Vite dans nouveau frontend

**Fichier** : `XMLForge_FrontRedesign/vite.config.ts`

**Recommandation** : Ajouter section `server.proxy` identique à old frontend :

```ts
server: {
  host: '0.0.0.0',
  allowedHosts: true,
  proxy: {
    '/api': {
      target: 'http://localhost:5000',
      changeOrigin: true,
    },
    '/socket.io': {
      target: 'http://localhost:5000',
      ws: true,
      changeOrigin: true,
    },
  },
},
```

**Justification** : Permet dev `localhost:5173` → `/api` → Flask `5000` sans CORS, même comportement old frontend, pas de modification backend, pas de nouvel endpoint, pas de mock, conserve `/api` relative pour prod same-origin.

**Alternative** : Documenter `VITE_API_URL=http://localhost:5000/api` dans `.env.development` pour dev new V2.3, mais proxy reste plus simple et évite CORS.

**Ne pas faire** : Ne pas changer `API_URL` en absolu `http://localhost:5000/api` en dur dans `client.ts` — casserait prod same-origin (Flask 5000 sert dist, même origine). Garder `/api` relative + proxy dev.

### Vérification après correction

- `npm run dev` new V2.3 → Login → GET `/api/databases` → 200 avec JWT → Dashboard bases réelles OK
- `npm run build` → `dist/index.html` singlefile 461KB → Flask serving → GET `/` 200 html V2.3, GET `/api/databases` 401 sans auth / 200 avec auth → OK
- Backend tests 350 passed inchangés

---

## 18. Verdict

**Verdict : FRONT/BACK CONNECTED WITH ISSUES**

- **CONNECTED en production** : Flask 5000 sert dist (old multi-chunks et new V2.3 singlefile), `/api/*` → 404 JSON pas SPA, sensitive paths → 404 JSON, JWT réel, CRUD réel, XML/SQL réels, permissions réelles, 350 tests verts
- **CONNECTED en dev old** : Vite 5173 proxy /api → Flask 5000 → OK
- **WITH ISSUES en dev new V2.3** : proxy manquant dans `vite.config.ts` → dev broken Failed to fetch, P1 majeur dev only, 0 P0 bloquant prod

**Aucune donnée mock runtime**, **aucun fake endpoint**, **aucun SQLite**, **aucune régression backend** due au packaging — seul proxy Vite manquant dans nouveau frontend est la cause racine.

---

**Fin audit connexion — Prêt pour correction ciblée P1 proxy Vite**
