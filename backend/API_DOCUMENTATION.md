# XMLForge Backend V2 - API Documentation

Base URL: `http://localhost:5000`  
Préfixe alternatif: `/api` (ex: `/api/databases` et `/databases` fonctionnent identiquement)

Toutes les routes protégées nécessitent header: `Authorization: Bearer <JWT>`

Clé pour tables protégées: header `X-Database-Key: XML-XXXX-XXXX-XXXX` ou body `key_identifier`

---

## Authentification

### POST /register
Inscription nouvel utilisateur.

**Body:**
```json
{
  "full_name": "Nyx Dev",
  "email": "nyx@xmlforge.io",
  "password": "secret123"
}
```
- full_name: 2-120 chars, requis
- email: format email, unique, requis
- password: 6-128 chars, requis

**Réponses:**
- 201: `{success:true, data:{id, full_name, email, created_at}, message:"Inscription réussie"}`
- 400: email déjà utilisé / validation

### POST /login
Connexion.

**Body:**
```json
{"email":"nyx@xmlforge.io","password":"secret123"}
```

**Réponse 200:**
```json
{
  "success": true,
  "data": {
    "user": {"id":1,"full_name":"Nyx Dev","email":"...","created_at":"..."},
    "access_token": "eyJ..."
  }
}
```
- 401: email ou mot de passe incorrect

### GET /me
Infos utilisateur courant. JWT requis.

**Headers:** `Authorization: Bearer <token>`

**Réponse 200:** user dict
- 404: utilisateur introuvable

### POST /logout
Déconnexion (stateless, client supprime token). JWT requis. Audit log DECONNEXION.

**Réponse 200:** message déconnexion

---

## Bases de données - Métadonnées V2

**Modèle Database V2:**
```json
{
  "id": 1,
  "uuid": "8c000ed1-9b6a-4cbf-a1c5-fcaa05ab1229",
  "name": "Bibliothèque",
  "description": "Base exemple",
  "creator_id": 1,
  "creator_name": "Nyx Dev",
  "created_at": "2024-01-01T10:00:00",
  "updated_at": "2024-01-01T12:00:00",
  "last_modified_by_id": 2,
  "last_modified_by": "Lily",
  "comment": "Base critique prod",
  "status": "ACTIVE", // ACTIVE / ARCHIVED
  "tables_count": 5,
  "key_identifier": "XML-9F4A-28BD-71A2" // inclus seulement si créateur ou si X-Database-Key fourni et valide
}
```

### GET /databases
Liste toutes les bases visibles (collaboratif).

**Query:** `?include_archived=true|false` (default true)

**Headers:** JWT

**Réponse 200:** array databases (sans key)

### POST /databases
Créer base.

**Body:**
```json
{"name":"Bibliothèque","description":"Gestion livres","comment":"Base initiale"}
```
- name requis 1-120
- description optionnel
- comment optionnel V2

**Réponse 201:** database avec uuid, comment, status ACTIVE, key_identifier inclus + last_modified_by

**Historique:** log IP, before null, after full dict. **Audit:** CREATION_BASE. **Socket:** new_database

### GET /databases/<id>
Détail base.

**Headers:** JWT + optionnel `X-Database-Key` ou `?key=XML-...` pour inclure key_identifier

**Réponse 200:** database dict

**Erreur 404:** introuvable

### PUT /databases/<id>
Modifier base. Bloqué si ARCHIVED.

**Body:** `{name?, description?, comment?}`

**Réponse 200:** updated + history before/after + audit MODIFICATION_BASE + socket modification

**Erreur 400:** archivée

### DELETE /databases/<id>
Supprimer. Bloqué si ARCHIVED.

**Réponse 200:** supprimée + history + audit SUPPRESSION_BASE + socket suppression

### POST /databases/<id>/archive
Archiver.

**Réponse 200:** status ARCHIVED. Bloque futures modifications/suppressions. Export reste possible.

**Audit:** ARCHIVAGE_BASE

### POST /databases/<id>/restore
Restaurer ACTIVE.

