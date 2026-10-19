# XMLForge — Analyse technique de l’état actuel du backend

**Date de l’analyse :** 13 août 2026  
**Périmètre :** `backend/` uniquement  
**Dépôt de référence :** `https://github.com/Em-m-anuel/XMLForge.git`  
**Branche distante :** `main`  
**Commit analysé :** `ccfd9c57f0345799bfe95167ac85bda82c7787f5` (`ccfd9c5`)  
**Sujet du commit :** `Mise à jour du projet`  
**Date du commit :** 12 août 2026 à 21:31:59 +01:00

---

## 0. Provenance, méthode et niveau de certitude

Le dépôt a été cloné à nouveau depuis GitHub dans un emplacement temporaire indépendant de tout ancien workspace. Le `HEAD` distant de `main` et le commit local ont été comparés avant et après l’analyse : ils pointaient tous les deux vers `ccfd9c57f0345799bfe95167ac85bda82c7787f5`. Le clone est resté propre (`git status` sans modification) et `git fsck` n’a signalé aucune anomalie.

L’analyse ne repose donc pas sur une ancienne copie locale.

Méthode employée :

1. inventaire complet de `backend/` ;
2. lecture des modèles, routes, services, converters, configuration, TCP et XSD ;
3. suivi des imports et des appels route → service → modèle ;
4. extraction de toutes les routes Flask ;
5. démarrage contrôlé de l’application avec `TestingConfig`, base SQLite en mémoire et démarrage TCP neutralisé, afin de vérifier la vraie table de routage ;
6. smoke tests en mémoire sur l’authentification, l’administration, l’isolation des bases, la protection des tables et plusieurs endpoints cassés ;
7. validation des XML d’exemple contre le XSD ;
8. test du round-trip SQL → XML → SQL sur PK, FK, UNIQUE et INSERT ;
9. comparaison du code avec la documentation du dépôt.

**Limite explicite :** aucun serveur MySQL externe n’était configuré. La route MySQL a donc été analysée intégralement dans le code, mais aucune création réelle sur une instance MySQL n’a été exécutée. Cette limite n’empêche pas de constater l’absence de synchronisation continue XML/MySQL, de mapping persistant ou de transactions atomiques dans le code.

Aucun fichier du projet n’a été modifié. Le présent document est l’unique fichier créé dans le workspace.

---

# 1. Résumé exécutif

## 1.1 Verdict global

Le backend actuel est une API Flask fonctionnelle pour gérer un **catalogue logique** de bases, tables, colonnes et lignes. Cependant, son stockage réel est SQLAlchemy — SQLite par défaut — et non un ensemble de fichiers XML. Les lignes métier sont stockées dans `table_rows.data_json` sous forme de JSON texte. Le XML est aujourd’hui un **format d’import, d’export et d’édition/synchronisation vers ce catalogue SQLAlchemy**, pas la source persistante de vérité.

MySQL intervient seulement de deux façons :

- SQLAlchemy peut utiliser un `DATABASE_URL` MySQL pour stocker les tables internes XMLForge (`users`, `databases`, `tables`, etc.) ;
- `POST /database/create` matérialise ponctuellement une base logique dans un schéma MySQL en exécutant le SQL exporté.

Il n’existe pas de synchronisation bidirectionnelle durable entre un XML canonique et MySQL, pas de mapping entre une base logique et son schéma MySQL, pas d’application automatique des changements CRUD vers MySQL, et pas de reconstruction XML depuis MySQL.

## 1.2 État synthétique des fonctionnalités demandées

| Domaine | État réel | Conclusion |
|---|---|---|
| Authentification Flask | Inscription, login, bcrypt, JWT 24 h, `/me`, logout client-side | Partiel ; sécurité et révocation incomplètes |
| Utilisateurs | CRUD admin, activation, reset password | Présent mais rôle admin codé en dur par email |
| Rôles/permissions | Aucun modèle de rôle ni ACL de base | Absent |
| Bases personnelles | `creator_id` existe, mais l’API ne filtre pas dessus | Non effectif |
| Bases communes | Aucun type de visibilité ni partage | Absent |
| Base XML persistante | Aucun chemin ou repository XML ; aucun fichier écrit par les CRUD | Absent |
| Métadonnées tables/colonnes | CRUD logique SQLAlchemy | Présent, avec endpoints cassés et incohérences |
| Données | CRUD de `TableRow` JSON | Présent mais sans types ni contraintes |
| Relations | Flags PK/FK/UNIQUE ; converter sait générer certaines FK | Partiel ; cible de FK non persistée |
| MySQL | Matérialisation ponctuelle via SQL exporté | Partiel, non synchronisé |
| API Flask | Nombreuses routes, services et enveloppes JSON | Large couverture, aucune isolation par base |
| TCP/IP | Protocole, serveur threadé, client Python, auth et SELECT simple | Prototype ; écritures non implémentées et permissions absentes |
| Import/export | XML, SQL et projet par base | Présent mais pertes de sémantique et pas d’export global XMLForge |
| XSD | Deux copies identiques | Incompatible avec le XML réellement produit |
| Tests automatisés | Aucun vrai test pytest | Absent |

## 1.3 Bloqueurs critiques avant de poursuivre l’architecture cible

1. **Aucune isolation entre utilisateurs.** Tout utilisateur JWT peut lister, lire, renommer, archiver, supprimer, synchroniser ou exporter les bases des autres. Les smoke tests ont confirmé qu’un utilisateur A peut renommer la base créée par l’utilisateur B.
2. **L’administration est revendicable publiquement.** `User.is_admin()` retourne vrai uniquement si l’email est `nyx@xmlforge.io`, mais `/register` est public. Si cette adresse n’existe pas encore, n’importe qui peut l’enregistrer et devenir administrateur.
3. **XML n’est pas la source de vérité.** La vérité actuelle est la base SQLAlchemy ; aucun stockage XML canonique n’existe.
4. **MySQL n’est pas synchronisé.** La route `/database/create` est un déploiement ponctuel et partiel, pas un moteur d’exécution relié au cycle CRUD.
5. **La protection des tables n’est pas une permission.** Le `file_identifier` est renvoyé par `Table.to_dict()` à tout utilisateur authentifié ; la lecture des lignes ignore la protection ; TCP SELECT l’ignore aussi.
6. **Le schéma XML officiel est invalide par rapport aux exports.** Le XSD attend des `<column>` directement sous `<table>`, alors que le backend produit `<columns>` et `<rows>`. Les XML d’exemple versionnés échouent eux-mêmes contre le XSD.
7. **Plusieurs routes documentées appellent des méthodes inexistantes :** commentaire de table, commentaire/archive/restore de colonne et affichage du mot de passe TCP.
8. **TCP n’est pas utilisable comme plateforme CRUD.** Seul SELECT possède une implémentation ; INSERT/UPDATE/DELETE retournent toujours zéro.
9. **Les credentials TCP générés ne sont pas utilisés par le serveur TCP.** Le serveur vérifie le mot de passe principal XMLForge, pas `TcpCredential.tcp_password`.
10. **Les contraintes relationnelles ne sont pas appliquées aux données JSON.** PK, FK, UNIQUE, NOT NULL, types et AUTO_INCREMENT sont essentiellement des métadonnées destinées à l’export SQL.

---

# 2. Architecture réellement implémentée

## 2.1 Flux actuel

```text
Client web / client REST
        |
        v
Routes Flask (app/routes)
        |
        v
Services métier (app/services)
        |
        +--> Modèles SQLAlchemy
        |      users / databases / tables / columns / table_rows(JSON)
        |      history / audit_logs / table_unlocks / tcp_credentials
        |
        +--> Converters XML <-> SQL
        |
        +--> Export XML calculé à la demande
        |
        +--> POST /database/create seulement
                 |
                 v
              MySQL : CREATE DATABASE + exécution de SQL exporté
```

Le TCP suit un chemin séparé :

```text
Client TCP Python
   |
   v
TCPProtocol (1 octet type + 4 octets longueur + JSON UTF-8)
   |
   v
TCPServer en mémoire
   |
   +--> AuthService.verify_credentials (mot de passe principal)
   +--> DatabaseService.get_database_by_name_any_user
   +--> SELECT directement dans TableRow.data_json
   +--> INSERT/UPDATE/DELETE = stubs retournant 0
```

## 2.2 Ce qui fait foi aujourd’hui

| Information | Stockage réel actuel |
|---|---|
| Utilisateurs et mots de passe | SQLAlchemy (`users`) |
| Bases logiques | SQLAlchemy (`databases`) |
| Tables logiques | SQLAlchemy (`tables`) |
| Colonnes et contraintes déclarées | SQLAlchemy (`columns`) |
| Données des tables | JSON texte dans SQLAlchemy (`table_rows.data_json`) |
| Déverrouillages | SQLAlchemy (`table_unlocks`) |
| Audit/historique | SQLAlchemy (`audit_logs`, `history`) |
| XML | Généré à la demande ou reçu en import/sync ; non persisté comme vérité |
| MySQL cible | Créé ponctuellement ; aucun état de synchronisation mémorisé |

