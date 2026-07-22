# BACKEND DOCUMENTATION – XMLForge Flask V2

> Documentation officielle développeur – Backend Flask professionnel, modulaire, production-ready  
> Version 2.0.0 – Compatible frontend React V2 (JWT, SocketIO, metadata enrichies)

---

## 1. Présentation

### Rôle du backend
Backend REST API pour XMLForge : gestion d'utilisateurs, bases logiques XML, tables, colonnes avec métadonnées riches, protection par clé, commentaires, archivage, historique détaillé, audit indépendant, import/export XML/SQL, conversion XML↔SQL, création réelle MySQL, temps réel SocketIO.

### Pourquoi Flask ?
- Léger, explicite, contrôle total (vs Django trop opinioné)
- Blueprints pour modularité (1 fichier par domaine)
- Facile intégration Flask-JWT, Bcrypt, CORS, SocketIO
- Compatible avec stack demandée (Flask, SQLAlchemy, etc.)

### Pourquoi SQLAlchemy ?
- ORM mature, relations, cascades, migrations légères
- Support SQLite dev + MySQL prod via même code (`DATABASE_URL`)
- `db.relationship` pour `Database -> Table -> Column` + `User`
- `UniqueConstraint` pour `database_id+name`, `table_id+name`

### Pourquoi JWT ?
- Stateless, scalable, pas de session serveur
- `Flask-JWT-Extended` gère `@jwt_required()`, `get_jwt_identity()`, expiration 24h
- Stockage côté client `localStorage`, envoi `Authorization: Bearer`

### Pourquoi cette architecture ?
- **Separation of concerns** : Routes (validation + appel service) / Services (logique métier + history + audit + socket) / Models (ORM) / Converters (pur Python sans Flask) / Utils (validators, responses)
- Facilement extensible (ajouter `POST /databases/<id>/archive` sans toucher routes existantes)
- Testable : Services testables sans Flask, Converters testables en CLI
- Production-ready : .env, CORS, max content 16MB, logs, error handling cohérent

### Architecture générale

```
React (Vite :5173)
   ↓ fetch + JWT + X-Database-Key (sessionStorage)
Flask (app.py / run.py, :5000, SocketIO)
   ↓ Blueprints (/register, /databases, /tables, etc. + /api/* clones)
   ↓ Marshmallow validation (validators.py) + JWT @jwt_required()
Services (database_service, table_service, column_service, etc.)
   → HistoryService.log() (IP, before/after, uuid)
   → AuditService.log() (action, IP, meta)
   → socket_events.emit_*() (SocketIO)
   → Models (SQLAlchemy)
     → SQLite (dev xmlforge.db) ou MySQL (prod via DATABASE_URL)
   ↓
Converters (xml_to_sql.py, sql_to_xml.py) purs, lxml
   ↓
MySQL réel via mysql-connector-python (POST /database/create)
```

---

## 2. Arborescence complète

```
backend/
├── app/
│   ├── __init__.py (create_app factory, avec _migrate_v2 ALTER TABLE)
│   ├── config.py (Config, TestingConfig, ProductionConfig, .env)
│   ├── extensions.py (db, jwt, bcrypt, cors, socketio)
│   ├── app.py (wrapper flask_app + socketio.run)
│   ├── socket_events.py (emit_event, emit_new_database, new_table, new_column, modification, suppression, import_xml, export_sql)
│   ├── auth/ (authentification helpers)
│   │   ├── __init__.py (export protected_table_required)
│   │   └── decorators.py (protected_table_required decorator, vérifie X-Database-Key)
│   ├── database/ (__init__.py placeholder, db via extensions)
│   ├── models/ (SQLAlchemy ORM)
│   │   ├── __init__.py (export User, Database, Table, Column, History, AuditLog)
│   │   ├── user.py (id, full_name, email unique, password_hash, created_at, relations databases_created, tables_created, columns_created)
│   │   ├── database.py (id, uuid UUID4, name, description, creator_id, created_at, updated_at, last_modified_by_id/name, comment, status ACTIVE/ARCHIVED, key_identifier XML-XXXX-..., tables relationship, last_modifier relationship)
│   │   ├── table.py (id, uuid, name, description, database_id, creator_id, created_at, updated_at, last_modified_by_id/name, comment, status, is_protected, columns relationship)
│   │   ├── column.py (id, uuid, name, type, length, nullable, pk, fk, unique, ai, default, creator_id, created_at, updated_at, last_modified_by_id/name, comment, status, table_id)
│   │   ├── history.py (id, uuid, user_id, user_name, action_type, element_type, element_name, description, ip_address, before_data JSON, after_data JSON, database_id, table_id, created_at)
│   │   └── audit_log.py (id, uuid, user_id, user_name, ip_address, action, element_type, element_name, description, meta_data JSON, timestamp)
│   ├── routes/ (Blueprints, validation, appel services, 0 logique métier)
│   │   ├── __init__.py (_clone_blueprint pour support /api/* + /*, register_routes)
│   │   ├── auth.py (POST /register, /login, GET /me, POST /logout + audit)
│   │   ├── databases.py (GET /databases, POST, GET/PUT/DELETE /databases/<id> + include_archived, comment, archive/restore)
│   │   ├── tables.py (GET /tables/<database_id>, POST /tables, PUT/DELETE /tables/<id> + protection + archived)
│   │   ├── columns.py (GET /columns/<table_id>, POST/PUT/DELETE + protection)
│   │   ├── imports.py (POST /import/xml + /import/sql multipart/form-data ou JSON)
│   │   ├── exports.py (GET /export/xml/<id>, GET /export/sql/<id> ?download=true → blob)
│   │   ├── converters.py (POST /convert/xml-to-sql, /convert/sql-to-xml)
│   │   ├── history.py (GET /history?limit&database_id)
│   │   ├── audit.py (GET /audit-logs, GET /audit alias)
│   │   ├── unlock.py (POST /unlock-table {table_id, key_identifier})
│   │   ├── database_create.py (POST /database/create {database_id, target_database_name?} → MySQL réel)
│   │   └── metadata.py (V2 commentaires + archive/restore dédiés: GET/PUT /databases|tables|columns/<id>/comment, POST .../archive|restore)
│   ├── services/ (toute logique métier)
│   │   ├── __init__.py (export tous services)
│   │   ├── auth_service.py (register: check email unique + bcrypt hash, login: check hash + create_access_token + audit CONNEXION/ERREUR_CONNEXION)
│   │   ├── database_service.py (get_all, get_by_id, create: génère key XML-XXXX, uuid, comment, status ACTIVE, last_modified_by, commit, History + Audit CREATION_BASE + emit_new_database, update: check archived, before/after, last_modified_by, commit, History MODIFICATION_BASE + Audit, delete: check archived, History + Audit + emit_suppression, update_comment, archive, restore)
│   │   ├── table_service.py (get_by_database, get_by_id, _check_protection (vérifie database.key_identifier), _check_archived, create, update, delete, update_comment, archive, restore, unlock + History + Audit + socket)
│   │   ├── column_service.py (get_by_table, get_by_id, create, update, delete, update_comment, archive, restore + checks protection + archived + parent table archived + History + Audit + socket)
│   │   ├── history_service.py (log(user_id, user_name, action_type, element_type, element_name, description, database_id, table_id, ip_address, before, after) → uuid + json dumps before/after + commit, get_all(limit, database_id))
│   │   ├── audit_service.py (log(user_id, user_name, ip, action, element_type, element_name, description, meta) → uuid + json meta + commit, get_all(limit))
│   │   ├── import_service.py (import_xml/xml_content, database_name, creator_id/name, description, ip, comment → parse_xml via converters, crée Database uuid/key/comment/status/last_modified_by, puis Tables + Columns avec uuid/comment/status/last_modified_by, commit, History + Audit IMPORT_XML/IMPORT_SQL + emit_import_xml)
│   │   └── export_service.py (export_database_to_xml: build lxml database/table/column avec uuid, comment, status, protected → tostring pretty, export_database_to_sql: export_xml puis convert_xml_to_sql + Audit EXPORT_XML/SQL + emit_export)
│   ├── converters/ (purs, sans Flask, réutilisables CLI)
│   │   ├── __init__.py (export convert_xml_to_sql, convert_sql_to_xml, parse_xml, parse_sql)
│   │   ├── xml_to_sql.py (parse_xml: lxml fromstring, trouve <database>/<table>/<tables>, _parse_column_element: parse name,type,length,nullable, pk, fk, unique, ai, default, references, _column_to_sql: type(length) + NOT NULL + AUTO_INCREMENT + UNIQUE + DEFAULT, convert_xml_to_sql: tables → CREATE DATABASE IF NOT EXISTS + USE + CREATE TABLE avec col defs + PRIMARY KEY + FOREIGN KEY si references)
│   │   └── sql_to_xml.py (parse_sql: _strip_comments -- et /* */, _split_sql_statements, _extract_table_name_and_body (compte parenthèses), _split_columns (split comma hors parenthèses et hors quotes), _parse_column_def (regex name type(length) + NOT NULL + AUTO_INCREMENT + UNIQUE + DEFAULT + PRIMARY KEY inline, constraints PRIMARY KEY (cols) et FOREIGN KEY (col) REFERENCES table(col) → set pk/fk + references), convert_sql_to_xml: build lxml database/table/column avec attrs)
│   └── utils/
│       ├── __init__.py
│       ├── helpers.py (generate_key_identifier(): secrets.token_hex(2).upper() x3 → XML-XXXX-XXXX-XXXX, slugify, now_utc(), is_valid_email())
│       ├── responses.py (success_response(data,message,status), error_response(message,status,errors) → JSON cohérent {success,message,data/errors})
│       └── validators.py (Marshmallow Schemas avec Meta unknown=INCLUDE pour permettre key_identifier additionnel: RegisterSchema, LoginSchema, DatabaseCreateSchema/UpdateSchema, TableCreate/Update, ColumnCreate/Update, UnlockTableSchema, ConvertXmlToSqlSchema, ConvertSqlToXmlSchema)
├── uploads/ (.gitkeep, stockage fichiers import)
├── exports/ (.gitkeep)
├── app/ (dossier app/uploads, app/exports pour compat spec)
│   ├── uploads/.gitkeep
│   └── exports/.gitkeep
├── run.py (entry point Flask + SocketIO, socketio.run)
├── app.py (ancien entry, maintenant wrapper avec importlib pour éviter conflit nom)
├── config.py (compat root importe depuis app/config.py)
├── requirements.txt (Flask, SQLAlchemy, JWT, Bcrypt, CORS, SocketIO, dotenv, lxml, mysql-connector, marshmallow, eventlet)
├── .env.example (SECRET_KEY, JWT_SECRET_KEY, DATABASE_URL, MYSQL_HOST/PORT/USER/PASSWORD, CORS_ORIGINS)
├── API_DOCUMENTATION.md (doc complète routes)
├── postman_collection.json (collection Postman V2 avec variables baseUrl, token, db_key)
└── README.md (V1 + V2)
```

