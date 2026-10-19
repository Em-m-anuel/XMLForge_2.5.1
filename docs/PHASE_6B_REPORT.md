# PHASE 6B — Rapport : Modèles XML + XSD + validation

**Date** : 2026-09-06 · **Statut** : ✅ Terminée (arrêt avant 6C, en attente de validation)

---

### 1. Résumé

Phase de **modélisation et validation** uniquement : création des structures
Python (`records.py`), des 4 XSD du Control Plane et de la suite de tests.
**Aucune logique métier SQLite n'a été modifiée** ; `CONTROL_BACKEND=sqlite`
reste le défaut. Le Control Plane XML n'est pas encore utilisé par les services.

### 2. Fichiers créés

- `backend/app/xml_control/records.py` — modèles (dataclasses + enums) + sérialisation/désérialisation + validation XSD.
- `backend/app/static/control/security.xsd`
- `backend/app/static/control/catalog.xsd`
- `backend/app/static/control/history.xsd`
- `backend/app/static/control/audit.xsd`
- `backend/tests/test_xml_control_models.py` — 50 tests.
- `XML_CONTROL_PLANE.md` — documentation.
- `PHASE_6B_REPORT.md` — ce rapport.

### 3. Fichiers modifiés

- Aucun fichier existant modifié (hors l'ajout des tests/doc ci-dessus).

### 4. Structure security.xml

`roles/role` · `users/user` (email, role_id, is_active, token_version en attributs ; full_name, password_hash, created_at/updated_at/last_login en enfants) · `tcp_credentials/credential` (tcp_username, tcp_host, tcp_port, user_id + enfant password_hash bcrypt). **Pas** de `revoked_tokens`, **pas** de `unlocks` (décision validée).

### 5. Structure catalog.xml

`databases/database` (références + ownership + scope + common_permission + chemins + version/checksum/sync_status + key_identifier) · `database_permissions/database_permission` · `table_permissions/table_permission`. **Aucune** définition de table/colonne/row (Data Plane).

### 6. Structure history.xml

`entries/entry` : tous les champs réels du modèle `History` (user_name, action_type, element_type, element_name, description, ip_address, database_id, table_id) + `before_data`/`after_data` en CDATA (NULL = élément absent).

### 7. Structure audit mensuel

`audit/audit-YYYY-MM.xml` : `entries/entry` fidèle au modèle `AuditLog` réel (user_id nullable, user_name, ip_address, action, element_type, element_name, description, meta_data en CDATA, timestamp).

### 8. Modèles Python

`records.py` : `SecurityDocument` (Role/User/TcpCredentialRecord), `CatalogDocument` (Database/DatabasePermission/TablePermissionRecord), `HistoryDocument` (HistoryRecord), `AuditDocument` (AuditRecord) + enums `Scope` et `CommonPermission`. Indépendants de Flask/SQLAlchemy. Round-trip `to_xml_bytes()` / `from_xml_bytes()` avec validation XSD.

### 9. Contraintes XSD

Voir `XML_CONTROL_PLANE.md` §8 : unicité (internal_id, email, tcp_username, key_identifier, composites), keyref internes (role_id, tcp user_id), enums (scope, common_permission, status, sync_status), formats (key_identifier, month), bornes (token_version ≥ 1, port 1–65535).

### 10. Contraintes inter-documents

Non exprimées en XSD (impossible entre fichiers) : documentées et laissées à la couche métier (`XmlControlPlaneService`). Aucun faux keyref inter-fichier.

### 11. Gestion NULL

Attribut/élément **absent** = NULL ; chaîne vide préservée ; rien n'est transformé en `""` ni en `"NULL"`. Testé (`test_null_vs_empty_string_distinction`).

### 12. Gestion internal_id / UUID

`internal_id` (ancien ID SQLAlchemy) **conservé** et requis ; `uuid` optionnel (backfill prévu en 6C). L'un ne remplace pas l'autre.

### 13. Tests effectués

`tests/test_xml_control_models.py` : 50 tests (sécurité 14, catalogue 13, history 4, audit 6, général 13).

### 14. Résultats pytest

- Suite 6B : **50/50 passés**.
- Suite complète : **267 passés, 0 échoué** (217 précédents + 50 nouveaux).

### 15. Non-régressions

Aucune : suite complète verte (auth, permissions, REST, TCP, Data Plane XML, XML engine, comparaison SQLite/XML, projection, Windows).

### 16. Ce qui reste SQLite

**Inchangé** : les 14 tables SQLAlchemy du Control Plane et la projection de données. Aucun service n'a été basculé.

### 17. Ce qui est explicitement NON implémenté (phases suivantes)

Export SQLite→XML (6C), `XmlControlPlaneService` (6D), migration des services (6E–6H), double-write/compare (6I), bascule `CONTROL_BACKEND=xml`, rotation/compression d'audit (6G), unlocks/revoked en mémoire (6E/6F), purge des hardcodings (6L). Aucune création automatique de `security.xml`/admin.

### 18. Préparation pour Phase 6C

- `records.py` fournit les cibles de sérialisation de l'export.
- Les XSD fournissent la validation post-export (avant bascule).
- `store.py` fournit l'écriture atomique + version + checksum pour écrire les fichiers exportés.

### 19. Risques / points signalés

1. **`success` / `database_id` / `table_id` d'audit** (mentionnés dans un exemple de conception) **n'existent pas** dans le modèle `AuditLog` réel : ils ne sont **pas** déclarés dans `audit.xsd` (les `database_id`/`table_id` vivent dans `meta_data` JSON). → à confirmer si le produit souhaite les ajouter plus tard.
2. **Noms de rôles** : la base réelle stocke `admin`/`user` en minuscules (et `Role` est documenté « extensible ») ; l'XSD impose `name` obligatoire + unique mais **pas** d'enum {ADMIN, USER}. → à confirmer si un enum strict est requis.
3. **`database name` non unique globalement** : le code vérifie l'unicité par propriétaire (`owner_id + name`), pas globale ; pas de contrainte XSD `name` unique.
4. `token_version ≥ 1` appliqué (décision validée), alors qu'un exemple de conception montrait `token_version="0"`.
5. `database_id` ajouté à `table_permission` (dénormalisation demandée par la conception, absente du modèle SQLAlchemy actuel) pour faciliter le contrôle métier inter-fichiers.
