# XMLForge Backend - API REST Flask

Backend professionnel, modulaire et maintenable pour **XMLForge** (gestion de bases de données XML → SQL).

Frontend React existant communique via API REST.

## Stack

- Python 3.12+
- Flask 3.1
- Flask-SQLAlchemy (ORM)
- Flask-JWT-Extended (JWT)
- Flask-Bcrypt (hash password)
- Flask-CORS
- python-dotenv
- lxml (XML parsing)
- mysql-connector-python (création réelle de bases)
- Marshmallow (validation)
- SQLite pour dev/tests, MySQL pour prod

## Architecture demandée

```
backend/
├── app/
│   ├── __init__.py (create_app factory)
│   ├── config.py
│   ├── extensions.py
│   ├── app.py (wrapper)
│   ├── auth/ (decorators)
│   ├── database/ (init)
│   ├── models/
│   │   ├── user.py
│   │   ├── database.py (key_identifier XML-XXXX-XXXX-XXXX)
│   │   ├── table.py (is_protected)
│   │   ├── column.py
│   │   └── history.py
│   ├── routes/
│   │   ├── auth.py (/register, /login, /me, /logout)
│   │   ├── databases.py
│   │   ├── tables.py
│   │   ├── columns.py
│   │   ├── imports.py (/import/xml, /import/sql)
│   │   ├── exports.py (/export/xml/<id>, /export/sql/<id>)
│   │   ├── converters.py (/convert/xml-to-sql, /convert/sql-to-xml)
│   │   ├── history.py (/history)
│   │   ├── unlock.py (/unlock-table)
│   │   └── database_create.py (/database/create)
│   ├── services/ (logique métier, pas dans routes)
│   │   ├── auth_service.py
│   │   ├── database_service.py
│   │   ├── table_service.py
│   │   ├── column_service.py
│   │   ├── history_service.py
│   │   ├── import_service.py
│   │   └── export_service.py
│   ├── converters/ (réutilisables, sans Flask)
│   │   ├── xml_to_sql.py
│   │   └── sql_to_xml.py
│   └── utils/
│       ├── validators.py (Marshmallow)
│       ├── helpers.py (key generation)
│       └── responses.py (JSON cohérent)
├── uploads/
├── exports/
├── app.py (entry point)
├── config.py (compat root)
├── requirements.txt
├── .env.example
└── README.md
```

## Authentification JWT

- `POST /register` {full_name, email, password} -> 201, email unique
- `POST /login` {email, password} -> {user, access_token}
- `GET /me` (Bearer) -> user info
- `POST /logout` -> message (client supprime token)
- Password hashé Bcrypt
- JWT 24h par défaut (configurable via JWT_EXPIRES_HOURS)

Modèle User: id, full_name, email (unique), password_hash, created_at

## Bases de données

- `GET /databases` -> toutes visibles par tous (collaboratif)
- `POST /databases` {name, description} -> créée avec `key_identifier` auto `XML-9F4A-28BD-71A2`
- `PUT /databases/<id>` {name, description}
- `DELETE /databases/<id>`
- `GET /databases/<id>` -> si créateur ou X-Database-Key fourni, inclut key_identifier

Modèle Database: id, name, description, creator_id, created_at, updated_at, key_identifier (unique), tables relationship

Clé générée via `secrets.token_hex(2).upper()` x3

## Gestion collaborative & tables protégées

- Toutes les bases visibles par tous, tout le monde peut ouvrir
- Table protégée: `is_protected=true` nécessite `key_identifier` de la base pour modification/suppression/structure
- Lecture toujours autorisée
- Protection vérifiée via header `X-Database-Key` ou body `key_identifier`
- `POST /unlock-table` {table_id, key_identifier} -> vérifie clé

## Tables & Colonnes

**Table**: id, name, description, database_id, creator_id, created_at, updated_at, is_protected (+ unique constraint database_id+name)

Routes:
- `GET /tables/<database_id>` -> liste
- `POST /tables` {name, description, database_id, is_protected}
- `PUT /tables/<id>` {name?, description?, is_protected?, key_identifier?}
- `DELETE /tables/<id>?key=XML-...`

