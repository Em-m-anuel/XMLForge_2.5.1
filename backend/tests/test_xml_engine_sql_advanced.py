"""Tests du langage SQL avancé sur le moteur XML natif (sans Flask ni SQLite).

Couvre : DISTINCT, alias, colonnes qualifiées, agrégats SUM/AVG/MIN/MAX/COUNT,
GROUP BY, HAVING, INNER JOIN + ON, INSERT multi-lignes, DDL SQL, index mémoire.
"""

import pytest

from app.errors import ConstraintViolation, ValidationFailed
from app.query.sql_parser import parse_sql_statement
from app.query.xml_executor import XmlQueryExecutor
from app.xml_engine.xml_native import XmlIndex, XmlNativeEngine


def _doc():
    """Mini-base : authors / categories / books avec FK et NULL."""
    return {
        "uuid": "db-1", "name": "lib", "description": "", "comment": "", "status": "ACTIVE",
        "scope": "PERSONAL", "version": 1, "generator": "XMLForge", "created_at": "2026-01-01T00:00:00", "author": "t",
        "tables": [
            {"uuid": "t-cat", "name": "categories", "description": "", "comment": "", "protected": False,
             "file_identifier": None, "status": "ACTIVE", "constraints": [], "indexes": [],
             "columns": [
                 {"uuid": "c-c1", "name": "id", "type": "INT", "length": "-", "nullable": False, "primary_key": True,
                  "foreign_key": False, "references": None, "on_delete": "NO ACTION", "on_update": "NO ACTION",
                  "unique": False, "auto_increment": True, "index": False, "default": None, "comment": "", "status": "ACTIVE"},
                 {"uuid": "c-c2", "name": "name", "type": "VARCHAR", "length": "50", "nullable": False, "primary_key": False,
                  "foreign_key": False, "references": None, "on_delete": "NO ACTION", "on_update": "NO ACTION",
                  "unique": True, "auto_increment": False, "index": False, "default": None, "comment": "", "status": "ACTIVE"},
             ],
             "rows": [
                 {"uuid": "r-c1", "data": {"id": "1", "name": "SF"}},
                 {"uuid": "r-c2", "data": {"id": "2", "name": "Policier"}},
                 {"uuid": "r-c3", "data": {"id": "3", "name": "Essai"}},
             ]},
            {"uuid": "t-books", "name": "books", "description": "", "comment": "", "protected": False,
             "file_identifier": None, "status": "ACTIVE", "constraints": [], "indexes": [],
             "columns": [
                 {"uuid": "c-b1", "name": "id", "type": "INT", "length": "-", "nullable": False, "primary_key": True,
                  "foreign_key": False, "references": None, "on_delete": "NO ACTION", "on_update": "NO ACTION",
                  "unique": False, "auto_increment": True, "index": False, "default": None, "comment": "", "status": "ACTIVE"},
                 {"uuid": "c-b2", "name": "title", "type": "VARCHAR", "length": "100", "nullable": False, "primary_key": False,
                  "foreign_key": False, "references": None, "on_delete": "NO ACTION", "on_update": "NO ACTION",
                  "unique": False, "auto_increment": False, "index": False, "default": None, "comment": "", "status": "ACTIVE"},
                 {"uuid": "c-b3", "name": "category_id", "type": "INT", "length": "-", "nullable": True, "primary_key": False,
                  "foreign_key": True, "references": "categories.id", "on_delete": "SET NULL", "on_update": "NO ACTION",
                  "unique": False, "auto_increment": False, "index": True, "default": None, "comment": "", "status": "ACTIVE"},
                 {"uuid": "c-b4", "name": "price", "type": "REAL", "length": "-", "nullable": True, "primary_key": False,
                  "foreign_key": False, "references": None, "on_delete": "NO ACTION", "on_update": "NO ACTION",
                  "unique": False, "auto_increment": False, "index": False, "default": None, "comment": "", "status": "ACTIVE"},
             ],
             "rows": [
                 {"uuid": "r-b1", "data": {"id": "1", "title": "Fondation", "category_id": "1", "price": "9.5"}},
                 {"uuid": "r-b2", "data": {"id": "2", "title": "Dune", "category_id": "1", "price": "12.0"}},
                 {"uuid": "r-b3", "data": {"id": "3", "title": "Le chien jaune", "category_id": "2", "price": "7.0"}},
                 {"uuid": "r-b4", "data": {"id": "4", "title": "Sans catégorie", "category_id": None, "price": "5.0"}},
             ]},
        ],
    }


@pytest.fixture()
def engine():
    return XmlNativeEngine(document=_doc())


def run(engine, sql):
    return XmlQueryExecutor.execute_engine(engine, sql)