Conséquence : changer manuellement un fichier XML versionné dans `backend/` n’a aucun effet automatique sur l’application ou MySQL.

## 2.3 Couches présentes et absentes

- **Routes/controllers :** les fichiers `app/routes/*.py` jouent le rôle de controllers.
- **Services :** présents dans `app/services/`.
- **Modèles :** présents dans `app/models/`.
- **Schemas de validation :** concentrés dans `app/utils/validators.py`, avec trois schemas utilisateur définis directement dans `routes/users.py`.
- **Serializers :** pas de couche dédiée ; chaque modèle expose `to_dict()`.
- **Repositories :** absents ; les services interrogent directement les modèles SQLAlchemy.
- **Migrations :** pas d’Alembic ; seulement `db.create_all()` et des `ALTER TABLE` ad hoc dans `app/__init__.py`.
- **Gestion globale des erreurs :** absente.
- **Tests unitaires/intégration :** absents ; les fichiers `test_tcp_*.py` sont des scripts manuels.

---

# 3. Modèle de données interne actuel

## 3.1 Entités

### `User`

Champs : `id`, `full_name`, `email` unique, `password_hash`, `is_active`, `last_login`, dates. Relations de création vers bases, tables et colonnes.

- Aucun champ `role`.
- Aucun lien vers des permissions.
- `is_admin()` compare l’email en minuscules à `nyx@xmlforge.io`.
- La relation `databases_created` porte `cascade="all, delete-orphan"` : supprimer un propriétaire risque de supprimer ses bases plutôt que de les transférer.

### `Database`

Champs : UUID, nom, description, `creator_id`, commentaire, statut, dernier modificateur, `key_identifier` secret.

- `creator_id` ressemble à une propriété mais n’est pratiquement jamais utilisé pour autoriser l’accès.
- Aucun champ personnel/commun/public.
- Aucun `xml_path`, version XML, checksum, état de sync, nom de schéma MySQL ou connexion cible.
- Aucun nom unique global ou par propriétaire.

### `Table`

Champs : UUID, nom unique par base, `database_id`, créateur, description, commentaire, statut, `is_protected`, `file_identifier`.

- Le `file_identifier` est stocké en clair et sérialisé systématiquement.
- Les colonnes et lignes sont supprimées en cascade via relations SQLAlchemy.

### `Column`

Champs : nom unique par table, type, longueur, nullable, PK, FK, unique, auto-increment, default, statut et métadonnées.

- **Aucun champ `references`.** La cible d’une clé étrangère parsée depuis XML/SQL est donc perdue lors de la persistance.
- Aucun modèle de contrainte composite, index, nom de contrainte, `ON DELETE` ou `ON UPDATE`.

### `TableRow`

Champs : UUID, `table_id`, `data_json`, créateur et dates.

- Une ligne métier complète est un dictionnaire JSON opaque.
- Aucun type SQL, NOT NULL, PK, FK, UNIQUE ou AUTO_INCREMENT n’est vérifié.
- L’ID SQLAlchemy de `TableRow` est un identifiant interne XMLForge, pas forcément la PK métier.

### `TableUnlock`

Association unique utilisateur/table avec expiration à 24 h.

- Le commentaire parle de session, mais aucun `jti` JWT ni identifiant de session n’est stocké.
- Le déverrouillage s’applique à tous les tokens du même utilisateur.

### `TcpCredential`

Un enregistrement par utilisateur : username, hash bcrypt du mot de passe TCP, host, port, activation.

- Ces credentials sont gérés par l’API mais **ignorés par `TCPServer._handle_auth()`**.

### `History` et `AuditLog`

Deux journaux distincts : historique métier avec before/after JSON et audit d’actions sensibles. Leurs services font chacun leur propre `commit()`, ce qui casse l’atomicité avec l’opération métier.

## 3.2 Contraintes réellement appliquées

Les seules contraintes robustement matérialisées dans la base interne sont notamment : email utilisateur unique, clé de base unique, UUID uniques, nom de table unique par base, nom de colonne unique par table et unlock unique par utilisateur/table.

Les contraintes décrites par une `Column` ne s’appliquent pas à `TableRow.data_json`.

---

# 4. Analyse fonctionnelle détaillée

## 4.1 Authentification

### Ce qui existe

- `POST /register` : validation Marshmallow, email normalisé en minuscules, bcrypt, création active.
- `POST /login` : vérification bcrypt, refus des comptes inactifs, mise à jour `last_login`, JWT d’accès.
- JWT : identité = ID utilisateur converti en chaîne ; expiration configurable, 24 h par défaut.
- `GET /me` : résolution de l’utilisateur par ID.
- `POST /logout` : efface les unlocks de l’utilisateur et demande au client de supprimer son token.
- `@jwt_required()` protège la majorité des routes.
- `@admin_required` protège users/history/audit.

### Ce qui manque ou pose problème

- Aucun refresh token.
- Aucun stockage de session JWT, aucune blocklist de `jti`, aucune révocation au logout/reset/désactivation.
- Un token déjà délivré reste techniquement valide après désactivation ; la plupart des routes ne recontrôlent pas `is_active`.
- Logout ne révoque pas le JWT.
- Mots de passe : minimum six caractères seulement ; pas de politique de complexité, mot de passe compromis, historique ou changement autonome.
- Pas de rate limiting, lockout, MFA, vérification d’email ni récupération de compte.
- Secrets de développement faibles par défaut ; `ProductionConfig` ne force rien.
- `run.py` et `app/app.py` activent toujours `debug=True` et `allow_unsafe_werkzeug=True` lorsqu’ils sont lancés directement.
- Les erreurs internes sont souvent renvoyées via `str(e)`.
- Les adresses IP ne sont pas gérées par une politique de proxy de confiance.
- Les erreurs JWT natives ne suivent pas nécessairement l’enveloppe JSON XMLForge.
- CORS SocketIO est `*` ; le CORS REST autorise les credentials.

## 4.2 Utilisateurs, rôles et cas `nyx@xmlforge.io`

### Logique réellement codée

`User.is_admin()` vaut vrai si et seulement si :

```python
self.email.lower() == "nyx@xmlforge.io"
```

Cette condition est utilisée par `admin_required`, donc les routes suivantes sont réservées à cet email :

- CRUD utilisateurs ;
- reset password et toggle active ;
- historique ;
- audit.

`UserService.delete()` interdit de supprimer cet email. `toggle_active()` interdit de le désactiver.

### Failles et limites précises

- L’adresse n’est pas seedée ni réservée. Le premier utilisateur qui l’enregistre via le endpoint public devient admin.
- Il n’existe ni modèle Role, ni permission, ni table de liaison.
- La protection de l’admin est contournable par `PUT /users/<id>` : `UserService.update()` permet de changer l’email et `is_active`, y compris pour l’admin principal. Les interdictions n’existent que dans `delete()` et `toggle_active()`.
- Le privilège se déplace avec l’email : renommer un utilisateur vers cet email lui donne le rôle si l’unicité le permet.
- Le reset de mot de passe ne révoque pas les tokens ni sessions TCP.
- La suppression utilisateur ne traite que les unlocks. Avec des FK strictes MySQL, les history/audit/rows associés peuvent empêcher la suppression ; avec SQLite sans enforcement strict, des orphelins sont possibles. La relation vers les bases peut aussi entraîner leur suppression.
- Aucun endpoint de profil ou changement de mot de passe pour l’utilisateur courant.

## 4.3 Bases de données

### Présent

- Créer, lister, récupérer, modifier, supprimer.
- Commentaire, archivage et restauration.
- UUID, créateur, dernier modificateur, secret de base.
- Import XML/SQL vers une nouvelle base logique.
- Export XML/SQL d’une base.
- Export/import « projet » d’une base, incluant les lignes et certaines clés.
- Matérialisation manuelle sur MySQL.

### Absent ou incomplet

- L’API `get_all()` renvoie toutes les bases à tous les utilisateurs.
- `creator_id` ne crée pas une base personnelle effective.
- Aucun modèle de base commune ou de partage.
- Aucune ACL lecture/écriture/DDL/admin.
- Tous les utilisateurs peuvent modifier/supprimer/archiver/exporter/synchroniser une base tierce.
- L’update retourne la clé de la base à l’appelant, même s’il n’est pas propriétaire.
- L’export projet inclut `key_identifier` et est accessible à tout JWT.
- Pas d’unicité ou de namespace fiable des noms ; TCP choisit la première base active portant un nom.
- `DatabaseUpdateSchema` accepte `status`, mais `DatabaseService.update()` ne l’applique pas.
- Aucun fichier XML persistant.
- Aucun import appliqué à une base MySQL associée.
- Aucun export global de toute la plateforme XMLForge (utilisateurs, rôles, ACL, toutes les bases). « Project export » exporte une seule base logique.
- Les dossiers `uploads/` et `exports/` sont créés mais jamais utilisés par les routes : les contenus restent en mémoire et sont renvoyés dans la réponse.

