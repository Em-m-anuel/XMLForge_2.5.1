# XML Control Plane — Documentation (Phase 6B)

**Projet** : XMLForge · **Date** : 2026-09-06
**Statut** : modèles + XSD + validation **créés**. Le Control Plane XML n'est **pas encore utilisé** par les services (ce sera 6C+). `CONTROL_BACKEND=sqlite` reste le comportement par défaut.

---

## 1. Architecture des fichiers

```
backend/
  app/static/control/          # XSD (ressources, pas des fichiers de données)
    security.xsd
    catalog.xsd
    history.xsd
    audit.xsd
  app/xml_control/
    __init__.py
    store.py                   # Phase 6A : stockage atomique, verrous, version, checksum, snapshot, validation
    records.py                 # Phase 6B : modèles + sérialisation/désérialisation + validation
  data/control/                # DONNÉES PERSISTANTES (jamais servi en statique)
    security.xml               # rôles + utilisateurs + credentials TCP
    catalog.xml                # références des bases + grants (ACL)
    history.xml                # historique métier
    audit/
      audit-YYYY-MM.xml        # audit mensuel (rotation)
      audit-YYYY-MM.xml.gz     # (compression des mois anciens, phases ultérieures)
```

Les fichiers de `data/control/` sont des **données persistantes**, jamais des
artefacts régénérables silencieusement : `security.xml`/`catalog.xml` absents
ou corrompus → **erreur explicite (fail-closed)**.

---

## 2. Rôle de chaque XML

| Fichier | Contenu | Absent/corrompu |
|---|---|---|
| `security.xml` | `<roles>`, `<users>`, `<tcp_credentials>` | erreur explicite |
| `catalog.xml` | `<databases>` (références), `<database_permissions>`, `<table_permissions>` | erreur explicite |
| `history.xml` | `<entries>` (historique métier V2, before/after JSON) | erreur explicite dès qu'utilisé (6G) |
| `audit/audit-YYYY-MM.xml` | audit de sécurité, rotation mensuelle | le mois courant pourra être créé au premier log (logique AuditStore, phase ultérieure) |

---

## 3. Structures principales

- `security.xml` : `roles/role` (internal_id, uuid?, name, description?, created_at?), `users/user` (internal_id, uuid?, email, role_id, is_active, token_version + enfants full_name, password_hash, created_at?, updated_at?, last_login?), `tcp_credentials/credential` (internal_id, uuid?, user_id, tcp_username, tcp_host, tcp_port, is_active + enfant password_hash).
- `catalog.xml` : `databases/database` (internal_id, uuid?, name, description?, comment?, creator_id, owner_id?, scope, common_permission?, xml_file_path?, projection_path?, document_version, xml_checksum?, sync_status?, status, key_identifier, dates, last_modified_by_*), `database_permissions/database_permission`, `table_permissions/table_permission` (droits `can_read/can_write/can_ddl/can_admin`).
- `history.xml` : `entries/entry` (internal_id, uuid?, user_id, user_name, action_type, element_type, element_name, ip_address?, database_id?, table_id?, created_at + enfants description?, before_data?, after_data? en CDATA).
- `audit-YYYY-MM.xml` : `entries/entry` (internal_id, uuid?, user_id?, user_name?, ip_address?, action, element_type?, element_name?, timestamp + enfants description?, meta_data? en CDATA).

---

## 4. Data Plane / Control Plane — différence

- **Data Plane** (déjà XML) : données métier (tables, colonnes, contraintes, index, lignes).
- **Control Plane** (cible XML) : utilisateurs, rôles, ACL/grants, ownership, références des bases, audit, historique, credentials TCP.

Le Control Plane **ne recopie jamais** les tables/colonnes/lignes : `catalog.xml`
ne contient que des **références** (`database_id`, `table_id`, chemins).

---

## 5. COMMON / PERSONAL

