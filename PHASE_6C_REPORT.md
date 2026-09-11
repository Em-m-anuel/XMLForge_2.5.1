# PHASE 6C — Rapport : Export SQLite → XML du Control Plane

**Date** : 2026-09-06 · **Statut** : ✅ Terminée (arrêt avant 6D, en attente de validation)

---

### 1. Résumé

Création d'un **exporteur déterministe** SQLite → XML pour le plan de contrôle,
avec sauvegarde (copie + SHA-256), snapshot des fichiers XML existants,
écriture atomique + validation XSD, et **vérification par relecture** des
comptages. Aucune modification de comportement applicatif : l'export est une
lecture de SQLite + écriture de fichiers XML. `CONTROL_BACKEND=sqlite` reste le
défaut.

### 2. Fichiers créés

- `backend/app/xml_control/exporter.py` — exporteur déterministe + mappings purs + backup + vérification.
- `backend/scripts/export_control_plane.py` — CLI d'export.
- `backend/tests/test_xml_control_plane_migration.py` — 12 tests.

### 3. Fichiers modifiés / supprimés

Aucun fichier existant modifié, aucun supprimé.

### 4. Ce qui est exporté / non exporté

- **Exporté** : `roles`, `users`, `tcp_credentials` → `security.xml` ; `databases`, `database_permissions`, `table_permissions` → `catalog.xml` ; `history` → `history.xml` ; `audit_logs` → `audit/audit-YYYY-MM.xml` (regroupement mensuel).
- **NON exporté** (projections du Data Plane) : `tables`, `columns`, `table_rows`. Vérifié par test (`test_no_table_column_row_in_catalog`).

### 5. Déterminisme

- Ordres stables (`ORDER BY id`).
- **Backfill UUID déterministe** via **UUIDv5** (namespace fixe + `type:internal_id`) → deux exports produisent des octets strictement identiques (testé sur les 3 fichiers + tous les mois d'audit).
- Les UUID déjà présents (`Database`, `History`, `AuditLog`) sont **conservés** tels quels.

### 6. IDs / NULL

- `internal_id` = ancien ID SQLAlchemy, **conservé** (testé).
- NULL → attribut/élément absent (jamais `""`), réutilisant les records 6B.

### 7. Sauvegarde / snapshot / rollback

- `backup_sqlite()` : copie de `xmlforge.db` + fichier `.sha256` (testé : contenu identique + digest cohérent) ; `None` pour les bases en mémoire ou non-fichier.
- Snapshot des fichiers XML existants avant écriture ; **restauration automatique en cas d'échec** (testé : le fichier antérieur reste intact après un export qui échoue).

### 8. Fail-closed

- `role_id` NULL sur un utilisateur → `ValueError` explicite (testé).
- `key_identifier` manquant sur une base → `ValueError` explicite (testé via mapping).
- `timestamp` NULL sur une entrée d'audit → `ValueError` explicite (testé via mapping).

### 9. Vérification des comptages

L'exporteur **relit et revalide** chaque fichier écrit (XSD) puis compare aux
comptages SQLite attendus (`roles`, `users`, `tcp_credentials`, `databases`,
`database_permissions`, `table_permissions`, `history`, `audit_logs`). Toute
divergence → `StorageError`. (testé)

### 10. Démonstration sur données réelles

Export exécuté sur une **copie isolée** de `backend/xmlforge.db` (le fichier
réel du workspace n'a pas été touché) :

- 2 rôles, 1 utilisateur, 1 credential TCP, 0 base, 7 history, 14 audit ;
- `security.xml` contient uniquement des **hashes bcrypt** (aucun clair) ;
- backup `xmlforge-*.db` + `.sha256` générés.

### 11. Résultats pytest

- Suite 6C : **12/12 passés**.
- Suite complète : **279 passés, 0 échoué** (267 précédents + 12 nouveaux).

### 12. Non-régressions

Aucune : suite complète verte (auth, permissions, REST, TCP, Data Plane XML,
XML engine, comparaison, projection, Windows, 6A, 6B).

### 13. Ce qui reste SQLite

**Inchangé** : les 14 tables SQLAlchemy du Control Plane et la projection de
données. Aucun service basculé, `CONTROL_BACKEND=sqlite` toujours actif.

### 14. Ce qui est explicitement NON implémenté (phases suivantes)

`XmlControlPlaneService` (6D), migration des services (6E–6H), double-write
(6I), bascule `CONTROL_BACKEND=xml`, rotation/compression/rétention d'audit
(6G), unlocks/revoked en mémoire (6E/6F), purge des hardcodings (6L),
`common_permission` effectif (6F).

### 15. Préparation pour Phase 6D

`XmlControlPlaneService` disposera de : `records.py` (structures), 4 XSD
(validation), `store.py` (lecture/écriture/version/checksum), `exporter.py`
(seed initial des fichiers). 6D pourra charger `security.xml`/`catalog.xml`
et exposer les lectures (get_user, list_roles, etc.) sans encore brancher les
services.

### 16. Risques / points signalés

1. Le **backfill UUID est en UUIDv5 déterministe** (choix technique pour
   satisfaire « déterministe + stable »). Si le produit préfère des UUIDv4
   aléatoires **persistés**, il faudra les générer une seule fois en 6C puis
   les stocker en base (hors périmètre actuel). → à confirmer.
2. `common_permission` n'est **pas encore** exporté (la colonne n'existe pas
   sur `databases`) : sera ajouté en 6F.
3. `table_permission.database_id` est dénormalisé pendant l'export (recherche
   via le catalogue ORM `Table`) ; un grant dont la table n'existe plus exporte
   `database_id=None` (permis par le XSD, signalé comme donnée à vérifier).
4. Les timestamps exportés sont en microsecondes (repris tels quels de la base).
