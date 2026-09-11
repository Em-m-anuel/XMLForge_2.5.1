# PHASE 6J-B — Retrait définitif de SQLite et architecture XML-only

**Date** : 2026-09-08

---

## 1. État avant 6J-B

XML-only dans le **chemin d'exécution** (6H/6I) mais composants SQLite encore
**présents physiquement** : modèles ORM (`app/models/`), `schema_migrations.py`,
`sqlite_backend.py`, `compare_backend.py`, `exporter.py`, `projection.py`,
`sqlite_runtime.py`, `QueryService` (sqlite), `comparator.py`, export/import
SQLite, `db` SQLAlchemy, 420 tests.

## 2. Audit SQLite (classification avant suppression)

| Élément | Runtime XML ? | Classe | Remplacement XML | Suppression |
|---|---|---|---|---|
| `app/models/*` (13 modèles) | non | LEGACY | records + vues | ✅ |
| `app/schema_migrations.py` | non | LEGACY | version document XML | ✅ |
| `app/query/service.py` + `sqlite_runtime.py` + `projection.py` | non | LEGACY | XmlQueryService / XmlDataPlane | ✅ |
| `app/query/comparator.py` + `sql_render.py` | non | COMPARAISON | — (plus de comparaison runtime) | ✅ |
| `app/control_plane/sqlite_backend.py` + `compare_backend.py` | non | FALLBACK | XmlControlPlane | ✅ |
| `app/xml_control/exporter.py` | non | MIGRATION | `xml-bootstrap` | ✅ |
| `app/routes/database_create.py` + mysql.connector | non | LEGACY | — (non utilisé par le frontend) | ✅ |
| `app/extensions.py` (db SQLAlchemy) | non | RUNTIME retiré | extensions sans db | ✅ |
| services export/import/sync/project | oui (résolution ORM) | ADAPTÉ | XmlDataPlane | réécrits XML |
| `app/xml_engine/storage.py` (sidecars SQLite) | partiel | NETTOYÉ | atomic_write/lock/unlink purs | ✅ |

## 3. Fichiers supprimés

- `app/models/` (13 modèles), `app/database/`, `app/schema_migrations.py`
- `app/query/service.py`, `app/query/sqlite_runtime.py`, `app/query/comparator.py`, `app/query/sql_render.py`
- `app/xml_engine/projection.py`
- `app/control_plane/sqlite_backend.py`, `app/control_plane/compare_backend.py`
- `app/xml_control/exporter.py`
- `app/routes/database_create.py`
- Scripts dev legacy : `check_user.py`, `create_essoya_tcp.py`, `create_test_user.py`, `create_yann_user.py`, `get_tp_javabd_tables.py`, `test_tcp_credentials.py`

**Tests d'implémentation SQLite supprimés** (couverture métier conservée côté XML) :
`test_xml_projection.py`, `test_windows_storage.py`, `test_xml_engine_comparison.py`,
`test_xml_engine_backend.py`, `test_xml_control_plane_migration.py`,
`test_control_plane_migration.py`, `test_control_plane_convergence.py`,
`test_control_plane_6g_validation.py`, `test_control_plane_6h_switch.py`,
`e2e/test_concurrency_robustness_e2e.py`, `e2e/test_rest_xml_sqlite_e2e.py`.

## 4. Fichiers conservés et justification

- `app/xml_engine/` : `document.py` (parse/serialize), `storage.py` (verrous +
  écriture atomique, épuré), `service.py` (facade XML), `xml_native.py` (moteur).
- `app/xml_control/` : `store.py`, `records.py`, `service.py` (+ `bootstrap()`).
- `app/control_plane/` : `base.py` (XML unique), `xml_backend.py`, `views.py`,
  `volatile.py` (tokens révoqués mémoire).
- `app/data_plane/` : `xml_backend.py` (`XmlDataPlane`), `xml_services.py`.
- `app/converters/` : transformations SQL↔XML **sans SQLite** (export/import SQL
  désormais calculés depuis XML).
- `app/tcp/` : protocole + serveur (port 3307 inchangé), sans SQLite.

## 5. Dépendances supprimées (requirements.txt)

`SQLAlchemy`, `Flask-SQLAlchemy`, `mysql-connector-python` — **retirés**.
Restent : Flask, Flask-JWT-Extended, Flask-Bcrypt, Flask-CORS, Flask-SocketIO,
python-dotenv, lxml, marshmallow, eventlet, pytest, pytest-cov.

## 6. Architecture finale

