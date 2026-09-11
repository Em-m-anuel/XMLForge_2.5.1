# XMLForge — Audit complet post-Phase 7

**Date :** 2026-09-11
**Périmètre :** repository `/home/user/XMLForge` (backend, client Python, frontend, docs, tests)
**Méthode :** lecture/analyse de code, exécution réelle des tests, E2E REST+TCP sur environnement vierge, benchmarks mesurés, **aucune modification de code**.

---

## 1. Executive Summary

Le projet **XMLForge** est dans un état **fonctionnel et cohérent** : architecture XML-only réelle, moteur SQL XML natif complet, serveur TCP 3307 opérationnel, client Python officiel utilisable, REST et TCP partageant les mêmes services et la même ACL.

**Tous les tests passent** : 334/334 backend (~63 s), 10+1 frontend, E2E live frontend↔backend vert, E2E TCP 15/15, installation vierge sans aucun fichier `.db`/`.sqlite`, fail-closed vérifié sur XML corrompu, persistance vérifiée après redémarrage, concurrence d'allocation d'IDs vérifiée.

**Des problèmes réels subsistent, mais aucun ne bloque le fonctionnement ou la sécurité du runtime.** Les principaux sont :
1. **Aucun commit git** des Phases 5→7 (105 fichiers modifiés/supprimés + nombreux non suivis, 2 commits seulement, aucun remote) — risque de perte et historique incohérent (MAJEUR).
2. **Identifiants codés en dur** présents dans des docs legacy (`TP_JAVABD_SQL_GUIDE.md`, `app/tcp/SETUP.md`) — violation de la règle permanente du projet (MAJEUR).
3. **Workflow CI cassé** (référence des fichiers de test supprimés) (MOYEN).
4. **UI frontend « Projection SQLite » obsolète** (bouton sans effet réel + messages trompeurs) (MOYEN).
5. **Divergences doc↔code** sur le dialecte SQL (PK composite, `FOREIGN KEY (…)` table-level) (MOYEN).
6. Dette technique mineure : code mort, docstrings périmés, dépendance `eventlet` inutilisée, fichiers legacy physiques (MOYEN/MINEUR).

**Statut final : `PHASE_7_POST_AUDIT_ISSUES_FOUND`** — voir §32.

---

## 2. Architecture réelle

```
┌─────────────────────────────────────────────────────────────────────┐
│ Frontend React (xmlforge-react/, Vite 5173)                         │
│   → REST via /api (proxy Vite) + Socket.IO (optionnel, désactivé)   │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ REST :5000 (Flask)
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Services XMLForge (backend/app/services/)                            │
│   auth · user · permission (ACL unique) · database · table · column  │
│   row · schema · unlock (mémoire) · history · audit · tcp_credential │
│   export · import · sync · project · access                          │
└───────┬───────────────────────────────┬─────────────────────────────┘
        │                               │
        ▼                               ▼
┌───────────────────────┐      ┌──────────────────────────────────────┐
│ Control Plane (XML)    │      │ Data Plane (XML)                     │
│ xml_control/           │      │ data_plane/ (XmlDataPlane)           │
│  security.xml          │      │  data/xml/<id>_<slug>.xml            │
│  catalog.xml           │      │  (tables/colonnes/lignes,            │
│  history.xml           │      │   contraintes, index, versions)      │
│  audit/YYYY-MM.xml[.gz]│      └───────────────┬──────────────────────┘
│  (XSD, locks, versions,│                      │
│   checksum SHA-256,    │                      ▼
│   snapshot/restore)    │      ┌──────────────────────────────────────┐
└───────────────────────┘      │ XML Native Engine (xml_native.py)     │
                               │  SELECT/INSERT/UPDATE/DELETE/DDL/     │
                               │  agrégats/JOIN/index/PK/FK/UNIQUE     │
                               └───────────────┬──────────────────────┘
                                               ▼
                               ┌──────────────────────────────────────┐
                               │ XML Storage (storage.py)              │
                               │  flock/RLock, atomic_write, version,  │
                               │  checksum, snapshot/rollback          │
                               └──────────────────────────────────────┘

Application externe
   → xmlforge/ (client Python, stdlib uniquement)
   → TCP :3307 → tcp_server.py (sessions, transactions, erreurs métier)
   → mêmes services (XmlQueryService, PermissionService, XmlDataPlane)
```

**Vérifié :** REST (`routes/query.py`) et TCP (`tcp_server.py._handle_query`) appellent **tous deux** `XmlQueryService.execute_sql`. Une seule ACL (`PermissionService`) est consommée par les deux surfaces. **Pas de duplication de logique métier SQL/ACL** constatée.

**Compat « dual route » :** chaque blueprint est enregistré **deux fois** (racine `/` et `/api`, cf. `routes/__init__.py`). C'est un choix de compat documenté dans le code, mais cela expose **deux URL publiques par endpoint** (surface d'API doublée) et explique que `/health` (défini hors blueprint) n'existe **pas** sous `/api` (404) alors qu'il existe à la racine.

---

## 3. Vérification XML-only

Recherche exhaustive (`grep -ri` sur tout le dépôt, hors `.git`/`node_modules`/`.venv`/`dist`, puis restreinte aux fichiers de code `.py/.js/.jsx`).

### 3.1 Code actif (backend runtime)
**Aucun** `import sqlite3`, `import sqlalchemy`, `import flask_sqlalchemy`, `import mysql.connector` ne subsiste dans `backend/app/`. Les occurrences restantes dans le code sont :

| Occurrence | Classification | Détail |
|---|---|---|
| `data_plane/__init__.py::uses_sqlite()` | ACTIVE (shim) | retourne `False` en dur ; **importée mais jamais appelée** dans `auth/decorators.py` et `permission_service.py` (imports morts) |
| `config.py::SYNC_SQLITE_PROJECTION = False` | ACTIVE (shim) | compat, toujours False |
| `errors.py::ProjectionError` (code `SQLITE_PROJECTION_ERROR`) | MORT | classe définie, **jamais levée** dans `app/` |
| `control_plane/base.py::record_divergence/divergences/clear_divergences` | MORT | jamais appelés (conservés pour diagnostic) |
| `scripts/export_control_plane.py` | LEGACY | CLI d'export SQLite→XML de la Phase 6C |
| `app/tcp/xmlforge_client.py` | LEGACY (ACTIF en test) | ancien client (paramètre `engine='sqlite'` par défaut), utilisé par `tests/e2e/test_tcp_security_permissions_e2e.py` |
| docstrings périmées | DOCUMENTATION | `permission_service.py` (« le catalogue des tables reste en SQLite »), `views.py` (« le backend SQLite retourne les modèles ORM »), `xml_engine/__init__.py` (« projection SQLite »), `auth_service.py` (« backend sqlite \| xml \| compare ») |

