# XMLForge — Intégration Frontend (compte-rendu)

Ce document décrit le travail réalisé côté **frontend** pour couvrir les
fonctionnalités réellement exposées par le backend Flask de XMLForge.

Aucun fichier backend n'a été modifié dans cette étape.

---

## 1. Résumé

Le frontend React (`xmlforge-react/`) couvrait déjà l'essentiel du circuit
(authentification, bases, tables, colonnes, lignes, XML/SQL, import/export,
protection, TCP, utilisateurs, audit, historique). L'audit comparatif
frontend ↔ backend a identifié plusieurs fonctionnalités backend **existantes
mais absentes ou partielles dans l'interface**. Elles ont été intégrées.

Fonctionnalités **ajoutées / complétées** dans cette étape :

| # | Fonctionnalité | État avant | État après |
|---|---|---|---|
| 1 | Import SQL (`POST /api/import/sql`) | service présent, aucune UI | UI dans le Dashboard (sélecteur XML / SQL / Projet) |
| 2 | Import projet (`POST /api/import/project`) | service présent, aucune UI | UI dans le Dashboard |
| 3 | Réinitialisation de mot de passe (`POST /api/users/:id/reset-password`) | service présent, aucune UI | Bouton + modal dans la page Utilisateurs (ADMIN) |
| 4 | Partage de table (`GET/POST/DELETE /api/tables/:id/permissions`) | service présent, aucune UI | Bouton « Partage de la table » + modal dans le Workspace |
| 5 | Partage de base dans le Workspace | uniquement dans le Dashboard | Bouton « Partage » dans la barre du Workspace |
| 6 | Contraintes de colonne avancées (PK, FK, références, auto-incrément, index, ON DELETE/UPDATE) | construites par le code mais non exposées dans le modal | Modal colonne complet |
| 7 | Ajouter une ligne quand le tableau est déjà rempli | bouton présent uniquement dans l'état vide | Bouton « + Ajouter une ligne » dans la barre d'outils Données |
| 8 | Retirer la protection d'une table (`PUT /api/tables/:id` avec `is_protected:false`) | aucune UI | Bouton « Ôter la protection » (table déverrouillée) |
| 9 | Vue générale de la base | informations éparses | Bandeau « Vue générale » (scope, propriétaire, accès, version XML, description) |
| 10 | Correction du doublon de base | nom `${db.name} (copie)` invalide (espace/parenthèses) | nom nettoyé `${base}_copie` respectant `^[A-Za-z_][A-Za-z0-9_]*$` |
| 11 | Édition de base sans droit admin | envoi systématique de `scope` → 403 pour les EDIT | `scope` envoyé seulement si `can_admin` |
| 12 | Liste des endpoints REST de référence | 4 endpoints d'aperçu | inventaire complet des routes exposées |

---

## 2. Pages créées / modifiées

### Modifiées

- **`src/pages/Dashboard/Dashboard.jsx`**
  - Modal d'import à 3 modes (XML / SQL / Projet XMLForge), avec `accept` et
    libellé dynamiques, dispatch vers `importService.importXml/importSql` ou
    `projectService.importProject`.
  - `handleSaveEditDb` : n'envoie `scope` que si `access.can_admin`
    (le backend exige `can_admin` dès que la clé `scope` est présente).
  - `handleDuplicate` : nom de copie assaini en identifiant XML valide.

- **`src/pages/Users/Users.jsx`**
  - Bouton « Réinitialiser le mot de passe » par ligne (icône clé).
  - Modal de réinitialisation (nouveau mot de passe, min 6 caractères,
    rappel de la révocation des sessions / déverrouillages côté backend).

