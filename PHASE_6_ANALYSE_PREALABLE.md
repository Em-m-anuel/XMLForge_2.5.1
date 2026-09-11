# PHASE 6 — Analyse préalable (avant toute modification)

**Statut** : analyse livrée, **aucune modification de code effectuée**. En attente de validation avant de commencer 6A.
**Méthode** : lecture du code réel uniquement (modèles, services, routes, moteurs, tests, frontend). Aucune hypothèse présentée comme un fait.

---

## 1. Audit des dépendances actuelles

### 1.1 Les deux SQLite (rappel vérifié)
- **Control Plane** (`backend/xmlforge.db`, SQLAlchemy) — 14 tables : `users`, `roles`, `database_permissions`, `table_permissions`, `databases`, `tables`, `columns`, `table_rows`, `history`, `audit_logs`, `table_unlocks`, `tcp_credentials`, `revoked_tokens`, `schema_migrations`.
- **Projection de données** (`data/projections/*.sqlite`, `sqlite3`) — déjà optionnelle (`SYNC_SQLITE_PROJECTION=false`, Phase 4).

### 1.2 Vraies sources de vérité aujourd'hui (vérifié)
| Domaine | Source de vérité actuelle | Cible Phase 6 |
|---|---|---|
| utilisateurs, rôles | SQLite `users`, `roles` | `security.xml` |
| password hashes | SQLite (bcrypt) | `security.xml` (bcrypt) |
| ACL / grants | SQLite `database_permissions`, `table_permissions` | `catalog.xml` |
| ownership / scope / références base | SQLite `databases` (hybride) | `catalog.xml` |
| audit | SQLite `audit_logs` | `audit/audit-YYYY-MM.xml` (rotatif) |
| history | SQLite `history` | `history.xml` |
| unlocks | SQLite `table_unlocks` | **mémoire** (volatil) |
| revoked tokens | SQLite `revoked_tokens` | **mémoire** (volatil) |
| TCP credentials | SQLite `tcp_credentials` | `security.xml` |
| tables / colonnes / lignes | **XML Data Plane** (SQLite = projection) | **XML Data Plane** (découverte) |

