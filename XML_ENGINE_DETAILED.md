# XML Engine — documentation détaillée (fichier par fichier)

Documentation de conception du **moteur de données XML natif** de XMLForge.
Complète la [spécification technique globale](XMLFORGE_TECHNICAL_SPEC.md) et le
[guide du moteur](backend/XML_ENGINE.md).

---

## 1. Fichiers et responsabilités

### `backend/app/query/sql_parser.py` — Parser SQL

- **Rôle** : convertir une chaîne SQL en AST (arbre de dictionnaires).
- **Entrées** : chaîne SQL.
- **Sorties** : dict `{"operation": …, "table": …, "select_list": …,
  "where": …, "group_by": …, "having": …, "joins": …, "order_by": …}`.
- **Dépendances** : `app.errors.ValidationFailed` uniquement.
- **Particularités** :
  - tokenizer (espaces, nombres, chaînes, identifiants `` `quoted` ``,
    opérateurs, `*`, `,`, `(`, `)`, `;`, `.`) ;
  - mots-clés réservés (SELECT, FROM, JOIN, GROUP BY, HAVING, agrégats, DDL…) ;
  - colonnes qualifiées `table.col` / `alias.col` (profondeur max 2) ;
  - opérandes typées : `{"literal": v}` / `{"column": ref}` /
    `{"aggregate": {func, arg}}` (rétrocompatible avec l'ancien format
    chaîne/valeur nue) ;
  - refus explicites : `LEFT/RIGHT/OUTER JOIN`, `COUNT(DISTINCT …)`,
    `UPDATE`/`DELETE` sans `WHERE`.

### `backend/app/xml_engine/xml_native.py` — Moteur natif (cœur)

- **Rôle** : exécuter lecture, écriture, DDL et contraintes sur un document XML
  en mémoire (dict produit par `document.parse_document`).
- **Entrées** : document dict (ou chemin/fichier XML), requête/AST.
- **Sorties** : dicts de résultats (`{"rows": …, "total": …, "limit": …}`,
  `{"inserted": …}`, `{"updated": …}`, `{"deleted": …}`, `{"created": …}`).
- **Dépendances** : `xml_engine.document` (parse/serialize/validate),
  `xml_engine.storage` (verrou + écriture atomique). **Aucune** dépendance
  Flask/SQLAlchemy/SQLite.
- **Sous-composants** :
  - `Timing` : mesures réelles (parse, exec, read, write, total, rows) ;
  - `coerce_value` / `coerce_literal` : texte XML ↔ type natif ;
  - `XmlIndex` : index mémoire secondaire ;
  - `_eval_condition` : évaluateur WHERE/ON/HAVING (AND/OR, comparaisons,
    LIKE, IN, IS NULL, colonne=colonne, agrégats) ;
  - `select_statement` : SELECT complet (projection, DISTINCT, agrégats,
    GROUP BY, HAVING, JOIN, ORDER BY, LIMIT/OFFSET) ;
  - `_combine_rows` : produit cartésien filtré par ON (boucle imbriquée) ;
  - `_execute_aggregate` : partition par GROUP BY, calcul des agrégats,
    environnement HAVING/ORDER BY ;
  - `insert` / `insert_many` / `update` / `delete` : écritures avec validation ;
  - `_validate_row` : PK (simple/composite), UNIQUE, NOT NULL, FK, types ;
  - `_resolve_cascades` / `_propagate_reference_updates` : actions FK
    (`RESTRICT`/`NO ACTION`/`CASCADE`/`SET NULL`) ;
  - `create_table` / `add_column` / `drop_column` / `drop_table` : DDL.

### `backend/app/query/xml_executor.py` — Exécuteur

- **Rôle** : traduire l'AST du parser en appels du moteur natif.
- **Entrées** : moteur `XmlNativeEngine` (ou document) + SQL/AST.
- **Sorties** : résultats normalisés (y compris le cas spécial
  `SELECT COUNT(*) → {"count": N, "table": t}`).
- **Dépendances** : `sql_parser`, `xml_native`.

### `backend/app/query/xml_query_service.py` — Intégration backend

- **Rôle** : même contrat que `QueryService` (autorisations, protections,
  `expected_version`) avec le chemin XML.
- **Entrées** : `database_id`, `user_id`, SQL, `provided_key`, `expected_version`.
- **Sorties** : `{"result": …, "metrics": {parse_ms, exec_ms, read_ms,
  write_ms, total_ms, rows, engine}}`.
- **Dépendances** : SQLAlchemy (uniquement résolution/autorisation), le
  catalogue est resynchronisé par `XmlEngineService.mutate`.
