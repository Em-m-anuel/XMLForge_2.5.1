# PHASE 6D — XmlControlPlaneService

## 1. Résumé

Création de `backend/app/xml_control/service.py` : la couche centrale d'accès au
Control Plane XML (lecture, validation, intégrité, mutation). **Aucune migration
des services métier** : SQLite reste la source de vérité et
`CONTROL_BACKEND=sqlite` le défaut. Le service est testé en isolation et
utilisable par les phases suivantes.

## 2. Architecture

```
Services métier SQLite (inchangés)          Tests
        │                                       │
        ▼                                       ▼
SQLAlchemy SQLite                      XmlControlPlaneService
                                             │
                        security.xml · catalog.xml · history.xml · audit/*.xml
                                             │
                                           store.py (atomic/lock/version/XSD/checksum)
```

## 3. Fichiers créés

- `backend/app/xml_control/service.py` — le service.
- `backend/tests/test_xml_control_service.py` — 65 tests.
- `backend/XML_CONTROL_PLANE_SERVICE.md` — documentation.

## 4. Fichiers modifiés

- `backend/app/errors.py` — ajout de `ControlPlaneIntegrityError` (409,
  `CONTROL_PLANE_INTEGRITY`) et `ControlPlaneNotFoundError` (404,
  `CONTROL_PLANE_NOT_FOUND`).
- `backend/app/xml_control/records.py` — ajout de `to_root()` / `from_root()`
  sur les 4 documents (réutilisés par le service, sans re-parsing).

## 5. Méthodes publiques

| Méthode | Document | L/E | Description |
|---|---|---|---|
| `get_user`, `get_user_by_email`, `list_users` | security | L | comptes |
| `get_role`, `get_role_by_name`, `list_roles`, `get_user_role` | security | L | rôles + résolution user→role |
| `get_tcp_credential`, `get_tcp_credential_by_username`, `list_tcp_credentials` | security | L | credentials TCP |
| `get_database`, `get_database_by_uuid`, `get_database_by_name`, `list_databases`, `get_owner_databases` | catalog | L | références des bases |
| `get_database_permission`, `list_database_permissions`, `get_table_permission`, `list_table_permissions` | catalog | L | ACL |
| `get_history`, `list_history` | history | L | historique |
| `get_audit_entry`, `list_audit`, `list_audit_months` | audit | L | audit mensuel |
| `is_admin`, `is_database_owner`, `permission_level` | security+catalog | L | primitives 6F |
| `validate_integrity`, `validate_data_plane_references` | tous | L | contrôle d'intégrité |
| `create/update/delete_role·user·tcp_credential` | security | E | mutations |
| `create/update/delete_database·database_permission·table_permission` | catalog | E | mutations |
| `add_history`, `add_audit` | history/audit | E | append |
| `get_document_version`, `get_document_checksum`, `snapshot_document`, `restore_document` | tous | L | version/checksum/snapshot |

## 6. Security

Lectures via `_load_security()` (XSD + re-vérification des relations).
Mutations : email unique (insensible à la casse), `role_id` existant,
`password_hash` obligatoire, `token_version ≥ 1`, `internal_id` unique, uuid
unique. Suppression d'utilisateur en **RESTRICT** (credentials TCP, grants,
bases possédées/créées).

## 7. Catalog

Lectures filtrées (database_id, user_id, table_id). Mutations : `name` unique,
`internal_id`/`uuid` uniques, `key_identifier` unique + format,
`creator_id`/`owner_id` existants, scope/status valides.

## 8. History

`get_history`/`list_history` avec filtres. `before_data`/`after_data` conservés
(CDATA), NULL = élément absent.

## 9. Audit

Lecture mensuelle (`YYYY-MM`), filtres `user_id`/`action` (+ `database_id`/
`table_id` recherchés au mieux dans `meta_data` JSON). Mois absent → `[]`/`None`
(état vide contrôlé, contrairement aux documents principaux). `success`
inexistant dans le modèle réel → valeur non-None rejetée explicitement.

## 10. COMMON / PERSONAL

