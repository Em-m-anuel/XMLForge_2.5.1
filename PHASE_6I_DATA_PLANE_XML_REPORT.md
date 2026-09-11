# PHASE 6I — Data Plane XML sans SQLite

**Date** : 2026-09-08

---

## 1. Résumé

Le **Data Plane** fonctionne désormais **sans SQLite dans son chemin d'exécution
normal** : en `DATA_BACKEND=xml` (+ `CONTROL_BACKEND=xml`, `QUERY_BACKEND=xml`,
`SYNC_SQLITE_PROJECTION=false`), **SQLAlchemy n'est pas initialisé**, le fichier
`xmlforge.db` est **absent**, et l'application démarre et exécute REST + TCP :
auth, bases, tables, colonnes, lignes, DDL, contraintes, index, schéma,
permissions, history, audit, redémarrage, concurrence — le tout via
`XmlNativeEngine` + fichiers XML + écriture atomique.

SQLite reste conservé comme fallback/référence (défaut `DATA_BACKEND=sqlite`).

## 2. Architecture avant 6I

```
Application → Data Plane → SQLAlchemy (Database/Table/Column/TableRow) → SQLite + projection
```

## 3. Architecture après 6I

```
Application → Data Plane
   ├── DATA_BACKEND=sqlite (défaut) : pont ORM + projection (historique)
   └── DATA_BACKEND=xml             : XmlDataPlane (catalogue CP + documents XML + XmlNativeEngine)
```

## 4. Audit des dépendances SQLite

Cartographie complète : `PHASE_6I_DATA_PLANE_AUDIT.md`. Points découplés :
`XmlEngineService` (pont ORM), `DatabaseService`/`TableService`/`ColumnService`/
`RowService`/`SchemaService`/`UnlockService`/`PermissionService` (résolution
ORM), `QueryService`/`XmlQueryService` (résolution + projection), `tcp_server`,
`auth/decorators`, `create_app` (db.init_app/migrations), JWT loader/logout
(RevokedToken).

## 5. Modifications effectuées

- `app/config.py` : `DATA_BACKEND` (sqlite|xml) + validation ; `.env.example`.
- `app/data_plane/` (nouveau) : `__init__.py` (resolver), `xml_backend.py`
  (`XmlDataPlane`), `xml_services.py` (CRUD/DDL XML), audit carto.
- `app/xml_control/service.py` : `allocate_object_id()` (compteur global sous
  verrou dans `catalog.xml`), `add_audit` sérialisé sous verrou (plus de perte
  en concurrence), lecture d'audit `.gz`.
- `app/xml_control/records.py` : `CatalogDocument.next_object_id`.
- `app/static/control/catalog.xsd` : attribut `next_object_id`.
- `app/control_plane/views.py` : `TableView`, `ColumnView` ; `volatile.py`
  (tokens révoqués mémoire).
- `app/xml_engine/service.py` : `mutate`/`read_document` branchent sur le mode
  XML (aucun `_sync_catalog`, aucune projection).
- Services : `database_service`, `table_service`, `column_service`,
  `row_service`, `schema_service`, `unlock_service` (mémoire en XML),
  `permission_service` (résolution table), `query/service` (garde), `xml_query_service`
  (résolution + internal_id), `auth_service`/`user_service` (unlocks via service).
- `app/tcp/tcp_server.py`, `app/auth/decorators.py`, `app/routes/auth.py`
  (logout volatil), `app/__init__.py` (SQLAlchemy gated, JWT loader volatil).
- `app/__init__.py`/`app/services/__init__.py`/`app/xml_engine/__init__.py`
  déjà légers (6H) — conservés.

## 6. Nouvelles abstractions

- `XmlDataPlane` : résolution base (catalogue CP), document IO (read/mutate/
  write_new/delete_storage), allocation d'id globale, tables/colonnes/schéma,
  exécution d'AST SQL.
- `resolver` : `uses_sqlite()`, `get_data_plane()`, `resolve_table`,
  `get_table`, `list_tables`.

## 7–15. Fonctionnement Data Plane XML / REST / TCP / permissions / CRUD / DDL / contraintes / index

Validé par `tests/test_data_plane_6i.py` (6 tests) : application complète sans
SQLite (auth → bases PERSONAL/COMMON → table → colonnes → index → INSERT/SELECT/
UPDATE/DELETE → UNIQUE violé refusé → rows REST → schéma → history → permissions
COMMON collectives), redémarrage, contraintes FK, concurrence (8 threads), TCP
réel, schéma sans SQLAlchemy.

## 16–19. Persistance / corruption / checksum / expected_version

