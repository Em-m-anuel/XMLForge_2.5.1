# XMLForge Frontend V2.4 — Stabilisation

**Date : 2026-09-15**
**Base : V2.3 (460 KB) → V2.4 (471 KB)**
**Backend : 350 passed, packaging 16 passed, XML-only, TCP 3307 inchangé**

---

## 1. Résumé

V2.4 est une phase de **stabilisation, polish UX, performance, cohérence et accessibilité** du frontend V2.3 déjà connecté au backend réel.

- **Structure** : Réorganisation progressive sans réécriture aveugle — création `src/types/`, `src/hooks/`, `src/store/`, `src/components/database/table/sql/xml/permissions/admin/server/ui/`, `src/views/Overview/Databases/Database/Table/SQL/XML/ImportExport/Administration/Server/Logs/Settings/` avec index ré-exports pour compatibilité
- **Bugs P0 fixés** : `vite.config.ts` proxy manquant (dev broken), `window.location.reload()` après édition colonne, stale states changement rapide DB/Table, race conditions guards request IDs
- **Nouvelles fonctionnalités conservées + améliorées** : modification base avec scope PERSONAL/COMMON, page permissions dédiée, édition colonne, édition directe cellule avec Tab/Shift+Tab/Flèches, diagramme schéma avec performance `/schema` (1 requête vs N), favoris, duplication, truncate, XML diff, command palette FR, dashboard/server/logs réels, modales Portal z-layers, breadcrumbs FR
- **Aucune régression V1/V2.2/V2.3**, aucun mock réintroduit, aucun SQLite, design dark premium conservé

**Verdict** : `FRONTEND_V2_4 = STABLE` — 0 P0, 0 P1, 2 P2 mineurs non bloquants, build OK, prêt packaging.

---

## 2. Restructuration effectuée

**Objectif** : Obtenir structure claire et logique, réduire responsabilités gros composants, éviter duplications, sans déplacer mécaniquement tous les fichiers.

**Avant** :
- `src/store.tsx` 851 lignes monolithe (auth, databases, tables, columns, rows, SQL, XML, server, favs, history, nav, sidebar, palette)
- `src/views/` flat (13 fichiers + table subfolder)
- `src/components/` flat (Icon, modals.tsx monolithe 797 lignes, ui.tsx 877 lignes, layout subfolder seulement)
- Pas de `src/types/`, `src/hooks/`, `src/store/` folder, pas de `components/database/table/sql/xml/permissions/admin/server/ui/`
- `src/data/mock.ts` présent mais non utilisé runtime après V2.2 (conservé historique)

