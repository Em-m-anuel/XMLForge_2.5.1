# XMLForge — Intégration du frontend au modèle (compte-rendu)

Le modèle fourni (`xmlforge (7).html`) devient la **référence visuelle** du
frontend. Ce document décrit comment le frontend React (`xmlforge-react/`) a
été adapté à ce modèle, **sans casser la logique backend déjà connectée**.

Aucune modification du backend n'a été nécessaire.

---

## 1. Constat initial (audit modèle ↔ frontend)

Le modèle et le CSS du projet (`src/styles/maquette.css`) partagent déjà les
mêmes **design tokens** (thème sombre `#0F1117`, accents `#3B82F6`, cartes
arrondies, badges, toasts, timeline, tables, modals). Le diff automatique des
sélecteurs CSS a montré que `maquette.css` était un sur-ensemble du modèle,
**à l'exception de 7 sélecteurs** (détaillés en §3).

Les écarts réels se situaient donc surtout dans la **structure JSX** :
- le Workspace n'avait que 3 onglets (modèle : 4, avec « Avancé ») ;
- le panneau « Avancé » du modèle (protection, reconstruction de projection,
  synchronisation/conflits) n'existait pas ;
- le modal de colonne utilisait un champ libre `table.colonne` au lieu des
  listes déroulantes « Table référencée / Colonne référencée » du modèle ;
- la barre d'outils des données n'utilisait pas la classe `data-toolbar` ;
- la table de structure n'affichait pas la colonne « Index » ;
- la suppression d'utilisateur utilisait `window.confirm` (modèle : modale) ;
- le composant TCP/IP utilisait ses propres classes plutôt que le langage
  `api-card-top` / `api-grid` du modèle.

---

## 2. Règles de priorité appliquées

- **Modèle prioritaire pour le design** : structure, onglets, cartes, grilles,
  badges, modales, espacements, responsive ont été repris du modèle.
- **Backend prioritaire pour la logique** : partout où le modèle décrivait une
  fonctionnalité inexistante côté backend, le frontend a été adapté pour rester
  véridique (voir §7). Aucun mock n'a été introduit.

---

## 3. Composants / styles modifiés

### `src/styles/maquette.css`
Ajout des 7 sélecteurs manquants du modèle :
- `.panel-scroll` (zone défilante des onglets Relations et Avancé) ;
- `.fk-fields-block` (bloc encadré des champs de clé étrangère) ;
- `.conflict-banner` (+ `.conflict-banner svg`, `.conflict-banner .btn`) ;
- `.acl-list`, `.acl-row`, `.acl-row input` ;
- `.data-toolbar`, `.data-toolbar .form-input` ;
- `.data-add-row td`, `.data-add-row input`.
Ajout de `overflow-y:auto` sur `.sidebar` (conforme au modèle).

### `src/pages/Workspace/Workspace.jsx`
- **Onglet « Avancé »** ajouté (4ᵉ onglet du `tabs-seg`), contenant :
  1. **Protection de la table** — carte `api-card-top` avec icône, état
     PROTÉGÉE/LIBRE, boutons « Protéger la table » / « Déverrouiller pour cette
     session » / « Retirer la protection définitivement » (selon l'état et les
     droits `can_ddl`) ;
  2. **Projection SQLite** — bouton réel « Reconstruire la projection »
     (`POST /databases/:id/rebuild-projection`), avec état de progression ;
  3. **Synchronisation & conflits** — explication du `expected_version` et du
     code `409`, affichage de la version XML courante, bouton « Rafraîchir » ;
  4. **Fonctionnalités avancées (XML / REST)** — encart d'information sur les
     PK composites / FK complexes accessibles via l'éditeur XML ou l'API.
- **Modal de colonne** : la clé étrangère se configure désormais via deux
  listes déroulantes **« Table référencée »** (tables réelles de la base) et
  **« Colonne référencée »** (colonnes réelles de la table choisie, chargées à
  la demande), plus les actions `ON DELETE` / `ON UPDATE`. La valeur envoyée
  reste le format backend `table.colonne`. Ajout de l'encart d'information sur
  les PK composites.
- **Onglet Données** : barre d'outils `data-toolbar` (recherche, tri, ordre,
  actualiser, « Ajouter une ligne », compteur de lignes). Suppression du bouton
  redondant « Ajouter une ligne » de l'état vide (un seul bouton, comme le
  modèle).
- **Table de structure** : colonne « Index » ajoutée (+ `colSpan` corrigé) ;
  badge `PK` affiché dans l'en-tête des colonnes de l'onglet Données.
- **Onglet Relations** : conteneur passé sur la classe `panel-scroll`.
- Refactorisation : helpers `openColumnModal(col)`, `handleFkTableChange`,
  `handleRebuildProjection` ; la constante `emptyColumnForm` est déplacée au
  niveau module.

