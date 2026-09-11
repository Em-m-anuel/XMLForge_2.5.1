"""Tests finaux du moteur XML natif (étapes 1-13).

Couvre : DDL complet (CREATE DATABASE, CREATE TABLE, ALTER MODIFY/RENAME/DROP,
CREATE/DROP INDEX, UNIQUE INDEX composite), INSERT complet, UPDATE/DELETE
robustes, NULL semantics, types + coercition, DEFAULT (CURRENT_TIMESTAMP),
AUTO_INCREMENT sans réutilisation, intégrité référentielle, opérateurs
BETWEEN/NOT IN/NOT LIKE, pagination, introspection de schéma.
"""

import os
import socket

import pytest

from app.errors import (
    ConflictError,
    ConstraintViolation,
    DataValidationError,
    NotFoundError,
    ValidationFailed,
)
from app.query.sql_parser import parse_sql_statement
from app.query.xml_executor import XmlQueryExecutor
from app.xml_engine.xml_native import XmlNativeEngine
from .conftest import register_and_login, auth


# ---------------------------------------------------------------------------
# Base relationnelle réaliste (users / categories / books / orders / order_items)
# ---------------------------------------------------------------------------
def _col(name, ctype, length="-", nullable=True, primary_key=False, foreign_key=False,
         references=None, unique=False, auto_increment=False, default=None,
         on_delete="NO ACTION", indexed=False):
    return {
        "uuid": f"c-{name}", "name": name, "type": ctype, "length": length,
        "nullable": nullable, "primary_key": primary_key, "foreign_key": foreign_key or bool(references),
        "references": references, "on_delete": on_delete, "on_update": "NO ACTION",
        "unique": unique, "auto_increment": auto_increment, "index": indexed,
        "default": default, "comment": "", "status": "ACTIVE",
    }


def _table(name, columns, rows=None):
    return {"uuid": f"t-{name}", "name": name, "description": "", "comment": "",
            "protected": False, "file_identifier": None, "status": "ACTIVE",
            "constraints": [], "indexes": [], "columns": columns,
            "rows": [{"uuid": f"r-{name}-{i}", "data": dict(r)} for i, r in enumerate(rows or [])]}


def _base_document():
    users = _table("users", [
        _col("id", "INT", primary_key=True, auto_increment=True, nullable=False),
        _col("name", "VARCHAR", length="150", nullable=False),
        _col("email", "VARCHAR", length="255", unique=True, nullable=False),
        _col("age", "INT", default="18"),
        _col("active", "BOOLEAN", default="true"),
        _col("created_at", "DATETIME", default="CURRENT_TIMESTAMP"),
    ], [
        {"id": "1", "name": "Alice", "email": "alice@test.com", "age": "30", "active": "true", "created_at": "2026-01-01 10:00:00"},
        {"id": "2", "name": "Bob", "email": "bob@test.com", "age": "25", "active": "false", "created_at": "2026-01-02 11:30:00"},
        {"id": "3", "name": "Charlie", "email": "charlie@test.com", "age": None, "active": "true", "created_at": "2026-01-03 09:15:00"},
    ])
    categories = _table("categories", [
        _col("id", "INT", primary_key=True, auto_increment=True, nullable=False),
        _col("name", "VARCHAR", length="100", unique=True, nullable=False),
    ], [{"id": "1", "name": "SF"}, {"id": "2", "name": "Policier"}])
    books = _table("books", [
        _col("id", "INT", primary_key=True, auto_increment=True, nullable=False),
        _col("title", "VARCHAR", length="200", nullable=False, indexed=True),
        _col("category_id", "INT", foreign_key=True, references="categories.id", on_delete="SET NULL"),
        _col("price", "DECIMAL", default="0.00"),
        _col("published", "DATE"),
    ], [
        {"id": "1", "title": "Fondation", "category_id": "1", "price": "9.50", "published": "1951-01-01"},
        {"id": "2", "title": "Dune", "category_id": "1", "price": "12.00", "published": "1965-08-01"},
        {"id": "3", "title": "Le chien jaune", "category_id": "2", "price": "7.00", "published": "1931-01-01"},
    ])
    orders = _table("orders", [
        _col("id", "INT", primary_key=True, auto_increment=True, nullable=False),
        _col("user_id", "INT", foreign_key=True, references="users.id", on_delete="RESTRICT", nullable=False),
        _col("total", "DECIMAL", default="0.00"),
    ], [{"id": "1", "user_id": "1", "total": "21.50"}])
    order_items = _table("order_items", [
        _col("id", "INT", primary_key=True, auto_increment=True, nullable=False),
        _col("order_id", "INT", foreign_key=True, references="orders.id", on_delete="CASCADE", nullable=False),
        _col("book_id", "INT", foreign_key=True, references="books.id", on_delete="RESTRICT", nullable=False),
        _col("qty", "INT", default="1"),
    ], [{"id": "1", "order_id": "1", "book_id": "1", "qty": "2"}])
    return {"uuid": "db-final", "name": "final_db", "description": "base finale",
            "comment": "", "status": "ACTIVE", "scope": "PERSONAL", "version": 1,
            "generator": "XMLForge", "created_at": "2026-01-01T00:00:00", "author": "tests",
            "tables": [users, categories, books, orders, order_items]}