- `scope="PERSONAL"` : permissions individuelles (grants).
- `scope="COMMON"` : accès **collectif** via `common_permission` ∈ {VIEW, EDIT, MANAGE}. Tout utilisateur actif en bénéficie automatiquement ; **aucun grant individuel nécessaire**. Une base COMMON ne doit pas être déclinée en grants individuels.
- `common_permission` est **optionnel en XSD** ; absent → la couche métier applique `COMMON_PERMISSION_DEFAULT` (VIEW).

---

## 6. Règles de sécurité

- Mots de passe : **hash bcrypt uniquement** (jamais de clair) pour `users.password_hash` et `tcp_credentials.password_hash`.
- Le secret JWT reste en configuration/environnement — **jamais** dans un XML.
- `revoked_tokens` et `unlocks` : **mémoire uniquement** (non persistés). L'invalidation JWT persistante repose sur `user.token_version`.
- Parsing **XXE-safe** (`resolve_entities=False`, `no_network=True`, `huge_tree=False`) via `store.parse_safely`.
- Dossier `data/control/` en `0700`, fichiers sensibles en `0600`, jamais servis en statique.

---

## 7. Règles de version

- Chaque document porte `version` (entier ≥ 1) en racine.
- Pas de `schema_migrations` dans le Control Plane final.
- Mutations via `store.mutate(..., expected_version=...)` : conflit → `ConflictError` (409).

---

## 8. Contraintes XSD (intra-document)

- `security.xsd` : `role.internal_id` unique, `user.internal_id` unique, `user.email` unique, `tcp_username` unique, un credential par user (`user_id` unique), `user.role_id → role.internal_id` (keyref), `tcp_credentials.user_id → user.internal_id` (keyref), `token_version ≥ 0` (cohérence SQLAlchemy : 0 stockable, négatifs rejetés), `tcp_port ∈ [1, 65535]`.
- `catalog.xsd` : `database.internal_id` unique, `key_identifier` unique + format `XML-XXXX-XXXX-XXXX`, `scope` ∈ {PERSONAL, COMMON}, `common_permission` ∈ {VIEW, EDIT, MANAGE}, `status` ∈ {ACTIVE, ARCHIVED}, `sync_status` ∈ {PENDING, SYNCED, ERROR}, unicité composite (database_id+user_id) et (table_id+user_id).
- **Unicité du nom de base** : (owner effectif, name) — **couche métier uniquement** (pas d'`xs:unique` sur `name`, règle identique à `DatabaseService`).
- `history.xsd` / `audit.xsd` : `internal_id` unique, `month` au format `YYYY-MM`, `action` non vide (≤ 100 car.).

---

## 9. Contraintes inter-documents (hors XSD)

> **Les contraintes inter-documents sont contrôlées par la couche métier
> (`XmlControlPlaneService`, phases 6C+) et non par XSD.**

- `catalog.database.owner_id` / `database_permission.user_id` → `security.users.internal_id` (fichier différent).
- `catalog.table_permission.table_id` → table du **Data Plane** (fichier différent) : l'XSD ne peut pas faire de keyref inter-fichier ; la vérification sera métier.
- Aucun faux keyref inter-fichier n'est déclaré dans les XSD.

---

## 10. Décisions : unlocks / revoked_tokens

- `unlocks` : mémoire uniquement (UnlockStore, phases suivantes). Non persistés.
- `revoked_tokens` : mémoire uniquement. Non persistés.
- `schema_migrations` : disparaît du Control Plane final.

---

## 11. Ce qui reste SQLite

**Tout le plan de contrôle SQLAlchemy reste inchangé** (14 tables) tant que
`CONTROL_BACKEND=xml` n'est pas activé (phases 6D/6E+). La projection de
données reste optionnelle (Phase 4).

---

## 12. Ce qui sera fait en 6C+

6C export SQLite → XML (déterministe, IDs conservés, backfill UUID) · 6D
`XmlControlPlaneService` · 6E Auth/Users/Rôles · 6F ACL + COMMON · 6G Audit
(rotation/compression/rétention) + History · 6H TCP credentials · 6I
double-write/compare · 6J XML source de vérité · 6K tests sans SQLite · 6L
suppression.
