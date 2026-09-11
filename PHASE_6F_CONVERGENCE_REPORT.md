# PHASE 6F — Convergence SQLite ↔ XML du Control Plane

**Date** : 2026-09-06

---

## 1. Résumé

Normalisation du modèle fonctionnel du Control Plane entre SQLite et XML :

- ajout de la colonne `common_permission` au modèle SQLAlchemy `Database` (migration V7 idempotente, **NULL conservé tel quel**) ;
- résolution des permissions **commune** (branche COMMON effective dans `PermissionService`, via `effective_common_permission`) ;
- interdiction des **grants individuels sur les bases COMMON** (PermissionService + service XML + intégrité) ;
- correction d'un **bug préexistant** : `XmlEngineService.mutate/ensure_storage` écrasaient silencieusement le `scope` modifié par un mutateur (le changement de scope REST ne fonctionnait donc pas) ;
- comparaison `common_permission` désormais effective dans le backend compare, avec statut structuré sur les divergences.

SQLite reste conservé, autoritaire en mode compare, et `CONTROL_BACKEND=sqlite` reste le défaut.

## 2. Divergences trouvées

| Divergence | Constat | Résolution |
|---|---|---|
| `common_permission` absent du modèle SQLite | colonne manquante côté SQLAlchemy | ajoutée (V7), NULL conservé |
| résolution d'accès : COMMON ignorée par `PermissionService` | le niveau collectif n'était appliqué que dans la primitive XML | branche COMMON branchée dans `PermissionService` (logique unique) |
| `scope` non modifiable via REST | `mutate`/`ensure_storage` forçaient `document["scope"] = database.scope` | corrigé : le document conserve le scope, l'ORM est resynchronisé |
| `table_permission.database_id` | absent du modèle ORM, dénormalisé côté XML | décision : **calculé** côté XML (BACKEND_SPECIFIC) |
| `tables_count` | relation ORM vs comptage Data Plane | **calculé/backend-spécifique** (exclu du compare) |
| `common_permission` exclu du compare | car colonne absente côté SQLite | désormais **comparé** |

## 3. Modifications effectuées

1. `app/models/database.py` — colonne `common_permission` (String(20), nullable).
2. `app/schema_migrations.py` — refactor en liste `MIGRATIONS` (V5, V7), ajout V7 `_add_column("databases", "common_permission", "VARCHAR(20)")`, idempotent, **aucune donnée modifiée**.
3. `app/control_plane/base.py` — `effective_common_permission(database)` (stocké vs effectif : le défaut `COMMON_PERMISSION_DEFAULT` n'est appliqué qu'à la résolution).
4. `app/services/permission_service.py` — branche COMMON dans `database_access`/`can_database` ; refus des grants individuels sur COMMON (`grant_database`, `grant_table`).
5. `app/services/database_service.py` — `create`/`update` acceptent `common_permission` (normalisation, PERSONAL+cp refusé, purge automatique quand scope passe PERSONAL).
6. `app/utils/validators.py`, `app/routes/databases.py` — champ REST `common_permission` (create/update) + code 400 pour les `ValueError`.
7. `app/xml_control/service.py` — `_validate_database_permission` et `validate_integrity` rejettent les `database_permission` sur base COMMON.
8. `app/xml_engine/service.py` — **correctif** : le `scope` n'est plus écrasé par la ligne ORM (mutate/ensure_storage).
9. `app/control_plane/compare_backend.py` — `common_permission` dans `_norm_database` ; différences enrichies d'un `status`.

## 4. Modification common_permission

- `nullable=True` ; valeurs autorisées `VIEW|EDIT|MANAGE|NULL`.
- Les anciennes bases COMMON restent `NULL` en base (aucune invention rétroactive) ; `COMMON_PERMISSION_DEFAULT=VIEW` n'est appliqué qu'au moment de la résolution effective.
- `PERSONAL` : `common_permission` toujours `NULL` (rejeté sinon, purgé au passage en PERSONAL).

## 5. Migration SQLite