- **`src/pages/Workspace/Workspace.jsx`**
  - Bandeau de « Vue générale » (scope, propriétaire, niveau d'accès,
    version XML, description).
  - Bouton « Partage » (base) dans la barre de titre + modal
    liste/accorde/révoque (`accessService.listDatabase/grantDatabase/revokeDatabase`).
  - Bouton « Partage de la table » + modal
    (`accessService.listTable/grantTable/revokeTable`), avec rappel du
    comportement **additif** des droits de table.
  - Bouton « Ôter la protection » pour une table protégée déjà déverrouillée
    (`tableService.update({ is_protected:false, file_identifier:null })`).
  - Modal de colonne étendu : liste de types complète, clé primaire,
    auto-incrément, index, clé étrangère + référence (`table.colonne`) +
    actions `ON DELETE` / `ON UPDATE`.
  - Bouton « + Ajouter une ligne » dans la barre d'outils de l'onglet Données
    (auparavant uniquement visible sur l'état vide).

- **`src/pages/Settings/Settings.jsx`**
  - Remplacement des 4 endpoints d'aperçu par l'inventaire complet des routes
    réellement enregistrées (auth, bases, tables, colonnes, lignes, imports,
    exports, conversions, déverrouillages, utilisateurs, historique, audit,
    TCP, santé).

- **`src/components/TCPCredentials/TCPCredentials.jsx`**
  - Précision : l'identifiant de base à sélectionner est l'ID de l'URL
    (`/database/<id>`), et le mot de passe TCP est distinct du mot de passe web.

### Créées

- **`XMLForge_frontend_template.html`** — modèle autonome HTML/CSS/JS
  représentant l'intégralité du frontend (voir section 6).
- **`FRONTEND_IMPLEMENTATION.md`** — ce document.

---

## 3. Services API utilisés (inchangés)

Les services existants couvraient déjà tous les endpoints ; aucune création de
service n'a été nécessaire :

| Service | Endpoints consommés |
|---|---|
| `authService` | `POST /register`, `POST /login`, `GET /me`, `POST /logout` |
| `databaseService` | `GET/POST /databases`, `GET/PUT/DELETE /databases/:id`, `archive`, `restore`, `rebuild-projection` |
| `tableService` | `GET /tables/:dbId`, `GET /tables/:id/detail`, `POST /tables`, `PUT/DELETE /tables/:id`, `archive`, `restore`, `unlock`, `getXml`, `getSql`, `syncXml` |
| `columnService` | `GET /columns/:tableId`, `POST /columns`, `GET /columns/:id/detail`, `PUT/DELETE /columns/:id`, `archive`, `restore` |
| `rowService` | `GET /tables/:id/rows`, `POST /tables/:id/rows`, `PUT/DELETE /tables/:id/rows/:rowId` |
| `accessService` | `GET/POST /databases/:id/permissions`, `DELETE /databases/:id/permissions/:userId`, `GET/POST /tables/:id/permissions`, `DELETE /tables/:id/permissions/:userId` |
| `importService` | `POST /import/xml`, `POST /import/sql` |
| `exportService` | `GET /export/xml/:id`, `GET /export/sql/:id`, `GET /export/table-xml/:id`, `GET /export/table-sql/:id` |
| `projectService` | `GET /export/project/:id`, `POST /import/project` |
| `converterService` | `POST /convert/xml-to-sql`, `POST /convert/sql-to-xml` |
| `syncService` | `POST /databases/:id/sync-xml`, `POST /tables/:id/sync-xml` |
| `unlockService` | `POST /unlock-table`, `GET /unlocks`, `DELETE /unlocks` |
| `tcpService` | `GET/POST/PUT/DELETE /tcp/credentials`, `regenerate`, `show-password`, `GET /tcp/sessions`, `GET /tcp/status` |
| `userService` | `GET/POST /users`, `GET/PUT/DELETE /users/:id`, `reset-password`, `toggle-active` |
| `auditService` | `GET /audit-logs` |
| `historyService` | `GET /history` |

---

## 4. Permissions prises en compte

Le frontend respecte le contrat d'autorisation du backend
(`PermissionService`) :

- **Niveaux** : `VIEW` (lecture), `EDIT` (`can_write` ou `can_ddl`),
  `MANAGE` (`can_admin`), `NONE`.
- **Dashboard** : le menu contextuel n'expose
  « Modifier » que si `can_write` ; « Dupliquer / Export complet / Gérer les
  accès / Archiver-Restaurer / Supprimer » que si `can_admin`.
- **Workspace** :
  - `Ajouter une colonne / Archiver / Supprimer / Protéger / Ôter la protection`
    gated par `can_ddl` ;
  - `Ajouter / Modifier / Supprimer une ligne` gated par `can_write` ;
  - `Partage` (base et table), `Export complet` gated par `can_admin` ;
  - `Appliquer les modifications` (sync XML) gated par `can_admin` **et**
    table déverrouillée.
- **Pages admin** (`/users`, `/audit`, `/history`) protégées par `AdminRoute`
  (rôle `ADMIN` uniquement) ; jamais visibles pour un USER.
- **Erreurs** : 401 (déconnexion + retour login), 403 (message droits + repli
  vers le déverrouillage de table le cas échéant), 404, 409 (modale de
  conflit de version), 400/422/5xx via messages compréhensibles
  (`src/services/api.js`).

---

## 5. Fonctionnalités nécessitant encore une évolution backend

Ces éléments sont **documentés** dans le frontend (ou le manuel) mais ne
peuvent pas être réalisés sans travail backend :

1. **Clés API** — le backend n'expose aucune gestion de clés API. La page
   API & TCP/IP l'indique explicitement (« aucun token fictif n'est généré »).