```
                 ┌──────────────┐
                 │   Frontend   │
                 └──────┬───────┘
                        │ REST
                 ┌──────▼───────────────┐
                 │  Services XMLForge   │
                 └──────┬───────────────┘
           ┌────────────┴────────────┐
   CONTROL PLANE (XML)        DATA PLANE (XML)
   security.xml · catalog.xml   <id>_<slug>.xml
   history.xml · audit/YYYY-MM  (tables/colonnes/lignes)
           │                        │
           └──────────┬─────────────┘
                      │
              XML Native Engine
                      │
               XML Storage (atomic write / locks / version / checksum)
                      │
                  fichiers XML

TCP 3307 ─────────────┘  (mêmes services, mêmes permissions)
```

## 7. Tests

| | |
|---|---|
| tests avant | 420 |
| tests après | **322** |
| tests ajoutés | `test_xmlforge_without_sqlite_final.py` (5), bootstrap (2), COMMON collectif (1), résolution TCP (adaptés) |
| tests supprimés | ~94 (implémentation SQLite : projection, runtime, compare, migration, backup, ORM) |
| tests réécrits | conftest (bootstrap XML), auth_permissions, xml_backend_mode, xml_engine_final, data_plane_6i, e2e conftest + tcp |

La diminution est **entièrement expliquée** par la suppression des tests
d'implémentation SQLite ; les **comportements métier** (auth, permissions,
CRUD, DDL, contraintes, index, schéma, TCP, audit/history, concurrence,
corruption, rollback, persistance) restent couverts par des tests XML.

## 8. Preuve SQLite

`tests/test_xmlforge_without_sqlite_final.py` démarre dans un répertoire vierge,
exécute bootstrap + admin + bases + tables + colonnes + index + CRUD + DDL +
contraintes + permissions + TCP + redémarrage, puis **échoue si un seul fichier
`.db`/`.sqlite`/`.sqlite3` apparaît** (assertion). Vérifié : aucun fichier créé.

## 9. Preuve SQLAlchemy

`python -c "import app; import app.control_plane.xml_backend; …"` ne charge
**aucun** module `sqlalchemy`/`flask_sqlalchemy`/`app.models`/`app.extensions`
(testé en sous-processus). Aucun `import sqlite3`/`sqlalchemy`/`mysql` ne subsiste
dans `app/` (grep exhaustif).

## 10. REST

Register/login/me/logout, bases (CRUD, PERSONAL/COMMON, common_permission),
tables/colonnes/lignes, `/query` (moteur XML), `/schema`, permissions, history,
audit, TCP credentials, export/import XML+SQL, convertisseurs — fonctionnels
sans SQLite.

## 11. TCP 3307

Protocole inchangé ; AUTH/SELECT/INSERT/UPDATE/DELETE/DDL/index via le moteur
XML ; mêmes règles de permission que REST (unique `PermissionService`).

## 12–14. Persistence / Concurrency / Security

Redémarrage XML-only vérifié (données relues, IDs stables, `next_object_id`
persistant, AUTO_INCREMENT non réutilisé). 8 écritures concurrentes sans perte.
bcrypt, JWT (`token_version`), ACL, XSD, checksum, `expected_version`, locks,
atomicité, audit/history conservés. Répertoire `control/` en 0700, fichiers 0600.

## 15. Corruption / rollback

Fail-closed : `security.xml`/`catalog.xml`/`history.xml` manquants ou corrompus →
démarrage refusé (validation XSD). Rollback par snapshots XML (indépendant de
SQLite).

## 16. Limitations restantes

1. **Write amplification XML** : chaque mutation réécrit le document complet
   (~520 ms à 200 lignes, mesuré en 6I) — documenté, non optimisé (pas de cache
   global introduit).
2. `resolve_table` par id global scanne les documents (O(bases)) — acceptable,
   documenté.
3. `creator_id`/`created_at` des **lignes** ne sont pas persistés (le document
   Data Plane ne les portait pas historiquement) — les tables/colonnes, elles,
   les portent désormais.
4. Le frontend affiche encore un libellé obsolète sur COMMON (non modifié, hors
   périmètre backend).

## 17. Conclusion

SQLite, SQLAlchemy, Flask-SQLAlchemy, la projection SQLite, les modèles ORM,
`schema_migrations`, le backend compare et l'exporteur SQLite→XML ont été
**retirés du projet**. XML est l'unique source de vérité du Control Plane **et**
du Data Plane ; REST, TCP 3307 et le frontend continuent de fonctionner ; une
installation vierge démarre sans SQLite ; 322/322 tests passent.

PHASE_6J_XML_ONLY_COMPLETE
