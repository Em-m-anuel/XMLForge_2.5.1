# XMLForge — Phase 4 — Rapport final (bascule XML + audit SQLite)

État au 2026-09-05. Objectif : vérifier que XMLForge fonctionne réellement avec
**XML comme moteur principal** (`QUERY_BACKEND=xml`), et identifier précisément
ce qui dépend encore de SQLite. **SQLite n'est PAS supprimé** dans cette phase.

---

## 1. État initial

- 177 tests réussis ; moteur XML complet (étapes 1-13) mais **SQLite configuré
  comme backend par défaut**.
- Point bloquant identifié : `XmlEngineService.mutate()` et `ensure_storage()`
  reconstruisaient **toujours** la projection SQLite, même en mode XML ; les
  lectures `engine=xml` (SELECT) étaient déjà XML-only, mais les **écritures**
  dépendaient de SQLite.

## 2. État final

- `QUERY_BACKEND=xml` + `SYNC_SQLITE_PROJECTION=false` active un **mode XML
  pur** : SELECT/INSERT/UPDATE/DELETE/DDL/index/pagination/introspection
  s'exécutent **uniquement** sur le XML. SQLite de données n'est plus nécessaire.
- Aucun **fallback silencieux** : `engine=sqlite` sans projection échoue
  explicitement (`SQLITE_PROJECTION_ERROR`) ; une erreur XML n'est jamais
  rejouée sur SQLite.
- Observabilité : chaque requête journalise son moteur (`[QUERY] engine=…
  operation=… database=… table=…`).

## 3. Fichiers modifiés