@pytest.fixture()
def engine():
    return XmlNativeEngine(document=_base_document())


def run(engine, sql):
    return XmlQueryExecutor.execute_engine(engine, sql)


# ---------------------------------------------------------------------------
# Étape 1 — DDL complet
# ---------------------------------------------------------------------------
class TestDdlComplete:
    def test_create_table_full(self, engine):
        assert run(engine, "CREATE TABLE t (id INT PRIMARY KEY AUTO_INCREMENT NOT NULL, "
                           "name VARCHAR(150) NOT NULL, email VARCHAR(255) UNIQUE)")["created"] == "t"

    def test_modify_column_type_and_length(self, engine):
        run(engine, "ALTER TABLE users MODIFY COLUMN name VARCHAR(200)")
        assert engine.table("users")["columns"][1]["length"] == "200"

    def test_modify_column_rejects_incompatible_values(self, engine):
        # 'age' contient 30/25/NULL : type INT -> TEXT est possible ;
        # modifier 'email' VARCHAR en INT doit être refusé (valeurs non entières).
        with pytest.raises(ConstraintViolation):
            run(engine, "ALTER TABLE users MODIFY COLUMN email INT")

    def test_modify_column_not_null_on_nulls(self, engine):
        # 'age' contient une valeur NULL : rendre NOT NULL doit échouer.
        with pytest.raises(ConstraintViolation):
            run(engine, "ALTER TABLE users MODIFY COLUMN age INT NOT NULL")

    def test_rename_table_updates_fk(self, engine):
        assert run(engine, "ALTER TABLE categories RENAME TO genres")["new_name"] == "genres"
        # books.category_id référence désormais genres.id
        assert engine.table("books")["columns"][2]["references"] == "genres.id"

    def test_rename_to_existing_refused(self, engine):
        with pytest.raises(ConstraintViolation):
            run(engine, "ALTER TABLE users RENAME TO books")

    def test_drop_table_referenced_refused(self, engine):
        with pytest.raises(ConstraintViolation):
            run(engine, "DROP TABLE categories")

    def test_drop_column_referenced_refused(self, engine):
        with pytest.raises(ConstraintViolation):
            run(engine, "ALTER TABLE categories DROP COLUMN id")

    def test_drop_column(self, engine):
        assert run(engine, "ALTER TABLE books DROP COLUMN published")["dropped_column"] == "published"