## 4.4 Tables et colonnes

### Tables

Présent : création, liste par base, modification/renommage, suppression, commentaire annoncé, protection, `file_identifier`, archive/restore et sync XML par table.

Comportement de protection :

1. si non protégée, accès écriture autorisé ;
2. sinon un `TableUnlock` valide autorise l’opération ;
3. sinon le client doit fournir le `file_identifier` de la table ou le `key_identifier` de la base.

Problèmes :

- `GET /tables/<database_id>` ne vérifie ni propriété ni protection et expose `file_identifier` ; le secret nécessaire au déverrouillage est donc divulgué.
- `GET /tables/<id>/rows` ne vérifie pas la protection.
- TCP SELECT ne vérifie pas la protection.
- Les exports ne la vérifient pas.
- `PUT /tables/<id>/comment` appelle `TableService.update_comment`, méthode inexistante : 500 confirmé.
- Le create ignore `status` et `archived` acceptés par le schema.
- Les status en minuscules acceptés par le schema d’update sont ignorés par le service.
- Aucune permission de créer une table dans la base d’un tiers.
- Renommer/supprimer une colonne ne migre pas les clés des JSON de lignes.

### Colonnes

Présent : liste, create, update et delete logiques.

Problèmes :

- `references` est accepté par les schemas mais n’est ni stocké ni appliqué.
- Les alias `primaryKey`, `foreignKey`, `autoIncrement` sont déclarés, mais les services ne les normalisent pas. Avec les valeurs par défaut snake_case, une requête contenant seulement `primaryKey: true` crée une colonne avec `primary_key: false` ; ce comportement a été confirmé par smoke test.
- L’update ignore également les aliases camelCase, `references`, `status` et `archived`.
- L’update d’un nom ne vérifie pas l’unicité avant commit.
- `PUT /columns/<id>/comment`, `POST /columns/<id>/archive` et `/restore` appellent des méthodes absentes de `ColumnService` et renvoient 500.
- Les types et longueurs sont presque arbitraires ; pas d’allowlist dialecte MySQL.
- Pas de modèle de contrainte composite ou d’index.

## 4.5 XML

### Format effectivement produit et consommé

```xml
<database
  name="..."
  uuid="..."
  description="..."
  comment="..."
  status="ACTIVE">
  <table
    name="..."
    uuid="..."
    description="..."
    comment="..."
    protected="false"
    archived="false"
    status="ACTIVE"
    file_identifier="...">
    <columns>
      <column
        name="id"
        type="INT"
        length="11"
        nullable="false"
        primary_key="true"
        foreign_key="false"
        unique="false"
        auto_increment="true"
        default="..."
        uuid="..."
        status="ACTIVE"
        comment="..."/>
    </columns>
    <rows>
      <row uuid="...">
        <cell column="id">1</cell>
      </row>
    </rows>
  </table>
</database>
```

`ProjectService` ajoute `key_identifier` à `<database>`. `sql_to_xml.py` produit plutôt les aliases camelCase `primaryKey`, `foreignKey`, `autoIncrement`, ainsi que `index` et `references`.

### Schéma XSD réel

Les deux fichiers `backend/xmlforge.xsd` et `backend/app/static/xmlforge.xsd` sont identiques. Ils décrivent :

- racines `database`, `table` ou `tables` ;
- `<table>` contenant directement zéro à plusieurs `<column>` ;
- attributs de contraintes de colonne ;
- protection et file identifier de table.

Ils **ne décrivent pas** :

- le wrapper `<columns>` ;
- `<rows>`, `<row>` ou `<cell>` ;
- les attributs générés `version`, `generator`, `author`, `created_at` ;
- `key_identifier` d’un export projet.

Les fichiers `test.xml` et `BaseDonnees_INPTIC.xml` versionnés ont été validés contre ce XSD et ont échoué sur `<columns>`. Aucun code applicatif n’appelle `XMLSchema.validate()` : les imports et syncs ne valident jamais le XSD.

### XML → SQL

`app/converters/xml_to_sql.py` :

- parse base/table/tables ;
- supporte wrapper `<columns>` ou colonnes directes ;
- lit les rows/cells ;
- génère `CREATE DATABASE`, `USE`, `CREATE TABLE`, PK composite simple, FK simples, UNIQUE inline, defaults et INSERT ;
- accepte `references="table(col)"` ou `table.col`.

Limites :

- pas d’ALTER, DROP, index nommé, CHECK, ON DELETE/UPDATE, vues, triggers, procédures ;
- pas de validation XSD ;
- identifiants interpolés dans des backticks sans validation centralisée ;
- cellules XML toujours textuelles, donc les nombres sont souvent exportés comme chaînes SQL ;
- aucune représentation fiable de NULL versus chaîne vide ;
- le SQL de table seule inclut encore CREATE DATABASE/USE, avec un nom dérivé de la racine table ;
- une colonne marquée FK sans `references` ne génère pas de FK.

### SQL → XML

`app/converters/sql_to_xml.py` :

- parse `CREATE TABLE` et `INSERT INTO` ;
- reconnaît PK, FK simple, UNIQUE/KEY/INDEX simples ;
- génère colonnes et rows.

Limites :

- parser regex et split naïf sur `;`, non adapté à du SQL MySQL général ;
- pas d’UPDATE, DELETE, ALTER, DROP, JOIN, vues ou triggers ;
- contraintes composites UNIQUE aplaties en flags par colonne, ce qui change la sémantique ;
- types complexes, quoting, fonctions et échappements incomplets ;
- `ImportService.import_sql()` ignore les `rows` pourtant parsées : les INSERT du SQL importé ne deviennent pas des `TableRow` ;
- FK parsée puis perdue lors de la persistance, faute de champ `Column.references`.

### Synchronisation XML actuelle

`SyncService` compare le XML reçu aux modèles SQLAlchemy :

- crée ou met à jour les tables présentes ;
- crée/met à jour/supprime les colonnes des tables représentées ;
- supprime puis recrée toutes les rows d’une table ;
- retourne un SQL régénéré.

Ce service ne synchronise pas MySQL. Il ne persiste pas le XML. De plus :

- le parseur ajoute toujours une clé `rows`, même si `<rows>` est absent ; une sync de structure peut donc effacer toutes les lignes ;
- une sync de base ne supprime pas les tables absentes du XML ; le XML n’est donc pas pleinement autoritaire ;
- les tables protégées sans bonne clé sont silencieusement ignorées en sync de base, produisant une base partiellement synchronisée ;
- le nom/statut de la base n’est pas synchronisé ;
- les rows sont identifiées par position/remplacement global, pas par PK/UUID ;
- les opérations et journaux utilisent plusieurs commits ; pas d’atomicité globale ;
- aucun diff DDL ou transaction MySQL n’est exécuté.

## 4.6 CRUD des données

### REST actuel

- SELECT logique : `GET /tables/<table_id>/rows?limit=&offset=`.
- INSERT logique : POST avec `{data: {...}}` ou dictionnaire direct.
- UPDATE logique : PUT remplace le dictionnaire complet.
- DELETE logique : suppression par ID interne `TableRow.id`.
- Pagination rudimentaire : `limit`/`offset`, limite haute 500.

### Manques

- Pas de GET d’une ligne unique.
- Pas de filtres, recherche, tri, sélection de colonnes ou curseur stable.
- Pas de JOIN.
- Pas d’évaluation de relations.
- Pas de validation de types.
- Pas d’application de NOT NULL, PK, FK, UNIQUE, default ou AUTO_INCREMENT.
- Pas de détection des colonnes inconnues ou manquantes.
- Pas de transaction multi-lignes ni bulk API publique.
- Pas d’optimistic locking/version.
- La lecture contourne protection et archivage.
- Les données sont lues dans JSON SQLAlchemy, pas dans MySQL.

### TCP actuel

SELECT simple supporte syntaxiquement une liste de colonnes et une égalité WHERE rudimentaire, mais :

- le parser met la requête en majuscules, ce qui altère noms et littéraux ;
- les noms de tables sont forcés en minuscules ;
- ORDER BY, LIMIT et GROUP BY sont seulement reconnus comme bornes de regex, jamais appliqués ;
- pas de JOIN ;
- INSERT/UPDATE/DELETE sont des stubs.

## 4.7 MySQL

### Connexion et création présentes

`POST /database/create` :

1. exporte la base logique vers SQL ;
2. se connecte avec `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD` ;
3. crée un schéma MySQL ;
4. supprime les statements CREATE DATABASE/USE de l’export ;
5. split le SQL sur `;` ;
6. exécute chaque statement, collecte les erreurs et commit.

### Limites critiques