Redémarrage XML-only : données persistées, `internal_id` stables. Corruption :
fail-closed au démarrage (validation XSD security/catalog/history). Checksum
SHA-256 ; `expected_version` → `ConflictError`.

## 20. Concurrence

8 écritures concurrentes (INSERT) en XML pur : sérialisées, aucune perte
(correctif : `add_audit` + allocation d'id sous verrou), comptage exact.

## 21. Tests sans SQLite

- `tests/test_data_plane_6i.py` (6) : SQLite **absent**, SQLAlchemy **non
  initialisé**, projection désactivée.
- Test ultime `test_full_application_without_sqlite` (création utilisateur,
  login, bases, table, colonnes, index, INSERT/SELECT/UPDATE/DELETE,
  contraintes, permissions, history/audit, intégrité XML).

## 22. Comparaison SQLite/XML

Aucune divergence fonctionnelle inexpliquée (suite compare 6G verte). Différences
acceptées (BACKEND_SPECIFIC) : `tables_count`, `table_permission.database_id`.

## 23. Performances (ms, 15 itérations, 200 lignes ; min/max/moy/médiane/P95)

| Opération | SQLite | XML |
|---|---|---|
| SELECT * LIMIT 10 | 5.53/6.59/5.71/5.62/5.76 | 5.50/6.13/5.59/5.55/5.65 |
| SELECT WHERE | 5.60/5.83/5.68/5.65/5.82 | 5.65/5.91/5.74/5.74/5.84 |
| COUNT(*) | 5.47/5.80/5.59/5.56/5.70 | 5.40/5.77/5.53/5.52/5.71 |
| INSERT | 447/565/479/453/560 | 526/558/538/532/556 |
| UPDATE | 450/538/513/523/536 | 446/554/519/519/537 |

Les lectures sont équivalentes (dominées par HTTP). Les écritures réécrivent le
document XML complet (~530 ms à 200 lignes) : **write amplification documentée**,
à optimiser plus tard (pas de cache introduit). SQLite reconstruit sa projection
(≈480 ms) ; XML ≈10 % plus lent en écriture à cette taille.

## 24. Dépendances SQLite restantes

| Occurrence | Classe |
|---|---|
| `app/control_plane/sqlite_backend.py`, `app/xml_control/exporter.py` | FALLBACK / MIGRATION |
| `app/query/sqlite_runtime.py`, `app/xml_engine/projection.py` | LEGACY / COMPARAISON |
| `app/services/export_service.py`, `import_service.py`, `sync_service.py`, `routes/exports.py`, `routes/sync.py` | LEGACY (export/import SQL, hors chemin XML normal) |
| `app/xml_engine/service.py` (chemin sqlite), `app/query/service.py` (chemin sqlite) | FALLBACK (DATA_BACKEND=sqlite) |
| `app/models/`, `app/schema_migrations.py`, `app/__init__.py` (chemin sqlite) | FALLBACK / MIGRATION |
| `app/query/comparator.py` | COMPARAISON |

Aucune de ces occurrences n'est sollicitée dans le chemin **REST XML / TCP XML /
Data Plane XML** (`DATA_BACKEND=xml`) — vérifié par le test « SQLite absent ».

## 25. Limitations

1. **Write amplification XML** : chaque mutation réécrit le document complet
   (documenté, optimisation différée — pas de cache complexe en 6I).
2. `internal_id` des nouvelles tables/colonnes/lignes alloués via compteur
   global `catalog.next_object_id` (amorcé au max des IDs Data Plane existants).
3. `creator_id`/`created_at` des tables/colonnes (données ORM historiques) sont
   NULL en mode XML (non stockés dans le document) — affichage frontend partiel.
4. Export/import SQL (legacy) restent SQLite : hors chemin XML normal.

## 26. Risques

- Le `resolve_table` par id global en mode XML scanne les documents de toutes
  les bases (coût O(bases) — acceptable, à optimiser).
- Écriture document complet = risque de latence sur gros volumes.

## 27. Rollback

`DATA_BACKEND=sqlite` (défaut) restaure immédiatement le comportement
historique ; les fichiers XML ne sont jamais modifiés par le mode sqlite. Aucune
suppression destructive.

## 28. Recommandation pour Phase 6J

**PHASE_6I_READY_FOR_6J**

Preuves : 415/415 tests verts ; `test_full_application_without_sqlite` démontre
le Data Plane XML complet (CRUD/DDL/contraintes/index/schéma/permissions/TCP/
persistance/concurrence) **sans `xmlforge.db` ni projection** ; aucune
divergence fonctionnelle inexpliquée ; SQLite conservé (fallback/référence) ;
aucun mécanisme de sécurité désactivé ; aucune suppression destructive.