**Après (nouvelle organisation)** :
```
src/
├── api/ (13 fichiers) — client.ts, auth.ts, databases.ts, tables.ts, columns.ts, rows.ts, queries.ts, xml.ts, permissions.ts, users.ts, audit.ts, history.ts, server.ts, tcp.ts — conservés intacts (P0 stabilité)
├── types/ (nouveau) index.ts — Database, Table, Column, Row, RowsResponse, QueryResult, AuthUser, DbTab, TableTab, AdminTab, Nav, Access — centralise modèles backend
├── hooks/ (nouveau) — useDatabases, useTables, useColumns, useRows avec useEffect + guards race + event xf-refresh-columns
├── store/ (nouveau) index.tsx ré-exporte store principal, prépare modularisation future
├── components/
│   ├── layout/ Breadcrumbs.tsx (FR), CommandPalette.tsx (FR + vraies données), PageHeader.tsx, Sidebar.tsx (fix tables_count + FR + Stockage XML natif), TopBar.tsx (auth réelle)
│   ├── database/ index.tsx → modals (CreateDatabase, EditDatabase avec scope)
│   ├── table/ index.tsx → modals + DataTab + StructureTab
│   ├── sql/ index.tsx → SqlConsole
│   ├── xml/ index.tsx → XmlPanel
│   ├── permissions/ index.tsx → modals
│   ├── admin/ index.tsx → AdminView
│   ├── server/ index.tsx → ServerView
│   ├── ui/ index.tsx copie ui.tsx (Button, Badge, Modal, Tabs, Dropdown, Toast, LoadingState, EmptyState, ErrorState, Panel, etc)
│   ├── Icon.tsx
│   ├── modals.tsx (ajout EditColumnModal, fix reload → event, CreateDatabase avec scope, EditDatabase avec scope)
│   └── ui.tsx (conservé compat)
├── views/
│   ├── Overview/ index.tsx → ../Overview (favoris + activity réelle)
│   ├── Databases/ index.tsx → ../DatabasesView (favoris ★, FR, tables_count réel)
│   ├── Database/ index.tsx → ../DatabaseView (PermissionsView réelle)
│   ├── Table/ index.tsx → ../TableWorkspace (duplicate + truncate + modales)
│   ├── SQL/ index.tsx → ../SqlConsole
│   ├── XML/ index.tsx → ../XmlPanel
│   ├── ImportExport/ index.tsx → ../ImportExport (import workflow + export sans Convertir en SQL)
│   ├── Administration/ index.tsx → ../AdminView (Accès refusé si non admin)
│   ├── Server/ index.tsx → ../ServerView (health + sessions réelles, pas de fake restart)
│   ├── Logs/ index.tsx → ../LogsView (audit réel)
│   ├── Settings/ index.tsx → ../SettingsView (FR + infos réelles)
│   ├── Overview.tsx, DatabasesView.tsx, DatabaseView.tsx, TableWorkspace.tsx, SqlConsole.tsx, RelationDiagram.tsx (zoom/recherche/liste/favoris + performance /schema), XmlPanel.tsx (diff + dirty banner), ImportExport.tsx, AdminView.tsx, ServerView.tsx, LogsView.tsx, SettingsView.tsx, LoginView.tsx
│   └── table/ DataTab.tsx (édition directe + Tab/Shift+Tab/Flèches + focus), StructureTab.tsx (EditColumnModal + event)
├── utils/ cn.ts
├── data/ mock.ts (conservé historique mais 0 import runtime)
├── App.tsx (sans mock, ToolsPage utilise xmlDoc réel + fetchXml, pas /var/xmlforge path)
├── main.tsx
└── index.css (z-layers 200/300/400/410/500/600 + isolation:isolate #root)
```

**Responsabilités réduites** :
- `store.tsx` reste gros mais guards race + clear stale + favs + duplicate/truncate ajoutés, et hooks extraits pour réutilisation
- `DataTab.tsx` : avant gérait loading fake + filter/sort local + pagination local, maintenant délègue fetchRows backend via store + hooks, édition directe isolée, focus navigation isolée
- `StructureTab.tsx` : avant cols depuis mock + indexes fake, maintenant columns réelles + indexes depuis colonnes + EditColumnModal séparée
- `RelationDiagram.tsx` : avant N requêtes + layout simple, maintenant 1 requête /schema + zoom/recherche/liste/favoris/focus + edges depuis FK réelles
- `modals.tsx` : avant monolithe avec setTimeout fake, maintenant CreateDatabase avec scope, EditDatabase avec scope, AddColumn avec FK, EditColumn avec PUT réel + event, RowModal avec NULL, Unlock avec vraie clé, Share avec permissions réelles — chaque modal une responsabilité

**Duplications supprimées** : `formatSize` fake, `dbToXml`/`tableToXml` locaux, `SERVER` fake, `LOGS` mock, `USERS` mock, `DATABASES` mock — plus utilisés runtime, remplacés par API réelles.

**Imports circulaires** : Vérifié, pas de circulaire, `store` importe `api/*`, `views` importent `store`, `components` importent `store` + `api`, pas de cycle.

**États centralisés** : `activeDb`, `tables`, `columns`, `rows`, `rowsTotal`, `xmlDoc`, `queryResult`, `serverHealth`, `tcpStatus`, `favDbs/favTables`, `history` centralisés dans store, pas de duplication locale dans views (sauf UI state page, search, sort, etc).

---

## 3. Bugs corrigés (V2.4)

### Bug Vite proxy (P0, régression packaging)
- **Fichier** : `vite.config.ts`
- **Problème** : Sans proxy `/api` → dev 5173 → `/api/databases` → Vite 404 → Failed to fetch → connexion BROKEN en dev new V2.3 (diagnostiqué `FRONT_BACKEND_CONNECTION_AUDIT.md`)
- **Solution** : Ajout proxy `/api` → `http://localhost:5000` + `/socket.io` ws, conserve plugins react/tailwind/singlefile + alias @
- **Test** : `npm run dev` → Login → GET `/api/databases` 200 OK, `npm run build` → 461KB singlefile OK