- Aucun lien persistant `database_id` → schéma MySQL cible.
- `MYSQL_DATABASE` est défini mais non utilisé dans ce flux.
- Aucun pool/repository MySQL métier.
- Aucun ALTER/DROP automatique après changement de structure XML.
- Aucun INSERT/UPDATE/DELETE MySQL après CRUD REST.
- Aucun SQL → XML depuis une base MySQL existante.
- Aucun mécanisme de détection de drift.
- Les erreurs statement par statement sont collectées, mais les statements réussis sont quand même commités : résultat partiel possible.
- L’API peut annoncer le succès avec une liste d’erreurs.
- Le compteur `executed_statements` n’est pas un nombre de tables ; il compte aussi les INSERT.
- Pas de rollback global ni de stratégie compensatoire XML/MySQL.
- Split SQL naïf.
- `target_database_name` fourni explicitement n’est pas passé dans le même sanitizer que le nom dérivé.
- N’importe quel utilisateur authentifié peut déclencher la création MySQL d’une base qu’il ne possède pas.

## 4.8 API Flask : cartographie

### Convention de routage réellement vérifiée

Pour tous les blueprints sauf TCP, chaque route existe deux fois :

- sans préfixe, par exemple `/databases` ;
- avec `/api`, par exemple `/api/databases`.

Cette duplication est faite en copiant `Blueprint.deferred_functions` dans `app/routes/__init__.py`.

Le blueprint TCP a déjà `url_prefix='/api/tcp'`. Il produit :

- les routes documentées `/api/tcp/...` ;
- des clones inattendus `/api/credentials`, `/api/sessions`, `/api/status`.

Il n’existe pas de routes `/tcp/...` simples.

Toutes les réponses helpers ont la forme :

```json
{"success": true, "message": "...", "data": {}}
```

ou :

```json
{"success": false, "message": "...", "errors": null}
```

Exceptions : `/`, `/health`, téléchargements XML/SQL et erreurs natives Flask/JWT.

Dans les tableaux suivants, `{P}` signifie `""` ou `"/api"`, sauf indication TCP.

### Authentification et utilisateurs

| Méthode/URL | Auth/rôle | Entrée | Réponse/effet | Fichiers |
|---|---|---|---|---|
| POST `{P}/register` | Public | `full_name`, `email`, `password` | User, 201 ; pas de token | `routes/auth.py`, `validators.py`, `auth_service.py`, `user.py` |
| POST `{P}/login` | Public | email/password | User + access token | mêmes fichiers + `audit_service.py` |
| GET `{P}/me` | JWT | aucune | User courant | `routes/auth.py`, `auth_service.py` |
| POST `{P}/logout` | JWT | aucune | Efface tous les unlocks du user ; token non révoqué | `routes/auth.py`, `unlock_service.py` |
| GET `{P}/users` | JWT + email admin | `search`/`q`, `include_inactive` | Liste sans pagination | `routes/users.py`, `user_service.py`, `decorators.py` |
| GET `{P}/users/<id>` | JWT + admin | path ID | User | mêmes fichiers |
| POST `{P}/users` | JWT + admin | nom/email/password/is_active | User créé | `routes/users.py`, `user_service.py` |
| PUT `{P}/users/<id>` | JWT + admin | nom/email/is_active | User modifié | mêmes fichiers |
| DELETE `{P}/users/<id>` | JWT + admin | path ID | Suppression ; garde partielle admin | mêmes fichiers |
| POST `{P}/users/<id>/reset-password` | JWT + admin | `new_password` | Hash remplacé ; tokens non révoqués | mêmes fichiers |
| POST `{P}/users/<id>/toggle-active` | JWT + admin | aucune | Bascule activation | mêmes fichiers |

### Bases, tables, colonnes et métadonnées

| Méthode/URL | Auth | Entrée | Réponse/état | Fichiers |
|---|---|---|---|---|
| GET `{P}/databases` | JWT | `include_archived` | Toutes les bases | `routes/databases.py`, `database_service.py` |
| POST `{P}/databases` | JWT | name/description/comment | Base + clé, 201 | mêmes + `validators.py` |
| GET `{P}/databases/<id>` | JWT | header/query key optionnel | Base ; clé si créateur ou clé correcte | mêmes fichiers |
| PUT `{P}/databases/<id>` | JWT | name/description/comment/status | Modifie sans ACL ; renvoie clé | mêmes fichiers |
| DELETE `{P}/databases/<id>` | JWT | ID | Supprime sans ACL | mêmes fichiers |
| GET/PUT `{P}/databases/<id>/comment` | JWT | PUT `comment` | Fonctionnel | `routes/metadata.py`, `database_service.py` |
| POST `{P}/databases/<id>/archive` | JWT | aucune | Fonctionnel, sans ACL | mêmes fichiers |
| POST `{P}/databases/<id>/restore` | JWT | aucune | Fonctionnel, sans ACL | mêmes fichiers |
| GET `{P}/tables/<database_id>` | JWT | include_archived | Tables, file identifiers inclus | `routes/tables.py`, `table_service.py` |
| POST `{P}/tables` | JWT | name, database_id, protection, file ID, description/comment | Table créée sans ACL base | mêmes + `validators.py` |
| PUT `{P}/tables/<id>` | JWT | champs table + clé | Renommage/modification ; protection vérifiée | mêmes fichiers |
| DELETE `{P}/tables/<id>` | JWT | clé query/header/body | Suppression logique | mêmes fichiers |
| GET `{P}/tables/<id>/comment` | JWT | aucune | Fonctionnel | `routes/metadata.py`, `table_service.py` |
| PUT `{P}/tables/<id>/comment` | JWT | comment + clé | **500 : méthode service absente** | mêmes fichiers |
| POST `{P}/tables/<id>/archive` | JWT | clé | Fonctionnel | mêmes fichiers |
| POST `{P}/tables/<id>/restore` | JWT | clé | Fonctionnel | mêmes fichiers |
| GET `{P}/columns/<table_id>` | JWT | include_archived | Colonnes, sans contrôle de table | `routes/columns.py`, `column_service.py` |
| POST `{P}/columns` | JWT | définition + table_id + clé | Colonne ; aliases camelCase défectueux | mêmes + `validators.py` |
| PUT `{P}/columns/<id>` | JWT | champs + clé | Colonne modifiée | mêmes fichiers |
| DELETE `{P}/columns/<id>` | JWT | clé | Colonne supprimée | mêmes fichiers |
| GET `{P}/columns/<id>/comment` | JWT | aucune | Fonctionnel | `routes/metadata.py`, `column_service.py` |
| PUT `{P}/columns/<id>/comment` | JWT | comment + clé | **500 : méthode absente** | mêmes fichiers |
| POST `{P}/columns/<id>/archive` | JWT | clé | **500 : méthode absente** | mêmes fichiers |
| POST `{P}/columns/<id>/restore` | JWT | clé | **500 : méthode absente** | mêmes fichiers |

### Données, sync, import/export et conversion

| Méthode/URL | Auth | Entrée | Réponse/état | Fichiers |
|---|---|---|---|---|
| GET `{P}/tables/<id>/rows` | JWT | limit/offset | Rows + total ; protection non vérifiée | `routes/rows.py`, `row_service.py` |
| POST `{P}/tables/<id>/rows` | JWT | dict ou `{data}`, clé | Crée JSON row | mêmes fichiers |
| PUT `{P}/tables/<id>/rows/<row_id>` | JWT | dict ou `{data}`, clé | Remplace row | mêmes fichiers |
| DELETE `{P}/tables/<id>/rows/<row_id>` | JWT | clé | Supprime row | mêmes fichiers |
| POST `{P}/databases/<id>/sync-xml` et `/sync` | JWT | `xml`, clé optionnelle | Met à jour SQLAlchemy, renvoie diff + SQL ; pas MySQL | `routes/sync.py`, `sync_service.py`, `import_service.py`, `export_service.py` |
| POST `{P}/tables/<id>/sync-xml` et `/sync` | JWT | `xml`, clé | Sync une table, renvoie XML/SQL | mêmes fichiers |
| POST `{P}/import/xml` | JWT | multipart file ou JSON xml + metadata | Nouvelle base logique, rows incluses | `routes/imports.py`, `import_service.py` |
| POST `{P}/import/sql` | JWT | multipart file ou JSON sql | Nouvelle base ; INSERT parsés mais rows non persistées | mêmes + `sql_to_xml.py` |
| GET `{P}/export/xml/<database_id>` | JWT | `download=true` | XML calculé ; aucune ACL | `routes/exports.py`, `export_service.py` |
| GET `{P}/export/sql/<database_id>` | JWT | download | SQL calculé | mêmes + `xml_to_sql.py` |
| GET `{P}/export/table-xml/<table_id>` | JWT | download | XML table avec rows | mêmes fichiers |
| GET `{P}/export/table-sql/<table_id>` | JWT | download | SQL structure seulement | mêmes fichiers |
| GET `{P}/export/xml/table/<id>` | JWT | alias | Alias table XML | `routes/exports.py` |
| GET `{P}/export/sql/table/<id>` | JWT | alias | Alias table SQL | `routes/exports.py` |
| GET `{P}/export/project/<database_id>` | JWT | download | Projet d’une base, données + secrets | `routes/projects.py`, `project_service.py` |
| POST `{P}/import/project` | JWT | multipart ou JSON xml | Nouvelle base/projet | mêmes fichiers |
| POST `{P}/convert/xml-to-sql` | JWT | xml + nom optionnel | SQL | `routes/converters.py`, converters |
| POST `{P}/convert/sql-to-xml` | JWT | sql + nom optionnel | XML | mêmes fichiers |
| POST `{P}/database/create` | JWT | database_id, target name optionnel | Matérialisation MySQL partielle | `routes/database_create.py`, `export_service.py` |