### `src/pages/Users/Users.jsx`
- Suppression d'utilisateur via **modale de confirmation** (conforme au
  `modal-deleteuser` du modèle) au lieu de `window.confirm`.

### `src/pages/Dashboard/Dashboard.jsx`
- Modal « Nouvelle base » : encart d'information rappelant le comportement
  backend réel de la portée (COMMON = filtre, partage explicite requis ; une
  base PERSONAL peut aussi être partagée). Libellés de portée alignés sur le
  modèle.

### `src/components/TCPCredentials/TCPCredentials.jsx`
- Restructuration visuelle sur le langage du modèle : en-tête `api-card-top`
  (icône + titre + sous-titre + badge ACTIF/INACTIF) et grille `api-grid`
  (`api-field-label` / `api-field-value`) pour Hôte / Port / Utilisateur TCP.
  Tous les appels réels sont conservés : statut serveur, credentials,
  régénération du secret, `show-password`, sessions actives, exemple de client
  Python, note sur l'ID de base et l'absence de client HTTP sur le port TCP.

### `src/pages/Settings/Settings.jsx`
- Titre aligné sur le modèle : « Paramètres — API & connexions externes ».

### `src/pages/Workspace/Workspace.jsx` (ajustement de libellé)
- Bouton retour du Workspace : « Bases » → « **Bases de données** » (texte
  exact du modèle).

---

## 4. Fonctionnalités conservées (aucune suppression)

Authentification (login/register/logout, JWT) · rôles ADMIN/USER · gestion des
utilisateurs (création, rôle, activation, reset mot de passe, suppression) ·
bases PERSONAL/COMMON · partage de base et de table (VIEW/EDIT/MANAGE) ·
création/modification/suppression de bases · tables (création, archive,
suppression, protection/déverrouillage) · colonnes (PK, FK, références, index,
unique, auto-incrément, ON DELETE/UPDATE) · lignes (CRUD, recherche, tri,
pagination) · relations entrantes/sortantes · import XML / SQL / projet ·
export XML / SQL / projet · synchronisation XML (`sync-xml`) · versionnage
`expected_version` et conflit 409 · historique et audit (ADMIN) · informations
TCP/IP · états loading / empty / succès / erreur · erreurs 401/403/404/409
avec messages compréhensibles.

---

## 5. Fonctionnalités ajoutées dans cette étape

1. Onglet **« Avancé »** (protection + reconstruction de projection +
   synchronisation/conflits + encart XML/REST).
2. **Reconstruction de projection** accessible depuis l'interface (endpoint
   réel déjà existant mais non exposé).
3. **FK via listes déroulantes** table/colonne (données réelles).
4. **Modale de suppression d'utilisateur**.
5. **Colonne « Index »** dans la table de structure.
6. Barre d'outils des données conforme (`data-toolbar` + compteur).
7. Restructuration visuelle de la carte TCP/IP.

---

## 6. Endpoints consommés (inchangés + nouveaux usages)

| Domaine | Endpoints |
|---|---|
| Auth | `POST /register`, `POST /login`, `GET /me`, `POST /logout` |
| Bases | `GET/POST /databases`, `GET/PUT/DELETE /databases/:id`, `archive`, `restore`, **`POST /databases/:id/rebuild-projection`** |
| Tables | `GET /tables/:dbId`, `POST /tables`, `PUT/DELETE /tables/:id`, `archive`, `restore`, `unlock` |
| Colonnes | `GET /columns/:tableId`, `POST /columns`, `PUT/DELETE /columns/:id` |
| Lignes | `GET /tables/:id/rows`, `POST /tables/:id/rows`, `PUT/DELETE /tables/:id/rows/:rowId` |
| Partage | `GET/POST /databases/:id/permissions`, `DELETE .../:userId`, `GET/POST /tables/:id/permissions`, `DELETE .../:userId` |
| Import/export | `POST /import/xml`, `POST /import/sql`, `POST /import/project`, `GET /export/xml|sql|project|table-xml|table-sql` |
| Conversion/sync | `POST /convert/xml-to-sql`, `POST /convert/sql-to-xml`, `POST /databases/:id/sync-xml`, `POST /tables/:id/sync-xml` |
| Protection | `POST /unlock-table`, `GET /unlocks`, `DELETE /unlocks` |
| Utilisateurs (ADMIN) | `GET/POST /users`, `GET/PUT/DELETE /users/:id`, `reset-password`, `toggle-active` |
| Audit/historique (ADMIN) | `GET /history`, `GET /audit-logs` |
| TCP | `GET /tcp/status`, `GET /tcp/credentials`, `POST .../regenerate`, `POST .../show-password`, `GET /tcp/sessions` |

