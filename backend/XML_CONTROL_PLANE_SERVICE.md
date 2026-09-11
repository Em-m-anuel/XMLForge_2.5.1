# XmlControlPlaneService — Documentation (Phase 6D)

**Projet** : XMLForge · **Date** : 2026-09-06

> **Statut important** : `XmlControlPlaneService` existe et est testé, mais
> **n'est pas encore utilisé comme source de vérité par les services métier**.
> SQLite reste la source de vérité de l'application et `CONTROL_BACKEND=sqlite`
> le défaut. La bascule se fera en 6E+.

---

## 1. Rôle du service

Couche centrale d'accès au Control Plane XML : chargement, validation, contrôle
d'intégrité (intra- et inter-documents), lecture et mutation de :

- `security.xml` (rôles, utilisateurs, credentials TCP)
- `catalog.xml` (références des bases, grants/ACL)
- `history.xml` (historique métier)
- `audit/audit-YYYY-MM.xml` (audit mensuel)

Il ne **remplace pas** un ORM : les records sont de simples structures de
données (Phase 6B) ; le parsing sécurisé, les verrous, l'écriture atomique, la
version et le checksum sont délégués à `store.py` (Phase 6A).

## 2. Architecture

```
Services métier (plus tard 6E–6H)
            │
            ▼
XmlControlPlaneService (app/xml_control/service.py)
            │
    ┌───────┼──────────────┐
    ▼       ▼              ▼
security.xml catalog.xml history.xml
                            ▼
                      audit/YYYY-MM.xml
            │
            ▼
        store.py (atomic write / lock / checksum / version / XSD)
```

`XmlControlPlaneService` ne dépend ni de Flask ni de SQLAlchemy : il s'instancie
avec un simple répertoire de stockage (ou des chemins explicites).

## 3. Méthodes publiques

### Lectures security
`get_user`, `get_user_by_email`, `list_users`, `get_role`, `get_role_by_name`,
`list_roles`, `get_tcp_credential`, `get_tcp_credential_by_username`,
`list_tcp_credentials`, `get_user_role` (résolution user → role).

### Lectures catalog
`get_database`, `get_database_by_uuid`, `get_database_by_name`, `list_databases`,
`get_database_permission`, `list_database_permissions(database_id, user_id)`,
`get_table_permission`, `list_table_permissions(database_id, table_id, user_id)`,
`get_owner_databases(user_id)`.

### Primitives de permissions (pour 6F)
`is_admin(user_id)`, `is_database_owner(user_id, database_id)`,
`permission_level(...)` (fonction module : NONE/VIEW/EDIT/MANAGE),
`effective_common_permission(database)`,
`resolve_database_access(user_id, database_id)` (ordre : absent/inactif → admin →
owner → COMMON collectif → grants PERSONAL).

### History / Audit
`get_history`, `list_history(user_id, database_id, table_id, action)`,
`get_audit_entry(audit_id, month)`, `list_audit(month, user_id, database_id,
table_id, action, success)`, `list_audit_months`.

### Intégrité
`validate_integrity()`, `validate_data_plane_references(xml_storage_folder)`.

### Mutations (XML uniquement, pas utilisées par l'app)
- security : `create_role`, `update_role`, `create_user`, `update_user`,
  `delete_user`, `create_tcp_credential`, `update_tcp_credential`,
  `delete_tcp_credential` ;
- catalog : `create_database`, `update_database`, `delete_database`,
  `create_database_permission`, `update_database_permission`,
  `delete_database_permission`, `create_table_permission`,
  `update_table_permission`, `delete_table_permission` ;
- `add_history`, `add_audit(record, month)`.

### Version / checksum / snapshot
`get_document_version(document)`, `get_document_checksum(document)`,
`snapshot_document(document)`, `restore_document(document, snap)` avec
`document ∈ {security, catalog, history, audit:<YYYY-MM>}`.

## 4. Règles d'intégrité