### Protection, historique, audit et TCP

| Méthode/URL | Auth | Entrée | Réponse/état | Fichiers |
|---|---|---|---|---|
| POST `{P}/unlock-table` | JWT | table_id + key_identifier | Unlock utilisateur 24 h | `routes/unlock.py`, `unlock_service.py`, `table_service.py` |
| GET `{P}/unlocks` | JWT | aucune | Unlocks valides | mêmes fichiers |
| DELETE `{P}/unlocks` | JWT | aucune | Efface tous les unlocks utilisateur | mêmes fichiers |
| GET `{P}/history` | JWT + admin | limit, database_id | Historique max 500 | `routes/history.py`, `history_service.py` |
| GET `{P}/audit-logs` ou `{P}/audit` | JWT + admin | limit | Audit max 500 | `routes/audit.py`, `audit_service.py` |
| GET `/api/tcp/credentials` | JWT | aucune | Auto-crée si absent mais ne rend pas le mot de passe auto-généré | `routes/tcp.py`, `tcp_credential_service.py` |
| POST `/api/tcp/credentials` | JWT | username/password/host/port | Credential + mot de passe clair initial | mêmes fichiers |
| PUT `/api/tcp/credentials` | JWT | champs optionnels | Credential modifié, mais ignoré par serveur | mêmes fichiers |
| POST `/api/tcp/credentials/regenerate` | JWT | aucune | Nouveau secret en clair | mêmes fichiers |
| DELETE `/api/tcp/credentials` | JWT | aucune | Supprime le credential | mêmes fichiers |
| POST `/api/tcp/credentials/show-password` | JWT | current_password | **500 : `AuthService.verify_password` absent** | mêmes + `auth_service.py` |
| GET `/api/tcp/sessions` | JWT | aucune | Devrait filtrer par user, mais compare email et ID : liste vide | `routes/tcp.py`, `tcp_server.py` |
| GET `/api/tcp/status` | Public | aucune | État serveur et nombre de sessions | mêmes fichiers |

Les mêmes routes TCP clonées existent sous `/api/credentials`, `/api/sessions`, `/api/status`.

## 4.9 TCP/IP détaillé

### Emplacement et démarrage

- `app/tcp/tcp_protocol.py` : framing et codes.
- `app/tcp/tcp_server.py` : socket, threads, sessions, auth et requêtes.
- `app/tcp/xmlforge_client.py` : client Python.
- `app/__init__.py` : démarre automatiquement `TCPServer(0.0.0.0, 3307, flask_app)` dans un thread daemon.

Le port et l’host sont codés en dur dans la factory, sans configuration dédiée.

### Protocole

```text
[type: uint8][longueur JSON: uint32 big-endian][JSON UTF-8]
```

Types : AUTH=1, QUERY=2, RESPONSE=3, ERROR=4, PING=5, PONG=6.

Auth request : `username`, `password`, `database` optionnelle.  
Query request : `query`, `session_token`.

### Authentification et identification

- `username` est résolu comme email `User`.
- `password` est vérifié contre `User.password_hash` par `AuthService.verify_credentials()`.
- `TcpCredential.tcp_username`, son mot de passe et `is_active` ne sont jamais consultés.
- La base est choisie par nom avec `get_database_by_name_any_user()` ; aucune propriété/permission n’est vérifiée.
- Si le nom n’existe pas, l’auth réussit sans base.

### Sessions

Sessions UUID stockées dans un dictionnaire en mémoire, propres au processus. Expiration annoncée à 30 minutes.

Problèmes :

- la session n’est pas retirée lors de la déconnexion socket ;
- le handler ne rattache pas correctement la session locale juste après AUTH, car il cherche un token dans la requête AUTH ;
- une query peut néanmoins récupérer la session par le token envoyé ;
- l’expiration n’est pas vérifiée lors de cette récupération ; elle est surtout nettoyée par `get_sessions_info()` ou un timeout lié à une session locale ;
- sessions perdues au redémarrage et non partagées entre workers ;
- pas de révocation lors d’un changement de mot de passe ou désactivation ;
- pas de limite par utilisateur/IP.

### Opérations

- PING/PONG : présent.
- SELECT : lit les `TableRow` du catalogue SQLAlchemy.
- INSERT : TODO, retourne `{"inserted": 0}`.
- UPDATE : TODO, retourne `{"updated": 0}`.
- DELETE : TODO, retourne `{"deleted": 0}`.

### Sécurité et maturité

- TCP en clair, sans TLS.
- Mot de passe transmis en clair dans JSON sur le réseau.
- Pas de permissions, de contrôle de protection, d’audit TCP ou de rate limit.
- Pas de taille maximale explicite de message.
- Pas de requêtes paramétrées ; le client construit des chaînes SQL sans escaping fiable.
- Pas de transaction, pagination réelle, JOIN, DDL, changement de base ni prepared statements.
- SELECT interroge JSON SQLAlchemy, pas MySQL.
- Un utilisateur peut sélectionner une base homonyme appartenant à n’importe qui.
- Le statut REST peut indiquer `running=True` avant que le thread ait réellement réussi le `bind()`.
- En mode debug/reloader ou multi-worker, plusieurs démarrages peuvent entrer en conflit sur le port.

Pour qu’une application externe utilise réellement XMLForge, TCP doit devenir un simple transport vers le même `QueryService` autorisé, typé, transactionnel et synchronisé que REST. Il ne doit pas conserver sa propre logique de parsing et d’accès aux modèles.

## 4.10 Permissions et accès aux bases

### Ce qui existe

- `Database.creator_id` identifie le créateur.
- `DatabaseService.get_database_by_name(user_id, name)` sait filtrer par créateur, mais les routes REST ne l’utilisent pas et TCP utilise explicitement la version « any user ».
- Le rôle administrateur est une comparaison d’email.
- La clé de base/table contrôle certaines écritures sur tables protégées.

### Ce qui n’existe pas

- Aucun propriétaire explicite distinct du créateur.
- Aucun type personal/common.
- Aucun membre de base.
- Aucun droit lecture, écriture, création de table, suppression ou administration.
- Aucun héritage de droits base → table.
- Aucun contrôle centralisé route/service.
- Aucun filtrage de liste.
- Aucun partage ou invitation.
- Aucun droit TCP.

### Conclusion

La protection par secret ne doit pas être confondue avec une ACL. Elle peut rester une protection additionnelle ou un verrou éditorial, mais doit être évaluée **après** l’autorisation de l’utilisateur et ne jamais exposer son secret dans les serializers publics.

---

# 5. Cartographie détaillée des dossiers et fichiers

## 5.1 Racine `backend/`

| Fichier/dossier | Rôle réel, interactions et évolution probable |
|---|---|
| `run.py` | Point d’entrée Flask/SocketIO. Appelle `create_app(Config)` puis lance en debug. Devra sélectionner une config par environnement et ne pas démarrer debug en production. |
| `config.py` | Wrapper de compatibilité réexportant les configs de `app/config.py`. Aucun métier. À conserver si des outils externes l’importent. |
| `requirements.txt` | Dépendances Flask/SQLAlchemy/JWT/bcrypt/CORS/SocketIO/MySQL/Marshmallow. `lxml` est commenté alors qu’il est importé au démarrage par les converters : un environnement créé uniquement depuis ce fichier peut échouer. |
| `.env.example` | Variables Flask/JWT/SQLAlchemy/MySQL/CORS. Ne décrit pas le TCP configurable, le stockage XML ou les politiques de sync. |
| `README.md` | Documentation backend historique V1/V2. Utile comme intention, mais pas source de vérité. Affirme notamment « production ready ». |
| `API_DOCUMENTATION.md` | Contrats documentés principalement V2/V3. Ne reflète pas toutes les routes V4/TCP ni les endpoints cassés. |
| `BACKEND_DOCUMENTATION.md` | Documentation très détaillée d’intention. Elle affirme XML source de vérité alors que le SQLAlchemy interne l’est réellement. |
| `TCP_SERVER_README.md` | Décrit le TCP et affirme le support complet CRUD ; le code n’implémente que SELECT. L’exemple cURL vers le port TCP est incompatible avec le protocole binaire. |
| `postman_collection.json` | Collection manuelle d’API. À régénérer depuis un contrat OpenAPI lorsque les routes seront stabilisées. |
| `xmlforge.xsd` | Copie XSD racine, actuellement incompatible avec les exports réels. |
| `BaseDonnees_INPTIC.xml`, `test.xml` | Exemples XML non utilisés automatiquement. Tous deux utilisent `<columns>/<rows>` et sont invalides contre le XSD actuel. |
| `InptricConcours_database.xml`, `base_donnees_alumni_inptic.xml`, `inptic_database_schema.xml`, `soutenance_app.xml` | Fichiers XML vides versionnés ; aucune logique ne les charge. |
| `converters` | Ancien script Python sans extension, dupliquant des converters plus anciens. Aucun import du backend actuel ne le référence. À marquer legacy puis retirer seulement après vérification externe. |
| `uploads/`, `exports/` | Placeholders créés au démarrage. Les routes ne sauvegardent aucun upload/export dedans. |
| `check_user.py` | Script opérationnel ciblé sur un email codé en dur ; crée aussi l’app, donc tente de démarrer TCP. |
| `create_test_user.py`, `create_yann_user.py` | Scripts de seed manuels contenant des mots de passe de démonstration en clair. Ne remplacent pas une migration/commande CLI sûre. |
| `create_essoya_tcp.py` | Crée un credential TCP spécifique, mais le serveur TCP ne l’utilise pas. |
| `get_tp_javabd_tables.py` | Script d’inspection d’une base logique nommée en dur. |
| `test_tcp_credentials.py`, `test_tcp_server.py` | Scripts interactifs/manuels, pas des tests automatisés isolés. Certains « tests » vérifient seulement des imports ou impriment les routes attendues. |