- **Autorisation** : table de base **et** tables jointes (`_authorize_tables`).

### `backend/app/query/sql_render.py` — Rendu SQL (projection)

- **Rôle** : rendre l'AST en SQL réel exécuté sur la projection SQLite, avec
  alias de sortie identiques à ceux du moteur XML (clés comparables).
- **Particularités** : extension de `*` selon le schéma XML, validation des
  références de colonnes (mêmes erreurs que le moteur XML), citation des
  identifiants, échappement des littéraux.

### `backend/app/query/service.py` — Moteur SQLite (référence)

- **Rôle** : exécuter l'AST sur la projection SQLite (moteur historique,
  **défaut**).
- Ajouts récents : `count()`, `_compile_where_v2` (AST v2 pour UPDATE/DELETE),
  `_execute_rendered_select`, `_execute_ddl`, multi-INSERT, application des
  DEFAULT dans le XML à l'écriture.

### `backend/app/query/comparator.py` — Comparateur

- **Rôle** : exécuter la même requête sur SQLite et le moteur XML et comparer.
- **Sorties** : `{equivalent, sqlite: {rows, metrics, result}, xml: {…}, diff}`.
- **Écritures** : exécutées une seule fois (via XML) puis état final relu par
  les deux moteurs et comparé.
- **Benchmark** : N exécutions (lecture seule), min/max/moyenne/médiane réels.

### `backend/app/xml_engine/document.py` — Format canonique

Parseur/sérialiseur **uniques** du XMLForge : validation XSD
(`static/xmlforge.xsd`), normalisation (`<table>`/`<tables>` racine, `<column>`
directs), validation métier (`validate_document` : identifiants, types,
AUTO_INCREMENT sur PK entière, références FK existantes).

### `backend/app/xml_engine/service.py` — Orchestrateur transactionnel

`mutate(database_id, mutator, expected_version)` : verrou → lecture → contrôle
de version → copie profonde → mutateur → version + 1 → reconstruction de la
projection → synchronisation du catalogue → commit XML + SQLite. `read_document`
pour les lectures pures.

### `backend/app/xml_engine/projection.py` — Projection SQLite

Document → base SQLite : mapping de types, DDL (PK/UNIQUE/FK/index/DEFAULT),
insertion des lignes avec conversion de types, `PRAGMA foreign_key_check` /
`quick_check`, checkpoint WAL.

### `backend/app/xml_engine/storage.py` — Stockage

Verrous (`database_lock` : flock + thread RLock), écriture atomique
(`atomic_write` : temporaire + fsync + `os.replace`), snapshot/restore,
nettoyage WAL/SHM, retries Windows (`WinError 5`) et fallback
copie/suppression.

### `backend/app/tcp/tcp_server.py`, `tcp_protocol.py`, `xmlforge_client.py` — TCP

Serveur multi-client, sessions (timeout 30 min), authentification TCP (bcrypt),
dispatch `engine` (`sqlite`/`xml`/`compare`), protocole binaire JSON, client
Python avec `engine` optionnel.

### `tcp-tester/` — Banc d'essai

Express + interface web : configuration (host/port/credentials/base/moteur),
exécution de requête (métriques réelles), comparaison SQLite↔XML, benchmark
(1 requête, N runs), suite de benchmark par catégories (lecture sur les deux
moteurs, écriture sur table de travail temporaire).

---

## 2. Circuit d'une requête

```text
SQL
 ↓  parse_sql_statement()           [sql_parser]
AST
 ↓  QueryService.execute_sql        [sqlite]  -> render_select_sql -> projection
 │  XmlQueryService.execute_sql     [xml]     -> XmlNativeEngine.select_statement
 ↓  QueryComparator.compare         [compare] -> les deux + diff
Résultat
```

## 3. Circuit d'une mutation (INSERT)

```text
SQL
 ↓  parse_sql_statement()
AST
 ↓  autorisation (PermissionService.can_table + UnlockService.check_protection)
 ↓  XmlEngineService.mutate :
    1. verrou de base (flock + RLock)
    2. lecture + parse XML (validation XSD)
    3. contrôle expected_version (ConflictError si obsolète)
    4. copie profonde du document
    5. XmlNativeEngine.insert :
         - colonnes inconnues -> ValidationFailed
         - DEFAULT appliqué (colonne absente)
         - AUTO_INCREMENT calculé (max + 1)
         - _validate_row : PK (simple/composite) unique, UNIQUE, NOT NULL,
           FK (existence via index ou scan), types
         - ajout de la ligne (uuid)
    6. version + 1
    7. reconstruction de la projection SQLite (validation FK/quick_check)
    8. synchronisation du catalogue SQLAlchemy (TableRow)
    9. écriture atomique : XML puis projection (fsync + os.replace)
   10. commit (hash, sync_status=SYNCED)
Résultat {"inserted": 1, "row": …}
```

