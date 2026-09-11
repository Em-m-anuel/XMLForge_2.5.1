# PHASE 6E — Migration progressive du Control Plane SQLite → XML

**Date** : 2026-09-06

---

## 1. Résumé

Mise en place de la **couche d'adaptation du Control Plane** (`app/control_plane/`)
avec trois backends interchangeables (`sqlite`, `xml`, `compare`), et migration
**progressive** des services métier (auth, users, rôles, permissions, bases,
credentials TCP, historique, audit) pour lire/écrire via cette couche.

- `CONTROL_BACKEND=sqlite` (défaut, inchangé) : comportement historique.
- `CONTROL_BACKEND=xml` : les services migrés lisent/écrivent le Control Plane
  XML (indépendant de SQLAlchemy).
- `CONTROL_BACKEND=compare` : SQLite + XML exécutés en parallèle, comparaison
  structurée, double-write contrôlée, divergence signalée.

SQLite reste présent, autoritaire en mode compare, et le mécanisme de retour
arrière (`CONTROL_BACKEND=sqlite`) est immédiat.

## 2. Architecture

```
               Services métier (auth/user/permission/database/tcp/history/audit)
                                  │
                        Control Plane Adapter
                                  │
             ┌────────────────────┼────────────────────┐
             │                    │                    │
        SQLiteControlPlane   XmlControlPlane    CompareControlPlane
             │                    │                    │
        SQLAlchemy           XmlControlPlane     SQLite ↔ XML
        (modèles ORM)          Service/records        │
                                  │           (comparaison + divergence)
                          security/catalog/history/audit/*.xml
```

Le **catalogue des tables/colonnes/lignes** (Data Plane) reste en SQLite
pendant la transition (pont consommé par `XmlEngineService`).

## 3. Services migrés

| Service | SQLite | XML | Compare | Écriture |
|---|---|---|---|---|
| Auth (login/register/get_user) | ✅ | ✅ | ✅ | users (insert/update) |
| User (list/get/create/update/delete/reset/toggle) | ✅ | ✅ | ✅ | users (insert/update/delete) |
| Role (reads + ensure_role) | ✅ | ✅ | ✅ | rôles (insert) |
| Permission (résolution + grants) | ✅ | ✅ | ✅ | database_permissions / table_permissions |
| Database (métadonnées CP) | ✅ | ✅ (miroir catalog.xml) | ✅ (miroir + compare) | ligne ORM « pont Data Plane » + miroir XML |
| TCP Credential | ✅ | ✅ | ✅ | tcp_credentials |
| History | ✅ | ✅ | ✅ | history |
| Audit | ✅ | ✅ | ✅ | audit mensuel |

**Non migrés (volontairement)** : `UnlockService` (unlocks = SQLite en 6E,
mémoire-only plus tard), `RevokedToken` (SQLite, non persisté en XML),
`schema_migrations` (inutilisé par le backend XML), catalogue
`tables/columns/table_rows` (pont Data Plane).

## 4. Stratégie de double-write

- **Lectures (compare)** : SQLite → résultat ; XML → résultat ; comparaison
  structurelle (`_diff`). Divergence → `record_divergence()` + log
  `CONTROL PLANE DIVERGENCE` (sans jamais exposer de secret). Le résultat
  **SQLite** est retourné (référence historique).