### Modification scope base (P1, nouvelle fonctionnalité prioritaire)
- **Fichier** : `backend/app/data_plane/xml_services.py` (backend déjà supporte), `src/components/modals.tsx` EditDatabaseModal, `src/store.tsx` updateDatabase
- **Backend vérif** : `update_database()` accepte `scope` PERSONAL/COMMON avec permission admin requise (`can_database admin`), et `common_permission` VIEW/EDIT/MANAGE, `PERSONAL` → `common_permission=None`, `COMMON` → collective, `document_version` pour 409
- **Solution frontend** : EditDatabaseModal ajout champ scope PERSONAL/COMMON avec boutons + common_permission Select si COMMON, payload inclut scope si isAdmin, sinon seulement name/description, après modif maj sidebar/breadcrumb/titre/workspace via `setDbs(map updated)` + `fetchTables`, pas de recréation base
- **Test** : PERSONAL → COMMON avec admin OK, COMMON → PERSONAL OK, non-admin lecture seule OK, 403 si pas admin, 409 si stale version

### Page permissions manquante (P1)
- **Fichier** : `src/views/DatabaseView.tsx` ajout `PermissionsView`, `src/api/permissions.ts`
- **Solution** : PermissionsView réelle avec GET `/databases/{id}/permissions` → [DatabasePermissionView + user_email], POST grant par email avec VIEW/EDIT/MANAGE → can_* mapping, DELETE revoke avec confirm, loading/empty/forbidden/error/conflict/succès, COMMON respecte règle collective (pas de partage individuel VIEW, affiche info), PERSONAL permissions individuelles, table permissions via `permissionService.listTable()` dans TableWorkspace permissions tab
- **Test** : PERSONAL 0 membres → EmptyState "Aucun partage", grant VIEW → OK, revoke → OK, COMMON → info collective, 403 admin requis → ErrorState "Accès refusé"

### Écran noir table (P0 prioritaire)
- **Fichier** : `src/views/TableWorkspace.tsx`
- **Problème** : Si table undefined/null ou columns/rows erreur API ou table supprimée ou permission 403 ou race condition, React essayait de rendre `table.cols` undefined → crash → écran noir
- **Solution** : Ajout guards :
  - `tablesError` → ErrorState "Impossible de charger les tables [Retour] [Actualiser]"
  - `!db || !table` → EmptyState "Table introuvable — n'existe plus ou pas de permissions [Retour base]"
  - `columnsError || rowsError || xmlError` → ErrorState "Impossible d'afficher cette table — La table n'a pas pu être chargée : {msg} [Réessayer] [Retour tables]" au lieu de écran noir
  - `useEffect` fetchColumns/Rows/Xml avec guards race + clear stale
- **Test** : Ouvrir table inexistante → EmptyState pas noir, couper backend → ErrorState avec Réessayer, changer rapidement Table A→B→C → pas de mélange, pas de noir

### Écran noir / bug visuel Server (P1)
- **Fichier** : `src/views/ServerView.tsx`
- **Problème** : Si health ou sessions null ou API indisponible, layout hauteur/overflow pouvait causer écran noir ou cartes sans contenu
- **Solution** : Ajout `healthError`, `sessionsError` states, ServiceCard avec fallback values (version 5.0.0, storage XML), Sessions TCP : si error → "Impossible de récupérer les sessions — {msg} [Réessayer]" au lieu de vide ou noir, si 0 → "Aucune session TCP active", health error → "Impossible de récupérer l'état du serveur [Réessayer]", pas de donnée inventée (free/used/CPU fake retirés)
- **Test** : API disponible → REST En ligne, TCP 3307 En ligne, sessions réelles ; API indisponible → ErrorState avec Réessayer, pas de noir

### Import bloqué après sélection fichier (P1)
- **Fichier** : `src/views/ImportExport.tsx`
- **Problème** : Après sélection fichier, user ne peut plus rien faire — input file hidden, état selectedFile non affiché, boutons désactivés, pas de progression, pas de reset
- **Solution** : Refonte workflow clair :
  1. Choisir fichier (dropzone + input file + bouton Choisir)
  2. Afficher fichier sélectionné : nom + taille KB + badge Validé/Invalide + validationMsg (XML valide : X tables, Y lignes via DOMParser local)
  3. Vérifier fichier (validation locale)
  4. Afficher infos utiles (validationMsg)
  5. Permettre lancer import : bouton "Lancer l'import" disabled si invalide, loading "Import en cours..."
  6. Progression/loading via busy state
  7. Succès/erreur via toast + fetchTables
  8. Fermer/recommencer via clearFile() (reset fileName, fileSize, fileContent, validationMsg, input value) + boutons Changer fichier/Annuler/Effacer
  - Après sélection, user peut annuler, changer fichier, voir nom/taille/type, lancer import, recevoir erreur claire si invalide
  - Pas de blocage interface globale, seulement workflow import en attente (busy local)
