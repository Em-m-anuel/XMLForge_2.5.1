> ⚠️ **DOCUMENT HISTORIQUE** — décrit l'état du dépôt au 14 août 2026 (control plane SQLAlchemy, projection SQLite). Ne décrit pas l'architecture runtime actuelle (XML-only depuis la Phase 6J-B). Conservé comme archive.

# Manuel complet de test et de validation de XMLForge

> **État analysé :** code présent dans le dépôt le 14 août 2026, branche `main`, base Git `ccfd9c57f0345799bfe95167ac85bda82c7787f5`, y compris les modifications non validées présentes dans l’espace de travail.  
> **Périmètre :** frontend React/Vite, API Flask, control plane SQLAlchemy, document XML canonique, projection SQLite, protocole TCP/IP, tests automatisés.  
> **Règle de lecture :** ce manuel décrit le code réellement présent. Lorsqu’une valeur d’exploitation n’existe pas dans le dépôt, elle est indiquée comme **« À renseigner / non déterminé dans le code actuel »**.

---

## 0. Résumé exécutable

Le circuit réellement implémenté est le suivant :

```text
Navigateur
   |
   | HTTP REST + JWT, préfixe /api
   v
Frontend React (Vite : 5173 par défaut)
   |
   v
Backend Flask (5000, fixé dans run.py)
   |
   +--> control plane SQLAlchemy
   |      backend/xmlforge.db par défaut
   |      utilisateurs, rôles, ACL, catalogue, audit, historique,
   |      credentials TCP et déverrouillages
   |
   +--> XML canonique, source persistante de vérité
   |      backend/data/xml/<id>_<slug>.xml par défaut
   |
   +--> projection relationnelle SQLite reconstruite depuis le XML
          backend/data/projections/<id>_<slug>.sqlite par défaut

Application externe
   |
   | protocole TCP binaire JSON, 3307 par défaut
   v
TCPServer -> authentification TCP -> QueryService
   |                                  |
   | SELECT                           +--> lecture de la projection SQLite
   | INSERT/UPDATE/DELETE             +--> mutation XML puis reconstruction SQLite
   v
Réponse TCP

Retour dans XMLForge : actualiser l’onglet Données ou rouvrir la table via REST.
```

Points essentiels :

- le navigateur **n’ouvre pas de socket TCP** ; il utilise REST ;
- REST et TCP réutilisent le même `QueryService` pour le sous-ensemble SQL de données ;
- les écritures ne modifient pas directement le fichier SQLite en service : elles modifient le document XML sous verrou, valident une nouvelle projection temporaire, puis promeuvent les deux artefacts ;
- `COMMON` ne rend pas une base automatiquement visible : une ACL explicite reste obligatoire ;
- les rôles globaux réellement présents sont uniquement `user` et `admin` ;
- les niveaux affichés `VIEW`, `EDIT`, `MANAGE` sont des synthèses d’ACL, pas des rôles globaux ;
- aucune clé API n’est implémentée ;
- le TCP n’accepte pas le DDL : seulement `SELECT`, `INSERT`, `UPDATE`, `DELETE` dans le sous-ensemble documenté plus bas.

### 0.1 Architecture frontend constatée

- React 19 + React Router + Vite ;
- routes publiques : `/login`, `/register` ;
- routes authentifiées : `/dashboard`, `/database/:databaseId`, `/workspace/:dbName`, `/settings` ;
- routes admin : `/users`, `/history`, `/audit` ;
- `AuthContext` restaure le JWT par `GET /me` et calcule le rôle depuis le profil Flask ;
- `DatabaseContext` restaure seulement les IDs de tables que le backend confirme comme déverrouillées ; aucune clé de protection n’est conservée côté frontend ;
- tous les appels HTTP de production passent par `src/services/api.js` ;
- `ApiError` centralise 401/403/404/409/400/422/500 et les erreurs réseau ;
- Monaco affiche/édite les panneaux XML et SQL ;
- le Workspace expose 4 onglets par table : **Structure**, **Données**, **Relations**, **Avancé** (protection, reconstruction de projection, synchronisation/conflits) ;
- le modal de colonne couvre les contraintes simples : PK, FK (listes déroulantes table/colonne), `UNIQUE`, `AUTO_INCREMENT`, index, `DEFAULT`, nullable et actions `ON DELETE`/`ON UPDATE` ;
- le Dashboard propose un import à 3 modes : **XML**, **SQL**, **Projet XMLForge** ;
- le partage est géré graphiquement pour la base (Dashboard et Workspace) et pour la table (Workspace) ;
- le retrait de protection est disponible graphiquement (« Ôter la protection » / « Retirer la protection définitivement ») ;
- Socket.IO est facultatif et désactivé par défaut.

### 0.2 Architecture backend constatée

- factory Flask, blueprints REST avec aliases `/api` ;
- JWT, bcrypt, révocation de token et `token_version` ;
- SQLAlchemy pour le control plane ;
- `PermissionService` commun aux routes et au TCP ;
- `XmlEngineService` pour lecture, versionnement, validation, commit et reconstruction ;
- `QueryService` commun au endpoint SQL REST et au serveur TCP ;
- XSD canonique chargé depuis `backend/app/static/xmlforge.xsd` ;
- serveur TCP multiclient dans un thread daemon ;
- Socket.IO sur le même serveur HTTP que Flask ;
- migrations idempotentes du control plane, version courante `6`.

---

# Partie I — Préparation et démarrage

## 1. Prérequis

### 1.1 Logiciels obligatoires

| Élément | Exigence réellement déterminable |
|---|---|
| Python | Python 3 est requis. Version minimale formellement déclarée : **À renseigner / non déterminé dans le code actuel**. L’environnement d’analyse utilise Python 3.13. |
| `venv` et `pip` | requis pour installer `backend/requirements.txt` |
| Node.js | le lockfile installe Vite `8.1.5`, qui déclare `^20.19.0 || >=22.12.0` |
| npm | requis ; version minimale du projet : **À renseigner / non déterminé dans le code actuel** |
| Navigateur moderne | requis pour React, `localStorage`, `sessionStorage`, Monaco et les téléchargements Blob |
| MySQL | **facultatif** ; uniquement pour `POST /api/database/create`. Le circuit XML/SQLite principal n’en a pas besoin. |
| `curl` | facultatif, utilisé dans certains contrôles REST de ce manuel |
| client `sqlite3` en ligne de commande | facultatif ; les vérifications proposées utilisent aussi la bibliothèque Python standard `sqlite3` |

### 1.2 Ports par défaut

| Service | Adresse/port par défaut | Source |
|---|---|---|
| Flask + REST + Socket.IO | `0.0.0.0:5000` | fixé dans `backend/run.py` |
| TCP XMLForge | `0.0.0.0:3307` | `TCP_HOST`, `TCP_PORT` |
| Frontend Vite | `0.0.0.0:5173` en principe | Vite choisit son port par défaut et peut en prendre un autre si 5173 est occupé |
| MySQL optionnel | `localhost:3306` | `MYSQL_HOST`, `MYSQL_PORT` |
| application `tcp-tester` optionnelle | `3000` | `APP_PORT` dans `tcp-tester` |

Pour un client local, utiliser `127.0.0.1`, pas `0.0.0.0`. `0.0.0.0` est une adresse d’écoute serveur.

### 1.3 État initial du dépôt

Dans l’état analysé :

- aucun `backend/xmlforge.db` n’est versionné ;
- aucun fichier runtime n’est présent dans `backend/data/xml/` ou `backend/data/projections/` ;
- aucun compte n’est donc garanti après un clone neuf ;
- aucune base logique n’est automatiquement importée au premier démarrage.

Fichiers XML d’exemple présents :

- `backend/BaseDonnees_INPTIC.xml` : non vide, racine `database`, nom `INPTIC_Partenariats`, conforme au XSD au moment de l’analyse ;
- `backend/test.xml` : non vide, racine `database`, nom `Bibliotheque`, conforme au XSD au moment de l’analyse ;
- `backend/InptricConcours_database.xml`, `backend/base_donnees_alumni_inptic.xml`, `backend/inptic_database_schema.xml` et `backend/soutenance_app.xml` : fichiers vides, donc non importables tels quels.

Ces fichiers ne deviennent des bases XMLForge qu’après un import explicite.

---

## 2. Installation

Les commandes suivantes partent de la racine du dépôt.

### 2.1 Backend — Linux/macOS

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
```

### 2.2 Backend — Windows PowerShell

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

### 2.3 Frontend

Dans un second terminal :

```bash
cd xmlforge-react
npm ci
cp .env.example .env
```

Sous PowerShell :

```powershell
cd xmlforge-react
npm ci
Copy-Item .env.example .env
```

`npm ci` est préférable pour reproduire exactement `package-lock.json`.

---

## 3. Configuration réelle

### 3.1 Variables backend

Fichier : `backend/.env`.

| Variable | Valeur par défaut/comportement | Obligatoire pour ce manuel |
|---|---|---|
| `SECRET_KEY` | secret de développement codé par défaut | définir une valeur non triviale |
| `JWT_SECRET_KEY` | secret JWT de développement codé par défaut | définir une valeur non triviale |
| `JWT_EXPIRES_HOURS` | `24` | non |
| `DATABASE_URL` | vide = `sqlite:///.../backend/xmlforge.db` | laisser vide pour le scénario standard |
| `XML_STORAGE_FOLDER` | vide = `backend/data/xml` | non |
| `SQLITE_PROJECTION_FOLDER` | vide = `backend/data/projections` | non |
| `SQLITE_BUSY_TIMEOUT_MS` | `1000` | non |
| `SQLITE_LOCK_RETRIES` | `5` | non |
| `SQLITE_RETRY_BASE_DELAY_MS` | `50` | non |
| `TCP_ENABLED` | `true` | oui pour les tests TCP |
| `TCP_HOST` | `0.0.0.0` | non |
| `TCP_PORT` | `3307` | non |
| `TCP_SESSION_TIMEOUT_MINUTES` | `30` | non |
| `ALLOW_UNSAFE_WERKZEUG` | `true` | oui pour `python run.py` en local ; mettre `false` en production |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000` | vérifier si le frontend est ouvert depuis une autre origine |
| `MYSQL_HOST` | `localhost` | seulement pour l’export physique MySQL optionnel |
| `MYSQL_PORT` | `3306` | idem |
| `MYSQL_USER` | `root` | idem |
| `MYSQL_PASSWORD` | vide | idem |
| `MYSQL_DATABASE` | vide | présent dans la configuration mais non utilisé par le circuit principal |
| `FLASK_ENV` | présent dans l’exemple | pas lu directement par `app.config.Config` |
| `FLASK_APP` | présent dans l’exemple | le manuel utilise explicitement `--app run.py` |

Configuration locale minimale recommandée :

```dotenv
SECRET_KEY=<CHOISIR_UN_SECRET_LOCAL>
JWT_SECRET_KEY=<CHOISIR_UN_SECRET_JWT_LOCAL>
JWT_EXPIRES_HOURS=24
DATABASE_URL=
XML_STORAGE_FOLDER=
SQLITE_PROJECTION_FOLDER=
TCP_ENABLED=true
TCP_HOST=0.0.0.0
TCP_PORT=3307
TCP_SESSION_TIMEOUT_MINUTES=30
ALLOW_UNSAFE_WERKZEUG=true
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

