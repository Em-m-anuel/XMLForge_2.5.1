# XMLForge Backend V5 — Documentation technique

> Cette documentation décrit uniquement les fonctionnalités réellement présentes dans le backend du dépôt. Le frontend n’est pas concerné.
>
> **Moteur XML natif (Phase 4)** : un moteur de données XML fonctionne **en
> parallèle de SQLite** (champ `engine` sur REST et TCP : `sqlite` | `xml` |
> `compare`). Il couvre le DDL complet, les index, les contraintes, les
> opérateurs, la pagination et l'introspection de schéma. Depuis la Phase 4,
> **XML peut être le moteur principal** : `QUERY_BACKEND=xml` +
> `SYNC_SQLITE_PROJECTION=false` active un **mode XML pur** où les données
> métier ne dépendent plus de SQLite (aucun fallback silencieux). Voir
> **[XML_BACKEND_MODE.md](../XML_BACKEND_MODE.md)**,
> **[SQLITE_DEPENDENCIES.md](../SQLITE_DEPENDENCIES.md)** et
> **[XML_ENGINE.md](XML_ENGINE.md)**.

## 1. Architecture

```text
REST Flask                    TCP/IP
     \                          /
      +---- Auth / ACL / rôles-+
                    |
              Services XMLForge
                    |
        document XML canonique par base
             SOURCE DE VÉRITÉ
                    |
         validation XSD + validation métier
                    |
       projection SQLite physique par base
          moteur de requêtes interne
```

Le fichier XML est persistant et autoritaire. La projection SQLite d’une base est reproductible et peut être supprimée puis reconstruite à partir du XML. SQLAlchemy reste utilisé pour le **control plane** et le catalogue de compatibilité : utilisateurs, rôles, permissions, pointeurs de stockage, tables/colonnes/rows projetées, audit, historique, unlocks et credentials TCP.

Répertoires par défaut :

- XML : `backend/data/xml/<id>_<slug>.xml` ;
- projections : `backend/data/projections/<id>_<slug>.sqlite` ;
- control plane : `backend/xmlforge.db` en développement.

Les chemins peuvent être remplacés avec `XML_STORAGE_FOLDER` et `SQLITE_PROJECTION_FOLDER`.

## 2. Cycle de vie XML → SQLite

### Démarrage

`create_app()` exécute les migrations, puis `XmlEngineService.initialize_all()` :

1. charge chaque XML existant avec un parser durci (entités externes désactivées) ;
2. valide le document contre `app/static/xmlforge.xsd` ;
3. valide noms, types, références et structure ;
4. construit une nouvelle projection SQLite temporaire ;
5. applique les contraintes et toutes les rows ;
6. exécute `foreign_key_check` et `quick_check` ;
7. remplace atomiquement la projection ;
8. réaligne le catalogue SQLAlchemy sur le XML.

Si une ancienne base ne possède pas encore de XML, le premier démarrage V5 migre son catalogue et ses `TableRow` vers un document XML sans supprimer les anciennes données.

### Mutation

Toutes les mutations V5 passent par `XmlEngineService.mutate()` :

1. verrou thread + verrou fichier par base ;
2. lecture de la version XML courante ;
3. contrôle `expected_version`/`If-Match` lorsqu’il est fourni ;
4. mutation d’une copie en mémoire ;
5. validation ;
6. construction complète d’une projection SQLite temporaire ;
7. préparation de la projection catalogue SQLAlchemy sans commit ;
8. écriture atomique du XML, puis remplacement de la projection validée ;
9. commit du control plane ;
10. restauration des snapshots XML/SQLite et rollback SQLAlchemy si une erreur gérée survient.

Le XML est écrit avant la projection finale. En cas de crash brutal entre les deux remplacements, le démarrage suivant reconstruit SQLite depuis le XML.

## 3. Format XML canonique

