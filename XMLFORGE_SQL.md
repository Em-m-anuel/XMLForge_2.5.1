# XMLForge — Dialecte SQL

Sous-ensemble SQL exécuté par le moteur XML natif (REST et TCP). La matrice
ci-dessous reflète **uniquement ce qui est réellement implémenté et testé**.
Le code (parser + moteur) fait foi ; cette page le décrit sans promesse
supplémentaire.

| Fonction | Support | Notes |
|---|---|---|
| SELECT | ✅ | `*`, colonnes qualifiées `t.col`, alias `AS`, DISTINCT |
| WHERE | ✅ | `= != <> < <= > >=`, AND/OR/parenthèses |
| IS NULL / IS NOT NULL | ✅ | |
| IN / NOT IN | ✅ | |
| LIKE / NOT LIKE | ✅ | pattern `%`/`_` |
| BETWEEN | ✅ | |
| ORDER BY | ✅ | multi-colonnes, alias, agrégats |
| LIMIT / OFFSET | ✅ | pagination `{page, page_size, total, total_pages, current_page}` ; **LIMIT par défaut = 100** |
| COUNT / SUM / AVG / MIN / MAX | ✅ | |
| GROUP BY / HAVING | ✅ | |
| INNER JOIN … ON | ✅ | aliases, `table.col`, `col=col` |
| LEFT JOIN … ON | ✅ | **Phase 7** — lignes sans correspondance conservées (NULL) |
| RIGHT / FULL OUTER JOIN | ❌ | non supporté (erreur de syntaxe) |
| INSERT | ✅ | simple, multi-lignes atomique, `VALUES` implicite |
| UPDATE / DELETE | ✅ | `WHERE` obligatoire (refusé sinon) |
| CREATE TABLE | ✅ | PK **simple**, UNIQUE, NOT NULL, DEFAULT, AUTO_INCREMENT, FK **inline** (voir limites ci-dessous) |
| ALTER TABLE | ✅ | ADD/MODIFY/DROP COLUMN, RENAME TO |
| DROP TABLE | ✅ | refusé si référencé par une FK |
| CREATE [UNIQUE] INDEX / DROP INDEX | ✅ | simples et composites |
| CREATE DATABASE / DROP DATABASE | ✅ | `DROP DATABASE` = **Phase 7** ; `CREATE DATABASE` crée toujours une base `PERSONAL` |
| USE | ✅ | **Phase 7** — niveau session TCP |
| BEGIN / COMMIT / ROLLBACK | ✅ | **Phase 7** — transactions de session TCP (REST sans état) |
| COUNT(DISTINCT …), sous-requêtes, UNION | ❌ | non supportés (erreur de validation/syntaxe) |

## Limites de `CREATE TABLE`

- **Clé primaire** : uniquement sur une colonne (`id INT PRIMARY KEY`). La
  clause table-level `PRIMARY KEY (a, b)` (clé composite) **n'est pas
  supportée** par le parser SQL actuel.
- **Clé étrangère** : uniquement la forme inline
  `book_id INT REFERENCES books(id)` (ou `REFERENCES books.id`). La clause
  table-level `FOREIGN KEY (book_id) REFERENCES books(id)` **n'est pas
  supportée**.

## Types

`INT` `BIGINT` `SMALLINT` `TINYINT` `TEXT` `VARCHAR` `CHAR` `REAL` `FLOAT`
`DOUBLE` `DECIMAL` `NUMERIC` `BOOLEAN` `DATE` `DATETIME` `TIMESTAMP` `TIME`
`BLOB` `JSON`.

- `VARCHAR(n)` : longueur contrôlée ;
- `DATE` `YYYY-MM-DD`, `DATETIME` `YYYY-MM-DD HH:MM:SS`, `TIME` `HH:MM:SS` ;
- `DEFAULT` (y compris `CURRENT_TIMESTAMP`, évalué à l'insertion) ;
- `AUTO_INCREMENT` : compteur persistant (`next_auto_increment`), jamais réutilisé
  après `DELETE`.

## NULL

`NULL`, `""` et `"NULL"` sont trois valeurs distinctes. En XML :
`<cell null="true"/>`.

## Transactions

Voir `XMLFORGE_TRANSACTIONS.md` — transactions **de session TCP** (snapshot du
document XML + rollback), sans isolation multi-version.