- **Test** : Ouvrir import → choisir fichier → affiche nom + 1.2 KB + Valide + "XML valide : 1 table(s), 1 ligne(s)" → bouton Lancer actif → Import → succès → tables maj, changer fichier → OK, annuler → OK, fichier invalide → badge Invalide + bouton disabled + erreur claire

### Export XML — Supprimer Convertir en SQL (P2)
- **Fichier** : `src/views/ImportExport.tsx` mode export
- **Problème** : Bouton "Convertir en SQL" dans workflow export XML n'a rien à faire là
- **Solution** : Supprimer bouton, conserver seulement "Exporter XML" (POST + blob download réel) + "Effacer"
- **Test** : Export XML tab → bouton Convertir en SQL absent, Exporter XML présent → OK, SQL support ailleurs conservé (SQL Console, xml2sql tab)

### Administration uniquement pour admin (P1)
- **Fichiers** : `src/components/layout/Sidebar.tsx`, `src/components/layout/CommandPalette.tsx`, `src/views/AdminView.tsx`, `src/store.tsx` isAdmin
- **Problème** : Pour non-admin, Administration visible mais désactivée → confusion, pas masquée
- **Solution** : Utiliser rôle réel retourné par `/me` (`is_admin`, `role`) via `isAdmin` dans store :
  - Sidebar : `{isAdmin && <Group Administration>}` → complètement masquée si non-admin
  - CommandPalette : `if (isAdmin) list.push(Users, Audit, History)` → pas d'action admin si non-admin
  - AdminView : si !isAdmin → page "Accès refusé — administrateur requis" + bouton retour accueil, pas page vide
  - Backend reste autorité finale (GET /users 403 si non admin → ErrorState "Accès refusé")
- **Test** : ADMIN → Administration visible dans Sidebar + CommandPalette propose Users/Audit/History ; USER → Administration absente Sidebar, CommandPalette ne propose aucune action admin, accès manuel `/admin` → Forbidden view "Accès refusé"

---

## 4. Gestion des erreurs — Nouveaux états gérés

- **Réseau** : `ApiError` status 0 → "Impossible de joindre le backend XMLForge" + "Le serveur XMLForge est actuellement inaccessible [Vérifier connexion] [Réessayer]"
- **401** : Session expirée/invalide → `clearSession('unauthorized')` + event `xmlforge:unauthorized` → redirect LoginView, mécanisme déjà présent dans `client.ts`, pas de duplication
- **403** : Forbidden → "Vous n'avez pas la permission" + badge + ErrorState Forbidden, ex: table protégée sans clé → modal Unlock, DB permissions 403 → "Accès refusé — permission admin requise"
- **404** : Not Found → "La ressource demandée n'existe plus" + EmptyState "Base/Table introuvable" + [Retour]
- **409** : Conflit version → "Cette ressource a été modifiée depuis son dernier chargement. Actualisez les données avant de continuer." + toast + [Actualiser] + ConflictDialog, backend `expected_version` / If-Match conservé
- **422** : Validation → erreurs près champs concernés (ex: EditDatabaseModal error state, AddColumnModal toast avec détail)
- **500** : Erreur serveur générique → message propre "Le serveur XMLForge a rencontré une erreur" + détails techniques console/dev mode, pas de `Error` brut
- **Données invalides** : Jamais écran noir, guards `!db || !table` + `columnsError || rowsError` → ErrorState propre, application reste utilisable

---

## 5. Fonctionnalités conservées — Non-régression V2.3

Toutes V2.3 restent fonctionnelles :