2. **Export global multi-bases** — l'export projet est par base
   (`/export/project/:id`). Aucun endpoint d'export de toutes les bases.
3. **Socket.IO** — optionnel (`VITE_ENABLE_SOCKET_IO=false` par défaut), sans
   authentification ni cloisonnement par rooms/ACL côté événements. REST suffit.
4. **Moteur SQL** — `SELECT/INSERT/UPDATE/DELETE` uniquement ; pas de JOIN,
   GROUP BY, agrégats, sous-requêtes, DDL (refusés explicitement).
5. **COMMON** — la portée est un filtre ; elle ne donne **aucune** visibilité
   automatique : un partage explicite est requis. Une base `PERSONAL` peut
   aussi être partagée (le backend ne l'interdit pas).
6. **Droits de table** — additifs : ils ne révoquent jamais un droit de base.
   Un partage de table seul ne rend pas la base sélectionnable ; la lecture
   sur la base doit être accordée (rappel affiché dans le modal de partage).
7. **Cascades FK** — `ON DELETE` / `ON UPDATE` sont stockés dans le XML/DDL
   mais ne sont pas rejoués automatiquement dans le XML comme effets en cascade.
8. **Déverrouillage** — nécessite `can_write` sur la table : un utilisateur
   VIEW ne peut pas déverrouiller pour écrire.

---

## 6. Modèle autonome `XMLForge_frontend_template.html`

Livrable séparé, **modèle visuel** modifiable par l'utilisateur. Fichier unique
contenant HTML + CSS + JavaScript :

- **vues** : Login, Register, Dashboard (Toutes / Personnelles / Communes,
  recherche, cartes, menu contextuel, import/export, partage),
  Workspace (liste de tables, vue générale, Structure / Données / Relations,
  panneaux XML et SQL, sync, protection/déverrouillage, partage base + table),
  Utilisateurs (ADMIN), Historique (ADMIN), Audit (ADMIN), API & TCP/IP.
- **états** : loading (skeleton/spinner), empty states, erreurs, succès
  (toasts), conflit 409 (modale).
- **permissions** : mêmes gating que le React (`can_read/write/ddl/admin`,
  `ADMIN`).
- **aucun mock** : toutes les actions appellent les vrais endpoints via
  `API_URL` (constante en tête de script, `http://localhost:5000/api` par
  défaut). Les données affichées viennent du backend ; sans backend, les
  états vide/erreur s'affichent.

---

## 7. Vérifications effectuées

Exécutées dans cette étape (frontend uniquement) :

```text
npm run lint    → 0 erreur, 3 avertissements (fast-refresh uniquement, préexistants)
npm run build   → ✓ build (Vite 8.1.5)
npm test        → 10 tests passés, 1 live test ignoré par défaut
```

Le modèle autonome a été validé par :
- `node --check` (syntaxe JavaScript) ;
- exécution sous jsdom avec backend simulé : rendu Login, Dashboard
  (PERSONAL/COMMON, filtres, menu admin), Workspace (tables, colonnes,
  lignes, panneaux XML/SQL, partage, vue générale) et Settings TCP/IP.

Les tests backend n'ont **pas** été relancés (aucune modification backend).

---

## 8. Points à vérifier manuellement

1. USER se connecte → voit ses bases personnelles.
2. USER voit les bases COMMON **partagées avec lui** (et uniquement celles-ci).
3. USER ouvre une base → consulte tables / structure / données.
4. USER ajoute / modifie / supprime une ligne (bouton présent même avec des lignes).
5. USER modifie la structure si `can_ddl` (colonne complète : PK, FK,
   références, index, ON DELETE/UPDATE).
6. USER partage une base / une table si `can_admin` ; vérifier que VIEW/EDIT
   ne voient pas les actions réservées.
7. ADMIN se connecte → accède à Utilisateurs, Historique, Audit.
8. ADMIN crée un utilisateur, change son rôle, le désactive, réinitialise
   son mot de passe, le supprime.
9. Import XML, import SQL et import projet créent chacun une nouvelle base.
10. Export XML / SQL / projet téléchargent les fichiers.
11. Synchronisation XML : modifier le panneau XML puis « Appliquer les
    modifications » ; vérifier le conflit 409 si la version a changé.
12. Protection : protéger une table (clé), se reconnecter, la déverrouiller
    avec la clé, puis « Ôter la protection ».
13. La page API & TCP/IP affiche le statut du serveur, l'hôte/port,
    l'utilisateur TCP et le client Python d'exemple.
14. Les erreurs 401 / 403 / 404 / 409 affichent des messages compréhensibles.