Ne pas recopier les placeholders entre chevrons en production.

### 3.2 Variables frontend

Fichier : `xmlforge-react/.env`.

```dotenv
VITE_API_URL=/api
VITE_SOCKET_URL=http://localhost:5000
VITE_ENABLE_SOCKET_IO=false
```

Comportement réel :

- `/api` passe par le proxy Vite vers `http://localhost:5000` ;
- `/socket.io` est également proxifié ;
- Socket.IO est désactivé par défaut et aucune fonction métier n’en dépend ;
- le mode Socket.IO actuel ne crée pas de rooms ACL par base et diffuse globalement les événements. Ne l’activer que dans un environnement de test maîtrisé.

### 3.3 Valeurs d’exploitation absentes du dépôt

- URL publique de production : **À renseigner / non déterminé dans le code actuel**.
- nom DNS ou IP d’un serveur TCP distant : **À renseigner / non déterminé dans le code actuel**.
- configuration pare-feu/VPN : **À renseigner / non déterminé dans le code actuel**.
- serveur WSGI de production : **À renseigner / non déterminé dans le code actuel**.
- instance MySQL et credentials MySQL : **À renseigner / non déterminé dans le code actuel**.

---

## 4. Lancer XMLForge

### 4.1 Créer un administrateur avant le premier lancement

Aucun administrateur neuf n’est codé en dur. Depuis `backend`, environnement virtuel actif :

```bash
flask --app run.py create-admin
```

La commande demande :

- `Email` ;
- `Name` ;
- `Password` avec confirmation.

Elle crée le compte s’il n’existe pas, lui attribue le rôle persistant `admin` et l’active. Les valeurs sont choisies par l’opérateur ; elles ne sont pas fournies par le dépôt.

> Exécuter de préférence ce bootstrap avant `python run.py`. L’import de l’application initialise aussi le serveur TCP ; si le port est déjà occupé, Flask consigne l’échec TCP mais le control plane peut tout de même être initialisé.

### 4.2 Lancer le backend

Depuis `backend` :

```bash
python run.py
```

Résultat attendu :

- Flask écoute sur le port `5000` ;
- le control plane est créé/migré ;
- les rôles `admin` et `user` sont seedés ;
- les XML existants du control plane sont relus ;
- leurs projections SQLite sont reconstruites ;
- le serveur TCP est démarré si `TCP_ENABLED=true`.

Contrôles :

```bash
curl http://127.0.0.1:5000/health
curl http://127.0.0.1:5000/api/tcp/status
```

Réponses attendues, valeurs de session variables omises :

```json
{"service":"XMLForge Backend V4","status":"ok","version":"4.0.0"}
```

et une enveloppe de succès contenant notamment :

```json
{
  "success": true,
  "data": {
    "running": true,
    "host": "0.0.0.0",
    "port": 3307,
    "active_sessions": 0
  }
}
```

Le texte de version V4/V5 n’est pas uniforme dans tous les fichiers. Pour les tests fonctionnels, les routes et modèles décrits dans ce manuel sont l’autorité.

### 4.3 Lancer le frontend

Depuis `xmlforge-react` :

```bash
npm run dev
```

Ouvrir l’URL indiquée par Vite, normalement :

```text
http://localhost:5173
```

Si Vite choisit un autre port, ajouter cette origine à `CORS_ORIGINS`, redémarrer Flask et utiliser l’URL affichée.

### 4.4 Arrêt propre

- arrêter Vite avec `Ctrl+C` ;
- arrêter Flask avec `Ctrl+C` ; le thread TCP est un thread daemon ;
- ne pas supprimer manuellement un fichier de projection pendant que Flask est en cours d’exécution.

---

# Partie II — Comptes, rôles et accès

## 5. Première connexion

### 5.1 Aucun compte de test préinstallé

Un clone neuf ne contient pas de control plane versionné. Les scripts historiques `create_test_user.py` et `create_yann_user.py` définissent des comptes lorsqu’ils sont exécutés, mais ils ne prouvent pas que ces comptes existent dans l’installation courante. Le scénario de référence utilise donc les mécanismes normaux.

### 5.2 Créer un utilisateur normal

1. Ouvrir `/register` ou cliquer **Créer un compte** depuis la connexion.
2. Saisir un nom, un email valide et un mot de passe d’au moins 6 caractères.
3. Confirmer le mot de passe.
4. Cliquer **Créer mon compte**.
5. Revenir sur `/login` et se connecter.

Appels réels :

```text
POST /api/register
POST /api/login
GET  /api/me lors de la restauration de session
```

Le nouveau compte reçoit toujours le rôle `user`. Le JWT est conservé dans `localStorage` sous `xmlforge_token`, et le profil sous `xmlforge_user`.

### 5.3 Ce qui doit être visible

Après connexion :

- URL `/dashboard` ;
- titre **Mes bases de données** ;
- liste vide sur une installation neuve ;
- filtres **Toutes**, **Personnelles**, **Communes** ;
- actions **Importer** (modale à 3 modes : XML / SQL / Projet XMLForge), **Export complet**, **Nouvelle base** ;
- menu **Bases de données** et **API & TCP/IP** ;
- pas de menu **Utilisateurs**, **Historique** ni **Audit** pour un rôle `user`.

### 5.4 Fiche de données de test

Renseigner ces valeurs avant les scénarios :

```text
ADMIN_EMAIL       = À renseigner / non déterminé dans le code actuel
ADMIN_PASSWORD    = À renseigner / non déterminé dans le code actuel
USER_A_EMAIL      = À renseigner / non déterminé dans le code actuel
USER_A_PASSWORD   = À renseigner / non déterminé dans le code actuel
USER_B_EMAIL      = À renseigner / non déterminé dans le code actuel
USER_B_PASSWORD   = À renseigner / non déterminé dans le code actuel
```

Créer A et B via `/register`, et l’administrateur via la commande CLI.

---

## 6. Rôles réellement implémentés

### 6.1 Rôle `user`

Un utilisateur actif :

- peut créer une base `PERSONAL` ou `COMMON` ;
- est propriétaire de ses bases et obtient `MANAGE` sur elles ;
- peut partager ses propres bases ;
- peut lire/modifier une base partagée selon son ACL ;
- peut obtenir ses propres credentials TCP ;
- ne peut pas gérer globalement les comptes ;
- ne peut pas consulter les pages administratives Historique/Audit ;
- ne voit pas les bases non partagées d’autres utilisateurs.

### 6.2 Rôle `admin`

Un administrateur actif :

- obtient lecture, écriture, DDL et administration sur toutes les bases ;
- voit toutes les bases `PERSONAL` et `COMMON` ;
- accède à `/users`, `/history`, `/audit` ;
- peut créer, modifier, activer/désactiver et supprimer des utilisateurs sous les garde-fous décrits ci-dessous ;
- reste soumis à la protection des tables pour les mutations : le rôle admin ne contourne pas automatiquement une clé de protection.

Garde-fous backend :

- impossible de désactiver, rétrograder ou supprimer le dernier administrateur actif ;
- impossible pour un administrateur de supprimer son propre compte ;
- impossible de supprimer un utilisateur qui possède encore des bases ;
- une désactivation, un changement de mot de passe ou certains changements de statut incrémentent `token_version` et invalident les JWT antérieurs.

### 6.3 Test utilisateur normal

1. Se connecter avec A.
2. Vérifier l’absence des menus administratifs.
3. Créer une base personnelle.
4. Créer une table, des colonnes et des lignes.
5. Ouvrir directement `/users`.
6. Résultat frontend attendu : écran **Accès refusé**.
7. Appeler `GET /api/users` avec le JWT de A.
8. Résultat backend attendu : HTTP `403`, message `Accès refusé: rôle administrateur requis`.

### 6.4 Test administrateur

1. Se connecter avec le compte créé par `create-admin`.
2. Vérifier les menus **Historique**, **Utilisateurs**, **Audit**.
3. Ouvrir **Utilisateurs**.
4. Créer un utilisateur avec le rôle `user` ou `admin`.
5. Modifier son rôle.
6. Le désactiver puis vérifier qu’une nouvelle connexion échoue avec `Compte désactivé, contactez l'administrateur`.
7. Le réactiver.
8. Vérifier les traces correspondantes dans Audit et, pour les opérations prises en charge, Historique.

Limites frontend de la page Utilisateurs :

- l’édition graphique ne change que le rôle ; le backend accepte aussi `full_name`, `email` et `is_active` via REST ;
- la réinitialisation de mot de passe est accessible graphiquement (icône clé → modale, minimum 6 caractères, `POST /api/users/<id>/reset-password`) ;
- la suppression passe par une modale de confirmation (le backend protège le dernier admin actif et refuse la suppression d’un utilisateur propriétaire de bases) ;
- l’activation/désactivation est disponible via l’icône dédiée (`POST /api/users/<id>/toggle-active`).

---

## 7. ACL : `VIEW`, `EDIT`, `MANAGE`

Les droits persistants sont :

```text
can_read
can_write
can_ddl
can_admin
```

Les niveaux affichés par le frontend sont calculés ainsi :

| Niveau UI | Preset créé par le frontend | Effet pratique |
|---|---|---|
| `VIEW` | lecture seule | lister/ouvrir, voir structure et rows, requêtes `SELECT`, export SQL |
| `EDIT` | `read + write + ddl` | `VIEW` + CRUD rows + création/modification/suppression de tables et colonnes |
| `MANAGE` | `read + write + ddl + admin` | `EDIT` + partage, suppression/archivage de base, changement de scope, exports contenant les secrets de protection |

Nuances réelles :

1. Le backend accepte des combinaisons fines ne correspondant pas exactement aux trois presets.
2. `level=EDIT` est affiché si `can_write` **ou** `can_ddl` est vrai.
3. `level=MANAGE` est affiché si `can_admin` est vrai, même si un appel REST manuel n’a pas accordé les autres bits.
4. Le frontend accorde toujours les combinaisons complètes du tableau.
5. Une permission de table est additive : elle ne retire pas un droit de base.
6. La gestion graphique expose le partage au niveau base. Les endpoints de partage au niveau table existent, mais n’ont pas d’interface dédiée.
7. Une permission de table seule ne rend pas la base découvrable sur le dashboard ni sélectionnable en TCP ; accorder au moins la lecture de la base pour un scénario normal.

