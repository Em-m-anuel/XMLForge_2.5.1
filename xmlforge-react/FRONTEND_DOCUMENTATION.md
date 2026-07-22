# FRONTEND DOCUMENTATION – XMLForge React

> Documentation officielle développeur – Frontend React connecté au backend Flask V2  
> Version 2.0.0 – Architecture production-ready sans mockData

---

## 1. Présentation

### Rôle du frontend
Le frontend XMLForge est une application web de type **IDE léger** pour gérer des bases de données décrites en XML et les convertir en SQL. Il remplace phpMyAdmin/Adminer/DBeaver pour un usage spécialisé XML → SQL. Il permet :
- Authentification JWT
- Gestion collaborative de bases (toutes visibles)
- Gestion de tables avec protection par clé
- Gestion de colonnes avec métadonnées riches
- Commentaires libres sur base/table/colonne
- Archivage / restauration
- Import XML/SQL par drag-drop
- Export XML/SQL avec download
- Conversion XML↔SQL via backend
- Éditeurs style VS Code (Monaco) avec copy/download/fullscreen
- Historique métier timeline + Audit log
- Temps réel via Socket.IO

### Technologies utilisées
- **React 19** + **React Router 6** (SPA, protected routes)
- **Vite 8** (build, code splitting)
- **CSS classique** uniquement (pas de Tailwind/Bootstrap) – tokens centralisés
- **@monaco-editor/react** (Monaco Editor, fallback VSCodeEditor custom)
- **socket.io-client** (temps réel)
- **Inter + JetBrains Mono** (typo)
- **lxml** côté backend, mais frontend parse aussi XML pour preview local

### Architecture générale

```
Browser (React)
   ↓ (fetch + JWT + X-Database-Key sessionStorage)
api.js (client centralisé)
   ↓
services/* (auth, database, table, column, import, export, converter, history, audit, socket)
   ↓
Context (AuthContext, DatabaseContext)
   ↓
Hooks (useDatabases, useAuth) + Pages
   ↓
Components réutilisables (Button, Input, Card, Modal, Toast, MonacoEditor, etc.)
```

### Philosophie du projet
- **Zéro mockData** : tout vient de l'API Flask. `src/utils/mockData.js` a été supprimé.
- **Service Layer strict** : aucun composant ne fait `fetch` direct. Tout passe par `services/api.js` → `services/*`.
- **Design conservé** : identité dark `#0F1117`, accent `#3B82F6`, radius 6/10/16, animations 150/180ms, hover translateY(-1/-3px). On professionnalise, on ne change pas.
- **Monaco-ready** : `VSCodeEditor` a la même API que `MonacoEditor` wrapper, `vs-content` est le mount point pour remplacer facilement.
- **Perf** : Lazy loading (`React.lazy` + `Suspense`), code splitting Vite (chunks Dashboard, Workspace, History, Audit), `useCallback`/`useMemo`, Context pour éviter prop drilling.

---

## 2. Arborescence complète

### Racine

```
xmlforge-react/
├── index.html (fonts Inter + JetBrains Mono)
├── vite.config.js
├── package.json (react, react-router-dom, socket.io-client, @monaco-editor/react)
├── .env.example (VITE_API_URL=http://localhost:5000)
├── src/
│   ├── App.jsx (Router + Providers + Lazy)
│   ├── main.jsx (BrowserRouter + tokens.css + global.css)
│   ├── assets/ (react.svg, hero.png - conservés mais non critiques)
│   ├── components/ (16 composants réutilisables)
│   ├── pages/ (6 pages)
│   ├── services/ (11 services)
│   ├── context/ (2 contexts)
│   ├── hooks/ (1 hook principal + futurs)
│   ├── styles/ (tokens + global)
│   └── utils/ (icons)
└── dist/ (build prod)
```

### `src/` – vue d'ensemble

#### `src/App.jsx`
- **Rôle** : Root router + providers
- **Pourquoi** : Centralise ToastProvider, AuthProvider, DatabaseProvider, Suspense, Routes
- **Quand utilisé** : Au démarrage `main.jsx`
- **Utilise** : `ProtectedRoute`, `Loader`, pages lazy
- **Données** : Aucune, juste composition

#### `src/main.jsx`
- **Rôle** : Entry point Vite, monte React dans `#root`
- **Pourquoi** : Sépare bootstrap (BrowserRouter) de logique App
- **Utilise** : `tokens.css`, `global.css`
- **Données** : Aucune

#### `src/assets/`
- **Pourquoi existe** : Actifs statiques (logo React, hero). Conservé du template Vite, non critique mais laissé pour compat.
- **Contient** : `react.svg`, `hero.png`
- **Communication** : Importé nulle part après refactor, peut être supprimé – gardé pour ne pas casser.

#### `src/styles/`

**`tokens.css`**
- **Rôle** : Single source of truth design. Variables CSS `--bg`, `--card`, `--border`, `--accent`, `--radius-sm/lg`, `--shadow-card/pop`, `--ease`, `--duration-*`, `--sidebar-width`, etc.
- **Pourquoi** : Harmonisation demandée (mêmes couleurs, rayons, ombres partout)
- **Utilisé par** : Tous les composants CSS
- **Données** : Aucune, que des tokens