- COMMON exige `common_permission ∈ {VIEW, EDIT, MANAGE}` ; rejet si absent.
- PERSONAL rejette `common_permission` présent.
- Grants individuels sur base COMMON → rejetés par `validate_integrity`.
- Niveaux : NONE/VIEW/EDIT/MANAGE ; DELETE exige `can_admin`.

## 11. Intégrité inter-documents

`validate_integrity()` vérifie (avec messages détaillés) : rôles/users/credentials
(security), références creator/owner/grant (catalog), cohérence COMMON, et
relations croisées security↔catalog. Incohérence → `ControlPlaneIntegrityError`.

## 12. Vérification Data Plane

`validate_data_plane_references()` : `table_permission.table_id` contrôlé contre
le document XML du Data Plane de la base référencée (aucune copie de table).
Base/chemin/table absents → erreur explicite. Testé (existant + inexistant).

## 13. Versioning

`expected_version` vérifié avant mutation ; conflit → `ConflictError` (409).
Version incrémentée par document modifié.

## 14. Checksum

`get_document_checksum()` = SHA-256 (prêt pour compare/double-write 6I).

## 15. Transactions multi-documents

`_control_plane_transaction` : verrous ordonnés (security→catalog→history→audit),
mutateurs sur copies profondes, validation XSD, snapshot puis écriture
atomique ; échec → restauration des snapshots. Mutateur retournant `False` =
garde seule (pas d'écriture). **Pas d'ACID SQL** (documenté, pas simulé).

## 16. Rollback

Snapshots par document + restauration automatique en cas d'échec (testé :
`delete_user` qui échoue laisse security et catalog intacts).

## 17. Fail-closed

security/catalog/history absents ou corrompus → `StorageError`/`XmlValidationError`.
Jamais de régénération silencieuse. Exception documentée : audit mensuel
créé au premier log du mois.

## 18. Gestion NULL

Attribut/élément absent = NULL ; chaîne vide préservée ; testé (history
before/after NULL, audit user_id NULL).

## 19. Gestion internal_id / UUID

`internal_id` conservé (recherche par ID entier) ; `uuid` conservé, backfill
déterministe assuré en 6C.

## 20. Tests

- **Tests 6D : 65/65 passés.**
- **Suite complète : 344 passés, 0 échoué** (279 précédents + 65 nouveaux).

## 21. Non-régressions

Aucune : auth, permissions, REST, TCP, Data Plane XML, XML engine, comparaison,
projection, Windows, 6A, 6B, 6C — tous verts.

## 22. Ce qui reste SQLite

Inchangé : 14 tables SQLAlchemy du Control Plane + projection de données.
`CONTROL_BACKEND=sqlite` actif. Aucun service basculé.

## 23. Ce qui n'a PAS été modifié

AuthService, UserService, PermissionService, AuditService, HistoryService,
TcpCredentialService, DatabaseService, routes REST, serveur TCP, modèles
SQLAlchemy, migrations. Aucun fichier SQLite supprimé, aucune table supprimée.

## 24. Limitations éventuelles

1. `database_id`/`table_id` d'audit ne sont pas des champs du modèle réel :
   filtres appliqués au mieux dans `meta_data` JSON ; `success` rejeté
   explicitement (non présent dans le modèle).
2. `name` de base rendu **unique** au niveau catalogue (plus strict que
   l'unicité SQLAlchemy actuelle « par propriétaire ») → à réconcilier en 6F
   lors du branchement de `DatabaseService`.
3. Lecture directe depuis XML à chaque appel (pas de cache) : cohérence
   prioritaire sur la performance (décision 6D).
4. `validate_data_plane_references` nécessite le chemin du Data Plane (ou un
   `xml_file_path` absolu) ; sinon erreur explicite.

## 25. Préparation Phase 6E

Le service fournit déjà : `get_user`, `get_user_by_email`, `list_users`,
`get_role`, `get_role_by_name`, `is_admin`, `create_user`, `update_user`,
`delete_user`, `create_role`, `update_role`, `get_document_version`… — tout ce
dont `AuthService`/`UserService` ont besoin pour être câblés sur
`security.xml` en 6E (avec `CONTROL_BACKEND`).
