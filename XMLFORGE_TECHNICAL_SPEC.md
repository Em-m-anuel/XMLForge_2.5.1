# XMLForge — Spécification technique globale

> Spécification du système réellement implémenté dans le dépôt. À jour au
> 2026-08-31. Aucun comportement décrit ici n'est « prévu » : tout est
> présent dans le code et couvert par des tests.

---

## 1. Vue d'ensemble

XMLForge est une application web (Flask + React) qui gère des bases de données
dont la **source de vérité est un document XML canonique**. Une projection
relationnelle **SQLite** est reconstruite depuis ce XML pour accélérer les
requêtes ; un **moteur XML natif** exécute désormais les mêmes requêtes
directement sur le XML, en parallèle de SQLite.

```text
Navigateur (React, Vite :5173)
   |  HTTP REST + JWT, préfixe /api
   v
Backend Flask (:5000)
   |      +-- control plane SQLAlchemy (xmlforge.db) : utilisateurs, rôles,
   |      |   ACL, catalogue, audit, historique, credentials TCP, unlocks
   |      |
   |      +-- XML canonique (source de vérité)   data/xml/<id>_<slug>.xml
   |      |
   |      +-- projection SQLite (reconstruite)   data/projections/<id>_<slug>.sqlite

Application externe
   |  TCP binaire JSON (:3307)
   v
TCPServer -> QueryService (sqlite) | XmlQueryService (xml) | QueryComparator (compare)
```

## 2. Composants

| Composant | Fichier(s) | Rôle |
|---|---|---|
| Parser SQL | `backend/app/query/sql_parser.py` | SQL → AST (SELECT/INSERT/UPDATE/DELETE/DDL) |
| Moteur SQLite | `backend/app/query/service.py` | exécute l'AST sur la projection SQLite (moteur historique, **défaut**) |
| Moteur XML natif | `backend/app/xml_engine/xml_native.py` | exécute les opérations directement sur le document XML |
| Exécuteur XML | `backend/app/query/xml_executor.py` | AST → appels du moteur XML |
| Service XML intégré | `backend/app/query/xml_query_service.py` | autorisations + persistance XML via `mutate` |
| Rendu SQL | `backend/app/query/sql_render.py` | AST → SQL (projection) avec alias/validation |
| Comparateur | `backend/app/query/comparator.py` | SQLite ↔ XML (équivalence + benchmark) |
| Parseur/sérialiseur XML | `backend/app/xml_engine/document.py` | format canonique, validation XSD + métier |
| Orchestrateur | `backend/app/xml_engine/service.py` | lecture, mutation atomique, rebuild SQLite, sync catalogue |
| Projection | `backend/app/xml_engine/projection.py` | document → base SQLite (types, contraintes, index) |
| Stockage | `backend/app/xml_engine/storage.py` | verrous, écriture atomique, snapshot/restore |
| Serveur TCP | `backend/app/tcp/tcp_server.py` | sessions, authentification, dispatch moteur |
| Client TCP | `backend/app/tcp/xmlforge_client.py` | client Python (`engine` optionnel) |
| tcp-tester | `tcp-tester/` | banc d'essai Express (requête, compare, benchmark) |

## 3. Flux de données

### Lecture (SELECT / agrégats / JOIN)

```text
SQL -> Parser -> AST -> [moteur sqlite]  projection SQLite
                      -> [moteur xml]    document XML (parse + filtrage + tri en mémoire)
                      -> [compare]       les deux + comparaison
```

### Écriture (INSERT / UPDATE / DELETE)

```text
SQL -> Parser -> AST -> autorisation (PermissionService + UnlockService)
    -> XmlEngineService.mutate :
         verrou base -> lecture XML -> vérif expected_version -> copie profonde
         -> mutation (validation contraintes) -> version + 1
         -> rebuild projection SQLite -> sync catalogue SQLAlchemy
         -> écriture atomique XML puis projection -> commit
    -> réponse
```

Le chemin d'écriture est **identique** pour `engine=sqlite` et `engine=xml` :
toute écriture passe par le XML (source de vérité) puis reconstruit SQLite.
Seule la **lecture** diffère (SQLite vs XML natif).

## 4. Modèle XML canonique

```xml
<database name="bibliotheque" version="3" scope="PERSONAL" status="ACTIVE" uuid="...">
  <table name="books" protected="false" status="ACTIVE" uuid="...">
    <columns>
      <column name="id" type="INT" primary_key="true" auto_increment="true" nullable="false"/>
      <column name="author_id" type="INT" foreign_key="true" references="authors.id"
              on_delete="RESTRICT" on_update="NO ACTION" unique="false" index="false"
              default="" length="-"/>
    </columns>
    <constraints>…</constraints>   <!-- optionnel : contraintes au niveau table -->
    <indexes>…</indexes>           <!-- optionnel : index composites -->
    <rows>
      <row uuid="..."><cell column="id">1</cell><cell column="author_id">2</cell></row>
    </rows>
  </table>
</database>
```

