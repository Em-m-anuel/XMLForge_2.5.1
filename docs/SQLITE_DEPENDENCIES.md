> ⚠️ **DOCUMENT HISTORIQUE** — ne décrit pas l'architecture runtime actuelle (XML-only depuis la Phase 6J-B, SQLite/SQLAlchemy retirés). Conservé comme archive.

# SQLite — Audit des dépendances restantes (Phase 4)

Audit réalisé le 2026-09-05 sur le code réel du dépôt. Classification :

- **A. CRITIQUE** — SQLite est absolument nécessaire au fonctionnement.
- **B. TRANSITOIRE** — encore utilisé, remplaçable par XML.
- **C. COMPARAISON / TEST** — utilisé uniquement pour comparer ou benchmarker.
- **D. LEGACY / INUTILE** — encore référencé, ne devrait plus être nécessaire.

> Préambule : XMLForge utilise **deux** bases SQLite distinctes qu'il ne faut
> pas confondre :
> 1. le **control plane** (`backend/xmlforge.db`, via SQLAlchemy) : utilisateurs,
>    rôles, permissions, catalogue des bases/tables/colonnes/lignes, historique,
>    audit, déverrouillages, credentials TCP ;
> 2. la **projection de données** (`data/projections/<id>_<slug>.sqlite`, via
>    `sqlite3`) : reconstruction relationnelle du XML, utilisée par le moteur
>    SQLite (legacy) et par la comparaison.
>
> La Phase 4 rend la **projection de données** optionnelle
> (`SYNC_SQLITE_PROJECTION=false`). Le **control plane** SQLAlchemy reste, lui,
> hors périmètre de migration (authentification, permissions, catalogue).

## Tableau des dépendances

