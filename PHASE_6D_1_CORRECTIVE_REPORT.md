# PHASE 6D.1 — Rapport correctif du Control Plane XML

**Date** : 2026-09-06 · **Statut** : ✅ Correctif terminé (aucune migration 6E effectuée)

---

## 1. Résumé

Audit des divergences entre `XmlControlPlaneService` (et ses XSD) et le modèle
SQLAlchemy réel. Trois divergences ont été trouvées et corrigées :

1. **`token_version`** : le XML exigeait `>= 1`, alors que le modèle SQLAlchemy
   autorise `0` (INTEGER `default=1`, sans contrainte CHECK).
2. **`database.name`** : le XML exigeait l'unicité **globale** du nom, alors que
   la règle réelle (dans `DatabaseService`) est l'unicité **par propriétaire**
   (`filter_by(owner_id, name)`).
3. **`COMMON_PERMISSION`** : le XML **rejetait** une base COMMON sans
   `common_permission`, alors que les bases historiques n'ont pas cette colonne.
   Le comportement retenu : état historique **valide**, niveau collectif
   effectif = défaut configuré (`COMMON_PERMISSION_DEFAULT=VIEW`), appliqué en
   lecture seule (aucune valeur inventée ni réécrite).

Aucun composant SQLite/SQLAlchemy, service métier, route, TCP ou migration n'a
été modifié.

## 2. Audit effectué

- `backend/app/models/user.py`, `database.py` (contraintes réelles)
- `backend/app/schema_migrations.py` (migration V5)
- `backend/app/services/database_service.py` (check de doublon)
- `backend/app/services/auth_service.py`, `user_service.py`, `app/__init__.py`
  (usage JWT de `token_version`)
- `backend/app/xml_control/service.py`, `records.py`, `store.py`
- 4 XSD du Control Plane (`app/static/control/`)
- `backend/app/xml_control/exporter.py`
- données réelles `backend/xmlforge.db` (`users.token_version = 1`)

## 3. token_version

- **Règle trouvée (SQLite/SQLAlchemy)** : `token_version = db.Column(db.Integer,
  nullable=False, default=1)` — **aucune contrainte CHECK**. La migration V5
  crée `INTEGER NOT NULL DEFAULT 1`. Partout dans le code, la valeur est lue via
  `user.token_version or 1` (le `0` est donc coercé en `1` au moment de la
  comparaison JWT, mais **stockable** en base).
- **Règle retenue (XML)** : `token_version ≥ 0` (0 autorisé, négatifs rejetés).
- **Modifications** :
  - `security.xsd` : `tokenVersionType` `minInclusive` 1 → **0**.
  - `service.py` `_validate_user` : rejet si `< 0` (au lieu de `< 1`).
  - `records.py` `UserRecord.from_element` : correction du `or 1` qui écrasait
    `0` → seul l'attribut **absent** retombe sur la valeur par défaut 1.
- **Tests** : 0 accepté (XSD + round-trip service), 1 accepté, négatif rejeté.

## 4. Database.name

- **Contrainte SQLite réelle** : **aucun** `UniqueConstraint` sur `name`. Le
  contrôle de doublon est applicatif : `DatabaseService.create` fait
  `Database.query.filter_by(owner_id=creator_id, name=name).first()` →
  unicité **(owner, name)**, pas globale.
- **Ancienne contrainte XML** : `name` unique globalement (trop restrictif).
- **Nouvelle contrainte XML** : unicité sur **(owner effectif, name)** où
  `owner = owner_id or creator_id` — identique à SQLite. Deux propriétaires
  peuvent avoir une base homonyme.
- **Justification** : fidélité sémantique ; ne pas rendre le XML plus restrictif
  que le système réel.
- **Modifications** :
  - `service.py` `_validate_database` : unicité (owner, name).
  - `service.py` `validate_integrity` : ajout de la vérification (owner, name).
  - `catalog.xsd` : **inchangé** (aucune contrainte `name` n'y figurait ; la
    contrainte composite reste dans la couche métier car `owner` = `owner_id or
    creator_id` ne peut pas s'exprimer fidèlement en XSD — `owner_id` est
    optionnel et le repli sur `creator_id` est une règle Python).
- **Tests** : même nom + même owner rejeté ; même nom + owner différent accepté ;
  modification de nom ; conflit lors d'une modification.

## 5. COMMON_PERMISSION

