# XML Engine — moteur de données XML natif (expérimental, en parallèle de SQLite)

Ce document décrit l'évolution de XMLForge vers une architecture où **XML devient
progressivement le moteur de données principal**, **sans supprimer ni remplacer
SQLite pour le moment**.

> **État actuel** : SQLite (projection) reste le moteur utilisé par défaut par
> l'application. Le moteur XML natif est un chemin **parallèle, expérimental et
> testable**, sélectionnable par requête.

---

## 1. Architecture actuelle

```text
Navigateur
   |  HTTP REST + JWT (/api)
   v
Backend Flask (:5000)
   |
   +--> control plane SQLAlchemy (backend/xmlforge.db)
   |      utilisateurs, rôles, ACL, catalogue, audit, historique, credentials TCP
   |
   +--> XML canonique (source de vérité)  backend/data/xml/<id>_<slug>.xml
   |
   +--> projection SQLite (reconstruite depuis le XML)  backend/data/projections/<id>_<slug>.sqlite

Application externe
   |  TCP binaire JSON (:3307)
   v
TCPServer -> QueryService -> SELECT sur SQLite / écritures via XML + rebuild SQLite
```

Le moteur de requêtes partagé REST/TCP (`app/query/service.py` — `QueryService`)
lit les données dans la **projection SQLite** et applique les écritures au **XML**
puis reconstruit SQLite. C'est ce chemin qui reste le **défaut** et qui est
**inchangé**.

## 2. Architecture future (cible)

```text
Application / Frontend
        |
        v
     XMLForge
        |
        v
   Moteur XML natif
        |
        v
   Fichier XML
```

SQLite sera retiré **uniquement** dans une phase ultérieure, après validation du
moteur XML. D'ici là, les deux moteurs coexistent :

```text
    Application / Frontend
            |
            v
        XMLForge
         |       |
         v       v
      SQLite   XML (moteur natif)
      (actuel) (expérimental)
```

## 3. Rôles respectifs

| Composant | Rôle |
|---|---|
| **SQLite (projection)** | Moteur **actuel** : exécution SQL rapide sur une projection relationnelle reconstruite depuis le XML. |
| **XML canonique** | Source de vérité persistante : structure, données, contraintes, versions. |
| **XML Engine** (`xml_engine/xml_native.py`) | Nouveau moteur **indépendant** : lit/écrit directement le XML, valide les contraintes, sans SQLite ni SQLAlchemy. |
| **Query Parser** (`query/sql_parser.py`) | Convertit le SQL en AST (SELECT/INSERT/UPDATE/DELETE, WHERE, ORDER BY, LIMIT/OFFSET, COUNT). |
| **XML Executor** (`query/xml_executor.py`) | Exécute l'AST sur le moteur XML. |
| **XmlQueryService** (`query/xml_query_service.py`) | Intégration : autorisations + persistance via `XmlEngineService.mutate` (SQLite reste synchronisé). |
| **Comparator** (`query/comparator.py`) | Compare SQLite vs XML (résultat, lignes, erreurs, temps). |

## 4. Fonctionnement du Query Parser

`app/query/sql_parser.py` tokenise et produit un AST. Sous-ensemble **réellement
supporté** (commun aux deux moteurs) :

- `SELECT * FROM t` / `SELECT a, b FROM t` / `SELECT DISTINCT …` ;
- colonnes qualifiées `t.col` / `alias.col`, alias `AS` ;
- agrégats `COUNT(*)`, `COUNT(col)`, `SUM`, `AVG`, `MIN`, `MAX` ;
- `FROM t [alias]` + `INNER JOIN t2 [alias] ON …` ;
- `WHERE` avec `AND`, `OR`, parenthèses, `= != <> < <= > >=`, `LIKE`,
  `NOT LIKE`, `IN (...)`, `NOT IN (...)`, `BETWEEN a AND b`, `IS NULL`,
  `IS NOT NULL`, comparaisons colonne = colonne ;