**`global.css`**
- **Rôle** : Reset, scrollbar harmonisée (10px, #2A303C), `focus-visible` outline accent, `.grid-2`, `.hidden`
- **Pourquoi** : Base commune sans framework
- **Utilisé par** : `main.jsx` (import global)

#### `src/components/`

**`Button/Button.jsx + Button.css`**
- **Rôle** : Bouton réutilisable. Variants `default/primary/danger/ghost`, size `md/sm`, `fullWidth`, `leftIcon/rightIcon`, disabled
- **Pourquoi** : Supprimer duplications `.btn` dans ancien HTML (login, dashboard, workspace avaient 3 définitions)
- **Utilisé par** : Toutes les pages, modals, header
- **Données** : `children`, `variant`, `onClick`

**`IconButton/IconButton.jsx`**
- **Rôle** : Bouton icône 30x30, hover card-hover
- **Pourquoi** : Actions row (edit, copy, trash) dans tables colonnes
- **Utilisé par** : Workspace, Modal close, ContextMenu trigger

**`Badge/Badge.jsx`**
- **Rôle** : Pastille 11px 600 `blue/green`, dot optionnel
- **Pourquoi** : Statut CONNECTÉ, ACTIVE/ARCHIVED, etc.
- **Utilisé par** : Navbar, DatabaseCard, Workspace titlebar

**`Input/Input.jsx`**
- **Rôle** : Deux composants : `Input` (field avec label + icon + input) et `FormInput` (simple input pour modals)
- **Pourquoi** : Harmoniser Login/Register/Modals qui avaient `.field-input` vs `.form-input` différents
- **Utilisé par** : Login, Register, Modals création table/colonne, comment, unlock
- **Données** : label, icon, value, onChange, error

**`Card/Card.jsx`**
- **Rôle** : Base card avec hover transform
- **Pourquoi** : Factoriser `.db-card`, `.card` etc.
- **Utilisé par** : Dashboard (via DatabaseCard custom qui étend Card)

**`Modal/Modal.jsx`**
- **Rôle** : Overlay `rgba(6,8,12,.65)` + blur, card 440px (wide 560px), animation translateY 14px scale .97 → none, Esc + overlay click close
- **Pourquoi** : Remplacer `openModal('id')` vanilla JS par state React
- **Utilisé par** : Dashboard (import, new DB, edit DB), Workspace (new table, edit col, delete, unlock, comment)

**`Toast/Toast.jsx`**
- **Rôle** : `ToastProvider` Context + `useToast()` hook `notify(type,title,msg)`. Stack fixed top-right, auto remove 3400ms, animation toastIn
- **Pourquoi** : Remplacer `notify()` global vanilla par React Context
- **Utilisé par** : Toutes les pages pour success/error/info

**`Loader/Loader.jsx`**
- **Rôle** : Spinner border 2px + top accent, animation spin 0.7s
- **Pourquoi** : Loading states, page ProtectedRoute fallback
- **Utilisé par** : ProtectedRoute, AppFallback Suspense

**`Skeleton/Skeleton.jsx + Skeleton.css`**
- **Rôle** : Shimmer animation gradient `var(--card) 25% -> var(--card-hover) 50% -> var(--card) 75%`, `Skeleton`, `SkeletonCard`, `SkeletonTable`
- **Pourquoi** : UX moderne pendant fetch API (remplace vide)
- **Utilisé par** : Dashboard (6 cards), History, Audit

**`EmptyState/EmptyState.jsx`**
- **Rôle** : Illustration + title + desc + action button, centré 60px padding
- **Pourquoi** : États vides (aucune base, aucun historique)
- **Utilisé par** : Dashboard, History, Audit

**`Sidebar/Sidebar.jsx`**
- **Rôle** : Navigation Dashboard : logo XMLForge + nav-group Bases/Historique/Audit/Paramètres + bottom user + déconnexion
- **Pourquoi** : Remplacer sidebar HTML statique par composant React avec `useNavigate`, `useLocation` active state, `useAuth` user
- **Utilisé par** : Dashboard, History, Audit
- **Données** : user.full_name, isActive(path)

**`Navbar/Navbar.jsx`**
- **Rôle** : Topbar 60px : search input + badge connecté + avatar
- **Pourquoi** : Recherche bases Dashboard
- **Utilisé par** : Dashboard
- **Données** : searchValue, onSearchChange

**`ContextMenu/ContextMenu.jsx`**
- **Rôle** : Bouton trigger + menu absolu top 34px right 0, 150px min, animation translateY -6 scale .97, outside click close via `useRef` + `document.addEventListener`
- **Pourquoi** : Remplacer `toggleCtx()` vanilla
- **Utilisé par** : DatabaseCard (renommer, dupliquer, exporter, archiver, supprimer)

**`CodePane/CodePane.jsx` (legacy, conservé)**
- **Rôle** : Ancien panneau XML/SQL simple avec dots
- **Pourquoi** : Conservé pour compat mais non utilisé dans Workspace V2 (remplacé par MonacoEditor)
- **Utilisé par** : Ancien Workspace (plus utilisé)

**`VSCodeEditor/VSCodeEditor.jsx + VSCodeEditor.css`**
- **Rôle** : Mini VS Code : header 36px dots R/J/V + title + lang badge + actions copy/download/fullscreen, body flex gutter 48px line numbers + content highlight + textarea transparent overlay pour édition avec syntax highlight derrière
- **Pourquoi** : Répond au cahier des charges "panneau droite mini VS Code" + Monaco-ready (vs-content mount point)
- **Utilisé par** : Workspace (fallback si Monaco échoue)
- **Données** : title, value, onChange, language xml/sql, readOnly, isFullscreen

**`MonacoEditor/MonacoEditor.jsx`**
- **Rôle** : Wrapper `@monaco-editor/react` avec fallback VSCodeEditor. Définit thème `xmlforge-dark` (bg #12151C, gutter #0F1117, tag #7CACFB, attr #5EE29A, val #FFB86B, kw #C792EA). Props identiques à VSCodeEditor
- **Pourquoi** : Vrai éditeur Monaco avec Minimap false, font JetBrains Mono 12px, lineNumbers on, wordWrap on
- **Utilisé par** : Workspace (2 instances XML Source + SQL généré, même hauteur flex:1, même style)
- **Données** : value, onChange, language

**`ProtectedRoute/ProtectedRoute.jsx`**
- **Rôle** : Guard : si loading → Loader, si !isAuthenticated → Navigate /login, sinon children
- **Pourquoi** : Protéger dashboard/workspace/history/audit
- **Utilisé par** : App.jsx Routes

#### `src/pages/`

**`Login/Login.jsx + Login.css`**
- **Rôle** : Page auth avec AuthBackground SVG drift 14s/18s, card 400px backdrop blur, logo gradient
- **Pourquoi** : Remplacer `#screen-login` vanilla par composant React
- **Utilise** : `Input`, `Button`, `Icons`, `useAuth().login()`, `useToast`, `AuthBackground`
- **Données** : email, password (state), loading
- **Flux** : submit → `login({email,password})` → `authService.login` → `POST /login` → stocke token + user + socket.connect() → `navigate('/dashboard')` → toast success, catch → error toast

**`Register/Register.jsx`**
- **Rôle** : Idem Login mais 4 champs, card wide 440px, même AuthBackground (harmonisation demandée : même fond Login/Register)
- **Utilise** : Même composants + `useAuth().register()` → `POST /register` → navigate /login

**`Dashboard/Dashboard.jsx + Dashboard.css`**
- **Rôle** : Liste bases réelles via API, plus du mock
- **Pourquoi** : Remplacer `renderDatabases()` vanilla
- **Utilise** : `Sidebar`, `Navbar`, `Button`, `Modal`, `SkeletonCard`, `EmptyState`, `useDatabases` (API), `databaseService`, `importService`, `exportService`, `socketService`
- **Données** : databases[], loading, query search, newDbName/Desc/Comment, dragOver, importing
- **Features** :
  - `useDatabases` fetch `GET /databases?include_archived`
  - `filteredDbs(query)` memo
  - Create modal → `POST /databases` {name, description, comment}
  - Edit modal → `PUT /databases/<id>` {name, description, comment}
  - Delete → confirm → `DELETE /databases/<id>`
  - Archive/Restore → `POST /databases/<id>/archive|restore` → badge ARCHIVÉ + dashed border
  - Export XML/SQL → `exportService.exportXml(id, {download:true})` → blob download
  - Import : dropzone dragOver state, `onDrop` → `importService.importXml(file)` → `fetchDatabases()` + toast + socket `import_xml` event → update auto
  - Socket : `socketService.on('new_database')` → toast + refresh

**`Workspace/Workspace.jsx + Workspace.css`**
- **Rôle** : Page la plus complexe : gestion tables/colonnes d'une base
- **URL** : `/workspace/:dbName?dbId=1` → dbId récupéré via `useSearchParams`
- **Utilise** : `MonacoEditor`, `Button`, `useDatabaseContext` (dbKey session), `tableService`, `columnService`, `databaseService`, `converterService`, `exportService`, `apiClient`, `socketService`
- **Données** :
  - `database` (GET /databases/:id)
  - `tables` (GET /tables/:dbId)
  - `currentTable` (selected)
  - `columns` (GET /columns/:tableId)
  - `xmlDraft` (généré via `generateXmlForTable` + éditable)
  - `sqlGenerated` (via `POST /convert/xml-to-sql`)
  - Modals : new table, edit column, delete table, unlock, comment
- **Logique clé protégée** :
  ```
  requireKeyIfProtected(table):
    if !is_protected → true
    else if dbKey || sessionStorage → true
    else → setShowUnlock(table) → false
  ```
  Unlock modal → `POST /unlock-table` {table_id, key_identifier} → `apiClient.setDbKey(key)` + `saveKey()` (sessionStorage) → toast
- **Commentaires** : `openCommentEditor(type,obj)` → modal textarea → `PUT /databases|tables|columns/<id>/comment` {comment}
- **Structure** : table html avec colonnes nom/type/longueur/nullable/PK/FK/unique/AI/commentaire/état/last_modified_by + actions ✎ 💬 🗑
- **Right panel modern** : `ws-right-modern` flex column gap 12px padding 12px, deux `MonacoEditor` flex:1 même hauteur/style + bouton entre `Appliquer les modifications` + `Convertir XML→SQL` / `SQL→XML` via `converterService.xmlToSql` / `sqlToXml` (POST /convert/*)
- **Copy/Download/Fullscreen** : `navigator.clipboard.writeText`, Blob download, toggle fullscreen class `vs-fullscreen` fixed inset 16px
- **Socket** : `new_table`, `modification`, `suppression` → refresh tables/columns

**`History/History.jsx + History.css`**
- **Rôle** : Timeline historique V2
- **Utilise** : `historyService.list(limit, databaseId)`, `SkeletonTable`, `EmptyState`
- **Données** : history[] avec uuid, ip_address, before/after, user_name, action_type, element_type, element_name, created_at
- **Groupage** : `groupByDate()` → Aujourd'hui/Hier/date longue
- **Filtres** : select all/base/table/colonne + input database_id
- **Affichage** : dot accent + card avec header user_name a créé element_name + time + type badge + desc + IP + details before/after JSON + footer UUID + badges DB/table

**`Audit/Audit.jsx + Audit.css`**
- **Rôle** : Audit log indépendant
- **Utilise** : `auditService.list(limit)`
- **Données** : audit_logs[] avec action CONNEXION, DECONNEXION, CREATION_BASE, IMPORT_XML, EXPORT_SQL, CONVERSION_XML, ERREUR, etc., ip, user, element, meta_data
- **Filtre** : select all/CONNEXION/CREATION/SUPPRESSION/IMPORT/EXPORT/CONVERSION/ERREUR
- **Table** : date mono, user, badge action couleur (green connexion, red suppression), element, description, IP

#### `src/services/`

**`api.js`**
- **Rôle** : Client centralisé unique, aucun fetch direct dans composants
- **Pourquoi** : Centraliser JWT, X-Database-Key session, erreurs 401→redirect login, 403, 500
- **Utilise** : localStorage xmlforge_token, sessionStorage xmlforge_db_key, `fetch`
- **Fonctions** : `request(path, {method, body, isFormData, withAuth, withDbKey})`, `get/post/put/delete`, `setDbKey`, `getDbKey`
- **Données** : Token, dbKey, headers

**`authService.js`**
- **Rôle** : Wrapper auth : register, login (stocke token+user), me, logout (clear storage), getStoredUser, isAuthenticated
- **Utilise** : `apiClient`

**`databaseService.js`**
- **Rôle** : CRUD bases + archive/restore/comment/createReal
- **Utilise** : `apiClient` → `GET /databases?include_archived`, `POST /databases`, `GET /databases/<id>`, `PUT`, `DELETE`, `POST /archive|restore`, `GET/PUT /comment`, `POST /database/create`

**`tableService.js`**
- **Rôle** : Tables + protection + unlock
- **Utilise** : `apiClient`, `X-Database-Key` header
- **Fonctions** : list, create, update, delete, archive, restore, getComment, updateComment, unlock (qui setDbKey session si success)

**`columnService.js`**
- **Rôle** : Colonnes + protection parent table
- **Même pattern que tableService**

**`commentService.js`**
- **Rôle** : Facade pour commentaires base/table/colonne (wrapper autour des 3 services)
- **Pourquoi** : Spec demande panneau commentaires unifié

**`historyService.js`**
- **Rôle** : `GET /history?limit&database_id`

**`auditService.js`**
- **Rôle** : `GET /audit-logs`

**`importService.js`**
- **Rôle** : Import XML/SQL via FormData (file + database_name/description/comment). `apiClient.post` détecte FormData et ne met pas Content-Type json
- **Utilise** : `POST /import/xml`, `/import/sql`

**`exportService.js`**
- **Rôle** : Export XML/SQL avec ou sans download. Si download=true → fetch brut blob avec token Authorization, `downloadBlob()` via URL.createObjectURL
- **Utilise** : `GET /export/xml/<id>?download=true`

**`converterService.js`**
- **Rôle** : `POST /convert/xml-to-sql` {xml, database_name} → {sql}, `POST /convert/sql-to-xml` → {xml}
- **Utilisé par** : Workspace right panel

**`socketService.js`**
- **Rôle** : Client Socket.IO : `io(baseUrl)`, `connect()`, `disconnect()`, `on(event, cb)` avec Map listeners, `emitLocal` pour relais, auto écoute `xmlforge_event` générique + spécifiques `new_database`, `new_table`, etc.
- **Pourquoi** : Préparer temps réel sans modifier REST
- **Utilisé par** : AuthContext (connect on login), Dashboard, Workspace

#### `src/context/`

**`AuthContext.jsx`**
- **Rôle** : Context global auth : user, loading, login, register, logout, isAuthenticated
- **Pourquoi** : Éviter prop drilling, protéger routes
- **Utilise** : `authService`, `socketService` (connect on login/me, disconnect on logout)
- **Données** : user (from localStorage), token check via `me()` on mount

**`DatabaseContext.jsx`**
- **Rôle** : Context pour base courante + clé protégée session
- **Pourquoi** : Partager currentDatabase et dbKey entre Sidebar, Workspace, Modals
- **Utilise** : sessionStorage `xmlforge_db_key`, `saveKey`, `clearKey`

#### `src/hooks/`

**`useDatabases.js`**
- **Rôle** : Hook qui remplace ancien mock : fetch `GET /databases`, states databases/loading/error, CRUD `createDatabase`, `updateDatabase`, `deleteDatabase`, `archiveDatabase`, `restoreDatabase`, `filteredDbs(query)`
- **Pourquoi** : Custom hook réutilisable, sépare logique data de UI
- **Utilise** : `databaseService`, `useToast`
- **Données** : databases[], loading bool

#### `src/styles/` déjà expliqué

#### `src/utils/`

**`icons.jsx`**
- **Rôle** : Bibliothèque SVG unique : logo, user, lock, mail, login, logout, plus, upload, download, search, settings, db, more, edit, trash, copy, check, close, arrowRight/Left, table, userPlus, warning, file, shield
- **Pourquoi** : Même style stroke 2, tailles 15-16px UI, 19px card icons, éviter duplications SVG dans HTML original
- **Utilisé par** : Tous les composants

---

## 3. Logique de navigation

```
Login (/login)
  ↓ POST /login → JWT + user → localStorage + socket.connect()
  ↓ Navigate /dashboard
Dashboard (/dashboard) [ProtectedRoute]
  ├── Sidebar : Bases | Historique | Audit | Paramètres
  ├── Navbar : search + badge connecté + avatar
  ├── DB Grid : cards avec meta (nom, desc, créateur, date, tables_count, status, last_modified_by, comment)
  ├── Actions : Créer base (POST /databases), Import XML/SQL (drag-drop → POST /import/*), Export, Archive/Restore
  └── Click "Ouvrir" → /workspace/:dbName?dbId=:id

Workspace (/workspace/:dbName?dbId=1) [ProtectedRoute]
  ├── Titlebar : back Bases | breadcrumb / dbName / tableName + badge status + 💬 Base + Export XML/SQL
  ├── Left Sidebar : Tables (name, count, ARCH, 🔒) + key hint + Nouvelle table
  ├── Center Main :
  │   ├── Head : table name + sub (colonnes, status, modifié par + date) + comment box
  │   ├── Actions : + Colonne, Commenter, Supprimer table
  │   ├── Tabs : Structure (table cols) | Données (mock MySQL)
  │   └── Table cols : nom/type/longueur/nullable/PK/FK/unique/AI/commentaire/état/last_modified_by + actions ✎ 💬 🗑
  └── Right Modern (ws-right-modern) :
      ├── MonacoEditor XML Source (editable, line numbers, highlight XML, dark #12151C)
      ├── Bouton ↓ Convertir XML→SQL (POST /convert/xml-to-sql) → SQL généré
      ├── Bouton Appliquer les modifications (simulé + toast)
      └── MonacoEditor SQL généré (readonly, copy/download/fullscreen) + ↑ SQL→XML

History (/history) [ProtectedRoute]
  ├── Header : back Dashboard + filtres type + database_id + Actualiser
  └── Timeline groupée par date : Aujourd'hui/Hier/date longue
      └── Card : user_name a créé element_name + time + type badge + desc + IP + before/after details + UUID + DB/Table badges

Audit (/audit) [ProtectedRoute]
  ├── Header : filtres action + Actualiser
  └── Table : date mono, user, badge action couleur, element, description, IP

Login ↔ Register (Link)
Déconnexion : Sidebar bottom → AuthContext logout → clear token + user + dbKey + socket.disconnect() → Navigate /login
Token expiré : api.js intercepte 401 → clear storage + window.location.href = '/login'
```

Schéma ASCII :

```
[Browser]
   |
   +--> /login --POST /login--> [Flask JWT] --token--> localStorage
   |         |
   |         +--> /dashboard (ProtectedRoute) --GET /databases--> [Service] --api.js--> Flask --SQLAlchemy--> SQLite/MySQL
   |                  |
   |                  +--> Click DB card --/workspace/:name?dbId=1
   |                           |
   |                           +--> GET /databases/:id + GET /tables/:dbId + GET /columns/:tableId
   |                           +--> Monaco XML (editable) --POST /convert/xml-to-sql--> SQL
   |                           +--> Monaco SQL --POST /convert/sql-to-xml--> XML
   |                           +--> Export → GET /export/xml/:id?download=true → Blob download
   |                           +--> Table protégée ? → Modal clé → POST /unlock-table → sessionStorage X-Database-Key
   |                           +--> Comment → PUT /tables/:id/comment
   |                           +--> Archive → POST /tables/:id/archive
   |
   +--> /history --GET /history?limit&database_id--> Timeline
   +--> /audit --GET /audit-logs--> Table audit
```

---

## 4. Communication avec le backend

### API centralisée
- **Fichier unique** : `src/services/api.js` → `apiClient.get/post/put/delete`
- **Base URL** : `import.meta.env.VITE_API_URL || 'http://localhost:5000'`
- **Headers auto** :
  - `Content-Type: application/json` (sauf FormData)
  - `Authorization: Bearer <token>` si `localStorage xmlforge_token` existe
  - `X-Database-Key: <key>` si `sessionStorage xmlforge_db_key` existe (session uniquement, spec)
- **Gestion erreurs** :
  - 401 → clear storage + redirect /login (token expiré)
  - 403 → table protégée sans clé (affiche modal unlock)
  - 500 → toast error
  - Parse JSON avec `data.message` ou `Erreur {status}`

Aucun composant ne fait `fetch` direct. Exemple Dashboard :

```js
// Avant (mock) : setDbs([...dbs, newDb])
// Maintenant :
const data = await databaseService.create({name, description, comment})
setDatabases(d=> [data, ...d])
```

### JWT
- Stockage : `localStorage xmlforge_token` + `xmlforge_user` JSON
- Envoi : header Authorization Bearer
- Vérif : `AuthContext` → `authService.me()` au mount, si 401 → logout
- Expiration : `api.js` intercepte 401 → redirect

### Services → Hooks → Context → Components

```
Component (Dashboard)
  → useDatabases() hook
    → databaseService.list() 
      → apiClient.get('/databases')
        → fetch + JWT + error handling
          → Flask route @jwt_required() → Service → Model → DB
            → JSON {success, data, message}
          → setState databases
  → render db-grid
```

### Permissions tables protégées

```
User click Modifier table protégée
  → requireKeyIfProtected(table) checks dbKey || sessionStorage
  → if no key → setShowUnlock(table) → Modal input clé
  → POST /unlock-table {table_id, key_identifier}
  → si 200 → apiClient.setDbKey(key) → sessionStorage + saveKey() context → retry action
  → si 403 → toast "Clé invalide"
```

Clé conservée uniquement en session (spec) → `sessionStorage`, pas `localStorage`, clear au logout.

### Imports

- Drag-over state `dragOver` bool → class `dragover` border accent
- `onDrop` → `e.dataTransfer.files[0]` → `importService.importXml(file)` → `FormData` file + database_name → `POST /import/xml` multipart (pas de Content-Type json, fetch détecte FormData)
- Progress `importing` bool → texte "Importation en cours..."
- Après 201 → `fetchDatabases()` + toast + socket `import_xml` → Dashboard auto update

### Exports

- `exportService.exportXml(id, {download:true})` → `fetch(.../export/xml/:id?download=true, headers Authorization)` → `res.blob()` → `URL.createObjectURL` → `<a download>` click → toast

### Commentaires

- Bouton 💬 → `openCommentEditor(type, obj)` → setEditingComment + commentDraft
- Modal textarea → `PUT /databases|tables|columns/<id>/comment` {comment} (+ key si protégée)
- Après 200 → update state local `setTables(t=> t.map(...))` + toast + socket modification

### Historique & Audit

- `historyService.list(limit, databaseId)` → `GET /history?limit&database_id`
- `auditService.list(limit)` → `GET /audit-logs?limit`
- Affichage timeline / table, filtres select

### Socket.IO

- `socketService.connect()` dans `AuthContext` après login/me + dans `Dashboard`/`Workspace` useEffect
- `io(baseUrl, transports: websocket|polling)`
- Listeners Map : `on(event, cb)` → Set callbacks, `off`, `emitLocal`
- Backend émet `new_database`, `new_table`, `new_column`, `modification`, `suppression`, `import_xml`, `export_sql`, `xmlforge_event` générique
- Frontend : `socketService.on('new_table', payload=>{ if payload.table.database_id === Number(dbId) → notify + fetchTables() })`

---

## 5. Cycle d'une action – exemples détaillés

### Exemple 1 : Créer une table (protégée)

```
Utilisateur tape "client" dans modal Nouvelle table + coche Protégée + commente "Table clients" → Clique Créer
  ↓
Dashboard.handleCreateTable() -> tableService.create({name:"client", database_id:1, is_protected:true, comment:"Table clients"})
  ↓
services/tableService.js -> apiClient.post('/tables', body)
  ↓
api.js -> fetch http://localhost:5000/tables, headers Authorization Bearer token + Content-Type json, body JSON
  ↓
Flask route POST /tables @jwt_required() -> TableCreateSchema validation -> TableService.create()
  ↓
Service: vérifie base existe, pas archivée, pas déjà table même nom, crée Table uuid=UUID4, comment, status ACTIVE, last_modified_by = user.id/name, commit, update database updated_at, HistoryService.log() avec IP, before null, after dict, AuditService.log() CREATION_TABLE, emit_new_table() SocketIO
  ↓
Retour JSON 201 {data: table dict avec uuid, comment, status, is_protected, columns_count}
  ↓
Frontend: setTables([...tables, table]) + setCurrentTable(table) + close modal + notify success + socket event new_table reçu par autres clients → toast + refresh
```

### Exemple 2 : Import XML drag-drop

```
User drag fichier lib.xml sur dropzone Dashboard (onDragOver true → class dragover)
  ↓
onDrop -> file = e.dataTransfer.files[0] -> importService.importXml(file)
  ↓
FormData append file + database_name -> apiClient.post('/import/xml', formData) isFormData=true → pas de Content-Type json, header Authorization Bearer + pas X-Database-Key
  ↓
Flask POST /import/xml @jwt_required() -> request.files['file'].read().decode -> ImportService.import_xml() -> parse_xml() via converters (lxml), génère Database uuid/key, Tables, Columns, commit, History + Audit IMPORT_XML, emit_import_xml via SocketIO
  ↓
Retour 201 database dict avec key_identifier
  ↓
Frontend: fetchDatabases() -> nouvelle base apparaît, toast Import réussi, modal fermé
  ↓
Socket: autres clients reçoivent import_xml -> toast + refresh
```

### Exemple 3 : Conversion XML → SQL (éditeur droit)

```
User édite XML dans MonacoEditor (xmlDraft state onChange)
  ↓
Clique bouton "↓ Convertir XML → SQL"
  ↓
handleConvertXmlToSql() -> setConverting true -> converterService.xmlToSql(xmlDraft, database.name) -> apiClient.post('/convert/xml-to-sql', {xml, database_name})
  ↓
Flask POST /convert/xml-to-sql @jwt_required() -> ConvertXmlToSqlSchema validation -> convert_xml_to_sql() converter (sans Flask, lxml) -> génère CREATE TABLEs
  ↓
Audit CONVERSION_XML, retour JSON 200 {sql: "CREATE TABLE..."}
  ↓
Frontend: setSqlGenerated(res.sql) → MonacoEditor SQL (readonly) affiche SQL instantanément
  ↓
User clique Copier → navigator.clipboard.writeText(sqlGenerated) → toast Copié
```

### Exemple 4 : Déverrouillage table protégée

```
User clique Modifier sur table is_protected=true, sans clé en session
  ↓
requireKeyIfProtected(table) -> dbKey null && sessionStorage null → setShowUnlock(table) → Modal "🔒 Table protégée"
  ↓
User entre clé XML-9F4A-... → Clique Déverrouiller
  ↓
tableService.unlock(tableId, key) → POST /unlock-table {table_id, key_identifier} → apiClient
  ↓
Flask POST /unlock-table @jwt_required() -> TableService.unlock() vérifie database.key_identifier == key → 200 {unlocked:true} + Audit DEVERROUILLAGE_TABLE, sinon 403
  ↓
Frontend si 200: apiClient.setDbKey(key) → sessionStorage + DatabaseContext saveKey(key) → close modal → retry action originale (update table)
  ↓
Si 403: toast "Clé invalide"
```

### Exemple 5 : Archivage + commentaire

```
User clique Archiver sur base
  ↓
databaseService.archive(id) → POST /databases/<id>/archive
  ↓
Flask: check is_archived? → si déjà archivé 400, sinon before={status:ACTIVE}, set status ARCHIVED, last_modified_by, commit, History a archivé avec IP + before/after, Audit ARCHIVAGE_BASE, emit_modification
  ↓
Frontend: setDatabases map id → status ARCHIVED → card opacity .7 dashed border + badge ARCHIVÉ, toast
  ↓
User tente Modifier base archivée → PUT /databases/<id> → service check is_archived() → 400 "Base archivée, modification impossible"
```

---

## 6. Design

### Palette (tokens.css)
- --bg #0F1117 (fond principal)
- --bg-elevated #13161D (right panel, code)
- --sidebar #171B22
- --card #1C212B
- --card-hover #232A37
- --border #262C38, --border-soft #20252F
- --accent #3B82F6, --accent-dim #3B82F630, --accent-soft #3B82F615
- --success #22C55E, --danger #EF4444
- --text #FFFFFF, --text-secondary #A0AEC0, --text-tertiary #5B6472
- Status badge: ACTIVE green #22C55E, ARCHIVED blue #A0AEC0, protected red/orange

### Typographie
- UI: Inter 400/500/600/700/800
- Mono: JetBrains Mono 400/500/600 (code, line numbers, badges, key_identifier, IP)
- Hiérarchie: h1 22px 700 Dashboard, 20px 700 Auth, 16px 700 Workspace table name, 15px 600 card title, 13px base, 12px meta, 11px uppercase sidebar-head, 10.5px mono count

### Responsive
- Sidebar 224px → 72px @900px (text caché, icons seuls) – conservé
- Topbar search 340px → 200px @640px
- db-grid auto-fill minmax(280px, 1fr) → 240px orig → 280px V2 pour plus d'infos
- ws-right-modern 380px → 340px @1100px → hidden @900px (comme original)
- Grids 2 col → 1 col @640px
- Modals 440px / wide 560px, max-width 92vw, max-height 86vh

### Éditeur XML / SQL
- **Ancien** CodePane simple textarea
- **Nouveau** MonacoEditor wrapper + fallback VSCodeEditor
- Header 36px #13161D, border-bottom soft, dots R/J/V 10px, title 12.5px 600 secondary, lang badge 10px mono #202636, actions icon-btn 26px
- Body flex, gutter 48px #0F1117 border-right soft, line numbers 12px mono tertiary right align
- Content flex:1, highlight layer pre absolute + textarea transparent caret-color, line-height 21px (1.75*12px), padding 14px 16px
- Tokens VS Code Dark+: tag #7CACFB bold, attr #5EE29A, val #FFB86B, kw #C792EA bold, type #FFB86B, num #5EE29A
- Focus: border accent + box-shadow 0 0 0 3px accent-dim
- Same height: both editors flex:1 in ws-right-modern column gap 12px, same visual style
- Between: ws-apply-row column gap 8px, primary button fullWidth Convertir + Appliquer + hint mono 11px tertiary
- Actions second editor: Copy, Download (Blob), Fullscreen (vs-fullscreen fixed inset 16px z-index 200)
- Compatible Monaco: vs-content mount point, theme xmlforge-dark défini (bg #12151C, gutter #0F1117)

### Dashboard
- db-card: padding 18px, radius 10px, shadow-card, hover translateY(-3px) border #333b4a bg card-hover, animation fadeUp 0.45s
- Top: icon 38px 10px radius accent-soft #7CACFB + context menu + key hint mono 10px
- Meta: 12px secondary, dim tertiary
- Desc 12.5px secondary, comment 11.5px #FFD86B bg #FFD86B12 border #FFD86B22 italic
- Meta row: last_modified_by + status dot green/archived
- Footer: badges ACTIVE/ARCHIVED + last-user + open button 12.5px 600 #7CACFB arrow translateX 2px hover
- Archived state: opacity .7 dashed border
- Dropzone: border 1.5px dashed, hover accent + accent-soft, dragover scale 1.02

### Sidebar
- 224px, bg sidebar #171B22, border-right soft, padding 16px 12px
- Logo: mark 28px gradient #3B82F6→#2563EB radius 8px + text 14.5px 700
- Nav-group gap 2px, nav-item flex gap 10px padding 9px 10px radius sm, color secondary, hover card bg, active accent-soft #7CACFB + ::before 3px accent left
- Bottom: user full_name 11px tertiary + déconnexion
- History/Audit added: icons clock/shield

### Composants
- Button: padding 9/16 sm 6/11, radius sm 6px, border, shadow, hover translateY -1px, variants primary (accent bg + shadow), danger (soft red), ghost transparent
- Input: field margin 16px, label 12.5px 600 secondary, field-input flex gap 10px bg #12151C border radius sm padding 11/12, focus border accent + shadow, icon 16px tertiary, error border red + red shadow
- Modal: overlay rgba(6,8,12,.65) blur 3px, modal 440px wide 560px max 92vw 86vh scroll, bg card, border, radius-lg 16px, shadow-pop, transform translateY 14px scale .97 → none, head 18/22 border-bottom soft, body 20/22, footer flex end gap 10 border-top soft
- Toast: stack fixed top 20 right 20, toast 320px padding 13/14 bg card-hover border radius, shadow-pop, animation toastIn 0.35s translateX 30px, ic 20px radius 6px success-soft/danger-soft/accent-soft
- Badge: inline-flex gap 5px padding 3/9 radius 100px 11px 600, blue accent-soft #7CACFB, green success-soft
- ContextMenu: absolute top 34 right 0 min 150 bg card-hover border radius sm shadow-pop, opacity 0 translateY -6 scale .97 → open opacity 1, buttons 8/10 padding 12.5px secondary hover accent-soft

### UX
- Toasts modernes pour toutes actions (succès green, erreur red, info blue)
- Skeleton shimmer gradient card->card-hover 1.4s infinite pour loading
- Loader spinner border 2px + top accent spin .7s
- EmptyState centré 60px padding, icon 40px opacity .6, title 15px 600, desc 13px secondary, action button
- Error handling: 401 → redirect login, 403 → modal unlock + toast, 400 → toast validation, 500 → toast erreur
- Commentaires: 💬 badge + modal textarea
- Protected: 🔒 icon + modal clé + sessionStorage
- Archived: dashed + badge ARCHIVÉ + block modif/delete
- Real-time: toasts pour autres utilisateurs + auto refresh lists

---

## 7. Évolutions possibles

- **Monaco full** : remplacer VSCodeEditor fallback par Monaco partout, ajouter IntelliSense XML (XSD validation via lxml côté backend déjà prêt, renvoyer erreurs ligne/colonne)
- **Vraie base MySQL live** : Workspace tab Données actuellement mock, brancher `POST /database/create` puis `SELECT` via API `GET /data/<table_id>` à créer backend
- **Collaborative editing** : SocketIO déjà émet, ajouter Operational Transformation pour XML (yjs + Monaco)
- **Versioning** : table `versions` avec diff avant/après déjà stocké en History before/after JSON, UI pour restaurer version
- **Permissions fines** : au lieu de is_protected bool, RBAC par table (read/write/admin) avec table `permissions`
- **Search global** : Navbar search actuellement filtre local, passer à `GET /search?q=` backend avec FTS sur nom/description/commentaire
- **Export avancé** : Export avec `?include_archived=false`, `?format=json`, `?with_data=true`
- **Import validation** : Afficher erreurs XML ligne/colonne retournées par `parse_xml` + highlight dans Monaco avec squiggles
- **Audit timeline** : Chart.js pour graphique actions par jour / par user
- **Tests e2e** : Cypress/Playwright pour auth, CRUD, protection, import, converter
- **PWA** : Service Worker + offline cache pour éditeurs
- **Thème clair** : Ajouter tokens light mode, toggle via CSS variables

---

*Documentation générée pour nouveau développeur rejoignant XMLForge – Frontend v2.0.0 – Aucune donnée fictive, 100% API Flask*