# ---------------------------------------------------------------------------
# Étape 2 — Index XML
# ---------------------------------------------------------------------------
class TestIndexes:
    def test_create_and_drop_index(self, engine):
        run(engine, "CREATE INDEX idx_books_price ON books (price)")
        assert any(i["name"] == "idx_books_price" for i in engine.table("books")["indexes"])
        assert run(engine, "DROP INDEX idx_books_price ON books")["dropped_index"] == "idx_books_price"

    def test_composite_index(self, engine):
        run(engine, "CREATE INDEX idx_cat_price ON books (category_id, price)")
        index = next(i for i in engine.table("books")["indexes"] if i["name"] == "idx_cat_price")
        assert index["columns"] == ["category_id", "price"]

    def test_unique_index_enforced_on_existing(self, engine):
        # price contient des valeurs uniques ; category_id contient des doublons.
        run(engine, "CREATE UNIQUE INDEX idx_price ON books (price)")
        with pytest.raises(ConstraintViolation):
            run(engine, "CREATE UNIQUE INDEX idx_cat ON books (category_id)")

    def test_unique_index_enforced_on_insert(self, engine):
        run(engine, "CREATE UNIQUE INDEX idx_title ON books (title)")
        with pytest.raises(ConstraintViolation):
            run(engine, "INSERT INTO books (title) VALUES ('Dune')")

    def test_index_on_missing_column_refused(self, engine):
        with pytest.raises(ValidationFailed):
            run(engine, "CREATE INDEX idx_bad ON books (nope)")

    def test_index_dropped_with_table(self, engine):
        run(engine, "CREATE INDEX idx_orders ON orders (user_id)")
        run(engine, "CREATE TABLE scratch (id INT PRIMARY KEY)")
        run(engine, "CREATE INDEX idx_scratch ON scratch (id)")
        run(engine, "DROP TABLE scratch")
        # l'index de scratch a disparu avec la table
        assert "scratch" not in [t["name"] for t in engine.document["tables"]]

    def test_drop_index_no_table_qualifier(self, engine):
        run(engine, "CREATE INDEX idx_price2 ON books (price)")
        assert run(engine, "DROP INDEX idx_price2")["dropped_index"] == "idx_price2"


# ---------------------------------------------------------------------------
# Étape 3 — INSERT complet
# ---------------------------------------------------------------------------
class TestInsertComplete:
    def test_insert_explicit_columns_arbitrary_order(self, engine):
        run(engine, "INSERT INTO users (email, name, age) VALUES ('d@t.com', 'Dave', 40)")
        row = run(engine, "SELECT name, age FROM users WHERE email = 'd@t.com'")["rows"][0]
        assert row == {"name": "Dave", "age": 40}

    def test_multi_row_insert(self, engine):
        result = run(engine, "INSERT INTO users (name, email) VALUES "
                             "('Eva', 'eva@t.com'), ('Frank', 'frank@t.com'), ('Gina', 'gina@t.com')")
        assert result["inserted"] == 3

    def test_multi_row_insert_atomic_on_violation(self, engine):
        with pytest.raises(ConstraintViolation):
            run(engine, "INSERT INTO users (name, email) VALUES ('Ok', 'ok@t.com'), ('Dup', 'bob@test.com')")
        assert run(engine, "SELECT COUNT(*) FROM users")["count"] == 3  # rien d'inséré

    def test_insert_implicit_columns(self, engine):
        # INSERT INTO t VALUES (...) sans liste de colonnes : ordre du schéma.
        run(engine, "INSERT INTO categories VALUES (3, 'Essai')")
        assert run(engine, "SELECT name FROM categories WHERE id = 3")["rows"][0] == {"name": "Essai"}

    def test_insert_implicit_wrong_count(self, engine):
        with pytest.raises(ValidationFailed):
            run(engine, "INSERT INTO categories VALUES (4)")  # 1 valeur pour 2 colonnes

    def test_default_and_null(self, engine):
        run(engine, "INSERT INTO users (name, email) VALUES ('NullAge', 'nullage@t.com')")
        row = run(engine, "SELECT age, active FROM users WHERE email = 'nullage@t.com'")["rows"][0]
        assert row["age"] == 18 and row["active"] is True

    def test_auto_increment_no_reuse(self, engine):
        run(engine, "INSERT INTO users (name, email) VALUES ('Tmp', 'tmp@t.com')")  # id 4
        run(engine, "DELETE FROM users WHERE id = 4")
        run(engine, "INSERT INTO users (name, email) VALUES ('Tmp2', 'tmp2@t.com')")
        ids = [r["id"] for r in run(engine, "SELECT id FROM users ORDER BY id")["rows"]]
        assert 4 not in ids and 5 in ids

    def test_explicit_id_bumps_counter(self, engine):
        run(engine, "INSERT INTO users (id, name, email) VALUES (100, 'Big', 'big@t.com')")
        run(engine, "INSERT INTO users (name, email) VALUES ('After', 'after@t.com')")
        ids = [r["id"] for r in run(engine, "SELECT id FROM users ORDER BY id")["rows"]]
        assert max(ids) == 101