- `GROUP BY col, …` et `HAVING` (fonctions d'agrégat ou alias) ;
- `ORDER BY col [ASC|DESC]` (multi-colonnes, colonnes ou agrégats) ;
- `LIMIT n OFFSET m` + métadonnées de pagination (page, page_size, total,
  total_pages, current_page) ;
- `INSERT INTO t (cols) VALUES (...), (...)` (multi-lignes, atomique) et
  `INSERT INTO t VALUES (...)` (colonnes implicites, ordre du schéma) ainsi que
  `INSERT INTO t VALUES ()` (tuple vide : tous les DEFAULT/AUTO_INCREMENT) ;
- `UPDATE t SET c = v, ... WHERE ...` (WHERE obligatoire) ;
- `DELETE FROM t WHERE ...` (WHERE obligatoire) ;
- DDL : `CREATE TABLE t (coldef, …)` (REFERENCES `table(col)` ou `table.col`),
  `DROP TABLE t`, `ALTER TABLE t ADD COLUMN`, `ALTER TABLE t MODIFY COLUMN`,
  `ALTER TABLE t DROP COLUMN`, `ALTER TABLE t RENAME TO` ;
- Index : `CREATE INDEX`, `CREATE UNIQUE INDEX` (simples et composites),
  `DROP INDEX` ;
- `CREATE DATABASE name` (crée une base PERSONAL possédée par l'appelant,
  via `DatabaseService`).

**Non supporté (refusé explicitement)** : `LEFT`/`RIGHT`/`OUTER JOIN`,
sous-requêtes, `UNION`, `COUNT(DISTINCT …)`, transactions.

## 4bis. Mode backend XML (Phase 4)

`QUERY_BACKEND` (`sqlite` | `xml` | `compare`) définit le moteur **principal**
quand le champ `engine` d'une requête est absent. `SYNC_SQLITE_PROJECTION`
(`true` | `false`) contrôle la reconstruction de la projection SQLite après
mutation :

- **MODE XML PUR** (`QUERY_BACKEND=xml` + `SYNC_SQLITE_PROJECTION=false`) :
  SELECT/INSERT/UPDATE/DELETE/DDL/index/pagination/introspection s'exécutent
  **uniquement** sur le XML (source de vérité). SQLite de données n'est plus
  nécessaire ; `engine=sqlite` échoue explicitement (`SQLITE_PROJECTION_ERROR`),
  jamais de bascule automatique.
- **MODE SQLITE** (défaut) : projection SQLite reconstruite et utilisée en
  lecture (legacy), écritures XML-first avec resynchronisation.
- **MODE COMPARE** : exécute les deux moteurs (nécessite la projection).

Détails : [XML_BACKEND_MODE.md](../XML_BACKEND_MODE.md) et
[SQLITE_DEPENDENCIES.md](../SQLITE_DEPENDENCIES.md).

## 5. Fonctionnement du TCP

`app/tcp/tcp_server.py` — le message `MSG_QUERY` accepte un champ optionnel
`engine` :

| Valeur | Comportement |
|---|---|
| `sqlite` (défaut) | `QueryService.execute_sql` — comportement historique, inchangé. |
| `xml` | `XmlQueryService.execute_sql` — lecture XML directe, écriture XML + resynchronisation SQLite. |
| `compare` | `QueryComparator.compare` — exécute et compare les deux moteurs. |

Le champ `QUERY_BACKEND` (config) définit le moteur **par défaut** lorsque
`engine` est omis. `XML_ENGINE_ENABLED` est un garde-fou documenté (activation
explicite du moteur XML en exploitation).

## 6. Fonctionnement du REST

`POST /api/databases/<id>/query` accepte le corps :

```json
{"sql": "SELECT * FROM books", "engine": "sqlite|xml|compare"}
```

- `engine` absent → moteur par défaut (`QUERY_BACKEND`, défaut `sqlite`).
- `engine=xml` → réponse `{"result": ..., "metrics": {...}}`.
- `engine=compare` → réponse `{"comparison": {...}}`.

`GET /api/databases/<id>/schema` → introspection du schéma **basée sur le XML** :

```json
{"database": "Bibliotheque", "tables": [{"name": "users",
  "columns": [{"name": "id", "type": "INT", "primary_key": true, "nullable": false,
               "auto_increment": true, "references": null, "default": null, ...}],
  "indexes": [{"name": "idx_email", "columns": ["email"], "unique": true}],
  "foreign_keys": [{"column": "category_id", "references": "categories.id", ...}],
  "primary_key": ["id"], "row_count": 120}]}
```

## 7. Structure du fichier XML (canonique)

```xml
<database name="bibliotheque" version="3" scope="PERSONAL" status="ACTIVE">
  <table name="books" protected="false" status="ACTIVE">
    <columns>
      <column name="id" type="INT" primary_key="true" auto_increment="true" nullable="false"/>
      <column name="author_id" type="INT" foreign_key="true" references="authors.id"
              on_delete="RESTRICT" on_update="NO ACTION"/>
    </columns>
    <rows>
      <row uuid="..."><cell column="id">1</cell><cell column="author_id">2</cell></row>
    </rows>
  </table>
</database>
```

Conventions : les valeurs de cellule sont stockées en **texte** (ou `null="true"`
pour NULL) ; le moteur XML les **coerce** (int/float/bool/str) selon le type de
colonne pour les comparaisons et le tri. Parseur/sérialiseur uniques :
`xml_engine/document.py` (validation XSD + `validate_document`).

## 8. Fonctionnement des contraintes (moteur XML)

Vérifiées **avant** écriture, sur l'état prospectif du document :

| Contrainte | Comportement |
|---|---|
| PRIMARY KEY (simple ou composite) | valeur non NULL + tuple unique ; levée `ConstraintViolation` sinon. |
| NOT NULL | refus d'une valeur NULL. |
| UNIQUE (colonne) | refus d'une valeur déjà présente. |
| UNIQUE INDEX (simple ou composite) | doublons refusés à l'INSERT/UPDATE **et** à la création de l'index ; NULL ne participe pas à l'unicité. |
| FOREIGN KEY | la valeur doit exister dans la table/colonne référencée (via index mémoire ou scan). |
| DEFAULT | appliqué à l'INSERT quand la colonne est absente, et **backfillé** dans les lignes existantes lors d'un `ADD COLUMN` avec défaut. |
| DEFAULT CURRENT_TIMESTAMP | évalué au moment de l'INSERT (pas à la création) ; format `YYYY-MM-DD HH:MM:SS` (UTC). |
| DEFAULT NULL | équivalent à l'absence de défaut (documenté). |
| AUTO_INCREMENT | compteur persistant `next_auto_increment` stocké dans le XML : **ne réutilise pas les IDs supprimés**, survit au redémarrage, gère l'insertion d'ID explicite. |
| ON DELETE / ON UPDATE | `NO ACTION`/`RESTRICT` → refus ; `CASCADE` → propagation ; `SET NULL` → mise à NULL (colonne nullable requise). `SET DEFAULT` → **non supporté** (levée explicite). |
| VARCHAR / CHAR (length) | longueur maximale vérifiée à l'INSERT/UPDATE/MODIFY. |
| DATE / DATETIME / TIME | format documenté validé en écriture : `YYYY-MM-DD`, `YYYY-MM-DD HH:MM:SS`, `HH:MM:SS`. |

Types invalides → `DataValidationError`. Colonne/table inexistante → `NotFoundError`/`ValidationFailed`.
NULL (`<cell null="true"/>`) est **distinct** de la chaîne vide et du texte
littéral « NULL ».

## 9. Fonctionnement des requêtes (moteur XML)

- Lecture : `parse_document` (validation) → filtrage (évaluation de l'AST WHERE
  sur valeurs coercées) → tri stable (NULLs premiers en ASC, derniers en DESC,
  comme SQLite) → `LIMIT/OFFSET`.
- **DISTINCT** : déduplication des lignes projetées (après projection).
- **Agrégats / GROUP BY / HAVING** : partition des lignes par clé de groupe,
  calcul des agrégats, évaluation de HAVING sur un environnement
  `{nom_canonique, alias}`, tri sur colonnes de sortie/alias/agrégats.
- **INNER JOIN … ON …** : boucle imbriquée, résolution des colonnes qualifiées
  par alias, refus des colonnes ambiguës.
- `LIKE` : insensible à la casse (ASCII), motifs `%` et `_`, pour rester aligné
  sur le comportement par défaut de SQLite.
- **Index mémoire** : index secondaire des colonnes `primary_key`/`unique`/
  `index`, reconstruit depuis le XML à la première requête, invalidé après
  mutation. Accélère les point-lookups d'égalité et les vérifications FK.
- Écriture : mutation du document en mémoire, puis persistance atomique
  (`xml_engine/storage.py`) avec **verrou de fichier** et contrôle de version
  (`expected_version`). Les DEFAULT sont matérialisés dans le XML à l'écriture
  (source de vérité complète).

## 10. Base XML de test

`backend/bibliotheque_engine_test.xml` — générée par
`backend/scripts/generate_engine_test_base.py` (déterministe, graine fixe).

| Table | Lignes | Contraintes remarquables |
|---|---|---|
| `authors` | 30 | PK auto, `name` UNIQUE, `birth_year`/`country` NULL, `deceased` BOOL default false |
| `categories` | 10 | PK auto, `name` UNIQUE |
| `users` | 120 | PK auto, `email` UNIQUE, `birth_date` DATE NULL, `active` BOOL default true |
| `books` | 400 | FK `author_id` (RESTRICT), FK `category_id` (SET NULL), `isbn` UNIQUE NULL, `price` REAL, `stock` INT default 0, `available` BOOL default true |
| `loans` | 300 | FK `book_id`/`user_id` (RESTRICT), `loan_date`/`return_date` DATE, `status` default 'active' |

Total : **860 lignes**. Données fictives (aucune donnée personnelle réelle).
Cas couverts : NULL, uniques, défauts, nombres, chaînes, dates, booléens,
recherche, tri, filtres, pagination, FK (RESTRICT/SET NULL).

## 11. Lancement des tests

```bash
# Backend (dépendances installées dans un venv)
cd backend
python -m venv .venv && .venv/bin/python -m pip install -r requirements.txt

# Moteur XML natif uniquement (aucun Flask/SQLite requis)
PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_xml_native_engine.py

# Intégration backend (équivalence SQLite/XML, REST engine, TCP engine)
PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_xml_engine_backend.py

# Suite complète (aucune régression attendue)
PYTHONPATH=. .venv/bin/python -m pytest -q tests/
```

## 12. Lancement du backend / frontend / tcp-tester

```bash
# Backend
cd backend
.venv/bin/python run.py                      # Flask :5000, TCP :3307

# Frontend
cd xmlforge-react
npm ci && npm run dev                        # Vite :5173

# TCP tester (outil d'étude des moteurs)
cd tcp-tester
npm install
cp .env.example .env                         # renseigner host/port/credentials TCP
npm start                                    # Express :3000
```

## 13. Procédure exacte : requête TCP vers le moteur XML

1. Importer la base de test (Dashboard → **Importer** → `backend/bibliotheque_engine_test.xml`),
   ou la créer via `POST /api/import/xml`.
2. Récupérer les credentials TCP : page **API & TCP/IP** → copier utilisateur +
   mot de passe TCP (affiché une seule fois).
3. Client Python :

```python
from app.tcp import XMLForgeClient
c = XMLForgeClient('127.0.0.1', 3307)
c.connect('user@example.com', 'TCP_PASSWORD', database='bibliotheque_engine_test')
print(c.execute("SELECT * FROM books WHERE category_id = 1 ORDER BY price DESC LIMIT 5", engine="xml"))
```

4. Via le **tcp-tester** : sélectionner le moteur **xml** dans le sélecteur,
   saisir la requête, cliquer **Exécuter**. Les métriques serveur
   (lecture/écriture XML, temps de traitement) s'affichent réellement.

## 14. Réalisation d'un benchmark

tcp-tester : saisir la requête (lecture seule), choisir le moteur, renseigner
**Runs**, cliquer **Benchmark** → min / max / moyenne / médiane + détail par run
(mesures réelles). La même opération est disponible par API :

```bash
curl -X POST http://localhost:3000/api/benchmark \
  -H 'Content-Type: application/json' \
  -d '{"query":"SELECT * FROM books WHERE category_id = 1","engine":"xml","runs":10}'
```

## 15. Comparaison SQLite / XML

tcp-tester : bouton **Comparer SQLite ↔ XML** (ou `engine=compare`). Le backend
exécute la requête sur les deux moteurs et retourne :

```json
{
  "equivalent": true|false,
  "sqlite": {"rows": N, "metrics": {"total_ms": ...}, "result": ...},
  "xml":    {"rows": N, "metrics": {"total_ms": ..., "read_ms": ..., "write_ms": ...}, "result": ...},
  "diff": null | {...}
}
```

La comparaison est **honnête** : si XML est plus lent, cela s'affiche ; si les
résultats diffèrent, `diff` permet de localiser le problème. Pour les écritures,
la requête n'est exécutée qu'une fois (via XML), puis l'état final est relu par
les deux moteurs et comparé.

## 16. Limites actuelles

- Le moteur XML **n'est pas** le moteur par défaut (SQLite reste le chemin standard).
- Pas de `LEFT/RIGHT/OUTER JOIN`, sous-requêtes, `UNION`, `COUNT(DISTINCT …)`.
- `ON DELETE`/`ON UPDATE` = `SET DEFAULT` non supporté par le moteur XML
  (levée explicite).
- La lecture XML charge et parse le document en mémoire ; l'index secondaire
  est **en mémoire** (reconstruit au démarrage, non persisté sur disque). C'est
  le coût principal face à SQLite sur de très gros volumes.
- Les index UNIQUE composites sont vérifiés à l'écriture ; les index non-uniques
  sont **logiques** (métadonnées + point-lookups en mémoire, pas d'optimisation
  de scan pour le tri/les range sur disque).
- Le benchmark est limité aux requêtes en **lecture seule** (une écriture
  répétée muterait l'état ; les benchmarks d'écriture du tcp-tester opèrent
  sur une table de travail temporaire).

## 17. Fonctionnalités réellement implémentées

- `XmlNativeEngine` : SELECT (`*`, colonnes qualifiées, alias, DISTINCT),
  WHERE complet (AND/OR/parenthèses/opérateurs/LIKE/NOT LIKE/IN/NOT IN/
  BETWEEN/IS NULL/IS NOT NULL/colonne=colonne), agrégats COUNT/SUM/AVG/MIN/MAX,
  GROUP BY, HAVING, INNER JOIN + ON, ORDER BY multi-colonnes
  (colonnes/alias/agrégats), LIMIT/OFFSET + métadonnées de pagination ;
  INSERT (simple, multi-lignes atomique, colonnes implicites, tuple vide),
  UPDATE, DELETE (WHERE obligatoire) ;
  DDL : CREATE DATABASE, CREATE TABLE (REFERENCES `table(col)`/`table.col`),
  DROP TABLE, ALTER TABLE ADD/MODIFY/DROP COLUMN, ALTER TABLE RENAME TO,
  CREATE INDEX / CREATE UNIQUE INDEX (simples et composites), DROP INDEX.
- Contraintes : PK (simple/composite), UNIQUE (colonne **et** index UNIQUE
  simple/composite), NOT NULL, FK (existence + RESTRICT/CASCADE/SET NULL),
  DEFAULT (matérialisé dans le XML, backfill au ADD COLUMN, CURRENT_TIMESTAMP
  évalué à l'INSERT), AUTO_INCREMENT à compteur persistant (pas de réutilisation
  d'IDs), validation des types et des longueurs VARCHAR, validation des formats
  DATE/DATETIME/TIME.
- NULL distinct de la chaîne vide et du texte « NULL ».
- Index mémoire (PK/UNIQUE/index + index de table simples/composites)
  reconstruit depuis le XML, invalidé après mutation — point-lookups + FK.
- Parseur SQL complet (agrégats, GROUP BY/HAVING, JOIN, alias, DDL, index).
- Rendu SQL (`sql_render.py`) pour la projection, alias de sortie identiques
  au moteur XML (comparaison exacte).
- `XmlQueryService` (autorisation table + jointures, métriques parse/exec/read/write).
- `QueryComparator` (équivalence + benchmark réel).
- Sélection du moteur par requête sur **REST** et **TCP** (`engine`).
- `expected_version` sur REST et TCP (409 / erreur structurée).
- **Introspection de schéma** : `GET /api/databases/<id>/schema` (basée sur le
  XML, pas sur SQLite) — tables, colonnes, PK/FK/UNIQUE/default/auto_increment,
  index, nombre de lignes.
- Base de test générée (860 lignes, 5 tables) + générateur déterministe.
- tcp-tester : requête (métriques réelles), comparaison, benchmark,
  **suite de benchmark par catégories** (lecture sur les deux moteurs, écriture
  sur table de travail temporaire).

## 18. Fonctionnalités encore expérimentales / non implémentées

- Index XML **persisté** sur disque (l'index actuel est en mémoire).
- `SET DEFAULT` pour les actions référentielles.
- `LEFT/RIGHT/OUTER JOIN`, sous-requêtes, `UNION`.
- Exécution multi-process/multi-fichiers (le verrou est par fichier).
- Retrait effectif de SQLite (phase ultérieure uniquement).

## 19. Procédure pour remplacer progressivement SQLite

1. Faire tourner le moteur XML en parallèle (`engine=xml` / `compare`) et
   contrôler `equivalent=true` sur des jeux de données réels.
2. Benchmarker les deux moteurs (tcp-tester) et documenter les écarts.
3. Basculer `QUERY_BACKEND=xml` sur un environnement de test, puis valider
   REST/TCP/UI de bout en bout.
4. Garder SQLite en projection « en lecture seule » (audit/reconciliation).
5. Désactiver la projection SQLite seulement après campagne de validation
   complète (régression, concurrence, volumes).

## 20. Fichiers

- `backend/app/xml_engine/xml_native.py` — moteur natif (cœur).
- `backend/app/xml_engine/document.py` — parseur/sérialiseur canonique (réutilisé).
- `backend/app/query/xml_executor.py` — AST → moteur XML.
- `backend/app/query/xml_query_service.py` — intégration backend.
- `backend/app/query/comparator.py` — comparaison/benchmark.
- `backend/app/query/service.py` — ajout de `QueryService.count` (SQLite).
- `backend/app/query/sql_parser.py` — ajout de `COUNT`/`AS`.
- `backend/app/tcp/tcp_server.py`, `tcp_protocol.py`, `xmlforge_client.py` — champ `engine`.
- `backend/app/routes/query.py` — champ `engine` REST.
- `backend/app/config.py` — `XML_ENGINE_ENABLED`, `QUERY_BACKEND`.
- `backend/bibliotheque_engine_test.xml` + `backend/scripts/generate_engine_test_base.py`.
- `backend/tests/test_xml_native_engine.py`, `backend/tests/test_xml_engine_backend.py`.
- `tcp-tester/` — outil d'étude réécrit.