### GET /databases/<id>/comment
Récupérer commentaire seul.

**Réponse 200:** `{comment, database_id, uuid}`

### PUT /databases/<id>/comment
Mettre à jour commentaire.

**Body:** `{"comment":"Nouveau commentaire"}`

**Réponse 200:** commentaire mis à jour + history COMMENTAIRE_BASE + audit

---

## Tables

**Modèle Table V2:**
```json
{
  "id":1,
  "uuid":"...",
  "name":"client",
  "description":"",
  "database_id":1,
  "creator_id":1,
  "creator_name":"Nyx",
  "created_at":"...",
  "updated_at":"...",
  "last_modified_by_id":2,
  "last_modified_by":"Lily",
  "comment":"Table contenant les informations des clients.",
  "status":"ACTIVE",
  "is_protected":true,
  "columns_count":6
}
```

### GET /tables/<database_id>
Liste tables d'une base. `?include_archived=true|false`

**Réponse 200:** array tables

### POST /tables
Créer table.

**Body:**
```json
{"name":"client","description":"","database_id":1,"is_protected":false,"comment":"Table clients"}
```
- name requis, unique par database
- database_id requis
- is_protected bool default false
- comment optionnel V2

**Réponse 201:** table dict + history + audit CREATION_TABLE + socket new_table

**Erreur 400:** base archivée ou table existe déjà

### PUT /tables/<id>
Modifier table. Nécessite clé si protégée.

**Headers:** optionnel `X-Database-Key`

**Body:** `{name?, description?, is_protected?, comment?, key_identifier?}`

**Réponse 200:** updated

**Erreurs:** 403 protégée sans clé / clé invalide, 400 archivée, 404 introuvable

### DELETE /tables/<id>
Supprimer. Nécessite clé si protégée. Bloqué si archivée.

**Query:** `?key=XML-...` ou header `X-Database-Key` ou body `key_identifier`

**Réponse 200**

### POST /tables/<id>/archive /restore
Archiver/restaurer table.

### GET /tables/<id>/comment / PUT /tables/<id>/comment
Commentaire dédié table.

---

## Colonnes

**Modèle Column V2:**
```json
{
  "id":1,
  "uuid":"...",
  "name":"email",
  "type":"VARCHAR",
  "length":"255",
  "nullable":false,
  "primary_key":false,
  "foreign_key":false,
  "unique":true,
  "auto_increment":false,
  "default":null,
  "creator_id":1,
  "created_at":"...",
  "updated_at":"...",
  "last_modified_by_id":1,
  "last_modified_by":"Nyx",
  "comment":"Ne jamais supprimer",
  "status":"ACTIVE",
  "table_id":1
}
```

### GET /columns/<table_id>
`?include_archived`

### POST /columns
Créer colonne. Vérifie protection table parente.

**Body:**
```json
{
  "name":"email",
  "type":"VARCHAR",
  "length":"255",
  "nullable":false,
  "primary_key":false,
  "foreign_key":false,
  "unique":true,
  "auto_increment":false,
  "default":null,
  "table_id":1,
  "comment":"Email unique",
  "key_identifier":"XML-...-...-..." // si table protégée
}
```

**Réponse 201**

### PUT /columns/<id> / DELETE /columns/<id>
Même logique protection + archivé.

### POST /columns/<id>/archive /restore
### GET /columns/<id>/comment / PUT /columns/<id>/comment

---

## Import / Export

### POST /import/xml
Importer XML et créer base + tables + colonnes.

**Headers:** JWT, `Content-Type: multipart/form-data` ou `application/json`

**Body multipart:**
- file: fichier .xml
- database_name: optionnel
- description: optionnel
- comment: optionnel V2

**Body JSON alternatif:**
```json
{"xml":"<database name=\"test\">...</database>","database_name":"test","description":"Import","comment":""}
```

**Réponse 201:** database avec key_identifier + history IP + audit IMPORT_XML + socket import_xml

**Erreurs 400:** XML invalide / parsing

### POST /import/sql
Idem avec SQL.

**Body:** file ou `{sql:"CREATE TABLE...", database_name}`

