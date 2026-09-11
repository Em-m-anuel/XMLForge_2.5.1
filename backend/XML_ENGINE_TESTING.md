# XML Engine — Guide de test complet

Procédure exacte pour tester le moteur XML natif de XMLForge en conditions
réelles (REST + TCP + comparaison SQLite/XML + vérification du fichier XML).

---

## 1. Installation

```bash
# Backend (venv Python)
cd backend
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

# Frontend (optionnel)
cd ../xmlforge-react
npm ci

# tcp-tester (banc d'essai)
cd ../tcp-tester
npm install
cp .env.example .env      # renseigner TCP_HOST/PORT/USERNAME/PASSWORD
```

## 2. Lancement

```bash
# Backend (Flask :5000, TCP :3307)
cd backend
.venv/bin/python run.py

# Administrateur (une fois)
printf 'admin@test.dev\nAdmin\nadmin123\nadmin123\n' | .venv/bin/flask --app run.py create-admin

# Frontend (optionnel, Vite :5173)
cd ../xmlforge-react
npm run dev

# tcp-tester (Express :3000)
cd ../tcp-tester
npm start
```

## 3. Création / import d'une base

```bash
# Import de la base de test (860 lignes, 5 tables)
curl -X POST http://127.0.0.1:5000/api/import/xml \
  -H "Authorization: Bearer $JWT" \
  -F "file=@backend/bibliotheque_engine_test.xml"
```

Ou, via SQL :

```text
CREATE DATABASE ma_base;   -- crée une base PERSONAL (propriétaire = appelant)
```

## 4. Login (REST)

```bash
JWT=$(curl -s -X POST http://127.0.0.1:5000/api/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@test.dev","password":"admin123"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['access_token'])")
```

## 5. Création de tables (DDL)

```sql
CREATE TABLE users (
  id INT PRIMARY KEY AUTO_INCREMENT NOT NULL,
  name VARCHAR(150) NOT NULL,
  email VARCHAR(255) UNIQUE
);

CREATE TABLE categories (
  id INT PRIMARY KEY AUTO_INCREMENT NOT NULL,
  name VARCHAR(100) UNIQUE NOT NULL
);

CREATE TABLE books (
  id INT PRIMARY KEY AUTO_INCREMENT NOT NULL,
  title VARCHAR(200) NOT NULL,
  category_id INT REFERENCES categories(id) ON DELETE SET NULL,
  price DECIMAL DEFAULT 0.00
);
```

## 6. INSERT

```sql
INSERT INTO users (name, email) VALUES ('Alice', 'alice@test.com');
INSERT INTO users (name, email) VALUES
  ('Bob', 'bob@test.com'),
  ('Charlie', 'charlie@test.com');      -- multi-lignes atomique
INSERT INTO users VALUES (4, 'Dave', 'dave@test.com');  -- colonnes implicites
INSERT INTO users (name, email) VALUES (NULL, 'x@test.com');  -- refusé (NOT NULL)
INSERT INTO users (name, email) VALUES ('Eve', 'alice@test.com');  -- refusé (UNIQUE)
```

## 7. SELECT

```sql
SELECT * FROM users;
SELECT name, email FROM users WHERE id = 1;
SELECT * FROM users WHERE name LIKE 'A%';
SELECT * FROM users WHERE id NOT IN (1, 2);
SELECT * FROM users WHERE name NOT LIKE 'A%';
SELECT * FROM books WHERE price BETWEEN 10 AND 50;
SELECT * FROM users WHERE email IS NULL;
SELECT * FROM users WHERE email IS NOT NULL;
SELECT COUNT(*) FROM users;
SELECT category_id, COUNT(*) AS n FROM books GROUP BY category_id HAVING COUNT(*) > 5;
SELECT b.title, c.name FROM books b JOIN categories c ON b.category_id = c.id;
SELECT * FROM users ORDER BY name DESC LIMIT 20 OFFSET 40;   -- pagination
```

## 8. UPDATE / DELETE

```sql
UPDATE users SET name = 'Alice2', age = 25 WHERE id = 1;
UPDATE users SET price = 1;            -- refusé (WHERE obligatoire)
DELETE FROM users WHERE id = 10;
DELETE FROM users;                     -- refusé (WHERE obligatoire)
```

## 9. DDL avancé

```sql
ALTER TABLE users ADD COLUMN age INT DEFAULT 18;
ALTER TABLE users MODIFY COLUMN name VARCHAR(200);
ALTER TABLE users DROP COLUMN age;
ALTER TABLE users RENAME TO customers;
CREATE INDEX idx_books_price ON books (price);
CREATE UNIQUE INDEX idx_books_title ON books (title);
DROP INDEX idx_books_price ON books;
DROP TABLE customers;
```

## 10. Index