### 7.1 Test d’accès interdit

Avec B sans partage :

```bash
curl -i http://127.0.0.1:5000/api/databases/<DATABASE_ID_A> \
  -H "Authorization: Bearer <JWT_B>"
```

Attendu : HTTP `403`, message `Accès refusé`.

Après partage `VIEW`, tenter :

```bash
curl -i -X POST http://127.0.0.1:5000/api/tables/<TABLE_ID>/rows \
  -H "Authorization: Bearer <JWT_B>" \
  -H "Content-Type: application/json" \
  -d '{"data":{"nom":"Interdit","email":"interdit@example.invalid"}}'
```

Attendu : HTTP `403`, avec un message contenant `Permission write refusée`.

### 7.2 Recette par niveau

#### `VIEW`

1. A partage une base à B en `VIEW`.
2. B se connecte et ouvre la base.
3. Autorisé : lister tables/colonnes/rows, rechercher, trier, paginer, exécuter un `SELECT`, exporter le SQL.
4. Refusé : créer/modifier/supprimer une row, changer la structure, partager, supprimer/archiver la base, exporter les secrets XML/projet.
5. Attendu REST pour une écriture : `403`.

#### `EDIT`

1. A réaccorde la même permission en `EDIT`.
2. B actualise.
3. Autorisé : tout `VIEW`, CRUD rows, création/renommage/suppression/archivage de tables et colonnes.
4. Refusé : gestion des ACL, suppression/archivage de la base, changement de scope, export XML/projet contenant les secrets.
5. Édition de base : le modal n’envoie le `scope` que si l’utilisateur a `can_admin` ; un `EDIT` renomme/décrit donc la base sans recevoir `403`, mais ne peut pas changer la portée.

#### `MANAGE`

1. A réaccorde la permission en `MANAGE`.
2. B actualise.
3. Autorisé sur cette base : lecture, rows, DDL, ACL, scope, archive/suppression et export complet.
4. Toujours refusé sans rôle global `admin` : pages Utilisateurs, Historique et Audit.
5. Toujours soumis à clé/unlock : mutation d’une table protégée.

---

# Partie III — Bases, tables et données

## 8. Test complet d’une base `PERSONAL`

Utiliser des identifiants SQL simples : lettres, chiffres et underscore, sans commencer par un chiffre. Le parseur XML impose réellement :

```regex
^[A-Za-z_][A-Za-z0-9_]*$
```

Cette règle s’applique aux noms de base, table, colonne et index. Les modales de création (base, table, colonne) ne prévalident pas le format ; un nom avec espace ou parenthèses échoue donc au backend. En revanche l’action **Dupliquer** du Dashboard assainit désormais le nom généré (voir §16.6).

### 8.1 Créer la base

1. Connexion : utilisateur A.
2. Dashboard → **Nouvelle base**.
3. Nom : `validation_personal`.
4. Description : libre.
5. Visibilité : `PERSONAL`.
6. Cliquer **Créer la base**.

Circuit réel :

| Couche | Action |
|---|---|
| Frontend | `databaseService.create(...)` |
| REST | `POST /api/databases` |
| Backend | `DatabaseService.create` crée owner, scope et clé interne de base |
| Control plane | ajoute une ligne dans `databases` |
| XML | crée le document canonique version 1 |
| Projection SQLite | crée un fichier SQLite vide de tables métier |
| Réponse | carte avec `access.level=MANAGE`, `scope=PERSONAL`, `document_version=1` |

### 8.2 Créer la table `contacts`

1. Ouvrir la carte.
2. Cliquer **Nouvelle table**.
3. Nom : `contacts`.
4. Laisser activé **Ajouter automatiquement une clé primaire "id"**.
5. Cliquer **Créer la table**.

Le frontend effectue deux mutations réelles :

1. `POST /api/tables` avec l’`expected_version` courant ;
2. `POST /api/columns` pour `id INT PRIMARY KEY AUTO_INCREMENT NOT NULL`, avec la nouvelle version.

Chaque mutation :

```text
lit XML -> vérifie expected_version -> modifie -> version + 1
-> construit une projection temporaire -> synchronise le catalogue
-> écrit/promouvoit XML et SQLite -> répond
```

### 8.3 Ajouter `nom` et `email`

Dans **Structure** → **Ajouter une colonne** :

- `nom` : `VARCHAR`, longueur `100`, désactiver `Nullable` ;
- `email` : `VARCHAR`, longueur `255`, désactiver `Nullable`, activer `Unique`.

Le modal de colonne expose désormais l’ensemble des contraintes simples :

- nom, type (liste complète des types autorisés par le document canonique), longueur, valeur par défaut ;
- `Nullable`, `Unique` ;
- `Clé primaire`, `Auto-incrément`, `Index` ;
- `Clé étrangère` avec listes déroulantes **Table référencée** / **Colonne référencée** (colonnes réelles chargées depuis le backend) et actions `ON DELETE` / `ON UPDATE`.

Les cas avancés (PK composite, FK complexe déclarée au niveau table, index composé) restent à faire via l’éditeur XML ou l’API REST, comme indiqué dans l’encart du modal.

### 8.4 Ajouter, modifier et supprimer des lignes

1. Onglet **Données**.
2. **Ajouter une ligne**.
3. Laisser `id` vide pour l’auto-incrément.
4. Ajouter par exemple trois lignes avec des emails distincts.
5. Modifier la deuxième ligne avec l’icône crayon.
6. Supprimer la troisième avec l’icône corbeille.
7. Cliquer **Actualiser**.

Circuit d’un `INSERT` UI :

```text
Modal React
  -> rowService.create(tableId, data, documentVersion)
  -> POST /api/tables/<table_id>/rows
  -> RowService.create
  -> QueryService.insert
  -> mutation du tableau rows dans le document XML
  -> auto-incrément calculé à partir des lignes XML existantes
  -> validation/reconstruction de la projection SQLite
  -> synchronisation de TableRow.data_json dans le control plane
  -> réponse JSON puis relecture de la table dans React
```

Routes pour les trois opérations :

```text
POST   /api/tables/<table_id>/rows
PUT    /api/tables/<table_id>/rows/<row_id>
DELETE /api/tables/<table_id>/rows/<row_id>
```

### 8.5 Vérifications négatives

- Réutiliser un email : l’interface rows reçoit actuellement HTTP `400` avec un message de contrainte SQLite.
- Faire la même insertion via `/api/databases/<id>/query` : le moteur commun renvoie HTTP `409`, code `CONSTRAINT_VIOLATION`.
- Saisir du texte dans une colonne entière : HTTP `400` via la route rows.
- Supprimer une base archivée : refus ; il faut d’abord la restaurer.

La différence `400`/`409` entre la façade rows et la façade query est une incohérence actuelle à conserver dans les attentes de test.

---

## 9. Test complet d’une base `COMMON`

### 9.1 Comportement réel de `COMMON`

- Tout utilisateur authentifié peut créer `COMMON` ; ce n’est pas réservé à l’admin.
- `COMMON` est un attribut de portée et un filtre visuel.
- B ne voit **pas** automatiquement une base commune créée par A.
- Une ACL explicite est nécessaire.
- Une base `PERSONAL` peut également être partagée : le backend ne bloque pas ce cas.

### 9.2 Scénario A/B

1. A crée `validation_common` avec portée `COMMON`.
2. B se connecte.
3. Résultat attendu avant partage : B ne voit pas la base.
4. A se reconnecte.
5. Menu contextuel de la carte → **Gérer les accès**.
6. Saisir l’email réel de B.
7. Accorder `VIEW`.
8. B se reconnecte ou actualise.
9. B voit la carte avec `Commune` et `accès VIEW`.
10. B ouvre la base et lit structure/données.
11. B tente une écriture : bouton désactivé dans l’UI ; appel REST direct = `403`.
12. A remplace le partage par `EDIT` en accordant à nouveau l’email avec `EDIT`.
13. B actualise, ajoute/modifie une ligne ou une colonne.
14. A actualise et vérifie la modification.
15. A passe B à `MANAGE`.
16. B peut alors gérer les accès et exporter le projet complet.
17. A retire B avec la croix de la modale de partage.
18. B actualise : la base disparaît. Une session TCP déjà ouverte reçoit également un refus à la requête suivante, car les ACL sont réévaluées.

### 9.3 Comportement de l’édition de base selon le niveau

Le backend autorise la modification du nom/description avec `can_write`, mais exige `can_admin` dès que la clé `scope` est présente dans le corps du `PUT`. Le frontend en tient compte : le modal **Modifier la base** n’envoie le champ `scope` que si l’utilisateur dispose de `can_admin` (le sélecteur de portée est sinon désactivé). Un utilisateur `EDIT` peut donc renommer et décrire la base, mais pas changer sa portée — et l’enregistrement ne produit plus de `403` sur ce chemin. Les modifications de tables, colonnes et rows restent disponibles selon les droits.

---

## 10. Test détaillé des tables et contraintes

### 10.1 Capacités backend actives

| Fonction | Backend/XML/SQLite | Interface actuelle |
|---|---|---|
| création, renommage, suppression de table | oui | oui |
| archivage/restauration | oui | oui |
| ajout/modification/suppression de colonne | oui | oui |
| PK simple/composite | oui | PK simple via checkbox du modal ; composite via XML/REST |
| FK | oui, `references=table.colonne` | listes déroulantes table/colonne dans le modal + onglet Relations ; complexe via XML/REST |
| `UNIQUE` | oui | oui, simple colonne |
| `NULL` / `NOT NULL` | oui | oui |
| `DEFAULT` | oui | oui |
| `AUTO_INCREMENT` | oui pour PK entière | checkbox du modal + auto sur `id` |
| index simple/composite | oui dans XML/projection | index simple via checkbox ; composite via XML/REST |
| actions FK | `NO ACTION`, `RESTRICT`, `SET NULL`, `SET DEFAULT`, `CASCADE` validées dans le DDL SQLite | `ON DELETE` / `ON UPDATE` dans le modal (`NO ACTION`, `RESTRICT`, `CASCADE`, `SET NULL`) |
| commentaires/statuts | routes backend présentes | exposition partielle (pas d’édition de commentaire dans l’UI) |

Types acceptés par le document canonique :

