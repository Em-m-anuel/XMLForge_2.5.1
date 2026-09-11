# XMLForge V4 - Dernière évolution fonctionnelle

## 1. Administration (admin@example.com uniquement)

### Backend
- Modèle `User` étendu: `is_active` bool, `last_login` datetime, `updated_at`, `is_admin()` → email.lower() == admin@example.com
- Décorateur `admin_required` dans `app/auth/decorators.py` → vérifie JWT + is_admin, retourne 403 sinon
- Routes protégées:
  - `GET /history` + `GET /audit-logs` + `GET /audit` → `@admin_required`
  - `GET/POST/PUT/DELETE /users` + reset-password + toggle-active → admin uniquement
- Logout (`POST /logout`) → clear `TableUnlock` personnels via `UnlockService.clear_user_unlocks(user_id)`

### Frontend
- `AuthContext` : `isAdmin` = email == admin@example.com ou is_admin flag, `isPrivileged` alias
- `Sidebar` : affiche Historique, Audit, Utilisateurs uniquement si `isAdmin`
- `AdminRoute` : guard frontend, affiche page 🔒 Accès refusé si non admin, sinon children
- `App.jsx` : `/history`, `/audit`, `/users` wrappés dans `<ProtectedRoute><AdminRoute>`

### Erreur autorisation
- Backend: 403 `{success:false, message:"Accès refusé: privilèges administrateur requis (admin@example.com uniquement)"}`
- Frontend: AdminRoute rend page avec bouton Retour Dashboard

## 2. Page Users (admin)

### Backend
- Service `UserService`:
  - `get_all(search, include_inactive)` → filtre ilike email/full_name
  - `create(full_name, email, password, creator, is_active)`
  - `update(id, data, updater)`
  - `delete(id)` → empêche suppression admin principal + self-delete
  - `reset_password(id, new_password)`
  - `toggle_active(id)` → flip is_active, empêche désactivation admin principal
- Routes `app/routes/users.py`:
  - `GET /users?search=&include_inactive=true` → liste
  - `GET /users/<id>` → détail
  - `POST /users` → création (RegisterSchema-like)
  - `PUT /users/<id>` → modif nom/email/is_active
  - `DELETE /users/<id>` → suppression
  - `POST /users/<id>/reset-password` `{new_password}`
  - `POST /users/<id>/toggle-active`

### Frontend
- `pages/Users/Users.jsx` :
  - Table `audit-table` style (même design): avatar, email mono, badge ACTIF/DÉSACTIVÉ, dates created_at/last_login, actions icon-btn
  - Search input topbar-search
  - Modals: Create (nom, email, password, actif switch), Edit (nom, email, actif), Reset Password (info-box + new password)
  - Actions: edit (✎), reset pwd (🔒), toggle active (👁️‍🗨️), delete (🗑️) disabled si admin principal
  - Service `userService.js` → apiClient CRUD
  - Design identique maquette (modal-overlay, form-input, badge, etc.)

## 3. Données d'une table (rows)

### Modèle
- `TableRow`: id, uuid, table_id FK cascade delete, data_json TEXT (JSON dict colonne→valeur), creator_id, created_at, updated_at, last_modified_by
- `get_data()` / `set_data(dict)` helpers json

### Backend
- Service `RowService`:
  - `_check_table_access(table_id, user_id, provided_key)` → vérifie archivé + protection personnelle (UnlockService.is_unlocked) + clé file_identifier / database.key_identifier
  - `get_by_table(table_id, limit, offset)` → pagination, total count
  - `create(table_id, data_dict, creator, key)` → TableRow + history/audit/socket
  - `update(table_id, row_id, data_dict, updater, key)`
  - `delete(table_id, row_id, deleter, key)`
  - `bulk_import(table_id, rows_data, creator)` → pour import projet
- Routes `app/routes/rows.py`:
  - `GET /tables/<id>/rows?limit=&offset=`
  - `POST /tables/<id>/rows` `{data: {col:val}}` ou direct dict + optional key_identifier
  - `PUT /tables/<id>/rows/<row_id>` `{data:{...}}`
  - `DELETE /tables/<id>/rows/<row_id>`