- Utilisation du mécanisme existant (`schema_migrations.py`, pas d'Alembic).
- V7 idempotente : `ALTER TABLE databases ADD COLUMN common_permission VARCHAR(20)` si absente.
- Vérifiée sur : base vide (create_all fournit la colonne), base avec bases PERSONAL, bases COMMON sans/avec permission — aucune donnée modifiée.

## 6. Alignement XML

- `DatabaseRecord.common_permission` : sérialisé **absent** si NULL (jamais `"VIEW"` par défaut) ; enum `CommonPermission` sinon. Déjà conforme (6B/6D.1), vérifié par les tests de convergence.
- `XmlControlPlane`/`SQLiteControlPlane` exposent tous deux `common_permission` (colonne vs record) — comparables.

## 7. Permission resolution

Une **seule** logique branchée : `PermissionService.database_access`/`can_database` (utilisée par REST et TCP), ordre :

1. utilisateur inexistant/inactif → NONE ;
2. ADMIN → MANAGE (role) ;
3. owner → MANAGE (owner) ;
4. **COMMON → niveau collectif effectif** (`common_permission` ou défaut) ;
5. PERSONAL → grants individuels ;
6. DELETE → `can_admin`.

`XmlControlPlaneService.resolve_database_access` reste une primitive de vérification (non branchée), désormais **équivalente** (testée scénario par scénario).

## 8. Compare backend

- `common_permission` comparé (plus d'exclusion).
- Divergences enrichies : `{field, sqlite, xml, status}` avec `status=DIFFERENT` ; les exclusions restantes sont documentées (`tables_count`, `table_permission.database_id` → BACKEND_SPECIFIC).
- Double-write conservée : SQLite autoritaire → XML shadow (même `internal_id`) → comparaison ; échec XML → rollback + signalement ; échec SQLite → XML jamais appliqué silencieusement.

## 9. Tests

- **Nouveaux** : `tests/test_control_plane_convergence.py` (10 tests) — users/rôles/credentials/bases (PERSONAL, COMMON NULL/VIEW/EDIT/MANAGE)/permissions/history/audit équivalents, résolution d'accès (admin/owner/actif/inactif/absent/COMMON), pas de grants individuels sur COMMON, `internal_id` stable, backend XML sans SQLAlchemy ni Flask.
- **Adaptés (pas supprimés)** : `test_xml_engine_comparison.py::test_common_collective_access` (l'ancien `test_common_requires_share` encodait la sémantique obsolète) ; `tests/e2e/test_tcp_security_permissions_e2e.py` (base COMMON+EDIT collective, grant individuel refusé, changement de scope retire l'accès).

## 10. Résultats SQLite/XML/Compare

- Suite complète : **379 passés, 0 échoué** (369 précédents + 10 convergence).
- Les deux backends produisent les mêmes résultats fonctionnels (tests de convergence) ; le compare ne masque plus de divergence réelle.

## 11. Performances (ms, 150 itérations ; min/max/moy/médiane)

| Opération | SQLite | XML |
|---|---|---|
| get_user_by_email | 0.216 / 0.626 / 0.315 / 0.285 | 0.956 / 1.383 / 1.017 / 1.008 |
| get_user | 0.181 / 0.58 / 0.208 / 0.199 | 0.967 / 1.499 / 1.005 / 0.991 |
| list_users (20) | 0.334 / 3.027 / 0.407 / 0.377 | 8.623 / 12.702 / 9.948 / 10.169 |
| list_roles | 0.097 / 0.678 / 0.116 / 0.103 | 0.383 / 0.628 / 0.424 / 0.416 |
| get_database | 0.115 / 1.099 / 0.14 / 0.12 | 0.902 / 1.646 / 1.001 / 0.99 |
| list_database_permissions | 0.084 / 0.915 / 0.101 / 0.088 | 0.051 / 0.194 / 0.061 / 0.055 |
| resolve_database_access | 0.333 / 0.969 / 0.394 / 0.381 | 1.384 / 2.255 / 1.585 / 1.598 |
| compare.get_user | — | 1.485 / 1.924 / 1.607 / 1.604 |

Le backend XML relit et valide le fichier à chaque appel (cohérence prioritaire) : coût visible sur les listes ; optimisation différée (pas de cache introduit en 6F).

## 12. Régressions éventuelles

Aucune. Deux tests historiques ont été adaptés à la décision produit COMMON (documenté en §9) ; un bug de changement de scope a été corrigé (comportement attendu restauré).

## 13. Fichiers créés

- `tests/test_control_plane_convergence.py`

## 14. Fichiers modifiés

- `app/models/database.py`, `app/schema_migrations.py`
- `app/control_plane/base.py`, `__init__.py`, `compare_backend.py`
- `app/services/permission_service.py`, `database_service.py`
- `app/utils/validators.py`, `app/routes/databases.py`
- `app/xml_control/service.py`
- `app/xml_engine/service.py` (correctif scope)
- `tests/test_xml_engine_comparison.py`, `tests/e2e/helpers.py`, `tests/e2e/test_tcp_security_permissions_e2e.py`

## 15. Limitations restantes

1. `tables_count` reste backend-spécifique (relation ORM vs comptage Data Plane) — exclu du compare, documenté.
2. `table_permission.database_id` est calculé côté XML uniquement (colonne absente du modèle ORM) — exclu du compare, documenté.
3. Le frontend affiche encore un libellé obsolète (« COMMON = simple filtre ») — **non modifié** (hors périmètre 6F), à corriger dans une phase frontend.
4. Les bases COMMON historiques qui posséderaient déjà des grants individuels (SQLite) restent lisibles ; `validate_integrity` les signale comme incohérence (aucune purge automatique).

## 16. Risques

- La séquence de changement de scope COMMON→PERSONAL purge `common_permission` : comportement voulu, à surveiller côté frontend.
- `list_users` XML ≈ 10 ms (validation à chaque lecture) : acceptable, à optimiser plus tard.

## 17. Recommandation pour 6G

**PHASE_6F_READY_FOR_6G**

`common_permission` existe dans SQLite et XML (NULL conservé), `COMMON_PERMISSION_DEFAULT` appliqué en résolution seule, PERSONAL sans niveau collectif, COMMON lisible par tout utilisateur actif (VIEW/EDIT/MANAGE), grants individuels COMMON interdits, permissions effectives identiques entre SQLite et XML (testées), compare sans masquage, `internal_id`/UUID stables, auth/TCP/history/audit fonctionnels dans les deux backends, `expected_version`/`checksum`/`rollback` opérationnels, XML indépendant de SQLAlchemy, 379/379 tests verts, aucune suppression destructive.