---

## 7. Adaptations imposées par la logique backend (modèle ≠ backend)

| Élément du modèle | Réalité backend | Décision frontend |
|---|---|---|
| Rôles `VIEWER / EDITOR / ADMIN` | Rôles réels : `admin`, `user` | Sélecteur limité à **USER / ADMIN** (backend prioritaire) |
| « Commune — visible par tous les membres » (toggle) | `COMMON` est un simple filtre ; aucune visibilité automatique | Toggle supprimé ; encart d'information : partage explicite requis |
| Checklist ACL dans le modal de création de base | `POST /databases` n'accepte pas de permissions | Non reproduit ; partage via « Gérer les accès » (email + VIEW/EDIT/MANAGE) |
| Bouton « Générer une clé API » | Aucun endpoint de gestion de clés API | Bouton désactivé + encart explicite (aucun token fictif) |
| TCP « Base à exposer » + boutons Se connecter / Se déconnecter | Aucun endpoint web de connexion/déconnexion TCP (le serveur démarre au boot du backend) | Remplacé par statut réel (host/port/running/sessions) + credentials + client Python |
| `simulateImport`, `simulateConflict`, `generateApiKey`, données mock | — | Non portés ; vrais endpoints et vraies données uniquement |
| Panneaux XML/SQL en `<pre>` statique avec coloration | Éditeur nécessaire (modification XML) | **MonacoEditor conservé** (éditable, lecture seule selon droits) ; en-têtes alignés sur le modèle |

---

## 8. Incohérences restantes / points à connaître

1. **Clés API** : section présente visuellement mais sans endpoint backend
   (bouton désactivé, message explicite).
2. **Export global multi-bases** : l'export « complet » est par base
   (`/export/project/:id`) ; pas d'export de toutes les bases.
3. **Socket.IO** : optionnel et désactivé par défaut (`VITE_ENABLE_SOCKET_IO`),
   sans authentification/cloisonnement par rooms côté événements. REST suffit.
4. **Moteur SQL** : `SELECT/INSERT/UPDATE/DELETE` uniquement (pas de JOIN,
   GROUP BY, agrégats, sous-requêtes, DDL).
5. **Cascades FK** : `ON DELETE`/`ON UPDATE` stockés dans le XML/DDL mais non
   rejoués automatiquement comme effets en cascade dans le XML.
6. **Déverrouillage** : nécessite `can_write` sur la table (un VIEW ne peut pas
   déverrouiller pour écrire).
7. **Droits de table** : additifs, ne révoquent jamais un droit de base ; un
   partage de table seul ne rend pas la base sélectionnable (rappel affiché
   dans les modales de partage).

---

## 9. Vérifications effectuées (cette étape)

Environnement réel monté pour vérification : backend Flask (`0.0.0.0:5000`,
TCP `0.0.0.0:3307`) + frontend Vite (`0.0.0.0:5173`).

```text
npm run lint     → 0 erreur, 3 avertissements fast-refresh (préexistants)
npm run build    → ✓ build (Vite 8.1.5)
npm test         → 10 tests passés, 1 live test ignoré par défaut
npm run test:e2e → 1 test Playwright passé (20,6 s)
                   registre → login → dashboard → base COMMON → table →
                   colonne → ligne → conflit 409 → settings TCP
```

Vérifications API complémentaires (compte ADMIN réel créé via
`flask create-admin`) :

```text
GET /users, POST /users, PUT /users/:id (rôle), POST /users/:id/reset-password,
POST /users/:id/toggle-active, GET /history, GET /audit-logs,
GET /tcp/credentials, GET /tcp/sessions, GET /tcp/status  →  tous HTTP 200/201
```

**Second passage de vérification** (re-contrôle complet après comparaison
CSS bloc-à-bloc du modèle vs `maquette.css`) :
- CSS : plus aucun sélecteur du modèle manquant (seule nuance : `border-radius`
  et `margin-bottom` du `.conflict-banner` sont portés dans la feuille plutôt
  qu'en style inline — équivalent visuel).
- Libellés distinctifs du modèle présents dans le React (« Retirer la
  protection définitivement », « Reconstruire la projection », « Table
  référencée », « Colonne référencée », « Supprimer définitivement »…).
- Re-vérification complète rejouée : lint 0 erreur, build ✓, 10 tests unitaires
  passés, 1 test Playwright passé (20,6 s).

---

## 10. Livrables

- Frontend React adapté au modèle (fichiers listés en §3).
- `FRONTEND_MODEL_INTEGRATION.md` (ce document).
- Le modèle reste disponible tel que fourni (`uploads/xmlforge (7).html`) et
  n'a pas été modifié.