**Réponse 201**

### GET /export/xml/<database_id>
Génère XML depuis modèles. Exportable même si ARCHIVED.

**Query:** `?download=true` → fichier attachment `database_<id>.xml`, mimetype `application/xml`

**Réponse 200 sans download:**
```json
{"success":true,"data":{"xml":"<?xml version=\"1.0\"...","database_id":1}}
```

**Audit:** EXPORT_XML + socket export_xml

### GET /export/sql/<database_id>
Génère XML puis convertit via `xml_to_sql`. `?download=true` → .sql

**Audit:** EXPORT_SQL + socket export_sql

---

## Converters (réutilisables, sans Flask)

### POST /convert/xml-to-sql
Conversion sans persistance.

**Body:**
```json
{"xml":"<table name=\"client\">...</table>","database_name":"ma_base"}
```

**Réponse 200:** `{"sql":"CREATE TABLE..."}`
**Audit:** CONVERSION_XML
**Erreur 400:** XML invalide

### POST /convert/sql-to-xml
**Body:** `{"sql":"CREATE TABLE client (...);","database_name":"ma_base"}`

**Réponse 200:** `{"xml":"<?xml..."}`
**Audit:** CONVERSION_SQL

---

## Création réelle MySQL

### POST /database/create
Exécute SQL généré sur MySQL réel via `mysql-connector-python`.

**Body:**
```json
{"database_id":1,"target_database_name":"ma_base_prod"}
```
- database_id requis
- target_database_name optionnel (sinon nom logique nettoyé)

**Réponse 200:**
```json
{
  "target_database":"ma_base_prod",
  "executed_statements": 5,
  "errors":[],
  "sql_preview":"CREATE TABLE..."
}
```

**Erreur 500:** MySQL non configuré / erreur connexion. Vérifier `.env`:
```
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=
```

**Audit:** CREATION_REELLE_BASE ou ERREUR_CREATION_REELLE

---

## Déverrouillage table protégée

### POST /unlock-table
Vérifie clé.

**Body:**
```json
{"table_id":1,"key_identifier":"XML-9F4A-28BD-71A2"}
```

**Réponse 200:** `{unlocked:true, table_id:1}` + audit DEVERROUILLAGE_TABLE

**Erreur 403:** clé invalide → audit ERREUR_DEVERROUILLAGE

---

## Historique V2

### GET /history
Journal métier enrichi.

**Query:** `?limit=100` (max 500), `?database_id=1`

**Réponse 200:**
```json
{
  "data":[
    {
      "id":1,
      "uuid":"...",
      "user_id":1,
      "user_name":"Nyx",
      "action_type":"a créé",
      "element_type":"base",
      "element_name":"Bibliothèque",
      "description":"Base créée",
      "ip_address":"127.0.0.1",
      "before":null,
      "after":"{\"id\":1,...}",
      "database_id":1,
      "table_id":null,
      "created_at":"2024-01-01T10:00:00",
      "date":"2024-01-01T10:00:00"
    }
  ]
}
```

Champs V2: uuid, ip_address, before (JSON string), after (JSON string)

---

## Audit Log (indépendant)

### GET /audit-logs
Audit technique.

**Query:** `?limit=100` max 500

**Réponse 200:**
```json
{
  "data":[
    {
      "id":1,
      "uuid":"...",
      "user_id":1,
      "user_name":"Nyx",
      "ip_address":"127.0.0.1",
      "action":"CONNEXION", // CONNEXION, DECONNEXION, CREATION_BASE, SUPPRESSION, IMPORT_XML, EXPORT_SQL, CONVERSION_XML, CONVERSION_SQL, DEVERROUILLAGE_TABLE, ERREUR_*
      "element_type":"auth|base|table|colonne|converter|system",
      "element_name":"nyx@xmlforge.io",
      "description":"Connexion nyx@xmlforge.io",
      "meta_data":"{\"user_id\":1}",
      "timestamp":"2024-01-01T10:00:00"
    }
  ]
}
```

Alias: `GET /audit`

---

