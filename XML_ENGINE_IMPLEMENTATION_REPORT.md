# XML Engine — Rapport final d'implémentation (étapes 1-13)

État au 2026-09-04. Le moteur XML natif couvre désormais **l'ensemble des
opérations relationnelles nécessaires à un usage normal de XMLForge** :
DDL complet, index, CRUD robuste, NULL, types/coercition, DEFAULT,
AUTO_INCREMENT sans réutilisation, intégrité référentielle, opérateurs de
recherche, pagination et introspection de schéma. SQLite est **conservé** comme
moteur par défaut, fallback, référence et outil de comparaison.

---

## 1. Fonctionnalités implémentées (étapes 1-13)

### Étape 1 — DDL complet
- `CREATE DATABASE name` (crée une base PERSONAL possédée par l'appelant, via `DatabaseService`) ;
- `CREATE TABLE` avec `REFERENCES table(col)` **et** `REFERENCES table.col`, `DEFAULT`, `UNIQUE`, `NOT NULL`, `AUTO_INCREMENT` ;
- `ALTER TABLE … ADD COLUMN` (avec backfill du DEFAULT), `MODIFY COLUMN` (type/longueur/nullable/défaut, validation des lignes existantes), `DROP COLUMN` (refus si référencé par FK), `RENAME TO` (mise à jour des références FK) ;
- `DROP TABLE` (refus si référencé).

### Étape 2 — Index XML
- `CREATE INDEX`, `CREATE UNIQUE INDEX` (simples et composites), `DROP INDEX [ON table]` ;
- représentation XML : `<indexes><index name="…" unique="…"><column name="…"/></index></indexes>` (schéma XSD existant) ;
- validation des colonnes, **doublons refusés** pour UNIQUE (à la création **et** à l'insertion/update) ;
- nettoyage des index à la suppression de colonne/table ;
- index **mémoire** (PK/UNIQUE/index + index de table) reconstruit depuis le XML, invalidé après mutation, utilisé pour les point-lookups et les FK (documenté : logique vs optimisation).

### Étape 3 — INSERT complet
- colonnes explicites, ordre arbitraire, multi-lignes **atomique**, colonnes implicites (`INSERT INTO t VALUES (...)`), tuple vide (`VALUES ()`), DEFAULT, NULL, AUTO_INCREMENT, validation types/PK/UNIQUE/NOT NULL/FK, longueur VARCHAR.

### Étapes 4-5 — UPDATE / DELETE robustes
- multi-colonnes, opérateurs WHERE complets ; `UPDATE`/`DELETE` sans WHERE **refusés** ;
- contraintes revalidées après mutation ; FK `RESTRICT`/`NO ACTION`/`CASCADE`/`SET NULL` ; atomicité.

### Étape 6 — NULL semantics
- NULL (`<cell null="true"/>`) **distinct** de la chaîne vide et du texte « NULL » ; `IS NULL` / `IS NOT NULL` ; NULL ne participe pas à l'unicité (PK/UNIQUE/index).

### Étape 7 — Types et coercition
- INT/BIGINT/…, DECIMAL/FLOAT/DOUBLE, BOOLEAN (`true/false/1/0/yes/no`), DATE (`YYYY-MM-DD`), DATETIME (`YYYY-MM-DD HH:MM:SS`), TIME (`HH:MM:SS`), VARCHAR/TEXT (longueur vérifiée) ; refus propre des valeurs incompatibles (aucune conversion silencieuse).

### Étape 8 — DEFAULT complet
- `DEFAULT 'value'` / `0` / `true` / `NULL` / `CURRENT_TIMESTAMP` (évalué à l'INSERT, pas à la création) ; cohérent pour INSERT et ADD COLUMN (backfill) ; `DEFAULT NULL` équivalent à l'absence de défaut (documenté).

### Étape 9 — AUTO_INCREMENT
- compteur **persistant** `next_auto_increment` stocké dans le XML : pas de réutilisation des IDs supprimés (`1,2,3 → delete 3 → 4`), insertion d'ID explicite (bump du compteur), table vide, redémarrage, concurrence (verrou + version).

### Étape 10 — Intégrité référentielle
- FK vérifiées à l'INSERT/UPDATE (existence) ; DELETE avec `RESTRICT`/`NO ACTION`/`CASCADE`/`SET NULL` ; `DROP TABLE`/`DROP COLUMN` refusés si référencés ; contraintes au niveau table (FK composites) exposées via l'introspection.

### Étape 11 — Opérateurs de recherche
- `BETWEEN a AND b`, `NOT IN (...)`, `NOT LIKE '…'` en plus de `= != <> < <= > >= LIKE IN AND OR IS NULL IS NOT NULL` ; précédence AND/OR respectée (parenthèses).

### Étape 12 — Pagination
- `LIMIT/OFFSET` + métadonnées `{page, page_size, total, total_pages, current_page}` sur REST et TCP ; le XML est chargé en mémoire (limitation documentée).

### Étape 13 — Introspection de schéma
- `GET /api/databases/<id>/schema` (et `/api/databases/<id>/schema`) : base, tables, colonnes (type, nullable, PK, FK, unique, défaut, auto_increment, longueur, index), index (simples/composites), clés étrangères, descriptions, nombre de lignes — **basée sur le XML**, pas sur SQLite.

## 2. Fichiers créés

| Fichier | Rôle |
|---|---|
| `backend/tests/test_xml_engine_final.py` | 59 tests (étapes 1-13 + cas négatifs + intégration REST/TCP/comparaison) |
| `backend/app/services/schema_service.py` | Introspection de schéma depuis le XML |
| `backend/XML_ENGINE_TESTING.md` | Guide de test complet (install, lancement, scénarios, résultats attendus) |

## 3. Fichiers modifiés

| Fichier | Modification |
|---|---|
| `backend/app/query/sql_parser.py` | CREATE DATABASE, CREATE/DROP INDEX (UNIQUE, composite), ALTER MODIFY/RENAME, REFERENCES table(col), BETWEEN/NOT IN/NOT LIKE, INSERT implicite + tuple vide, DEFAULT CURRENT_TIMESTAMP |
| `backend/app/xml_engine/xml_native.py` | create_index/drop_index/modify_column/rename_table, UNIQUE index appliqué, backfill DEFAULT, CURRENT_TIMESTAMP, AUTO_INCREMENT à compteur persistant, longueur VARCHAR, formats DATE/DATETIME/TIME, BETWEEN/NOT IN/NOT LIKE, pagination, index mémoire incluant les index de table, résolution INSERT implicite, update replace + matching indexé |
| `backend/app/xml_engine/document.py` | `next_auto_increment` (lecture + sérialisation) |
| `backend/app/static/xmlforge.xsd` + `backend/xmlforge.xsd` | attribut `next_auto_increment` (optionnel, rétrocompatible) |
| `backend/app/query/xml_executor.py` | dispatch DDL/index, résolution INSERT implicite |
| `backend/app/query/xml_query_service.py` | create_database, DDL/index, résolution INSERT implicite |
| `backend/app/query/service.py` | INSERT/UPDATE/DELETE **unifiés** via le moteur XML (atomicité multi-lignes, CASCADE/SET NULL dans le XML), DDL/index, create_database, pagination |
| `backend/app/query/sql_render.py` | rendu BETWEEN/NOT IN/NOT LIKE |
| `backend/app/routes/query.py` | endpoint `GET /databases/<id>/schema` |
| `backend/XML_ENGINE.md`, `backend/BACKEND_DOCUMENTATION.md` | documentation mise à jour |

## 4. Fonctionnalités déjà présentes réutilisées

- SELECT (DISTINCT, colonnes qualifiées, alias, agrégats COUNT/SUM/AVG/MIN/MAX, GROUP BY/HAVING, INNER JOIN, ORDER BY, LIMIT/OFFSET) ;
- contraintes PK (simple/composite), UNIQUE, NOT NULL, FK existence ;
- écriture atomique, verrou par base, `expected_version`, SHA-256, snapshot/rollback ;
- `engine=sqlite/xml/compare` (REST + TCP), comparateur, benchmark, tcp-tester ;
- base de test `bibliotheque_engine_test.xml` (860 lignes) + générateur ;
- permissions (`PermissionService`/`UnlockService`) appliquées identiquement sur les deux moteurs.

## 5. Tests

```text
backend/tests/ → 177 tests, 177 réussis, 0 échec (durée ~7 min 48 s) :
  - tests historiques                    14   (aucune régression)
  - test_xml_native_engine.py           49
  - test_xml_engine_sql_advanced.py     28
  - test_xml_engine_backend.py           8
  - test_xml_engine_comparison.py       19
  - test_xml_engine_final.py            59   (nouveau : étapes 1-13)
```

### Cas négatifs couverts (nouveaux)
PK dupliquée, UNIQUE dupliquée (colonne **et** index UNIQUE simple/composite), FK inexistante, suppression FK interdite (RESTRICT), NOT NULL violé, mauvais type, VARCHAR trop long, index sur colonne inexistante, DROP colonne référencée, UPDATE/DELETE sans WHERE, INSERT multi-lignes partiellement invalide (atomique), mauvais LIMIT/OFFSET (bornage), mauvaise syntaxe SQL, format DATE/DATETIME invalide, MODIFY COLUMN incompatible avec les données existantes.

## 6. Scénario end-to-end exécuté (conditions réelles)

Backend lancé (Flask :5000, TCP :3307), base de test importée (860 lignes) :

1. `CREATE TABLE reviews (...)` avec `REFERENCES books(id) ON DELETE CASCADE` ✓
2. `CREATE INDEX` / `CREATE UNIQUE INDEX` ✓
3. `INSERT` multi-lignes ✓
4. `SELECT ... BETWEEN ... ORDER BY` ✓
5. `SELECT ... NOT IN ...` ✓
6. `SELECT ... LIMIT/OFFSET` + pagination ✓
7. `UPDATE` / `DELETE` ✓
8. `ALTER TABLE ... MODIFY COLUMN` ✓
9. `ALTER TABLE ... RENAME TO` (+ mise à jour des FK) ✓
10. `DROP INDEX` ✓
11. `SELECT COUNT(*)` ✓
12. introspection : `GET /api/databases/1/schema` → tables, colonnes, index, FK, row_count ✓
13. XML réellement écrit : `<rows>`, `<column next_auto_increment>`, `<indexes>`, `version` ✓
14. comparaison `engine=compare` : `equivalent=true` ✓
15. **TCP** : CREATE TABLE/INDEX/INSERT multi/AUTO_INCREMENT (ids `[1,2,4]` sans réutilisation)/MODIFY/RENAME/DROP INDEX/DROP TABLE/BETWEEN/NOT LIKE/compare GROUP BY, UPDATE sans WHERE refusé, table inexistante refusée ✓

## 7. Exemple de XML généré

```xml
<database name="bibliotheque_engine_test" version="7" scope="PERSONAL" status="ACTIVE">
  <table name="reviews" status="ACTIVE" uuid="...">
    <columns>
      <column name="id" type="INT" primary_key="true" auto_increment="true"
              next_auto_increment="3" nullable="false" uuid="..."/>
      <column name="book_id" type="INT" foreign_key="true" references="books.id"
              on_delete="CASCADE" uuid="..."/>
      <column name="rating" type="INT" default="5" uuid="..."/>
    </columns>
    <indexes><index name="idx_reviews_id" unique="true"><column name="id"/></index></indexes>
    <rows>
      <row uuid="..."><cell column="id">1</cell><cell column="book_id">1</cell>
        <cell column="rating">5</cell></row>
    </rows>
  </table>
</database>
```

## 8. Exemples de requêtes SQL testées

```sql
CREATE TABLE users (id INT PRIMARY KEY AUTO_INCREMENT NOT NULL, name VARCHAR(150) NOT NULL, email VARCHAR(255) UNIQUE);
ALTER TABLE users ADD COLUMN age INT DEFAULT 18;
ALTER TABLE users MODIFY COLUMN name VARCHAR(200);
ALTER TABLE users RENAME TO customers;
CREATE UNIQUE INDEX idx_email ON customers (email);
INSERT INTO users (name, email) VALUES ('Alice','a@t.com'), ('Bob','b@t.com');
INSERT INTO users VALUES (3, 'Charlie', 'c@t.com');
SELECT * FROM users WHERE id BETWEEN 1 AND 3 ORDER BY name DESC LIMIT 20 OFFSET 0;
SELECT name FROM users WHERE id NOT IN (1,2) AND name NOT LIKE 'A%';
UPDATE users SET age = 31 WHERE id = 1;
DELETE FROM users WHERE id = 3;
DROP INDEX idx_email ON customers;
DROP TABLE customers;
```

## 9. Tests REST réalisés

`engine=xml` : DDL complet, index, BETWEEN/NOT IN/NOT LIKE, GROUP BY/HAVING,
JOIN, pagination, `CREATE DATABASE`, introspection `/schema`, `expected_version`
(409), permissions (403 VIEW→écriture, schema interdit sans partage).

## 10. Tests TCP réalisés

`engine=xml` : SELECT (WHERE/BETWEEN/NOT IN/NOT LIKE/ORDER BY/LIMIT/OFFSET),
INSERT (multi + implicite + tuple vide), UPDATE/DELETE (sans WHERE refusés),
CREATE TABLE, CREATE/DROP INDEX (UNIQUE), ALTER MODIFY/RENAME, DROP TABLE,
AUTO_INCREMENT sans réutilisation, erreurs structurées, `engine=compare`
(équivalence GROUP BY). Protocole existant compatible (champ `engine` optionnel).

## 11. Comparaison SQLite / XML

Toutes les requêtes de comparaison (SELECT, DISTINCT, GROUP BY, HAVING, JOIN,
alias, agrégats, BETWEEN/NOT IN/NOT LIKE) donnent **`equivalent=true`** :
mêmes lignes, mêmes valeurs, même ordre. Les écritures passent par le XML
(unique chemin) puis reconstruisent SQLite — l'état final est identique.

## 12. Limitations restantes

- Lecture XML en mémoire (scan + parse) : sur de très gros volumes, SQLite
  reste plus rapide en lecture.
- Index XML **en mémoire** (reconstruit au démarrage) ; les index non-uniques
  sont logiques + point-lookups, pas d'optimisation de tri/range sur disque.
- Pas de `LEFT/RIGHT/OUTER JOIN`, sous-requêtes, `UNION`, `COUNT(DISTINCT …)`, transactions multi-requêtes.
- `SET DEFAULT` référentiel non supporté (levée explicite).
- Le moteur par défaut reste SQLite (`QUERY_BACKEND=sqlite`).

## 13. Prochaines étapes recommandées

1. Basculer progressivement `QUERY_BACKEND=xml` sur un environnement de test
   et valider les parcours UI de bout en bout.
2. Persister l'index XML sur disque (accélérer les gros volumes).
3. Ajouter `LEFT JOIN` (et éventuellement sous-requêtes) si le besoin se confirme.
4. Campagne de charge (volumes > 100 k lignes) pour mesurer l'écart SQLite/XML
   et décider de la bascule définitive.
5. Supprimer SQLite **uniquement** après validation complète (phase ultérieure).

## 14. Commandes exactes pour reproduire les tests

```bash
cd backend
python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/generate_engine_test_base.py          # régénère la base de test
PYTHONPATH=. .venv/bin/python -m pytest -q tests/              # suite complète (177)
PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_xml_engine_final.py   # étapes 1-13
.venv/bin/python run.py                                        # Flask :5000, TCP :3307
```