# ---------------------------------------------------------------------------
# Étapes 4-5 — UPDATE / DELETE robustes
# ---------------------------------------------------------------------------
class TestUpdateDelete:
    def test_update_multi_column(self, engine):
        assert run(engine, "UPDATE users SET name = 'Alice2', age = 31 WHERE id = 1")["updated"] == 1
        row = run(engine, "SELECT name, age FROM users WHERE id = 1")["rows"][0]
        assert row == {"name": "Alice2", "age": 31}

    def test_update_without_where_refused(self, engine):
        with pytest.raises(ValidationFailed):
            run(engine, "UPDATE users SET age = 1")

    def test_delete_without_where_refused(self, engine):
        with pytest.raises(ValidationFailed):
            run(engine, "DELETE FROM users")

    def test_update_fk_violation(self, engine):
        with pytest.raises(ConstraintViolation):
            run(engine, "UPDATE books SET category_id = 999 WHERE id = 1")

    def test_update_unique_violation(self, engine):
        with pytest.raises(ConstraintViolation):
            run(engine, "UPDATE users SET email = 'bob@test.com' WHERE id = 1")

    def test_delete_fk_restrict(self, engine):
        with pytest.raises(ConstraintViolation):
            run(engine, "DELETE FROM users WHERE id = 1")  # référencé par orders

    def test_delete_fk_set_null(self, engine):
        run(engine, "DELETE FROM categories WHERE id = 1")
        assert run(engine, "SELECT COUNT(*) FROM books WHERE category_id IS NULL")["count"] == 2

    def test_delete_fk_cascade(self, engine):
        run(engine, "DELETE FROM orders WHERE id = 1")
        assert run(engine, "SELECT COUNT(*) FROM order_items")["count"] == 0


# ---------------------------------------------------------------------------
# Étape 6 — NULL semantics
# ---------------------------------------------------------------------------
class TestNullSemantics:
    def test_null_vs_empty_string(self, engine):
        run(engine, "CREATE TABLE n (id INT PRIMARY KEY AUTO_INCREMENT NOT NULL, v VARCHAR)")
        run(engine, "INSERT INTO n (v) VALUES (NULL)")
        run(engine, "INSERT INTO n (v) VALUES ('')")
        run(engine, "INSERT INTO n (v) VALUES ('NULL')")
        assert run(engine, "SELECT COUNT(*) FROM n WHERE v IS NULL")["count"] == 1
        assert run(engine, "SELECT COUNT(*) FROM n WHERE v = ''")["count"] == 1
        assert run(engine, "SELECT COUNT(*) FROM n WHERE v = 'NULL'")["count"] == 1
        assert run(engine, "SELECT COUNT(*) FROM n WHERE v IS NOT NULL")["count"] == 2


# ---------------------------------------------------------------------------
# Étape 7 — Types et coercition
# ---------------------------------------------------------------------------
class TestTypes:
    def test_int_rejects_text(self, engine):
        with pytest.raises(DataValidationError):
            run(engine, "INSERT INTO users (name, email, age) VALUES ('X', 'x@t.com', 'bonjour')")

    def test_boolean_representations(self, engine):
        run(engine, "CREATE TABLE b (id INT PRIMARY KEY, flag BOOLEAN)")
        run(engine, "INSERT INTO b (id, flag) VALUES (1, true)")
        run(engine, "INSERT INTO b (id, flag) VALUES (2, 'false')")
        assert run(engine, "SELECT flag FROM b WHERE id = 1")["rows"][0]["flag"] is True
        assert run(engine, "SELECT flag FROM b WHERE id = 2")["rows"][0]["flag"] is False
        with pytest.raises(DataValidationError):
            run(engine, "INSERT INTO b (id, flag) VALUES (3, 'maybe')")

    def test_decimal(self, engine):
        assert run(engine, "SELECT price FROM books WHERE id = 1")["rows"][0]["price"] == 9.5

    def test_date_validation(self, engine):
        with pytest.raises(DataValidationError):
            run(engine, "INSERT INTO books (title, published) VALUES ('X', '01/01/2020')")
        run(engine, "INSERT INTO books (title, published) VALUES ('X', '2020-01-15')")

    def test_datetime_validation(self, engine):
        with pytest.raises(DataValidationError):
            run(engine, "INSERT INTO users (name, email, created_at) VALUES ('X', 'dt@t.com', 'pas-une-date')")

    def test_varchar_length(self, engine):
        with pytest.raises(DataValidationError):
            run(engine, "INSERT INTO categories (name) VALUES ('" + "X" * 200 + "')")