## WebSocket (Flask-SocketIO)

**Connexion:** `io.connect('http://localhost:5000')` (socket.io-client)

**Events émis par backend (sans modifier REST):**
- `new_database` {database, by}
- `new_table` {table, by}
- `new_column` {column, by}
- `modification` {element_type, element, by}
- `suppression` {element_type, element_name, database_id, by}
- `import_xml` {database, by}
- `export_sql` {database_id, by}
- `export_xml` {database_id, by}
- `xmlforge_event` {type, data} – événement générique pour tous

Frontend peut écouter:
```js
socket.on('new_database', (payload)=>{ console.log(payload) })
socket.on('xmlforge_event', (e)=>{ console.log(e.type, e.data) })
```

Serveur lancé via `socketio.run(app)` dans `run.py` / `app.py` (threading mode, pas besoin eventlet en dev).

---

## Erreurs communes

- 400 Validation: `{success:false, message:"Validation échouée", errors:{field:["msg"]}}`
- 401 JWT manquant/invalide: `{"msg":"Missing Authorization Header"}`
- 403 Table protégée: `{"success":false,"message":"Table 'client' protégée. Clé_identifiant requise."}`
- 403 Clé invalide
- 400 Archivée: `{"message":"Base 'X' archivée, modification impossible."}`
- 404 Introuvable
- 500 Erreur serveur / MySQL

## Codes HTTP

- 200 OK (GET, PUT, POST unlock, POST archive/restore)
- 201 Created (POST create)
- 400 Bad Request (validation, archivée, XML invalide)
- 401 Unauthorized (JWT)
- 403 Forbidden (protégée sans clé)
- 404 Not Found
- 500 Internal / MySQL error

## Compatibilité frontend React

- Toutes anciennes routes conservées sans préfixe (`/databases`) + clones `/api/databases` → frontend peut appeler indifféremment
- Nouveaux champs `uuid, comment, status, last_modified_by, updated_at` ajoutés aux `to_dict()` → non cassant, frontend ignore extra fields
- `include_archived` param optionnel, défaut true pour ne pas cacher données existantes
- CORS configuré pour `http://localhost:5173` (Vite)
- Token stocké `localStorage xmlforge_token`, clé base `xmlforge_db_key` pour header `X-Database-Key`

