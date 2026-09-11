# PHASE 6H — Basculement contrôlé : XML source de vérité du Control Plane

**Date** : 2026-09-07

---

## 1. Résumé

XML est désormais **source de vérité du Control Plane** : en
`CONTROL_BACKEND=xml`, toutes les lectures/écritures du plan de contrôle
(users, rôles, bases, permissions, credentials TCP, history, audit) passent
par les fichiers XML, et **aucune donnée Control Plane n'est écrite dans les
tables SQLite** (démontré par test). Trois corrections majeures ont été
nécessaires : allocation d'`internal_id` **sous verrou** (bug de concurrence
XML pur), import du backend XML **sans SQLAlchemy** (rendu possible en rendant
`app/__init__.py`, `app/services/__init__.py` et `app/xml_engine/__init__.py`
légers), et **rotation/compression/rétention de l'audit** implémentée.

SQLite reste conservé comme fallback/référence ; `CONTROL_BACKEND=sqlite`
reste le défaut.

## 2. Architecture avant 6H

```
Services → Control Plane Adapter → SQLite (autorité) ; XML (shadow, même id)
```

## 3. Architecture après 6H

```
Services → Control Plane Adapter
   ├── sqlite (fallback/référence, défaut)
   ├── xml   (SOURCE DE VÉRITÉ, sans SQLAlchemy)
   └── compare (diagnostic)
```

## 4. Procédure de basculement

1. **Backup** : `flask control-seed` exporte SQLite → XML (sauvegarde SQLite +
   SHA-256 via `exporter.backup_sqlite`).
2. **Validation pré-bascule** : comparaison SQLite/XML (mode compare) → 0
   divergence fonctionnelle.
3. **Activation** : `CONTROL_BACKEND=xml`. Au démarrage : validation XSD de
   `security.xml`/`catalog.xml`/`history.xml` (fail-closed).
4. **Rollback** : repasser `CONTROL_BACKEND=sqlite` (SQLite maintenu à jour en
   mode compare).

## 5. Migration des données

Export déterministe existant (`exporter.export_control_plane`) : IDs conservés,
UUIDv5 backfill, comptages vérifiés. Aucun import destructif.

## 6–17. Tests XML-only (résumé)

`tests/test_control_plane_6h_switch.py` (10 tests) :
- **XML ne touche pas SQLite CP** : après register/login/grant/credentials, les
  tables SQLite `users/database_permissions/table_permissions/tcp_credentials/
  history/audit_logs` restent **vides** (rôles seedés par la migration bootstrap,
  identiques dans les deux backends).
- **Scénario complet XML-only** : auth, bases PERSONAL/COMMON (common_permission
  EDIT), tables/colonnes/lignes (Data Plane), grants PERSONAL acceptés, grants
  COMMON refusés, accès collectif COMMON, TCP réel, **redémarrage** (persistance
  + login).
- **Import sans SQLAlchemy** (sous-processus) : `import app.control_plane.xml_backend`
  ne charge ni `sqlalchemy`, ni `flask_sqlalchemy`, ni `app.extensions`, ni `app.models`.
- **Corruption fail-closed** : `catalog.xml`/`security.xml` corrompus → démarrage
  xml refusé (aucune régénération, aucun fallback).
- **Rollback réel** : snapshot/restore de `security.xml` ; SQLite historique
  intact après bascule retour.