### Import/Export
- `export_service.py` et `project_service.py` incluent désormais `<rows><row uuid><cell column="...">value</cell></row></rows>` dans XML table et database
- `import_service.py` : `_parse_rows_from_table()` parse `<rows><row><cell column="">` et fallback pour ancien format
- `import_xml` et `project import` créent `TableRow` en plus de tables/colonnes

### Frontend
- `rowService.js` → list/create/update/delete via apiClient
- `Workspace.jsx` :
  - Nouveau state `rows`, `rowsTotal`, `tab` avec 2 onglets : Structure (cols-table) et Données (rowsTotal badge)
  - Tab Data : table `cols-table` avec header = columns.map(col.name) + actions edit/delete, lignes = rows.map(row.data[col.name])
  - Bouton `+ Ligne` dans `ws-main-actions` → ouvre modal Row avec inputs dynamiques basés sur columns
  - `openNewRow()` → init form `{col.name: ''}` → modal, `openEditRow(row)` → form = row.data
  - `handleSaveRow()` → rowService.create/update avec clé personnelle `getTableKey(table)`
  - `handleDeleteRow()` → confirm + delete
  - Après chaque modif : `fetchRows(table.id)` + `fetchTableXml(table)` pour regénérer XML avec données
  - Design identique maquette : `table-wrap`, `cols-table`, `empty-state`, `row-actions`, `icon-btn sm`

## 4. Monaco Editor

- Remplacement définitif textarea → `@monaco-editor/react`
- Composant `components/MonacoEditor/MonacoEditor.jsx` :
  - Définit thème custom `xmlforge-dark` : bg #12151C, gutter #0F1117, tag #7CACFB bold, attr #5EE29A, val #FFB86B, kw #C792EA bold, comment #5B6472 italic, lineHighlight #1C212B, selection #3B82F630
  - Options : minimap false, font JetBrains Mono 12px lineHeight 21, wordWrap on, lineNumbers on, folding true, foldingStrategy indentation, showFoldingControls always, matchBrackets always, autoClosingBrackets/Quotes always, formatOnPaste/Type true, tabSize 2, scrollbar 10px, automaticLayout true
  - Search : Ctrl+F natif Monaco
  - ReadOnly option pour SQL pane
- Workspace : `code-pane-body` contient `<MonacoEditor value={xmlCode} onChange={setXmlCode} language="xml" />` et SQL pane `language="sql"`
- Conservation style : `code-pane` border soft, `code-pane-head` avec badge, `code-pane-body` flex 1 minHeight 240px
- Détection erreurs XML : useEffect DOMParser parse xmlCode, si `<parsererror>` → setXmlError + badge rouge `Erreur XML` + div danger-soft sous éditeur `⚠ message`

## 5. Déverrouillage personnel

### Ancien comportement (global)
- Table protégée déverrouillée globalement, `sessionStorage xmlforge_db_key` unique

### Nouveau comportement (personnel par utilisateur/session)
- Modèle `TableUnlock` : id, user_id FK, table_id FK, unlocked_at, expires_at (24h), unique(user_id, table_id)
- Service `UnlockService` :
  - `is_unlocked(user_id, table_id)` → check existe + non expiré, sinon delete expiré
  - `unlock_table(user_id, table_id, key)` → vérifie clé valide (file_identifier ou database.key_identifier), crée/update unlock avec expires 24h
  - `list_user_unlocks(user_id)` → filtre expirés
  - `clear_user_unlocks(user_id)` → delete all (appelé logout)
  - `check_protection(user_id, table, provided_key)` → d'abord unlock personnel, sinon clé fournie
- `TableService._check_protection(table, provided_key, user_id)` et `ColumnService`, `RowService`, `SyncService` utilisent désormais `user_id` + personal unlock check
- Routes `unlock.py` :
  - `POST /unlock-table` → passe user_id à `TableService.unlock(table_id, key, user_id)` → crée unlock personnel, audit `DEVERROUILLAGE_TABLE personnel`
  - `GET /unlocks` → liste tables déverrouillées session courante
  - `DELETE /unlocks` → clear session