**Column**: id, name, type, length, nullable, primary_key, foreign_key, unique, auto_increment, default, creator_id, table_id, created_at

Routes:
- `GET /columns/<table_id>`
- `POST /columns` {name, type, length, nullable, primary_key, foreign_key, unique, auto_increment, default, table_id, key_identifier?}
- `PUT /columns/<id>`
- `DELETE /columns/<id>`

## Historique

Conserve toutes les actions: user qui a créé/ajouté/supprimé/modifié/importé

Modèle History: user_id, user_name (dénormalisé), action_type, element_type (base/table/colonne), element_name, description, database_id, table_id, created_at

`GET /history?limit=100&database_id=1` -> 500 max, tri desc

## Import / Export

- `POST /import/xml` : multipart file `file` ou JSON {xml, database_name}
  -> parse via `converters.parse_xml`, crée base + tables + colonnes, log historique
- `POST /import/sql` : idem avec SQL
- `GET /export/xml/<database_id>` -> génère XML via lxml
  - `?download=true` -> fichier attachment
- `GET /export/sql/<database_id>` -> XML->SQL via converter

## Converters (réutilisables, sans Flask)

**xml_to_sql.py**:
- `parse_xml(xml_content) -> List[TableDict]`
- `convert_xml_to_sql(xml_content, database_name=None) -> str`
- Supporte `<database><table>`, `<table>`, `<tables>`
- Génère `CREATE DATABASE IF NOT EXISTS`, `USE`, puis `CREATE TABLE` avec colonnes, PRIMARY KEY, FOREIGN KEY si references fourni

**sql_to_xml.py**:
- `parse_sql(sql_content) -> List[TableDict]`
- `convert_sql_to_xml(sql_content, database_name) -> str`
- Parser robuste: strip commentaires -- et /* */, split statements, extraction nom table via regex, split colonnes en gérant parenthèses DECIMAL(10,2), parse contraintes PK/FK
- Génère `<database><table><column .../></table></database>`

Tests unitaires possibles sans Flask: `python -m app.converters.xml_to_sql`

## Création réelle base MySQL

`POST /database/create` {database_id, target_database_name?}

- Exporte SQL de la base logique
- Connecte MySQL via `mysql-connector-python` avec config .env MYSQL_HOST/PORT/USER/PASSWORD
- `CREATE DATABASE IF NOT EXISTS target`, `USE`, exécute CREATE TABLEs
- Retourne {target_database, executed_statements, errors, sql_preview}
- Si MySQL non configuré, retourne erreur 500 avec SQL pour debug

.env exemple:
```
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=
```

## API Complète

```
POST   /register
POST   /login
GET    /me           (JWT)
POST   /logout       (JWT)

GET    /databases    (JWT)
POST   /databases    (JWT)
GET    /databases/<id> (JWT)
PUT    /databases/<id> (JWT)
DELETE /databases/<id> (JWT)

GET    /tables/<database_id> (JWT)
POST   /tables       (JWT)
PUT    /tables/<id>  (JWT + X-Database-Key si protégée)
DELETE /tables/<id>  (JWT + key)

GET    /columns/<table_id> (JWT)
POST   /columns      (JWT + key si table protégée)
PUT    /columns/<id> (JWT + key)
DELETE /columns/<id> (JWT + key)

POST   /import/xml   (JWT, multipart)
GET    /export/xml/<id> (JWT)
POST   /import/sql   (JWT)
GET    /export/sql/<id> (JWT)

POST   /convert/xml-to-sql (JWT) {xml, database_name?} -> {sql}
POST   /convert/sql-to-xml (JWT) {sql, database_name?} -> {xml}

POST   /database/create (JWT) {database_id, target_database_name?}

POST   /unlock-table (JWT) {table_id, key_identifier}

GET    /history?limit=100&database_id= (JWT)

GET    /health
GET    /              (liste endpoints)
```

Toutes ces routes existent aussi avec préfixe `/api/*` pour compatibilité frontend React (ex: `/api/databases` et `/databases`).

## Réponses JSON cohérentes