```text
INTEGER, INT, BIGINT, SMALLINT, TINYINT,
TEXT, VARCHAR, CHAR, CLOB,
REAL, FLOAT, DOUBLE, DECIMAL, NUMERIC,
BOOLEAN, BOOL, DATE, DATETIME, TIMESTAMP, TIME,
BLOB, JSON
```

La projection ramène les familles entières et booléennes vers `INTEGER`, les flottants vers `REAL`, les décimaux vers `NUMERIC`, `BLOB` vers `BLOB`, et le reste vers `TEXT`.

Limite importante des actions FK : les écritures sont d’abord appliquées au document XML, puis la projection est reconstruite. Le code ne propage pas automatiquement dans le document XML les effets d’un `CASCADE`, `SET NULL` ou `SET DEFAULT` déclenchés par un DML SQLite. Tester `RESTRICT`/intégrité est fiable ; ne pas valider un workflow de cascade automatique comme acquis sans test additionnel et correction du write-back XML.

### 10.2 Test FK réel

1. Créer une table `departements` avec l’`id` automatique.
2. Ajouter une ligne dans `departements`.
3. Dans `contacts`, ajouter `departement_id` de type `INT`.
4. En tant que propriétaire/MANAGE, sélectionner `contacts`.
5. Deux chemins équivalents pour déclarer la FK :
   - **modal de colonne** : ouvrir **Ajouter une colonne**, cocher `Clé étrangère`, choisir `departements` dans **Table référencée** puis `id` dans **Colonne référencée**, régler `ON DELETE`/`ON UPDATE`, enregistrer ; ou
   - **XML Source** : modifier l’attribut de la colonne comme suit :

```xml
<column
  name="departement_id"
  type="INT"
  length="-"
  nullable="false"
  primary_key="false"
  foreign_key="true"
  unique="false"
  auto_increment="false"
  index="true"
  references="departements.id"
  on_delete="RESTRICT"
  on_update="NO ACTION"
  uuid="..."
  status="ACTIVE"/>
```

6. Selon le chemin choisi : cliquer **Appliquer les modifications** (éditeur XML) ou **Enregistrer** (modal).
7. Ouvrir l’onglet **Relations** : la relation sortante doit apparaître.
8. Ajouter un contact avec un `departement_id` existant : succès.
9. Ajouter un contact avec une valeur inexistante : rejet de contrainte.
10. Vérifier `PRAGMA foreign_key_list("contacts")` dans la projection.

L’éditeur XML n’est modifiable que pour `MANAGE` et, si la table est protégée, après déverrouillage.

### 10.3 Suppressions structurelles

Le backend refuse :

- la suppression d’une table encore référencée par une FK ;
- la suppression d’une colonne encore référencée ;
- l’ajout d’une valeur incompatible avec son type ;
- `AUTO_INCREMENT` sur une colonne qui n’est pas une PK entière.

La suppression d’une colonne retire aussi cette clé des rows XML de la table et retire les index qui la contiennent.

---

## 11. Test des données, recherche, tri et pagination

### 11.1 Affichage

`GET /api/tables/<table_id>/rows` renvoie l’enveloppe standard ; son champ `data` a cette forme lorsque le frontend demande une page de 25 éléments :

```json
{
  "rows": [],
  "total": 0,
  "limit": 25,
  "offset": 0,
  "table": {}
}
```

Le frontend utilise :

- taille de page fixe : `25` ;
- recherche texte sur toutes les colonnes actives ;
- tri sur une colonne, `ASC` ou `DESC` ;
- bouton **Ajouter une ligne** (toujours visible dans la barre d’outils Données, gated par `can_write`) ;
- boutons **Précédent** et **Suivant** ;
- bouton **Actualiser** ;
- compteur « N ligne(s) » dans la barre d’outils.

### 11.2 Scénario positif

1. Ajouter au moins 26 rows pour activer réellement la seconde page.
2. Rechercher une sous-chaîne présente dans `nom` ou `email`.
3. Trier par `id`, puis basculer `ASC`/`DESC`.
4. Passer à la page 2.
5. Vérifier `Page 2 · 26 ligne(s)` et au moins une ligne.

Le backend borne `limit` entre 1 et 500 et `offset` à 0 minimum.

### 11.3 Filtres exacts via REST

Les filtres par colonne sont pris en charge par l’API mais n’ont pas de formulaire graphique dédié. Exemple conceptuel :

```text
GET /api/tables/<TABLE_ID>/rows
    ?limit=25
    &offset=0
    &filters={"email":"adresse@exemple"}
    &sort=id
    &order=DESC
```

Encoder le JSON dans l’URL avec le client HTTP utilisé.

### 11.4 Types dans les trois représentations

- dans le XML, les cellules non nulles sont du texte ;
- dans la projection SQLite, les valeurs sont converties selon le type (`INTEGER`, `REAL`, `NUMERIC`, `TEXT`, `BLOB`) ;
- dans la réponse REST, SQLite renvoie les types natifs disponibles ;
- une valeur `NULL` explicite devient `<cell column="..." null="true"/>` ;
- un champ omis pour laisser agir un `DEFAULT` peut rester absent de la row XML et être matérialisé par SQLite lors de chaque reconstruction.

---

# Partie IV — XML, SQLite et synchronisation

## 12. Le XML comme source de vérité

### 12.1 Emplacement

Par défaut, pour une base d’ID `<DB_ID>` :

```text
backend/data/xml/<DB_ID>_<slug-du-nom>.xml
backend/data/projections/<DB_ID>_<slug-du-nom>.sqlite
```

Le séparateur du stem est `_`, puis le slug utilise des tirets. Après renommage, les chemins déjà enregistrés restent ceux créés initialement.

Pour localiser les artefacts :

```bash
find backend/data/xml -type f
find backend/data/projections -type f
```

Sous PowerShell :

```powershell
Get-ChildItem backend/data/xml
Get-ChildItem backend/data/projections
```

### 12.2 Vérification avant/après

Après création d’une table sans rows, le sérialiseur produit cette structure ; UUID et IDs sont générés, donc volontairement abrégés :

```xml
<?xml version='1.0' encoding='UTF-8'?>
<database name="validation_personal" uuid="..." status="ACTIVE"
          scope="PERSONAL" version="V" owner_id="..." ...>
  <table name="contacts" uuid="..." protected="false"
         archived="false" status="ACTIVE" ...>
    <columns>
      <column name="id" type="INT" nullable="false"
              primary_key="true" auto_increment="true" .../>
      <column name="nom" type="VARCHAR" nullable="false" .../>
      <column name="email" type="VARCHAR" nullable="false"
              unique="true" .../>
    </columns>
    <rows/>
  </table>
</database>
```

Après ajout d’une ligne :

```xml
<rows>
  <row uuid="..." internal_id="...">
    <cell column="nom">Alice</cell>
    <cell column="email">alice@exemple.invalid</cell>
    <cell column="id">1</cell>
  </row>
</rows>
```

L’ordre des cellules suit l’ordre des données du dictionnaire de la mutation et ne doit pas être utilisé comme invariant métier.

Procédure :

1. relever `version="V"` dans le fichier ;
2. ajouter une row dans le frontend ;
3. rouvrir le fichier ;
4. vérifier le nouveau `<row>` et `version="V+1"` ;
5. modifier la row ; vérifier le texte de la cellule et une nouvelle incrémentation ;
6. supprimer la row ; vérifier la disparition du `<row>` et une nouvelle incrémentation.

### 12.3 `document_version` et `expected_version`

- la racine XML porte `version` ;
- le control plane conserve la même valeur dans `databases.document_version` ;
- la réponse API expose `document_version` ;
- les mutations frontend structure/rows/sync envoient `expected_version` dans le JSON ou `If-Match` pour les `DELETE` ;
- sous le verrou de base, `XmlEngineService.mutate` compare la version attendue à la version réellement lue dans le XML ;
- en cas d’écart : HTTP `409`, code `SYNC_CONFLICT`, aucune promotion d’artefact.

### 12.4 Hash XML

Le backend calcule un SHA-256 du XML sérialisé et le stocke dans `databases.xml_checksum`. Ce hash :

- n’est pas inclus dans `Database.to_dict()` ;
- n’est donc pas exposé par les écrans actuels ;
- n’est pas le verrou optimiste principal ; la version l’est ;
- est recalculé après chaque commit réussi.

Contrôle direct du control plane par défaut :

```bash
cd backend
python - <<'PY'
import sqlite3
c = sqlite3.connect('xmlforge.db')
for row in c.execute('SELECT id, name, document_version, xml_checksum, xml_file_path, projection_path, sync_status FROM databases'):
    print(row)
c.close()
PY
```

Si `DATABASE_URL` pointe ailleurs, adapter cette vérification.

### 12.5 Persistance atomique

Le code actuel :

1. prend un verrou par base (`.lock`) ;
2. écrit dans un fichier temporaire ;
3. `flush` + `fsync` ;
4. ferme les connexions SQLite suivies ;
5. consolide le WAL ;
6. promeut avec `os.replace` ;
7. sous Windows, reprend jusqu’à 5 fois les `PermissionError`/`WinError 5` avec délai ;
8. utilise un fallback copie + fsync + suppression + promotion ;
9. restaure le snapshot XML/SQLite en cas d’exception gérée.

Le XML est promu avant SQLite. En cas de crash brutal entre les deux, le démarrage suivant reconstruit SQLite depuis XML.

### 12.6 Vérification de la projection

```bash
python - <<'PY'
import sqlite3
path = r'backend/data/projections/<REMPLACER_PAR_LE_FICHIER>.sqlite'
c = sqlite3.connect(path)
print(c.execute('SELECT id, nom, email FROM contacts ORDER BY id').fetchall())
print(c.execute('PRAGMA table_info("contacts")').fetchall())
print(c.execute('PRAGMA index_list("contacts")').fetchall())
print(c.execute('PRAGMA foreign_key_list("contacts")').fetchall())
c.close()
PY
```

La projection contient aussi une colonne technique `_xmlforge_row_uuid`, masquée par l’API publique.

### 12.7 Reconstruction volontaire

Endpoint réel :

```text
POST /api/databases/<database_id>/rebuild-projection
```

Droit requis : `can_ddl`. Il relit le XML, reconstruit SQLite et synchronise le catalogue. Le bouton est désormais accessible dans le Workspace, onglet **Avancé** → **Projection SQLite** → **Reconstruire la projection** (avec indicateur de progression).

---

## 13. Test de conflit optimiste

### 13.1 Deux navigateurs