## 5.2 `app/`

| Fichier/dossier | Rôle et flux |
|---|---|
| `app/__init__.py` | Factory centrale : config, dossiers, extensions, routes, create_all, pseudo-migrations, TCP, health/index. C’est le point de couplage principal. Devra déléguer migrations et lifecycle TCP. |
| `app/app.py` | Wrapper de compatibilité qui instancie l’app à l’import et lance SocketIO en debug s’il est exécuté. Risque de doubles side effects. |
| `app/config.py` | Config SQLAlchemy/JWT/MySQL/CORS/paths. SQLite interne par défaut. `ProductionConfig` ne renforce aucune exigence. |
| `app/extensions.py` | Instances globales SQLAlchemy, JWT, bcrypt, CORS et SocketIO. Correct pour éviter imports circulaires. |
| `app/socket_events.py` | Helpers d’émission globale d’événements. Appelé par les services après CRUD. Pas d’auth SocketIO, rooms par base ou gestion de client ; les exceptions sont avalées. |
| `app/static/xmlforge.xsd` | Deuxième copie du XSD ; risque de divergence, bien qu’identique actuellement. |
| `app/uploads/`, `app/exports/` | Deux autres placeholders, également inutilisés. |

### `app/auth/`

- `__init__.py` réexporte seulement `protected_table_required`.
- `decorators.py` contient :
  - `protected_table_required`, non utilisé par les routes principales, vérifie clé de base/file identifier mais pas unlock personnel ;
  - `admin_required`, utilisé par users/history/audit et fondé sur l’email hardcodé.

Ce dossier devra accueillir ou appeler une autorisation centralisée, sans dupliquer les règles déjà présentes dans plusieurs services.

### `app/converters/`

- `xml_to_sql.py` : parse XML et génère DDL/DML MySQL.
- `sql_to_xml.py` : parser SQL regex puis XML.
- `__init__.py` : API publique des deux modules.

Ils sont appelés par import/export/conversion/sync et `/database/create`. Ils doivent devenir consommateurs d’un même modèle canonique de schéma plutôt que chacun interpréter des variantes XML.

### `app/database/`

`__init__.py` est vide. Aucun repository de connexion ou transaction ne s’y trouve. Ce dossier est un emplacement naturel pour la couche d’exécution MySQL, mais il ne joue actuellement aucun rôle.

### `app/models/`

- `__init__.py` importe tous les modèles pour `db.create_all()`.
- `user.py` : identité, bcrypt hash stocké, admin par email.
- `database.py` : catalogue logique et clé de base.
- `table.py` : table logique, protection et file identifier.
- `column.py` : métadonnées de colonnes, sans référence FK.
- `table_row.py` : rows JSON.
- `table_unlock.py` : unlock utilisateur/table 24 h.
- `tcp_credential.py` : credentials TCP séparés mais non consommés par TCPServer.
- `history.py` : historique métier before/after sérialisé.
- `audit_log.py` : journal sensible séparé.

Les modèles actuels sont le stockage réel. Ils devront distinguer le control plane (users/ACL/sync state) du contenu canonique XML et du runtime MySQL.

### `app/routes/`

- `__init__.py` enregistre chaque blueprint deux fois via clonage interne ; le cas TCP produit des aliases inattendus.
- `auth.py` : register/login/me/logout.
- `users.py` : schemas locaux + CRUD admin.
- `databases.py` : CRUD base sans permission.
- `tables.py` : CRUD table et protection.
- `columns.py` : CRUD colonne.
- `rows.py` : CRUD data JSON.
- `metadata.py` : commentaires/archive/restore ; cinq appels ciblent des méthodes absentes.
- `imports.py` : multipart ou JSON pour XML/SQL.
- `exports.py` : exports base/table, JSON ou download.
- `projects.py` : export/import complet d’une base logique.
- `converters.py` : conversion texte sans persistance.
- `sync.py` : sync XML base/table vers SQLAlchemy.
- `database_create.py` : déploiement ponctuel MySQL.
- `unlock.py` : unlocks personnels.
- `history.py`, `audit.py` : consultation admin.
- `tcp.py` : gestion REST des credentials/sessions/statut TCP ; préfixe atypique et endpoint show-password cassé.

Les routes font validation légère, résolvent l’utilisateur et appellent les services. Elles ne doivent pas porter la future logique ACL ou sync transactionnelle.

### `app/services/`

- `auth_service.py` : bcrypt, login/register/JWT et vérification du mot de passe principal pour TCP. Il ne contient pas `verify_password` attendu par la route TCP.
- `user_service.py` : CRUD admin, historique/audit.
- `database_service.py` : CRUD catalogue, commentaire/archive/restore et deux lookups TCP par nom.
- `table_service.py` : CRUD, archive/restore et protection ; pas de `update_comment`.
- `column_service.py` : create/update/delete uniquement ; pas de commentaire/archive/restore.
- `row_service.py` : rows JSON, contrôle de protection seulement en écriture.
- `unlock_service.py` : vérification des clés et unlock 24 h.
- `import_service.py` : parse XML V3/V4 ou SQL et crée le graphe SQLAlchemy.
- `export_service.py` : sérialise modèles/rows en XML, puis XML → SQL.
- `project_service.py` : variante d’export/import qui inclut données et secret de base.
- `sync_service.py` : merge/remplacement XML vers modèles, puis génération SQL sans exécution.
- `tcp_credential_service.py` : hash/génération CRUD des credentials TCP.
- `history_service.py`, `audit_service.py` : écrivent et commitent leurs journaux.
- `__init__.py` : réexporte la plupart des services, mais pas `TcpCredentialService`.

Il n’y a aucun service unifié de permission, de requête, de validation de données ou de synchronisation MySQL.

### `app/tcp/`

- `__init__.py` réexporte serveur, protocole et client.
- `tcp_protocol.py` définit framing, types et helpers.
- `tcp_server.py` gère sockets/threads/sessions et SELECT logique.
- `xmlforge_client.py` est un client Python synchrone qui construit des chaînes SQL.
- `examples.py` contient des exemples, y compris des writes qui retournent zéro avec le serveur actuel.
- `SETUP.md` est une documentation mêlée à un fichier `.py`-style contenant des chaînes ; elle n’est pas exécutée.

### `app/utils/`

- `helpers.py` : génération cryptographique de clés, slug, date UTC et regex email.
- `responses.py` : enveloppes JSON et helper pagination non utilisé par les rows.
- `validators.py` : Marshmallow schemas avec `unknown=INCLUDE`, ce qui laisse passer de nombreux champs non maîtrisés.
- `__init__.py` : vide.

---

# 6. Documentation versus code

| Affirmation documentaire | Code réel |
|---|---|
| « XML est source de vérité » | SQLAlchemy est la persistance ; XML n’est pas écrit. |
| XSD « valide la spec V3 » | Le XSD rejette les XML produits et les exemples versionnés. |
| TCP supporte SELECT/INSERT/UPDATE/DELETE | INSERT/UPDATE/DELETE sont TODO et retournent zéro. |
| Credentials TCP affichables et utilisables | show-password appelle une méthode absente ; TCPServer utilise le mot de passe principal. |
| Production ready | debug direct, secrets fallback, pas de TLS TCP, pas d’ACL, pas de tests ni migrations. |
| Commentaires/archive/restore colonnes | Routes présentes, méthodes service absentes. |
| Commentaire table | Route présente, méthode absente. |
| Sessions TCP utilisateur | Le filtre compare email à ID JWT et ne retrouve pas les sessions. |
| Dossiers upload/export stockent les fichiers | Aucun fichier n’y est sauvegardé. |
| MySQL comme base réelle synchronisée | Matérialisation ponctuelle uniquement. |
| `/` liste `/tcp/credentials` | Les routes réelles sont `/api/tcp/...` et aliases `/api/...`. |
| `lxml` disponible | Import obligatoire, mais dépendance commentée dans `requirements.txt`. |

