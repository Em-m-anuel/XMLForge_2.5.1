# XMLForge Frontend — intégration Flask réelle

## 1. Architecture

Le frontend conserve le template visuel XMLForge fourni : tokens, sidebar, cartes, modals, workspace à trois panneaux, Monaco, timelines et tableaux. Il n’embarque aucune base, row ou utilisateur fictif.

```text
React Router
  ├─ AuthContext (JWT, /me, rôles)
  ├─ DatabaseContext (unlocks confirmés par Flask, sans stocker les clés)
  ├─ pages
  └─ services centralisés
          ↓
      apiClient
          ↓
       Flask /api
          ↓
       XML / SQLite
```

Tous les appels HTTP applicatifs passent par `src/services/api.js`. Le seul `fetch()` du projet est celui du client central.

## 2. Configuration

`.env` :

```env
VITE_API_URL=/api
VITE_SOCKET_URL=http://localhost:5000
```

En développement, Vite proxifie `/api` et `/socket.io` vers `http://localhost:5000`. Une URL Flask n’est donc pas dispersée dans les composants. Pour un frontend séparé :

```env
VITE_API_URL=https://backend.example.com/api
VITE_SOCKET_URL=https://backend.example.com
```

## 3. Routing

- `/login`, `/register` : public ;
- `/dashboard` : authentifié ;
- `/database/:databaseId` : authentifié, les ACL sont chargées depuis Flask ;
- `/workspace/:dbName?dbId=` : alias historique conservé ;
- `/users`, `/audit`, `/history` : rôle ADMIN ;
- `/settings` : authentifié, configuration TCP REST uniquement.

`ProtectedRoute` et `AdminRoute` protègent l’expérience utilisateur. Flask reste l’autorité finale et peut retourner 401/403.

## 4. API client et erreurs

`services/api.js` centralise :

- base URL ;
- JWT `Authorization: Bearer` ;
- détection locale de `exp` ;
- parsing des enveloppes Flask ;
- downloads blob authentifiés ;
- erreurs réseau ;
- 401 : session supprimée et événement global ;
- 403 : accès refusé ;
- 404 : ressource absente ;
- 409 : `ApiError.isConflict=true` et code `SYNC_CONFLICT` ;
- 400/422 : validation ;
- 500 : erreur serveur lisible.

Les services métier sont : auth, databases, tables, columns, rows, access, XML/sync, import, export, projects, users, audit/history, converters et TCP.

## 5. Authentification et rôles

- login réel `/api/login` ;
- token et user sauvegardés dans localStorage ;
- restauration par `/api/me` au rechargement ;
- expiration contrôlée avant chaque requête ;
- logout réel `/api/logout`, puis nettoyage local ;
- aucun faux utilisateur local ;
- aucun privilège basé sur un email magique ;
- rôle lu depuis `user.role`/`user.is_admin` retourné par Flask.

Les pages Users/Audit/History sont réservées à ADMIN dans le routeur, tout en gérant aussi un éventuel 403 backend.

## 6. Bases PERSONAL / COMMON / partagées

Le dashboard affiche uniquement `/api/databases` et montre :

- scope PERSONAL/COMMON ;
- propriétaire ;
- source d’accès (`owner`, `role`, `shared`) ;
- niveau VIEW/EDIT/MANAGE ;
- statut et nombre de tables.

Filtres : toutes, PERSONAL, COMMON, partagées. La création et l’édition envoient `scope`. Les actions sont affichées selon `database.access` :

- VIEW : lecture/ouverture ;
- EDIT : écritures/DDL accordés ;
- MANAGE : suppression, archivage, export complet et partage.

Le modal de partage utilise réellement les endpoints `/databases/:id/permissions`, avec recherche de la cible par email côté backend.

## 7. Workspace

Le design existant est conservé : explorateur de tables à gauche, structure/données/relations au centre, Monaco XML/SQL à droite.

### Structure

Les propriétés réelles sont affichées et éditées : type, longueur, nullable, PK, FK, référence, UNIQUE, AUTO_INCREMENT, INDEX, DEFAULT, ON DELETE et ON UPDATE.

### Données

La table utilise les paramètres serveur réels :

- `limit=25`, `offset` ;
- `search` ;
- `sort`, `order` ;
- pagination précédente/suivante ;
- ajout, mise à jour et suppression ;
- affichage explicite de NULL ;
- valeurs auto-increment/default omises du payload quand elles doivent être calculées par Flask.