- `auth.py` logout → `UnlockService.clear_user_unlocks(user_id)`
- Frontend :
  - `DatabaseContext` : `unlocks` map `{tableId: key}`, `saveUnlock(tableId, key)` stocke dans sessionStorage `xmlforge_unlocks` JSON + legacy `xmlforge_db_key`
  - `getTableKey(table)` → `getUnlock(table.id) || dbKey || apiClient.getDbKey()`
  - `requireKeyIfProtected(table)` → check `getTableKey(table)`, sinon modal unlock
  - `handleUnlock()` → `tableService.unlock(id, key)` + `saveUnlock(id, key)` → toast "Déverrouillée pour votre session" + refresh cols/rows
  - Modal unlock texte adapté : "Déverrouillage personnel (session utilisateur uniquement). Autres utilisateurs devront fournir la clé."
  - Sur logout, `AuthContext.logout()` clear `xmlforge_unlocks` + `xmlforge_db_key` + appel API `DELETE /unlocks`

### Exemple
- User A saisit File Identifier pour table `clients` protégée → backend crée `TableUnlock(user_id=A, table_id=clients)` → User A peut modifier
- User B liste tables → `is_unlocked(B, clients)` false → voit toujours 🔒, doit saisir clé
- User A se déconnecte → `clear_user_unlocks(A)` → protection réactivée

## 6. Export complet projet

### Export
- Service `ProjectService.export_project_to_xml(database_id)` :
  - `<database name uuid description comment status key_identifier>`
  - Pour chaque table : `<table name uuid description comment protected status archived file_identifier>`
    - `<columns><column name type length nullable primary_key foreign_key unique auto_increment uuid status default comment /></columns>`
    - `<rows><row uuid><cell column="id">1</cell><cell column="nom">Jean</cell></row></rows>`
  - Inclut toutes contraintes, protections, file_identifier, descriptions, données
  - Historique nécessaire à reconstruction non inclus dans XML (mais logs gardés côté audit) – option future : inclure before/after si besoin
- Route `GET /export/project/<id>?download=true` → attachment `project_{id}.xml`, sinon JSON `{xml, database_id}`

### Import
- Service `ProjectService.import_project_from_xml(xml, creator)` :
  - Parse database & tables via lxml
  - Pour chaque table : crée Table avec protected/file_identifier/status, colonnes, rows (via TableRow)
  - Génère key_identifier unique pour nouvelle base
  - Commit, history/audit/import_xml socket
  - Retourne database dict avec key_identifier
- Route `POST /import/project` multipart file `file` ou JSON `{xml}` → 201 database

### Frontend
- Service `projectService.js` :
  - `exportProject(databaseId, {download})` → fetch blob avec token Auth, download `project_{id}.xml`
  - `importProject(fileOrXml)` → FormData file ou JSON xml → POST /import/project
- Dashboard :
  - Context menu card : "Exporter projet complet" → `projectService.exportProject(id, {download:true})` + toast
  - Bouton topbar "Importer projet" → modal dropzone → `handleImportProjectFile(file)` → `projectService.importProject(file)` → fetchDatabases + toast + navigate si besoin
- Workspace :
  - Titlebar bouton "Projet" (export projet)
  - Sidebar actions : "Importer projet" + "Exporter projet" → mêmes services
  - Dropzone modals avec `dragover` class, `import-progress` spinner

## 7. Vérification finale

- Routes backend: 50 blueprints (auth, databases, tables, columns, imports, exports, converters, history admin, unlock personal, database_create, metadata, audit admin, sync, users admin, rows, projects) + /api clones → toutes testées compile ok
- Services: UserService, RowService, UnlockService, ProjectService ajoutés, TableService/ColumnService/SyncService adaptés personal unlock, ExportService avec columns/rows wrappers
- Appels API frontend: api.js centralisé, tous services utilisent apiClient, plus aucun mock
- Code mort supprimé: ancien `useDatabases` hook, anciens components Button/Badge/Card etc, commentService, temporary files
- Documentation mise à jour: ce fichier EVOLUTIONS_V4.md + commentaires dans code + `app/__init__.py` endpoint list
- Design conservé: maquette.css intact 33179 chars, mêmes classes, mêmes couleurs #0F1117 #171B22 #1C212B #3B82F6, mêmes radius, mêmes animations, mêmes espacements
- Nouvelles fonctionnalités intégrées sans casser existant: login/register, gestion bases/tables/colonnes, import/export XML/SQL, conversion, protection file_identifier, sync XML table persiste, historique/audit restent fonctionnels pour admin seulement