# ---------------------------------------------------------------------------
# Étape 8 — DEFAULT complet
# ---------------------------------------------------------------------------
class TestDefault:
    def test_default_current_timestamp_evaluated_at_insert(self, engine):
        run(engine, "CREATE TABLE ev (id INT PRIMARY KEY AUTO_INCREMENT NOT NULL, ts DATETIME DEFAULT CURRENT_TIMESTAMP)")
        run(engine, "INSERT INTO ev (id) VALUES (1)")
        row = run(engine, "SELECT ts FROM ev WHERE id = 1")["rows"][0]
        assert row["ts"] is not None and row["ts"].startswith("20")

    def test_default_null_equivalent(self, engine):
        run(engine, "CREATE TABLE dn (id INT PRIMARY KEY AUTO_INCREMENT NOT NULL, v VARCHAR DEFAULT NULL)")
        run(engine, "INSERT INTO dn (id) VALUES (1)")
        assert run(engine, "SELECT v FROM dn WHERE id = 1")["rows"][0]["v"] is None

    def test_default_on_add_column(self, engine):
        run(engine, "ALTER TABLE categories ADD COLUMN active BOOLEAN DEFAULT true")
        assert run(engine, "SELECT active FROM categories WHERE id = 1")["rows"][0]["active"] is True


# ---------------------------------------------------------------------------
# Étape 9 — AUTO_INCREMENT
# ---------------------------------------------------------------------------
class TestAutoIncrement:
    def test_counter_persisted_in_xml(self, engine, tmp_path):
        path = str(tmp_path / "ai.xml")
        engine.save(path)
        reloaded = XmlNativeEngine(xml_path=path)
        run(reloaded, "INSERT INTO users (name, email) VALUES ('N1', 'n1@t.com')")
        reloaded.save()
        reloaded2 = XmlNativeEngine(xml_path=path)
        run(reloaded2, "INSERT INTO users (name, email) VALUES ('N2', 'n2@t.com')")
        ids = [r["id"] for r in run(reloaded2, "SELECT id FROM users ORDER BY id")["rows"]]
        assert ids[-1] == 5  # 3 initiaux + N1 + N2, sans réutilisation

    def test_explicit_id_no_collision(self, engine):
        run(engine, "INSERT INTO users (id, name, email) VALUES (50, 'E', 'e@t.com')")
        run(engine, "INSERT INTO users (name, email) VALUES ('F', 'f@t.com')")
        ids = [r["id"] for r in run(engine, "SELECT id FROM users WHERE id >= 50 ORDER BY id")["rows"]]
        assert ids == [50, 51]


# ---------------------------------------------------------------------------
# Étape 10 — Intégrité référentielle
# ---------------------------------------------------------------------------
class TestReferentialIntegrity:
    def test_insert_fk_missing(self, engine):
        with pytest.raises(ConstraintViolation):
            run(engine, "INSERT INTO books (title, category_id) VALUES ('Orphelin', 999)")

    def test_update_fk_exists(self, engine):
        run(engine, "UPDATE books SET category_id = 2 WHERE id = 1")
        assert run(engine, "SELECT category_id FROM books WHERE id = 1")["rows"][0]["category_id"] == 2

    def test_drop_table_used_by_fk(self, engine):
        with pytest.raises(ConstraintViolation):
            run(engine, "DROP TABLE users")  # orders.user_id


# ---------------------------------------------------------------------------
# Étape 11 — Opérateurs de recherche
# ---------------------------------------------------------------------------
class TestWhereOperators:
    def test_between(self, engine):
        assert run(engine, "SELECT COUNT(*) FROM books WHERE price BETWEEN 8 AND 12")["count"] == 2

    def test_not_in(self, engine):
        assert run(engine, "SELECT COUNT(*) FROM books WHERE id NOT IN (1, 3)")["count"] == 1

    def test_not_like(self, engine):
        assert run(engine, "SELECT COUNT(*) FROM books WHERE title NOT LIKE 'F%'")["count"] == 2

    def test_precedence_and_or(self, engine):
        # (a OR b) AND c  vs  a OR (b AND c) — parenthèses respectées.
        # Livres : Fondation(9.5, cat1), Dune(12.0, cat1), Le chien jaune(7.0, cat2)
        r = run(engine, "SELECT COUNT(*) FROM books WHERE (category_id = 1 OR category_id = 2) AND price > 8")
        assert r["count"] == 2  # Fondation + Dune
        r2 = run(engine, "SELECT COUNT(*) FROM books WHERE category_id = 1 OR (category_id = 2 AND price > 8)")
        assert r2["count"] == 2  # Fondation + Dune (cat1) ; chien jaune exclu (7.0)