Après chaque mutation, le frontend recharge la version de base, les rows et le XML.

### Relations

L’onglet Relations charge les colonnes réelles des tables et affiche FK sortantes/entrantes. Aucun JOIN ou relation fictive n’est simulé.

## 8. XML et Monaco

Monaco reste utilisé. Pour un utilisateur MANAGE :

1. export table XML réel ;
2. version `document_version` mémorisée ;
3. édition locale et validation de syntaxe DOM ;
4. POST sync XML avec `expected_version` ;
5. recharge structure, rows, base et version.

Pour un niveau ne permettant pas l’export secret/protection, l’éditeur indique que le XML est indisponible ; aucun XML fallback synthétique n’est inventé.

## 9. Conflits de version

Les mutations structurelles, rows et sync envoient `expected_version` ou `If-Match` selon le contrat backend.

Un 409 ouvre `ConflictDialog` :

- indique qu’une version plus récente existe ;
- garantit que rien n’a été écrasé ;
- propose abandon ou rechargement complet.

## 10. Tables protégées

Les clés ne sont jamais stockées dans localStorage/sessionStorage. Le frontend :

1. consulte `/unlocks` ;
2. mémorise seulement les IDs confirmés par Flask ;
3. demande la clé si une mutation vise une table verrouillée ;
4. appelle `/unlock-table` ;
5. marque l’ID comme déverrouillé après succès ;
6. vide/recharge cet état au login/logout.

Le backend reste vérifié à chaque mutation. Le déverrouillage d’un utilisateur n’est jamais présenté comme global.

## 11. Import / export

- import XML fichier ou texte : endpoints Flask réels ;
- import projet complet : endpoint projet réel ;
- export XML/SQL table/base ;
- export projet complet ;
- downloads centralisés et authentifiés dans `apiClient.download` ;
- aucune génération approximative de projet côté navigateur.

## 12. Users, audit et historique

Users utilise le CRUD backend, activation, reset password et rôles USER/ADMIN. Les protections du dernier admin restent côté Flask.

Audit et historique chargent les journaux réels et conservent les filtres visuels du template.

## 13. TCP/IP

La page `/settings` n’ouvre aucune socket TCP dans le navigateur. Elle utilise seulement les routes REST `/api/tcp/*` pour :

- créer/consulter/régénérer les credentials ;
- confirmer le mot de passe XMLForge ;
- afficher une fois le nouveau secret ;
- afficher statut et sessions.

Seul le client Python réellement fourni est documenté. Les exemples Node et cURL HTTP sur le port TCP ont été retirés car ces clients/protocoles n’existent pas.

## 14. Loading, empty et refresh

Dashboard, workspace, rows, users, audit, historique et TCP possèdent chargement, vide, erreur et succès. Les mutations actualisent les vues concernées au lieu de conserver un état simulé.

REST assure tous les refreshs fonctionnels. Socket.IO est optionnel (`VITE_ENABLE_SOCKET_IO=true`) et désactivé par défaut tant que le déploiement ne fournit pas un transport Socket.IO testé ; aucune page ne dépend de lui.

## 15. Tests

```bash
npm run lint
npm run build
npm test
```

Tests unitaires frontend : API/JWT/401/409, rôles backend, unlocks sans clé, propagation `expected_version`, dialog de conflit.

Test live services ↔ Flask :

```bash
VITE_API_URL=http://127.0.0.1:5000/api \
XMLFORGE_LIVE_E2E=1 \
npm test -- src/test/liveBackend.test.js
```

E2E navigateur réel (backend et Vite lancés) :

```bash
npx playwright install chromium
npm run test:e2e
```

Scénarios réels : register/login, COMMON owner MANAGE, partage VIEW, création table/colonnes/row, lecture row, export/import XML, mutation externe, conflit stale 409 visible dans le navigateur, rechargement et nettoyage.

## 16. Limites backend respectées

- pas de JOIN texte dans QueryService : aucune UI JOIN simulée ;
- pas de client TCP navigateur ;
- pas de client Node TCP officiel ;
- export XML complet limité aux droits MANAGE ;
- les ACL frontend améliorent l’UX mais ne remplacent jamais Flask.