1. Ouvrir la même base avec A dans deux fenêtres/profils.
2. Dans la fenêtre 1, ouvrir une row en édition sans enregistrer.
3. Dans la fenêtre 2, modifier une row et enregistrer.
4. Revenir dans la fenêtre 1 et enregistrer la version obsolète.
5. Attendu : modale **Conflit de version**.
6. Vérifier le texte : les changements locaux n’ont pas écrasé la version récente.
7. Cliquer **Recharger la version récente**.
8. Vérifier la donnée de la fenêtre 2.

### 13.2 Réponses réellement observables selon la façade

La route SQL commune `/api/databases/<id>/query` conserve le code textuel :

```json
{
  "success": false,
  "message": "Conflit de version: attendu <ancienne>, version courante <nouvelle>",
  "errors": {"code": "SYNC_CONFLICT"}
}
```

Plusieurs routes de service (`rows`, `tables`, `columns` ou `sync`) attrapent actuellement l’exception puis ne conservent que son message ; leur champ `errors` peut donc être `null` malgré le statut `409`. Le client frontend détecte d’abord le statut HTTP (`isConflict=true`) et affiche la même modale. La version courante reste lisible dans le message, mais n’est pas garantie sous forme d’un champ `details.current_version` sur toutes les façades.

---

# Partie V — Conversion et import/export

## 14. Test XML → SQL

### 14.1 Par le frontend

1. Ouvrir une table contenant des rows.
2. Vérifier le panneau **XML Source**.
3. Cliquer **Convertir XML → SQL**.
4. Vérifier le panneau **SQL généré**.
5. Rechercher :
   - `CREATE DATABASE IF NOT EXISTS` ;
   - `USE` ;
   - `CREATE TABLE` ;
   - les colonnes PK/FK/UNIQUE/NOT NULL/DEFAULT/AUTO_INCREMENT ;
   - `CREATE INDEX` si un index existe ;
   - un `INSERT INTO` par row présente dans `<rows>`.

Route :

```text
POST /api/convert/xml-to-sql
JSON: {"xml":"...", "database_name":"..."}
```

### 14.2 Vérification des rows

Pour chaque :

```xml
<row>
  <cell column="id">1</cell>
  <cell column="nom">Alice</cell>
</row>
```

attendre une instruction de la forme :

```sql
INSERT INTO `contacts` (`id`, `nom`) VALUES ('1', 'Alice');
```

Les cellules XML sont des chaînes ; le convertisseur peut donc les citer même pour une colonne numérique. MySQL/SQLite peut ensuite les convertir selon l’affinité de la colonne.

### 14.3 Limites XML → SQL

- sortie orientée MySQL : backticks, `ENGINE=InnoDB`, `DEFAULT CHARSET=utf8mb4` ;
- aucune exécution n’a lieu lors de la conversion ;
- une table sans colonne est ignorée ;
- le convertisseur lit les tables archivées au lieu de les filtrer explicitement ;
- les actions FK de contraintes canoniques composites sont exportées ; les FK définies uniquement au niveau colonne n’exportent pas forcément toutes les actions référentielles ;
- les identifiants SQL ne sont pas re-quotés contre tous les cas exotiques ; utiliser les identifiants XMLForge valides ;
- pas de vue, trigger, procédure, transaction ou DDL avancé.

---

## 15. Test SQL → XML

### 15.1 SQL de validation

Créer un fichier `validation_import.sql` :

```sql
CREATE TABLE contacts_import (
  id INT NOT NULL AUTO_INCREMENT,
  nom VARCHAR(100) NOT NULL,
  email VARCHAR(255) NOT NULL UNIQUE,
  PRIMARY KEY (id),
  INDEX idx_contacts_import_nom (nom)
);
INSERT INTO contacts_import (id, nom, email)
VALUES (1, 'Alice', 'alice@exemple.invalid'),
       (2, 'Bob', 'bob@exemple.invalid');
```

### 15.2 Conversion seule

Route :

```text
POST /api/convert/sql-to-xml
JSON: {"sql":"...", "database_name":"validation_sql"}
```

Attendu :

```text
SQL
 -> suppression des commentaires simples
 -> découpage en instructions
 -> parsing CREATE TABLE
 -> parsing INSERT INTO
 -> structure Python tables/columns/rows
 -> XML <database><table><columns>...<rows>...
```

Le XML de réponse n’est pas persisté tant qu’il n’est pas importé ou appliqué. Pour le SQL ci-dessus, vérifier au minimum une structure de ce type (les attributs de date varient) :

```xml
<database name="validation_sql" version="1" generator="XMLForge" ...>
  <table name="contacts_import" protected="false" archived="false" ...>
    <columns>
      <column name="id" type="INT" nullable="false"
              primaryKey="true" autoIncrement="true" .../>
      <column name="nom" type="VARCHAR" length="100" nullable="false" .../>
      <column name="email" type="VARCHAR" length="255"
              nullable="false" unique="true" .../>
    </columns>
    <rows>
      <row>
        <cell column="id">1</cell>
        <cell column="nom">Alice</cell>
        <cell column="email">alice@exemple.invalid</cell>
      </row>
    </rows>
  </table>
</database>
```

Dans le workspace, l’icône **SQL → XML** convertit le contenu du panneau SQL vers le panneau XML. **Appliquer les modifications** utilise ensuite le endpoint de synchronisation de la table courante et prend la première table du document converti. Pour un SQL multi-table, utiliser plutôt `POST /api/import/sql`.

### 15.3 Ce qui est récupéré

- `CREATE TABLE` ;
- colonnes avec type alphabétique et longueur simple ;
- `NULL`/`NOT NULL` ;
- PK inline ou table ;
- FK simple colonne ;
- `UNIQUE` dans plusieurs formes simples ;
- `AUTO_INCREMENT` ;
- `DEFAULT` simple ;
- `INDEX`/`KEY` simple ;
- `INSERT INTO`, y compris plusieurs tuples `VALUES`.

### 15.4 Limites SQL → XML

Le parseur est fondé sur des expressions régulières, pas sur un parseur SQL complet :

- découpage naïf par `;` ; un point-virgule dans une chaîne n’est pas sûr ;
- noms qualifiés, schémas, guillemets complexes et types contenant autre chose que des lettres/longueur simple : support limité ;
- `ALTER TABLE`, vues, triggers, procédures, transactions : ignorés/non supportés ;
- FK composite : non récupérée fidèlement ;
- actions `ON DELETE`/`ON UPDATE` : non reconstruites par ce convertisseur ;
- contrainte UNIQUE composite ou UNIQUE nommée : récupération partielle selon la forme, potentiellement ramenée à des flags par colonne ;
- fonctions SQL dans les valeurs peuvent rester du texte et échouer lors de la projection ;
- un `NULL` importé est représenté par l’absence de cellule plutôt que systématiquement par `null="true"` ;
- une instruction INSERT dont le nombre de valeurs ne correspond pas au nombre de colonnes est ignorée ;
- les instructions concernant une table sans `CREATE TABLE` reconnu sont ignorées.

---

## 16. Import et export

### 16.1 Matrice réelle

| Fonction | Endpoint | Frontend actuel | Droit |
|---|---|---|---|
| importer XML comme nouvelle base | `POST /api/import/xml` | Dashboard **Importer → XML** | authentifié |
| remplacer la base courante par XML | `POST /api/databases/<id>/sync-xml` | Workspace **Importer XML** | DDL + protections déverrouillées |
| importer SQL comme nouvelle base | `POST /api/import/sql` | Dashboard **Importer → SQL** | authentifié |
| exporter base XML | `GET /api/export/xml/<id>` | pas de bouton XML simple ; export complet proche | admin de base |
| exporter base SQL | `GET /api/export/sql/<id>` | oui | lecture |
| exporter table XML | `GET /api/export/table-xml/<id>` | panneau XML/téléchargement local | admin de table |
| exporter table SQL | `GET /api/export/table-sql/<id>` | panneau SQL/téléchargement local | lecture API |
| exporter projet complet | `GET /api/export/project/<id>` | **Export complet** | admin de base |
| importer projet complet | `POST /api/import/project` | Dashboard **Importer → Projet XMLForge** | authentifié |
| export CSV/JSON | absent | absent | non implémenté |
| export global de toutes les bases | absent | absent | non implémenté |

### 16.2 Import XML nouvelle base

1. Dashboard → **Importer**.
2. Laisser le mode **XML (structure)** sélectionné.
3. Choisir `backend/test.xml` ou un export XMLForge réel.
4. Attendre la création de la carte.
5. Ouvrir la base et vérifier tables/rows.

Le backend :

- valide avec `backend/app/static/xmlforge.xsd` ;
- génère de nouveaux UUID pour la base, les tables, colonnes et rows ;
- crée une nouvelle base `PERSONAL`, même si le document source portait `COMMON` ;
- reconstruit XML et SQLite ;
- supprime la base incomplète si le remplacement échoue.

### 16.3 Import SQL

Deux chemins équivalents :

1. **Frontend** : Dashboard → **Importer** → mode **SQL (script)** → choisir un fichier `.sql`. Le backend convertit le SQL en XML (limites du parseur en §15.4), puis importe le XML.
2. **API** :

```bash
curl -i -X POST http://127.0.0.1:5000/api/import/sql \
  -H "Authorization: Bearer <JWT>" \
  -F "file=@validation_import.sql" \
  -F "database_name=validation_sql"
```

Attendu : HTTP `201`, base personnelle créée. Vérifier les rows importées dans l’onglet Données et dans le XML canonique.

### 16.4 Export avec téléchargement

```bash
curl -L http://127.0.0.1:5000/api/export/xml/<DB_ID>?download=true \
  -H "Authorization: Bearer <JWT_MANAGE>" \
  -o validation.xml

curl -L http://127.0.0.1:5000/api/export/sql/<DB_ID>?download=true \
  -H "Authorization: Bearer <JWT_VIEW_OU_PLUS>" \
  -o validation.sql

curl -L http://127.0.0.1:5000/api/export/table-xml/<TABLE_ID>?download=true \
  -H "Authorization: Bearer <JWT_MANAGE>" \
  -o contacts.xml

curl -L http://127.0.0.1:5000/api/export/table-sql/<TABLE_ID>?download=true \
  -H "Authorization: Bearer <JWT_VIEW_OU_PLUS>" \
  -o contacts.sql
```

Vérifier que les exports SQL et XML de table contiennent les rows.

### 16.5 Export projet

L’export projet est le document XML canonique complet, y compris données et métadonnées de protection. Il porte sur **une base à la fois**. L’action globale du dashboard ouvre donc un sélecteur de base administrable ; elle ne produit pas une archive de toutes les bases.

### 16.6 Comportement du bouton Dupliquer