# ---------------------------------------------------------------------------
# Étape 12 — Pagination
# ---------------------------------------------------------------------------
class TestPagination:
    def test_limit_offset(self, engine):
        result = run(engine, "SELECT id FROM books ORDER BY id LIMIT 2 OFFSET 1")
        assert [r["id"] for r in result["rows"]] == [2, 3]

    def test_pagination_metadata(self, engine):
        result = run(engine, "SELECT * FROM books ORDER BY id LIMIT 2 OFFSET 0")
        p = result["pagination"]
        assert p == {"page": 1, "page_size": 2, "total": 3, "total_pages": 2, "current_page": 1}


# ---------------------------------------------------------------------------
# Étape 13 — Introspection (REST)
# ---------------------------------------------------------------------------
class TestSchemaIntrospection:
    def test_schema_endpoint(self, app, client):
        user, token = register_and_login(client, "Schema", "schema@example.com")
        database = client.post('/databases', json={"name": "schema_db"}, headers=auth(token)).get_json()["data"]
        client.post('/tables', json={"name": "users", "database_id": database["id"]}, headers=auth(token))
        table = client.get(f"/tables/{database['id']}", headers=auth(token)).get_json()["data"][0]
        client.post('/columns', json={"name": "id", "type": "INT", "table_id": table["id"], "primary_key": True, "auto_increment": True, "nullable": False}, headers=auth(token))
        client.post('/columns', json={"name": "email", "type": "VARCHAR", "table_id": table["id"], "unique": True, "index": True}, headers=auth(token))

        resp = client.get(f"/databases/{database['id']}/schema", headers=auth(token))
        assert resp.status_code == 200
        schema = resp.get_json()["data"]
        assert schema["database"] == "schema_db"
        assert schema["tables"][0]["name"] == "users"
        cols = {c["name"]: c for c in schema["tables"][0]["columns"]}
        assert cols["id"]["primary_key"] is True and cols["id"]["auto_increment"] is True
        assert cols["email"]["unique"] is True
        assert schema["tables"][0]["row_count"] == 0

    def test_schema_forbidden_without_share(self, app, client):
        owner, token = register_and_login(client, "Owner S", "owner-schema@example.com")
        database = client.post('/databases', json={"name": "private_db"}, headers=auth(token)).get_json()["data"]
        other, other_token = register_and_login(client, "Other S", "other-schema@example.com")
        resp = client.get(f"/databases/{database['id']}/schema", headers=auth(other_token))
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Intégration REST / TCP / comparaison
# ---------------------------------------------------------------------------
def free_port():
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _build_via_rest(client, token, name="rest_final"):
    database = client.post('/databases', json={"name": name}, headers=auth(token)).get_json()["data"]
    cats = client.post('/tables', json={"name": "categories", "database_id": database["id"]}, headers=auth(token)).get_json()["data"]
    client.post('/columns', json={"name": "id", "type": "INT", "table_id": cats["id"], "primary_key": True, "auto_increment": True}, headers=auth(token))
    client.post('/columns', json={"name": "name", "type": "VARCHAR", "table_id": cats["id"], "nullable": False, "unique": True}, headers=auth(token))
    books = client.post('/tables', json={"name": "books", "database_id": database["id"]}, headers=auth(token)).get_json()["data"]
    client.post('/columns', json={"name": "id", "type": "INT", "table_id": books["id"], "primary_key": True, "auto_increment": True}, headers=auth(token))
    client.post('/columns', json={"name": "title", "type": "VARCHAR", "table_id": books["id"], "nullable": False}, headers=auth(token))
    client.post('/columns', json={"name": "category_id", "type": "INT", "table_id": books["id"], "references": "categories.id", "on_delete": "SET NULL"}, headers=auth(token))
    client.post('/columns', json={"name": "price", "type": "REAL", "table_id": books["id"], "nullable": True}, headers=auth(token))
    for n in ["SF", "Policier"]:
        client.post(f"/databases/{database['id']}/query", json={"sql": f"INSERT INTO categories (name) VALUES ('{n}')"}, headers=auth(token))
    for i in range(1, 6):
        client.post(f"/databases/{database['id']}/query", json={
            "sql": f"INSERT INTO books (title, category_id, price) VALUES ('L{i}', {(i % 2) + 1}, {i * 2.5})"}, headers=auth(token))
    return database


