# PHASE 6 — Control Plane XML : Implémentation

**Projet** : XMLForge
**Date** : 2026-09-06
**Rapport de référence** : `PHASE_5_CONTROL_PLANE_XML_AUDIT.md` · Analyse préalable : `PHASE_6_ANALYSE_PREALABLE.md`

> Ce document ne décrit que ce qui a **réellement été implémenté**. Les phases non commencées sont marquées « à venir ».

---

## État d'avancement

| Sous-phase | Statut |
|------------|--------|
| 6A — Infrastructure Control Plane XML | ✅ Terminée |
| 6B — Modèles XML + XSD | ✅ Terminée |
| 6C — Export SQLite → XML | ✅ Terminée |
| 6D — XmlControlPlaneService | ✅ Terminée |
| 6E — Migration progressive (adaptateur sqlite/xml/compare) | ✅ Terminée |
| 6F — Convergence SQLite ↔ XML (COMMON, common_permission) | ✅ Terminée |
| 6G — Validation prolongée (comparaison intensive, 0 divergence) | ✅ Terminée |
| 6H — Basculement contrôlé (XML source de vérité, audit rotatif) | ✅ Terminée |
| 6I — Data Plane XML sans SQLite (DATA_BACKEND=xml) | ✅ Terminée |
| 6J — Finalisation XML (6J-A) | ✅ Terminée |
| 6J-B — Retrait définitif de SQLite/SQLAlchemy | ✅ Terminée (XML-only) |
| 6K — Stabilisation, optimisation et validation produit | ✅ Terminée (stable) |
| 6G — Audit + History | ⏳ à venir |
| 6H — TCP credentials | ⏳ à venir |
| 6I — Double-write + Compare | ⏳ à venir |
| 6J — XML source de vérité | ⏳ à venir |
| 6K — Tests sans Control Plane SQLite | ⏳ à venir |
| 6L — Suppression des dépendances SQLite du CP | ⏳ à venir |

---

## 1. Phase 6A — Infrastructure (implémentée)

### 1.1 Nouveaux paramètres de configuration (`app/config.py`)

| Paramètre | Valeur par défaut | Valeurs autorisées | Rôle |
|---|---|---|---|
| `CONTROL_BACKEND` | `sqlite` | `sqlite` · `xml` · `compare` | backend du plan de contrôle |
| `CONTROL_STORAGE_FOLDER` | `backend/data/control/` | chemin | dossier privé des fichiers CP XML |
| `AUDIT_RETENTION_MONTHS` | `24` | entier ≥ 1 | rétention de l'audit rotatif |
| `COMMON_PERMISSION_DEFAULT` | `VIEW` | `VIEW` · `EDIT` · `MANAGE` | accès collectif par défaut d'une base COMMON |

Validation **au démarrage** via `Config.validate()` : une valeur inconnue de
`CONTROL_BACKEND` (ou de `COMMON_PERMISSION_DEFAULT`, ou une rétention < 1)
provoque une `RuntimeError` explicite. `ProductionConfig.validate()` appelle
désormais `super().validate()` avant son propre contrôle des secrets.

> **Important** : le Control Plane XML reste **INACTIF** tant que
> `CONTROL_BACKEND=xml` (ou `compare`) n'est pas explicitement activé. En 6A,
> seule l'infrastructure existe ; **aucun service métier n'a été touché** :
> Auth/Users/Permissions/Audit/History/TCP continuent d'utiliser SQLite.

### 1.2 Package `app/xml_control/store.py`

Couche unique de gestion des fichiers du Control Plane XML. API fournie :

| Fonction | Rôle |
|---|---|
| `ensure_dir(path, mode=0o700)` | création du dossier privé (0700 sur POSIX, no-op Windows) |
| `read(path)` | octets bruts ; **fail-closed** si absent |
| `read_validated(path, schema=None)` | parse XXE-safe + validation XSD optionnelle ; retourne la racine `etree` |
| `write(path, content, chmod_mode=0o600)` | écriture atomique + restriction des droits |
| `mutate(path, mutator, expected_version=None, schema=None)` | mutation versionnée, verrouillée, atomique |
| `get_version(path)` | lecture de l'attribut racine `version` |
| `checksum(path)` / `checksum_bytes(data)` / `verify_checksum(path, expected)` | SHA-256 |
| `snapshot(path)` / `restore(path, snap)` | instantané/restauration mono-fichier |
| `parse_safely(bytes)` / `validate_bytes(bytes, schema)` / `cached_schema(xsd_path)` | parsing/validation |

### 1.3 Mécanismes réutilisés (aucune duplication)