La documentation reste utile pour comprendre l’intention, mais ne doit pas servir de contrat tant que ces écarts ne sont pas résolus.

---

# 7. Comparaison architecture actuelle / architecture cible

| Fonctionnalité | État actuel | Problème | Comportement cible | Fichiers concernés | Dépendances |
|---|---|---|---|---|---|
| XML canonique | Export calculé, XSD incohérent | Pas de vérité persistante | Un XML versionné, validé et écrit atomiquement par base | XSD, import/export/sync/converters, modèles Database | Migrations, storage repository |
| MySQL runtime | Création ponctuelle | Drift immédiat après changement | Schéma MySQL associé, DDL/DML transactionnels depuis XML | config, database_create, sync, futurs repositories | XML canonique, query service |
| SQL → XML | Parser texte CREATE/INSERT | Pas d’introspection MySQL ni UPDATE/DELETE | Introspection contrôlée ou change pipeline, selon politique | sql_to_xml, futur mysql repository | Mapping et transactions |
| Propriété | `creator_id` informatif | Toutes les bases sont globales | owner explicite, filtre systématique | Database, routes/services | ACL |
| Bases communes | Rien | Aucun partage | visibilité + memberships/permissions | nouveaux modèles ACL | Rôles/utilisateurs |
| Rôles | Email hardcodé | Admin revendicable et non extensible | rôles persistés, superadmin seedé | User, decorators, auth/user services | Migrations |
| Permissions | Secret de table seulement | Fuite des secrets, lecture ouverte | read/write/DDL/delete/admin centralisés | toutes routes/services, TCP | ACL et query service |
| Contraintes | Flags de colonne | Non appliquées aux rows | modèle de contraintes + MySQL + validation pré-écriture | Column, row/sync/import/export | XML schema |
| FK | Flag + cible temporaire converter | Référence perdue | référence persistée, validée et générée | Column ou Constraint, converters | ordre DDL, introspection |
| CRUD data | JSON opaque | Pas de types/filtres/relations | SQL MySQL exécuté, write-back XML atomique | RowService, routes rows | Query/sync engine |
| JOIN | Absent | Pas de fonctionnalités relationnelles | requêtes contrôlées via MySQL | nouveau QueryService/API/TCP | ACL, schema catalog |
| Protection | Clé en clair exposée | Ne protège pas les données | ACL d’abord, secret masqué/hashé, verrou optionnel | Table serializers/unlock | Permissions |
| API | Double routes et services directs | Contrat ambigu, erreurs disparates | `/api/v1`, schemas cohérents, erreurs globales | routes init/all routes | Services stabilisés |
| TCP | Prototype parallèle | Bypass ACL, writes absents | transport vers le même moteur métier | tcp server/protocol/client | QueryService, TLS/auth |
| Import/export | Par base | Pertes FK/rows SQL, pas global | round-trip canonique et export plateforme distinct | import/export/project | XML, ACL |
| Sessions/token | JWT stateless | Pas de révocation | jti/refresh/revocation et active check | auth/config/models | Migrations/cache |
| Migrations | create_all + ALTER ad hoc | Non reproductible | Alembic/version de schéma | app init + nouveau migrations | Tous changements modèle |
| Tests | Scripts manuels | Régressions non détectées | unitaires/intégration/API/TCP/MySQL | nouveau tests | Environnements de test |

---

# 8. Plan structuré des futures modifications

## FONCTIONNALITÉ 1 — Définir le XML canonique et son stockage

**Fichiers existants à modifier :**

- `backend/xmlforge.xsd` et `backend/app/static/xmlforge.xsd` : fusionner la source, décrire exactement columns/rows/cells/NULL/types/relations/contraintes/metadata/version.
- `app/models/database.py` : ajouter référence de document, version/checksum/état de stockage, sans mettre le contenu métier dans ce modèle.
- `app/services/import_service.py`, `export_service.py`, `project_service.py`, `sync_service.py` : utiliser un même parseur/serializer canonique.
- `app/converters/*.py` : consommer la représentation canonique.
- `requirements.txt` : rendre `lxml` explicite.

**Nouveaux fichiers recommandés :**

- `app/repositories/xml_repository.py` : lecture/écriture atomique, verrou de fichier, checksum, backup et chemins sûrs.
- `app/xml/document.py` : dataclasses/objets canoniques Database/Table/Column/Constraint/Row.
- `app/xml/parser.py` et `app/xml/serializer.py` : un seul parser et un seul serializer.
- `app/xml/validator.py` : validation XSD sécurisée et erreurs structurées.

**Pourquoi :** supprimer les variantes concurrentes et rendre vraie l’affirmation « XML source de vérité ».

**Dépendances :** décisions sur NULL, types, UUID/PK de rows, contraintes composites, ordre des tables et emplacement des fichiers.

**Impact :** import, export, sync, CRUD et TCP devront tous passer par cette couche.

## FONCTIONNALITÉ 2 — Migrations et séparation control plane / données métier

**À modifier :** `app/__init__.py`, `app/config.py`, tous les modèles.

**Nouveaux fichiers/dossiers :**

- `migrations/` avec Alembic/Flask-Migrate ;
- éventuellement `app/models/database_runtime.py` pour `xml_path`, schéma MySQL, version appliquée, checksum et dernier résultat de sync.

**Pourquoi :** `create_all()` ne migre pas les colonnes et les ALTER ad hoc ne sont pas fiables. Le control plane doit garder users/ACL/audit, tandis que le contenu métier canonique reste XML et son exécution MySQL.

**Dépendances :** modèle XML et politique de déploiement.

**Impact :** prérequis à tous les nouveaux modèles.

## FONCTIONNALITÉ 3 — Rôles et administration sûre

**À modifier :** `models/user.py`, `services/auth_service.py`, `user_service.py`, `auth/decorators.py`, `routes/users.py`, scripts de seed.

**Nouveaux fichiers :**

- `models/role.py`, `models/user_role.py` ;
- `services/role_service.py` ;
- migration/commande CLI de bootstrap superadmin.

**Pourquoi :** remplacer la comparaison d’email. Réserver ou seed `nyx@xmlforge.io` de manière explicite, mais ne pas faire de l’email le droit lui-même.

**Dépendances :** migrations et stratégie de bootstrap.

**Impact :** admin_required, réponses User, frontend et tokens.

## FONCTIONNALITÉ 4 — Permissions et bases personnelles/communes

**À modifier :** `database.py`, `database_service.py`, tous les services database/table/column/row/import/export/sync, toutes les routes correspondantes, TCP.

**Nouveaux fichiers :**

- `models/database_access.py` ou `database_membership.py` avec owner/member et droits read/write/create_table/delete/admin ;
- `services/permission_service.py` ;
- `auth/permissions.py` pour helpers/décorateurs fins ;
- routes de partage/membres.

**Pourquoi :** filtrer les listes et contrôler chaque opération au niveau service, pas seulement route. Le propriétaire doit être distinct ou explicitement dérivé du créateur. Une base commune doit avoir une visibilité et des ACL explicites.

**Dépendances :** rôles et modèle de propriété.

**Impact :** changement transversal et correction de la fuite inter-utilisateurs.

## FONCTIONNALITÉ 5 — Modèle relationnel complet

**À modifier :** `models/column.py`, validators, column/import/export/sync services et converters.

**Nouveaux fichiers possibles :**

- `models/constraint.py` pour PK/UNIQUE/FK/CHECK composites et actions référentielles ;
- `models/index.py` si les index ne sont pas représentés uniquement dans XML ;
- `services/schema_validation_service.py`.

**Pourquoi :** un booléen `foreign_key` sans cible ne suffit pas. Les contraintes composites et actions doivent être représentables sans perte.

**Dépendances :** document XML canonique et dialecte MySQL supporté.

**Impact :** DDL MySQL, import/export et validation des rows.

## FONCTIONNALITÉ 6 — Synchronisation XML → MySQL transactionnelle

**À modifier :** `sync_service.py`, `database_create.py`, `config.py`, `export_service.py`.

**Nouveaux fichiers :**

- `app/repositories/mysql_repository.py` : connexions, transactions, introspection et requêtes paramétrées ;
- `app/services/schema_diff_service.py` : diff XML canonique ↔ schéma appliqué ;
- `app/services/mysql_sync_service.py` : ordre DDL, DML, rollback/compensation ;
- `app/services/sync_state_service.py` : versions/checksums/drift.

**Pourquoi :** passer de la création ponctuelle à une synchronisation mesurable et reproductible.

**Dépendances :** XML canonique, contraintes, mapping runtime et migrations.

**Impact :** cœur de l’architecture cible ; doit être développé avant le CRUD final.

## FONCTIONNALITÉ 7 — CRUD de données et moteur de requêtes commun