### 1.3 Dépendances ponctuelles importantes (vérifiées dans le code)
1. **`common_permission` n'existe nulle part** (backend + frontend + XSD). Le `scope` COMMON est aujourd'hui un simple filtre sans effet ACL. La Phase 6 ajoute un **nouveau champ** + une **nouvelle règle ACL** (accès collectif VIEW/EDIT/MANAGE).
2. **Le frontend affiche textuellement** : « Le backend ne rend pas une base COMMON automatiquement visible : la portée est un simple filtre » (`Dashboard.jsx`). Ce texte deviendra **faux** → correction de libellé à prévoir (sans changer le contrat REST).
3. **`RevokedToken` est lu au chargement de chaque JWT** (`app/__init__.py` `verify_active_user`) et écrit au logout (`routes/auth.py`). Le passage en mémoire impose de remplacer ces deux points par un store mémoire.
4. **`TableUnlock` est manipulé dans 4 services** : `UnlockService` (lecture/écriture), `AuthService.login` (purge), `UserService.reset_password` (purge), `UserService.delete` (purge), `tcp_server` (clear à l'auth). Passage en mémoire → un `UnlockStore` central.
5. **Suppression d'utilisateur** : `UserService.delete` vérifie `Database.query.filter_by(owner_id=...).count()` → devra lire `catalog.xml`.
6. **Seed des rôles** : `schema_migrations.py` (V5) + `AuthService.register` + `create-admin` → devront écrire `security.xml`.
7. **`to_dict()` des modèles = contrat REST** : le CP XML devra produire des dicts **identiques** (mêmes clés) pour ne pas casser le frontend (`user.to_dict()`, `database.to_dict(include_key=)`, etc.).
8. **Résolution ORM Table/Column/TableRow** utilisée par : `table_service`, `column_service`, `row_service`, `permission_service` (résolution table), `unlock_service`, `tcp_server`, `auth/decorators`, `export_service`, `sync_service`, `query/service.py`, `query/xml_query_service.py`, `xml_engine/document.py` (`document_from_catalog`), `xml_engine/service.py` (`_sync_catalog`) → découplage à mener en 6J/6L.
9. **Hardcodings identifiés** : `schema_migrations.py` (promotion one-shot d'un email historique en admin), `create_essoya_tcp.py` (mot de passe TCP en clair), `create_test_user.py`, `create_yann_user.py` (mots de passe en clair). À transformer en scripts de seed **explicites** sans credentials sensibles.
10. **Sessions TCP** : déjà en mémoire (`TCPServer.sessions`) → rien à migrer.

---

## 2. Fichiers concernés

### Créés
- `backend/app/xml_control/` — nouveau package :
  - `__init__.py`
  - `records.py` (représentations dict des entités CP, miroir de `to_dict()`)
  - `security_store.py`, `catalog_store.py`, `history_store.py`, `audit_store.py`
  - `store.py` (verrous, atomicité, checksum, snapshot/restore, `expected_version` — réutilise `xml_engine/storage.py`)
  - `validator.py` (validation XSD + fail-closed, réutilise le pattern XXE-safe de `xml_engine/document.py`)
  - `exporter.py` (export SQLite → XML déterministe)
  - `service.py` (`XmlControlPlaneService`)
- `backend/app/static/control/security.xsd`, `catalog.xsd`, `history.xsd`, `audit.xsd`
- `backend/data/control/` (généré) : `security.xml`, `catalog.xml`, `history.xml`, `audit/`
- `backend/tests/test_xml_control_plane.py` (+ `_auth`, `_permissions`, `_migration`, `_resilience` si nécessaire)
- `backend/scripts/export_control_plane.py` (CLI d'export)
- Docs : `PHASE_6_CONTROL_PLANE_XML_IMPLEMENTATION.md`, `CONTROL_PLANE_MIGRATION.md`, `CONTROL_PLANE_ROLLBACK.md`

### Modifiés (progressivement, sans casser)
- `app/config.py` : `CONTROL_BACKEND` (sqlite|xml|compare), `CONTROL_STORAGE_FOLDER`, `AUDIT_RETENTION_MONTHS` (défaut 24), `COMMON_PERMISSION_DEFAULT`.
- `app/__init__.py` : initialisation du CP XML, JWT loader (revoked en mémoire), seed, migrations conditionnelles.
- `app/services/auth_service.py`, `user_service.py`, `permission_service.py`, `database_service.py`, `audit_service.py`, `history_service.py`, `unlock_service.py`, `tcp_credential_service.py`.
- `app/auth/decorators.py`, `app/routes/auth.py` (logout), `app/tcp/tcp_server.py`.
- `app/models/database.py` (ajout `common_permission`) et éventuellement `app/models/table.py` (ajout `database_id` dans `table_permissions` est déjà OK).
- Découplage catalogue (6J/6L) : `query/service.py`, `query/xml_query_service.py`, `services/*`, `xml_engine/service.py`, `xml_engine/document.py`.
- `backend/.env.example` (documentation des nouveaux réglages).

### À purger / transformer (6L, uniquement après validation)
- Hardcodings dans `schema_migrations.py` et scripts racine `create_essoya_tcp.py`, `create_test_user.py`, `create_yann_user.py` (convertis en seed explicite **sans** credentials codés en dur).

---

## 3. Plan d'implémentation 6A → 6L

**6A — Infrastructure Control Plane XML**
- `app/xml_control/store.py` : `atomic_write`/`database_lock`/`snapshot`/`restore`/`checksum` (délègue à `xml_engine/storage.py`), plus `read_validated(path, xsd)` fail-closed et `mutate(path, mutator, expected_version)`.
- `config.py` : `CONTROL_BACKEND`, `CONTROL_STORAGE_FOLDER`, `AUDIT_RETENTION_MONTHS`.
- Aucune branche de code existante ne change de comportement (le CP XML est inerte tant que `CONTROL_BACKEND` n'est pas `xml`).
- **Tests** : unitaires du store (écriture atomique, verrou, version, checksum).

**6B — Modèles XML + XSD**
- `records.py` (dicts des entités : role, user, tcp_credential, database, database_permission, table_permission, history_entry, audit_entry).
- 4 XSD avec les contraintes exigées (unicité, keyref, `XML-XXXX-XXXX-XXXX`, port 1–65535, token_version ≥ 1).
- `validator.py`.
- **Tests** : validation XSD (valide/invalide), unicité, keyref, fail-closed sur fichier corrompu.

**6C — Export SQLite → XML**
- `exporter.py` : backup `xmlforge.db` + SHA-256, puis export déterministe de `roles, users, tcp_credentials, databases, database_permissions, table_permissions, history, audit_logs` (jamais `tables/columns/table_rows`).
- Conservation `internal_id`, backfill `uuid` manquant, tri stable par `id`.
- Vérifications de comptage (users, roles, databases, grants, history, audits, credentials).
- **Tests** : déterminisme (2 exports identiques), comptages, IDs conservés, pas de projection exportée.

**6D — XmlControlPlaneService**
- API centrale : `load_security()`, `load_catalog()`, `load_history()`, `load_audit(month)` ; `create_user`, `get_user`, `list_users`, `grant`, `revoke`, `log_audit`, `log_history`, `create_database`, … ; mutations via `mutate()` (verrou + expected_version + XSD + checksum).
- Cohérence inter-fichiers au démarrage (références user↔role↔grant↔database).
- **Tests** : cycle complet en mémoire/tmp.

**6E — Auth + Users + Roles**
- `AuthService`/`UserService` lisent/écrivent `security.xml` quand `CONTROL_BACKEND=xml` (sinon SQLite inchangé).
- Conserver bcrypt, `is_active`, `role`, `token_version`, `last_login`, JWT (secret hors XML).
- `create-admin`/seed → `security.xml`.
- **Tests** : registration/login/mauvais mdp/inactif/reset/token_version/rôle/email unique.

**6F — ACL + PERSONAL + COMMON**
- `PermissionService` : portage de l'ordre exact (absent/inactif → ADMIN → owner → **COMMON (common_permission)** → grant base → grant table → NONE).
- Ajout `common_permission` (modèle SQLite + doc XML Data Plane + `catalog.xml` + `DatabaseService`).
- Règle COMMON collective : aucun grant individuel requis ; les grants individuels ne contournent pas la sémantique collective (pas de « promotion » au-dessus du niveau collectif, sauf owner/admin).
- **Tests** : PERSONAL NONE/VIEW/EDIT/MANAGE/owner ; COMMON VIEW/EDIT/MANAGE + accès automatique d'un actif.

**6G — Audit + History**
- `AuditService`/`HistoryService` écrivent `audit/audit-YYYY-MM.xml` (rotation mensuelle, rétention configurable, compression gzip des mois anciens, purge contrôlée) et `history.xml`.
- **Tests** : écriture/lecture, rotation, rétention, compression, meta JSON, user_id nullable (audit pré-auth), before/after (history).

**6H — TCP credentials**
- `TcpCredentialService` lit/écrit `security.xml` (bcrypt, un credential par user, username unique).
- `tcp_server` : auth inchangée (même service), sessions mémoire.
- **Tests** : credentials, auth, mauvais password, compte inactif, permissions, SELECT/INSERT/UPDATE/DELETE/DDL, erreurs.

**6I — Double-write + Compare**
- `CONTROL_BACKEND=compare` : chaque opération CP est exécutée sur les deux backends, puis comparée (existence, IDs, valeurs, permissions, compteurs) → **diagnostic explicite**, aucune divergence masquée, aucun fallback silencieux.
- **Tests** : divergence détectée (ex. user présent en SQLite absent en XML → signalée).

**6J — XML comme source de vérité**
- Bascule des lectures CP sur XML ; SQLite reste en shadow écriture (compare en recette).
- Découplage catalogue : remplacement des `Table.query`/`Column.query`/`TableRow.query` par la lecture du Data Plane XML (`SchemaService`, `XmlEngineService.read_document`), sans changer les contrats REST (IDs entiers conservés).
- **Tests** : non-régression REST (databases/tables/columns/rows/schema/query) + TCP.

**6K — Tests sans Control Plane SQLite**
- Environnement où SQLAlchemy CP n'est **pas** initialisé (démarrage Flask, auth, users, DB, permissions, table/CRUD, TCP, audit, history, redémarrage).
- **Tests** : suite dédiée (marquée), prouvant l'absence de dépendance runtime à SQLite.

**6L — Suppression des dépendances SQLite du Control Plane**
- Recherche globale (`sqlalchemy`, `db.session`, `Model.query`, `sqlite3`, `sqlite_runtime`, `xmlforge.db`, `SQLALCHEMY_DATABASE_URI`, `schema_migrations`, `db.create_all`) → classification CRITIQUE/TRANSITOIRE/TEST/LEGACY/À SUPPRIMER.
- Suppression **uniquement** des occurrences prouvées inutilisées, après validation 6K.
- Purge des hardcodings (§24).
- **Rollback permanent** : `CONTROL_BACKEND=sqlite` reste fonctionnel jusqu'à la toute fin.

---

## 4. Risques

1. **Changement de sémantique COMMON** (comportement utilisateur) → tests dédiés + libellé frontend à corriger ; risque de régression si l'ordre ACL n'est pas reproduit fidèlement.
2. **Pas de transaction multi-fichiers** (security.xml ↔ catalog.xml) → ordre de verrouillage fixe, cohérence vérifiée au démarrage, détection d'opération partielle (ex. suppression user : grants → credentials → user en dernier).
3. **Régression ACL** : `delete→can_admin`, surcharge table en « OR », priorité owner/admin — tout doit être porté à l'identique (tests différentiels SQLite/XML en mode compare).
4. **Volatilité unlocks/revoked tokens** (changement de comportement vs SQLite) → tests de redémarrage (persistance vs disparition).
5. **IDs** : toute renumérotation casse REST/frontend/ACL/audit → `internal_id` figé, `uuid` backfillé sans remplacement.
6. **Fail-closed** : jamais de recréation silencieuse de `security.xml` vide, jamais de fallback silencieux SQLite←XML.
7. **Secret JWT** : jamais dans le XML (reste en environnement).
8. **Volumétrie audit** : rotation + rétention + compression obligatoires.
9. **Contrat REST/frontend** : préserver les clés de `to_dict()` et les `id` entiers.
10. **Double-write** : toute divergence doit être **visible** (log + rapport compare), jamais corrigée en silence.

---

## 5. Tests existants et tests à ajouter

### Existants (à conserver verts)
- `tests/test_auth_permissions.py` — auth, logout/révocation, rôles, PERSONAL/COMMON + grants (le test « COMMON sans effet » devra être **mis à jour** pour la nouvelle sémantique).
- `tests/test_tcp.py`, `tests/test_tables_rows.py`, `tests/test_xml_backend_mode.py` (mode XML pur), `tests/test_windows_storage.py`, `tests/test_xml_projection.py`, `tests/test_xml_engine_comparison.py`, `tests/test_xml_engine_*` (Data Plane), `tests/e2e/*` (REST/TCP/concurrence).
- **Attention** : `test_auth_permissions.py::test_personal_common_and_explicit_permissions` suppose qu'une base COMMON **n'est pas** visible par défaut → à adapter quand COMMON devient collectif.

### À ajouter
- `tests/test_xml_control_plane.py` (store, XSD, records, service) ;
- `tests/test_xml_control_plane_auth.py` (users/rôles/auth/token_version) ;
- `tests/test_xml_control_plane_permissions.py` (PERSONAL + COMMON VIEW/EDIT/MANAGE) ;
- `tests/test_xml_control_plane_migration.py` (export déterministe, IDs, comptages, backup SHA-256) ;
- `tests/test_xml_control_plane_resilience.py` (XML corrompu, XSD invalide, checksum, expected_version, concurrence, interruption, snapshot) ;
- `tests/test_xml_control_plane_no_sqlite.py` (6K — CP sans SQLite).

---

## Prochaine étape
Dès validation de cette analyse : **démarrer la Phase 6A** (infrastructure `xml_control` + `store.py` + config `CONTROL_BACKEND`), sans toucher au comportement existant, puis enchaîner 6B → 6C → … en validant les tests à chaque sous-phase.