- **Comportement historique** : la colonne `common_permission` **n'existe pas**
  dans le modèle SQLAlchemy ni dans la base historique. Une base `COMMON`
  exportée par 6C porte donc `common_permission` absent.
- **Comportement XML (6D)** : `validate_integrity` **rejetait** « COMMON sans
  common_permission ».
- **Décision retenue** : une base COMMON sans `common_permission` est un **état
  historique valide**. Le niveau collectif effectif est le **défaut configuré**
  (`COMMON_PERMISSION_DEFAULT`, VIEW), calculé **en lecture seule** via
  `effective_common_permission()` — aucune valeur n'est inventée ni réécrite
  dans le fichier. Les bases COMMON restent **collectives** (aucun grant
  individuel VIEW n'est créé ; les grants individuels sur COMMON restent
  rejetés).
- **Impact 6F** : en 6F, `PermissionService` utilisera `resolve_database_access`
  qui applique déjà l'ordre admin → owner → COMMON (collectif) → grants
  PERSONAL. La colonne `common_permission` pourra être ajoutée au modèle
  SQLAlchemy **à ce moment-là** (migration métier 6F), pas avant.
- **Tests** : COMMON sans common_permission → validé, effectif = VIEW ; COMMON
  avec niveau explicite non écrasé ; création COMMON sans common_permission
  autorisée.

## 6. permission_level

`permission_level()` reste une **primitive** : elle convertit les 4 booléens en
niveau NONE/VIEW/EDIT/MANAGE (avec `DELETE → can_admin` documenté). Elle ne
remplace pas `PermissionService`. Une primitive de lecture complémentaire,
`resolve_database_access(user_id, database_id)`, a été ajoutée pour **vérifier**
le calcul sur données XML réelles (admin → MANAGE/role ; owner → MANAGE/owner ;
COMMON → niveau collectif ; PERSONAL → grants ; inactif/inexistant → NONE). Elle
n'est **pas branchée** sur les services existants.

## 7. Fichiers modifiés

- `backend/app/static/control/security.xsd` — `tokenVersionType` minInclusive 0.
- `backend/app/xml_control/service.py` — `token_version ≥ 0` ; unicité
  (owner, name) ; suppression du rejet « COMMON sans common_permission » ;
  ajout `effective_common_permission()`, `resolve_database_access()`,
  `_common_access()` ; paramètre `common_permission_default` (+ `from_config`).
- `backend/app/xml_control/records.py` — `UserRecord.from_element` : préservation
  de `token_version=0`.
- `backend/tests/test_xml_control_models.py` — tests token_version (0 accepté,
  négatif rejeté).
- `backend/tests/test_xml_control_service.py` — tests COMMON (défaut effectif,
  niveau explicite), name (même/différent owner, conflit update), token_version
  (0/négatif), `resolve_database_access` (admin/owner/PERSONAL/COMMON/inactif/
  inexistant).

## 8. Tests

- **Correctifs 6D.1** : 16 tests ajoutés/ajustés, tous verts.
- **Suite Control Plane (6A+6B+6C+6D)** : **172/172 passés**.
- **Suite complète** : **360 passés, 0 échoué** (344 précédents + 16).

Aucun test masqué, désactivé ou skippé artificiellement.

## 9. Compatibilité

Aucune migration métier 6E n'a été effectuée. SQLite, SQLAlchemy, les services
métier (`AuthService`, `UserService`, `PermissionService`, `AuditService`,
`HistoryService`, `UnlockService`, `TcpCredentialService`), les routes REST, le
serveur TCP et les migrations sont **inchangés**. `CONTROL_BACKEND=sqlite` reste
le défaut ; `XmlControlPlaneService` reste indépendant de SQLAlchemy et
fail-closed (aucun fallback SQLite).

## 10. État pour la Phase 6E

**READY_FOR_6E**

Justification :
- `token_version` est compatible avec le modèle réel (0 autorisé, négatifs rejetés) ;
- l'unicité de `Database.name` correspond au comportement réel ((owner, name)) ;
- `COMMON_PERMISSION` est clairement défini (défaut explicite en lecture seule,
  aucune invention silencieuse) ;
- `permission_level()` reste une primitive et ne duplique pas `PermissionService` ;
- les XSD sont cohérents avec les règles retenues ;
- tous les tests passent (360/360) ;
- SQLite n'a pas été supprimé ;
- aucune migration métier de la Phase 6E n'a été commencée.