L’action **Dupliquer** exporte le XML de la base, assainit le nom (caractères autorisés uniquement, préfixe de repli `_` si nécessaire) et importe le résultat sous `<nom>_copie`. Le nom produit respecte donc `^[A-Za-z_][A-Za-z0-9_]*$` et l’import ne doit plus échouer pour cause d’identifiant invalide. Si une copie existe déjà côté API, l’échec éventuel reste celui du backend (nom déjà utilisé), à confirmer en test réel.

---

# Partie VI — Protection des tables

## 17. Test complet d’une table protégée

### 17.1 Création

1. Workspace → **Nouvelle table**.
2. Cocher **Table protégée**.
3. Saisir explicitement une clé de test ; le backend n’en génère pas automatiquement pour la table.
4. Garder la clé primaire automatique si souhaité.
5. Créer.

Le frontend crée la table, appelle `/unlock-table`, puis ajoute `id` avec la nouvelle version.

### 17.2 Protection d’une table existante

1. Sélectionner une table non protégée.
2. Cliquer **Protéger** (barre d’actions ou onglet **Avancé** → **Protection de la table**).
3. Saisir un `file_identifier`.
4. Enregistrer.

Pour retirer la protection, deux boutons graphiques existent désormais :

- **Ôter la protection** (barre d’actions), visible lorsque la table protégée est déverrouillée pour la session ;
- **Retirer la protection définitivement** (onglet **Avancé** → carte de protection).

Les deux envoient `PUT /api/tables/<id>` avec `is_protected:false` et `file_identifier:null`, après déverrouillage/autorisation.

### 17.3 Refus et déverrouillage

1. Se déconnecter puis se reconnecter.
2. Tenter d’ajouter une row : la modale de déverrouillage doit s’ouvrir.
3. Saisir une mauvaise clé : HTTP `403`, `Clé invalide`.
4. Saisir la clé correcte : succès.
5. Ajouter/modifier/supprimer une row : succès.
6. Se déconnecter.
7. Se reconnecter.
8. Tenter une nouvelle mutation : la clé doit être demandée à nouveau.

Clés acceptées :

- `table.file_identifier` ;
- ou la clé interne `database.key_identifier`.

La clé de base est retournée à la création/aux administrateurs via API, mais le frontend actuel ne la présente pas clairement. Utiliser le `file_identifier` choisi lors du test.

### 17.4 Sémantique exacte des unlocks

Le modèle persiste un déverrouillage par couple `(user_id, table_id)` avec expiration de 24 heures. Il est :

- personnel à l’utilisateur, pas global à la table ;
- réutilisable par les requêtes REST/TCP du même utilisateur tant qu’il existe ;
- supprimé à la connexion web, à la déconnexion web et à l’authentification TCP ;
- supprimé lors d’un reset de mot de passe ;
- filtré/supprimé après expiration.

Il n’est pas lié à un identifiant unique de fenêtre ou de socket. Deux sessions parallèles du même utilisateur peuvent donc partager l’état backend. Une nouvelle authentification TCP efface aussi les unlocks web de ce même utilisateur.

---

# Partie VII — TCP/IP et application externe

## 18. Configuration TCP réelle

### 18.1 Obtenir les credentials

1. Se connecter dans le frontend.
2. Ouvrir **API & TCP/IP**.
3. Au premier accès, `GET /api/tcp/credentials` crée automatiquement un username et un mot de passe TCP.
4. Copier immédiatement le mot de passe affiché une seule fois.
5. Si le secret n’est plus visible :
   - saisir le mot de passe XMLForge dans **Générer un mot de passe affichable** ; cette action **régénère** le secret au lieu de relire l’ancien ; ou
   - cliquer **Régénérer sans confirmation**, endpoint JWT existant.

Les mots de passe TCP sont hashés avec bcrypt. Les credentials TCP sont distincts des credentials web/JWT.

Routes :

```text
GET    /api/tcp/credentials
POST   /api/tcp/credentials
PUT    /api/tcp/credentials
DELETE /api/tcp/credentials
POST   /api/tcp/credentials/regenerate
POST   /api/tcp/credentials/show-password
GET    /api/tcp/sessions
GET    /api/tcp/status              # sans JWT
```

Si `TCP_PORT` est changé dans le `.env`, le statut serveur donne le port réel. Les credentials auto-créés utilisent encore les valeurs par défaut `127.0.0.1:3307` sauf mise à jour explicite ; corriger au besoin avec `PUT /api/tcp/credentials`.

La chaîne `xmlforge://...` affichée est informative. Aucun driver URI générique n’est enregistré ; le client Python fourni reçoit host, port, username, password et database séparément.

### 18.2 Protocole

Transport en clair, sans TLS :

```text
[type: 1 octet non signé]
[length: uint32 big-endian, longueur du JSON]
[payload: JSON UTF-8]
```

Limite de buffer par connexion : 8 MiB.

| Type | Code | Usage |
|---|---:|---|
| `MSG_AUTH` | 1 | auth TCP, base optionnelle |
| `MSG_QUERY` | 2 | requête SQL, version/clé optionnelles |
| `MSG_RESPONSE` | 3 | succès |
| `MSG_ERROR` | 4 | erreur structurée |
| `MSG_PING` | 5 | ping |
| `MSG_PONG` | 6 | pong |
| `MSG_SELECT_DATABASE` | 7 | choisir une base |
| `MSG_UNLOCK_TABLE` | 8 | déverrouiller une table |
| `MSG_CLOSE` | 9 | fermer la session |

Codes :

```text
AUTH_SUCCESS=0
AUTH_FAILED=1
QUERY_SUCCESS=2
QUERY_ERROR=3
SESSION_EXPIRED=4
INVALID_REQUEST=5
```

Session inactive : expiration après `TCP_SESSION_TIMEOUT_MINUTES`, 30 minutes par défaut.

### 18.3 Authentification et sélection de base

Payload AUTH :

```json
{
  "username": "<TCP_USERNAME>",
  "password": "<TCP_PASSWORD>",
  "database": "<DATABASE_ID_OU_NOM>"
}
```

Le serveur :

1. vérifie le credential TCP actif et son utilisateur actif ;
2. efface les anciens unlocks de cet utilisateur ;
3. sélectionne uniquement une base lisible par ACL ;
4. renvoie un `session_token` UUID ;
5. refuse un nom ambigu. Utiliser l’ID est recommandé, car plusieurs propriétaires peuvent avoir le même nom.

### 18.4 SQL supporté

#### `SELECT`

```sql
SELECT * FROM contacts;
SELECT id, nom, email FROM contacts WHERE id >= 1 ORDER BY id DESC LIMIT 25 OFFSET 0;
SELECT * FROM contacts WHERE (nom LIKE 'A%' OR nom LIKE 'B%') AND email IS NOT NULL;
SELECT * FROM contacts WHERE id IN (1, 2, 3);
```

Opérateurs :

```text
=  !=  <>  <  <=  >  >=  LIKE  IN  IS NULL  IS NOT NULL
AND  OR  parenthèses
ORDER BY ASC|DESC
LIMIT  OFFSET
```

#### `INSERT`

```sql
INSERT INTO contacts (nom, email) VALUES ('Application externe', 'externe@exemple.invalid');
```

Une seule row par requête, liste de colonnes explicite.

#### `UPDATE`

```sql
UPDATE contacts SET nom='Nom modifié' WHERE id=1;
```

`WHERE` est obligatoire.

#### `DELETE`

```sql
DELETE FROM contacts WHERE id=1;
```

`WHERE` est obligatoire.

### 18.5 SQL non supporté par `QueryService`

- `CREATE`, `ALTER`, `DROP` ;
- `JOIN` ;
- `GROUP BY`, `HAVING` ;
- agrégats comme `COUNT`, `SUM`, `AVG` ;
- sous-requêtes ;
- alias de table/colonne ;
- `DISTINCT` ;
- transactions explicites ;
- requêtes multiples ;
- `UPDATE`/`DELETE` sans `WHERE` ;
- INSERT multi-row.

Ces constructions doivent produire une erreur, pas un succès simulé.

### 18.6 Format des réponses

Succès SELECT :

```json
{
  "status": 2,
  "result": {
    "rows": [{"id": 1, "nom": "...", "email": "..."}],
    "total": 1,
    "limit": 100,
    "offset": 0,
    "table": {}
  }
}
```

Succès INSERT/UPDATE/DELETE :

```json
{"status":2,"result":{"inserted":1,"row":{}}}
{"status":2,"result":{"updated":1}}
{"status":2,"result":{"deleted":1}}
```

Erreur :

```json
{"code":3,"message":"..."}
```

Les erreurs métier détaillées deviennent généralement `QUERY_ERROR=3` sur le transport TCP. Les codes textuels REST comme `SYNC_CONFLICT` ne sont pas transportés tels quels par le protocole TCP actuel.

---

## 19. Scénario TCP complet

Précondition : la base et la table `contacts(id, nom, email)` existent, et le compte TCP possède au moins `EDIT` pour les écritures.

Depuis la racine du dépôt, créer `backend/validation_tcp_client.py` hors production ou exécuter ce script interactif en remplaçant les placeholders :

```python
from app.tcp import XMLForgeClient

HOST = "127.0.0.1"
PORT = 3307
TCP_USERNAME = "<COPIER_DEPUIS_API_TCP_IP>"
TCP_PASSWORD = "<COPIER_LE_SECRET_AFFICHÉ>"
DATABASE_ID = "<ID_VISIBLE_DANS_URL_DATABASE>"

client = XMLForgeClient(HOST, PORT, timeout=30)
try:
    client.connect(TCP_USERNAME, TCP_PASSWORD, DATABASE_ID)

    print("PING:", client.ping())
    print("AVANT:", client.execute(
        "SELECT id, nom, email FROM contacts ORDER BY id ASC LIMIT 100"
    ))

    print("INSERT:", client.insert("contacts", {
        "nom": "Application externe",
        "email": "externe@exemple.invalid",
    }))

    print("APRÈS INSERT:", client.select(
        "contacts", where="email='externe@exemple.invalid'"
    ))

    print("UPDATE:", client.update(
        "contacts",
        {"nom": "Application externe modifiée"},
        "email='externe@exemple.invalid'",
    ))

    print("APRÈS UPDATE:", client.select(
        "contacts", where="email='externe@exemple.invalid'"
    ))

    print("DELETE:", client.delete(
        "contacts", "email='externe@exemple.invalid'"
    ))

    print("APRÈS DELETE:", client.select(
        "contacts", where="email='externe@exemple.invalid'"
    ))
finally:
    client.disconnect()
```

Exécution :

```bash
cd backend
python validation_tcp_client.py
```

À chaque étape :