```xml
<database name="crm" uuid="..." internal_id="1"
          scope="PERSONAL" owner_id="1" status="ACTIVE"
          version="12" generator="XMLForge">
  <table name="customers" uuid="..." internal_id="4"
         protected="false" status="ACTIVE">
    <columns>
      <column name="id" type="INTEGER" nullable="false"
              primary_key="true" auto_increment="true"/>
      <column name="company_id" type="INTEGER" nullable="false"
              foreign_key="true" references="companies.id"
              on_delete="RESTRICT"/>
      <column name="email" type="VARCHAR" length="255"
              nullable="false" unique="true" index="true"/>
      <column name="note" type="TEXT" nullable="true" default="none"/>
    </columns>
    <constraints>
      <unique name="uq_customer_company_email">
        <column name="company_id"/><column name="email"/>
      </unique>
    </constraints>
    <indexes>
      <index name="idx_customer_email" unique="false">
        <column name="email"/>
      </index>
    </indexes>
    <rows>
      <row uuid="..." internal_id="8">
        <cell column="id">1</cell>
        <cell column="email">admin@example.com</cell>
        <cell column="note" null="true"/>
      </row>
    </rows>
  </table>
</database>
```

Le XSD supporte `columns`, `constraints`, `indexes`, `rows`, `row`, `cell`, NULL explicite, PK/FK/UNIQUE, defaults, auto increment, index, protection et métadonnées. Les deux copies versionnées du XSD sont identiques : `xmlforge.xsd` et `app/static/xmlforge.xsd`.

Compatibilité d’import : racines `database`, `table`, `tables`, anciens `<column>` directs, aliases `primaryKey`, `foreignKey`, `autoIncrement` et `fileIdentifier`.

Types SQLite supportés : familles integer, text/varchar/char/json/date/time, real/float/double, decimal/numeric, bool et blob. Les valeurs sont converties avant insertion ; une incompatibilité annule l’opération.

## 4. Projection relationnelle SQLite

Chaque table XML active devient une vraie table SQLite. Une colonne interne `_xmlforge_row_uuid` relie les rows SQLite aux `<row uuid>` sans remplacer la PK métier.

Sont réellement appliqués par SQLite :

- PRIMARY KEY simple ou composite ;
- FOREIGN KEY simple ou composite ;
- UNIQUE simple ou composite ;
- NOT NULL ;
- DEFAULT ;
- INTEGER PRIMARY KEY AUTOINCREMENT ;
- INDEX et UNIQUE INDEX ;
- actions FK `NO ACTION`, `RESTRICT`, `SET NULL`, `SET DEFAULT`, `CASCADE`.

Une violation empêche le remplacement du XML et de la projection. Modifier/supprimer une colonne reconstruit la table à partir du document ; un rename déplace les cellules des rows et met à jour les références FK internes. Supprimer une table/colonne encore référencée est refusé.

## 5. Utilisateurs, rôles et JWT

Modèles : `Role`, `User`, `RevokedToken`.

Rôles seedés : `admin`, `user`. Le privilège ne dépend plus d’un email. Pendant la migration seulement, un ancien compte déjà existant `admin@example.com` reçoit le rôle admin. Un nouveau compte portant cet email reste `user`.

Bootstrap explicite :

```bash
flask --app run.py create-admin
```

JWT : expiration configurable, claim `token_version`, contrôle du compte actif et blocklist `jti`. Logout révoque le token courant. Reset de mot de passe, désactivation et réactivation incrémentent `token_version`, invalidant les tokens antérieurs. Login efface les unlocks de la session précédente.

## 6. Propriété, scopes et permissions

Une `Database` possède :

- `owner_id` ;
- `scope` = `PERSONAL` ou `COMMON` ;
- permissions explicites par utilisateur ;
- version/checksum/statut et chemins XML/SQLite.

`PERSONAL` n’est visible que par le propriétaire, un admin ou un utilisateur autorisé. `COMMON` décrit la nature de la base mais ne contourne pas les ACL : les membres reçoivent des permissions explicites.

Droits de base et de table :

- `can_read` ;
- `can_write` ;
- `can_ddl` ;
- `can_admin`.

Ordre d’autorisation : compte actif → rôle admin/propriétaire → ACL base → éventuelle ACL table → protection de table pour les écritures/DDL.

Les clés `key_identifier` et `file_identifier` ne sont plus sérialisées dans les réponses ordinaires. Un export XML complet avec métadonnées de protection requiert le droit admin sur la base/table.

## 7. Protection des tables

Une table conserve `protected` et `file_identifier` dans le XML. Un unlock est stocké par `(user_id, table_id)` avec expiration. Il ne modifie jamais la protection globale.

- A déverrouille : A peut écrire ; B reste bloqué.
- logout ou nouveau login : unlocks de l’utilisateur effacés ;
- expiration : unlock supprimé ;
- TCP : message `MSG_UNLOCK_TABLE`/`client.unlock_table()`.