### 3.2 Fichiers physiques `.db/.sqlite` présents sur le disque (gitignorés, non utilisés)

| Fichier | Taille | Statut |
|---|---|---|
| `backend/xmlforge.db` | 208 896 o | base SQLite 3.x historique (ancien Control Plane), **plus référencée par le code** |
| `backend/data/projections/1_schema-db.sqlite` | 12 288 o | ancienne projection, plus référencée |
| `backend/data/xml/1_schema-db.xml` + 2 fichiers `.lock` (0 o, dont 1 orphelin) | — | résidus d'une session de dev antérieure |

Ces fichiers sont couverts par `.gitignore` (non versionnés), mais présents sur la machine de dev.

### 3.3 Installation vierge (mesuré)
Bootstrap + E2E complet sur `/tmp` : **0 fichier** `.db`/`.sqlite`/`.sqlite3` créé (vérifié par `find`). ✅

### 3.4 Documentation
De nombreux documents historiques mentionnent SQLite/SQLAlchemy/MySQL : `MANUEL_TEST_VALIDATION_XMLFORGE.md`, `SQLITE_DEPENDENCIES.md`, `XML_BACKEND_MODE.md`, `QUICKSTART.md`, `README_TCP_COMPLETE.md`, rapports Phase 4/5/6, `backend/migrations/README.md`, `backend/postman_collection.json` (requête « Create real MySQL database »), `tcp-tester/` (moteurs `sqlite`/`compare`). Classés **DOCUMENTATION LEGACY** (historique) — à archiver/mettre à jour (voir §21, §26).

**Conclusion : SQLite/SQLAlchemy/MySQL sont réellement absents du runtime.** Les traces restantes sont soit des shims de compat inoffensifs, soit du code mort, soit des fichiers/doc legacy non supprimés.

---

## 4. Control Plane