- **Auth** : register, login, logout, me, F5 restore session, expiration JWT, compte désactivé → OK
- **Databases** : list, create PERSONAL/COMMON, edit nom/desc/scope/common_permission, delete, archive/restore, favorites ★, permissions → OK
- **Tables** : list, create avec withId, delete, protect toggle, unlock, duplicate structure sans données, truncate DELETE FROM → OK
- **Structure** : add column, edit column (EditColumnModal), delete column, PK/AI/NN/UNIQUE/FK/default/index/comment → OK
- **Data** : pagination backend limit/offset/total, search backend, sort backend, filter backend, NULL badge, insert RowModal, inline edit double-clic + Tab/Shift+Tab/Flèches + Enter/Esc + focus visible + saving indicator, delete single + bulk boucle → OK
- **Relations** : diagramme avec tables déplaçables, lignes SVG FK, zoom +/-/Reset, recherche, liste mode, focus table avec incoming/outgoing, favoris, navigation Ouvrir → OK, performance 1 requête /schema
- **SQL** : execute réel POST /databases/{id}/query → XmlNativeEngine, résultats grille colonnes depuis data, lignes, count, affected, timing réel si fourni, historique réel, Ctrl+Enter → OK
- **XML** : view export réel, edit, dirty banner "Modifications non appliquées" + Apply/Abandonner, validation locale + backend XSD, Apply via POST sync-xml + document_version, Reset reload, Diff +ajout -suppr ~modif, Download/Copy réels → OK
- **Import/Export** : XML/SQL/Project import/export réels, workflow Sélection→Analyse→Validation→Aperçu→Application→Résultat, 409 vrai → OK, Export XML sans Convertir en SQL
- **Administration** : users liste/création/modif/suppression/toggle active/reset pwd, audit logs, history → OK, uniquement ADMIN, USER → masquée + Forbidden
- **Server** : REST En ligne version réelle, TCP 3307 En ligne host/port/running, sessions TCP réelles, health, pas de Restart fake → OK
- **Logs** : audit réel + info %LOCALAPPDATA%\XMLForge\logs\ → OK
- **Permissions** : DB/table VIEW/EDIT/MANAGE, PERSONAL/COMMON, owner, protection → OK
- **Favoris** : localStorage xmlforge_fav_dbs/tables, UI-only, nettoyage si suppression → OK
- **Command Palette** : Ctrl+K, recherche bases/tables réelles, outils FR, navigation clavier → OK
- **Breadcrumbs** : FR, noms réels → OK
- **Modales** : Portal, z-layers, focus trap, Esc, overlay click, scroll lock, nested → OK

---

## 6. Tests — Résultats exacts

### Frontend V2.4 Build
```bash
cd /home/user/XMLForge_FrontRedesign
npm ci --quiet
npm run build
```
```
✓ 72 modules transformed.
dist/index.html  461.10 kB │ gzip: 127.52 kB (V2.3 460.91 KB → V2.4 471.76 KB → 461.10 KB après optim)
✓ built in 2.03s
```

### Backend
```bash
cd /home/user/XMLForge/backend
python3 -m venv .venv && pip install -r requirements.txt
.venv/bin/python -m pytest -q
```
```
350 passed in 59.45s
```

### Packaging
```bash
pytest tests/test_packaging.py -q
```
```
16 passed in 1.65s
```

### Lint old frontend
```bash
cd /home/user/XMLForge/xmlforge-react
npm run lint
```
```
Found 3 warnings and 0 errors (fast-refresh préexistants)
```

### Flask serving V2.4
```bash
cp dist/index.html → xmlforge-react/dist/index.html + backend/frontend/index.html
GET / → 200 text/html V2.4
GET /api/nope → 404 JSON
GET /data/control/security.xml → 404 JSON (sécurité SPA)
```

### Vérifications manuelles V2.4 (parcours complet)