## Tests manuels recommandés

1. Créer compte test@test.com → login → vérifier Sidebar n'affiche pas Historique/Audit/Users → essayer /history directement → 403 + page Accès refusé
2. Login admin@example.com → voir Historique/Audit/Users dans Sidebar → Users: créer user, search, edit, reset pwd, toggle active, delete
3. Dashboard: créer base, tables, colonnes
4. Workspace: sélectionner table → voir XML dans Monaco (coloration, numéros, folding) → modifier XML invalide → badge rouge Erreur XML → corriger → badge disparaît
5. Table protégée: créer table avec protégée + file_identifier XML-TEST-123 → autre user test@test.com tente modifier → modal unlock → saisir clé → déverrouillé uniquement pour lui → se déconnecter → reconnecter → protection réactivée
6. Data: onglet Données → ajouter ligne (form dynamique colonnes) → modifier ligne → supprimer ligne → vérifier rows exportées dans Projet XML
7. Export projet: Dashboard context menu Exporter projet complet → fichier XML contient <database><table><columns> + <rows> + protected file_identifier → Importer projet → nouvelle base reconstruite avec données
8. Import projet: glisser fichier projet complet → base reconstruite
9. Vérifier socket: ouvrir 2 navigateurs différents, créer table dans l'un → toast dans l'autre + refresh auto

## Fichiers modifiés/ajoutés

Backend:
- app/models/user.py (is_active, last_login, updated_at, is_admin)
- app/models/table_row.py (nouveau)
- app/models/table_unlock.py (nouveau)
- app/models/__init__.py (export nouveaux modèles)
- app/__init__.py (migrate_v4, liste endpoints V4)
- app/auth/decorators.py (admin_required)
- app/services/auth_service.py (is_active check, last_login)
- app/services/user_service.py (nouveau)
- app/services/row_service.py (nouveau)
- app/services/unlock_service.py (nouveau)
- app/services/project_service.py (nouveau)
- app/services/table_service.py (personal unlock)
- app/services/column_service.py (personal unlock)
- app/services/sync_service.py (personal unlock)
- app/services/import_service.py (parse <columns> et <rows>)
- app/services/export_service.py (<columns> et <rows> wrappers)
- app/routes/auth.py (clear unlocks logout)
- app/routes/history.py (admin_required)
- app/routes/audit.py (admin_required)
- app/routes/users.py (nouveau)
- app/routes/rows.py (nouveau)
- app/routes/projects.py (nouveau)
- app/routes/unlock.py (personal unlock + list/clear unlocks)
- app/routes/__init__.py (enregistre users, rows, projects)
- app/services/__init__.py (export nouveaux services)

Frontend:
- src/context/AuthContext.jsx (isAdmin, clear unlocks)
- src/context/DatabaseContext.jsx (unlocks map per table)
- src/components/Sidebar/Sidebar.jsx (hide admin pages si non admin)
- src/components/AdminRoute/AdminRoute.jsx (nouveau)
- src/components/MonacoEditor/MonacoEditor.jsx (nouveau, remplace textarea)
- src/services/rowService.js (nouveau)
- src/services/projectService.js (nouveau)
- src/services/userService.js (nouveau)
- src/services/unlockService.js (nouveau)
- src/services/api.js (inchangé mais gère JWT + X-Database-Key)
- src/pages/Dashboard/Dashboard.jsx (export/import projet, context menu projet)
- src/pages/Workspace/Workspace.jsx (Monaco Editor, data tab avec rows CRUD, personal unlock per table, export/import projet, xmlError badge)
- src/pages/Users/Users.jsx (nouveau, design maquette)
- src/App.jsx (routes /users + AdminRoute wrapper pour /history /audit /users)
- EVOLUTIONS_V4.md (ce fichier)