# ------------------------------------------------------------- SELECT / DISTINCT
class TestSelectDistinct:
    def test_distinct_single_column(self, engine):
        result = run(engine, "SELECT DISTINCT category_id FROM books ORDER BY category_id")
        assert result["rows"] == [{"category_id": None}, {"category_id": 1}, {"category_id": 2}]

    def test_distinct_multiple(self, engine):
        run(engine, "INSERT INTO books (title, category_id, price) VALUES ('X', 1, 1.0)")
        run(engine, "INSERT INTO books (title, category_id, price) VALUES ('Y', 1, 1.0)")
        result = run(engine, "SELECT DISTINCT category_id, price FROM books ORDER BY category_id, price")
        # (1,1.0) apparaît une seule fois
        pairs = [(r["category_id"], r["price"]) for r in result["rows"]]
        assert pairs.count((1, 1.0)) == 1


class TestAliasesAndQualified:
    def test_column_alias(self, engine):
        result = run(engine, "SELECT title AS t, price AS p FROM books ORDER BY p DESC LIMIT 2")
        assert result["rows"][0] == {"t": "Dune", "p": 12.0}

    def test_table_alias_qualified(self, engine):
        result = run(engine, "SELECT b.title FROM books b WHERE b.price > 9 ORDER BY b.price")
        assert [r["title"] for r in result["rows"]] == ["Fondation", "Dune"]

    def test_ambiguous_column_rejected(self, engine):
        with pytest.raises(ValidationFailed):
            run(engine, "SELECT title FROM books b JOIN categories c ON b.category_id = c.id WHERE id = 1")


# ------------------------------------------------------------- agrégats
class TestAggregates:
    def test_sum_avg_min_max(self, engine):
        s = run(engine, "SELECT SUM(price) FROM books")["rows"][0]["SUM(price)"]
        assert s == pytest.approx(33.5)
        a = run(engine, "SELECT AVG(price) FROM books")["rows"][0]["AVG(price)"]
        assert a == pytest.approx(8.375)
        lo = run(engine, "SELECT MIN(price) FROM books")["rows"][0]["MIN(price)"]
        assert lo == 5.0
        hi = run(engine, "SELECT MAX(price) FROM books")["rows"][0]["MAX(price)"]
        assert hi == 12.0

    def test_count_star_and_column(self, engine):
        assert run(engine, "SELECT COUNT(*) FROM books")["count"] == 4
        assert run(engine, "SELECT COUNT(category_id) FROM books")["count"] == 3

    def test_group_by(self, engine):
        result = run(engine, "SELECT category_id, COUNT(*) AS n FROM books GROUP BY category_id ORDER BY n DESC")
        assert result["rows"][0] == {"category_id": 1, "n": 2}

    def test_group_by_with_nulls(self, engine):
        result = run(engine, "SELECT category_id, COUNT(*) AS n FROM books GROUP BY category_id ORDER BY category_id")
        assert result["rows"][0] == {"category_id": None, "n": 1}

    def test_having_function_and_alias(self, engine):
        r1 = run(engine, "SELECT category_id, COUNT(*) AS n FROM books GROUP BY category_id HAVING COUNT(*) > 1")
        assert r1["rows"] == [{"category_id": 1, "n": 2}]
        r2 = run(engine, "SELECT category_id, COUNT(*) AS n FROM books GROUP BY category_id HAVING n > 1")
        assert r2["rows"] == [{"category_id": 1, "n": 2}]

    def test_having_aggregate_not_in_select(self, engine):
        result = run(engine, "SELECT category_id FROM books GROUP BY category_id HAVING COUNT(*) > 1")
        assert result["rows"] == [{"category_id": 1}]

    def test_order_by_aggregate(self, engine):
        result = run(engine, "SELECT category_id, SUM(price) AS total FROM books GROUP BY category_id ORDER BY SUM(price) DESC LIMIT 1")
        assert result["rows"][0]["category_id"] == 1


# ------------------------------------------------------------- JOIN
class TestJoin:
    def test_inner_join_on(self, engine):
        result = run(engine, "SELECT books.title, categories.name FROM books JOIN categories ON books.category_id = categories.id ORDER BY books.id")
        assert result["rows"] == [
            {"title": "Fondation", "name": "SF"},
            {"title": "Dune", "name": "SF"},
            {"title": "Le chien jaune", "name": "Policier"},
        ]

    def test_join_alias_qualified(self, engine):
        result = run(engine, "SELECT b.title, c.name FROM books b JOIN categories c ON b.category_id = c.id WHERE c.name = 'SF' ORDER BY b.id")
        assert [r["title"] for r in result["rows"]] == ["Fondation", "Dune"]

    def test_join_star_qualified_keys(self, engine):
        result = run(engine, "SELECT * FROM books b JOIN categories c ON b.category_id = c.id LIMIT 1")
        row = result["rows"][0]
        assert "b.title" in row and "c.name" in row

    def test_join_on_column_equality(self, engine):
        # ON avec égalité colonne=colonne (sans littéral)
        result = run(engine, "SELECT b.title FROM books b JOIN categories c ON b.category_id = c.id WHERE b.category_id = 1")
        assert len(result["rows"]) == 2