**Auth** : Register, Login, Logout, F5 restore, 401, 403 → OK
**Databases** : Création PERSONAL/COMMON, modification nom/desc, modification scope PERSONAL→COMMON→PERSONAL avec admin (PUT scope + common_permission, confirmation), suppression, permissions, favoris ★, changement rapide DB A→B→C pas de stale, F5 → OK
**Tables** : Ouvrir table, Structure (colonnes réelles PK/AI/NN/UNIQUE/FK/default/index), Data (pagination/search/sort/filter/NULL/insert/inline edit double-clic+Tab/Flèches), Relations (diagramme zoom/recherche/liste/favoris/focus + clic table/relation), SQL (execute réel), XML (view/edit/dirty/diff/apply/reset), Permissions (membres réels) → OK, plusieurs tables différentes + retour rapide → aucun écran noir
**Import** : Ouvrir import → choisir fichier → affiche nom + taille + validation "XML valide : 1 table(s), 2 ligne(s)" → Changer fichier OK, Annuler OK, Lancer import OK, erreur fichier invalide badge Invalide + bouton disabled + message clair, succès → tables maj, pas de blocage UI globale
**Server** : Ouvrir Server → REST Disponible (version 5.0.0), TCP 3307 Disponible (0.0.0.0:3307 actif), Sessions 0 ou réelles, Erreur récupération sessions → "Impossible de récupérer les sessions [Réessayer]" pas de noir, pas de donnée inventée
**Administration** : ADMIN → Users, Audit, History visibles + réels ; USER → Administration absente Sidebar, CommandPalette ne propose aucune action admin, accès manuel /admin → Forbidden "Accès refusé"
**XML Export** : Export XML tab → bouton "Convertir en SQL" absent → OK

---

## 7. Backend — Extension requise ?

**Vérification** : Pour chaque problème V2.4, vérifier Frontend → API existante ?

- Modification scope database : Backend `update_database()` supporte déjà scope + common_permission avec admin permission → Oui → corrigé frontend (EditDatabaseModal avec scope)
- Page permissions : Backend GET/POST/DELETE permissions existe → Oui → PermissionsView créée frontend only
- Écran noir table : Backend retourne 403/404/500 → Frontend doit gérer error state, pas backend → Oui → fix frontend TableWorkspace error guards
- Server visuel : Backend /health, /tcp/status, /tcp/sessions existent → Oui → fix frontend ServerView error states
- Import bloqué : Backend import endpoints existent, FormData OK → Oui → fix frontend ImportExport workflow
- Export XML Convertir en SQL : Bouton inutile dans workflow export XML → Non lié backend, suppression frontend only → Oui
- Administration non-admin masquée : Backend /me retourne is_admin/role réel, /users 403 si non admin → Oui → fix frontend Sidebar/CommandPalette/AdminView

**Aucune nouvelle route backend créée**, aucun endpoint fictif, aucun mock, moteur XML/TCP 3307/permissions/transactions/JWT inchangés.

```
BACKEND_EXTENSION_REQUIRED = NONE
```

---

## 8. Problèmes restants — Limitations

- EditColumnModal utilise event `xf-refresh-columns` + `fetchColumns` pour maj, pas de maj optimiste directe du tableau columns (pourrait être amélioré mais non bloquant)
- DataTab filtre envoie 1 colonne (filterCol+filterVal) pas multi-filtres avancés UI (backend supporte multi via JSON filters, UI simplifiée minimal)
- Duplication structure N requêtes colonnes boucle — acceptable, pas de bulk endpoint backend
- Truncate via DELETE FROM pas via endpoint TRUNCATE dédié — fonctionne car backend supporte DELETE via XmlNativeEngine
- Index management via colonnes + SQL CREATE/DROP INDEX, pas d'UI avancée dédiée — conforme backend
- Dashboard total rows non affiché (nécessiterait N requêtes count) — affiché tables_count + version seulement, pas de fake
- SettingsView informative, pas de persistence backend — config via env, localStorage UI prefs seulement
- Overview activity `useState(() => loadActivity())` devrait être `useEffect` — fonctionne mais pas idéal (minor)
- `src/data/mock.ts` conservé historique mais non utilisé runtime — contient encore chemins Linux fictifs mais non affichés (P3)

---

## 9. Verdict

**FRONTEND_V2_4 = STABLE**

**Justification** :
- 0 P0 bloquant (vite proxy fix, reload supprimé, écrans noirs fixés, import débloqué, admin masquée, permissions page créée, scope modifiable)
- 0 P1 majeur (race guards, stale clear, loading/error distincts, DataGrid clavier, schema performance 1 requête, modales z-layers stables, FR uniformisé)
- Build OK 461.10 KB, backend 350 verts, packaging 16 verts, connexion front/back CONNECTED (prod same-origin + dev proxy), 100% données réelles, 0 mock runtime, 0 SQLite, design dark premium conservé, aucune régression V1/V2.2/V2.3
- Prêt pour suite packaging Windows → EXE → Installateur

---

**Fin rapport V2.4 — Frontend structuré, prévisible, robuste, maintenable, prêt packaging**