Un utilisateur doit d’abord posséder la permission d’écriture ; connaître une clé n’accorde pas l’accès à une base.

## 8. CRUD et requêtes

Le CRUD structurel appelle les services `DatabaseService`, `TableService`, `ColumnService`. Le CRUD data appelle `QueryService` via `RowService`, REST ou TCP.

### Sous-ensemble SQL supporté

- `SELECT colonnes|* FROM table [WHERE ...] [ORDER BY ...] [LIMIT n] [OFFSET n]`
- `INSERT INTO table (colonnes) VALUES (littéraux)`
- `UPDATE table SET colonne=valeur [, ...] WHERE ...`
- `DELETE FROM table WHERE ...`

WHERE : parenthèses, `AND`, `OR`, `=`, `!=`, `<>`, `<`, `<=`, `>`, `>=`, `LIKE`, `IN`, `IS NULL`, `IS NOT NULL`.

UPDATE et DELETE sans WHERE sont refusés. Les identifiants sont validés et les valeurs sont paramétrées dans SQLite. Le parser est un tokenizer + parser récursif, pas une regex d’exécution libre.

**Non supporté actuellement :** SQL DDL via l’endpoint query, JOIN texte, GROUP BY, agrégats, sous-requêtes. Les relations sont néanmoins réellement appliquées par les FK SQLite. Les JOIN pourront être ajoutés au parser sans modifier le stockage.

REST rows ajoute `limit`, `offset`, `filters` JSON, `search`, `sort`, `order`.

## 9. REST

Toutes les routes historiques non TCP existent sans préfixe et sous `/api`. Le préfixe stable recommandé pour ce dépôt reste `/api`. TCP REST existe uniquement sous `/api/tcp`; les anciens aliases accidentels `/api/credentials` ont été supprimés.

Principaux endpoints :

### Auth/users

- `POST /register`, `POST /login`, `POST /logout`, `GET /me`
- admin : `GET/POST /users`, `GET/PUT/DELETE /users/<id>`
- `POST /users/<id>/reset-password`, `/toggle-active`

### Bases et ACL

- `GET/POST /databases`
- `GET/PUT/DELETE /databases/<id>`
- archive/restore/comment
- `GET/POST /databases/<id>/permissions`
- `DELETE /databases/<id>/permissions/<user_id>`
- `POST /tables/<id>/permissions`

### Tables/colonnes/rows

- `GET /tables/<database_id>`, `POST /tables`, `PUT/DELETE /tables/<id>`
- archive/restore/comment et unlock
- `GET /columns/<table_id>`, `POST /columns`, `PUT/DELETE /columns/<id>`
- archive/restore/comment
- `GET/POST /tables/<id>/rows`
- `PUT/DELETE /tables/<id>/rows/<row_id>`

### Query/sync/import/export

- `POST /databases/<id>/query`
- `POST /databases/<id>/sync-xml` et `/sync`
- `POST /tables/<id>/sync-xml` et `/sync`
- `POST /import/xml`, `/import/sql`, `/import/project`
- exports XML/SQL base/table/projet
- converters XML↔SQL

### Audit/TCP

- admin : `/history`, `/audit`, `/audit-logs`
- `/api/tcp/credentials`, regenerate/show-password, sessions, status

Les réponses suivent `{success,message,data}` ou `{success,message,errors}`. Les erreurs métier ont un code stable (`XML_INVALID`, `DATA_INVALID`, `CONSTRAINT_VIOLATION`, `SYNC_CONFLICT`, `FORBIDDEN`, etc.).

## 10. TCP/IP

Framing : `[type uint8][longueur uint32 réseau][JSON UTF-8]`.

Messages : AUTH, QUERY, RESPONSE, ERROR, PING/PONG, SELECT_DATABASE, UNLOCK_TABLE, CLOSE.

Le serveur :

- bind synchronisé et backlog 64 ;
- un thread par client ;
- limite buffer 8 MiB ;
- sessions UUID en mémoire avec timeout ;
- suppression à CLOSE/déconnexion/expiration ;
- association explicite user ID + base ID ;
- revalidation ACL à chaque requête ;
- SELECT/INSERT/UPDATE/DELETE réels via `QueryService` ;
- audit `TCP_QUERY` ;
- plusieurs clients simultanés.

