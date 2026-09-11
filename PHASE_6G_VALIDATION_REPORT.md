# PHASE 6G — Validation prolongée du Control Plane SQLite ↔ XML

**Date** : 2026-09-07

---

## 1. Résumé

Validation prolongée et réaliste du Control Plane : chaque opération est
exécutée en mode **compare** (SQLite autoritaire + XML shadow) puis l'équivalence
fonctionnelle SQLite/XML est vérifiée. La phase a détecté **1 vraie divergence
fonctionnelle** (`document_version` du miroir `catalog.xml` figé) et **1 bug
d'implémentation du compare** (gestion des résultats de type liste), tous deux
**corrigés** avec tests de régression. À l'issue : **0 divergence fonctionnelle
non expliquée**, 399/399 tests verts.

## 2. Environnement de test

- `CONTROL_BACKEND=compare` (mode principal), `sqlite` et `xml` pour les tests
  ciblés.
- App Flask + SQLite fichier + `data/control/` réels (pas de mocks).
- Suite : `tests/test_control_plane_6g_validation.py` (20 tests).

## 3. Architecture testée

```
Opération (REST/TCP/service)
    → CompareControlPlane
        → SQLiteControlPlane (autoritaire)
        → XmlControlPlane (shadow, même internal_id)
        → comparaison structurée (_diff, _diff_list)
        → divergence enregistrée + loggée (jamais masquée)
```

## 4. Tests CRUD