| Élément | État | Preuve |
|---|---|---|
| `security.xml` (rôles admin/user, users bcrypt, tcp_credentials) | ✅ | bootstrap + create-admin observés ; hash `$2b$12$…` |
| `catalog.xml` (`next_object_id`, bases, permissions, miroir version/checksum) | ✅ | observé : `next_object_id=14`, `document_version=16`, `xml_checksum` SHA-256, `sync_status=SYNCED` |
| `history.xml` (before/after) | ✅ | observé |
| `audit/YYYY-MM.xml` (rotation, rétention, gzip) | ✅ | observé `audit-2026-09.xml` ; `audit_policy()` ne compresse/jamais le mois courant |
| Fail-closed démarrage (XSD security/catalog/history) | ✅ | `security.xml` corrompu → `XmlValidationError` au `create_app` (aucune régénération) |
| Fail-closed ré-exécution bootstrap | ✅ | re-bootstrap sans `force` → `ControlPlaneIntegrityError` |
| `allocate_object_id` sous verrou (compteur global) | ✅ | 8 threads × 100 = 800 IDs **uniques** en 255 ms |
| Transaction multi-documents CP (verrous ordonnés + snapshot/rollback) | ✅ | `_control_plane_transaction` (ordre de verrouillage déterministe, restore en cas d'exception) |
| Intégrité référentielle CP | ✅ | `validate_integrity()` (role_id, user_id, grants sur COMMON refusés) |
| Droits fichiers | ✅ | `control/` 0700, fichiers 0600 (vérifié `ls -la`) |

**Observations mineures :**
- Docstring de `bootstrap()` annonce `next_object_id=0` alors que le code crée `next_object_id=1` (docstring périmée).
- L'attribut `version` des fichiers d'audit reste à `1` : `add_audit()` est append-only sous verrou (unicité `internal_id`), sans incrément de version. Cohérent avec le modèle, mais l'attribut `version` n'est donc pas un indicateur fiable pour l'audit.

**Exposition des secrets :** `UserView.to_dict()` masque `password_hash` (`"***"`, optionnel) ; `TcpCredentialView.to_dict()` n'inclut **jamais** `tcp_password` ; le mot de passe TCP en clair n'est renvoyé qu'une seule fois à la création. `DatabaseView.to_dict()` n'expose ni `xml_file_path` ni `projection_path`. ✅

---

## 5. Data Plane

| Élément | État |
|---|---|
| Création/suppression de base | ✅ (ordre Data Plane puis catalogue, cf. correctif 6K) |
| CRUD tables/colonnes/lignes | ✅ |
| `mutate()` atomique + `expected_version` → `ConflictError` | ✅ (testé : `If-Match: 1` → `SYNC_CONFLICT`, « version courante 45 ») |
| Miroir catalogue (version/checksum/sync_status) | ✅ |
| `resolve_table` (id ou nom, dans une base) / `table_by_id` (O(nb bases)) | ✅ |
| Persistance après redémarrage | ✅ (voir §14) |

---

## 6. XML Native Engine

Fonctionnalités **vérifiées en exécution réelle** (REST + TCP) :

| Fonction | Testé |
|---|---|
| SELECT `*`, colonnes, alias `AS`, qualifiés `t.col` | ✅ |
| SELECT DISTINCT | ✅ |
| WHERE `= != <> < <= > >=`, AND/OR/parenthèses | ✅ |
| IN / NOT IN / LIKE / NOT LIKE / BETWEEN / IS NULL / IS NOT NULL | ✅ |
| ORDER BY (multi, DESC) | ✅ |
| LIMIT / OFFSET (pagination) | ✅ |
| COUNT / SUM / AVG / MIN / MAX | ✅ |
| GROUP BY / HAVING | ✅ |
| INNER JOIN / LEFT JOIN (NULL sur non-correspondance) | ✅ |
| INSERT simple / multi-lignes (atomique) | ✅ |
| UPDATE / DELETE **sans WHERE refusés** (« par sécurité ») | ✅ |
| CREATE TABLE (PK, UNIQUE, NOT NULL, DEFAULT, AUTO_INCREMENT, REFERENCES inline) | ✅ |
| ALTER TABLE ADD/MODIFY/DROP COLUMN, RENAME | ✅ (ADD avec backfill du DEFAULT observé) |
| DROP TABLE refusé si référencé par FK | ✅ (`« Table référencée par refs.book_id »`) |
| CREATE [UNIQUE] INDEX / DROP INDEX (simples et composites) | ✅ |
| Contraintes PK/UNIQUE/NOT NULL/FK (RESTRICT/CASCADE/SET NULL) | ✅ (couvert par tests) |
| AUTO_INCREMENT persistant (`next_auto_increment`) | ✅ (repris à 8 après redémarrage) |
| Types : INT/VARCHAR/FLOAT/DATE/DECIMAL/… | ✅ (couvert par tests) |

**Non testé en direct mais couvert par la suite** : MODIFY COLUMN, RENAME TABLE, DROP COLUMN, FK ON DELETE CASCADE/SET NULL (tests `test_xml_native_engine.py`).

---

## 7. Dialecte SQL — matrice réelle (doc ↔ parser ↔ engine ↔ tests)

| Fonction | Doc (`XMLFORGE_SQL.md`) | Parser | Engine | Tests | Verdict |
|---|---|---|---|---|---|
| SELECT / DISTINCT / alias | ✅ | ✅ | ✅ | ✅ | **CONFORME** |
| WHERE / AND / OR / parenthèses | ✅ | ✅ | ✅ | ✅ | **CONFORME** |
| IN / NOT IN / LIKE / NOT LIKE / BETWEEN / IS NULL | ✅ | ✅ | ✅ | ✅ | **CONFORME** |
| ORDER BY / LIMIT / OFFSET | ✅ | ✅ | ✅ | ✅ | **CONFORME** (défaut LIMIT=100 non documenté — cf. ci-dessous) |
| COUNT/SUM/AVG/MIN/MAX, GROUP BY, HAVING | ✅ | ✅ | ✅ | ✅ | **CONFORME** |
| INNER JOIN / LEFT JOIN | ✅ | ✅ | ✅ | ✅ | **CONFORME** |
| RIGHT / FULL OUTER JOIN | « refusé explicitement » | refusé via erreur générique | — | — | **COMPORTEMENT OK, MESSAGE DIVERGE** (la branche au message explicite est du code mort inatteignable) |
| INSERT (simple, multi, VALUES implicite) | ✅ | ✅ | ✅ | ✅ | **CONFORME** |
| UPDATE / DELETE (WHERE obligatoire) | ✅ | ✅ | ✅ (refus sans WHERE) | ✅ | **CONFORME** |
| CREATE TABLE — PK **simple** | ✅ | ✅ | ✅ | ✅ | **CONFORME** |
| CREATE TABLE — PK **composite** | ✅ annoncé | ❌ (aucune syntaxe `PRIMARY KEY (a,b)`) | ✅ (possible au niveau moteur) | ❌ (non testé) | **DIVERGENCE : annoncé mais non atteignable via SQL** |
| CREATE TABLE — `FOREIGN KEY (…) REFERENCES` table-level | « FK REFERENCES » (ambigu) | ❌ (`attendu IDENT, reçu FOREIGN`) | — | — | **DIVERGENCE partielle : seule la forme inline `col … REFERENCES t(c)` est supportée** |
| CREATE TABLE — UNIQUE / NOT NULL / DEFAULT / AUTO_INCREMENT | ✅ | ✅ | ✅ | ✅ | **CONFORME** |
| ALTER TABLE (ADD/MODIFY/DROP COLUMN, RENAME TO) | ✅ | ✅ | ✅ | ✅ | **CONFORME** |
| DROP TABLE refusé si FK | ✅ | — | ✅ | ✅ | **CONFORME** |
| CREATE [UNIQUE] INDEX / DROP INDEX | ✅ | ✅ | ✅ | ✅ | **CONFORME** |
| CREATE DATABASE / DROP DATABASE | ✅ | ✅ | ✅ | ✅ | **CONFORME** (mais `CREATE DATABASE` SQL force `scope=PERSONAL`) |
| USE / BEGIN / COMMIT / ROLLBACK | ✅ | ✅ | ✅ (session TCP) | ✅ | **CONFORME** |
| COUNT(DISTINCT), sous-requêtes, UNION | refusés | ❌ refusés | — | ✅ | **CONFORME** |

**Divergences relevées (détaillées §23) :**
1. PK composite : annoncé dans la doc, **impossible à exprimer en SQL** (le parser ne lit que `PRIMARY KEY` inline sur une colonne). Le moteur saurait le gérer (liste de `primary_key`), mais aucun chemin SQL/REST standard ne le produit.
2. `FOREIGN KEY (…) REFERENCES` table-level : non parsable ; seule la forme inline `REFERENCES t(col)` fonctionne.
3. LIMIT par défaut = **100** (implicite) non documenté.
4. `CREATE DATABASE` via SQL/TCP crée toujours une base `PERSONAL` (pas de `COMMON`/`common_permission` exposé en SQL).
5. Rejet RIGHT/FULL JOIN : message générique « Fin de requête inattendue » (la branche « refusé explicitement » du parser est inatteignable).

---

## 8. Protocole TCP

| Élément | Doc | Code | Verdict |
|---|---|---|---|
| Trame `[type:1][len:4 BE][JSON]` | ✅ | ✅ `pack_message/unpack_message` | **CONFORME** |
| Types 1..9 (AUTH/QUERY/RESPONSE/ERROR/PING/PONG/SELECT_DATABASE/UNLOCK_TABLE/CLOSE) | ✅ | ✅ | **CONFORME** |
| Codes réponse 0..5 | ✅ | ✅ | **CONFORME** |
| `error_code` additif (champ métier) | ✅ | ✅ `create_error(code, message, error_code=None)` | **CONFORME** |
| Lecture partielle (buffer + « Message incomplet ») | — | ✅ | OK |
| Taille maximale : 8 Mio/buffer | — | ✅ | OK (déconnexion propre au-delà) |
| Timeout socket 2 s / session 30 min | ✅ | ✅ | OK |
| JSON invalide → erreur | — | ✅ (`json.loads` échoue, traitée) | OK |
| Déconnexion brutale | — | ✅ sessions nettoyées en `finally` | OK |
| Plusieurs requêtes par connexion | ✅ | ✅ (boucle `_handle_client`) | OK |

**Testé en direct :** auth OK/échec, USE, SELECT/INSERT/UPDATE/DELETE, BEGIN/COMMIT/ROLLBACK, erreurs `TRANSACTION_ACTIVE`, `TRANSACTION_NOT_ACTIVE`, `DATABASE_NOT_SELECTED`, `TABLE_NOT_FOUND`, `SYNTAX_ERROR`, `AUTH_FAILED`.

**Nuance :** une erreur de `USE`/`SELECT_DATABASE` vers une base inexistante renvoie `error_code=INTERNAL_ERROR` (générique) au lieu d'un code plus précis (`DATABASE_NOT_FOUND`) — `_select_database_for_session` retourne une chaîne, sans exception typée. Amélioration possible (MINEUR).

---

## 9. Sessions TCP

`ClientSession` : `token` (uuid4, pas de champ `session_id`), `user_id`, `username`, `database_id`, `database_name`, `created_at`, `last_activity`, `authenticated`, `transaction_active/snapshot/path`. Stockage **mémoire** (`TCPServer.sessions`), purge sur timeout (`_purge_expired`) et à la déconnexion.

Testé : authentification unique, `USE` + changement de base, sessions simultanées (tests `test_phase7.py::test_tcp_sessions_are_isolated` et `test_tcp_concurrent_clients`), fermeture propre, reconnexion (nouveau token). `/api/tcp/status` et `/api/tcp/sessions` répondent correctement (observé : `running=true`, `active_sessions=0` après fermeture).

---

## 10. Transactions

| Cas | Comportement | Testé |
|---|---|---|
| `BEGIN` / `START TRANSACTION` | snapshot du document XML **et** de `catalog.xml` | ✅ (code + tests) |
| `BEGIN` → INSERT → `ROLLBACK` | restaure les deux snapshots | ✅ (count inchangé) |
| `BEGIN` → INSERT → `COMMIT` | libère le snapshot, données persistées | ✅ (count +1) |
| Double `BEGIN` | `TRANSACTION_ACTIVE` | ✅ |
| `COMMIT`/`ROLLBACK` sans transaction | `TRANSACTION_NOT_ACTIVE` | ✅ |
| Restauration impossible | `TRANSACTION_ERROR` | couvert par code |
| Redémarrage après COMMIT | données présentes | ✅ |

**Cohérence Data Plane ↔ Control Plane au rollback :** le snapshot couvre le document XML **et** le miroir `catalog.xml` (version/checksum), donc le rollback remet les deux en cohérence. ✅

**Limite documentée (assumée) :** pas de MVCC — les écritures sont immédiates ; un lecteur peut voir des modifications non validées ; dernier écrivain gagnant. Conforme à `XMLFORGE_TRANSACTIONS.md`.

---

## 11. Transactions vs audit/history

**Vérifié dans le code :** `_tx_rollback()` ne restaure que `transaction_path["xml"]` et `transaction_path["catalog"]`. Les fichiers `audit-*.xml` et `history.xml` ne sont **jamais** touchés par le rollback → audit/history sont **append-only**, conformes à la documentation. Un `ROLLBACK` laisse donc des entrées d'audit/historique correspondant à des opérations annulées — sémantique documentée et respectée. ✅

**Ce qui est transactionnel :** le document XML de la base + le miroir catalogue (version/checksum).
**Ce qui ne l'est pas :** audit, historique, unlocks (mémoire), sessions, `security.xml`.

---

## 12. Client Python

Package `xmlforge/` (stdlib uniquement). API : `connect()`, `Connection` (`authenticate/use/execute/query/close`, context manager), `Result`, `errors` (`XmlforgeError(message, code, numeric_code)`).

**E2E réel : 15/15 OK** (auth, USE, SELECT, COUNT, INSERT, UPDATE, DELETE, transactions, erreurs métier, `DATABASE_NOT_SELECTED`, `TABLE_NOT_FOUND`, `SYNTAX_ERROR`). Reconnexion et fermeture testées. Le client synchronise `database_id/name` après `USE`. ✅

---

## 13. Format Result

Champs vérifiés en réel :

| Champ | SELECT | INSERT | UPDATE/DELETE | COUNT | DDL/USE/transaction |
|---|---|---|---|---|---|
| `columns` | ✅ | — | — | `['count']` | — |
| `rows` | ✅ | — | — | `[{'count':N}]` | — |
| `row_count` | ✅ (total) | — | — | ✅ | — |
| `affected_rows` | — | ✅ | ✅ | — | — |
| `last_insert_id` | — | ✅ (id=6 observé) | — | — | — |
| `metadata` | pagination… | — | — | — | ✅ |

Conforme à `XMLFORGE_CLIENT.md`. ✅

---

## 14. Permissions

Logique unique `PermissionService` (REST **et** TCP) : admin → owner → COMMON collectif (`common_permission` ∈ {VIEW, EDIT, MANAGE}, défaut `COMMON_PERMISSION_DEFAULT`) → grants PERSONAL (`can_read/write/ddl/admin`), `delete → can_admin`. **Aucun grant individuel sur COMMON** (refusé, vérifié dans `grant_database`/`grant_table` et `validate_integrity`).

**Testé en direct :** base COMMON créée et accessible ; refus d'accès pour utilisateur non autorisé ; scénarios PERSONAL/COMMON couverts par `tests/e2e/test_tcp_security_permissions_e2e.py` (1 test complet AUTH/scopes/permissions/protection/erreurs structurées) et `test_auth_permissions.py`. `uses_sqlite` n'intervient jamais dans la décision (import mort). ✅

---

## 15. Sécurité

| Test | Résultat |
|---|---|
| TCP non authentifié / mauvais mot de passe / user inconnu | ✅ `AUTH_FAILED` |
| JWT invalide / absent | ✅ 401 |
| Utilisateur inactif / token_version | ✅ (loader `token_verification_loader` + tests) |
| JSON REST malformé | ✅ erreur 400 (message brut Flask, sans traceback) |
| Trame TCP malformée | ✅ (gestion `ValueError` « Message incomplet ») |
| Requête SQL invalide | ✅ `SYNTAX_ERROR` |
| **Path traversal** (nom de base `../../etc/pwned`, `a/b\c`) | ✅ refusé (validation « lettres, chiffres, underscore ») |
| Fichiers XML du Control Plane | ✅ jamais servis en statique, dossier 0700 |
| Secrets | ✅ bcrypt ; `password_hash` jamais renvoyé ; `tcp_password` jamais renvoyé (sauf création one-shot) ; pas de chemin de fichier exposé |
| Secrets de configuration | ⚠️ `SECRET_KEY`/`JWT_SECRET_KEY` ont des **défauts dev** dans `Config` (bloqués en production par `ProductionConfig.validate()`) |
| Corruption XML (control + data) | ✅ fail-closed, aucune régénération silencieuse |

**Problème : identifiants codés en dur dans des documents** (violation de la règle permanente du projet) :
- `TP_JAVABD_SQL_GUIDE.md` : `Username: <identifiant TCP retiré>`, `Password: <mot de passe retiré>`, et `'<mot de passe retiré>'` dans des données d'exemple.
- `backend/app/tcp/SETUP.md` (ligne 275) : `password=<retiré>`.

Aucune exploitation destructive n'a été tentée.

---

## 16. IDs et concurrence

| Élément | Résultat |
|---|---|
| `catalog.next_object_id` persistant, alloué sous verrou, jamais réutilisé | ✅ (observé : `next_object_id=14` après la session) |
| `AUTO_INCREMENT` persistant (`next_auto_increment`) | ✅ (repris à 8 après redémarrage) |
| `internal_id` + `uuid` backfill | ✅ (présents sur tables/colonnes/lignes) |
| Allocation concurrente | ✅ 8 threads × 100 = 800 IDs **uniques**, aucun doublon, 255 ms |
| Rollback | ✅ (l'état du compteur est restauré avec le snapshot du document) |

---

## 17. Persistance

Scénario « create → write → close → **restart** → read » **exécuté en réel** :
- base, tables, colonnes, lignes, index, contraintes, `next_auto_increment`, permissions (catalogue), utilisateurs (security.xml), audit, historique — **tout persiste**. ✅
- Après redémarrage : SELECT renvoie les 5 lignes attendues, INSERT suivant obtient `id=8` (continuité AUTO_INCREMENT), `authors` intacte.

---

## 18. Corruption XML

| Fichier corrompu | Comportement |
|---|---|
| `security.xml` | `create_app` lève `XmlValidationError` (fail-closed) ✅ |
| `catalog.xml` / `history.xml` | même chemin `read_validated` (XSD) ✅ |
| Document Data Plane (en cours d'exécution) | `SELECT` → erreur explicite `XML mal formé: …`, **fichier non régénéré** ✅ ; restauration manuelle → SELECT OK |

---

## 19. Frontend

| Commande | Résultat réel |
|---|---|
| `npm test` | **10 passed | 1 skipped** (le test live est sautillé sans backend) |
| `npm run lint` | **0 erreur, 3 avertissements** (fast-refresh) |
| `npm run build` | **OK** (vite 8.1.5, 345 ms) |
| `VITE_API_URL=http://localhost:5000/api XMLFORGE_LIVE_E2E=1 npx vitest run src/test/liveBackend.test.js` | **1 passed** (login, CRUD, XML, COMMON collectif, conflit `expected_version` contre le backend réel) |

**Divergence frontend↔backend :** la section « **Projection SQLite** » de `Workspace.jsx` (lignes ~1044-1061) affiche un bouton « Reconstruire la projection » avec le message de succès « La base SQLite de projection a été régénérée à partir du XML source » — **mensonger** : la route `POST /databases/<id>/rebuild-projection` est conservée « sans effet » et répond `{projection: "XML_ONLY"}` (voir `routes/sync.py`). L'UI présente donc une fonctionnalité qui n'existe plus. (Le sélecteur `common_permission` et la modale « COMMON collectif » corrigés en 6K sont bien présents.)

---

## 20. E2E réel (REST + TCP + frontend)

**Scénario exécuté sur environnement vierge (`/tmp/xmlforge-audit`) :**
1. `xml-bootstrap` (rôles admin/user) → `create-admin` → démarrage Flask :5000 + TCP :3307.
2. REST : login → `/me` → création base COMMON (common_permission=EDIT) → `CREATE TABLE` → `INSERT ×3` → `SELECT`/WHERE/ORDER BY → agrégats/GROUP BY/HAVING → DISTINCT/LIKE/IN/BETWEEN/IS NULL → UPDATE/DELETE → index → ALTER → LEFT JOIN.
3. TCP (client officiel) : 15/15 scénarios (cf. §12).
4. Conflit optimiste `expected_version` → 409.
5. **Arrêt → redémarrage → reconnexion → SELECT** : données présentes.
6. Corruption XML → fail-closed.
7. Cohérence REST/TCP/XML : les mêmes données sont visibles par les deux surfaces (même document XML).

✅ Cohérence complète constatée entre REST, TCP et les fichiers XML.

---

## 21. Tests

**Chiffres réels (mesurés, non repris du rapport) :**

| Suite | Résultat |
|---|---|
| `pytest -q` (backend) | **334 passed** en **63,45 s** (0 failed, 0 skipped, 0 xfailed) |
| `pytest tests/e2e` | **1 passed** (3,84 s) |
| Frontend `npm test` | 10 passed / 1 skipped |
| Frontend live E2E (backend réel) | 1 passed |
| `npm run lint` | 0 erreur / 3 warnings |
| `npm run build` | OK |
| `pip check` | « No broken requirements found » |

**Tests les plus lents** (backend) : `test_tcp_full_ddl_and_operators` 2,06 s ; `test_schema_forbidden_without_share` 1,25 s. Aucun test anormalement long.

**Classification :** unitaires (moteur, parser, records, store) ; intégration (services, REST via test_client) ; E2E TCP réel (socket + framing) ; frontend (vitest + 1 live) ; concurrency (écritures concurrentes) ; sécurité/permissions. Le chiffre 334 correspond bien au rapport Phase 7.

**Problème :** le workflow CI `.github/workflows/backend-e2e-windows.yml` référence `tests/test_windows_storage.py` (**fichier inexistant**) et `tests/e2e` — le job échouerait tel quel (`test_windows_storage.py` a été supprimé).

---

## 22. Dépendances

### Backend (`requirements.txt`)
| Paquet | Utilisé ? | Verdict |
|---|---|---|
| Flask 3.1.0, Flask-JWT-Extended 4.7.1, Flask-Bcrypt 1.0.1, Flask-CORS 5.0.0, Flask-SocketIO 5.3.6 | ✅ | OK |
| lxml 6.0.0 | ✅ | OK |
| marshmallow 3.22.0 | ✅ (`utils/validators.py`) | OK |
| python-dotenv 1.0.1 | ✅ (`config.py`) | OK |
| pytest / pytest-cov | ✅ (dev) | OK |
| **eventlet 0.36.1** | ❌ **inutilisé** (SocketIO en `async_mode='threading'`) | **À retirer ou à utiliser** |

### Frontend (`package.json`)
React 19, react-router 7, monaco, dompurify, socket.io-client (optionnel), Vite 8, Vitest 3, Playwright, oxlint.
`npm audit` : **2 vulnérabilités modérées** (vitest/@vitest/mocker, dev-only ; correctif = montée majeure vitest 4.1.11). Pas de vulnérabilité de production détectée.

---

## 23. Configuration

`backend/app/config.py` + `.env.example` : valeurs par défaut cohérentes (`CONTROL_BACKEND=xml`, `DATA_BACKEND=xml`, `QUERY_BACKEND=xml`, `SYNC_SQLITE_PROJECTION=False`, TCP 3307, timeout 30 min, rétention audit 24, compression gzip, `COMMON_PERMISSION_DEFAULT=VIEW`). `Config.validate()` refuse une valeur invalide de `COMMON_PERMISSION_DEFAULT` ou une rétention < 1 ; `ProductionConfig.validate()` exige des secrets explicites (pas de défaut dev).

**Installation propre :** testée — le projet ne dépend d'**aucun** état local, credentials machine, XML ancien ni cache (E2E complet sur répertoires temporaires vides). ✅
`backend/config.py` (racine) et `backend/app/app.py` sont des **shims de compat** (ré-export/alias) — fonctionnels.

---

## 24. Performance (confirmation, pas d'optimisation)

Mesures réelles de confirmation (environnement audit) :

| Mesure | Résultat | Référence Phase 7 | Verdict |
|---|---|---|---|
| `resolve_table(table_by_id)` scan complet (1 base) | **1,67 ms** | ~0,4 ms/base | cohérent |
| `read_document` (parse+validate, petit doc) | **1,02 ms** | — | cohérent |
| TCP SELECT round-trip (50 ex., petit jeu) | **médiane 8,27 ms** | ~19,6 ms (200 lignes) | cohérent (moins de données) |
| TCP INSERT round-trip (20 ex.) | **médiane 12,31 ms** | ~27,8 ms (200 lignes) | cohérent |
| `allocate_object_id` concurrent (8×100) | **800 IDs uniques, 255 ms** | — | OK |

**Aucune régression détectée.** Write amplification et `resolve_table` O(nb bases) restent les limites connues (documentées), non retravaillées ici.

---

## 25. Fichiers legacy / inutilisés

| Élément | Statut |
|---|---|
| `backend/xmlforge.db` (SQLite, 208 Ko) | LEGACY (non référencé, gitignoré) |
| `backend/data/projections/1_schema-db.sqlite` | LEGACY (gitignoré) |
| `backend/data/xml/1_schema-db.xml` + `.lock` (dont 1 orphelin `1_browser-…`) | LEGACY (résidus dev, gitignorés) |
| `backend/BaseDonnees_INPTIC.xml`, `InptricConcours_database.xml`, `base_donnees_alumni_inptic.xml`, `inptic_database_schema.xml`, `soutenance_app.xml`, `backend/test.xml` | UNUSED (aucune référence littérale dans le code/tests) |
| `backend/bibliotheque_engine_test.xml` | ACTIF (fixture de `test_xml_native_engine.py`) |
| `backend/scripts/export_control_plane.py` | LEGACY (export SQLite→XML Phase 6C) |
| `backend/scripts/generate_engine_test_base.py` | ACTIF (génère la fixture moteur) |
| `backend/migrations/README.md` | LEGACY (décrit des migrations SQLAlchemy disparues ; mentionne `<email historique retiré>`) |
| `backend/postman_collection.json` | LEGACY (contient « Create real MySQL database ») |
| `backend/test_tcp_server.py` | LEGACY (script de smoke-test pré-Phase 7) |
| `app/tcp/xmlforge_client.py` + `app/tcp/SETUP.md` + `app/tcp/examples.py` | LEGACY (client historique) — `xmlforge_client.py` encore utilisé par 1 test e2e |
| `tcp-tester/` (Express :3000) | LEGACY (conçu pour comparer moteurs `sqlite`/`xml`/`compare` ; le serveur ignore désormais `engine`) |
| `backend/config.py` (racine), `backend/app/app.py` | ACTIF (shims de compat) |
| Docs racine pré-Phase 6 (`QUICKSTART.md`, `README_TCP_COMPLETE.md`, `XML_BACKEND_MODE.md`, `SQLITE_DEPENDENCIES.md`, `MANUEL_TEST_VALIDATION_XMLFORGE.md`, `TP_JAVABD_SQL_GUIDE.md`, `EVOLUTIONS_V4.md`, `FRONTEND_*.md`, `IMPLEMENTATION_SUMMARY.md`) | DOCUMENTATION LEGACY |

---

## 26. Documentation

**À jour et conforme au code (vérifiées) :** `XMLFORGE_SERVER.md`, `XMLFORGE_PROTOCOL.md`, `XMLFORGE_SQL.md` (hors divergences §7), `XMLFORGE_CLIENT.md`, `XMLFORGE_TRANSACTIONS.md`, `XMLFORGE_CONCURRENCY.md`, `XMLFORGE_ERRORS.md`, `backend/README.md`, `xmlforge-react/README.md`.

**Périmées / divergentes :**
- `QUICKSTART.md` et `README_TCP_COMPLETE.md` : décrivent l'ancien serveur TCP (client Node, `test_tcp_server.py`, Express) — dépassés par la Phase 7.
- `XML_BACKEND_MODE.md`, `SQLITE_DEPENDENCIES.md`, `MANUEL_TEST_VALIDATION_XMLFORGE.md`, rapports Phase 4/5/6 : historique (SQLite/SQLAlchemy), à considérer comme archives.
- `TP_JAVABD_SQL_GUIDE.md` : guide TP avec **identifiants en clair**.
- `backend/migrations/README.md` : décrit des migrations SQLAlchemy qui n'existent plus.
- **Absence de `README.md` à la racine** du dépôt : l'entrée documentaire principale est `backend/README.md` ; les deux fichiers `README*` de la racine sont obsolètes.

---

## 27. Qualité du code

Points positifs : séparation claire (control_plane / data_plane / query / xml_engine / tcp), docstrings françaises soignées, gestion d'erreurs typée (`errors.py`), pas de dépendance circulaire (services/__init__ léger), écriture atomique centralisée.

Points à améliorer (non corrigés, conformément à la consigne) :
1. **Code mort** : `uses_sqlite()` importé sans appel (2 fichiers) ; `record_divergence/divergences/clear_divergences` ; `ProjectionError` ; branche « RIGHT/FULL refusés » inatteignable du parser.
2. **Docstrings périmées** : `permission_service.py`, `views.py`, `xml_engine/__init__.py`, `auth_service.py` mentionnent encore SQLite/SQLAlchemy.
3. **Duplication d'URL** : enregistrement de chaque blueprint deux fois (racine + `/api`).
4. `_handle_query` du serveur TCP : `USE` échoue avec `INTERNAL_ERROR` générique.
5. Docstring `bootstrap()` : `next_object_id=0` vs code `=1`.
6. `add_audit()` : attribut `version` jamais incrémenté (informationnel).

---

## 28. Installation propre (mesuré)

Exécutée sur `/tmp/xmlforge-audit` (aucun état préexistant) : bootstrap → create-admin → Flask → TCP → client Python → CRUD → transactions → **redémarrage → reconnexion**. Vérifié : **aucun** `.db`/`.sqlite`/`.sqlite3` créé ; aucune dépendance à un état local. ✅

---

## 29. Analyse des risques

### CRITIQUE
*Aucun.*

### MAJEUR
- **R-1 — Travail non commité.** `git status` : ~105 fichiers modifiés/supprimés + de nombreux non suivis ; 2 commits seulement (`Initial XMLForge repository`, `Mise à jour du projet`) ; **aucun remote**. La totalité des Phases 5→7 n'est protégée par aucun historique. Risque de perte + impossibilité de rollback. *(Preuve : `git log --oneline`, `git status --short`.)*
- **R-2 — Identifiants codés en dur dans la doc** (violation de la règle permanente) : `TP_JAVABD_SQL_GUIDE.md` (`<identifiant TCP retiré>` / `<mot de passe retiré>` / `<mot de passe retiré>`), `backend/app/tcp/SETUP.md` (`password=<retiré>`). *(Preuve : grep.)*

### MOYEN
- **R-3 — Workflow CI cassé** : `.github/workflows/backend-e2e-windows.yml` référence `tests/test_windows_storage.py` (supprimé) → le job échouerait.
- **R-4 — UI frontend « Projection SQLite » obsolète** (`Workspace.jsx`) : bouton sans effet réel + message de succès trompeur.
- **R-5 — Divergences doc↔code SQL** : PK composite annoncé mais non atteignable en SQL ; `FOREIGN KEY (…)` table-level non parsable.
- **R-6 — Fichiers legacy physiques** (`xmlforge.db`, `data/projections/*.sqlite`, résidus `data/xml/`) encore présents sur la machine de dev — source de confusion (même s'ils sont gitignorés et non utilisés).
- **R-7 — Pas de `README.md` racine** ; les deux `README*` racine sont obsolètes.
- **R-8 — `eventlet` inutilisé** dans `requirements.txt`.

### MINEUR
- **R-9** — Code mort : `uses_sqlite` (imports), `record_divergence`/`divergences`, `ProjectionError`, branche RIGHT/FULL inatteignable.
- **R-10** — Docstrings périmées (permission_service, views, xml_engine/__init__, auth_service).
- **R-11** — `/api/health` → 404 (health uniquement à la racine).
- **R-12** — `USE`/`SELECT_DATABASE` échouent avec `INTERNAL_ERROR` (au lieu de `DATABASE_NOT_FOUND`).
- **R-13** — LIMIT implicite = 100 non documenté.
- **R-14** — `CREATE DATABASE` SQL force `scope=PERSONAL` (pas de COMMON possible via SQL/TCP).
- **R-15** — Docstring `bootstrap()` `next_object_id=0` ≠ code `1`.
- **R-16** — `audit-*.xml` : attribut `version` statique (append-only informationnel).
- **R-17** — Blueprints dupliqués racine + `/api` (surface d'URL doublée).
- **R-18** — `npm audit` : 2 vulnérabilités modérées (dev-only).

### INFORMATION
- Write amplification XML (réécriture complète) — documentée, assumée.
- `resolve_table` O(nb bases) — documentée.
- Pas de MVCC (transactions dernier-écrivain-gagnant) — documentée.
- Lignes sans `creator_id`/`created_at` (présents sur tables/colonnes) — documenté.
- Fichiers `.lock` de 0 octet laissés sur disque (normal avec `flock`).
- `audit`/`history` append-only non annulés par ROLLBACK — documenté et conforme.

---

## 30. Fiches « Fait / Preuve / Impact / Sévérité / Recommandation » (principaux)

**PROBLÈME 1 — Travail non versionné**
- Fait : toute la migration XML-only (Phases 5→7) est non commitée.
- Preuve : `git log --oneline` (2 commits) ; `git status --short` (~105 M/D + untracked).
- Impact : risque de perte de tout le travail ; aucune capacité de retour arrière ; historique incohérent (le dernier commit contient l'ancienne architecture SQLAlchemy).
- Sévérité : MAJEUR.
- Recommandation : commit structuré (par phase) + création d'un remote ; idéalement réécrire l'historique des modèles supprimés avant publication.

**PROBLÈME 2 — Identifiants codés en dur dans la doc**
- Fait : `<identifiant TCP retiré>`/`<mot de passe retiré>`/`<mot de passe retiré>` dans `TP_JAVABD_SQL_GUIDE.md` ; `password=<retiré>` dans `app/tcp/SETUP.md`.
- Preuve : grep (résultats ci-dessus).
- Impact : violation de la règle permanente du projet ; fuite potentielle de comptes réels.
- Sévérité : MAJEUR.
- Recommandation : remplacer par des placeholders (`<À RENSEIGNER>`), comme déjà fait dans `MANUEL_TEST_VALIDATION_XMLFORGE.md`.

**PROBLÈME 3 — PK composite annoncé mais non supporté en SQL**
- Fait : `XMLFORGE_SQL.md` annonce « PK simple/composite ».
- Preuve : `sql_parser.py::_column_def` ne lit que `PRIMARY KEY` inline ; `CREATE TABLE pk2 (a INT, b INT, PRIMARY KEY (a, b))` → « attendu IDENT, reçu PRIMARY ». Le moteur gère une liste de `primary_key` mais aucun chemin ne la produit.
- Impact : documentation surévaluée ; fonctionnalité indisponible aux utilisateurs.
- Sévérité : MOYEN.
- Recommandation : soit documenter « PK simple uniquement (via SQL) », soit ajouter la clause table-level `PRIMARY KEY (…)`.

**PROBLÈME 4 — UI « Projection SQLite » obsolète**
- Fait : `Workspace.jsx` affiche un bouton de reconstruction de projection SQLite et un message de succès mensonger.
- Preuve : `Workspace.jsx:1044-1061`, `databaseService.js:22`, route `sync.py` « sans effet » répondant `projection: XML_ONLY`.
- Impact : UX trompeuse ; confusion utilisateur.
- Sévérité : MOYEN.
- Recommandation : retirer la section (ou la remplacer par un indicateur « stockage XML ») et supprimer l'appel `rebuildProjection`.

**PROBLÈME 5 — CI cassé**
- Fait : le workflow Windows référence un fichier de test supprimé.
- Preuve : `.github/workflows/backend-e2e-windows.yml` → `pytest tests/test_windows_storage.py` (inexistant).
- Impact : CI rouge sur tout push backend.
- Sévérité : MOYEN.
- Recommandation : mettre à jour le workflow (supprimer la référence ou recréer le test).

---

## 31. Fichiers inspectés (principaux)

- `backend/app/__init__.py`, `config.py`, `extensions.py`, `errors.py`, `app.py`
- `backend/app/control_plane/` : `base.py`, `views.py`, `xml_backend.py`, `volatile.py`
- `backend/app/xml_control/` : `store.py`, `records.py`, `service.py`
- `backend/app/data_plane/` : `__init__.py`, `xml_backend.py`, `xml_services.py`
- `backend/app/query/` : `sql_parser.py`, `xml_executor.py`, `xml_query_service.py`
- `backend/app/xml_engine/` : `document.py`, `service.py`, `storage.py`, `xml_native.py`
- `backend/app/tcp/` : `tcp_protocol.py`, `tcp_server.py`, `xmlforge_client.py`, `SETUP.md`, `examples.py`
- `backend/app/services/` : auth, user, permission, unlock, database, table, column, row, schema, history, audit, tcp_credential, export, import, sync, project, access
- `backend/app/routes/` : `__init__.py`, auth, databases, tables, columns, rows, query, sync, tcp, users, permissions, imports, exports, history, audit, unlock, metadata, converters, projects
- `backend/tests/` (16 fichiers + `e2e/`), `pytest.ini`, `conftest.py`
- `xmlforge/` (client, connection, protocol, result, errors), `examples/python_client_demo.py`
- `xmlforge-react/` (package.json, Workspace.jsx, databaseService.js, tests)
- `.github/workflows/backend-e2e-windows.yml`, `.gitignore`, `backend/requirements.txt`
- Docs racine : `XMLFORGE_*.md` (7), `QUICKSTART.md`, `README_TCP_COMPLETE.md`, rapports Phase 4→7, etc.

## 32. Fichiers modifiés

**AUCUN fichier du dépôt n'a été modifié, créé ou supprimé.**

Le seul fichier créé est le présent rapport (`PHASE_7_POST_AUDIT_REPORT.md`), comme demandé. Les artefacts d'audit ont été créés dans `/tmp/xmlforge-audit`, `/tmp/xmlforge-corrupt` et `/tmp/xmlforge-audit/*.py` (hors dépôt) ; le serveur d'audit a été arrêté et ces répertoires temporaires supprimés à la fin de l'audit. `npm ci` a (ré)installé `xmlforge-react/node_modules` (dossier non versionné et exclu des snapshots) — état fonctionnel identique à la reprise.

## 33. Commandes et résultats réels

| Commande | Résultat |
|---|---|
| `cd backend && .venv/bin/python -m pytest -q` | **334 passed in 63.45s** |
| `cd backend && .venv/bin/python -m pytest tests/e2e -q` | **1 passed in 3.84s** |
| `cd xmlforge-react && npm test` | **10 passed | 1 skipped** |
| `cd xmlforge-react && npm run lint` | **0 error, 3 warnings** |
| `cd xmlforge-react && npm run build` | **OK** |
| `VITE_API_URL=http://localhost:5000/api XMLFORGE_LIVE_E2E=1 npx vitest run src/test/liveBackend.test.js` | **1 passed** |
| E2E TCP client officiel (script d'audit) | **15/15 OK** |
| Benchmark confirmation (script d'audit) | resolve_table 1,67 ms ; read_document 1,02 ms ; 800 IDs uniques/255 ms ; TCP SELECT médiane 8,27 ms ; INSERT 12,31 ms |
| `find /tmp/xmlforge-audit -name '*.db' -o -name '*.sqlite*'` | **0** |
| `pip check` | No broken requirements found |
| `npm audit` | 2 moderate (dev-only) |

---

## 34. Statut final

```text
PHASE_7_POST_AUDIT_ISSUES_FOUND
```

**Justification :** le système est fonctionnel (aucun problème CRITIQUE ; tous les tests verts ; E2E REST/TCP/frontend réels validés ; XML-only réel et persistant). L'audit a néanmoins mis en évidence des problèmes qui **doivent être corrigés avant d'entamer une nouvelle phase** : absence totale de versionnement git des Phases 5→7 (MAJEUR), identifiants codés en dur dans deux documents (MAJEUR, violation de règle permanente), CI cassé, UI frontend obsolète, divergences doc↔code sur le SQL, code mort et fichiers legacy. Aucun de ces points ne bloque le runtime, ce qui exclut le statut `CRITICAL_ISSUES`, mais ils empêchent de déclarer l'état `CLEAN`.

**Recommandations priorisées :**
- **P0** : commit du travail (par phase) + remote ; retrait des identifiants en clair des docs.
- **P1** : mise à jour du workflow CI ; retrait de l'UI « Projection SQLite » ; alignement doc↔code du dialecte SQL (PK composite, `FOREIGN KEY (…)`).
- **P2** : nettoyage des fichiers legacy (`.db`, `.sqlite`, XML inutilisés, `eventlet`) ; `README.md` racine à jour ; suppression du code mort et des docstrings périmés.
- **P3** : granularité des codes d'erreur TCP (`USE`), documentation de LIMIT=100, statut `version` de l'audit, déduplication des URL racine/`/api` (à étudier pour non-régression du frontend).