```
Success:
{
  "success": true,
  "message": "OK",
  "data": {...}
}

Error:
{
  "success": false,
  "message": "Erreur",
  "errors": {...}
}
```

## Validation

Marshmallow schemas dans `app/utils/validators.py` avec `unknown=INCLUDE` pour permettre `key_identifier` additionnel.

## Installation & Lancement

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # éditer MYSQL_*
# SQLite dev par défaut (xmlforge.db créé auto)
python app.py  # http://localhost:5000
# ou
flask run --host=0.0.0.0 --port=5000
```

Pour MySQL prod, mettre dans .env:
```
DATABASE_URL=mysql+mysqlconnector://user:pass@host:port/xmlforge
```

## Tests rapides

```bash
# Health
curl http://localhost:5000/health

# Register
curl -X POST http://localhost:5000/register -H "Content-Type: application/json" -d '{"full_name":"Nyx","email":"nyx@xmlforge.io","password":"secret123"}'

# Login
curl -X POST http://localhost:5000/login -H "Content-Type: application/json" -d '{"email":"nyx@xmlforge.io","password":"secret123"}'

# Utiliser token
TOKEN=eyJ...
curl -H "Authorization: Bearer $TOKEN" http://localhost:5000/databases
```

## Intégration Frontend React

Frontend existant (`xmlforge-react`) utilise actuellement mockData. Pour connecter:

1. Créer `src/services/api.js` avec axios/fetch et baseURL `http://localhost:5000` ou `/api`
2. Remplacer `useDatabases` hook par appels API:
   - `GET /databases` -> setDbs
   - `POST /databases` -> create
   - etc.
3. Ajouter `Authorization: Bearer token` depuis localStorage après login
4. Gérer `X-Database-Key` header pour tables protégées (stocker clé après unlock, afficher modal demandant clé)

Le backend supporte déjà CORS pour `http://localhost:5173`.

## Bonnes pratiques respectées