### Pour chaque fichier Python – rôle détaillé

**`app/__init__.py`**
- Rôle: Factory `create_app(config_class)` qui initialise Flask, extensions, blueprints, SocketIO, crée dossiers uploads/exports, appelle `_migrate_v2()` pour ALTER TABLE ADD COLUMN si colonnes V2 manquent (SQLite dev), définit `/health` et `/` listant endpoints et features V2.
- Pourquoi existe: Séparation création app vs run, permet TestingConfig pour tests, évite import circulaire.
- Qui l'appelle: `run.py`, `app/app.py`, tests `from app import create_app`.
- Retourne: Flask app instance
- Classes: Aucune, fonctions: `create_app()`, `_migrate_v2(app)` (inspecteur SQLAlchemy, ALTER TABLE si colonne manquante)
- Imports importants:
  - `Flask` : framework web
  - `Config` : config depuis .env
  - `db,jwt,bcrypt,cors,socketio` : extensions centralisées
  - `register_routes` : enregistre blueprints
  - `os` : makedirs uploads/exports

**`app/config.py`**
- Rôle: Config centralisée avec .env, SQLite par défaut, MySQL si DATABASE_URL, JWT expires, MySQL host/port/user/pass, CORS origins, upload folder 16MB.
- Pourquoi: 12-factor, dev vs prod, TestingConfig avec `:memory:`
- Qui l'appelle: `create_app`, `app.py`, `config.py` root
- Classes: `Config`, `TestingConfig`, `ProductionConfig`

**`app/extensions.py`**
- Rôle: Centralise `db = SQLAlchemy()`, `jwt`, `bcrypt`, `cors`, `socketio` pour éviter imports circulaires
- Pourquoi: Si chaque module fait `SQLAlchemy()` séparé, deux instances différentes → erreurs
- Qui l'appelle: Tous les models, routes, app factory

**`app/socket_events.py`**
- Rôle: Helpers émission WebSocket temps réel, sans modifier REST
- Pourquoi: Préparer collaboration, frontend peut écouter sans polling
- Fonctions: `emit_event(event_name,payload)` try/except ne casse pas requête si socketio non init, `emit_new_database()`, `new_table`, `new_column`, `modification`, `suppression`, `import_xml`, `export_sql`, `export_xml` → tous appellent `emit_event` + `xmlforge_event` générique
- Imports: `current_app` (pour config), `socketio` from extensions (dans fonction pour éviter circulaire)

**`app/auth/decorators.py`**
- Rôle: Décorateur `protected_table_required` vérifie table protégée + clé, exemple d'extension auth
- Pourquoi: Montre comment faire décorateur custom, même si logique déjà dans services
- Utilise: `Table`, `Database` models, `request` pour header `X-Database-Key`

**`app/models/user.py`**
- Rôle: Table `users` : id PK, full_name, email unique index, password_hash, created_at, relations `databases_created` (FK creator_id), `tables_created`, `columns_created` avec `foreign_keys` explicites pour éviter ambiguïté avec last_modified_by_id
- Pourquoi: Authentification, creator tracking
- Qui l'appelle: `auth_service`, `User.query`
- Méthode: `to_dict()` sans password_hash

**`app/models/database.py` V2**
- Rôle: Base logique XMLForge
- Champs V1: id, name, description, creator_id, created_at, updated_at, key_identifier
- Champs V2: uuid UUID4 unique index, comment Text, status ACTIVE/ARCHIVED default ACTIVE, last_modified_by_id FK nullable, last_modified_by_name String
- Relations: `tables` cascade delete, `last_modifier` FK last_modified_by_id
- Méthodes: `to_dict(include_key=False)` retourne uuid, comment, status, last_modified_by, tables_count + key si include_key True, `is_archived()` helper
- Pourquoi: Métadonnées enrichies demandées, UUID pour identification stable hors id auto-inc, comment libre, état pour soft delete, last user pour UI "Modifié par Nyx"

**`app/models/table.py` V2**
- Similaire database + is_protected bool + columns relationship
- UniqueConstraint database_id+name
- Même V2 fields uuid, comment, status, last_modified_by

**`app/models/column.py` V2**
- Champs V1: name, type, length, nullable, pk, fk, unique, ai, default, creator_id, table_id, created_at
- V2: uuid, comment, status, updated_at (ajouté, manquait), last_modified_by_id/name
- UniqueConstraint table_id+name

**`app/models/history.py` V2**
- Champs V1: user_id, user_name, action_type, element_type, element_name, description, database_id, table_id, created_at
- V2: uuid, ip_address, before_data Text (JSON), after_data Text, date alias
- Pourquoi: Historique détaillé avec IP + before/after pour diff, UUID stable