- **Backup avant bascule** : copie + `.sha256` (contenu identique, digest cohérent).
- **Concurrence XML-only** : 8 registrations simultanées sans perte ni corruption
  (allocation d'id sous verrou).
- **Charge modérée** : 100 users, 30 bases (15 COMMON/15 PERSONAL), 14 grants,
  14 credentials TCP ; intégrité validée, comptages exacts.

## 18. Audit : rotation / compression / rétention (implémenté)

- `XmlControlPlaneService.audit_policy(retention_months, compress, now)` :
  compression gzip des mois anciens (`.xml` → `.xml.gz`), purge des mois
  au-delà de la rétention (`AUDIT_RETENTION_MONTHS=24`).
- **Le mois courant n'est jamais compressé ni supprimé** (testé).
- Lecture transparente des mois compressés (`list_audit`, `get_audit_entry`).
- Appliquée automatiquement à la **création d'un nouveau mois** (rotation), et
  disponible manuellement.
- Config : `AUDIT_RETENTION_MONTHS`, `AUDIT_COMPRESS_OLD_MONTHS` (documentées
  dans `.env.example`).

## 19. Sécurité fichiers

- `data/control/` en `0700`, fichiers en `0600` (POSIX).
- Aucun fichier CP exposé via Flask/static ; aucun `password_hash` ni credential
  en clair (bcrypt uniquement).

## 20–22. Persistance / Restart / Corruption

Voir §6–17. Redémarrage XML-only : données persistées, `internal_id`/UUID
stables. Corruption → démarrage refusé (validation XSD au démarrage étendue à
`history.xml`).

## 23. Checksum / expected_version

- `checksum` SHA-256 (détection d'altération, refus).
- `expected_version` : conflit → `ConflictError`, aucune écriture.

## 24. Concurrence

8 écritures concurrentes XML pur : sérialisées par verrous de fichier,
`internal_id` alloué **sous verrou** (correctif), aucune perte ni corruption.
Mono-processus (décision validée).

## 25. Rollback

Snapshots XML + restauration ; `CONTROL_BACKEND=sqlite` restaure immédiatement
l'historique. Aucun rollback automatique silencieux.

## 26. Performance (200 itérations, 40 users ; ms : min/max/moy/médiane/P95)

| Opération | SQLite | XML | Compare (avg) |
|---|---|---|---|
| get_user_by_email | .285/.857/.339/.335/.402 | 2.42/3.10/2.52/2.51/2.63 | 3.14 |
| get_user | .237/3.27/.295/.273/.345 | 2.44/2.90/2.54/2.53/2.64 | 3.14 |
| list_users | .652/3.70/.719/.697/.758 | 50.8/73.2/51.8/51.5/52.8 | 54.6 |
| list_roles | .145/.737/.167/.155/.209 | 1.21/1.81/1.27/1.27/1.34 | 1.61 |
| get_database | .156/1.34/.184/.169/.241 | .046/.263/.054/.048/.083 | 0.33 |
| list_database_permissions | .113/.888/.129/.117/.157 | .045/.244/.052/.047/.074 | 0.26 |
| resolve_database_access | .452/1.09/.514/.503/.592 | 1.28/1.91/1.34/1.33/1.39 | — |

XML relit/valide le fichier à chaque appel (cohérence prioritaire) : coût
linéaire sur `list_users` (~52 ms à 40 users). Documenté, non optimisé (pas de
cache global).

## 27. Charge modérée

100 users / 30 bases / 14 grants / 14 credentials : fonctionnel, persisté,
intégrité validée. Voir §6–17.

## 28–30. Tests sans SQLite / Divergences / Corrections

**Tests sans SQLite** : (a) backend XML importé et utilisé sans SQLAlchemy
(sous-processus) ; (b) mode XML avec tables SQLite CP **vides** (preuve que le
CP n'est plus adossé à SQLite).

**Divergences/corrections 6H** :
1. **Concurrence XML pur** : allocation `internal_id` hors verrou → perte de
   mises à jour. Corrigé : allocation dans le mutateur, sous verrou.
2. **Import indirect de SQLAlchemy** : `app/__init__.py`, `app/services/__init__.py`,
   `app/xml_engine/__init__.py` rendus légers (imports différés) → le backend
   XML s'importe sans `sqlalchemy`/`flask_sqlalchemy`/`app.models`.
3. **Rotation d'audit** manquante → implémentée (compression + rétention).
4. `Role` seedé en SQLite par la migration bootstrap (artefact, identique dans
   les deux backends) — documenté, pas une divergence.

**Divergences légitimes restantes** (BACKEND_SPECIFIC) : `tables_count`,
`table_permission.database_id`. Aucune divergence fonctionnelle restante.

## 31. Limitations

1. Le **pont Data Plane** (lignes ORM `Database/Table/Column/TableRow` +
   projection SQLite) exige encore SQLite au démarrage : un Flask **totalement**
   sans fichier SQLite ne sert pas encore le Data Plane. C'est précisément
   l'objet de 6I/6J. Le Control Plane, lui, est prouvé sans SQLite.
2. `list_users` XML ≈ 50 ms (validation par lecture) — optimisation différée.
3. `resolve_database_access` (primitive XML) non branchée dans
   `PermissionService` (logique unique portée par ce dernier, équivalence testée).
4. Purge/compression d'audit déclenchée à la rotation (nouveau mois) ; commande
   manuelle possible.

## 32. Risques

- Écriture XML par mutation Data Plane (miroir catalog.xml) : coût faible mais
  à surveiller sur gros volumes.
- Mono-processus confirmé.

## 33. Recommandation pour 6I

**PHASE_6H_READY_FOR_6I**

Preuves : 409/409 tests verts ; XML fonctionne comme source de vérité **et sans
SQLite pour le Control Plane** (tables CP SQLite vides en mode XML, backend XML
sans SQLAlchemy) ; auth/users/rôles/bases/permissions/COMMON/PERSONAL/TCP/REST/
history/audit validés en XML-only ; restart, corruption fail-closed, checksum,
expected_version, concurrence, rollback, charge modérée validés ; audit
rotation/compression/rétention opérationnels ; SQLite conservé et récupérable ;
compare fonctionnel ; aucune divergence fonctionnelle inexpliquée ; sécurité
fichiers vérifiée. Le **pont Data Plane** (dépendance SQLite résiduelle,
documentée) est l'objet de la Phase 6I.
