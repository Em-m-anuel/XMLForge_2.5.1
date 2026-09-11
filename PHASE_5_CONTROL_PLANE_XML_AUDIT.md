# PHASE 5 — Audit & Conception du Control Plane XML

**Projet** : XMLForge
**Date de l'audit** : 2026-09-06
**Périmètre** : AUDIT + CONCEPTION uniquement. **Aucune migration, aucune suppression de SQLite, aucune modification destructive n'a été effectuée.**
**Méthode** : lecture du code réel (`backend/app/**`, modèles, services, routes, moteurs XML/SQLite, serveur TCP, tests) + inspection du fichier SQLite réel (`backend/xmlforge.db`). Aucune hypothèse non vérifiée n'est présentée comme un fait.

> Conventions de fiabilité utilisées dans ce document :
> - **Vérifié** : constaté dans le code ou dans la base réelle.
> - **Documentation ≠ implémentation actuelle** : annoncé dans un document, absent du code.
> - **Implémentation actuelle non documentée** : présent dans le code, absent des docs.
> - **À confirmer** : ne peut pas être tranché par le seul code (décision produit).

---

## 1. Résumé exécutif

XMLForge repose aujourd'hui sur **deux stockages SQLite distincts** qu'il ne faut pas confondre :

1. **Le Control Plane** (`backend/xmlforge.db`, via SQLAlchemy ORM) — 14 tables : utilisateurs, rôles, permissions (ACL), catalogue des bases/tables/colonnes/lignes, historique, audit, déverrouillages, credentials TCP, tokens révoqués, registre de migrations. **C'est lui qui est audité dans cette phase.**
2. **La projection de données** (`backend/data/projections/<id>_<slug>.sqlite`, via `sqlite3`) — reconstruction relationnelle des données métier. **Déjà rendue optionnelle en Phase 4** (`SYNC_SQLITE_PROJECTION=false`) : le mode « XML pur » n'en a plus besoin.

L'audit établit les faits structurants suivants (tous vérifiés dans le code) :