# ------------------------------------------------------------- INSERT multi
class TestMultiInsert:
    def test_multi_row_insert(self, engine):
        result = run(engine, "INSERT INTO categories (name) VALUES ('A'), ('B'), ('C')")
        assert result["inserted"] == 3
        assert run(engine, "SELECT COUNT(*) FROM categories")["count"] == 6

    def test_multi_row_atomic_on_violation(self, engine):
        # 2e ligne viole UNIQUE : rien ne doit être inséré (validation globale).
        with pytest.raises(ConstraintViolation):
            run(engine, "INSERT INTO categories (name) VALUES ('Nouveau'), ('SF')")
        assert run(engine, "SELECT COUNT(*) FROM categories")["count"] == 3


# ------------------------------------------------------------- DDL SQL
class TestDdlSql:
    def test_create_add_drop(self, engine):
        assert run(engine, "CREATE TABLE scratch (id INT PRIMARY KEY AUTO_INCREMENT NOT NULL, label VARCHAR UNIQUE)")["created"] == "scratch"
        assert run(engine, "ALTER TABLE scratch ADD COLUMN price REAL DEFAULT 0.0")["added"] == "price"
        assert run(engine, "INSERT INTO scratch (label) VALUES ('x')")["inserted"] == 1
        row = run(engine, "SELECT * FROM scratch")["rows"][0]
        assert row["price"] == 0.0
        assert run(engine, "ALTER TABLE scratch DROP COLUMN price")["dropped_column"] == "price"
        assert run(engine, "DROP TABLE scratch")["dropped"] == "scratch"

    def test_drop_table_referenced_refused(self, engine):
        with pytest.raises(ConstraintViolation):
            run(engine, "DROP TABLE categories")

    def test_create_table_duplicate_refused(self, engine):
        with pytest.raises(ConstraintViolation):
            run(engine, "CREATE TABLE books (id INT)")


# ------------------------------------------------------------- index mémoire
class TestIndex:
    def test_index_lookup(self):
        engine = XmlNativeEngine(document=_doc())
        idx = XmlIndex()
        idx.build(engine.document)
        hits = idx.lookup_rows("categories", "name", "SF")
        assert len(hits) == 1 and hits[0]["uuid"] == "r-c1"
        assert idx.lookup_rows("categories", "name", "inconnu") == []

    def test_index_used_by_engine_and_invalidated(self, engine):
        run(engine, "SELECT * FROM books WHERE category_id = 1")
        assert engine._index.maps  # construit après la première requête
        run(engine, "INSERT INTO books (title, category_id) VALUES ('Z', 1)")
        assert not engine._index.maps  # invalidé après mutation

    def test_fk_check_uses_index(self, engine):
        # categories.id est indexée (PK) : le contrôle FK s'appuie sur l'index.
        assert run(engine, "INSERT INTO books (title, category_id) VALUES ('ok', 2)")["inserted"] == 1
        with pytest.raises(ConstraintViolation):
            run(engine, "INSERT INTO books (title, category_id) VALUES ('ko', 999)")


# ------------------------------------------------------------- parser refus
class TestParserRefusals:
    def test_outer_join_refused(self):
        # Phase 7 : LEFT JOIN est désormais supporté ; RIGHT/FULL restent refusés.
        st = parse_sql_statement("SELECT * FROM books LEFT JOIN categories ON books.category_id = categories.id")
        assert st["joins"][0]["type"] == "LEFT"
        with pytest.raises(ValidationFailed):
            parse_sql_statement("SELECT * FROM books RIGHT JOIN categories ON books.category_id = categories.id")
        with pytest.raises(ValidationFailed):
            parse_sql_statement("SELECT * FROM books FULL OUTER JOIN categories ON books.category_id = categories.id")

    def test_count_distinct_refused(self):
        with pytest.raises(ValidationFailed):
            parse_sql_statement("SELECT COUNT(DISTINCT category_id) FROM books")

    def test_update_without_where_refused(self):
        with pytest.raises(ValidationFailed):
            parse_sql_statement("UPDATE books SET price = 1")

    def test_delete_without_where_refused(self):
        with pytest.raises(ValidationFailed):
            parse_sql_statement("DELETE FROM books")