En cas d'échec à n'importe quelle étape : `db.session.rollback()` +
restauration du snapshot XML/SQLite — aucune écriture partielle.

## 4. Gestion des contraintes

| Contrainte | Où | Comportement |
|---|---|---|
| PRIMARY KEY (simple/composite) | `_validate_row` | tuple non NULL + unique, sinon `ConstraintViolation` |
| UNIQUE | `_validate_row` | doublon refusé |
| NOT NULL | `_validate_row` | NULL refusé |
| DEFAULT | `_compute_row_data` (XML) et `QueryService.insert` | valeur matérialisée dans le XML |
| AUTO_INCREMENT | `_compute_row_data` | max(existants)+1, réservé aux PK entières |
| FOREIGN KEY (existence) | `_check_foreign_key` | la valeur doit exister (index mémoire ou scan) |
| ON DELETE / ON UPDATE | `_resolve_cascades` / `_propagate_reference_updates` | `NO ACTION`/`RESTRICT` refus, `CASCADE` propagation, `SET NULL` mise à NULL |
| Types | `coerce_literal` / projection `convert_value` | valeur incompatible refusée |

## 5. JOIN (INNER JOIN … ON …)

- Le parser produit `from` (table + alias) et `joins` (table, alias, ON).
- Le moteur construit le schéma `{alias: {col: type}}` et combine les lignes
  par boucle imbriquée : pour chaque paire (gauche, droite), la condition ON
  est évaluée ; les paires valides sont fusionnées (clés `alias.col`).
- Les colonnes qualifiées (`b.title`) sont résolues via l'alias ; les colonnes
  nues ambiguës sont refusées (`Colonne ambiguë: id`).
- `SELECT *` sur un JOIN produit des clés qualifiées `alias.col` (le rendu
  SQLite applique la même convention via alias explicites).

## 6. Agrégations et GROUP BY / HAVING

- `_execute_aggregate` partitionne les lignes par les colonnes de GROUP BY
  (clé = tuple de valeurs), calcule chaque agrégat par groupe
  (`_aggregate_over_group`) et construit un environnement
  `{nom_canonique: valeur, alias: valeur}`.
- HAVING est évalué sur cet environnement (fonctions d'agrégat **ou** alias) ;
  ORDER BY peut référencer une colonne de sortie, un alias ou un agrégat.
- `COUNT(*)`/`COUNT(col)` seuls (sans GROUP BY) conservent la forme historique
  `{"count": N, "table": t}`.

## 7. Index mémoire

- `XmlIndex.maps[(table, col)] = {valeur_coercée: [rows…]}` pour les colonnes
  `primary_key` / `unique` / `index`.
- Construit **paresseusement** à la première requête qui en a besoin, à partir
  du document ; **invalidé** après chaque mutation.
- Utilisé pour : point-lookups d'égalité du WHERE (`=`, `IN`, intersections
  d'égalités via AND) et vérifications d'existence FK.
- Non persisté : reconstruit depuis le fichier XML au démarrage (comportement
  identique après redémarrage).

## 8. Concurrence et rollback

- Un seul écrivain par base (verrou de fichier) ; lectures hors verrou de
  mutation (lecture du fichier cohérent).
- `expected_version` vérifié sous verrou sur la version du disque.
- Échec → `db.session.rollback()` + restauration du snapshot (XML + SQLite).
- Le moteur natif autonome (`save`) vérifie aussi la version sur disque et
  refuse les commits obsolètes.

## 9. Erreurs

Hiérarchie : `XMLForgeError` → `ValidationFailed` / `XmlValidationError` /
`DataValidationError` / `ConstraintViolation` / `ConflictError` /
`NotFoundError` / `PermissionDenied` / `StorageError`. Codes stables, partagés
REST/TCP (voir spécification §13).

## 10. Dépendances entre composants

```text
sql_parser ──┐
             ├──> xml_executor ──> xml_native ──> document ──> xsd
             │                        │
sql_render ──┴────> service.py ───────┼──> projection ──> storage
      (sqlite)       (QueryService)   │
                                      └──> storage
xml_query_service ──> xml_native ──> service.mutate ──> projection ──> storage
comparator ──> service.py + xml_query_service
```