- **Écritures (compare)** : (1) validation côté service ; (2) écriture SQLite
  (autorisée) ; (3) écriture XML **shadow** avec le **même `internal_id`** que
  SQLite ; (4) comparaison de l'état résultant. Si SQLite échoue → l'exception
  remonte (XML n'est **jamais** appliqué silencieusement). Si XML échoue →
  **rollback XML** (snapshot) + signalement, résultat SQLite retourné. Si
  divergence → signalement explicite.
- **Écritures (xml)** : XML seul, fail-closed (échec = erreur).
- Les mots de passe restent des **hashes bcrypt** ; jamais de clair, jamais de
  hash dans les logs.

## 5. Divergences

Divergences **connues et documentées** entre SQLite et XML (aucune masquée) :

| Opération | SQLite | XML | Cause | Décision |
|---|---|---|---|---|
| `delete_user` avec références | `IntegrityError` (nullify sur FK NOT NULL) | `ControlPlaneIntegrityError` (RESTRICT) | mécanismes différents | **les deux refusent** ; textes d'erreur différents, documenté (pas une divergence silencieuse) |
| `database.tables_count` | `len(database.tables)` (relation ORM) | compté depuis le Data Plane XML (best-effort) | le CP XML ne copie pas les tables | exclu de la comparaison |
| `database_permission.to_dict()` user_email/user_name | relation ORM | résolu depuis security.xml | représentation | équivalent |
| `common_permission` | colonne absente du modèle SQLite (6F) | champ catalog.xml | décision 6D.1 | exclu de la comparaison en 6E |
| `table_permission.database_id` | absent du modèle ORM | dénormalisé dans catalog.xml | besoin du contrôle métier inter-fichiers | exclu de la comparaison |

Le mode compare ne « choisit » jamais XML silencieusement : toute différence
est loggée et enregistrée dans `control_plane.divergences()`.

## 6. Rollback

`CONTROL_BACKEND=sqlite` reste le défaut : repasser à cette valeur restaure
immédiatement le comportement historique (SQLite est maintenu à jour en mode
compare). Les snapshots XML + backup `control-seed` (copie + SHA-256) sont
conservés. Aucune suppression irréversible.

## 7. Tests

- **Tests Phase 6E : 9/9 passés** (`tests/test_control_plane_migration.py`).
- **Suite complète : 369 passés, 0 échoué** (360 précédents + 9).

## 8. Performance (mesures réelles, 200 itérations, ms)

| Opération | SQLite (moy / médiane) | XML (moy / médiane) |
|---|---|---|
| get_user_by_email | 0.246 / 0.234 | 1.012 / 0.976 |
| get_user | 0.234 / 0.209 | 0.995 / 0.984 |
| list_users (20 users) | 0.392 / 0.369 | 10.076 / 10.351 |
| list_roles | 0.108 / 0.098 | 0.415 / 0.412 |
| get_database | 0.120 / 0.107 | 0.025 / 0.023 |
| list_database_permissions | 0.084 / 0.075 | 0.025 / 0.022 |

XML relit/valide le fichier à chaque appel (cohérence prioritaire, pas de
cache) : coût visible sur les listes volumineuses ; optimisations prévues plus
tard (décision 6D). Compare = somme des deux + normalisation.

## 9. Fichiers modifiés

**Créés** :
- `app/control_plane/__init__.py`, `base.py`, `views.py`, `sqlite_backend.py`, `xml_backend.py`, `compare_backend.py`
- `tests/test_control_plane_migration.py`

**Modifiés** :
- `app/services/auth_service.py`, `user_service.py`, `permission_service.py`, `database_service.py`, `history_service.py`, `audit_service.py`, `tcp_credential_service.py`
- `app/__init__.py` (loader JWT via adaptateur, `create-admin` via adaptateur, contrôle de démarrage fail-closed xml/compare, CLI `control-seed`)
- `app/routes/tcp.py` (show-password via adaptateur)

**Non modifiés** : modèles SQLAlchemy, `schema_migrations.py`, `UnlockService`, protocole/serveur TCP, moteur Data Plane XML, routes REST (contrats inchangés).

## 10. SQLite

**SQLite conservé, non supprimé.** Modèles, `db.session`, migrations, données
intactes. `CONTROL_BACKEND=sqlite` reste le comportement par défaut.

## 11. Data Plane

La migration n'a **pas dupliqué** `tables`/`columns`/`rows`/`indexes` dans le
Control Plane. Le catalogue SQLite (pont) et les fichiers XML Data Plane sont
inchangés ; `catalog.xml` ne contient que des références.

## 12. État de migration

**PHASE_6E_READY_FOR_6F**

Justification : l'abstraction fonctionne (3 backends) ; SQLite fonctionne comme
avant (369/369) ; XML fonctionne indépendamment (login/register/permissions/TCP
testés en mode XML, backend sans import SQLAlchemy) ; Compare détecte réellement
les divergences ; les services migrés fonctionnent dans les trois modes ; la
double-write est contrôlée (rollback XML + signalement) ; le rollback
`CONTROL_BACKEND=sqlite` est immédiat ; l'authentification, les permissions,
TCP et REST fonctionnent ; aucun secret exposé ; SQLite toujours présent et
défaut ; aucune suppression irréversible.