- **security.xml** : `user.role_id → role.internal_id`, `tcp_credential.user_id
  → user.internal_id` (déjà garanties par le XSD, re-vérifiées au chargement).
- **catalog.xml (interne)** : `database_permission.database_id → database`,
  `table_permission.database_id → database`.
- **inter-documents** (hors XSD, vérifiées par `validate_integrity`) :
  `owner_id`/`creator_id`/`grant.user_id` → utilisateurs de `security.xml` ;
  `grant.database_id` → bases du catalogue.
- **COMMON** : accès collectif via `effective_common_permission` (explicite ou
  défaut configuré) ; aucun grant individuel (`database_permission`/
  `table_permission`) sur une base COMMON. Une base COMMON **sans**
  `common_permission` est un état historique valide (défaut appliqué en lecture).
- **PERSONAL** : `common_permission` absent (rejeté sinon).
- **Unicité du nom de base** : par **(owner effectif, name)** (règle identique à
  `DatabaseService`), pas globale.
- Toute incohérence → `ControlPlaneIntegrityError` avec message détaillé.

## 5. Data Plane check

`validate_data_plane_references()` vérifie `table_permission.table_id` contre le
document XML du Data Plane de la base référencée (aucune copie de table).
Base absente / chemin manquant / table introuvable → `ControlPlaneIntegrityError`.

## 6. COMMON / PERSONAL

- `scope="COMMON"` + `common_permission ∈ {VIEW, EDIT, MANAGE}` = droit
  **collectif** : aucun grant individuel requis ni toléré.
- `scope="PERSONAL"` : permissions individuelles (4 booléens).
- Niveaux : `VIEW` = read · `EDIT` = read+write(+ddl) · `MANAGE` = tout ·
  `DELETE` exige `can_admin`.

## 7. Versioning / checksum

- Chaque document porte `version` (entier ≥ 1). Toute mutation via `store.mutate`
  incrémente la version et refuse un `expected_version` obsolète (`ConflictError`).
- `get_document_checksum` = SHA-256 hexadécimal (pour compare/double-write 6I).

## 8. Transactions multi-documents

`_control_plane_transaction(ops, expected_versions)` : verrous acquis dans un
**ordre déterministe** (security → catalog → history → audit), vérification des
versions, application des mutateurs sur copies profondes, validation XSD,
snapshot puis écriture atomique ; tout échec → restauration des snapshots.
Un mutateur retournant `False` = garde cohérente seule (pas d'écriture).

> **Ce n'est pas une transaction ACID** : en cas de crash entre deux écritures,
> la cohérence est rétablie par validation XSD + intégrité au démarrage
> (vérifications décrites en Phase 5). C'est documenté, pas simulé.

## 9. Verrouillage

`store.database_lock` (flock + RLock) par fichier. Ordre fixe pour éviter les
deadlocks. Mono-process (décision validée Phase 6).

## 10. Fail-closed

- `security.xml`/`catalog.xml`/`history.xml` absents ou corrompus → erreur
  explicite (`StorageError`/`XmlValidationError`). Jamais de régénération.
- **Exception documentée** : un fichier d'audit mensuel absent est **créé** à la
  première écriture du mois (`add_audit`), et sa lecture retourne un résultat
  vide (`[]` / `None`). Ceci ne s'applique **jamais** aux documents principaux.
- Jamais de fallback silencieux vers SQLite.

## 11. Unlocks / revoked tokens

Non persistés (mémoire uniquement). Seule donnée persistante d'invalidation
JWT : `user.token_version` dans `security.xml`.

## 12. Ce qui reste SQLite / ce qui sera migré en 6E

Reste SQLite (inchangé) : les 14 tables SQLAlchemy + projection de données ;
services `AuthService`, `UserService`, `PermissionService`, `AuditService`,
`HistoryService`, `TcpCredentialService`, `DatabaseService` inchangés.

6E câblera `AuthService`/`UserService` sur ce service (lectures/écritures
security.xml), 6F `PermissionService` (ACL + COMMON), 6G audit/history, 6H TCP.