L’auth utilise exclusivement `TcpCredential.tcp_username` et son hash bcrypt actif. Elle n’utilise plus le mot de passe principal. Le nom/ID d’une base n’est jamais une autorisation : seules les bases accessibles peuvent être sélectionnées, et un nom ambigu est refusé.

Client Python : `connect`, `execute`, `select`, `insert`, `update`, `delete`, `select_database`, `unlock_table`, `ping`, `disconnect` propre.

Limite sécurité : le protocole applicatif ne chiffre pas lui-même le transport. En production, exposer le port uniquement derrière TLS/VPN/SSH ou ajouter un socket TLS configuré ; ne jamais l’exposer directement sur Internet.

## 11. Imports, exports et converters

Un import XML valide d’abord le document, crée une base propriétaire, écrit le XML puis construit SQLite. En cas d’échec, la base incomplète et ses artefacts sont compensés.

L’import SQL passe par SQL → XML canonique puis le même pipeline ; les INSERT sont désormais conservés. Le parser SQL de conversion historique reste destiné aux dumps simples CREATE TABLE/INSERT et non à tout le dialecte MySQL.

Les exports XML lisent le fichier persistant. Les exports SQL sont générés depuis ce XML. FK, indexes, contraintes composites et NULL sont pris en charge par le format canonique ; les limitations du parser SQL entrant sont documentées.

## 12. Concurrence et conflits

- verrou réentrant par chemin dans le processus ;
- `flock` inter-processus lorsque disponible ;
- projection SQLite persistée en mode WAL avec `synchronous=FULL` ;
- `busy_timeout` configurable pour chaque connexion runtime ;
- retries exponentiels limités sur les seules erreurs `SQLITE_BUSY/locked` ;
- `BEGIN IMMEDIATE` pendant la construction SQLite ;
- version entière du document ;
- `expected_version` ou `If-Match` ;
- sync complète utilisant la version du XML entrant si l’en-tête est absent ;
- sync de table exigeant explicitement une version ;
- écritures par petits changements appliquées à la dernière version sous verrou ;
- fermeture des connexions runtime et `dispose()` des engines de projection enregistrés avant swap ;
- checkpoint WAL et nettoyage `-wal/-shm` ;
- écriture temporaire + fsync + `os.replace` ;
- sous Windows : cinq retries WinError 5 à 50 ms et fallback copie+fsync+suppression+promotion ;
- rollback/restauration sur erreur.

## 13. Migrations

`app/schema_migrations.py` fournit la migration V5 idempotente et la table `schema_migrations`. Elle est non destructive : rôles, ACL, ownership/scope, chemins/version/checksum/sync, references/index, token version. Toutes les anciennes bases sont `PERSONAL` et leur owner initial est leur creator.

Voir `migrations/README.md`.

## 14. Tests

Configuration : `pytest.ini`, tests sous `tests/` uniquement.

Couverture fonctionnelle :

- login, mauvais mot de passe, inactif, token expiré, logout/révocation ;
- isolation personal, partage et droits read/write/DDL ;
- protection et unlock individuel/reconnexion ;
- CRUD rows, pagination, filtres, tri, UNIQUE, types ;
- XML invalide, conflit de version, reconstruction XML → catalogue/SQLite ;
- PK/FK et round-trip de référence ;
- TCP auth, CRUD réel, refus base non autorisée, multi-clients, timeout.

Exécution :

```bash
pytest -q
```

## 15. Cartographie des nouveaux modules

- `app/xml_engine/document.py` : modèle canonique, XSD, parser/serializer.
- `app/xml_engine/projection.py` : DDL/DML SQLite et contraintes.
- `app/xml_engine/storage.py` : locks, snapshots, atomic writes.
- `app/xml_engine/service.py` : orchestration et catalogue de compatibilité.
- `app/query/sql_parser.py` : sous-ensemble SQL.
- `app/query/sqlite_runtime.py` : WAL runtime, busy timeout et retries lock/busy.
- `app/query/service.py` : moteur REST/TCP.
- `app/services/permission_service.py` / `access_service.py` : autorisation centrale et façade AccessService.
- `app/models/role.py`, `database_permission.py`, `table_permission.py`, `revoked_token.py` : sécurité persistante.
- `app/routes/permissions.py`, `query.py` : API ACL et requêtes.
- `app/schema_migrations.py` : migration V5.

Les anciens services/routes restent en place et ont été adaptés plutôt que remplacés arbitrairement.
