# PHASE 6I — Audit des dépendances Data Plane (cartographie)

**Date** : 2026-09-07 · **Statut** : audit préalable aux modifications

## 1. Cartographie des dépendances SQLite du Data Plane

| Composant | Fichier | Rôle Data Plane | Dépendance ORM/SQLite | Chemin XML normal ? |
|---|---|---|---|---|
| `XmlEngineService` | app/xml_engine/service.py | orchestrateur XML (mutate/read/ensure/delete) | `Database` (chemins), `Table`/`Column`/`TableRow` (`_sync_catalog`), projection | **partiel** (mutate écrit XML mais synchrone ORM + projection) |
| `DatabaseService` | app/services/database_service.py | CRUD bases (métadonnées + création du fichier XML) | `Database.query`/`db.session` | **non** (ligne ORM = pont) |
| `TableService` | app/services/table_service.py | CRUD tables + protection | `Table.query`, `Database` | **non** (résolution ORM, mutation via XmlEngineService) |
| `ColumnService` | app/services/column_service.py | CRUD colonnes | `Column.query`, `Table` | **non** |
| `RowService` | app/services/row_service.py | CRUD lignes (facade REST) | `Table`, `TableRow` | partiel (repli XML sur ProjectionError) |
| `SchemaService` | app/services/schema_service.py | introspection schéma | `Database` (résolution), lecture XML | partiel (schéma lu depuis XML) |
| `PermissionService` | app/services/permission_service.py | ACL (table part) | `Table` (table_access/can_table/grant_table) | **non** (résolution table ORM) |
| `UnlockService` | app/services/unlock_service.py | déverrouillage de tables protégées | `Table`, `Database`, `TableUnlock` | **non** |
| `QueryService` | app/query/service.py | moteur legacy SELECT/projection + DML/DDL | `Database`, `Table`, `TableRow`, projection `connect_projection` | **non** |
| `XmlQueryService` | app/query/xml_query_service.py | moteur XML REST/TCP | `Database`, `Table`, `TableRow` (résolution) | partiel (lit XML, résout via ORM) |
| `sync_service` | app/services/sync_service.py | import XML complet | `Database`, `Table` | **non** |
| `export/import_service` | app/services/export_service.py, import_service.py | export SQL/XML, import | `Database`, `Table` | **non** (legacy) |
| `tcp_server` | app/tcp/tcp_server.py | sélection base + unlock | `Database.query`, `Table.query` | **non** |
| `auth/decorators` | app/auth/decorators.py | protection table par clé | `Table.query`, `Database.query` | **non** |
| `routes/exports.py` | app/routes/exports.py | export XML/SQL table | `Table.query`, `Database.query` | **non** (legacy) |
| `document_from_catalog` | app/xml_engine/document.py | migration SQLAlchemy→XML | `TableRow` | legacy |
| JWT loader / logout | app/__init__.py, routes/auth.py | révocation de token | `RevokedToken` | à rendre volatil en mode XML |
| `create_app` | app/__init__.py | init db + migrations + projection | `db.create_all`, `schema_migrations`, `initialize_all` | à ignorer en mode XML |

## 2. Qui fait quoi (lecture/écriture)

- **CREATE DATABASE** : DatabaseService.create → ligne ORM + `ensure_storage` (XML) + miroir catalog.xml.
- **DELETE DATABASE** : DatabaseService.delete → ORM + `delete_storage`.
- **CREATE/ALTER/DROP TABLE** : TableService/QueryService DDL → `XmlEngineService.mutate` (+ `_sync_catalog`).
- **COLONNES** : ColumnService → `mutate` + relecture `Column.query`.
- **INSERT/SELECT/UPDATE/DELETE lignes** : QueryService/XmlQueryService/RowService ; SELECT via projection SQLite (legacy) ou XmlNativeEngine.
- **SCHÉMA** : SchemaService (déjà XML pour le contenu).
- **PERMISSIONS table** : PermissionService (résolution `Table` ORM).
- **RELATIONS** : XmlNativeEngine (PK/FK/UNIQUE/NOT NULL/DEFAULT/AUTO_INCREMENT) — déjà sans SQLite.
- **PROJECTION** : projection.py (reconstruction SQLite) — optionnelle.

## 3. Conclusion de l'audit

- Le **moteur XML** (`XmlNativeEngine`, `xml_executor`) est déjà **sans SQLite** : il suffit de le brancher.
- Les **points de résolution** (`Database`, `Table`) et le **pont ORM** (`_sync_catalog`, projection, `create_all`) sont les seules vraies dépendances à découpler.
- Stratégie 6I : ajouter `DATA_BACKEND` (sqlite|xml) ; en mode `xml`, **SQLAlchemy n'est pas initialisé**, les résolutions passent par `catalog.xml` (bases) et le document XML (tables), et les mutations passent par `XmlNativeEngine` + écriture atomique sans `_sync_catalog`.