1. revenir dans le workspace XMLForge ;
2. onglet **Données** ;
3. cliquer **Actualiser** ;
4. vérifier l’apparition, la modification puis la disparition de la row ;
5. ouvrir le XML canonique et vérifier la même évolution ;
6. vérifier le fichier SQLite de projection.

Pour une table protégée :

```python
client.unlock_table("contacts", "<FILE_IDENTIFIER>")
```

ou passer `table_key` à `client.execute(...)` pour une requête individuelle.

### 19.1 Test des ACL TCP

1. Partager la base à B en `VIEW`.
2. Créer/obtenir les credentials TCP de B.
3. B se connecte et exécute `SELECT` : succès.
4. B exécute `INSERT` : `RuntimeError`, message contenant `Permission write refusée`.
5. A passe B à `EDIT`.
6. Sans recréer la session, B réessaie : succès, car l’ACL est relue à chaque requête.
7. A retire B.
8. Le SELECT suivant de B échoue.

### 19.2 Sécurité TCP

Le protocole n’utilise pas TLS. Pour un réseau non local :

- utiliser un VPN ou tunnel SSH ;
- filtrer le port par pare-feu ;
- ne pas exposer directement 3307 sur Internet ;
- faire tourner le client avec une adresse réseau réelle du serveur ;
- ne pas versionner les secrets.

Le dépôt contient un `tcp-tester` Express qui implémente le framing brut et expose une petite façade HTTP locale. Il s’agit d’un outil séparé avec interpolation SQL simple, pas d’un SDK Node publié ni du chemin de validation principal. Le client Python `app.tcp.XMLForgeClient` est la référence testée par la suite backend.

---

# Partie VIII — REST, audit et administration

## 20. Endpoints REST réellement enregistrés

Sauf indication contraire, chaque route ci-dessous existe en version canonique `/api/...` et en alias historique sans `/api`. Les routes TCP de gestion n’existent que sous `/api/tcp`. Les routes protégées attendent :

```http
Authorization: Bearer <JWT>
```

### 20.1 Authentification

| Méthode | Route | Auth |
|---|---|---|
| POST | `/api/register` | non |
| POST | `/api/login` | non |
| GET | `/api/me` | JWT |
| POST | `/api/logout` | JWT, révoque le JTI et efface les unlocks |

### 20.2 Bases

| Méthode | Route |
|---|---|
| GET, POST | `/api/databases` |
| GET, PUT, DELETE | `/api/databases/<db_id>` |
| GET, PUT | `/api/databases/<db_id>/comment` |
| POST | `/api/databases/<db_id>/archive` |
| POST | `/api/databases/<db_id>/restore` |
| POST | `/api/databases/<db_id>/sync-xml` |
| POST | `/api/databases/<db_id>/sync` — alias |
| POST | `/api/databases/<db_id>/rebuild-projection` |
| POST | `/api/databases/<db_id>/query` |

### 20.3 Tables, colonnes et rows

| Méthode | Route |
|---|---|
| GET | `/api/tables/<database_id>` |
| POST | `/api/tables` |
| GET | `/api/tables/<table_id>/detail` |
| PUT, DELETE | `/api/tables/<table_id>` |
| GET, PUT | `/api/tables/<table_id>/comment` |
| POST | `/api/tables/<table_id>/archive` |
| POST | `/api/tables/<table_id>/restore` |
| POST | `/api/tables/<table_id>/sync-xml` |
| POST | `/api/tables/<table_id>/sync` — alias |
| GET | `/api/columns/<table_id>` |
| POST | `/api/columns` |
| GET | `/api/columns/<column_id>/detail` |
| PUT, DELETE | `/api/columns/<column_id>` |
| GET, PUT | `/api/columns/<column_id>/comment` |
| POST | `/api/columns/<column_id>/archive` |
| POST | `/api/columns/<column_id>/restore` |
| GET, POST | `/api/tables/<table_id>/rows` |
| PUT, DELETE | `/api/tables/<table_id>/rows/<row_id>` |

### 20.4 Permissions et unlocks

| Méthode | Route |
|---|---|
| GET, POST | `/api/databases/<database_id>/permissions` |
| DELETE | `/api/databases/<database_id>/permissions/<user_id>` |
| GET, POST | `/api/tables/<table_id>/permissions` |
| DELETE | `/api/tables/<table_id>/permissions/<user_id>` |
| POST | `/api/unlock-table` |
| GET, DELETE | `/api/unlocks` |

### 20.5 Import, export, conversion

| Méthode | Route |
|---|---|
| POST | `/api/import/xml` |
| POST | `/api/import/sql` |
| GET | `/api/export/xml/<database_id>` |
| GET | `/api/export/sql/<database_id>` |
| GET | `/api/export/table-xml/<table_id>` |
| GET | `/api/export/table-sql/<table_id>` |
| GET | `/api/export/xml/table/<table_id>` — alias |
| GET | `/api/export/sql/table/<table_id>` — alias |
| POST | `/api/convert/xml-to-sql` |
| POST | `/api/convert/sql-to-xml` |
| GET | `/api/export/project/<database_id>` |
| POST | `/api/import/project` |

### 20.6 Administration

| Méthode | Route | Rôle |
|---|---|---|
| GET, POST | `/api/users` | admin |
| GET, PUT, DELETE | `/api/users/<user_id>` | admin |
| POST | `/api/users/<user_id>/reset-password` | admin |
| POST | `/api/users/<user_id>/toggle-active` | admin |
| GET | `/api/history` | admin |
| GET | `/api/audit-logs` | admin |
| GET | `/api/audit` — alias | admin |

### 20.7 TCP et MySQL optionnel

| Méthode | Route | Remarque |
|---|---|---|
| GET, POST, PUT, DELETE | `/api/tcp/credentials` | JWT |
| POST | `/api/tcp/credentials/regenerate` | JWT |
| POST | `/api/tcp/credentials/show-password` | JWT + mot de passe web actuel |
| GET | `/api/tcp/sessions` | JWT |
| GET | `/api/tcp/status` | public |
| POST | `/api/database/create` | crée une base MySQL physique, droit admin de base, pas de bouton frontend |

`POST /api/database/create` utilise `MYSQL_*`, exporte le SQL, crée la base MySQL et exécute les instructions séparées par `;`. Si MySQL n’est pas configuré : test **À renseigner / non déterminé dans le code actuel** et non requis pour valider le cœur XML/SQLite.

### 20.8 Enveloppes JSON

Succès :

```json
{"success":true,"message":"...","data":{}}
```

Erreur :

```json
{"success":false,"message":"...","errors":{}}
```

Statuts à tester :

- `400` validation/entrée ;
- `401` JWT absent, expiré, révoqué ou compte inactif ;
- `403` ACL/rôle/protection ;
- `404` ressource ;
- `409` conflit de version ou contrainte via le moteur query ;
- `500` stockage/projection/erreur serveur ;
- `503` serveur TCP absent sur la route sessions.

---

## 21. Audit et historique

### 21.1 Historique

`History` conserve notamment :

- utilisateur ;
- action métier ;
- type/nom d’élément ;
- base/table ;
- IP ;
- données `before`/`after` sérialisées ;
- timestamp et UUID.

L’écran Historique demande 200 entrées, les regroupe par date et filtre côté frontend. Le backend borne `limit` à 500 et accepte `database_id`.

### 21.2 Audit

`AuditLog` est distinct de l’historique et trace notamment :

- inscription/connexion/déconnexion/erreurs ;
- création/suppression/import/export/conversion ;
- partage ;
- protection/unlock ;
- gestion utilisateurs ;
- requêtes TCP réussies.

L’audit TCP stocke l’opération principale, pas le SQL complet. Les écritures faites directement via `POST /api/databases/<id>/query` ne passent pas par `RowService` et n’ont pas exactement les mêmes traces History/Audit que les routes rows. Ne pas exiger une symétrie totale des journaux entre toutes les façades.

### 21.3 Scénario

1. Avec A : connexion, création base/table/row, export SQL, déconnexion.
2. Avec B : tentative de login erronée et tentative d’accès interdit.
3. Avec admin : ouvrir **Audit**, vérifier les événements présents.
4. Ouvrir **Historique**, vérifier les actions métier prises en charge.
5. Utiliser les filtres et **Actualiser**.
6. Vérifier qu’un utilisateur normal reçoit `403` sur les endpoints.

---

# Partie IX — Tests automatisés et recette

## 22. Tests backend

Depuis la racine, environnement Python installé :

```bash
PYTHONPATH=backend python -m pytest -q backend/tests
```

Sous PowerShell :

```powershell
$env:PYTHONPATH="backend"
python -m pytest -q backend/tests
```

La suite contient actuellement 14 tests couvrant :

- auth, compte inactif, révocation JWT et rôles ;
- `PERSONAL`/`COMMON` et ACL ;
- tables, rows, filtres, tri, pagination et contraintes ;
- XML source, projection et conflits ;
- TCP CRUD, ACL, protections, timeout ;
- cycle E2E REST → XML → SQLite ;
- cycle E2E TCP ;
- concurrence 5 writers REST + 5 writers TCP ;
- WAL, busy timeout, retries et absence de lost updates ;
- remplacement SQLite sûr sous Windows et fermeture des handles SQLAlchemy.

Dernier résultat connu de l’état analysé : **14 réussis**.

## 23. Tests frontend

Depuis `xmlforge-react` :

```bash
npm run lint
npm run build
npm test
npm audit
```

Couverture actuelle :

- client API centralisé et JWT ;
- erreurs 401/409 ;
- rôle admin fourni par Flask ;
- restauration d’unlock sans stocker la clé ;
- propagation `expected_version`/`If-Match` ;
- dialogue de conflit.

Derniers résultats connus :

- build réussi ;
- lint : 0 erreur, 3 avertissements historiques `react(only-export-components)` ;
- Vitest : 10 tests réussis, 1 test live ignoré par défaut ;
- audit npm : 0 vulnérabilité.

## 24. Test live des services frontend contre Flask

Backend lancé sur 5000 :

```bash
cd xmlforge-react
VITE_API_URL=http://127.0.0.1:5000/api \
XMLFORGE_LIVE_E2E=1 \
npm test -- src/test/liveBackend.test.js
```

PowerShell :

```powershell
$env:VITE_API_URL="http://127.0.0.1:5000/api"
$env:XMLFORGE_LIVE_E2E="1"
npm test -- src/test/liveBackend.test.js
```

Ce test crée des utilisateurs réels dans le control plane courant. Il supprime ses bases, mais pas nécessairement tous les comptes, credentials et journaux générés.

Dernier résultat connu : **1 réussi**.

## 25. Test navigateur Playwright

Préconditions : Flask et Vite déjà lancés.