- **Le Data Plane XML est déjà la source de vérité des données métier.** Les tables SQLite `tables`, `columns` et `table_rows` ne sont **pas** une source indépendante : elles sont re-synchronisées depuis le XML par `XmlEngineService._sync_catalog()` à chaque mutation, et le XML est « autoritaire » au démarrage (`ensure_storage` lit le XML s'il existe).
- **Le Control Plane SQLAlchemy est, lui, une vraie source de vérité** pour : utilisateurs, rôles, ACL/grants, ownership, audit, historique, unlocks, credentials TCP, tokens révoqués. **Il n'a aucun équivalent XML aujourd'hui.** C'est l'objet de la migration future.
- **La table `databases` est hybride** : elle mélange (a) des références de control plane (`xml_file_path`, `projection_path`, `document_version`, `xml_checksum`, `sync_status`, `owner_id`, `scope`) et (b) des métadonnées également présentes dans le document XML (`name`, `description`, `comment`, `status`). Cette duplication est aujourd'hui **tolérée et arbitrée** : le XML gagne sur les données, le catalogue gagne sur l'ACL/ownership.
- **Les mécanismes de fiabilité nécessaires au futur Control Plane XML existent déjà et sont éprouvés côté Data Plane** : écriture atomique (`atomic_write`), verrou de fichier (`database_lock` : `fcntl.flock` + `RLock`), snapshot/restore (rollback), version de document + contrôle optimiste (`expected_version`/`If-Match` → `ConflictError` 409), checksum SHA-256, validation XSD. Ils peuvent être **réutilisés tels quels** pour le Control Plane.

**Conclusion** : le futur Control Plane XML est techniquement réalisable **sans réinventer l'infrastructure** (réutilisation de `storage.py` + `document.py`), à condition de (1) figer une stratégie d'IDs stables, (2) séparer clairement sécurité/ACL (source de vérité Control Plane) des données métier (source de vérité Data Plane), et (3) traiter le volume de l'audit par rotation de fichiers.

---

## 2. Architecture actuelle (vérifiée)

```
                        XMLFORGE (Flask 5000 + TCP 3307)
                                      │
        ┌─────────────────────────────┴─────────────────────────────┐
        │                                                           │
  CONTROL PLANE (SQLAlchemy → backend/xmlforge.db)            DATA PLANE (XML canonique)
        │                                                           │
  users · roles · database_permissions                        data/xml/<id>_<slug>.xml
  table_permissions · databases · tables                      (tables, colonnes, contraintes,
  columns · table_rows · history · audit_logs                 index, lignes)
  table_unlocks · tcp_credentials · revoked_tokens                  │
  schema_migrations                                           XmlEngineService.mutate()
        │                                                     (source de vérité)
        │  Lecture/écriture par services                            │
        │  auth_service · user_service · permission_service    ┌────┴─────┐
        │  audit_service · history_service · unlock_service    │          │
        │  tcp_credential_service · database_service…          ▼          ▼
        │                                             Moteur XML natif   Projection SQLite
        │                                             (XmlNativeEngine)  (data/projections/*.sqlite)
        │                                                                [OPTIONNELLE Phase 4]
        └─────────────── REST API (/ + /api/*) + TCP (3307) ◄────────────┘
                        (même moteur, mêmes permissions)
```

**Constats vérifiés** :
- Le catalogue (`tables`, `columns`, `table_rows`) est une **projection** du XML, re-synchronisée par `_sync_catalog` (app/xml_engine/service.py).
- Le serveur TCP (`app/tcp/tcp_server.py`) réutilise **les mêmes services** que REST : `TcpCredentialService.authenticate`, `PermissionService`, `UnlockService`, `QueryService`/`XmlQueryService`. Il n'existe **aucun** chemin de permission propre au TCP.
- SocketIO (`socket_events.py`) est en mémoire, sans dépendance SQLite.

---

## 3. Inventaire complet SQLite / SQLAlchemy

### 3.1 Les 14 tables du Control Plane (relevé réel de `xmlforge.db`, 2026-09-06)

| # | Table | Rôle | Source de vérité actuelle | Plan |
|---|-------|------|---------------------------|------|
| 1 | `users` | comptes XMLForge | Control Plane | Control Plane |
| 2 | `roles` | rôles applicatifs (admin, user) | Control Plane | Control Plane |
| 3 | `database_permissions` | grants (ACL) par base | Control Plane | Control Plane |
| 4 | `table_permissions` | surcharges d'ACL par table | Control Plane | Control Plane |
| 5 | `databases` | catalogue bases + références XML + ownership | **hybride** (voir §18) | Control Plane (réduit) |
| 6 | `tables` | catalogue tables (projection XML) | **Data Plane (XML)** | à supprimer du CP |
| 7 | `columns` | catalogue colonnes (projection XML) | **Data Plane (XML)** | à supprimer du CP |
| 8 | `table_rows` | lignes (projection XML, JSON) | **Data Plane (XML)** | à supprimer du CP |
| 9 | `history` | historique métier (V2 : before/after JSON) | Control Plane | Control Plane |
| 10 | `audit_logs` | audit de sécurité (connexions, actions) | Control Plane | Control Plane |
| 11 | `table_unlocks` | déverrouillages de tables protégées | Control Plane | Control Plane |
| 12 | `tcp_credentials` | credentials du serveur TCP | Control Plane | Control Plane |
| 13 | `revoked_tokens` | JWT révoqués (logout) | Control Plane | Control Plane |
| 14 | `schema_migrations` | registre de version du schéma | Control Plane (technique) | Control Plane (ou supprimé) |

### 3.2 Accès directs `sqlite3` (hors ORM)

| Fichier | Usage | Plan |
|---------|-------|------|
| `app/query/sqlite_runtime.py` | `connect_projection`, retries, registre de handles | moteur legacy — à supprimer en Phase 6+ |
| `app/xml_engine/projection.py` | `build_projection` (reconstruction SQLite) | optionnel (déjà désactivable) |
| `app/xml_engine/storage.py` | sidecars `-wal`/`-shm`, `commit_pair` | optionnel en mode XML pur |

### 3.3 Fichiers/points utilisant `db.session` ou `Model.query` (relevé exhaustif)

- **Control Plane (à migrer vers XML)** : `auth_service.py`, `user_service.py`, `permission_service.py`, `audit_service.py`, `history_service.py`, `unlock_service.py`, `tcp_credential_service.py`, `app/__init__.py` (create-app, JWT loader, create-admin), `auth/decorators.py`, `schema_migrations.py`.
- **Data Plane (catalogue — à déréférencer à terme)** : `database_service.py`, `table_service.py`, `column_service.py`, `row_service.py`, `schema_service.py`, `sync_service.py`, `query/service.py`, `query/xml_query_service.py`, `xml_engine/service.py`.
- **Frontières mixtes** : `routes/auth.py`, `routes/tcp.py` (logout → `RevokedToken` ; show-password → `User`).

---

## 4. Cartographie des dépendances (tableau demandé)

| Élément | Fichier | Type | Données (colonnes clés) | Relations/FK | Lectures | Écritures | Criticité | Migration XML |
|---|---|---|---|---|---|---|---|---|
| `User` | app/models/user.py | modèle ORM | id, full_name, email (unique), password_hash, is_active, last_login, token_version, role_id | FK roles.id | auth, user_service, permission_service, JWT loader, toutes les routes | AuthService.register/login, UserService | **CRITIQUE** | OUI (users.xml) |
| `Role` | app/models/role.py | modèle ORM | id, name (unique), description, created_at | users.role_id | user.is_admin(), AuthService, UserService | migration V5 (seed admin/user), create-admin | **CRITIQUE** | OUI (roles.xml) |
| `DatabasePermission` | app/models/database_permission.py | modèle ORM (ACL) | id, database_id, user_id, can_read/write/ddl/admin, granted_by_id | FK databases.id, users.id ; unique(database_id,user_id) | PermissionService (database_access, can_database, list) | grant_database/revoke_database | **CRITIQUE** | OUI (grants.xml) |
| `TablePermission` | app/models/table_permission.py | modèle ORM (ACL) | id, table_id, user_id, can_read/write/ddl/admin, granted_by_id | FK tables.id, users.id ; unique(table_id,user_id) | PermissionService (table_access, can_table) | grant_table/revoke_table | **CRITIQUE** | OUI (grants.xml) |
| `Database` | app/models/database.py | modèle ORM hybride | id, uuid, name, description, owner_id, scope, xml_file_path, projection_path, document_version, xml_checksum, sync_status, key_identifier (unique), status | FK users.id (creator, owner, last_modifier) ; rel tables, permissions | database_service, permission_service, TCP select, query, export/import | database_service.create/update/delete/archive | **CRITIQUE** (référence CP) | OUI (catalog.xml, réduit) |
| `Table` | app/models/table.py | modèle ORM = projection XML | id, uuid, name, description, database_id, is_protected, file_identifier, status | FK databases.id, users.id ; unique(database_id,name) | table_service, permission_service, query (resolve), unlock | `_sync_catalog` (depuis XML) | TRANSITOIRE | NON (découverte Data Plane) |
| `Column` | app/models/column.py | modèle ORM = projection XML | id, uuid, name, type, length, nullable, pk, fk, unique, auto_increment, default_value, references, on_delete/update, indexed, status | FK tables.id, users.id ; unique(table_id,name) | column_service, schema (partiel) | `_sync_catalog` (depuis XML) | TRANSITOIRE | NON (découverte Data Plane) |
| `TableRow` | app/models/table_row.py | modèle ORM = projection XML | id, uuid, table_id, data_json (JSON) | FK tables.id, users.id | row_service (catalogue id/created_at) | `_sync_catalog` (depuis XML) | TRANSITOIRE | NON (découverte Data Plane) |
| `History` | app/models/history.py | modèle ORM | id, uuid, user_id, user_name, action_type, element_type, element_name, description, ip_address, before_data, after_data, database_id, table_id | FK users.id, databases.id, tables.id | history_service.get_all (route /history admin) | HistoryService.log (tous services) | MOYENNE | OUI (history.xml, rotatif) |
| `AuditLog` | app/models/audit_log.py | modèle ORM | id, uuid, user_id (nullable), user_name, ip_address, action, element_type, element_name, description, meta_data (JSON), timestamp | FK users.id (nullable) | audit_service.get_all (route /audit-logs admin) | AuditService.log (tous services + TCP) | MOYENNE (volume) | OUI (audit.xml, rotatif) |
| `TableUnlock` | app/models/table_unlock.py | modèle ORM | id, user_id, table_id, unlocked_at, expires_at | FK users.id, tables.id ; unique(user_id,table_id) | UnlockService.is_unlocked/list | unlock_table, clear (login/logout) | MOYENNE (éphémère) | OUI (unlocks.xml, volatil) |
| `TcpCredential` | app/models/tcp_credential.py | modèle ORM | id, user_id (unique), tcp_username, tcp_password (bcrypt), tcp_host, tcp_port, is_active | FK users.id (unique) | TcpCredentialService.authenticate (TCP), routes /api/tcp/* | create/update/regenerate/delete | **CRITIQUE** | OUI (security.xml) |
| `RevokedToken` | app/models/revoked_token.py | modèle ORM | id, jti (unique), user_id, expires_at, revoked_at | FK users.id | JWT loader (vérification), logout | logout | MOYENNE (éphémère) | OUI (security.xml ou volatil) |
| `schema_migrations` | app/schema_migrations.py | table technique | version, applied_at | — | create_app | run_schema_migrations | TECHNIQUE | disparaît avec SQLite |
| `db.create_all` + `_migrate_v2/v4` | app/__init__.py | initialisation schéma CP | — | — | create_app | create_app | TECHNIQUE | disparaît avec SQLite |

**Tests couvrant ces composants** (vérifiés) : `tests/test_auth_permissions.py` (auth/ACL), `tests/test_tcp.py`, `tests/e2e/test_tcp_security_permissions_e2e.py` (ACL + TCP), `tests/test_tables_rows.py` (catalogue/lignes), `tests/test_xml_backend_mode.py` (mode XML pur, absence de projection), `tests/e2e/test_rest_xml_sqlite_e2e.py`, `tests/test_xml_engine_comparison.py` (comparaison SQLite/XML), `tests/e2e/test_concurrency_robustness_e2e.py`, `tests/test_windows_storage.py`.

---

## 5. Séparation Data Plane / Control Plane

### A. DONNÉES MÉTIER — DATA PLANE (source de vérité : XML)
- tables, colonnes (type, longueur, nullable, PK, FK, unique, auto_increment, défaut, références, index, commentaire, statut)
- contraintes (PK composite, UNIQUE, FK), index (simples/composites)
- lignes (cellules), compteur `next_auto_increment`
- version du document, nom/description/commentaire/statut/scope **portés par le document** pour l'auto-contenance des exports

### B. MÉTADONNÉES — CONTROL PLANE (source de vérité : futur XML CP)
- utilisateurs, rôles, password hashes, statut d'activation, token_version
- ownership (owner_id), scope réellement appliqué
- grants (ACL) base et table, créateur du grant
- catalogue de **référence** des bases (id, nom, propriétaire, chemin du XML, version, checksum, statut de synchro)
- audit, historique, unlocks, credentials TCP, tokens révoqués

**Règle de non-mélange (à coder en Phase 6)** : le Control Plane ne stocke **jamais** de lignes de données utilisateur ; il ne stocke que des **références** (`database_id`, `xml_file_path`) et des **métadonnées d'administration**.

---

## 6. Modèle actuel des utilisateurs (vérifié)

`users` : `id` (int PK auto), `full_name`, `email` (unique, index), `password_hash` (bcrypt, `generate_password_hash`), `created_at`, `updated_at`, `is_active` (bool, défaut true), `last_login`, `token_version` (int, défaut 1), `role_id` (FK roles.id, nullable pendant migration).

- **Pas de champ `username`** distinct : le login se fait par `email`. (Vérifié : `User` n'a ni `username` ni `uuid`.)
- `token_version` est incrémenté lors de : reset_password, toggle_active, changement d'`is_active`. Il est embarqué dans le JWT (`additional_claims`) et vérifié au chargement → invalidation globale des tokens existants.
- `is_admin()` = `role.name.lower() == 'admin'` (le privilège vient du **rôle**, jamais de l'email — sauf une promotion one-shot d'un compte historique dans `schema_migrations.py`).

---

## 7. Modèle actuel des rôles (vérifié)

Table `roles` : `id`, `name` (unique), `description`, `created_at`. **Deux rôles réels seulement** (relevé base : `admin`, `user`). Seed par la migration V5 (`schema_migrations.py`), re-création défensive dans `AuthService.register` (rôle `user`) et `create-admin` (rôle `admin`).
- Aucun autre rôle (pas de `editor`, `viewer`, etc.). **Ne pas inventer de rôles supplémentaires.**

---

## 8. Modèle actuel des permissions (vérifié — ne pas inventer)

Permissions réelles : **4 booléens** sur `database_permissions` et `table_permissions` :
`can_read`, `can_write`, `can_ddl`, `can_admin` (+ `granted_by_id`, dates).

Niveaux **calculés** (pas stockés) par `PermissionService` :
- `MANAGE` si `can_admin` (ou admin/owner)
- `EDIT` si `can_write` ou `can_ddl`
- `VIEW` si `can_read`
- `NONE` sinon

Mapping d'action : `read→can_read`, `write→can_write`, `ddl→can_ddl`, `admin→can_admin`, **`delete→can_admin`** (`ACTION_TO_FIELD`).

Résolution d'accès (ordre vérifié dans `PermissionService.database_access` / `table_access`) :
1. utilisateur inactif / ressource absente → NONE ;
2. **admin** (rôle) → tout ;
3. **owner** (`owner_id or creator_id`) → tout ;
4. **grant** base (`DatabasePermission`) ;
5. **surcharge table** (`TablePermission`) : les droits de la table ne peuvent que **s'ajouter** (OR) aux droits de la base, sauf si l'utilisateur a déjà `can_admin` sur la base (alors la surcharge est ignorée).

---

## 9. Modèle actuel des databases (vérifié)

`databases` : `id`, `uuid`, `name`, `description`, `creator_id`, `owner_id` (nullable, initialisé à creator_id), `scope` (`PERSONAL`|`COMMON`), `xml_file_path`, `projection_path`, `document_version` (int, défaut 1), `xml_checksum` (SHA-256), `sync_status` (`PENDING`/`SYNCED`/`ERROR`), `created_at`, `updated_at`, `last_modified_by_id/name`, `comment`, `status` (`ACTIVE`/`ARCHIVED`), `key_identifier` (unique, format `XML-XXXX-XXXX-XXXX`).

- `key_identifier` est généré par `generate_key_identifier()` (3 groupes de 4 hex, `XML-` préfixé), unicité garantie par boucle sur 10 tentatives.
- Le **fichier XML** est nommé `{id}_{slug(name)}.xml` (ou `database.xml`) ; la projection `{id}_{slug}.sqlite`.
- **Point d'attention (vérifié)** : `name`, `description`, `comment`, `status`, `scope`, `owner_id` existent **à la fois** dans la table `databases` **et** dans le document XML (attributs racine). L'arbitrage actuel est dans `_sync_catalog`/`ensure_storage` : **le XML est autoritaire au démarrage**, le catalogue est resynchronisé depuis lui.

---

## 10. Modèle actuel des tables / colonnes (vérifié)

`tables` : `id`, `uuid`, `name`, `description`, `database_id`, `creator_id`, `is_protected`, `file_identifier`, `status`, `comment`, timestamps, `last_modified_by_*`, unique(database_id, name).
`columns` : `id`, `uuid`, `name`, `type`, `length`, `nullable`, `primary_key`, `foreign_key`, `unique`, `auto_increment`, `default_value`, `references`, `on_delete`, `on_update`, `indexed`, `comment`, `status`, `table_id`, `creator_id`, unique(table_id, name).

**Fait structurant (vérifié)** : ces deux tables **et** `table_rows` sont **entièrement dérivées du XML** par `XmlEngineService._sync_catalog()`. Elles ne sont jamais la source de vérité. `SchemaService.get()` lit d'ailleurs le schéma **directement depuis le XML** (aucune donnée SQLite). Cela pré-démontre la faisabilité de la suppression du catalogue SQLite : il suffit de remplacer les quelques lectures ORM restantes (résolution nom→id, `is_protected`, `file_identifier`, `database_id`) par une lecture du document XML.

---

## 11. Modèle actuel des grants (vérifié)

- `database_permissions(database_id, user_id, can_read, can_write, can_ddl, can_admin, granted_by_id, created_at, updated_at)` — unique(database_id, user_id).
- `table_permissions(table_id, user_id, can_read, can_write, can_ddl, can_admin, granted_by_id, created_at, updated_at)` — unique(table_id, user_id).
- `grant_database`/`grant_table` imposent : l'acteur doit avoir `admin` sur la ressource ; impossible de granter le propriétaire ; un droit supérieur implique `can_read=true`.
- `revoke_*` supprime la ligne.
- **Constat (vérifié)** : la notion de `COMMON` est **stockée** (`scope`) mais **aucune règle d'accès automatique basée sur `COMMON` n'existe dans `PermissionService`** : une base `COMMON` reste inaccessible à un tiers sans grant explicite. → **À confirmer** si `COMMON` doit conférer un accès en lecture implicite (la sémantique actuelle est : `COMMON` = simple étiquette, l'ACL reste le seul décideur).

---

## 12. Modèle actuel audit / history (vérifié)

**`history`** (historique métier, UI) : user_id, user_name, action_type (« a créé », « a ajouté », « a modifié », « a supprimé », « a synchronisé »), element_type (base, table, colonne, ligne, utilisateur), element_name, description, ip_address, `before_data`/`after_data` (JSON), database_id, table_id, created_at, uuid.

**`audit_logs`** (audit de sécurité, admin) : user_id (nullable : erreurs pré-auth), user_name, ip_address, `action` (voir liste réelle ci-dessous), element_type (base/table/colonne/auth/system/utilisateur/ligne), element_name, description, `meta_data` (JSON), timestamp, uuid.

**Liste réelle des actions d'audit émises dans le code** (relevé exhaustif par grep + base) :
`CONNEXION`, `DECONNEXION`, `INSCRIPTION`, `ERREUR_INSCRIPTION`, `ERREUR_CONNEXION`, `CREATION_BASE`, `SUPPRESSION_BASE`, `ARCHIVAGE_BASE`, `CREATION_TABLE`, `SUPPRESSION_TABLE`, `MODIFICATION_TABLE`, `CREATION_COLONNE`, `MODIFICATION_COLONNE`, `SUPPRESSION_COLONNE`, `CREATION_LIGNE`, `MODIFICATION_LIGNE`, `SUPPRESSION_LIGNE`, `PARTAGE_BASE`, `RETRAIT_PARTAGE_BASE`, `PARTAGE_TABLE`, `RETRAIT_PARTAGE_TABLE`, `DEVERROUILLAGE_TABLE`, `ERREUR_DEVERROUILLAGE`, `CREATION_UTILISATEUR`, `MODIFICATION_UTILISATEUR`, `SUPPRESSION_UTILISATEUR`, `RESET_PASSWORD`, `ACTIVATION_UTILISATEUR`, `DESACTIVATION_UTILISATEUR`, `SYNC_XML`, `SYNC_XML_TABLE`, `TCP_QUERY`, `IMPORT_XML`, `EXPORT_XML`, `EXPORT_XML_TABLE`, `EXPORT_SQL`, `EXPORT_PROJECT`, `CONVERSION_XML`, `CONVERSION_SQL`, `ERREUR_CONVERSION_XML`, `ERREUR_CONVERSION_SQL`, `CREATION_REELLE_BASE`, `ERREUR_CREATION_REELLE`.

---

## 13. Modèle actuel unlock (vérifié)

`table_unlocks` : `id`, `user_id`, `table_id`, `unlocked_at`, `expires_at` (défaut +24 h via `default_expiry`), unique(user_id, table_id).
- Clé valide = `table.file_identifier` OU `database.key_identifier` (`UnlockService.unlock_table` / `check_protection`).
- Cycle de vie : effacés à la connexion (`login`), à la déconnexion (`logout`), au reset de mot de passe ; purge des expirés à la lecture.
- Le déverrouillage est **personnel** (par user + table), vérifié par `is_unlocked`.

---

## 14. Modèle actuel TCP credentials (vérifié)

`tcp_credentials` : `id`, `user_id` (unique), `tcp_username` (défaut = email), `tcp_password` (**bcrypt hash**), `tcp_host` (défaut 127.0.0.1), `tcp_port` (défaut 3307), `is_active`, `created_at`, `updated_at`.
- **Un seul credential par utilisateur** (contrainte unique `user_id`). Pas de credentials multiples.
- `tcp_username` doit être unique globalement (contrôle dans create/update).
- `authenticate(username, password)` vérifie : credential actif + user actif + `bcrypt.check_password_hash`.
- Les **sessions TCP** sont **en mémoire** (`TCPServer.sessions`, token uuid4, timeout 30 min, purge périodique) — **aucune persistance SQLite**. → Aucune migration nécessaire pour les sessions.
- Le mot de passe TCP est généré (`secrets.token_urlsafe(16)`) et **affiché une seule fois** ; la route `/api/tcp/credentials/show-password` régénère et réaffiche après confirmation du mot de passe XMLForge.

---

## 15. Analyse des IDs (vérifiée)

Stratégie actuelle :
- **`id` INTEGER autoincrement** sur toutes les tables ORM → identifiant d'exposition REST (routes `/users/<int:id>`, `/databases/<int:id>`, `/tables/<int:id>`, etc.).
- **`uuid` (string 36, uuid4)** présent sur : `Database`, `Table`, `Column`, `TableRow`, `History`, `AuditLog`. **Absent** de : `User`, `Role`, `DatabasePermission`, `TablePermission`, `TableUnlock`, `TcpCredential`, `RevokedToken`.
- **`key_identifier`** (XML-XXXX-XXXX-XXXX) : identifiant public/porteur de la clé de protection, uniquement sur `Database`.
- **`file_identifier`** (optionnel) : clé de protection au niveau table.
- **`jti`** : identifiant JWT (logout).

**Recommandation (conservation de stabilité)** :
1. **Ne jamais changer les `id` entiers existants** : ils sont référencés partout (ACL, audit, history, URLs REST, frontend). Ils deviennent des attributs `internal_id` persistés dans le XML CP.
2. **Ajouter `uuid` (backfill) aux entités qui n'en ont pas** (`users`, `roles`, `database_permissions`, `table_permissions`, `table_unlocks`, `tcp_credentials`, `revoked_tokens`) pour les futurs exports/fusions, **sans** remplacer `id`.
3. **Conserver `key_identifier`/`file_identifier`** inchangés (ils sont exposés aux utilisateurs finaux comme clés de protection).
4. **Règle d'unicité dans le XML CP** : `internal_id` (entier, stable) + `uuid` (opaque), avec index unique sur les deux.

---

## 16. Analyse sécurité (vérifiée)

**Acquis actuels (à conserver)** :
- Mots de passe utilisateur **bcrypt** (`password_hash`).
- Mots de passe TCP **bcrypt** (`tcp_password`).
- JWT signé (`JWT_SECRET_KEY`), `token_version` pour invalidation globale, `RevokedToken` (jti) pour logout.
- XSD de validation du Data Plane (`app/static/xmlforge.xsd`) avec protections XXE (`resolve_entities=False`, `no_network=True`, `huge_tree=False`).
- Validation stricte des identifiants SQL/XML (`IDENTIFIER_RE`), quoting défensif (`quote_identifier`).
- `ProductionConfig.validate()` **refuse** les secrets par défaut en production.

**Risques et protections pour le Control Plane XML** :
- **Fichiers sensibles** (`users`, `tcp_credentials`, `grants`) : permissions fichiers `0600`, répertoire `0700` ; **jamais** servis par Flask ; hors `UPLOAD_FOLDER`/`EXPORT_FOLDER`.
- **Pas de mot de passe en clair** : conserver bcrypt tels quels (le XML ne stocke que les hashes).
- **Secrets d'instance** : les `SECRET_KEY`/`JWT_SECRET_KEY` restent **hors XML** (variables d'environnement), sinon quiconque lit le XML pourrait forger des JWT. → le Control Plane XML ne doit pas contenir les clés de signature.
- **Modification manuelle/corruption** : réutiliser la validation XSD + checksum SHA-256 (déjà en place), et durcir `read_document` pour **refuser** (pas seulement tolérer) un mismatch de checksum sur les fichiers CP.
- **Exposition** : le contrôleur REST ne doit jamais accepter un chemin XML fourni par le client (aujourd'hui `xml_file_path` est calculé par le serveur — à conserver).
- **Sauvegardes** : snapshot/restore existant + sauvegarde externe des fichiers `control/` (le hash permet la détection d'altération).

---

## 17. Analyse concurrence & atomicité (vérifiée — réutiliser l'existant)

Mécanismes **déjà en production côté Data Plane** (`app/xml_engine/storage.py`, `service.py`) :
- **Verrou de fichier** : `database_lock()` = `fcntl.flock(LOCK_EX)` + `threading.RLock` par chemin. Portable POSIX, fallback thread sous Windows.
- **Écriture atomique** : `atomic_write()` = tempfile + `fsync` + `os.replace` (+ fallback copie/suppression Windows).
- **Commit pair** : `commit_pair()` écrit le XML **avant** la projection ; un crash entre les deux est rattrapé au démarrage (reconstruction depuis XML).
- **Rollback** : `snapshot()`/`restore()` des deux artefacts avant/après.
- **Contrôle optimiste** : `expected_version` (header `If-Match`) + champ `version` du document ; conflit → `ConflictError` (409, `SYNC_CONFLICT`).
- **Intégrité** : `xml_checksum` (SHA-256) + `PRAGMA quick_check` + `foreign_key_check` côté projection.

**Besoins du Control Plane XML** :
1. **Verrouillage** : même `database_lock` appliqué à chaque fichier du CP (`control/users.xml.lock`, etc.).
2. **Écriture atomique** : `atomic_write` tel quel.
3. **Lecture concurrente** : lecture du fichier sous verrou partagé (ou lecture d'un snapshot atomique — `os.replace` garantit qu'un lecteur voit toujours une version complète).
4. **Optimistic locking / version** : champ `version` par fichier CP ; `If-Match`/`expected_version` sur les mutations sensibles (grant, user).
5. **Rollback** : `snapshot`/`restore` par fichier avant mutation multi-étapes (ex. suppression d'utilisateur qui purge grants + unlocks + credentials).
6. **Corruption/crash** : le chargement valide XSD + checksum ; en cas d'échec, **refuser de démarrer** le composant concerné (jamais de re-création silencieuse d'un `users.xml` qui contiendrait des comptes).

**Limite à documenter** : il n'existe **pas de transaction multi-fichiers** (pas de « commit atomique » entre `users.xml` et `grants.xml`). La conception devra ordonner les écritures (ex. supprimer le user en dernier) et prévoir une réparation au démarrage.

---

## 18. Analyse duplication (vérifiée)

- **Déjà dupliqué aujourd'hui** : `name/description/comment/status/scope/owner_id` entre `databases` (SQLite) et le document XML. Arbitrage actuel : XML autoritaire au démarrage, catalogue resynchronisé.
- **Projection SQLite** : duplication complète des données métier (tables/colonnes/lignes) — déjà optionnelle (Phase 4), à supprimer à terme.
- **Catalogue `tables`/`columns`/`table_rows`** : duplication dérivée du XML — à supprimer (voir §19).
- **Règle pour la Phase 6** : le Control Plane XML ne doit **jamais** recopier les lignes de données utilisateur. Seules les **références** (`database_id`, chemin, version, checksum) et les **métadonnées d'administration** (ownership, ACL) y vivent.

---

## 19. Analyse catalogue — décision (section 21 du cahier des charges)

Trois solutions comparées :

| | Solution 1 : catalogue complet dans le CP | Solution 2 : CP = métadonnées base + chemin ; tables/colonnes lues du Data Plane | Solution 3 : hybride (cache) |
|---|---|---|---|
| Duplication | **élevée** (tables+colonnes en double) | **nulle** | faible mais cache à invalider |
| Cohérence | risque d'écart CP/XML | **toujours cohérent** (une seule source) | risque de cache stale |
| Performance listage | rapide (indexé) | doit ouvrir/parser les XML (par base) | rapide (cache) |
| Complexité | répliquer tout le moteur | réutiliser `SchemaService` (déjà XML) | mécanique de cache |
| Déjà prouvé dans le code | non | **OUI** : `SchemaService.get()` lit déjà le XML ; `_sync_catalog` montre que le catalogue n'est qu'une projection | non |

**Décision recommandée : Solution 2**, avec une **variante hybride minimale** : le Control Plane garde **uniquement** la liste des bases (id, nom, owner, scope, chemin, version, checksum, statut) — nécessaire pour lister les bases accessibles sans ouvrir tous les XML — et **rien** pour tables/colonnes/lignes, qui sont découvertes depuis le Data Plane à la demande (comme le fait déjà `SchemaService`).
- Les rares lectures ORM restantes sur `Table`/`Column`/`TableRow` (résolution nom→id, `is_protected`, `file_identifier`, compteurs) seront remplacées par la lecture du document XML (déjà disponible via `XmlEngineService.read_document`).
- Justification : minimiser la duplication et les incohérences, tout en gardant un index léger des bases (chemin + ACL) pour les listes d'écran.

---

## 20. Architecture XML recommandée (sections 12 & 20 du cahier des charges)

Comparaison des options de fichiers :

| Critère | OPTION A : `control_plane.xml` unique | OPTION B : plusieurs fichiers par domaine | OPTION C (recommandée) : plusieurs fichiers + audit rotatif |
|---|---|---|---|
| Atomicité | 1 fichier = 1 verrou = simple | cohérence multi-fichiers à gérer | idem B, mais domaines découplés |
| Concurrence | **contention forte** (chaque login/audit réécrit tout) | faible (verrous par fichier) | **faible** (audit découplé des users) |
| Croissance audit | **problème** (fichier grossit indéfiniment) | gérable | **résolu** (rotation mensuelle) |
| Backup partiel | impossible | possible par domaine | possible + rotation |
| Corrélation sécurité | un point de corruption touche tout | corruption isolée par domaine | isolée |
| Sécurité | un seul fichier à protéger | plusieurs fichiers à protéger | fichiers sensibles restreints (0600) |
| Complexité | minimale | moyenne | moyenne (mais réutilise `storage.py`) |
| Maintenance | simple | bonne lisibilité | bonne + archivage audit |

**Recommandation : OPTION C** — répertoire `backend/data/control/` :

```
control/
  security.xml        # roles + users + tcp_credentials + revoked_tokens  (unité de sécurité)
  catalog.xml         # databases (références) + grants base/table         (unité ACL/ownership)
  unlocks.xml         # table_unlocks (éphémère, purge automatique)
  history.xml         # historique métier (V2 before/after)
  audit-2026-09.xml   # audit par mois (rotation)
  audit-2026-10.xml
```

Justification : `security.xml` regroupe ce qui est lu à **chaque** authentification (rôle, hash, credentials) en un seul verrou ; `catalog.xml` regroupe ACL + références de bases (utilisé à chaque requête pour les permissions) ; l'**audit** est séparé et **rotatif** car c'est le seul flux à fort volume et append-heavy ; `unlocks` est volatil (peut même rester en mémoire, cf. sessions TCP).

---

## 21. Structure des fichiers XML (cohérente avec l'audit)

Fichier `security.xml` (exemple conceptuel, champs = modèles réels) :

```xml
<?xml version="1.0" encoding="UTF-8"?>
<security version="1">
  <roles>
    <role internal_id="1" uuid="…" name="admin" description="Administrateur XMLForge" created_at="…"/>
    <role internal_id="2" uuid="…" name="user" description="Utilisateur XMLForge" created_at="…"/>
  </roles>
  <users>
    <user internal_id="3" uuid="…" full_name="…" email="…" password_hash="$2b$…"
          is_active="true" last_login="…" token_version="2" role_id="2"
          created_at="…" updated_at="…"/>
  </users>
  <tcp_credentials>
    <credential internal_id="1" uuid="…" user_id="3" tcp_username="…" tcp_password="$2b$…"
                tcp_host="127.0.0.1" tcp_port="3307" is_active="true"
                created_at="…" updated_at="…"/>
  </tcp_credentials>
  <revoked_tokens>
    <token internal_id="1" jti="…" user_id="3" expires_at="…" revoked_at="…"/>
  </revoked_tokens>
</security>
```

Fichier `catalog.xml` :

```xml
<?xml version="1.0" encoding="UTF-8"?>
<catalog version="1">
  <databases>
    <database internal_id="5" uuid="…" name="bibliotheque" owner_id="3" scope="PERSONAL"
              xml_file_path="data/xml/5_bibliotheque.xml" document_version="12"
              xml_checksum="sha256…" sync_status="SYNCED" status="ACTIVE"
              key_identifier="XML-XXXX-XXXX-XXXX" created_at="…" updated_at="…"/>
  </databases>
  <grants>
    <database_permission internal_id="1" uuid="…" database_id="5" user_id="7"
                         can_read="true" can_write="true" can_ddl="false" can_admin="false"
                         granted_by_id="3" created_at="…" updated_at="…"/>
    <table_permission internal_id="2" uuid="…" table_id="12" user_id="7"
                      can_read="true" can_write="false" can_ddl="false" can_admin="false"
                      granted_by_id="3" created_at="…" updated_at="…"/>
  </grants>
</catalog>
```

Fichier `unlocks.xml` : `table_unlocks` (user_id, table_id, unlocked_at, expires_at).
Fichier `history.xml` : entrées `history` (user_id, action_type, element_type, element_name, before/after JSON échappé, database_id, table_id, ip_address, created_at).
Fichier `audit-YYYY-MM.xml` : entrées `audit_logs` (mêmes champs, `meta_data` JSON échappé, timestamp).

**Règles de conception** :
- Chaque élément porte `internal_id` (entier stable) + `uuid` (opaque).
- `password_hash`/`tcp_password` : **bcrypt uniquement** (jamais de clair).
- `before`/`after`/`meta_data` : JSON échappé en `CDATA` ou entités (comme le fait déjà le sérialiseur).
- Un seul schéma XSD par fichier (ou un XSD commun avec `root` alternatifs).

---

## 22. Schéma XML proposé (synthèse)

```
control_plane (répertoire, pas un fichier unique)
├── security.xml
│   ├── roles/role (internal_id, uuid, name, description, created_at)
│   ├── users/user (…, password_hash, is_active, last_login, token_version, role_id)
│   ├── tcp_credentials/credential (…, tcp_password bcrypt)
│   └── revoked_tokens/token (jti, expires_at, revoked_at)
├── catalog.xml
│   ├── databases/database (références + ownership + ACL admin)
│   └── grants/ (database_permission | table_permission)
├── unlocks.xml
│   └── unlocks/unlock (user_id, table_id, unlocked_at, expires_at)
├── history.xml
│   └── entries/entry (…, before_data, after_data)
└── audit-YYYY-MM.xml
    └── entries/entry (…, meta_data)
```

---

## 23. XSD proposé (structure, pas le XSD complet)

Chaque fichier CP est validé par un XSD dédié (réutilisation de `validate_xml_bytes` et du pattern XXE-safe de `document.py`).

- `security.xsd` :
  - `security` (obligatoire), attribut `version` (xs:integer, obligatoire).
  - `roles/role` : `name` (xs:token, **unique** via `xs:key`), `description`, `created_at` (xs:dateTime).
  - `users/user` : `email` (**unique**), `password_hash` (obligatoire, minLength 1), `is_active` (booléen), `token_version` (entier ≥ 1), `role_id` (**référence** `role/@internal_id` via `xs:keyref`), `last_login` (optionnel).
  - `tcp_credentials/credential` : `user_id` (**keyref** vers `user/@internal_id`, **unique**), `tcp_password` (obligatoire), `tcp_port` (entier 1–65535).
  - `revoked_tokens/token` : `jti` (**unique**).
- `catalog.xsd` :
  - `databases/database` : `name`, `owner_id` (**keyref** vers user), `key_identifier` (**unique**, pattern `XML-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}`), `document_version`, `xml_checksum` (pattern hex64), `scope` (enum PERSONAL/COMMON), `status` (enum ACTIVE/ARCHIVED).
  - `grants/*` : contrainte **unique (database_id, user_id)** et **unique (table_id, user_id)** via `xs:key`.
- `unlocks.xsd` : unique (user_id, table_id).
- `history.xsd` / `audit.xsd` : champs libres mais typés, `created_at`/`timestamp` (dateTime), JSON échappé en texte.

**Validation** : au chargement (comme `parse_document`), et **avant chaque mutation** ; un fichier invalide → refus (jamais de régénération silencieuse pour les fichiers de sécurité).

---

## 24. Source of Truth Matrix

| Information | Source actuelle | Future source | Duplication autorisée ? | Justification |
|---|---|---|---|---|
| utilisateurs | SQLite `users` | `security.xml` | NON | donnée d'administration pure |
| password hashes | SQLite `users` | `security.xml` (bcrypt) | NON | secret, jamais dupliqué |
| rôles | SQLite `roles` | `security.xml` | NON | référence des users |
| permissions/grants | SQLite `database_permissions`/`table_permissions` | `catalog.xml` | NON | ACL unique |
| ownership | SQLite `databases.owner_id` (+ attr XML) | `catalog.xml` | **copie tolérée** dans le document XML (attr `owner_id`) pour l'auto-contenance des exports, marquée « cache » | l'ACL fait foi ; l'attr XML n'est jamais décisionnaire |
| database metadata (name, desc, comment, status, scope) | hybride (SQLite + XML) | **catalog.xml = référence d'administration** ; le document XML porte une copie pour l'export | **copie tolérée, arbitrée** : XML = contenu exportable, catalog = ACL/chemins/version | éviter deux vérités contradictoires : règle de synchronisation fixe |
| table metadata | Data Plane (XML) — SQLite `tables` = projection | Data Plane (XML) | NON | découverte via `SchemaService` |
| column metadata | Data Plane (XML) — SQLite `columns` = projection | Data Plane (XML) | NON | idem |
| rows | Data Plane (XML) — SQLite `table_rows` = projection | Data Plane (XML) | NON | données métier |
| indexes | Data Plane (XML) | Data Plane (XML) | NON | structure |
| audit | SQLite `audit_logs` | `audit-YYYY-MM.xml` (rotatif) | NON | append-only |
| history | SQLite `history` | `history.xml` | NON | journal métier |
| unlocks | SQLite `table_unlocks` | `unlocks.xml` (volatil) | NON | éphémère |
| TCP credentials | SQLite `tcp_credentials` | `security.xml` | NON | secret, 1:1 user |
| sessions TCP | **mémoire** (TCPServer) | mémoire (inchangé) | NON | déjà hors SQLite |
| tokens révoqués | SQLite `revoked_tokens` | `security.xml` (ou mémoire) | NON | éphémère |

---

## 25. Plan de migration futur (Phase 6, non exécuté)

Progression cible :

```
SQLite CP ──► XML CP parallèle (double écriture contrôlée) ──► validation ──► XML source de vérité ──► SQLite fallback temporaire ──► suppression SQLite
```

**Étapes exactes (à dérouler en Phase 6, dans cet ordre)** :

1. **Backup SQLite** : copie froide de `xmlforge.db` + hash SHA-256 avant toute bascule.
2. **Squelette CP XML** : `XmlControlPlaneService` réutilisant `storage.py` (atomic_write, database_lock, snapshot/restore) + parseurs/sérialiseurs + XSD par fichier.
3. **Seed initial** : export **déterministe** SQLite → XML (`security.xml`, `catalog.xml`, `history.xml`, `audit-…xml`, `unlocks.xml`) en **conservant les `id`** (`internal_id`) et en backfillant les `uuid` manquants.
4. **Mode parallèle (double écriture)** : chaque mutation CP écrit SQLite **et** XML ; chaque lecture compare (mode « compare » du CP) — activable par variable d'env (`CONTROL_BACKEND=sqlite|xml|compare`, symétrique de `QUERY_BACKEND`).
5. **Validation** : suite de tests différentiels SQLite vs XML (voir §27) + rejeu d'audit/historique sur jeux de données réels.
6. **Bascule de lecture** : les lectures CP passent sur XML ; SQLite reste écrit en shadow.
7. **Bascule d'écriture** : XML devient seule source de vérité ; SQLite devient fallback **lecture seule** (aucun fallback silencieux : si XML échoue → erreur, conformément à la règle du projet).
8. **Suppression des projections** : retirer `tables`/`columns`/`table_rows` du CP (déjà de simples projections), puis `db.create_all`/migrations du CP.
9. **Suppression finale** : retirer SQLAlchemy/SQLite du CP **après** N semaines de marche en XML pur et validation des tests « SQLite absent » (§28).

**Conservation des IDs** : tous les `internal_id` sont conservés à l'identique ; les `uuid` ajoutés n'altèrent rien ; les `key_identifier`/`file_identifier` inchangés.

---

## 26. Plan de rollback

- **Avant bascule** : sauvegarde `xmlforge.db` + les fichiers `control/*.xml` (double snapshot).
- **Rollback rapide** : repasser `CONTROL_BACKEND=sqlite` (le mode parallèle garantit que SQLite est resté à jour pendant toute la phase de double écriture).
- **Rollback post-bascule écriture** : rejouer le dump SQLite depuis le XML CP (l'export étant déterministe, la reconstruction inverse est possible) — ou restaurer la sauvegarde froide si aucune écriture « XML-only » n'a eu lieu entre-temps.
- **Détection de corruption** : checksum + XSD au démarrage ; en cas d'échec, le composant concerné refuse de démarrer (pas de re-création silencieuse).
- **Jamais de suppression du fichier SQLite** tant que les tests « SQLite absent » n'ont pas tous réussi.

---

## 27. Tests nécessaires (à prévoir avant suppression SQLite)

Chaque ligne ci-dessous est un scénario **réel** (pas de mock), réutilisant les helpers existants (`register_and_login`, `auth`).

**Auth** : création utilisateur ; login ; mauvais mot de passe ; rôle ; vérification du hash bcrypt (jamais de clair) ; token_version invalide le JWT.

**Permissions** : owner (tous droits) ; VIEW ; EDIT ; MANAGE ; accès refusé (403) ; surcharge table (OR) ; `delete` exige `can_admin` ; inactif → refus.

**Databases** : création (PERSONAL/COMMON) ; suppression ; ownership ; duplicata de nom par propriétaire refusé ; `key_identifier` unique.

**Grants** : partage base ; modification du grant ; suppression ; vérification ; grant au propriétaire refusé ; non-admin ne peut pas granter.

**TCP** : authentification (credential valide) ; credential invalide ; accès autorisé/refusé (mêmes règles ACL que REST) ; sessions expirées ; unlock via TCP.

**Audit** : action enregistrée ; utilisateur correct ; timestamp ; ressource correcte ; action pré-auth (user_id NULL).

**Unlock** : table protégée ; déverrouillage ; mauvais mot de passe/clé ; expiration (+24 h) ; purge à la connexion/déconnexion.

**Résilience** : écriture atomique (pas de fichier tronqué après crash simulé) ; fichier XML corrompu → refus ; rollback snapshot ; concurrence (deux mutations simultanées, `expected_version` → 409).

**Régression Data Plane** : la suite existante (`test_xml_engine_*`, `test_xml_backend_mode.py`, e2e) doit rester **verte** — aucune modification destructive.

---

## 28. Tests « SQLite absent » (spécification pour la Phase 6, non exécutés ici)

Suite à lancer avec le CP XML **sans** SQLAlchemy/SQLite initialisé (le Data Plane restant en mode XML pur) :
- désactiver SQLite (pas de `db.init_app` / `DATABASE_URL` CP) ;
- démarrer Flask ;
- `create-admin`, inscription, login (JWT), `/me`, logout (revoked token) ;
- création d'une base, d'une table, d'une colonne, de lignes (moteur XML) ;
- partage base (grant), vérification VIEW/EDIT/MANAGE, révocation ;
- TCP : authentification + requête + unlock ;
- audit + historique consultables en admin ;
- purge des unlocks ;
- redémarrage : persistance des comptes, ACL, chemins, versions (aucune donnée perdue).

**Cette suite ne doit PAS être exécutée maintenant** (elle exigerait de casser l'architecture actuelle). Elle est spécifiée pour la Phase 6.

---

## 29. Risques

1. **Cohérence multi-fichiers** (pas de transaction atomique entre `security.xml` et `catalog.xml`) : une suppression d'utilisateur doit ordonner les écritures (grants → credentials → user) + réparation au démarrage.
2. **Régression ACL** : la sémantique `delete→can_admin`, la surcharge table en « OR », et le `scope COMMON` (actuellement sans effet ACL automatique) doivent être reproduits à l'identique — sinon brèche de sécurité.
3. **Volume de l'audit** : sans rotation, un fichier unique deviendrait ingérable → rotation mensuelle + archivage.
4. **Perte des IDs** : toute renumérotation casserait ACL/audit/history/frontend → `internal_id` figé.
5. **Secrets** : ne **jamais** stocker `SECRET_KEY`/`JWT_SECRET_KEY` ni mots de passe en clair dans le XML.
6. **Fallback silencieux** : interdire tout « XML → SQLite → résultat » automatique (règle permanente du projet) ; une erreur CP doit remonter.
7. **Corruption** : le XML CP doit être validé (XSD + checksum) et refuser de démarrer en cas d'incohérence — sans régénération silencieuse.
8. **Compat frontend** : le frontend consomme des `id` entiers (`/users/<id>`, `/tables/<id>`) — conserver les entiers.
9. **Tests legacy** : ne pas supprimer les tests SQLite tant que le comparateur/fallback existent.

---

## 30. Décisions recommandées

1. **Conserver SQLite/SQLAlchemy intacts** pendant toute la Phase 6 (aucune suppression tant que la bascule n'est pas validée).
2. **CP XML en plusieurs fichiers par domaine** (OPTION C) + **audit rotatif**.
3. **IDs : `internal_id` entier conservé + `uuid` ajouté** (backfill) ; `key_identifier`/`file_identifier` inchangés.
4. **Catalogue : Solution 2** (références de bases uniquement ; tables/colonnes/lignes découvertes du Data Plane).
5. **Authentification : conserver bcrypt + JWT + token_version + revoked_tokens** tels quels.
6. **Sessions TCP : rester en mémoire** (aucun stockage).
7. **Réutiliser `storage.py`/`document.py`** (verrous, atomicité, snapshot, XSD) sans réécriture.
8. **Aucun fallback silencieux** : mode parallèle `CONTROL_BACKEND=sqlite|xml|compare`, erreurs remontées.

---

## 31. Points nécessitant validation avant implémentation

1. **Sémantique de `COMMON`** : doit-elle accorder un accès implicite (lecture) à tous les utilisateurs authentifiés, ou rester une simple étiquette ? (Aujourd'hui : étiquette sans effet ACL — **À confirmer**.)
2. **Rotation de l'audit** : mensuelle ? avec archivage gzip ? politique de rétention légale ?
3. **`unlocks`** : persister en XML ou passer en mémoire (comme les sessions TCP) ? (Éphémère par nature.)
4. **`revoked_tokens`** : persister en XML ou en mémoire avec TTL ? (Éphémère par nature.)
5. **Compatibilité `schema_migrations`** : le registre de version disparaît-il avec SQLite, ou devient-il un attribut `version` de chaque fichier CP ?
6. **Multi-processus** : l'hypothèse actuelle (un seul processus Flask + threads) justifie `flock` par fichier ; confirmer qu'il n'y aura pas de workers multiples en production (sinon prévoir verrous partagés/exclusifs plus fins).
7. **Double écriture** : conserver le mode `compare` du CP en production ou seulement en recette ?

---

## 32. Architecture cible

```
                         XMLFORGE
                            │
            ┌───────────────┴───────────────┐
            │                               │
      CONTROL PLANE                    DATA PLANE
            │                               │
   backend/data/control/             backend/data/xml/
   ├─ security.xml (users, roles,    <id>_<slug>.xml
   │   tcp_credentials, revoked)     (tables, colonnes, contraintes,
   ├─ catalog.xml (databases,        index, lignes)
   │   grants)                       │
   ├─ unlocks.xml                    XmlEngineService.mutate()
   ├─ history.xml                    XmlNativeEngine (moteur SQL-like)
   └─ audit-YYYY-MM.xml              │
            │                        │
   XmlControlPlaneService       ┌────┴─────────────┐
   (réutilise storage.py :      │                  │
   atomic_write, flock,         ▼                  ▼
   snapshot/restore, XSD)   Moteur XML natif   Projection SQLite
            │               (source de vérité) (fallback/comparaison,
            │                                   désactivable)
            └───────────────┬────────────────────┘
                            │
                  REST API (5000) / TCP (3307)
                  (mêmes services, mêmes permissions)
                            │
                        Clients
```

SQLite ne subsiste, à terme, que comme **fallback temporaire / moteur de comparaison** (projection de données), puis disparaît.

---

## 33. Conclusion

- Le **Data Plane XML** est déjà la source de vérité des données métier ; le catalogue SQLite (`tables`/`columns`/`table_rows`) n'est qu'une projection dérivable, ce qui rend sa suppression mécanique une fois les dernières lectures ORM remplacées par la lecture du XML.
- Le **Control Plane** (utilisateurs, rôles, ACL, ownership, audit, historique, unlocks, credentials TCP) est la seule vraie dépendance résiduelle à SQLite. Il est **audité exhaustivement** ici : 14 tables, 8 services consommateurs, 40+ actions d'audit réelles, 2 rôles réels, 4 droits réels.
- L'infrastructure de fiabilité nécessaire (verrous, écriture atomique, rollback, version optimiste, XSD, checksum) **existe déjà** côté Data Plane et peut être réutilisée.
- La Phase 6 pourra donc procéder par **double écriture contrôlée** (`CONTROL_BACKEND=compare`), validation, bascule, puis suppression SQLite — **sans jamais casser l'existant**, conformément aux règles du projet.

---

## Tableau des décisions

| Décision | Choix recommandé | Raisons | Impact Phase 6 |
|----------|------------------|---------|----------------|
| fichier unique ou fichiers multiples | **Fichiers multiples par domaine + audit rotatif** (OPTION C) | contention minimale, croissance audit maîtrisée, backup partiel, corruption isolée | structure du `XmlControlPlaneService` |
| catalogue database | **Conserver** (références + ownership + ACL admin) | nécessaire pour lister les bases accessibles sans ouvrir les XML | `catalog.xml` |
| catalogue table | **Supprimer du CP** (découverte Data Plane) | duplication inutile, `SchemaService` lit déjà le XML | remplacer les lectures ORM de `Table` |
| catalogue column | **Supprimer du CP** (découverte Data Plane) | idem | remplacer les lectures ORM de `Column` |
| utilisateurs | **XML (`security.xml`)** | donnée d'administration, source de vérité CP | portage de `auth_service`/`user_service` |
| rôles | **XML (`security.xml`)** | 2 rôles réels, référence des users | seed + lecture rôle |
| permissions | **XML (`catalog.xml`)** | 4 booléens réels + niveaux calculés | portage de `permission_service` |
| grants | **XML (`catalog.xml`)** | unique(database_id,user_id) / unique(table_id,user_id) à préserver | portage grant/revoke |
| audit | **XML rotatif (`audit-YYYY-MM.xml`)** | volume append-heavy, rotation | `audit_service` réécrit, purge/archivage |
| history | **XML (`history.xml`)** | journal métier avec before/after JSON | `history_service` réécrit |
| unlocks | **XML volatil (`unlocks.xml`)** — alternative mémoire à valider | éphémère (+24 h), purgé aux connexions | `unlock_service` réécrit |
| TCP credentials | **XML (`security.xml`), bcrypt** | 1:1 user, secret | `tcp_credential_service` réécrit |
| IDs | **`internal_id` entier conservé + `uuid` backfillé** | stabilité ACL/audit/URLs | sérialiseur/parseur CP |
| version XML | **`version` par fichier + `expected_version`/If-Match** | réutilise le contrôle optimiste existant | `ConflictError` sur mutations CP |
| locking | **`database_lock` (flock+RLock) par fichier** | déjà éprouvé côté Data Plane | verrous CP |
| validation XSD | **XSD par fichier + checksum SHA-256, refus au démarrage** | réutilise `validate_xml_bytes`, anti-XXE | chargeur CP |
| backup | **snapshot/restore + sauvegarde froide avant bascule** | rollback sûr | procédure de migration |
| rollback | **rebasculer sur SQLite (mode parallèle) puis re-exporter** | SQLite reste à jour pendant la double écriture | plan §26 |

---

### Vérifications d'honnêteté (règle anti-hallucination)

- **Documentation ≠ implémentation actuelle** : les docs racine (`API_DOCUMENTATION.md`, `BACKEND_DOCUMENTATION.md`, `XML_ENGINE.md`) décrivent des endpoints/services parfois au-delà de l'implémentation (ex. libellés « Admin only » associés à une adresse historique) ; la présente analyse s'appuie **uniquement** sur le code et la base réelle.
- **Implémentation actuelle non documentée** : la route `/audit` (alias de `/audit-logs`), la duplication contrôlée `databases`↔XML, et le mode `QUERY_BACKEND=compare` ne sont que partiellement documentés.
- **À confirmer** : sémantique ACL de `COMMON` ; rotation/politique de rétention de l'audit ; persistance `unlocks`/`revoked_tokens` ; hypothèse mono-processus.
- **Hors périmètre et non modifié** : SQLite, SQLAlchemy, modèles, migrations, services, routes, tests existants. Aucune table SQLite n'a été supprimée, aucun fichier existant n'a été supprimé.
- **Identifiants codés en dur relevés dans le code** (signalés, non reproduits ici) : une adresse e-mail historique promue admin une seule fois dans `schema_migrations.py`, et des scripts racine (`create_essoya_tcp.py`, `create_test_user.py`, `create_yann_user.py`) contenant des identifiants d'exemple. → **Recommandation Phase 6 : purger ces scripts/hardcodings.**

*Fin du rapport Phase 5 — Audit & Conception du Control Plane XML.*