- `atomic_write`, `database_lock`, `safe_unlink` — réutilisés tels quels depuis `app/xml_engine/storage.py` (tempfile + `fsync` + `os.replace`, fallback Windows, `fcntl.flock` + `threading.RLock`).
- Parsing XXE-safe identique au Data Plane : `resolve_entities=False`, `no_network=True`, `huge_tree=False`.
- Erreurs existantes : `StorageError`, `XmlValidationError`, `ConflictError` (409, `SYNC_CONFLICT` pour `expected_version`).

### 1.4 Séquence d'une mutation (`mutate`)

1. verrou (`<fichier>.lock`) ;
2. lecture + parse (fichier absent → `StorageError`, **aucune régénération silencieuse**) ;
3. vérification `expected_version` (mismatch → `ConflictError`) ;
4. application du mutateur sur une **copie profonde** de la racine ;
5. incrément de `version` ;
6. validation XSD **avant** écriture (si schéma fourni) ;
7. `atomic_write` + `chmod 0600` ;
8. libération du verrou.

### 1.5 Sécurité du stockage

- `backend/data/control/` créé automatiquement au démarrage (`create_app`) en `0700` sur POSIX ;
- fichiers sensibles écrits en `0600` ;
- le dossier **n'est jamais servi** par Flask/statique (hors `static/`, hors `uploads/`, hors `exports/`) ;
- **fail-closed** : absence ou corruption = erreur explicite, jamais de régénération automatique de `security.xml`/`catalog.xml`.

### 1.6 Compatibilité Windows

Aucune dépendance Linux-only introduite : `atomic_write`/`database_lock`/
`safe_unlink` intègrent déjà le fallback Windows ; `os.chmod` est appliqué
uniquement sur POSIX (`os.name == "posix"`). Tests exécutés sous Linux
(environnement actuel) ; la compatibilité Windows repose sur les primitives
existantes (couvertes par `tests/test_windows_storage.py`).

---

## 2. Tests 6A

Fichier : `tests/test_xml_control_plane.py` — **29 tests** :

- configuration : défaut `sqlite`, valeurs valides, valeur invalide (`RuntimeError`), `COMMON_PERMISSION_DEFAULT` invalide, rétention invalide, rejet par `create_app`, création du dossier ;
- répertoire : création d'arborescence, permissions 0700 (POSIX) ;
- écriture/lecture : round-trip, **absence de fichier temporaire résiduel**, `read`/`read_validated`/`mutate` sur fichier absent (fail-closed), aucune régénération silencieuse ;
- checksum : cohérence + détection de divergence ;
- version : `get_version`, incrément, `expected_version` OK, **conflit refusé**, mutateur qui lève = rien d'écrit ;
- validation : XSD valide, contenu invalide, XML corrompu, validation **avant** écriture (échec = fichier intact) ;
- snapshot/restore : round-trip, restauration d'un état absent ;
- verrou : 8 mutations concurrentes sérialisées (version finale exacte), verrou libéré après mutation.

---

## 2 bis. Phase 6B — Modèles XML + XSD (implémentée)

- `app/xml_control/records.py` : `SecurityDocument`, `CatalogDocument`,
  `HistoryDocument`, `AuditDocument` + records (dataclasses) + enums
  `Scope`/`CommonPermission` ; sérialisation/désérialisation + validation XSD.
- `app/static/control/security.xsd`, `catalog.xsd`, `history.xsd`, `audit.xsd`
  (unicité, keyref internes, enums, formats). Détail : `XML_CONTROL_PLANE.md`.
- Tests : `tests/test_xml_control_models.py` (50).

## 2 ter. Phase 6C — Export SQLite → XML (implémentée)

- `app/xml_control/exporter.py` : export déterministe (`roles`, `users`,
  `tcp_credentials`, `databases`, `database_permissions`, `table_permissions`,
  `history`, `audit_logs`) — jamais `tables`/`columns`/`table_rows`. Backup
  `xmlforge.db` (copie + SHA-256), snapshot/rollback XML, backfill UUIDv5
  déterministe, vérification des comptages par relecture.
- CLI : `scripts/export_control_plane.py`.
- Tests : `tests/test_xml_control_plane_migration.py` (12).

---

## 3. Démarrage / restauration (6A)

**Procédure de démarrage** : inchangée — `python run.py`. Le backend prépare
`data/control/` mais continue d'utiliser SQLite pour le plan de contrôle tant
que `CONTROL_BACKEND` n'est pas basculé.

**Restauration** : sans objet en 6A (aucune donnée CP écrite en XML).

---

## 4. Dépendances SQLite (état après 6A)

**Inchangées.** Le plan de contrôle (14 tables SQLAlchemy) et la projection de
données restent exactement comme avant. `CONTROL_BACKEND=sqlite` est le défaut ;
le chemin `xml`/`compare` n'est pas encore câblé dans les services.

---

## 5. Prochaine étape

**Phase 6B** — Modèles XML (`records.py`) + XSD (`security.xsd`, `catalog.xsd`,
`history.xsd`, `audit.xsd`) + validation, sur la base de `store.py`.