| Fichier | Fonction/classe | Dépendance | Pourquoi | Nécessaire après XML ? | Classe | Action future |
|---|---|---|---|---|---|---|
| `backend/app/__init__.py` | `create_app` : `db.create_all()`, migrations, `jwt` loader | SQLAlchemy (control plane) | gestion utilisateurs/rôles/JWT | OUI (auth) | **A** | migration ultérieure éventuelle |
| `backend/app/config.py` | `SQLALCHEMY_DATABASE_URI` (sqlite://), `SQLITE_PROJECTION_FOLDER` | SQLAlchemy + SQLite | control plane + projection | control plane OUI, projection NON (désactivable) | **A/B** | conserver control plane ; projection optionnelle |
| `backend/app/models/*.py` | modèles SQLAlchemy (User, Role, Permission, Database, Table, Column, TableRow, Audit, History, Unlock, TcpCredential…) | SQLAlchemy | métadonnées système | OUI (catalogue + auth) | **A** | hors périmètre XML (documenté) |
| `backend/app/extensions.py` | `db = SQLAlchemy()` | SQLAlchemy | ORM global | OUI | **A** | conserver |
| `backend/app/schema_migrations.py` | migrations du control plane | SQLAlchemy + SQL | schéma du control plane | OUI | **A** | conserver |
| `backend/app/services/permission_service.py` | `database_access`, `table_access`, `can_database`… | SQLAlchemy (modèles) | ACL utilisateurs/partages | OUI (permissions) | **A** | hors périmètre XML |
| `backend/app/services/auth_service.py`, `user_service.py`, `tcp_credential_service.py`, `unlock_service.py` | login, rôles, credentials TCP, unlocks | SQLAlchemy | auth/security | OUI | **A** | hors périmètre XML |
| `backend/app/services/audit_service.py`, `history_service.py` | journalisation | SQLAlchemy | audit/historique | OUI | **A** | hors périmètre XML |
| `backend/app/services/database_service.py`, `table_service.py`, `column_service.py` | CRUD structurel | SQLAlchemy (catalogue) + `XmlEngineService.mutate` | catalogue + XML | catalogue OUI, projection NON | **B** | déjà XML-first pour les données ; catalogue conservé |
| `backend/app/services/row_service.py` | `get_by_table`, CRUD lignes | projection SQLite (lecture) → **repli XML ajouté en Phase 4** | lecture des lignes | NON (repli XML opérationnel) | **B** | le repli XML est la voie principale en mode XML |
| `backend/app/services/export_service.py`, `sync_service.py`, `import_service.py`, `schema_service.py` | export/sync/import/schema | XML (source de vérité) ; projection pour l'export SQL | export SQL table | export XML/schema : NON ; export SQL : OUI (lit le XML via convertisseur, pas la projection) | **C/D** | déjà XML |
| `backend/app/query/service.py` | `QueryService.select/count/_execute_rendered_select` | projection SQLite (`connect_projection`) | moteur legacy + comparaison | NON (mode XML) — erreur explicite si projection absente | **B** | supprimer après bascule |
| `backend/app/query/sqlite_runtime.py` | `connect_projection`, retries | `sqlite3` | moteur legacy | NON | **D** | supprimer après bascule |
| `backend/app/query/comparator.py` | `compare`, `benchmark` | SQLite (projection) + XML | comparaison | OUI tant que comparaison demandée | **C** | conserver comme outil |
| `backend/app/xml_engine/projection.py` | `build_projection` | `sqlite3` | reconstruction projection | NON (désactivable via `SYNC_SQLITE_PROJECTION`) | **B** | conserver pour legacy/comparaison |
| `backend/app/xml_engine/service.py` | `mutate`, `ensure_storage`, `initialize_all` | `build_projection` (SQLite) + catalogue SQLAlchemy | écriture XML + projection | projection NON (désactivable) ; catalogue OUI | **B** | bascule effectuée en Phase 4 |
| `backend/app/xml_engine/storage.py` | `commit_pair`, `snapshot/restore`, `cleanup_sqlite_sidecars` | SQLite sidecars (`-wal`/`-shm`) | atomicité XML+SQLite | NON en mode XML (écriture XML atomique seule) | **B** | conserver pour legacy |
| `backend/app/xml_engine/xml_native.py` | moteur XML natif | **aucune** (document XML dict) | moteur cible | NON | — | moteur principal |
| `backend/app/routes/tcp.py`, `tcp/tcp_server.py` | gestion credentials/sessions TCP | SQLAlchemy (auth TCP) | authentification TCP | OUI (auth) | **A** | hors périmètre XML |
| `backend/tests/test_windows_storage.py`, `test_xml_projection.py`, `test_rest_xml_sqlite_e2e.py`, `test_concurrency_robustness_e2e.py`, `test_xml_engine_comparison.py` | tests projection/concurrence/comparaison | SQLite | couverture legacy/comparaison | OUI (tests) | **C** | conserver |
| `backend/tests/test_xml_backend_mode.py` | tests mode XML | projection **absente** (vérifie l'absence) | prouve l'indépendance XML | NON | **C** | conserver |
| `tcp-tester/` | banc d'essai | TCP (aucune dépendance SQLite directe) | démonstration | NON | — | outil |

## Synthèse

- **Dépendances CRITIQUES (A)** restantes : le **control plane SQLAlchemy**
  (utilisateurs, rôles, permissions, catalogue, audit, historique, unlocks,
  credentials TCP). C'est **ce qui bloque aujourd'hui la suppression de SQLite** :
  l'authentification et les permissions ne sont **pas** migrées vers XML.
- **Dépendances TRANSITOIRES (B)** : la projection SQLite de données est
  désormais **optionnelle** (`SYNC_SQLITE_PROJECTION=false`). En mode XML pur,
  elle n'est plus construite ni lue.
- **Dépendances COMPARAISON (C)** : le comparateur et les benchmarks utilisent
  SQLite comme référence — à conserver tant que la transition dure.
- **Dépendances LEGACY (D)** : `sqlite_runtime.py`, `QueryService` (chemin
  SQLite) — à supprimer **uniquement** après validation complète du mode XML.

## Conclusion pour la suppression définitive de SQLite

La suppression de la **projection SQLite de données** est déjà techniquement
possible (mode XML pur validé). La suppression **totale** de SQLite exigerait
au préalable de migrer le **control plane** (auth, rôles, ACL, catalogue,
audit, historique) vers le XML — travail hors du périmètre de la Phase 4,
documenté comme dépendance résiduelle **critique**.