- Blueprints pour modularité
- Services contiennent toute logique métier, routes seulement validation + appel service
- Converters sans dépendance Flask, réutilisables en CLI
- Repository pattern simplifié via SQLAlchemy queries
- Validation Marshmallow, gestion erreurs centralisée, logs
- Historique complet
- Code commenté, docstrings, typage partiel
- Production ready: .env, SQLite fallback, MySQL réel, JWT expirations, CORS, max content length 16MB
```


---

# V2 - Améliorations professionnelles (sans breaking changes)

Cette version conserve **100% de compatibilité** avec la V1 (mêmes routes, mêmes Blueprints, même architecture) tout en ajoutant les métadonnées et fonctionnalités demandées.

## 1. Métadonnées enrichies

Tous les modèles possèdent désormais:
- `uuid` UUID4 unique indexé
- `comment` Text libre
- `status` ENUM ACTIVE/ARCHIVED
- `last_modified_by_id` + `last_modified_by_name`
- `created_at`, `updated_at` (colonne ajoutée pour Column)
- `creator_id` conservé

**Base:** uuid, name, description, creator, created_at, updated_at, last_modified_by, comment, status, key_identifier
**Table:** uuid, name, description, creator, created_at, updated_at, last_modified_by, comment, status, is_protected
**Colonne:** uuid, name, type, length, nullable, pk, fk, unique, ai, default, creator, created_at, updated_at, last_modified_by, comment, status

`to_dict()` retourne tous les nouveaux champs.

## 2. Commentaires

Système de commentaires libre pour base/table/colonne, enregistré en base.

Routes:
- `GET /databases/<id>/comment` - récupère commentaire
- `PUT /databases/<id>/comment` {comment}
- `GET /tables/<id>/comment` / `PUT /tables/<id>/comment`
- `GET /columns/<id>/comment` / `PUT /columns/<id>/comment`

Aussi modifiable via `PUT` général avec champ `comment` + historique COMMENTAIRE_* + audit.

## 3. État ACTIVE/ARCHIVED

- `POST /databases/<id>/archive` → status ARCHIVED
- `POST /databases/<id>/restore` → ACTIVE
- Idem pour tables et colonnes: `/tables/<id>/archive`, `/tables/<id>/restore`, `/columns/<id>/archive`, `/columns/<id>/restore`
- Lorsqu'archivé: apparaît dans interface (si include_archived=true), ne peut plus être modifié/supprimé (400), reste exportable

## 4. Dernier utilisateur

Chaque `update`, `create`, `comment`, `archive/restore` enregistre automatiquement `last_modified_by_id` + `last_modified_by_name` + `updated_at`. Frontend peut afficher "Modifié par Nyx Aujourd'hui à 14h20".

## 5. Historique V2

Modèle `History` enrichi:
- `uuid` UUID4
- `ip_address` (remote_addr / X-Forwarded-For)
- `before_data` JSON string (état avant)
- `after_data` JSON string (état après)
- `user_id`, `user_name`, `action_type`, `element_type`, `element_name`, `description`, `database_id`, `table_id`, `created_at`

`GET /history?limit&database_id` retourne maintenant `uuid`, `ip_address`, `before`, `after`, `date` alias.

## 6. Audit Log

Nouveau modèle `AuditLog` indépendant de l'historique métier:
- `uuid`, `user_id`, `user_name`, `ip_address`, `action` (CONNEXION, DECONNEXION, CREATION_BASE, SUPPRESSION, IMPORT_XML, EXPORT_SQL, CONVERSION_XML, CONVERSION_SQL, DEVERROUILLAGE_TABLE, ERREUR_*), `element_type`, `element_name`, `description`, `meta_data` JSON, `timestamp`

Routes:
- `GET /audit-logs?limit=100` (max 500)
- `GET /audit` alias

Toutes les routes importantes loguent désormais dans AuditService en plus de HistoryService.

## 7. WebSocket (Flask-SocketIO)

Ajout `Flask-SocketIO 5.3.6` + `eventlet` (threading mode).

`extensions.py` : `socketio = SocketIO(cors_allowed_origins="*", async_mode='threading')`

`app/__init__.py` : `socketio.init_app(app)` + import `app.socket_events`

`app/socket_events.py` : helpers `emit_event()`, `emit_new_database()`, `emit_new_table()`, `emit_new_column()`, `emit_modification()`, `emit_suppression()`, `emit_import_xml()`, `emit_export_sql()`

Événements émis sans modifier REST:
- `new_database`, `new_table`, `new_column`
- `modification`, `suppression`
- `import_xml`, `export_xml`, `export_sql`
- `xmlforge_event` générique {type, data}

Frontend peut écouter:
```js
import io from 'socket.io-client'
const socket = io('http://localhost:5000')
socket.on('new_database', (p)=>console.log(p))
socket.on('xmlforge_event', (e)=>console.log(e.type, e.data))
```

Lancement avec `socketio.run(app)` dans `run.py` / `app.py`.

## 8. Documentation

- `API_DOCUMENTATION.md` : toutes les routes, paramètres, body, réponses, erreurs, codes HTTP, exemples JSON, WebSocket
- `postman_collection.json` : collection Postman complète avec variables `{{baseUrl}}`, `{{token}}`, `{{db_key}}` et exemples pour toutes les routes V2 (commentaires, archive/restore, history V2, audit)

Importer dans Postman : File → Import → postman_collection.json

## 9. Qualité - Aucun breaking change

- Toutes les anciennes routes conservées (`/register`, `/databases`, etc.) + clones `/api/*`
- Nouveaux champs ajoutés avec defaults, anciens champs conservés
- `include_archived` query param optionnel, défaut true pour ne pas cacher données existantes
- Services et Blueprints conservés, logique ajoutée dans services existants, pas dans routes
- Converters inchangés et toujours sans dépendance Flask
- SQLAlchemy conservé, migration V2 légère via `_migrate_v2()` qui fait ALTER TABLE ADD COLUMN si colonne manquante (SQLite dev)

Testé: anciennes routes + nouvelles comment/archive/restore/history V2/audit/converters/import/export → tous OK, sans breaking change.

Lancement: `python run.py` (SocketIO) ou `python app.py`