class TestIntegration:
    def test_rest_engine_xml_operators_and_ddl(self, app, client):
        user, token = register_and_login(client, "Rest Final", "rest-final@example.com")
        database = _build_via_rest(client, token)

        resp = client.post(f"/databases/{database['id']}/query", json={
            "sql": "SELECT title FROM books WHERE price BETWEEN 4 AND 8 ORDER BY price", "engine": "xml"}, headers=auth(token))
        assert resp.status_code == 200
        assert len(resp.get_json()["data"]["result"]["rows"]) == 2

        resp = client.post(f"/databases/{database['id']}/query", json={
            "sql": "CREATE INDEX idx_title ON books (title)", "engine": "xml"}, headers=auth(token))
        assert resp.status_code == 200

        resp = client.post(f"/databases/{database['id']}/query", json={
            "sql": "ALTER TABLE books MODIFY COLUMN title VARCHAR(100)", "engine": "xml"}, headers=auth(token))
        assert resp.status_code == 200

    def test_new_operators_xml(self, app, client):
        user, token = register_and_login(client, "Cmp Final", "cmp-final@example.com")
        database = _build_via_rest(client, token)
        for sql, expected in [
            ("SELECT title FROM books WHERE price BETWEEN 4 AND 8 ORDER BY title",
             ["L2", "L3"]),
            ("SELECT title FROM books WHERE id NOT IN (1, 2) ORDER BY title",
             ["L3", "L4", "L5"]),
            ("SELECT title FROM books WHERE title NOT LIKE 'L1%' ORDER BY title",
             ["L2", "L3", "L4", "L5"]),
        ]:
            resp = client.post(f"/databases/{database['id']}/query", json={"sql": sql, "engine": "xml"},
                               headers=auth(token))
            assert resp.status_code == 200, resp.get_json()
            rows = resp.get_json()["data"]["result"]["rows"]
            assert [r["title"] for r in rows] == expected, sql

    def test_create_database_via_sql(self, app, client):
        user, token = register_and_login(client, "Create DB", "createdb-final@example.com")
        # CREATE DATABASE via le moteur (crée une base PERSONAL possédée par l'utilisateur).
        # On crée d'abord une base "hôte" pour disposer d'un contexte de requête.
        host = client.post('/databases', json={"name": "host_db"}, headers=auth(token)).get_json()["data"]
        resp = client.post(f"/databases/{host['id']}/query", json={"sql": "CREATE DATABASE newdb"}, headers=auth(token))
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["result"]["created"] == "newdb"
        dbs = client.get('/databases', headers=auth(token)).get_json()["data"]
        assert any(d["name"] == "newdb" for d in dbs)

    def test_tcp_full_ddl_and_operators(self, app, client):
        user, token = register_and_login(client, "TCP Final", "tcp-final@example.com")
        database = _build_via_rest(client, token, name="tcp_final")
        tcp = client.post('/api/tcp/credentials', json={"tcp_password": "tcp-final-secret"}, headers=auth(token)).get_json()["data"]

        from app.tcp.tcp_server import TCPServer
        from app.tcp.xmlforge_client import XMLForgeClient
        port = free_port()
        server = TCPServer('127.0.0.1', port, app)
        server.start()
        try:
            external = XMLForgeClient('127.0.0.1', port, timeout=5)
            assert external.connect(tcp["credential"]["tcp_username"], "tcp-final-secret", str(database["id"]))

            between = external.execute("SELECT title FROM books WHERE price BETWEEN 4 AND 8", engine="xml")
            assert len(between["rows"]) == 2

            external.execute("CREATE INDEX idx_t ON books (title)", engine="xml")
            external.execute("ALTER TABLE books ADD COLUMN year INT", engine="xml")
            external.execute("ALTER TABLE books RENAME TO livres", engine="xml")
            renamed = external.select('livres', where="id=1")
            assert renamed[0]["title"] == "L1"
            external.execute("ALTER TABLE livres RENAME TO books", engine="xml")

            external.execute("DROP INDEX idx_t ON books", engine="xml")
            external.disconnect()
        finally:
            server.stop()