**`app/models/audit_log.py` (nouveau V2)**
- Rôle: Audit indépendant historique métier
- Champs: id, uuid, user_id nullable (pour erreurs avant auth), user_name, ip_address, action (CONNEXION, DECONNEXION, CREATION_BASE, etc.), element_type, element_name, description, meta_data JSON Text, timestamp index
- Pourquoi: Séparer audit technique (qui s'est connecté, a importé, a échoué) de historique métier (qui a créé table client)

**`app/routes/__init__.py`**
- Rôle: Enregistre tous les blueprints avec double préfixe: sans préfixe (spec exacte POST /register) + avec /api (compat frontend React qui appelle /api/*). `_clone_blueprint()` copie deferred_functions pour éviter collision nom.
- Pourquoi: Respect spec + compat frontend sans dupliquer code routes

**`app/routes/auth.py`**
- Rôle: `POST /register` (RegisterSchema validation → auth_service.register → 201), `POST /login` (LoginSchema → auth_service.login → token), `GET /me` @jwt_required, `POST /logout` → Audit DECONNEXION
- Imports: `Blueprint`, `request`, `jwt_required`, `get_jwt_identity`, `RegisterSchema/LoginSchema`, `success_response/error_response`, `AuthService`, `AuditService`, `ValidationError`
- Pourquoi Blueprint: modularité, préfixe possible

**`app/routes/databases.py`**
- Routes: `GET /databases?include_archived`, `POST /databases`, `GET /databases/<id>`, `PUT /databases/<id>`, `DELETE /databases/<id>` + V2 comment/archive/restore via metadata blueprint mais aussi ici
- Logique: JWT, validation Marshmallow, appel DatabaseService, gestion IP via `get_ip()` helper (remote_addr / X-Forwarded-For)
- Pourquoi séparé: 1 fichier = 1 domaine

**`app/routes/tables.py`, `columns.py`, `imports.py`, `exports.py`, `converters.py`, `history.py`, `unlock.py`, `database_create.py`, `metadata.py`, `audit.py`**
- Même pattern: Blueprint, JWT, validation, appel service, IP, `X-Database-Key` handling, responses cohérentes, status 403 si protégée sans clé, 400 si archivée, 404 introuvable, 500 erreur

**`app/routes/metadata.py` (V2 nouveau)**
- Rôle: Routes dédiées commentaires et archive/restore pour base/table/colonne
- Routes: `GET/PUT /databases/<id>/comment`, `GET/PUT /tables/<id>/comment`, `GET/PUT /columns/<id>/comment`, `POST /databases/<id>/archive|restore`, `POST /tables/<id>/archive|restore`, `POST /columns/<id>/archive|restore`
- Pourquoi séparé: Spec demande "Créer les routes nécessaires. GET commentaires PUT commentaire + POST archive/restore" – regroupé ici pour clarté

**`app/services/auth_service.py`**
- Rôle: Logique auth sans Flask request (sauf audit IP passé en param)
- Fonctions: `register(full_name,email,password,ip)`: check email unique → Bcrypt hash → User → db commit → Audit INSCRIPTION ; `login(email,password,ip)`: find user → check hash → create_access_token → Audit CONNEXION / ERREUR_CONNEXION ; `get_user_by_id`
- Imports: `db, bcrypt`, `User`, `create_access_token`, `now_utc`, `AuditService`
- Pourquoi Service: Routes ne contiennent pas logique métier

**`app/services/database_service.py` V2**
- Rôle: CRUD bases + comment + archive/restore + history V2 + audit + socket
- Fonctions: `get_all(include_archived)`, `get_by_id`, `get_by_key`, `create(name,description,creator_id,creator_name,comment,ip)`: génère key XML-XXXX via `generate_key_identifier()`, uuid, status ACTIVE, last_modified_by, commit, History log avec IP, before None, after full dict, Audit CREATION_BASE, emit_new_database
- `update`, `delete`, `update_comment`, `archive`, `restore`: check is_archived() → block, before/after capture, last_modified_by update, History + Audit + emit_modification/suppression
- Imports: `db`, `Database`, `generate_key_identifier`, `now_utc`, `HistoryService`, `AuditService`, `emit_*`

**`app/services/table_service.py` V2**
- Similaire + `_check_protection(table, key)` vérifie `database.key_identifier == key` si `is_protected`, `_check_archived(table)`
- `create`, `update`, `delete`, `update_comment`, `archive`, `restore`, `unlock`
- Tous log History avec IP + before/after + table_id + database_id, Audit + socket

**`app/services/column_service.py` V2**
- Même + vérifie protection table parente + archived table parente + archived colonne elle-même
- `create`, `update`, `delete`, `update_comment`, `archive`, `restore`

**`app/services/history_service.py` V2**
- `log(user_id, user_name, action_type, element_type, element_name, description, database_id, table_id, ip_address, before, after)`: before/after dict → json.dumps, uuid, commit, try/except rollback
- `get_all(limit, database_id)` order desc

**`app/services/audit_service.py` (nouveau)**
- `log(user_id, user_name, ip_address, action, element_type, element_name, description, meta)`: meta dict → json, uuid, commit
- `get_all(limit)` order desc

**`app/services/import_service.py` V2**
- `import_xml(xml_content, database_name, creator_id, creator_name, description, ip_address, comment)`: `parse_xml()` via converters, génère Database uuid/key/comment/status/last_modified_by, flush pour id, loop tables → Table uuid/comment/status/last_modified_by, loop columns → Column uuid/comment/status/last_modified_by, commit, History + Audit IMPORT_XML + emit_import_xml
- `import_sql` idem via `parse_sql`

**`app/services/export_service.py` V2**
- `export_database_to_xml(database_id, user_id, user_name, ip_address)`: fetch Database + Tables (même archivées exportables), build lxml `database` avec attrs name, uuid, description, comment, status, `table` avec uuid, comment, status, protected, `column` avec uuid, comment, status + autres attrs, tostring pretty + `<?xml...`, Audit EXPORT_XML + emit_export_xml
- `export_database_to_sql(database_id, ...)`: appelle export_xml puis `convert_xml_to_sql()` + Audit EXPORT_SQL + emit_export_sql

**`app/converters/xml_to_sql.py`**
- Pur Python, dépendance `lxml` seulement, pas Flask
- `_parse_column_element(col_elem)`: parse attrs `name`, `type`, `length`, `nullable` (bool), `primaryKey|primary_key`, `foreignKey`, `unique`, `autoIncrement`, `default`, `references`
- `_column_to_sql(col)`: type(length) + NOT NULL + AUTO_INCREMENT + UNIQUE + DEFAULT 'val'
- `parse_xml(xml_content)`: fromstring, trouve tables via `<database>`, `<table>`, `<tables>`, `//table`, pour chaque table parse columns → list tables dict
- `convert_xml_to_sql(xml, database_name=None)`: parse → pour chaque table, col_defs + pk_cols + fk_defs (si references contient `table.col` → FOREIGN KEY), `CREATE TABLE` statement, optional `CREATE DATABASE` + `USE` si database_name fourni, join `\n\n`

**`app/converters/sql_to_xml.py`**
- Pur, `lxml` + `re`
- `_strip_comments(sql)`: enlève `--.*` et `/* */`
- `_split_sql_statements(sql)`: split `;`
- `_extract_table_name_and_body(create_stmt)`: regex `CREATE TABLE` + comptage parenthèses pour extraire body entre (...)
- `_split_columns(body)`: split par `,` hors parenthèses et hors quotes
- `_parse_column_def(col_def)`: si commence par PRIMARY KEY/FOREIGN KEY/UNIQUE KEY/KEY/CONSTRAINT → retourne `__constraint__`, sinon regex `` `?(\w+)`? \s+ ([A-Z]+)(?:\(([^)]+)\))? \s* (.*)`` → name, type, length, rest (NOT NULL, AUTO_INCREMENT, UNIQUE, DEFAULT, PRIMARY KEY inline)
- `parse_sql(sql)`: pour chaque CREATE TABLE, body → split columns → parse colonnes + constraints → pour PK constraint `PRIMARY KEY (id, ...)`, set primary_key True pour ces colonnes ; FK `FOREIGN KEY (col) REFERENCES table(col)` → set foreign_key True + references
- `convert_sql_to_xml(sql, database_name)`: build lxml `database` → `table` → `column` avec attrs

**`app/utils/helpers.py`**
- `generate_key_identifier()`: `secrets.token_hex(2).upper()` x3 → `XML-XXXX-XXXX-XXXX`, `secrets` cryptographiquement sûr
- `slugify()`, `now_utc()`, `is_valid_email()`
- Pourquoi `secrets` : sécurité clé, pas `random`

**`app/utils/responses.py`**
- `success_response(data,message,status)` → `{success:true, message, data}` + jsonify
- `error_response(message,status,errors)` → `{success:false, message, errors}`
- Pourquoi : JSON cohérent partout

**`app/utils/validators.py`**
- Marshmallow Schemas avec `class Meta: unknown = INCLUDE` pour permettre `key_identifier` additionnel sans erreur "Unknown field"
- `RegisterSchema`, `LoginSchema`, `DatabaseCreateSchema`, `TableCreateSchema`, `ColumnCreateSchema`, etc. + `key_identifier` optional pour routes protégées
- Pourquoi Marshmallow : validation déclarative, messages d'erreur propres, séparation validation/logique

**`app/extensions.py`**
- Centralise `db = SQLAlchemy()`, `jwt`, `bcrypt`, `cors`, `socketio` → évite import circulaire

**`app/config.py`**
- `Config` : SECRET_KEY, SQLALCHEMY_DATABASE_URI (SQLite par défaut `xmlforge.db` sinon `DATABASE_URL` env), JWT_SECRET_KEY, JWT_EXPIRES 24h, MYSQL_HOST/PORT/USER/PASSWORD, UPLOAD_FOLDER 16MB, CORS_ORIGINS split
- `TestingConfig` : `:memory:` SQLite, JWT secret test
- `ProductionConfig`
- Pourquoi `python-dotenv` : charge `.env`

**`app.py` / `run.py`**
- Entry point : `from app import create_app; app = create_app(Config); socketio.run(app, ...)`
- Pourquoi SocketIO run au lieu de Flask run : support WebSocket
- Conflit nom `app.py` vs `app/` package résolu en renommant entry en `run.py` + wrapper `app/app.py` avec `flask_app`

---

## 3. Cycle complet d'une requête

### Exemple 1 : POST /login

```
Client React (Login.jsx)
  ↓ email, password state + submit
  → authService.login({email,password})
    → apiClient.post('/login', body, withAuth=false)
      → fetch http://localhost:5000/login, Content-Type json, pas de Authorization
        ↓
Flask route POST /login (app/routes/auth.py)
  → request.get_json()
  → LoginSchema().load() validation Marshmallow (email format, password présent) → 400 si échec
  → AuthService.login(email,password,ip=remote_addr)
    → User.query.filter_by(email.lower()).first()
    → bcrypt.check_password_hash() → si faux → AuditService.log(ERREUR_CONNEXION, ip) + return 401
    → create_access_token(identity=str(user.id)) via Flask-JWT-Extended
    → AuditService.log(CONNEXION, user_id, ip, meta user_id)
    → return {user, token}
  → success_response({user: user.to_dict(), access_token: token}, "Connexion réussie") → JSON 200
        ↓
React: authService.login then() → localStorage.setItem('xmlforge_token', token) + user + socketService.connect() → navigate('/dashboard') + toast success
  ↓
Si 401 → api.js throw Error → Login catch → toast error
```

### Exemple 2 : Création d'une base POST /databases

```
Dashboard.jsx → Modal Nouvelle base → form name, description, comment state + Créer click
  → databaseService.create({name, description, comment})
    → apiClient.post('/databases', body) → headers Authorization Bearer token + Content-Type json
      ↓
Flask POST /databases @jwt_required() → get_jwt_identity() → user_id → AuthService.get_user_by_id
  → DatabaseCreateSchema validation
  → DatabaseService.create(name, description, creator_id, creator_name, comment, ip)
    → génère key_identifier via generate_key_identifier() → secrets.token_hex(2) x3 → XML-XXXX
    → boucle 5x vérif unicité key via query filter_by
    → Database(uuid=uuid4(), name, description, creator_id, key_identifier, comment, status ACTIVE, last_modified_by=creator, created_at=now_utc(), updated_at=now_utc())
    → db.session.add + commit
    → HistoryService.log(user_id, user_name, a créé, base, name, description, database_id, ip, before None, after to_dict(include_key))
    → AuditService.log(CREATION_BASE, base, name, meta database_id, key)
    → emit_new_database(to_dict(include_key), by=user_name) → socketio.emit('new_database') + 'xmlforge_event'
  → success_response 201 avec to_dict(include_key=True) pour créateur
      ↓
React: setDatabases([data, ...prev]) → nouvelle card apparaît + toast + socket event déjà émis → autres clients reçoivent new_database → toast + fetchDatabases()
```

### Exemple 3 : Création d'une table protégée POST /tables

```
Workspace → Modal Nouvelle table + coche Protégée + comment
  → tableService.create({name, description, database_id, is_protected:true, comment})
    → POST /tables body
      ↓
Flask POST /tables @jwt_required()
  → TableCreateSchema validation
  → TableService.create(): check base existe, check base pas archivée (is_archived), check table name unique dans base, crée Table uuid, comment, status ACTIVE, last_modified_by, commit, update database updated_at + last_modified_by, History + Audit CREATION_TABLE + emit_new_table
  → 201 table dict (uuid, comment, status, is_protected, columns_count)
```

### Exemple 4 : Import XML POST /import/xml

```
Dashboard → dropzone dragOver → onDrop file lib.xml → importService.importXml(file)
  → FormData file + database_name + description + comment → apiClient.post('/import/xml', formData) isFormData=true → pas Content-Type json, header Authorization Bearer
    ↓
Flask POST /import/xml @jwt_required()
  → request.files['file'].read().decode('utf-8') ou JSON xml field
  → ImportService.import_xml(xml_content, database_name, creator_id, creator_name, description, ip, comment)
    → parse_xml() via converters (lxml)
    → crée Database uuid/key/comment/status/last_modified_by + flush pour id
    → loop tables_data: Table uuid/comment/status + flush, loop columns: Column uuid/comment/status/last_modified_by
    → commit
    → History a importé base avec tables/columns count, ip, before None, after counts
    → Audit IMPORT_XML + emit_import_xml
  → 201 database dict
    ↓
React: fetchDatabases() → nouvelle base apparaît + toast + socket
```

### Exemple 5 : Conversion XML→SQL POST /convert/xml-to-sql

```
Workspace right panel → MonacoEditor XML Source value xmlDraft state onChange → user édite XML → Clique bouton "↓ Convertir XML → SQL"
  → converterService.xmlToSql(xmlDraft, database.name)
    → apiClient.post('/convert/xml-to-sql', {xml, database_name})
      ↓
Flask POST /convert/xml-to-sql @jwt_required()
  → ConvertXmlToSqlSchema validation (xml requis)
  → convert_xml_to_sql(xml, database_name) converter pur lxml → parse_xml → _column_to_sql → CREATE TABLE statements → join "\n\n"
  → Audit CONVERSION_XML + meta
  → success_response {sql}
      ↓
React: setSqlGenerated(res.sql) → MonacoEditor SQL (readonly) affiche SQL instantanément
```

### Exemple 6 : Export SQL GET /export/sql/<id>?download=true

```
Workspace titlebar → Export SQL button
  → exportService.exportSql(id, {download:true})
    → fetch http://localhost:5000/export/sql/1?download=true headers Authorization Bearer (pas via apiClient json, mais fetch blob)
      ↓
Flask GET /export/sql/<id> @jwt_required()
  → ExportService.export_database_to_sql(id, user_id, user_name, ip)
    → export_database_to_xml() build lxml avec uuid, comment, status, protected + columns
    → convert_xml_to_sql(xml, database.name)
    → Audit EXPORT_SQL + emit_export_sql
  → Si ?download=true → Response mimetype application/sql + Content-Disposition attachment
  → Sinon JSON {sql}
      ↓
React: si download → downloadBlob(blob, database_1.sql) → <a download> click → toast Export SQL téléchargé
```

### Exemple 7 : Déverrouillage table POST /unlock-table

```
Workspace → user clique Modifier sur table is_protected=true sans clé en sessionStorage
  → requireKeyIfProtected(table) → dbKey null → setShowUnlock(table) → Modal "🔒 Table protégée"
  → user entre clé XML-9F4A-... → Déverrouiller
    → tableService.unlock(tableId, key) → POST /unlock-table {table_id, key_identifier}
      ↓
Flask POST /unlock-table @jwt_required()
  → UnlockTableSchema validation
  → TableService.unlock() → Table.query.get → si !is_protected → True, sinon Database.query.get(table.database_id) → compare database.key_identifier == key → True/False + message
  → Audit DEVERROUILLAGE_TABLE ou ERREUR_DEVERROUILLAGE
  → 200 {unlocked:true} ou 403
      ↓
React: si 200 → apiClient.setDbKey(key) → sessionStorage setItem + DatabaseContext saveKey(key) → close modal + retry action originale
  → si 403 → toast Clé invalide
```

### Exemple 8 : Historique GET /history

```
HistoryPage.jsx mount → useEffect fetchHistory()
  → historyService.list(200, databaseFilter)
    → apiClient.get('/history?limit=200&database_id=1')
      ↓
Flask GET /history @jwt_required() → limit = min(int(limit),500) → HistoryService.get_all(limit, database_id) → query order_by created_at desc → limit
  → success_response [History.to_dict() avec uuid, ip_address, before (JSON string), after, user_name, action_type, element_type, element_name, description, database_id, table_id, created_at]
      ↓
React: setHistory(data) → groupByDate() → timeline groupée Aujourd'hui/Hier/date longue → cards avec dot accent, user_name, action_type, element_name, time, type badge, desc, IP mono, details before/after <details><pre> JSON
```

### Exemple 9 : Audit GET /audit-logs

```
AuditPage.jsx → auditService.list(200) → GET /audit-logs?limit=200
  → AuditService.get_all(limit) → order_by timestamp desc
  → JSON array AuditLog.to_dict() uuid, user_id, user_name, ip, action (CONNEXION, CREATION_BASE, IMPORT_XML, etc.), element_type, element_name, description, meta_data, timestamp
  → Table avec date mono, user, badge action couleur (green connexion, red suppression), element, description, IP
```

---

## 4. Explication des dossiers

**`app/`** : Package principal Flask. Contient factory, extensions, config, tous les sous-modules. Pourquoi séparé ? Pour éviter imports circulaires, permet `create_app(TestingConfig)` pour tests, et `app/` est un package Python (avec `__init__.py`) qui peut être importé via `from app import create_app`.

**`app/auth/`** : Auth helpers. `decorators.py` contient `protected_table_required` (exemple d'extension, même si logique déjà dans services). Pourquoi séparé ? Pour mettre décorateurs custom, middlewares auth futurs.

**`app/database/`** : Placeholder `__init__.py`. Pourrait contenir init db, migrations. Actuellement vide car `db` est dans `extensions.py` et `create_all()` dans factory. Gardé pour respecter architecture demandée.

**`app/models/`** : 5 modèles SQLAlchemy. Pourquoi séparés 1 fichier par modèle ? Lisibilité, évite fichier 1000 lignes, facile à maintenir, import ciblé. Chaque modèle a `to_dict()` + `is_archived()` helper.

**`app/routes/`** : 11 Blueprints, 1 fichier par domaine. Pourquoi séparés ? Single Responsibility, chaque route ne fait que validation + appel service + response. Pas de logique métier ici (spec). Facile à ajouter nouvelle route sans toucher autres domaines. `__init__.py` clone blueprints pour support `/api/*` et `/*` (compat frontend).

**`app/services/`** : Toute logique métier. Pourquoi séparés ? Testable sans Flask request, réutilisable, contient history, audit, socket, checks protection/archived, before/after pour history, last_modified_by. Aucune route ne fait `db.session` direct sauf via service.

**`app/converters/`** : Pur Python, dépendance `lxml` seulement, pas Flask. Pourquoi séparé ? Réutilisable en CLI (`python -m app.converters.xml_to_sql`), testable sans serveur, respecte spec "module ne doit dépendre ni de Flask ni des routes". Utilisé à la fois par `export_service` et `converters` routes et `import_service`.

**`app/utils/`** : Helpers transverses. `helpers.py` (key gen via `secrets`), `responses.py` (JSON cohérent), `validators.py` (Marshmallow schemas). Pourquoi séparé ? Évite duplication, centralise logique commune.

**`app/uploads/` et `app/exports/` + `uploads/` + `exports` à racine backend** : Dossiers pour fichiers importés/exportés. Pourquoi 2 emplacements ? Spec demande `uploads/` et `exports/` à l'intérieur de `app/` et aussi à racine backend. On crée les deux avec `.gitkeep`. `config.py` pointe vers racine backend `uploads/` pour `MAX_CONTENT_LENGTH`, mais `app/uploads` aussi créé pour compat.

**`app/extensions.py`** : Centralise `db`, `jwt`, `bcrypt`, `cors`, `socketio`. Pourquoi ? Évite import circulaire si chaque module fait `SQLAlchemy()` séparé → deux instances.

**`app/config.py`** : `Config` avec `SQLALCHEMY_DATABASE_URI` SQLite par défaut `xmlforge.db` sinon `DATABASE_URL` env, `JWT_SECRET_KEY`, `JWT_EXPIRES_HOURS`, `MYSQL_HOST/PORT/USER/PASSWORD`, `UPLOAD_FOLDER`, `CORS_ORIGINS`. `TestingConfig` `:memory:`, `ProductionConfig`. Pourquoi ? 12-factor, dev vs prod.

**`app/socket_events.py`** : Helpers émission SocketIO. Pourquoi séparé ? Pour ne pas mettre `socketio.emit` directement dans services (évite import circulaire), centralise noms événements.

**`app/app.py` et `run.py` et `config.py` root + `app.py` root** : Entry points. `run.py` = `socketio.run(app)`. `app/app.py` wrapper. `config.py` root importe depuis `app/config.py` pour compat spec qui liste `[config.py]` et `[app.py]` à racine backend. Architecture un peu redondante mais respecte spec.

**`uploads/` `exports/` racine** : Voir ci-dessus.

---

## 5. Explication des imports

Pour chaque fichier, rôle des imports importants :

- `from flask import Blueprint` : Crée modularité routes. Blueprint = mini app Flask enregistrable avec préfixe. Pourquoi : évite 1 fichier `app.py` 2000 lignes.
- `from flask import request` : Accéder JSON body, files, headers, remote_addr, args
- `from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token` : Décorateur protection route + récupère user_id depuis token + création token. Pourquoi JWT : stateless, pas session serveur.
- `from ..extensions import db, bcrypt, jwt, cors, socketio` : Extensions centralisées. `db` = SQLAlchemy instance, `bcrypt` pour hash, `socketio` pour emit.
- `from ..models.* import User, Database, Table, Column, History, AuditLog` : ORM. Pourquoi SQLAlchemy : abstraction SQLite/MySQL même code.
- `from ..utils.validators import *Schema` : Marshmallow Schemas. Pourquoi Marshmallow : validation déclarative `email = fields.Email(required=True)`, auto messages erreur, `unknown=INCLUDE` pour permettre key_identifier additionnel.
- `from marshmallow import ValidationError` : Catch validation.
- `from ..utils.responses import success_response, error_response` : JSON cohérent. Pourquoi : évite `jsonify({"data":...})` différent à chaque route.
- `from ..services.* import *Service` : Logique métier. Pourquoi : Routes ne contiennent pas logique.
- `from ..converters import parse_xml, convert_xml_to_sql` : Converters purs. Pourquoi lxml : parsing XML robuste, XPath, pretty print.
- `import uuid as uuid_lib` : Génération UUID4 pour tous les modèles V2. Pourquoi uuid : identifiant stable hors id auto-increment, utile pour frontend, historique, audit.
- `import secrets` : `secrets.token_hex(2)` pour clé `XML-XXXX-XXXX-XXXX`. Pourquoi secrets et pas random : cryptographiquement sûr.
- `from datetime import datetime` : `datetime.utcnow()` pour created_at/updated_at/timestamp. Pourquoi : traçabilité.
- `import re` : Regex pour parse SQL (`CREATE TABLE`, `PRIMARY KEY`, `FOREIGN KEY`) et nettoyage noms base MySQL réelle (`re.sub(r'[^a-zA-Z0-9_]+','_', name)`).
- `from lxml import etree` : Parsing XML, `fromstring`, `Element`, `SubElement`, `tostring pretty_print`, XPath `findall('.//table')`.
- `import mysql.connector` + `from mysql.connector import Error` : Connexion MySQL réelle, `CREATE DATABASE`, `USE`, exécution statements, catch Error.
- `import json` : dumps before/after pour History, meta_data pour AuditLog.
- `from flask_cors import CORS` : Autorise `http://localhost:5173` (Vite) → `Access-Control-Allow-Origin`.
- `from flask_bcrypt import Bcrypt` : Hash password `generate_password_hash`, check `check_password_hash`.
- `from flask_socketio import SocketIO` : WebSocket temps réel.
- `import os`, `from dotenv import load_dotenv` : Charge `.env` pour config.

---

## 6. Base de données

### Modèles

**User** : id PK, full_name 120, email 180 unique index, password_hash 255, created_at. Relations `databases_created` (FK creator_id), `tables_created`, `columns_created` avec `foreign_keys` explicites pour éviter ambiguïté avec last_modified_by.

**Database** : id PK, uuid 36 unique index default uuid4, name 120, description Text, creator_id FK users.id, created_at, updated_at onupdate, last_modified_by_id FK nullable, last_modified_by_name 120, comment Text default "", status 20 default ACTIVE, key_identifier 32 unique index (XML-XXXX-...), tables relationship cascade delete. `is_archived()` helper.

**Table** : id, uuid, name 120, description Text, database_id FK databases.id index, creator_id FK, created_at, updated_at, last_modified_by_id/name, comment, status ACTIVE/ARCHIVED, is_protected bool, columns relationship, `UniqueConstraint(database_id, name)`.

**Column** : id, uuid, name 120, type 50, length 20 default "-", nullable bool default True, primary_key bool, foreign_key bool, unique bool, auto_increment bool, default_value 255 nullable, creator_id FK, created_at, updated_at, last_modified_by_id/name, comment, status, table_id FK index, `UniqueConstraint(table_id, name)`.

**History** : id, uuid, user_id FK, user_name 120 dénormalisé, action_type 50 (a créé, a ajouté...), element_type 50 (base/table/colonne), element_name 120, description Text, ip_address 45, before_data Text JSON, after_data Text JSON, database_id FK nullable, table_id FK nullable, created_at index.

**AuditLog** : id, uuid, user_id nullable (pour erreurs avant auth), user_name 120 nullable, ip_address 45, action 100 (CONNEXION, DECONNEXION, CREATION_BASE, etc.), element_type 50 nullable, element_name 120 nullable, description Text, meta_data Text JSON, timestamp index.

### Relations SQLAlchemy

```
User 1--* Database (creator_id)
User 1--* Table (creator_id)
User 1--* Column (creator_id)
User 1--* History (user_id)
User 1--* AuditLog (user_id)
User 1--* Database (last_modified_by_id) via last_modifier relationship
User 1--* Table (last_modified_by_id)
User 1--* Column (last_modified_by_id)

Database 1--* Table (database_id) cascade delete
Table 1--* Column (table_id) cascade delete
Database 1--* History (database_id)
Table 1--* History (table_id) (history peut avoir database_id + table_id)
```

Schéma relationnel ASCII :

```
users
  | id PK
  | full_name
  | email UNIQUE
  | password_hash
  | created_at
  |
  +--< databases (creator_id FK)
  |     | id PK
  |     | uuid UNIQUE
  |     | name
  |     | key_identifier UNIQUE (XML-...)
  |     | comment
  |     | status (ACTIVE/ARCHIVED)
  |     | last_modified_by_id FK users
  |     | last_modified_by_name
  |     |
  |     +--< tables (database_id FK)
  |           | id PK
  |           | uuid
  |           | name UNIQUE per database
  |           | is_protected bool
  |           | comment, status, last_modified_by
  |           |
  |           +--< columns (table_id FK)
  |                 | id PK
  |                 | uuid
  |                 | name UNIQUE per table
  |                 | type, length, nullable, pk, fk, unique, ai, default
  |                 | comment, status, last_modified_by
  |
  +--< history (user_id FK)
  |     | uuid, user_name, action_type, element_type, element_name, ip, before, after, database_id, table_id, created_at
  |
  +--< audit_logs (user_id FK nullable)
        | uuid, user_name, ip, action, element_type, element_name, description, meta_data JSON, timestamp
```

SQLite dev : fichier `xmlforge.db` créé auto via `db.create_all()`. Migration V2 légère via `_migrate_v2()` qui fait `ALTER TABLE ADD COLUMN` si colonne manquante (inspecteur).

MySQL prod : si `DATABASE_URL=mysql+mysqlconnector://user:pass@host:port/dbname` dans .env, SQLAlchemy utilise MySQL. Création réelle de base via `POST /database/create` utilise `mysql-connector-python` directement (pas SQLAlchemy) pour `CREATE DATABASE`.

---

## 7. API REST - Liste complète avec détails

Toutes routes existent en double `/path` et `/api/path`.

### Auth

**POST /register**
- Body: `{full_name, email, password}` full_name 2-120, email format, password 6-128
- Headers: Content-Type json
- Réponse 201: `{success:true, data:{id, full_name, email, created_at}, message:"Inscription réussie"}`
- Erreurs: 400 email déjà utilisé, 400 validation {errors: {email: ["Not a valid email"]}}
- Audit: INSCRIPTION ou ERREUR_INSCRIPTION
- Permissions: public

**POST /login**
- Body: `{email, password}`
- Réponse 200: `{success:true, data:{user:{...}, access_token:"eyJ..."}, message:"Connexion réussie"}`
- Erreur 401: Email ou mot de passe incorrect
- Audit: CONNEXION ou ERREUR_CONNEXION

**GET /me**
- Headers: Authorization Bearer token
- Réponse 200: user dict
- Erreur 401: Missing Authorization Header, 404 utilisateur introuvable

**POST /logout**
- Headers: Bearer
- Réponse 200: Déconnexion réussie
- Audit: DECONNEXION
- Note: Stateless, client supprime token

### Databases

**GET /databases?include_archived=true|false** (default true)
- JWT requis
- Réponse 200: array databases sans key_identifier (sauf créateur)
- Erreur 401

**POST /databases**
- Body: `{name (1-120 requis), description?, comment?}`
- Réponse 201: database dict avec uuid, comment, status ACTIVE, last_modified_by, key_identifier inclus (créateur), tables_count 0
- Erreur 400 validation, 500
- History: a créé base + IP + before null + after full dict
- Audit: CREATION_BASE
- Socket: new_database

**GET /databases/<id>**
- Query: `?key=XML-...` ou header `X-Database-Key` pour inclure key
- Réponse 200: database dict, key incluse si créateur ou clé valide fournie
- 404 introuvable

**PUT /databases/<id>**
- Body: `{name?, description?, comment?}`
- Bloqué si ARCHIVED → 400
- Réponse 200: updated dict
- History: a modifié avec before/after, IP
- Audit: MODIFICATION_BASE
- Socket: modification

**DELETE /databases/<id>**
- Bloqué si ARCHIVED → 400
- Réponse 200: supprimée
- History + Audit SUPPRESSION_BASE + socket suppression

**POST /databases/<id>/archive**
- Pas de body
- 200: status ARCHIVED
- Bloque futures modifs/suppr mais reste exportable
- History a archivé + Audit ARCHIVAGE_BASE + socket modification

**POST /databases/<id>/restore**
- 200: status ACTIVE
- History a restauré + Audit RESTAURATION_BASE

**GET /databases/<id>/comment**
- Réponse 200: `{comment, database_id, uuid}`

**PUT /databases/<id>/comment**
- Body: `{comment: "Nouveau"}`
- Réponse 200: comment mis à jour + History COMMENTAIRE_BASE + Audit

### Tables

**GET /tables/<database_id>?include_archived=true|false**
- Réponse 200: array tables avec uuid, comment, status, is_protected, columns_count, last_modified_by

**POST /tables**
- Body: `{name (requis, unique par base), description?, database_id (requis), is_protected? bool default false, comment?}`
- Vérifie base existe et pas archivée
- 201: table dict
- History + Audit CREATION_TABLE + socket new_table

**PUT /tables/<id>**
- Body: `{name?, description?, is_protected?, comment?, key_identifier?}` + header X-Database-Key optionnel
- Checks: is_archived? → 400, is_protected? → besoin clé valide (database.key_identifier) sinon 403
- 200: updated

**DELETE /tables/<id>**
- Query `?key=` ou header ou body key_identifier
- Checks archived + protected
- 200 supprimée

**POST /tables/<id>/archive /restore**
- Checks protection
- 200 status changé

**GET /tables/<id>/comment / PUT /tables/<id>/comment**
- Protection check

**POST /unlock-table**
- Body: `{table_id, key_identifier}` requis
- Vérifie database.key_identifier == key
- 200 {unlocked:true} + Audit DEVERROUILLAGE_TABLE, sinon 403 + Audit ERREUR_DEVERROUILLAGE

### Columns

**GET /columns/<table_id>?include_archived**
- 200 array columns avec uuid, comment, status, last_modified_by, etc.

**POST /columns**
- Body: `{name, type, length?, nullable? bool default true, primary_key? bool, foreign_key? bool, unique? bool, auto_increment? bool, default?, table_id (requis), comment?, key_identifier?}`
- Vérifie table existe, table pas archivée, colonne name unique par table, protection table parente → besoin clé
- 201 column dict

**PUT /columns/<id>**
- Body: mêmes champs optionnels + key_identifier
- Checks archived colonne + table parente archived + protection
- 200 updated

**DELETE /columns/<id>**
- Query key ou header
- Checks

**POST /columns/<id>/archive /restore**
**GET/PUT /columns/<id>/comment**

### Import

**POST /import/xml**
- JWT requis
- Body multipart: file .xml + database_name?, description?, comment? OU JSON {xml, database_name, description, comment}
- Validation: parse_xml via converters, si échec 400
- Crée database uuid/key/comment/status/last_modified_by + tables + columns avec uuid/comment/status/last_modified_by
- 201 database dict avec key
- History + Audit IMPORT_XML + socket import_xml

**POST /import/sql**
- Idem avec SQL, parse_sql

### Export

**GET /export/xml/<database_id>**
- JWT
- Génère XML via ExportService (même archivé exportable)
- ?download=true → Response mimetype application/xml attachment filename database_<id>.xml
- Sans download → JSON {xml, database_id}
- Audit EXPORT_XML + socket export_xml

**GET /export/sql/<database_id>**
- Génère XML puis convert_xml_to_sql
- ?download=true → application/sql attachment
- Audit EXPORT_SQL + socket export_sql

### Converters

**POST /convert/xml-to-sql**
- Body: `{xml: "<table>...</table>", database_name?}`
- Validation: xml requis
- Appelle convert_xml_to_sql pur
- 200 {sql}
- Audit CONVERSION_XML
- Erreur 400 si XML invalide + Audit ERREUR_CONVERSION_XML

**POST /convert/sql-to-xml**
- Body: `{sql: "CREATE TABLE...", database_name?}`
- 200 {xml}
- Audit CONVERSION_SQL

### Database réelle

**POST /database/create**
- Body: `{database_id (requis), target_database_name?}`
- Exporte SQL de base logique, connecte MySQL via mysql-connector avec config .env MYSQL_HOST/PORT/USER/PASSWORD, CREATE DATABASE IF NOT EXISTS target, USE, split SQL par ; et exécute CREATE TABLEs, commit
- Réponse 200: {target_database, executed_statements, errors[], sql_preview}
- Erreur 500 si MySQL non configuré avec sql preview dans errors
- Audit CREATION_REELLE_BASE ou ERREUR_CREATION_REELLE

### History & Audit

**GET /history?limit=100&database_id=**
- JWT, limit max 500
- 200 array history dicts avec uuid, ip_address, before (JSON string), after, user_name, action_type, element_type, element_name, description, database_id, table_id, created_at
- Tri desc

**GET /audit-logs?limit=100**
- JWT
- 200 array audit logs uuid, user_id, user_name, ip_address, action (CONNEXION, etc.), element_type, element_name, description, meta_data JSON, timestamp
- Alias GET /audit

**GET /health**
- Public, 200 {status:ok, service:XMLForge Backend V2, version:2.0.0}

**GET /**
- Public, liste endpoints + features V2

---

## 8. Sécurité

**JWT**
- `Flask-JWT-Extended`, `JWT_SECRET_KEY` depuis .env, expiration 24h configurable `JWT_EXPIRES_HOURS`
- `create_access_token(identity=str(user.id))`, `jwt_required()` décorateur, `get_jwt_identity()` récupère user_id
- Stockage client `localStorage xmlforge_token`, envoi `Authorization: Bearer`
- 401 auto redirect login

**Hash mots de passe**
- `Flask-Bcrypt`, `generate_password_hash(password).decode('utf-8')`, `check_password_hash(hash, password)`
- Jamais stocké en clair, jamais retourné dans `to_dict()`

**Tables protégées**
- Champ `is_protected` bool sur Table
- Clé `key_identifier` sur Database, format `XML-XXXX-XXXX-XXXX` via `secrets.token_hex(2).upper()` x3 (cryptographiquement sûr, pas `random`)
- Vérification dans `TableService._check_protection(table, provided_key)` : si `is_protected` et pas de clé ou clé != `database.key_identifier` → 403
- Clé fournie via header `X-Database-Key` (recommandé), query `?key=`, ou body `key_identifier`
- Clé conservée uniquement en session côté frontend (`sessionStorage`), clear au logout, spec respectée
- Lecture toujours autorisée (GET tables/columns), écriture bloquée

**Permissions**
- Toutes bases visibles par tous (collaboratif) → `GET /databases` pas de filtre creator
- Création/modification/suppression : JWT requis, tout utilisateur authentifié peut créer, mais seul créateur voit clé par défaut (sauf si Fournit clé valide)
- Archivage bloque modif/suppr mais pas export/lecture
- `is_archived()` helper check dans services avant toute modif

**Validation**
- Marshmallow Schemas avec `unknown=INCLUDE` pour permettre `key_identifier` additionnel sans "Unknown field" erreur
- `RegisterSchema`: full_name 2-120, email format, password 6-128
- `LoginSchema`: email, password requis
- `DatabaseCreateSchema`: name 1-120 requis
- `TableCreateSchema`: name 1-120, database_id requis, is_protected bool default false
- `ColumnCreateSchema`: name 1-120, type 1-50 requis, table_id requis, etc.
- `UnlockTableSchema`: table_id, key_identifier requis
- `ConvertXmlToSqlSchema`: xml requis
- ValidationError → 400 avec `errors` dict

**CORS**
- `Flask-CORS`, `CORS_ORIGINS` depuis .env `http://localhost:5173,http://localhost:3000` split, `supports_credentials=True`

**Uploads**
- `MAX_CONTENT_LENGTH` 16MB, `UPLOAD_FOLDER` + `EXPORT_FOLDER` créés auto dans factory

---

## 9. Converters – Logique précise

**`xml_to_sql.py` – pourquoi indépendant Flask ?**
- Pour être réutilisable en CLI (`python -m app.converters.xml_to_sql`), testable sans serveur, utilisé à la fois par `export_service` (export) et `converters` route (conversion) et `import_service` reverse
- Dépendance uniquement `lxml`

Logique:
1. `parse_xml(xml_content)`: `etree.fromstring`, détecte root tag : si `<database>` → `findall('.//table')`, si `<table>` → [root], si `<tables>` → `findall('.//table')`, sinon `findall('.//table')` global, si aucune → ValueError. Pour chaque `<table>`, `get('name')`, `findall('./column')` → `_parse_column_element()` qui parse attrs `name`, `type`, `length`, `nullable` (true si attr `nullable="true"` sinon true par défaut, false si `nullable="false"`), `primaryKey|primary_key`, `foreignKey|foreign_key`, `unique`, `autoIncrement|auto_increment`, `default`, `references`. Retourne list tables dict.
2. `_column_to_sql(col)`: `type(length)` si length != '-' et type ne contient pas déjà `(`, sinon type seul. Parts: `` `name` TYPE `` + `NOT NULL` si nullable false + `AUTO_INCREMENT` + `UNIQUE` + `DEFAULT 'val'` (gère CURRENT_TIMESTAMP, NULL, digit vs string avec échappement `''`).
3. `convert_xml_to_sql()`: parse → pour chaque table, col_defs via `_column_to_sql`, pk_cols list, fk_defs list (si `references` contient `table.col` → `FOREIGN KEY (`col`) REFERENCES `table`(`col`)`), puis `CREATE TABLE `name` (\n col_defs + PRIMARY KEY + FKs \n);`. Si database_name fourni, prépend `CREATE DATABASE IF NOT EXISTS` + `USE`.

**`sql_to_xml.py` – indépendant**
- `_strip_comments(sql)`: regex `--.*?$` multiline + `/\*.*?\*/` dotall
- `_split_sql_statements(sql)`: split `;`, filter non vide contenant CREATE
- `_extract_table_name_and_body(stmt)`: regex `CREATE TABLE (IF NOT EXISTS)? `?(\w+)`? \s*\(`, puis compte parenthèses depth pour extraire body entre (...) gérant `DECIMAL(10,2)`
- `_split_columns(body)`: iterate char par char, depth compteur `(`, `)`, flags `in_single`/`in_double` pour quotes, split par `,` seulement si depth 0 et pas dans quotes
- `_parse_column_def(col_def)`: trim, si commence par PRIMARY KEY/FOREIGN KEY/UNIQUE KEY/KEY/CONSTRAINT → retourne `__constraint__`, sinon regex `` `?(\w+)`? \s+ ([A-Z]+)(?:\(([^)]+)\))? \s* (.*)`` → name, type, length, rest. Parse rest_upper pour NOT NULL, AUTO_INCREMENT, UNIQUE, PRIMARY KEY inline, DEFAULT via regex `DEFAULT\s+(?:'([^']*)'|"([^"]*)"|(\S+))`
- `parse_sql()`: pour chaque CREATE TABLE statement, extract name+body, split columns, parse chaque, sépare colonnes vs contraintes, pour PK constraint `PRIMARY KEY (id, ...)` → set primary_key True pour ces colonnes, pour FK `FOREIGN KEY (col) REFERENCES table(col)` → set foreign_key True + references
- `convert_sql_to_xml()`: build lxml `database name=database_name` → `table name` → `column` avec attrs name, type, length, nullable, primaryKey, foreignKey, unique, autoIncrement, default, references

---

## 10. Architecture globale – schémas ASCII

### Requête HTTP classique CRUD

```
React Component (Dashboard.jsx)
  |
  | const data = await databaseService.create({name})
  |   ↓
  | databaseService.create() → apiClient.post('/databases', body)
  |   ↓ fetch + JWT + Content-Type json
  |
Flask @jwt_required() Route POST /databases
  |
  | request.get_json() → DatabaseCreateSchema().load() → validation Marshmallow
  |   ↓
  | DatabaseService.create(name, description, creator_id, creator_name, comment, ip)
  |   | génère key XML-XXXX via secrets.token_hex
  |   | Database(uuid=uuid4(), name, key_identifier, comment, status ACTIVE, last_modified_by)
  |   | db.session.add + commit
  |   | HistoryService.log() → uuid, ip, before null, after dict
  |   | AuditService.log() → CREATION_BASE
  |   | emit_new_database() → socketio.emit('new_database', {database, by})
  |
  | success_response 201 {data: database.to_dict(include_key=True)}
  ↓
React: setDatabases([data, ...prev]) → nouvelle card + toast + socket event reçu par autres clients
```

### Import XML

```
React Dashboard dropzone onDrop file
  ↓
importService.importXml(file) → FormData file + database_name
  → apiClient.post('/import/xml', formData) isFormData=true → pas Content-Type json
    ↓
Flask POST /import/xml @jwt_required()
  → request.files['file'].read().decode('utf-8')
  → ImportService.import_xml(xml_content, database_name, creator_id, creator_name, ip, comment)
    → parse_xml() via converters (lxml)
    → Database + Tables + Columns avec uuid/comment/status/last_modified_by
    → commit
    → History + Audit IMPORT_XML
    → emit_import_xml
  → 201 database dict
→ React fetchDatabases() + toast + socket
```

### Conversion XML → SQL

```
MonacoEditor XML Source value xmlDraft (state onChange)
  ↓
Bouton Convertir → handleConvertXmlToSql()
  → converterService.xmlToSql(xmlDraft, database.name)
    → apiClient.post('/convert/xml-to-sql', {xml, database_name})
      ↓
Flask POST /convert/xml-to-sql @jwt_required()
  → ConvertXmlToSqlSchema validation
  → convert_xml_to_sql(xml, database_name) converter pur lxml → CREATE TABLEs
  → Audit CONVERSION_XML
  → 200 {sql}
      ↓
React setSqlGenerated(res.sql) → MonacoEditor SQL readonly affiche SQL instantanément
  → Bouton Copier → navigator.clipboard.writeText
  → Bouton Télécharger → Blob + URL.createObjectURL + <a download>
```

### Création réelle base MySQL

```
React Workspace Export SQL + Créer réelle
  → exportService.exportSql(id, {download:false}) → GET /export/sql/:id → {sql}
  → systemApi.createRealDatabase(databaseId, targetName) → POST /database/create {database_id, target_database_name}
    ↓
Flask POST /database/create @jwt_required()
  → ExportService.export_database_to_sql() → XML → SQL
  → mysql.connector.connect(host,port,user,password) via .env
  → cursor.execute(CREATE DATABASE IF NOT EXISTS target CHARACTER SET utf8mb4)
  → cursor.execute(USE target)
  → split SQL par ; + exécute CREATE TABLEs
  → commit + close
  → Audit CREATION_REELLE_BASE
  → 200 {target_database, executed_statements, errors, sql_preview}
    ↓
React toast + affichage target_database
```

### Schéma global V2

```
React (Vite :5173)
  |
  |-- AuthContext (JWT + socket connect)
  |-- DatabaseContext (currentDatabase + dbKey sessionStorage)
  |-- Services (api.js centralisé + 11 services)
  |     |-- apiClient (fetch + JWT + X-Database-Key + 401 redirect)
  |     |-- databaseService, tableService, columnService (CRUD + archive/restore/comment + protection)
  |     |-- importService (FormData) / exportService (blob download)
  |     |-- converterService (xmlToSql, sqlToXml)
  |     |-- historyService, auditService
  |     |-- socketService (socket.io-client, on new_database, new_table, modification, suppression, import_xml, export_sql)
  |
  ↓ HTTP REST + WebSocket
  |
Flask (run.py socketio.run :5000)
  |
  |-- Blueprints / + /api/* (auth, databases, tables, columns, imports, exports, converters, history, unlock, database_create, metadata, audit)
  |     |-- @jwt_required() + Marshmallow validation + get_ip() (remote_addr / X-Forwarded-For)
  |     |-- Services (toute logique métier, zero logique dans routes)
  |           |-- HistoryService (uuid, ip, before/after JSON)
  |           |-- AuditService (action CONNEXION, CREATION_BASE, IMPORT_XML, etc.)
  |           |-- socket_events.emit_* (new_database, new_table, etc.)
  |           |-- Models (SQLAlchemy)
  |                 |-- SQLite dev xmlforge.db ou MySQL prod via DATABASE_URL
  |                 |-- User, Database (uuid, comment, status, last_modified_by, key_identifier), Table (uuid, comment, status, is_protected), Column (uuid, comment, status), History (uuid, ip, before, after), AuditLog (uuid, action, ip, meta)
  |           |-- Converters purs (xml_to_sql, sql_to_xml) lxml
  |           |-- mysql-connector-python (création réelle)
  |
  +-- Extensions (db, jwt, bcrypt, cors, socketio)
  +-- Config (.env)
  +-- uploads/ exports/
```

---

## 11. Philosophie – Pourquoi cette architecture ?

**Pourquoi Services existent ?**
- Routes ne doivent contenir que validation + appel service + réponse JSON. Si logique métier dans routes, duplication, difficile à tester, mélange HTTP + business. Services testables sans Flask (`from app.services import ...` + mock db), réutilisables (import_service utilisé à la fois par import route et par tests), centralisent history/audit/socket.

**Pourquoi Routes ne contiennent pas de logique métier ?**
- Respect Single Responsibility, Clean Architecture. Route = Controller HTTP, Service = Use Case métier. Facile à ajouter nouvelle route sans dupliquer logique. Ex: `POST /databases/:id/archive` et `POST /tables/:id/archive` partagent même pattern check archived, mais chaque service gère son domaine.

**Pourquoi Converters séparés ?**
- Spec demande "module ne doit dépendre ni de Flask ni des routes" + "véritable service réutilisable". Converters utilisés à 3 endroits: `export_service` (export), `converters` routes (conversion), `import_service` reverse. Si Converters dépendaient de Flask, on ne pourrait pas les tester en CLI `python -m app.converters.xml_to_sql`. Séparation garantit pureté, testabilité, réutilisation.

**Pourquoi SQLAlchemy ?**
- ORM mature, supporte SQLite dev (fichier `xmlforge.db` auto créé) et MySQL prod via même code (change `DATABASE_URL`). Relations `relationship` + `cascade delete` + `UniqueConstraint` + `ForeignKey` évitent SQL manuel. `db.create_all()` crée tables auto. Migration légère `_migrate_v2()` ALTER TABLE ADD COLUMN pour dev.

**Pourquoi JWT ?**
- Stateless, scalable horizontalement (pas de session serveur), mobile-friendly, expiration 24h configurable, `Flask-JWT-Extended` gère `@jwt_required()`, `get_jwt_identity()`, `create_access_token`. Stockage client `localStorage`, envoi `Authorization: Bearer`. Logout côté client (suppression token) + audit DECONNEXION. Si besoin blacklist, ajouter table `token_blacklist`.

**Pourquoi modèles séparés ?**
- 1 fichier = 1 table, évite fichier 1000 lignes, import ciblé `from ..models.database import Database`, facile à ajouter champ V2 (uuid, comment, status) sans toucher autres modèles. `to_dict()` centralise sérialisation, `is_archived()` helper.

**Pourquoi cette architecture sera facile à maintenir ?**
- Ajout nouveau champ (ex: `color` sur Table) : modifier `models/table.py` ajouter colonne, ajouter à `to_dict()`, ajouter à `TableUpdateSchema` dans `validators.py`, ajouter à service `update()` handling, migration `_migrate_v2()` ajoutera colonne. Pas besoin toucher routes autres domaines.
- Ajout nouvelle route (ex: `POST /tables/<id>/duplicate`) : créer méthode `duplicate()` dans `TableService`, créer route dans `tables.py` qui appelle service, log history/audit/socket, done.
- Ajout nouveau event SocketIO (ex: `new_comment`) : ajouter helper `emit_new_comment()` dans `socket_events.py`, appeler depuis `comment` service, frontend écoute via `socketService.on('new_comment')`.
- Tests : `TestingConfig` avec `:memory:` SQLite, `app.test_client()`, pas besoin MySQL, pas besoin serveur.

---

*Documentation V2 – Backend prêt pour frontend React déjà développé – Aucune route V1 cassée, ajout V2 sans breaking change – Production ready*

---

# XMLForge XML Specification V3 - XML source de vérité

> Cette section documente le format XML officiel de XMLForge depuis la V3. Le XML est la source de vérité : toute modification via l'éditeur est synchronisée vers la base logique via `POST /databases/<id>/sync-xml`, et le SQL est toujours généré depuis la base logique, jamais directement depuis XML.

## Philosophie V3

Avant V3, le flux était :

```
XML (fichier) -> Conversion directe -> SQL (preview)
```

Problème : le backend répondait succès mais les tables n'étaient pas enregistrées, pas rechargées, suppression/ajout colonne ne modifiait pas la structure persistante.

Depuis V3 :

```
XML (éditeur Monaco)
  ↓ POST /databases/<id>/sync-xml {xml}
Backend parse complet XML (lxml)
  ↓
Si table n'existe pas → créer
Si table existe → maj description, protected, file_identifier, comment, status
Si colonne n'existe pas → créer
Si colonne existe → maj type, length, nullable, pk, fk, unique, ai, default, comment
Si colonne supprimée du XML → la supprimer de la structure logique
  ↓
Sauvegarde Models (SQLAlchemy) + History (IP, before/after, uuid) + Audit + SocketIO
  ↓
Génération SQL depuis base logique (export_service -> xml_to_sql) → retourne {database, created_tables, updated_tables, created_columns, updated_columns, deleted_columns, details, sql}
  ↓
Frontend : fetchTables(), fetchColumns(), fetchDatabase() sans rechargement manuel + toast + socket emit_modification → Dashboard rafraîchi auto
  ↓
SQL affiché vient toujours de la base logique, jamais directement du XML brut
```

## Balises

### <database>

Racine optionnelle mais recommandée. Peut contenir plusieurs `<table>`.

**Exemple :**
```xml
<database name="Bibliothèque" description="Gestion livres" comment="Base critique prod" status="ACTIVE">
  <table>...</table>
  <table>...</table>
</database>
```

Si XML ne contient qu'une seule `<table>` sans `<database>`, le backend considère que c'est une table appartenant à la base cible (sync sur base existante).

### <table>

Représente une table logique.

**Exemple :**
```xml
<table name="client" description="Clients" comment="Table contenant les informations des clients." protected="true" file_identifier="XML-9F4A-28BD-71A2" status="ACTIVE">
  <column ... />
</table>
```

### <column>

Représente une colonne, toujours enfant direct de `<table>`.

**Exemple :**
```xml
<column name="email" type="VARCHAR" length="255" nullable="false" primary_key="false" foreign_key="false" unique="true" auto_increment="false" default="" comment="Ne jamais supprimer cette colonne." />
```

### <tables>

Wrapper optionnel pour plusieurs tables sans database.

```xml
<tables>
  <table name="client">...</table>
  <table name="commande">...</table>
</tables>
```

## Attributs détaillés

### DATABASE

| Attribut | Obligatoire | Type | Défaut | Description |
|----------|-------------|------|--------|-------------|
| `name` | **Oui** | string 1-120 | – | Nom base, unique par utilisateur |
| `description` | Non | string | "" | Description courte |
| `comment` | Non | string | "" | Commentaire libre, ex: "Base critique prod" |
| `uuid` | Non (auto) | UUID4 | généré | Identifiant stable, généré backend, exporté pour traçabilité |
| `status` | Non | ACTIVE/ARCHIVED | ACTIVE | État, si ARCHIVED → lecture/export OK, modif/suppr bloquée |

**Exemple base complète :**
```xml
<database name="Bibliothèque" description="Gestion bibliothèque municipale" comment="Base principale - ne pas archiver sans backup" status="ACTIVE" uuid="8c000ed1-9b6a-4cbf-a1c5-fcaa05ab1229">
</database>
```

### TABLE

| Attribut | Obligatoire | Type | Défaut | Description |
|----------|-------------|------|--------|-------------|
| `name` | **Oui** | string 1-120 | – | Nom table, unique par base |
| `description` | Non | string | "" | Description |
| `protected` | Non | booleanString true/false/1/0/yes/no | false | Si true, table protégée nécessite file_identifier ou clé base |
| `file_identifier` | Non | string 4-64 | null | Alias: `fileIdentifier`, `file_id`. Identifiant fichier requis pour déverrouiller table protégée. Format recommandé `XML-XXXX-XXXX-XXXX` mais custom accepté. Ex: `XML-9F4A-28BD-71A2` |
| `comment` | Non | string | "" | Commentaire libre, ex: "Table contenant les informations des clients." |
| `archived` | Non | booleanString | false | Alias pour status ARCHIVED. Si true → status=ARCHIVED |
| `status` | Non | ACTIVE/ARCHIVED | ACTIVE | État |
| `uuid` | Non (auto) | UUID4 | généré | Exporté, réimportable |
| `protected` alias | – | – | – | `is_protected` accepté aussi pour compat V1 |
| `fileIdentifier` alias | – | – | – | CamelCase accepté |

**Méthodes protection :**

Méthode 1 – XML direct :
```xml
<table name="client" protected="true" file_identifier="XML-9F4A-28BD-71A2" comment="Table protégée">
```

Méthode 2 – Modal UI :
- Checkbox ☐ Protéger cette table
- Si coché → champ Identifiant du fichier [__________] apparaît
- Valeur enregistrée en base `file_identifier`

**Modification après création :**
Via `PUT /tables/<id>` ou `POST /tables/<id>/archive|restore` ou modal Paramètres table (⚙️) :
- Peut protéger/déprotéger
- Modifier file_identifier
- Modifier commentaire

**Comportement table protégée :**
- Lecture : Toujours autorisée (`GET /tables/<id>`, `GET /columns/<id>`)
- Modification : Impossible sans identifiant → 403 + frontend ouvre modal clé
- Suppression : Impossible sans identifiant → 403
- Ajout colonne : Impossible sans identifiant → 403
- Modification colonne : Impossible sans identifiant
- Suppression colonne : Impossible sans identifiant
- Frontend : modal demande clé, envoie via header `X-Database-Key` ou body `key_identifier`, si valide → poursuit action automatiquement + mémorise en sessionStorage jusqu'au rechargement

### COLUMN

| Attribut | Obligatoire | Type | Défaut | Description |
|----------|-------------|------|--------|-------------|
| `name` | **Oui** | string 1-120 | – | Nom colonne, unique par table |
| `type` | **Oui** | string 1-50 | – | Type SQL: INT, VARCHAR, TEXT, DATETIME, DECIMAL, BOOLEAN, BIGINT, etc. |
| `length` | Non | string | "-" | Longueur: 255, 11, 10,2 ou - si non applicable |
| `nullable` | Non | booleanString | true | true = NULL autorisé, false = NOT NULL |
| `primary_key` / `primaryKey` | Non | booleanString | false | PK |
| `foreign_key` / `foreignKey` | Non | booleanString | false | FK |
| `references` | Non | string | null | Format `table(colonne)` ex: `client(id)` – utilisé pour FOREIGN KEY |
| `unique` | Non | booleanString | false | UNIQUE |
| `auto_increment` / `autoIncrement` | Non | booleanString | false | AUTO_INCREMENT |
| `default` | Non | string | null | Valeur par défaut, ex: "0", "CURRENT_TIMESTAMP", "" |
| `comment` | Non | string | "" | Commentaire libre, ex: "Ne jamais supprimer cette colonne." |
| `uuid` | Non (auto) | UUID4 | généré | |
| `status` | Non | ACTIVE/ARCHIVED | ACTIVE | |
| `archived` | Non | booleanString | false | Alias |

**Exemple colonne complète :**
```xml
<column name="email" type="VARCHAR" length="255" nullable="false" primary_key="false" foreign_key="false" unique="true" auto_increment="false" default="" comment="Ne jamais supprimer cette colonne - email unique client" status="ACTIVE" />
```

**Exemple colonne avec FK :**
```xml
<column name="client_id" type="INT" length="11" nullable="false" foreign_key="true" references="client(id)" comment="Référence client" />
```

## Exemples complets

### Exemple 1 – Base simple avec protection via file_identifier (Méthode 1)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<database name="Bibliothèque" description="Gestion bibliothèque municipale" comment="Base principale" status="ACTIVE">
  <table name="client" description="Clients" comment="Table contenant les informations des clients." protected="true" file_identifier="XML-9F4A-28BD-71A2" status="ACTIVE">
    <column name="id" type="INT" length="11" nullable="false" primary_key="true" auto_increment="true" comment="Clé primaire - ne jamais supprimer" />
    <column name="nom" type="VARCHAR" length="100" nullable="false" comment="Nom complet client" />
    <column name="email" type="VARCHAR" length="255" nullable="false" unique="true" comment="Ne jamais supprimer cette colonne - email unique" />
    <column name="created_at" type="DATETIME" nullable="false" default="CURRENT_TIMESTAMP" />
  </table>
  <table name="commande" description="Commandes" comment="Table commandes" protected="false" status="ACTIVE">
    <column name="id" type="INT" length="11" primary_key="true" auto_increment="true" />
    <column name="client_id" type="INT" length="11" foreign_key="true" references="client(id)" />
    <column name="total" type="DECIMAL" length="10,2" nullable="false" default="0.00" />
  </table>
</database>
```

**Comportement backend lors de `POST /databases/<id>/sync-xml` avec ce XML :**
- Base `Bibliothèque` : met à jour description/comment si fournis, last_modified_by = user, updated_at = now
- Table `client` : existe ? Oui → update description, comment, protected=true, file_identifier=XML-9F4A-..., status ACTIVE. Vérifie protection : si table protégée, besoin clé fournie (file_identifier ou clé base) sinon skip avec message "Table protégée, clé invalide, mise à jour ignorée"
- Colonnes `client` : `id` existe → update type, length, pk, comment. `nom` n'existe pas → créer. `email` existe → update. Si colonne en DB `telephone` n'est plus dans XML → **supprimer** (spec)
- Table `commande` : n'existe pas → créer avec uuid, comment, status, puis colonnes id, client_id, total
- Commit, History log avec IP, before/after JSON, Audit SYNC_XML, Socket emit_modification
- Génère SQL depuis base logique (pas depuis XML brut) → `CREATE DATABASE` + `CREATE TABLE client (...)` + `CREATE TABLE commande (...)` avec PK, FK si references
- Retourne `{database, created_tables:1, updated_tables:1, created_columns:3, updated_columns:1, deleted_columns:1, details:[...], sql:"CREATE TABLE..."}`

### Exemple 2 – Table protégée créée via modal (Méthode 2)

Frontend :
- User clique "＋ Nouvelle table" → Modal : Nom `facture`, Description `Factures`, Commentaire `Ne jamais supprimer`, coche ☐ Protéger cette table → champ Identifiant du fichier apparaît → user entre `XML-ABCD-1234-EFGH` → Créer
- Frontend : `POST /tables {name:facture, description, database_id, is_protected:true, file_identifier:XML-ABCD-1234-EFGH, comment}`
- Backend : `TableService.create()` stocke `is_protected=true`, `file_identifier=XML-ABCD-...`
- Export XML ultérieur contiendra : `<table name="facture" protected="true" file_identifier="XML-ABCD-1234-EFGH" comment="Ne jamais supprimer" ...>`

### Exemple 3 – Modification après création (spec 5)

Frontend : Workspace → Table `facture` → bouton ⚙️ Paramètres (protection, file_id)

Modal Paramètres table :
- Nom (éditable)
- Description
- Commentaire
- État ACTIVE/ARCHIVED
- Checkbox Protéger cette table
- Si coché → Identifiant du fichier [XML-ABCD-...] (modifiable)

→ `PUT /tables/<id>` {name, description, comment, is_protected, file_identifier, status, key_identifier: <clé actuelle si table déjà protégée>}

Backend : `TableService.update()` vérifie protection existante avec clé fournie, puis met à jour is_protected, file_identifier, comment, status, last_modified_by.

### Exemple 4 – Export sans perte (spec 8)

`GET /export/xml/<id>` génère :

```xml
<?xml version="1.0" encoding="UTF-8"?>
<database name="Bibliothèque" uuid="beb810cd-..." description="Gestion" comment="Base principale" status="ACTIVE">
  <table name="client" uuid="db6af00f-..." description="Clients" comment="Table contenant les informations des clients." protected="true" file_identifier="XML-9F4A-28BD-71A2" status="ACTIVE" archived="false">
    <column name="id" type="INT" length="11" nullable="false" primary_key="true" foreign_key="false" unique="false" auto_increment="true" uuid="4516dbe2-..." status="ACTIVE" comment="Clé primaire" />
    <column name="email" type="VARCHAR" length="255" nullable="false" unique="true" comment="Ne jamais supprimer cette colonne." />
  </table>
</database>
```

Ce XML réimporté via `POST /import/xml` ou `POST /databases/<id>/sync-xml` ne perd aucune info : descriptions, commentaires, protection, file_identifier, nullable, PK, FK, UNIQUE, DEFAULT, AUTO_INCREMENT.

---

## XSD

Fichier `backend/xmlforge.xsd` et `backend/app/static/xmlforge.xsd` valide la spec V3.

**Validation exemple (Python) :**
```python
from lxml import etree
xsd = etree.parse('xmlforge.xsd')
schema = etree.XMLSchema(xsd)
xml = etree.parse('export.xml')
schema.assertValid(xml)  # lève si invalide
```

XSD gère :
- `database` avec `name` requis, `description`, `comment`, `uuid`, `status`
- `table` avec `name` requis, `description`, `protected` booleanString, `file_identifier` 4-64 chars, `comment`, `archived` booleanString, `status`, `uuid`
- `column` avec `name` requis, `type` requis, `length`, `nullable`, `primary_key`, `foreign_key`, `references`, `unique`, `auto_increment`, `default`, `comment`, `uuid`, `status`, `archived`
- Alias camelCase : `primaryKey`, `foreignKey`, `autoIncrement`, `fileIdentifier`
- Types `booleanString` acceptant true/false/1/0/yes/no
- `fileIdentifierType` 4-64 chars
- `statusType` ACTIVE/ARCHIVED (insensible casse)

---

## Flux final V3 - XML source de vérité

```
┌─────────────────┐
│ MonacoEditor    │  XML édité par utilisateur (coller XML complet base)
│ XML Source      │  Ex: <database><table protected="true" file_identifier="XML-...">...
└────────┬────────┘
         │ Clique "Appliquer les modifications → Backend Sync + Refresh auto"
         ↓ POST /databases/<id>/sync-xml {xml, key_identifier?}
┌─────────────────────────────────────────┐
│ Backend Flask                           │
│ - Parse XML V3 avec lxml (database, table avec protected/file_identifier/comment/archived, column avec nullable, pk, fk, references, unique, ai, default, comment) │
│ - Pour chaque table dans XML:           │
│   • Si n'existe pas → créer (uuid, comment, protected, file_identifier, status) │
│   • Si existe → maj description, protected, file_identifier, comment, status (check protection: besoin clé file_identifier ou clé base) │
│ - Pour chaque colonne dans table:       │
│   • Si n'existe pas → créer             │
│   • Si existe → maj type, length, nullable, pk, fk, unique, ai, default, comment │
│   • Si colonne en DB mais plus dans XML → supprimer (spec) │
│ - Commit, History (IP, before JSON, after JSON, uuid), Audit SYNC_XML, Socket emit_modification │
│ - Génère SQL depuis base logique (export_service -> xml_to_sql) : CREATE DATABASE + USE + CREATE TABLE avec PK, FK, UNIQUE, etc. │
└────────┬────────────────────────────────┘
         │ Retourne {database, created_tables, updated_tables, created_columns, updated_columns, deleted_columns, details, sql}
         ↓
Frontend Workspace
  ↓ setSqlGenerated(result.sql) → Monaco SQL affiche SQL généré depuis base logique (pas directement depuis XML)
  ↓ await fetchTables() + fetchColumns() + fetchDatabase() → arborescence Dashboard + détails base ouverte rafraîchis sans rechargement manuel
  ↓ SocketIO : Dashboard autres clients reçoit new_table/modification → toast + refresh auto
  ↓ Tables apparaissent immédiatement dans Dashboard, même après actualisation page (persistant en DB)

Export XML ensuite contient toutes infos (description, commentaire, protection, file_identifier, nullable, PK, FK, UNIQUE, DEFAULT, AUTO_INCREMENT) → réimport sans perte
```

**Corrections bugs antérieurs :**
- Avant : backend répondait succès mais tables non enregistrées car sync faisait des appels individuels create/update column sans transaction atomique et sans gestion deletion + pas de refresh Dashboard
- Maintenant : endpoint unique `/sync-xml` transaction atomique, suppression colonnes gérée, commit une fois, History/Audit/Socket, retour SQL depuis logique, frontend refetch auto

Toutes opérations (création, modification, suppression table, ajout/modif/suppression colonne, protection, import, export) sont désormais persistantes, cohérentes et immédiatement visibles.