- `CREATE INDEX` / `CREATE UNIQUE INDEX` / `DROP INDEX` (simples et composites) ;
- l'index est **logique** (stocké dans `<indexes>` du XML) et alimente un index
  mémoire pour les point-lookups ; les index UNIQUE sont réellement appliqués
  (doublons refusés à l'insertion et à la création de l'index).

## 11. Clés étrangères

```sql
DELETE FROM categories WHERE id = 1;    -- SET NULL : books.category_id -> NULL
DELETE FROM categories WHERE id = 2;    -- RESTRICT : refusé si référencé
DROP TABLE categories;                  -- refusé si encore référencé
ALTER TABLE categories DROP COLUMN id;  -- refusé (colonne référencée)
```

## 12. Pagination

`LIMIT/OFFSET` + métadonnées retournées :

```json
{"rows": [...], "total": 100, "pagination":
  {"page": 3, "page_size": 20, "total": 100, "total_pages": 5, "current_page": 3}}
```

## 13. Introspection

```bash
curl -s http://127.0.0.1:5000/api/databases/<DB_ID>/schema -H "Authorization: Bearer $JWT"
```

## 14. TCP

```python
from app.tcp import XMLForgeClient
c = XMLForgeClient('127.0.0.1', 3307)
c.connect('admin@test.dev', 'TCP_PASSWORD', database='bibliotheque_engine_test')

c.execute("SELECT * FROM books WHERE price BETWEEN 10 AND 50", engine="xml")
c.execute("INSERT INTO users (name, email) VALUES ('X', 'x@test.com')", engine="xml")
c.execute("CREATE INDEX idx ON books (price)", engine="xml")
c.execute("SELECT category_id, COUNT(*) AS n FROM books GROUP BY category_id", engine="compare")
```

Le protocole TCP existant reste compatible : le champ `engine` est optionnel
(défaut `sqlite`).

## 15. Comparaison SQLite / XML

```bash
curl -s -X POST http://127.0.0.1:5000/api/databases/<DB_ID>/query \
  -H "Authorization: Bearer $JWT" -H 'Content-Type: application/json' \
  -d '{"sql": "SELECT * FROM books WHERE price > 10 ORDER BY price", "engine": "compare"}'
```

`equivalent=true` attendu lorsque les deux moteurs retournent les mêmes lignes
(ordre et valeurs). Toute divergence réelle est signalée dans `diff`.

## 16. Vérification du XML réellement écrit

Après chaque mutation, le fichier canonique est mis à jour :

```bash
cat backend/data/xml/<DB_ID>_<slug>.xml
```

Vérifier : les `<row>/<cell>` insérés, les `<column next_auto_increment="...">`
(compteur AUTO_INCREMENT persistant), les `<indexes>` créés, la `version`
incrémentée.

## 17. Résultats attendus (exemples)

| Opération | Attendu |
|---|---|
| INSERT puis DELETE id 3 puis INSERT | nouvel id = 4 (pas de réutilisation) |
| INSERT multi-lignes avec 1 violation UNIQUE | aucune ligne insérée (atomique) |
| UPDATE/DELETE sans WHERE | erreur structurée (refusé) |
| INSERT VARCHAR trop long | `DATA_INVALID` |
| INSERT DATE `01/01/2020` | `DATA_INVALID` (format attendu YYYY-MM-DD) |
| CREATE UNIQUE INDEX sur doublons | `CONSTRAINT_VIOLATION` |
| DROP COLUMN référencé par une FK | `CONSTRAINT_VIOLATION` |
| `engine=xml` | les données proviennent du XML (métriques `read_ms`/`write_ms`) |

## 18. Tests automatisés

```bash
cd backend
PYTHONPATH=. .venv/bin/python -m pytest -q tests/                       # suite complète
PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_xml_native_engine.py      # moteur natif
PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_xml_engine_final.py       # étapes 1-13
PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_xml_backend_mode.py       # Phase 4 (mode XML)
PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_xml_engine_comparison.py  # comparaison + TCP
```

## 19. Mode backend XML (Phase 4)

```bash
# Lancer le backend en MODE XML PUR (SQLite de données désactivé)
cd backend
QUERY_BACKEND=xml SYNC_SQLITE_PROJECTION=false .venv/bin/python run.py

# Vérifications clés :
# - SELECT/INSERT/UPDATE/DELETE/DDL/index/pagination/schema via REST (engine=xml)
# - GET /api/databases/<id>/schema (introspection depuis le XML)
# - la façade CRUD (tables/colonnes/lignes) lit les lignes depuis le XML
# - aucun fichier data/projections/*.sqlite n'est créé
# - engine=sqlite échoue avec SQLITE_PROJECTION_ERROR (pas de fallback silencieux)
# - TCP engine=xml : mêmes opérations + erreurs structurées
```