| Fichier | Modification |
|---|---|
| `backend/app/config.py` | `QUERY_BACKEND` documenté (sqlite/xml/compare), nouveau `SYNC_SQLITE_PROJECTION` (true/false) |
| `backend/app/xml_engine/service.py` | `sync_projection_enabled()` ; `mutate()`/`ensure_storage()` écrivent le XML seul quand la projection est désactivée |
| `backend/app/query/service.py` | `QueryService.select/count/_execute_rendered_select` lèvent `ProjectionError` si projection absente (pas de reconstruction implicite) ; logs `[QUERY] engine=sqlite` |
| `backend/app/query/xml_query_service.py` | log `[QUERY] engine=xml` |
| `backend/app/services/row_service.py` | `_read_rows_from_xml()` : la façade lignes lit le XML quand la projection est absente |
| `backend/app/__init__.py` | `create-admin` défensif (re-crée le rôle admin s'il manque) |
| `backend/.env.example` | documente les 3 modes (SQLITE/XML/COMPARE) |
| `backend/XML_ENGINE.md`, `backend/XML_ENGINE_TESTING.md`, `backend/BACKEND_DOCUMENTATION.md` | mise à jour mode XML |

## 4. Fichiers créés

| Fichier | Rôle |
|---|---|
| `backend/tests/test_xml_backend_mode.py` | 11 tests du mode XML (backend, CRUD, DDL, index, pagination, introspection, permissions, façade lignes, conflit 409, TCP, coexistence compare) |
| `SQLITE_DEPENDENCIES.md` | audit classé des dépendances SQLite (CRITIQUE/TRANSITOIRE/COMPARAISON/LEGACY) |
| `XML_BACKEND_MODE.md` | documentation du mode backend XML (archi, config, REST, TCP, frontend, permissions, limitations) |

## 5. Dépendances SQLite supprimées / rendues optionnelles

- **Projection SQLite de données** : optionnelle (`SYNC_SQLITE_PROJECTION=false`) —
  plus construite ni lue en mode XML pur.
- **Lecture des lignes de la façade CRUD** : repli XML (`RowService`).
- **Reconstruction implicite** dans `QueryService.select` : remplacée par une
  erreur explicite (plus de reconstruction cachée).

## 6. Dépendances SQLite restantes (et critiques)

- **CRITIQUES (A)** — le **control plane SQLAlchemy** : utilisateurs, rôles,
  permissions (`PermissionService`), catalogue (Database/Table/Column/TableRow),
  audit, historique, déverrouillages, credentials TCP. **Ce sont elles qui
  bloquent la suppression totale de SQLite** (non migrées vers XML, hors
  périmètre de cette phase — voir `SQLITE_DEPENDENCIES.md`).
- **TRANSITOIRES (B)** — projection SQLite (optionnelle), `QueryService` chemin
  SQLite (legacy), `sqlite_runtime.py`, `projection.py` (conservés pour legacy).
- **COMPARAISON (C)** — comparateur, benchmarks, tests de projection/concurrence.
- **LEGACY (D)** — `sqlite_runtime.py` et chemin `engine=sqlite` (à supprimer
  après validation complète).

## 7. Fonctionnalités réellement XML-only (en mode XML pur)

SELECT (WHERE complet, agrégats, GROUP BY/HAVING, INNER JOIN, DISTINCT,
BETWEEN/NOT IN/NOT LIKE, ORDER BY, LIMIT/OFFSET), INSERT (simple/multi/
implicite), UPDATE, DELETE, CREATE/DROP/ALTER TABLE (ADD/MODIFY/DROP COLUMN,
RENAME), CREATE/DROP INDEX, CREATE DATABASE, PK/UNIQUE/NOT NULL/FK
(RESTRICT/CASCADE/SET NULL)/DEFAULT/AUTO_INCREMENT, pagination, introspection
`GET /api/databases/<id>/schema`, REST `engine=xml`, TCP `engine=xml`.

## 8. Fonctionnalités qui nécessitent encore SQLite

- `engine=sqlite` et `engine=compare` (projection SQLite) — par conception.
- Authentification, rôles, permissions, partage (control plane) — **inchangé**,
  mais ces métadonnées restent sur SQLAlchemy.

## 9. Résultats frontend

- Frontend **non modifié** (aucun changement visuel).
- Build ✓, 10 tests unitaires ✓, **Playwright e2e ✓ (20,3 s)** — registre →
  login → base COMMON → table → colonne → ligne → conflit 409 → settings TCP.
- La façade REST consommée par le frontend fonctionne en mode XML (tables,
  colonnes, **lignes lues depuis le XML**, mutations via le moteur XML).

## 10. Résultats REST

En mode XML pur (backend lancé avec `QUERY_BACKEND=xml SYNC_SQLITE_PROJECTION=false`) :

```
login / import base (860 lignes) / SELECT COUNT(=400, engine=xml)
SELECT BETWEEN+ORDER+LIMIT / INSERT / UPDATE / DELETE
CREATE TABLE / ALTER ADD/MODIFY COLUMN / CREATE INDEX / DROP INDEX / RENAME / DROP TABLE
GET /schema (5 tables)                → tous OK
engine=sqlite sans projection         → HTTP 500 SQLITE_PROJECTION_ERROR (explicite)
expected_version obsolète             → HTTP 409 SYNC_CONFLICT
```

## 11. Résultats TCP

En mode XML pur (SQLite de données indisponible) :

```
connect / SELECT COUNT / SELECT BETWEEN+NOT IN+NOT LIKE / INSERT+relecture /
UPDATE / DELETE / CREATE TABLE / ALTER / CREATE INDEX / DROP INDEX / RENAME /
DROP TABLE                            → tous OK
UPDATE sans WHERE                     → refusé (erreur structurée)
table inexistante                     → refusée (erreur structurée)
projection SQLite après TCP           → 0 fichier (aucun)
```

## 12. Résultats permissions

- OWNER : lecture + écriture autorisées.
- VIEW (partage) : lecture autorisée, INSERT refusé (403), même moteur XML.
- COMMON sans partage : invisible (inchangé).
- Introspection : autorisée en lecture, refusée sans partage (403).

## 13. Résultats CRUD / DDL

Tous les CRUD et DDL passent en mode XML pur, et les mutations sont **visibles
dans le fichier XML** (`version` incrémentée, aucune projection SQLite créée).

## 14. Test avec SQLite indisponible

**Réussi.** Backend lancé avec `QUERY_BACKEND=xml` + `SYNC_SQLITE_PROJECTION=false` :
démarrage OK, chargement des bases XML OK, login OK (control plane), CRUD/DDL/
index/pagination/introspection OK via REST et TCP, **0 fichier de projection
SQLite créé**, chemin SQLite échouant explicitement. SQLite de données n'a été
nécessaire à **aucune** opération XML.

## 15. Tests — avant / après

| | Avant Phase 4 | Après Phase 4 |
|---|---|---|
| Total | 177 | **188** |
| Réussis | 177 | **188** |
| Échoués | 0 | **0** |
| Ignorés | 0 (1 live-test frontend non compté ici) | 0 |
| Durée | ~7 min 48 s | ~14 min 34 s |

Aucune régression ; 11 tests nouveaux (`test_xml_backend_mode.py`).

## 16. Prochaines étapes

1. Migrer le **control plane** (auth, rôles, ACL, catalogue, audit, historique)
   vers XML si l'on veut supprimer totalement SQLite.
2. Basculer durablement `QUERY_BACKEND=xml` sur un environnement de test et
   valider les parcours UI de bout en bout (le frontend est déjà compatible).
3. Persister l'index XML sur disque (gros volumes).
4. Ajouter `LEFT JOIN` / sous-requêtes si besoin métier.
5. Supprimer la projection SQLite et `sqlite_runtime.py` **après** validation
   complète (phase ultérieure).

---

Rapport détaillé de l'implémentation moteur : `XML_ENGINE_IMPLEMENTATION_REPORT.md`.