**À modifier :** `row_service.py`, `routes/rows.py`, `table_row.py` — ce dernier devra être clairement cache/transitoire ou supprimé via migration, pas rester une seconde vérité.

**Nouveaux fichiers :**

- `services/query_service.py` : SELECT/INSERT/UPDATE/DELETE/JOIN autorisés ;
- `services/data_validation_service.py` : types/defaults/PK/FK/UNIQUE/NOT NULL ;
- `utils/sql_identifiers.py` : validation/quoting centralisé ;
- schemas de filtres, tri, pagination et projections.

**Pourquoi :** MySQL doit exécuter les opérations ; chaque écriture réussie doit produire une mise à jour XML atomique ou suivre une stratégie outbox explicite.

**Dépendances :** synchronisation, ACL et contraintes.

**Impact :** REST, TCP, import et interface web.

## FONCTIONNALITÉ 8 — Cohérence tables/colonnes/protection

**À modifier :** `table_service.py`, `column_service.py`, `routes/metadata.py`, validators, serializers `to_dict()`.

**Nouveaux fichiers éventuels :** aucun obligatoire si les méthodes sont ajoutées proprement aux services ; un `protection_service.py` peut éviter les trois implémentations actuelles.

**Pourquoi :** réparer les cinq endpoints cassés, normaliser camelCase/snake_case, gérer renames dans les rows/XML/MySQL, masquer les secrets et distinguer protection de permission.

**Dépendances :** ACL et moteur de sync.

**Impact :** correction immédiate d’API puis migration vers le flux canonique.

## FONCTIONNALITÉ 9 — Authentification renforcée et tokens

**À modifier :** config, extensions, auth routes/services, User, decorators.

**Nouveaux fichiers :**

- `models/revoked_token.py` ou adaptateur Redis ;
- `services/token_service.py` ;
- callbacks JWT et éventuellement refresh endpoints.

**Pourquoi :** révocation logout/reset/désactivation, contrôle `is_active`, secrets de production obligatoires, rate limit et politique de mot de passe.

**Dépendances :** migrations et choix de stockage de blocklist.

**Impact :** tous les clients devront gérer refresh/logout réel.

## FONCTIONNALITÉ 10 — API versionnée et erreurs cohérentes

**À modifier :** `routes/__init__.py`, toutes les routes, `utils/responses.py`, validators.

**Nouveaux fichiers :**

- `app/errors.py` avec erreurs métier typées et handlers Flask/JWT ;
- `app/schemas/` pour centraliser request/response schemas ;
- contrat OpenAPI.

**Pourquoi :** supprimer le clonage fragile, choisir `/api/v1`, uniformiser les codes et ne plus exposer `str(e)`.

**Dépendances :** services et ACL stabilisés.

**Impact :** possible dépréciation progressive des routes sans préfixe.

## FONCTIONNALITÉ 11 — TCP/IP utilisable et sûr

**À modifier :** `tcp_server.py`, `tcp_protocol.py`, `xmlforge_client.py`, `routes/tcp.py`, `tcp_credential_service.py`, lifecycle dans `app/__init__.py`.

**Nouveaux fichiers :**

- `tcp/query_parser.py` seulement si SQL texte est conservé ; sinon protocole d’opérations structurées ;
- `tcp/session_store.py` avec expiration/révocation partagée ;
- configuration TLS et certificats hors dépôt ;
- tests de protocole.

**Pourquoi :** utiliser réellement les credentials TCP ou supprimer cette duplication au profit de tokens applicatifs ; router toutes les opérations vers `QueryService` et `PermissionService` ; ajouter TLS, limites, audit et lifecycle propre.

**Dépendances :** QueryService, ACL, sync MySQL et auth.

**Impact :** le client Python devra échapper/paramétrer les valeurs et gérer les nouvelles erreurs/version du protocole.

## FONCTIONNALITÉ 12 — Import/export fiable et export global

**À modifier :** import/export/project services et routes, converters.

**Nouveaux fichiers :**

- `services/platform_export_service.py` pour un export global distinct des exports de base ;
- manifeste versionné d’export, éventuellement archive ZIP avec checksums.

**Pourquoi :** conserver rows SQL, FK, contraintes et NULL ; séparer export d’une base, export projet et sauvegarde complète XMLForge. Les secrets et hashes ne doivent pas être exportés sans mode sécurisé/chiffré.

**Dépendances :** XML canonique, ACL, rôles et migrations.

**Impact :** compatibilité/versionnage du format.

## FONCTIONNALITÉ 13 — Tests, observabilité et robustesse

**À modifier :** scripts `test_tcp_*`, services de log, app factory.

**Nouveaux dossiers :**

- `tests/unit/`, `tests/integration/`, `tests/api/`, `tests/tcp/` ;
- fixtures SQLite control plane + MySQL containerisé ;
- tests de round-trip XML/SQL, XSD, ACL, transactions et concurrence.

**Pourquoi :** les régressions constatées auraient été détectées par quelques tests d’endpoint et de contrat.

**Dépendances :** aucune pour commencer ; les tests doivent accompagner chaque étape.

**Impact :** condition de sécurité pour refactorer sans réécriture globale.

---

# 9. Ordre de développement recommandé

L’ordre suivant est fondé sur les dépendances du code actuel :

1. **Geler le comportement actuel par des tests** : route map, auth, CRUD logique, import/export, bugs connus, TCP framing.
2. **Introduire de vraies migrations** et sécuriser les configs/secrets/lifecycle app-TCP.
3. **Corriger les vulnérabilités immédiates** : empêcher l’enregistrement libre de l’admin réservé, masquer file identifiers/keys, bloquer accès inter-utilisateurs minimal, réparer les méthodes absentes.
4. **Définir et valider le XML canonique** : version, XSD compatible, parser/serializer unique, tests de round-trip.
5. **Ajouter rôles, propriétaire, memberships et permissions** ; appliquer au niveau service puis routes et TCP.
6. **Compléter le modèle relationnel** : références FK, contraintes composites, index, types et règles de validation.
7. **Mettre en place le repository MySQL et le mapping runtime** sans encore exposer de nouveaux CRUD complexes.
8. **Construire le diff/sync XML → MySQL transactionnel** et les états de sync/drift.
9. **Remplacer progressivement RowService JSON par QueryService MySQL + write-back XML** ; commencer INSERT/UPDATE/DELETE simples, puis filtres/tri/pagination.
10. **Ajouter relations et JOIN** via MySQL avec validation ACL et projections sûres.
11. **Faire converger l’API Flask** vers `/api/v1`, schemas et erreurs cohérentes, en gardant temporairement des aliases de compatibilité explicites.
12. **Brancher TCP sur QueryService/PermissionService** ; implémenter writes, sessions sûres, TLS et protocole versionné.
13. **Réviser import/export** pour le format canonique et ajouter l’export global XMLForge.
14. **Tests de charge, concurrence, crash/recovery et sécurité**, puis seulement retirer le stockage JSON/legacy devenu inutile.

Pourquoi cet ordre : implémenter d’abord TCP CRUD ou des JOIN sur `TableRow.data_json` créerait une seconde logique qu’il faudrait jeter. De même, synchroniser MySQL avant d’avoir un XML canonique et des contraintes persistables produirait des migrations non déterministes. Les ACL doivent précéder l’exposition de nouvelles capacités de requête.

---

# 10. Actions immédiates recommandées sans réécriture complète

Avant tout grand chantier, un petit lot correctif devrait :

1. réserver/seed correctement l’administrateur et interdire que `/register` attribue ce privilège implicitement ;
2. filtrer les bases par utilisateur et empêcher les écritures tierces ;
3. retirer `file_identifier` et `key_identifier` des serializers non autorisés ;
4. faire vérifier protection/permission par la lecture rows, exports, sync et TCP ;
5. implémenter ou retirer temporairement les endpoints appelant des méthodes absentes ;
6. corriger `AuthService.verify_password` ou supprimer le endpoint show-password tant que le contrat n’est pas cohérent ;
7. décider si TCP utilise le mot de passe principal ou `TcpCredential`, puis n’en garder qu’un contrat ;
8. marquer INSERT/UPDATE/DELETE TCP comme non supportés au lieu de retourner un faux succès zéro ;
9. ajouter `lxml` aux requirements ;
10. corriger le XSD ou cesser de prétendre valider les exports avec lui ;
11. désactiver debug et les secrets fallback en production ;
12. ajouter cinq tests d’isolation/ACL et cinq tests de contrat XML/TCP.

Ces corrections ne remplacent pas l’architecture cible, mais elles évitent d’aggraver les risques pendant sa construction.

---

# 11. Vérification finale du repository analysé

Juste avant la production de ce document :

- `origin/main` = `ccfd9c57f0345799bfe95167ac85bda82c7787f5` ;
- clone local `HEAD` = même commit ;
- branche = `main` ;
- working tree du clone = propre ;
- intégrité Git = OK.

La présente analyse correspond donc au backend du repository GitHub actuellement récupéré, et non à une version ancienne du workspace.