Attributs de colonne : `name`, `type`, `length`, `primary_key`, `foreign_key`,
`references` (`table.colonne`), `unique`, `nullable`, `auto_increment`,
`default`, `on_delete`, `on_update`, `index`, `comment`, `status`, `uuid`,
`internal_id`.

Conventions : les valeurs de cellule sont stockées en **texte** (ou
`null="true"` pour NULL) ; les moteurs les **coercent** (int/float/bool/str)
selon le type de colonne. Types autorisés : `INTEGER, INT, BIGINT, SMALLINT,
TINYINT, TEXT, VARCHAR, CHAR, CLOB, REAL, FLOAT, DOUBLE, DECIMAL, NUMERIC,
BOOLEAN, BOOL, DATE, DATETIME, TIMESTAMP, TIME, BLOB, JSON`.

## 5. SQL supporté (commun aux deux moteurs)

- **SELECT** `*` / colonnes (qualifiées `t.col` / `alias.col`) / alias `AS` /
  `DISTINCT` ;
- **agrégats** `COUNT(*)`, `COUNT(col)`, `SUM`, `AVG`, `MIN`, `MAX` ;
- **GROUP BY** (multi-colonnes) et **HAVING** (fonctions d'agrégat ou alias) ;
- **WHERE** avec `AND`, `OR`, parenthèses, `= != <> < <= > >=`, `LIKE`, `IN`,
  `IS NULL`, `IS NOT NULL` ; comparaisons colonne-colonne ;
- **ORDER BY** multi-colonnes, `ASC`/`DESC` (colonnes ou agrégats) ;
- **LIMIT / OFFSET** ;
- **INNER JOIN … ON …** (alias de table, colonnes qualifiées) ;
- **INSERT INTO t (cols) VALUES (...), (...)** (multi-lignes) ;
- **UPDATE t SET … WHERE …** (WHERE obligatoire) ;
- **DELETE FROM t WHERE …** (WHERE obligatoire) ;
- **DDL** : `CREATE TABLE t (coldef, …)`, `DROP TABLE t`,
  `ALTER TABLE t ADD COLUMN coldef`, `ALTER TABLE t DROP COLUMN col`.

**Refusé explicitement** : `LEFT/RIGHT/OUTER JOIN`, sous-requêtes, `UNION`,
`DISTINCT` dans les agrégats, transactions, `GROUP BY` sans agrégation de
sortie cohérente non documentée.

## 6. Moteur XML natif

- Lecture : parse + validation XSD, filtrage (évaluation d'AST WHERE sur
  valeurs coercées), tri stable (NULLs premiers en ASC, comme SQLite),
  pagination, agrégats, GROUP BY/HAVING, JOIN par boucle imbriquée.
- Écriture : validation des contraintes AVANT mutation (PK simple/composite,
  UNIQUE, NOT NULL, FK existence, DEFAULT, AUTO_INCREMENT, types), puis
  persistance atomique avec verrou + version optimiste.
- **Index mémoire** : index secondaire des colonnes `primary_key`/`unique`/
  `index`, reconstruit depuis le XML à la première utilisation, invalidé après
  chaque mutation. Accélère les point-lookups d'égalité (WHERE `=`, `IN`) et
  les vérifications FK. Non persisté sur disque (reconstruit au démarrage).

## 7. SQLite (projection)

Générée depuis le XML (`build_projection`) : types mappés
(`INTEGER` pour entiers/booléens, `REAL`, `NUMERIC`, `BLOB`, `TEXT`),
PK/UNIQUE/FK/index, lignes insérées avec conversion de types, validation
`PRAGMA foreign_key_check`/`quick_check`, checkpoint WAL. SQLite reste le
**moteur par défaut** et l'outil de **référence** pour la comparaison.

## 8. REST

Enveloppes :

```json
{"success": true, "message": "...", "data": ...}
{"success": false, "message": "...", "errors": {"code": "..."}}
```

`POST /api/databases/<id>/query` accepte :

```json
{"sql": "SELECT * FROM books", "engine": "sqlite|xml|compare",
 "expected_version": 3, "key_identifier": "..."}
```

- `engine` absent → `QUERY_BACKEND` (défaut `sqlite`) ;
- `engine=xml` → `{"result": …, "metrics": {parse_ms, exec_ms, read_ms, write_ms, total_ms, rows}}` ;
- `engine=compare` → `{"comparison": {equivalent, sqlite, xml, diff}}` ;
- `expected_version` obsolète → HTTP `409`, code `SYNC_CONFLICT`.

Les routes CRUD (bases/tables/colonnes/rows) passent par le XML via
`XmlEngineService.mutate` — identique quel que soit le moteur.

## 9. TCP/IP

Protocole : `[type:1 octet][longueur:4 octets BE][JSON UTF-8]`.

Messages : `AUTH(1)`, `QUERY(2)`, `RESPONSE(3)`, `ERROR(4)`, `PING(5)`,
`PONG(6)`, `SELECT_DATABASE(7)`, `UNLOCK_TABLE(8)`, `CLOSE(9)`.

`QUERY` accepte `engine` (`sqlite`/`xml`/`compare`), `expected_version`,
`table_key`. L'authentification utilise les credentials TCP (bcrypt), distincts
du mot de passe web. Les permissions sont réévaluées à chaque requête
(`PermissionService`) ; REST et TCP appliquent **les mêmes règles**.

## 10. Permissions

- Rôles globaux : `admin`, `user` (seuls rôles réels).
- Droits par base/table : `can_read`, `can_write`, `can_ddl`, `can_admin`.
- Niveaux affichés : `VIEW` (read), `EDIT` (write ou ddl), `MANAGE` (admin).
- `COMMON` = filtre de portée ; aucune visibilité automatique (partage explicite).
- `PERSONAL` peut être partagé (le backend ne l'interdit pas).
- Droits de table **additifs** (ne révoquent jamais un droit de base).
- Le moteur XML applique exactement les mêmes autorisations que SQLite
  (mêmes services `PermissionService`/`UnlockService`).

## 11. Versioning et concurrence

- Chaque document porte une `version` (entier, ≥ 1).
- Toute mutation accepte `expected_version` ; si la version courante diffère :
  `ConflictError` → REST `409`, TCP erreur structurée. Aucun écrasement
  silencieux.
- Verrou par base (`<xml>.lock`, flock + thread RLock), écriture atomique
  (fichier temporaire fsync + `os.replace`), snapshot/restore en cas d'échec.

## 12. Stockage

- XML : `backend/data/xml/<id>_<slug>.xml` (configurable `XML_STORAGE_FOLDER`).
- Projections : `backend/data/projections/<id>_<slug>.sqlite`
  (configurable `SQLITE_PROJECTION_FOLDER`).
- Control plane : `backend/xmlforge.db` (SQLAlchemy).
- Écritures atomiques compatibles Windows (retry `WinError 5`, fallback
  copie/suppression), cleanup WAL/SHM, libération des handles SQLite.

## 13. Erreurs

| Erreur | HTTP | Code |
|---|---|---|
| `ValidationFailed` | 400 | `VALIDATION_FAILED` |
| `XmlValidationError` | 400 | `XML_INVALID` |
| `DataValidationError` | 400 | `DATA_INVALID` |
| `ConstraintViolation` | 409 | `CONSTRAINT_VIOLATION` |
| `ConflictError` | 409 | `SYNC_CONFLICT` |
| `NotFoundError` | 404 | `NOT_FOUND` |
| `PermissionDenied` | 403 | `FORBIDDEN` |
| `StorageError` | 500 | `STORAGE_ERROR` |

## 14. Sécurité

- JWT signé + expiration, révocation au logout, `token_version` par utilisateur.
- bcrypt pour mots de passe web et TCP.
- Parseur XML durci (entités externes désactivées, `no_network`, taille limitée).
- SQL : identifiants cités, littéraux échappés (aucune injection dans le rendu).
- Socket.IO optionnel et désactivé par défaut (sans ACL/rooms).

## 15. Tests

```text
backend/tests/                         118 tests (moteur natif, intégration,
                                        comparaison, REST, TCP, concurrence,
                                        régression historique)
backend/bibliotheque_engine_test.xml   base de test (860 lignes, 5 tables)
backend/scripts/generate_engine_test_base.py  générateur reproductible
tcp-tester/                            banc d'essai + benchmark
```

## 16. Limites connues

- Lecture XML en mémoire (scan/parse du document) : sur très gros volumes,
  SQLite reste plus rapide — mesuré, pas masqué.
- Pas de `LEFT/RIGHT/OUTER JOIN`, sous-requêtes, `UNION`, transactions.
- `SET DEFAULT` pour les actions référentielles non supporté (levée explicite).
- Index XML en mémoire uniquement (reconstruit au démarrage).
- Socket.IO sans authentification/cloisonnement.
- `JOIN` limité à `INNER JOIN … ON …`.

---

Voir aussi : **[XML_ENGINE.md](backend/XML_ENGINE.md)** (guide du moteur) et
**[XML_ENGINE_DETAILED.md](XML_ENGINE_DETAILED.md)** (détail fichier par fichier).