```bash
cd xmlforge-react
npx playwright install chromium
# Sur Linux si nécessaire :
npx playwright install-deps chromium
npm run test:e2e
```

Le scénario réel couvre :

- inscription/connexion ;
- base `COMMON` ;
- table + PK auto ;
- colonne + row ;
- mutation backend concurrente ;
- conflit 409 visible et rechargement ;
- page API/TCP.

Il supprime la base créée, mais laisse le compte navigateur et les traces associées. Dernier résultat connu : **1 réussi** (revalidé après l’intégration du modèle frontend, en ~20,6 s : registre → login → dashboard → base `COMMON` → table → colonne → ligne → conflit 409 → page API/TCP).

## 26. Critères d’acceptation finale

Cocher uniquement après observation :

### Démarrage

- [ ] `/health` répond 200.
- [ ] `/api/tcp/status` annonce `running=true` si TCP activé.
- [ ] `/login` et `/register` s’affichent.
- [ ] le frontend joint `/api` sans erreur CORS.

### Auth et rôles

- [ ] un inscrit reçoit le rôle `user`.
- [ ] un admin créé par CLI voit Utilisateurs/Historique/Audit.
- [ ] un compte désactivé ne peut plus se connecter.
- [ ] un JWT révoqué au logout n’est plus accepté.

### Bases et ACL

- [ ] A crée `PERSONAL` et `COMMON`.
- [ ] B ne voit pas `COMMON` avant partage.
- [ ] `VIEW` autorise la lecture et refuse l’écriture.
- [ ] `EDIT` autorise rows et DDL.
- [ ] `MANAGE` autorise le partage et l’administration de base.
- [ ] le partage de table (Workspace → **Partage de la table**) accorde/révoque sans retirer de droit de base.
- [ ] un utilisateur `EDIT` renomme la base sans recevoir `403` (le champ `scope` n’est pas envoyé sans `can_admin`).
- [ ] la révocation est effective en REST et TCP.

### XML/SQLite

- [ ] chaque mutation incrémente `version`.
- [ ] chaque row est visible dans `<rows>`.
- [ ] la projection contient les mêmes données.
- [ ] PK/FK/UNIQUE/NOT NULL/DEFAULT/AUTO_INCREMENT/index sont observables.
- [ ] une contrainte échouée ne modifie ni XML ni version.
- [ ] une projection supprimée en environnement de test peut être reconstruite depuis XML (API ou bouton **Reconstruire la projection** de l’onglet Avancé).

### Concurrence et protection

- [ ] une version obsolète reçoit 409 sans écrasement.
- [ ] une table protégée refuse une mutation sans clé/unlock.
- [ ] login/logout oblige à redéverrouiller.

### Conversion/import/export

- [ ] XML → SQL contient CREATE et INSERT.
- [ ] SQL → XML récupère les tables/rows du sous-ensemble supporté.
- [ ] import XML crée une nouvelle base personnelle.
- [ ] import SQL (Dashboard → **Importer → SQL** ou API) crée une base et ses rows.
- [ ] import projet (Dashboard → **Importer → Projet XMLForge**) recrée une base à partir d’un export projet.
- [ ] le modal de colonne déclare une FK via les listes déroulantes et produit `references=table.colonne`.
- [ ] la protection d’une table se retire graphiquement (« Ôter la protection » / « Retirer la protection définitivement »).
- [ ] export SQL et projet téléchargent un fichier non vide.

### TCP

- [ ] credential TCP généré et copié.
- [ ] auth avec ID de base réussie.
- [ ] SELECT/INSERT/UPDATE/DELETE fonctionnent.
- [ ] UPDATE/DELETE sans WHERE sont refusés.
- [ ] un DDL ou JOIN est refusé.
- [ ] les mutations TCP apparaissent dans React après actualisation.

---

# Partie X — Limites connues et dépannage

## 27. Fonctionnalités absentes ou partielles

1. **Clés API :** section visuelle uniquement, bouton désactivé, aucun endpoint.
2. **Socket.IO :** optionnel côté frontend et désactivé par défaut, sans authentification/rooms ACL côté événements. Les émissions sont globales et certaines créations sérialisent la base avec sa clé interne ; ne pas l’activer/exposer en environnement partagé avant cloisonnement. REST suffit au fonctionnement actuel.
3. **SQL query REST/TCP :** pas de JOIN, agrégat, GROUP BY, sous-requête, DDL ou transaction.
4. **Import SQL :** disponible (Dashboard → **Importer → SQL**). Limites du parseur SQL en §15.4 (split naïf, pas d’`ALTER`/vues/triggers/procédures, INSERT malformé ignoré).
5. **Import projet :** disponible (Dashboard → **Importer → Projet XMLForge**). L’export projet se fait **une base à la fois**.
6. **Permissions table :** gérées graphiquement (Workspace → **Partage de la table**). Droits **additifs** seulement : une permission de table ne révoque jamais un droit de base, et un partage de table seul ne rend pas la base sélectionnable dans le Dashboard.
7. **Export global :** une base à la fois.
8. **Formats :** pas de CSV/JSON.
9. **MySQL physique :** endpoint optionnel sans UI, dépend d’une instance externe.
10. **Protection :** retrait graphique disponible (« Ôter la protection » / « Retirer la protection définitivement »). Le déverrouillage reste personnel à l’utilisateur et exige `can_write`.
11. **Éditeur colonne :** couvre les contraintes simples (PK, FK via listes déroulantes, `UNIQUE`, `AUTO_INCREMENT`, index, `DEFAULT`, nullable, `ON DELETE`/`ON UPDATE`). PK composite, FK complexe au niveau table et index composé restent via XML/REST.
12. **VIEW dans le workspace :** structure/rows sont lisibles, mais le chargement initial du panneau XML de table exige `can_admin`; le panneau SQL de droite peut donc aussi rester indisponible dans ce chemin, bien que l’export SQL de base/table soit autorisé par l’API en lecture.
13. **Duplication UI :** le nom généré est assaini (`<nom>_copie`) ; seul un conflit de nom déjà existant côté backend peut encore échouer (voir §16.6).
14. **Scope :** `COMMON` ne partage rien automatiquement ; `PERSONAL` n’interdit pas le partage explicite. Le modal « Nouvelle base » l’indique désormais explicitement.
15. **Référential actions :** DDL SQLite représenté, mais effets de cascade non réécrits automatiquement dans XML.
16. **TCP :** aucun TLS et pas de client officiel Java/Go ; client Python fourni. L’interface fournit statut/host/port/credentials et le client Python, mais n’émule aucune connexion (le navigateur ne parle jamais TCP).
17. **Comptes/bases de démonstration :** aucun état runtime garanti après clone.
18. **Paramètres :** l’item de sidebar **Paramètres** n’exécute aucune navigation ; la page réelle API/TCP est `/settings`.

## 28. Dépannage

### Backend injoignable

- vérifier `python run.py` ;
- tester `/health` ;
- vérifier le port 5000 ;
- vérifier `VITE_API_URL=/api` et le proxy Vite.

### CORS

Ajouter l’origine exacte du frontend dans `CORS_ORIGINS`, séparée par une virgule, puis redémarrer Flask.

### Port TCP occupé

Changer `TCP_PORT`, redémarrer Flask et vérifier `/api/tcp/status`. Mettre également à jour les credentials affichés si nécessaire.

### `WinError 5` ou fichier SQLite verrouillé

Le code libère les connexions connues, checkpoint le WAL, reprend 5 fois et utilise un fallback. Si l’erreur persiste :

- fermer un outil externe qui garde le `.sqlite` ouvert ;
- arrêter les vieux processus Flask/tests ;
- ne pas placer les projections dans un dossier synchronisé/verrouillé sans test ;
- exécuter `backend/tests/test_windows_storage.py`.

### Conflit 409

Ne pas renvoyer immédiatement le même payload. Cliquer **Recharger la version récente**, relire `document_version`, réappliquer manuellement la modification.

### XML rejeté

- vérifier le XSD `backend/app/static/xmlforge.xsd` ;
- vérifier les identifiants ;
- vérifier les types autorisés ;
- vérifier les références FK ;
- vérifier que `AUTO_INCREMENT` porte sur une PK entière ;
- vérifier la version en cas de sync.

### Nettoyage d’une recette locale

Arrêter Flask avant de supprimer les artefacts. Pour repartir totalement de zéro : sauvegarder si nécessaire, puis supprimer le control plane et les dossiers runtime :

```text
backend/xmlforge.db
backend/data/xml/
backend/data/projections/
```

Cette opération supprime comptes, rôles attribués, bases, ACL, historique, audit, credentials TCP et données. Elle ne doit jamais être exécutée sur une installation à conserver.

---

## 29. Fichiers de référence du code

Backend :

- `backend/run.py`
- `backend/app/config.py`
- `backend/app/__init__.py`
- `backend/app/routes/`
- `backend/app/services/permission_service.py`
- `backend/app/query/sql_parser.py`
- `backend/app/query/service.py`
- `backend/app/xml_engine/document.py`
- `backend/app/xml_engine/service.py`
- `backend/app/xml_engine/projection.py`
- `backend/app/xml_engine/storage.py`
- `backend/app/converters/xml_to_sql.py`
- `backend/app/converters/sql_to_xml.py`
- `backend/app/tcp/tcp_protocol.py`
- `backend/app/tcp/tcp_server.py`
- `backend/app/tcp/xmlforge_client.py`
- `backend/app/static/xmlforge.xsd`
- `backend/tests/`

Frontend :

- `xmlforge-react/src/App.jsx`
- `xmlforge-react/src/context/AuthContext.jsx`
- `xmlforge-react/src/context/DatabaseContext.jsx`
- `xmlforge-react/src/pages/Dashboard/Dashboard.jsx`
- `xmlforge-react/src/pages/Workspace/Workspace.jsx`
- `xmlforge-react/src/pages/Users/Users.jsx`
- `xmlforge-react/src/pages/History/History.jsx`
- `xmlforge-react/src/pages/Audit/Audit.jsx`
- `xmlforge-react/src/pages/Settings/Settings.jsx`
- `xmlforge-react/src/components/TCPCredentials/TCPCredentials.jsx`
- `xmlforge-react/src/services/`
- `xmlforge-react/e2e/xmlforge.spec.js`

Documentation croisée :

- `FRONTEND_MODEL_INTEGRATION.md` — intégration du frontend au modèle visuel de référence ;
- `FRONTEND_IMPLEMENTATION.md` — intégration des fonctionnalités backend manquantes dans le frontend ;
- `uploads/xmlforge (7).html` — modèle visuel de référence (fourni par l’utilisateur).

---

**Fin du manuel.**