- users (create/get/get_by_email/list/update/delete) ; rôles (create/list) ;
  bases (create/get/list/update/delete) ; grants base/table (grant/revoke/list) ;
  credentials TCP (create/get/update/delete) ; history (add/list/filter) ;
  audit (add/list/filter). Après chaque opération : `assert_equivalent`
  (SQLite == XML sur les 8 familles d'entités) + `functional_divergences() == []`.

## 5. Tests Auth

- Login correct / mauvais mot de passe / utilisateur inexistant / inactif /
  ADMIN / USER — identiques en SQLite et XML.
- `token_version` : incrément invalide les anciens JWT (mécanisme existant
  inchangé).

## 6. Tests permissions

- `permission_level` NONE/VIEW/EDIT/MANAGE vérifié sur les booléens
  (VIEW=read, EDIT=read+write, MANAGE=tout, DELETE→can_admin).
- SELECT/INSERT/UPDATE/DELETE/DDL via le moteur de requêtes selon le niveau.

## 7. Tests COMMON

- Matrice `COMMON × {NULL, VIEW, EDIT, MANAGE}` × {admin, propriétaire autre
  base, user normal, inactif, inexistant} : `COMMON+NULL → COMMON_PERMISSION_DEFAULT
  (VIEW)` ; niveaux explicites respectés ; inactif/inexistant → NONE.
- Aucun grant individuel nécessaire ; grant individuel sur COMMON → refusé
  (400/403) côté service, et rejeté côté XML (`_validate_database_permission`,
  `validate_integrity`).

## 8. Tests PERSONAL

- Propriétaires A/B : A → MANAGE sur sa base, B → NONE ; puis grants successifs
  VIEW → EDIT → MANAGE ; les deux backends donnent exactement le même résultat
  (`PermissionService.database_access` == `XmlControlPlaneService.resolve_database_access`).

## 9. Tests REST

- login/me, users (admin), création base/table/colonne, requêtes SQL
  (INSERT/SELECT), audit-logs, history : 200 et équivalence post-appel.

## 10. Tests TCP

- Vrai serveur TCP (port éphémère de test ; **le port de production reste
  3307** inchangé) : authentification, SELECT/INSERT/UPDATE/DELETE, accès
  COMMON EDIT collectif, mauvais mot de passe → `ConnectionError`. Équivalence
  post-opération.

## 11. Tests persistence

- Écriture → arrêt → redémarrage (même DB + même dossier control) → lecture :
  users/roles/bases/permissions/credentials/history/audit persistés ;
  `internal_id` stable ; équivalence préservée.

## 12. Tests restart

- Cycle start→write→stop→start→read vérifié ; après chaque cycle SQLite == XML.

## 13. Tests corruption

- Fichier CP manquant → démarrage xml/compare **refusé** (`RuntimeError`,
  fail-closed, pas de régénération).
- Fichier corrompu (XML mal formé) → démarrage xml **refusé** (validation XSD
  au démarrage ajoutée en 6G).
- Aucune recréation silencieuse d'un Control Plane vide/corrompu.

## 14. Tests rollback

- `expected_version` incorrect → `ConflictError`, aucune écriture ; version
  correcte → mutation acceptée et version incrémentée.

## 15. Tests concurrence

- 6 écritures concurrentes (register) en mode compare : sérialisées par les
  verrous, aucune perte, équivalence préservée, aucune divergence fonctionnelle.

## 16. Tests resilience

- `read`/`read_validated`/`mutate` sur fichier absent → `StorageError` ;
  XML mal formé → `XmlValidationError` ; XSD invalide → `XmlValidationError` ;
  jamais de fallback SQLite silencieux dans `XmlControlPlane`.

## 17. Tests identifiants

- `internal_id` et UUID stables : deux exports successifs produisent des octets
  identiques (UUIDv5 déterministe, IDs conservés).

## 18. Tests History/Audit

- Séquence réaliste (create/update/grant/revoke/credentials) puis
  `History SQLite == XML` et `Audit SQLite == XML` (filtres compris) ;
  rotation `audit-YYYY-MM.xml` vérifiée.

## 19. Tests longue séquence

- 40 users, 12 bases (6 PERSONAL + 6 COMMON aux niveaux variés), 9 grants
  PERSONAL, 9 credentials TCP, 19 mises à jour, 10 suppressions ; équivalence
  complète et **0 divergence fonctionnelle**.

## 20. Tests Data Plane

- Les mutations Data Plane (création table/colonne/ligne) déclenchent désormais
  le **rafraîchissement du miroir `catalog.xml`** (`document_version`,
  `xml_checksum`, `sync_status`) — vérifié par le test REST (insert/select) sans
  divergence. Le Control Plane ne copie toujours aucune table/colonne/ligne.

## 21. Divergences détectées

| # | Divergence | Type | Détail | Résolution |
|---|---|---|---|---|
| 1 | `document_version` (catalog.xml) | **fonctionnelle** | SQLite=N, XML=1 après mutations Data Plane (miroir non rafraîchi) | corrigé : `XmlEngineService._mirror_catalog` (upsert) après chaque mutation Data Plane |
| 2 | `list_users`/`list_audit` en compare | **bug compare** | `_read` normalisait la liste entière → `'list' object has no attribute 'id'` | corrigé : traitement liste vs objet séparé (`_diff_list`, `_safe_norm`) |
| 3 | démarrage xml sur CP corrompu | **robustesse** | l'existence seule était vérifiée | corrigé : validation XSD des fichiers CP au démarrage (fail-closed) |

Divergences **légitimes** (BACKEND_SPECIFIC, documentées, non masquées) :
`tables_count` (relation ORM vs comptage Data Plane) et
`table_permission.database_id` (dénormalisé côté XML). Aucune nouvelle
exclusion n'a été ajoutée.

**Total divergences fonctionnelles restantes : 0.**

## 22. Corrections effectuées

- `app/xml_engine/service.py` : `_mirror_catalog(database)` appelé après
  `ensure_storage` et `mutate` (mode xml/compare uniquement, upsert, best-effort
  avec signalement).
- `app/control_plane/compare_backend.py` : `_read` (list vs objet) + `_safe_norm`.
- `app/__init__.py` : validation XSD de `security.xml`/`catalog.xml` au démarrage
  en mode xml/compare.
- `tests/test_control_plane_6g_validation.py` (créé).

## 23. Performance (200 itérations, 40 users ; ms : min/max/moy/médiane/P95)

| Opération | SQLite | XML | Compare |
|---|---|---|---|
| get_user_by_email | .282/.863/.334/.327/.381 | 2.43/4.85/2.59/2.53/2.86 | 3.01/7.44/3.31/3.17/3.71 |
| get_user | .232/3.3/.297/.277/.337 | 2.43/5.04/2.55/2.52/2.68 | 2.90/5.01/3.07/3.05/3.17 |
| list_users | .666/3.6/.744/.721/.805 | 51.3/114.9/53.4/52.0/58.6 | 52.9/93.2/54.2/53.6/55.5 |
| list_roles | .149/.692/.170/.156/.216 | 1.21/2.07/1.30/1.27/1.43 | 1.53/3.49/1.65/1.61/1.87 |
| get_database | .157/1.27/.183/.169/.215 | .047/.239/.053/.049/.078 | .286/.452/.328/.322/.379 |
| list_database_permissions | .113/.815/.129/.118/.165 | .045/.221/.052/.048/.083 | .215/.398/.243/.234/.287 |
| resolve_database_access | .432/.893/.493/.486/.557 | 1.27/1.76/1.33/1.32/1.39 | — |

Le backend XML relit et valide le fichier à chaque appel (cohérence
prioritaire) : coût linéaire visible sur `list_users` (53 ms pour 40 users).
**Documenté, non optimisé** (pas de cache introduit en 6G).

## 24. Régressions

Aucune. **399/399 tests passés** (379 précédents + 20 nouveaux 6G).

## 25. Limitations

1. `list_users` XML ≈ 50 ms à 40 utilisateurs (validation à chaque lecture) ;
   optimisation différée.
2. `tables_count` et `table_permission.database_id` restent backend-spécifiques.
3. `resolve_database_access` (primitive XML) n'est pas encore branchée dans
   `PermissionService` (qui porte la logique unique) — équivalence testée.
4. La purge/compression/rotation de l'audit (rétention `AUDIT_RETENTION_MONTHS`)
   reste à implémenter (6H).

## 26. Risques

- Le rafraîchissement du miroir `catalog.xml` sur chaque mutation Data Plane
  ajoute une écriture par mutation (coût faible, mesuré indirectement) ; à
  surveiller sur gros volumes.
- Mono-processus confirmé : les verrous par fichier suffisent (multi-instance
  hors périmètre).

## 27. Recommandation pour 6H

**PHASE_6G_READY_FOR_6H**

Preuves : 399/399 tests verts ; CRUD/auth/permissions/COMMON/PERSONAL/REST/TCP/
persistance/restart/corruption/rollback/concurrence/identifiants/history/audit/
longue séquence validés ; **0 divergence fonctionnelle non expliquée** ; les
divergences restantes sont documentées BACKEND_SPECIFIC ; aucune nouvelle
exclusion de comparaison ; aucun mécanisme de sécurité (XSD, checksum,
expected_version, locks) désactivé ; SQLite toujours présent et défaut.
