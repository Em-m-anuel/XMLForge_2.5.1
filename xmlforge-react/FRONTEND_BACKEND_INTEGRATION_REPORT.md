# Rapport final — intégration frontend XMLForge / Flask

## Frontend analysé

Le frontend existant est une SPA React 19/Vite avec :

- React Router et routes lazy ;
- AuthContext et DatabaseContext ;
- pages Login, Register, Dashboard, Workspace, Users, Audit, History ;
- sidebar, toasts, Monaco, composant TCP ;
- services REST déjà amorcés ;
- CSS `maquette.css` issu du template XMLForge ;
- Socket.IO pour rafraîchissements collaboratifs.

Le fichier fourni `xmlforge (4).html` a été comparé au React existant. Le React reprenait déjà presque tout le design. Les éléments manquants du template — relations, écran API/TCP et styles associés — ont été intégrés sans changer les tokens, couleurs, layout ou typographie.

## Backend réellement utilisé

### Auth

- `POST /api/register`
- `POST /api/login`
- `GET /api/me`
- `POST /api/logout`

### Bases et accès

- `GET/POST /api/databases`
- `GET/PUT/DELETE /api/databases/:id`
- archive/restore
- `GET/POST /api/databases/:id/permissions`
- `DELETE /api/databases/:id/permissions/:userId`

### Tables, colonnes et rows

- tables list/detail/create/update/delete/archive/restore
- columns list/detail/create/update/delete
- rows list/create/update/delete avec pagination/search/sort
- `/api/unlock-table`, `/api/unlocks`

### XML/import/export

- export XML/SQL base et table
- export/import projet
- import XML/SQL
- sync XML base/table
- converters XML↔SQL

### Administration

- users CRUD, rôle, activation, reset password
- audit et historique

### TCP via REST uniquement

- credentials CRUD/regenerate/show-password
- sessions/status

Le navigateur n’ouvre jamais de socket TCP native.

## Fichiers frontend principaux modifiés

| Chemin | Rôle et modification |
|---|---|
| `src/services/api.js` | Client unique, JWT, expiration, 401/403/404/409/400/500, blobs, erreurs réseau |
| `src/services/*Service.js` | Contrats Flask réels et expected_version |
| `src/services/accessService.js` | ACL VIEW/EDIT/MANAGE |
| `src/services/tcpService.js` | Routes REST TCP réelles |
| `src/context/AuthContext.jsx` | Session `/me`, rôles backend, suppression email magique |
| `src/context/DatabaseContext.jsx` | Unlock IDs confirmés par Flask, aucune clé persistée |
| `src/pages/Dashboard/Dashboard.jsx` | Bases réelles, scopes, owner, accès, partage, conflits |
| `src/pages/Workspace/Workspace.jsx` | Structure/rows/relations/XML/version/protection/ACL |
| `src/pages/Users/Users.jsx` | CRUD et rôles USER/ADMIN réels |
| `src/pages/Settings/Settings.jsx` | Écran API/TCP du template connecté |
| `src/components/TCPCredentials/*` | Credentials/status/sessions ; exemples fictifs retirés |
| `src/components/ConflictDialog/*` | UX 409 reload/abandon |
| `src/App.jsx`, `Sidebar.jsx` | Routing protégé et settings |
| `vite.config.js`, `.env.example` | Proxy configurable sans URL REST hardcodée |
| `maquette.css` | Ajouts relations/API du template, design préservé |
| `FRONTEND_DOCUMENTATION.md` | Documentation opérationnelle |

## Adaptations backend nécessaires à l’intégration

- réponses bases/tables enrichies avec `access` et `is_owner` ;
- niveaux VIEW/EDIT/MANAGE calculés par PermissionService ;
- partage par email en plus de user_id ;
- permission serializers avec email/nom ;
- persistance `on_delete`/`on_update`, migration V6 ;
- 409 cohérents pour mutations rows/tables/colonnes ;
- import exporté puis réimporté avec régénération UUID sans collision ;
- création admin d’un user avec rôle dans une requête ;
- lancement direct Werkzeug configurable pour développement.

## Fonctionnalités intégrées

- login/logout/restauration/expiration ;
- rôles ADMIN/USER sans email hardcodé ;
- dashboard PERSONAL/COMMON/partagé ;
- VIEW/EDIT/MANAGE et partage par email ;
- explorateur de base ;
- CRUD tables/colonnes/rows ;
- pagination, recherche et tri serveur ;
- affichage NULL ;
- PK/FK/references/unique/nullable/default/auto increment/index/actions FK ;
- onglet relations ;
- Monaco XML réel ;
- expected_version et dialog 409 ;
- protection individuelle et reconnexion ;
- import/export XML/SQL/projet ;
- Users/Audit/History ;
- configuration TCP REST ;
- loading/empty/error/success et refresh après mutation.

## Mocks et simulations supprimés

- privilège par email magique ;
- stockage local des clés de protection ;
- XML fallback construit depuis les colonnes ;
- appels fetch dispersés pour downloads ;
- exemples TCP Node.js et cURL HTTP inexistants ;
- supposition qu’un nom de base ou un bouton frontend constitue une autorisation.

Aucune donnée métier mockée n’est présente dans le code de production. Les mocks restants sont exclusivement dans les tests unitaires.

## Tests exécutés

### Backend

```text
PYTHONPATH=backend python -m pytest -q backend/tests
14 passed
```

### Frontend statique/unitaire

```text
npm run lint   → 0 erreur, 3 avertissements Fast Refresh historiques
npm run build  → succès
npm test       → 10 passed, 1 live test skipped par défaut
npm audit --omit=dev → 0 vulnérabilité
```

### Services frontend contre Flask réel

```text
VITE_API_URL=http://127.0.0.1:5000/api XMLFORGE_LIVE_E2E=1 \
npm test -- src/test/liveBackend.test.js
1 passed
```

Scénario : register/login, COMMON owner MANAGE, partage VIEW, CRUD structure/row, export XML, import XML, stale expected_version 409 et nettoyage.

### Navigateur réel Playwright

```text
npm run test:e2e
1 passed
```

Scénario : navigateur Chromium → register/login → dashboard → COMMON → table → colonnes → row → Flask/XML/SQLite → mutation externe → sauvegarde obsolète → dialog 409 → reload.

## Problèmes restants réels

- QueryService backend ne supporte pas encore JOIN/GROUP BY/agrégats : aucune UI ne les simule.
- L’éditeur XML complet est réservé au niveau MANAGE car l’export backend peut contenir les métadonnées de protection.
- Socket.IO ne possède pas encore de rooms ACL par base. Il est donc optionnel et désactivé par défaut ; REST et Flask assurent toutes les fonctions et restent autoritaires.
- Trois avertissements lint `react/only-export-components` subsistent pour les fichiers context/hooks historiques ; aucune erreur lint.
- Monaco augmente la taille du bundle principal ; le chargement lazy des pages limite l’impact initial.

## Documentation

- `xmlforge-react/FRONTEND_DOCUMENTATION.md`
- `xmlforge-react/README.md`
- `xmlforge-react/FRONTEND_BACKEND_INTEGRATION_REPORT.md`
- documentation backend API/migrations mise à jour pour access et V6.