## Lancement

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
python run.py # ou python app.py avec socketio.run
# http://localhost:5000/health
```

## Collection Postman

Voir fichier `postman_collection.json` à la racine backend.
Importer dans Postman → toutes les routes pré-configurées avec exemples body.

---

## Synchronisation XML - Source de vérité V3

### POST /databases/<id>/sync-xml
**Nouveauté V3** : XML devient source de vérité. Synchronise base logique à partir du XML.

**URL:** `/databases/<int:database_id>/sync-xml` + `/api/databases/<int:database_id>/sync-xml`

**Alias:** `POST /databases/<id>/sync`

**Headers:** 
- `Authorization: Bearer <token>` JWT requis
- `X-Database-Key: XML-...` optionnel si tables protégées concernées

**Body:**
```json
{
  "xml": "<database name=\"Bibliothèque\"><table name=\"client\" protected=\"true\" file_identifier=\"XML-9F4A-...\" comment=\"Table clients\"><column name=\"id\" type=\"INT\" length=\"11\" primary_key=\"true\" auto_increment=\"true\" nullable=\"false\" comment=\"PK\"/><column name=\"email\" type=\"VARCHAR\" length=\"255\" unique=\"true\" comment=\"Email unique\"/></table></database>",
  "key_identifier": "XML-... (optionnel, clé base ou file_identifier pour tables protégées)"
}
```
- `xml` requis, string XML conforme spec V3 (voir XMLForge XML Specification)

**Logique backend V3 :**
- Parse XML complet via lxml
- Si table n'existe pas → créer (uuid, description, protected, file_identifier, comment, status)
- Si table existe → maj description, protected, file_identifier, comment, status (check protection besoin clé)
- Si colonne n'existe pas → créer
- Si colonne existe → maj type, length, nullable, pk, fk, unique, ai, default, comment, references
- Si colonne supprimée du XML → la supprimer de la structure logique (spec)
- Sauvegarde Models, History (IP, before/after JSON, uuid), Audit SYNC_XML, Socket emit_modification
- Génère SQL depuis base logique (pas directement depuis XML) via export_service -> xml_to_sql

**Réponse 200:**
```json
{
  "success": true,
  "message": "Synchronisation XML réussie - base logique mise à jour, SQL régénéré depuis structure enregistrée",
  "data": {
    "database": {"id":1, "name":"Bibliothèque", "uuid":"...", "key_identifier":"XML-..."},
    "created_tables": 1,
    "updated_tables": 1,
    "created_columns": 2,
    "updated_columns": 1,
    "deleted_columns": 1,
    "details": ["Table mise à jour: client", "  Colonne mise à jour: client.id", "  Colonne créée: client.nom", "  Colonne supprimée: client.email"],
    "sql": "CREATE DATABASE IF NOT EXISTS `Bibliothèque`;\nUSE ...\nCREATE TABLE `client` (...);"
  }
}
```

**Erreurs:**
- 400 XML invalide, aucune table trouvée, base archivée
- 404 Base introuvable
- 403 Clé invalide pour table protégée

**Flux complet V3 :**
```
XML (MonacoEditor)
↓ POST /databases/<id>/sync-xml {xml}
Backend parse + sync tables/colonnes + delete colonnes supprimées + commit + History/Audit/Socket
↓ Génère SQL depuis base logique (export -> xml_to_sql)
Retourne {database, created_tables, updated_tables, created_columns, updated_columns, deleted_columns, details, sql}
↓ Frontend setSqlGenerated(sql) + fetchTables() + fetchColumns() + fetchDatabase() sans rechargement manuel + toast
↓ Dashboard rafraîchi automatiquement via SocketIO modification event
SQL affiché vient toujours de la base logique, jamais directement du XML brut
```

**Exemple XML V3 complet avec protection via file_identifier :**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<database name="Bibliothèque" description="Gestion bibliothèque" comment="Base principale" status="ACTIVE">
  <table name="client" description="Clients" comment="Table contenant les informations des clients." protected="true" file_identifier="XML-9F4A-28BD-71A2" status="ACTIVE">
    <column name="id" type="INT" length="11" nullable="false" primary_key="true" auto_increment="true" comment="PK - ne jamais supprimer" />
    <column name="nom" type="VARCHAR" length="100" nullable="false" comment="Nom complet" />
    <column name="email" type="VARCHAR" length="255" nullable="false" unique="true" comment="Ne jamais supprimer cette colonne - email unique" />
  </table>
</database>
```

**Protection :** Si table a `protected="true" file_identifier="XML-9F4A-..."`, backend stocke `is_protected=true` + `file_identifier`. Toute modif/suppr/add colonne sur cette table nécessite clé = file_identifier ou clé base. Frontend ouvre modal 🔒 demandant clé, mémorisée sessionStorage.

---

## XMLForge XML Specification V3 (résumé)

Voir `BACKEND_DOCUMENTATION.md` section "XMLForge XML Specification V3" + fichier `xmlforge.xsd` pour XSD complet validant :
- DATABASE: name requis, description, comment, uuid, status ACTIVE/ARCHIVED
- TABLE: name requis, description, protected bool, file_identifier 4-64 chars, comment, archived bool, status, uuid
- COLUMN: name requis, type requis, length, nullable, primary_key, foreign_key, references (table(col)), unique, auto_increment, default, comment, uuid, status, archived

Export XML contient toutes infos (description, commentaire, protection, file_identifier, nullable, PK, FK, UNIQUE, DEFAULT, AUTO_INCREMENT) → réimport sans perte.

XSD : `backend/xmlforge.xsd` et `backend/app/static/xmlforge.xsd`
```python
from lxml import etree
xsd = etree.parse('xmlforge.xsd')
schema = etree.XMLSchema(xsd)
xml = etree.parse('export.xml')
schema.assertValid(xml)
```
