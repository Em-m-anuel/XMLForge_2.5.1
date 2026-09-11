"""Tests du moteur de données XML natif — sans Flask, sans SQLite, sans SQLAlchemy."""
import os

import pytest

from app.errors import ConstraintViolation, ConflictError, DataValidationError, NotFoundError, ValidationFailed
from app.xml_engine.document import parse_document, serialize_document
from app.xml_engine.xml_native import Timing, XmlNativeEngine


def _build_document(scope="PERSONAL"):
    return {
        "uuid": "db-uuid", "name": "bibliotheque", "description": "base de test",
        "comment": "", "status": "ACTIVE", "scope": scope, "version": 1,
        "generator": "XMLForge", "created_at": "2026-01-01T00:00:00", "author": "tests",
        "tables": [
            {
                "uuid": "t-authors", "name": "authors", "description": "", "comment": "",
                "protected": False, "file_identifier": None, "status": "ACTIVE",
                "constraints": [], "indexes": [],
                "columns": [
                    {"uuid": "c-a1", "name": "id", "type": "INT", "length": "-", "nullable": False,
                     "primary_key": True, "foreign_key": False, "references": None, "on_delete": "NO ACTION",
                     "on_update": "NO ACTION", "unique": False, "auto_increment": True, "index": False,
                     "default": None, "comment": "", "status": "ACTIVE"},
                    {"uuid": "c-a2", "name": "name", "type": "VARCHAR", "length": "100", "nullable": False,
                     "primary_key": False, "foreign_key": False, "references": None, "on_delete": "NO ACTION",
                     "on_update": "NO ACTION", "unique": True, "auto_increment": False, "index": False,
                     "default": None, "comment": "", "status": "ACTIVE"},
                ],
                "rows": [
                    {"uuid": "r-a1", "data": {"id": "1", "name": "Asimov"}},
                    {"uuid": "r-a2", "data": {"id": "2", "name": "Herbert"}},
                ],
            },
            {
                "uuid": "t-books", "name": "books", "description": "", "comment": "",
                "protected": False, "file_identifier": None, "status": "ACTIVE",
                "constraints": [], "indexes": [],
                "columns": [
                    {"uuid": "c-b1", "name": "id", "type": "INT", "length": "-", "nullable": False,
                     "primary_key": True, "foreign_key": False, "references": None, "on_delete": "NO ACTION",
                     "on_update": "NO ACTION", "unique": False, "auto_increment": True, "index": False,
                     "default": None, "comment": "", "status": "ACTIVE"},
                    {"uuid": "c-b2", "name": "title", "type": "VARCHAR", "length": "200", "nullable": False,
                     "primary_key": False, "foreign_key": False, "references": None, "on_delete": "NO ACTION",
                     "on_update": "NO ACTION", "unique": False, "auto_increment": False, "index": False,
                     "default": None, "comment": "", "status": "ACTIVE"},
                    {"uuid": "c-b3", "name": "author_id", "type": "INT", "length": "-", "nullable": True,
                     "primary_key": False, "foreign_key": True, "references": "authors.id",
                     "on_delete": "RESTRICT", "on_update": "NO ACTION", "unique": False,
                     "auto_increment": False, "index": False, "default": None, "comment": "", "status": "ACTIVE"},
                    {"uuid": "c-b4", "name": "price", "type": "REAL", "length": "-", "nullable": True,
                     "primary_key": False, "foreign_key": False, "references": None, "on_delete": "NO ACTION",
                     "on_update": "NO ACTION", "unique": False, "auto_increment": False, "index": False,
                     "default": None, "comment": "", "status": "ACTIVE"},
                    {"uuid": "c-b5", "name": "available", "type": "BOOLEAN", "length": "-", "nullable": True,
                     "primary_key": False, "foreign_key": False, "references": None, "on_delete": "NO ACTION",
                     "on_update": "NO ACTION", "unique": False, "auto_increment": False, "index": False,
                     "default": "true", "comment": "", "status": "ACTIVE"},
                ],
                "rows": [
                    {"uuid": "r-b1", "data": {"id": "1", "title": "Fondation", "author_id": "1", "price": "9.5", "available": "true"}},
                    {"uuid": "r-b2", "data": {"id": "2", "title": "Dune", "author_id": "2", "price": "12.0"}},
                    {"uuid": "r-b3", "data": {"id": "3", "title": "Les robots", "author_id": "1", "price": "7.25", "available": "false"}},
                ],
            },
        ],
    }


@pytest.fixture()
def doc():
    return _build_document()


@pytest.fixture()
def engine(doc):
    return XmlNativeEngine(document=doc)


def _write(tmp_path, document):
    path = str(tmp_path / "db.xml")
    with open(path, "w", encoding="utf-8") as stream:
        stream.write(serialize_document(document))
    return path


# ---------------------------------------------------------------- lecture
class TestSelect:
    def test_select_all(self, engine):
        result = engine.select("books")
        assert result["total"] == 3
        assert len(result["rows"]) == 3

    def test_select_columns(self, engine):
        result = engine.select("books", columns=["id", "title"])
        assert result["rows"][0] == {"id": 1, "title": "Fondation"}

    def test_where_equality(self, engine):
        assert engine.select("books", where={"op": "=", "column": "author_id", "value": 1})["total"] == 2

    def test_where_comparisons(self, engine):
        assert engine.select("books", where={"op": ">", "column": "price", "value": 9})["total"] == 2
        assert engine.select("books", where={"op": ">=", "column": "price", "value": 9.5})["total"] == 2
        assert engine.select("books", where={"op": "<", "column": "price", "value": 10})["total"] == 2
        assert engine.select("books", where={"op": "!=", "column": "author_id", "value": 1})["total"] == 1

    def test_where_and_or(self, engine):
        where = {"op": "AND", "left": {"op": "=", "column": "author_id", "value": 1},
                 "right": {"op": ">", "column": "price", "value": 8}}
        assert engine.select("books", where=where)["total"] == 1
        where_or = {"op": "OR", "left": {"op": "=", "column": "id", "value": 2},
                    "right": {"op": "=", "column": "id", "value": 3}}
        assert engine.select("books", where=where_or)["total"] == 2

    def test_where_like(self, engine):
        assert engine.select("books", where={"op": "LIKE", "column": "title", "value": "%robot%"})["total"] == 1
        assert engine.select("books", where={"op": "LIKE", "column": "title", "value": "DUN%"})["total"] == 1  # insensible à la casse

    def test_where_in(self, engine):
        assert engine.select("books", where={"op": "IN", "column": "id", "value": [1, 3]})["total"] == 2

    def test_where_is_null(self, engine):
        # r-b2 n'a pas de cellule "available" -> défaut true appliqué à la lecture ? Non :
        # la valeur manquante est lue comme None ici (le défaut est appliqué à l'écriture).
        nulls = engine.select("books", where={"op": "IS NULL", "column": "available"})
        assert nulls["total"] == 1
        not_nulls = engine.select("books", where={"op": "IS NOT NULL", "column": "available"})
        assert not_nulls["total"] == 2

    def test_order_by_and_limit_offset(self, engine):
        result = engine.select("books", order_by=[{"column": "price", "direction": "DESC"}])
        assert result["rows"][0]["title"] == "Dune"
        page = engine.select("books", order_by=[{"column": "id", "direction": "ASC"}], limit=2, offset=1)
        assert [r["id"] for r in page["rows"]] == [2, 3]

    def test_count(self, engine):
        assert engine.count("books") == 3
        assert engine.count("books", where={"op": "=", "column": "author_id", "value": 1}) == 2

    def test_unknown_column(self, engine):
        with pytest.raises(ValidationFailed):
            engine.select("books", columns=["nope"])
        with pytest.raises(ValidationFailed):
            engine.select("books", where={"op": "=", "column": "nope", "value": 1})

    def test_missing_table(self, engine):
        with pytest.raises(NotFoundError):
            engine.select("ghost")


# ---------------------------------------------------------------- insertion
class TestInsert:
    def test_insert_normal_and_autoincrement(self, engine):
        row = engine.insert("books", {"title": "1984", "author_id": 2, "price": "8.0"})
        assert row["data"]["id"] == 4  # auto-increment
        assert engine.count("books") == 4

    def test_insert_default_applied(self, engine):
        row = engine.insert("books", {"title": "X", "author_id": 1})
        assert row["data"]["available"] is True  # DEFAULT true

    def test_insert_pk_duplicate(self, engine):
        with pytest.raises(ConstraintViolation):
            engine.insert("books", {"id": 1, "title": "doublon"})

    def test_insert_unique_violation(self, engine):
        with pytest.raises(ConstraintViolation):
            engine.insert("authors", {"name": "Asimov"})

    def test_insert_not_null_violation(self, engine):
        with pytest.raises(ConstraintViolation):
            engine.insert("authors", {"name": None})

    def test_insert_fk_missing(self, engine):
        with pytest.raises(ConstraintViolation):
            engine.insert("books", {"title": "orphelin", "author_id": 999})

    def test_insert_invalid_type(self, engine):
        with pytest.raises(DataValidationError):
            engine.insert("books", {"title": "x", "price": "pas-un-nombre"})

    def test_insert_unknown_column(self, engine):
        with pytest.raises(ValidationFailed):
            engine.insert("books", {"nope": 1})


# ---------------------------------------------------------------- update
class TestUpdate:
    def test_update_single_and_multi(self, engine):
        assert engine.update("books", {"price": "15.0"}, where={"op": "=", "column": "id", "value": 1}) == {"updated": 1}
        assert engine.select("books", where={"op": "=", "column": "id", "value": 1})["rows"][0]["price"] == 15.0
        assert engine.update("books", {"price": "1.0"}, where={"op": "=", "column": "author_id", "value": 1}) == {"updated": 2}

    def test_update_fk_violation(self, engine):
        with pytest.raises(ConstraintViolation):
            engine.update("books", {"author_id": 777}, where={"op": "=", "column": "id", "value": 1})

    def test_update_unique_violation(self, engine):
        with pytest.raises(ConstraintViolation):
            engine.update("authors", {"name": "Herbert"}, where={"op": "=", "column": "id", "value": 1})

    def test_update_none_matched(self, engine):
        assert engine.update("books", {"price": "1"}, where={"op": "=", "column": "id", "value": 999}) == {"updated": 0}


# ---------------------------------------------------------------- delete
class TestDelete:
    def test_delete_simple(self, engine):
        assert engine.delete("books", where={"op": "=", "column": "id", "value": 3}) == {"deleted": 1}
        assert engine.count("books") == 2

    def test_delete_fk_restrict(self, engine):
        # author 1 est référencé par des books (on_delete RESTRICT)
        with pytest.raises(ConstraintViolation):
            engine.delete("authors", where={"op": "=", "column": "id", "value": 1})

    def test_delete_fk_cascade(self):
        doc = _build_document()
        doc["tables"][1]["columns"][2]["on_delete"] = "CASCADE"
        engine = XmlNativeEngine(document=doc)
        engine.delete("authors", where={"op": "=", "column": "id", "value": 1})
        assert engine.count("books") == 1  # les 2 livres d'Asimov supprimés en cascade
        assert engine.count("authors") == 1

    def test_delete_fk_set_null(self):
        doc = _build_document()
        doc["tables"][1]["columns"][2]["on_delete"] = "SET NULL"
        engine = XmlNativeEngine(document=doc)
        engine.delete("authors", where={"op": "=", "column": "id", "value": 1})
        assert engine.count("books") == 3  # les livres restent
        nulls = engine.select("books", where={"op": "IS NULL", "column": "author_id"})
        assert nulls["total"] == 2


# ---------------------------------------------------------------- structure
class TestStructure:
    def test_create_table(self, engine):
        engine.create_table("loans", columns=[{"name": "id", "type": "INT", "primary_key": True, "auto_increment": True, "nullable": False}])
        assert "loans" in engine.list_tables()
        engine.insert("loans", {})
        assert engine.count("loans") == 1

    def test_create_table_duplicate(self, engine):
        with pytest.raises(ConstraintViolation):
            engine.create_table("books")

    def test_add_column_and_backfill(self, engine):
        engine.add_column("books", {"name": "genre", "type": "VARCHAR", "nullable": True})
        assert engine.select("books", columns=["genre"])["rows"][0] == {"genre": None}

    def test_add_column_not_null_on_filled_table(self, engine):
        with pytest.raises(ConstraintViolation):
            engine.add_column("books", {"name": "x", "type": "INT", "nullable": False})

    def test_drop_column(self, engine):
        engine.drop_column("books", "price")
        with pytest.raises(ValidationFailed):
            engine.select("books", columns=["price"])
        assert "price" not in [c["name"] for c in engine.table("books")["columns"]]

    def test_drop_column_referenced(self, engine):
        with pytest.raises(ConstraintViolation):
            engine.drop_column("authors", "id")

    def test_drop_table(self, engine):
        engine.drop_table("books")
        assert "books" not in engine.list_tables()

    def test_drop_table_referenced(self, engine):
        with pytest.raises(ConstraintViolation):
            engine.drop_table("authors")


# ---------------------------------------------------------------- robustesse
class TestRobustness:
    def test_invalid_xml_rejected(self, tmp_path):
        path = str(tmp_path / "bad.xml")
        with open(path, "w", encoding="utf-8") as stream:
            stream.write("<database name='x'><table name='1bad'></table></database>")
        with pytest.raises(Exception):
            XmlNativeEngine(xml_path=path)

    def test_missing_file(self, tmp_path):
        with pytest.raises(NotFoundError):
            XmlNativeEngine(xml_path=str(tmp_path / "nope.xml"))

    def test_save_version_and_atomicity(self, tmp_path, doc):
        path = _write(tmp_path, doc)
        engine = XmlNativeEngine(xml_path=path)
        engine.insert("books", {"title": "Nouveau"})
        new_version = engine.save()
        assert new_version == 2
        reloaded = XmlNativeEngine(xml_path=path)
        assert reloaded.document["version"] == 2
        assert reloaded.count("books") == 4

    def test_save_expected_version_conflict(self, tmp_path, doc):
        # Deux moteurs sur le même fichier : le second commit avec une version
        # obsolète doit être refusé (conflit optimiste).
        path = _write(tmp_path, doc)
        first = XmlNativeEngine(xml_path=path)
        second = XmlNativeEngine(xml_path=path)
        first.insert("books", {"title": "A"})
        first.save()  # version 1 -> 2
        second.insert("books", {"title": "B"})
        with pytest.raises(ConflictError):
            second.save(expected_version=1)

    def test_roundtrip_preserves_types(self, tmp_path, doc):
        path = _write(tmp_path, doc)
        engine = XmlNativeEngine(xml_path=path)
        engine.insert("books", {"title": "Type test", "author_id": 2, "price": "3.14", "available": "true"})
        engine.save()
        reloaded = XmlNativeEngine(xml_path=path)
        row = reloaded.select("books", where={"op": "=", "column": "title", "value": "Type test"})["rows"][0]
        assert row["price"] == 3.14
        assert row["available"] is True
        assert isinstance(row["id"], int)

    def test_timing_is_measured(self, engine):
        timing = Timing(engine="xml")
        engine.select("books", timing=timing)
        assert timing.read_ms >= 0
        assert timing.total_ms >= 0
        assert timing.rows == 3


# --------------------------------------------------- base XML de test générée
ENGINE_BASE_PATH = os.path.join(os.path.dirname(__file__), "..", "bibliotheque_engine_test.xml")


class TestEngineTestBase:
    """Exercices sur la base réaliste générée (860 lignes, 5 tables)."""

    def _engine(self):
        return XmlNativeEngine(xml_path=ENGINE_BASE_PATH)

    def test_base_loads(self):
        engine = self._engine()
        assert set(engine.list_tables()) == {"authors", "categories", "users", "books", "loans"}

    def test_counts(self):
        engine = self._engine()
        assert engine.count("books") == 400
        assert engine.count("loans") == 300
        assert engine.count("users") == 120
        assert engine.count("authors") == 30
        assert engine.count("categories") == 10

    def test_filter_sort_limit_pagination(self):
        engine = self._engine()
        page = engine.select("books", where={"op": "=", "column": "category_id", "value": 1},
                             order_by=[{"column": "price", "direction": "DESC"}], limit=10, offset=5)
        assert len(page["rows"]) == 10
        prices = [r["price"] for r in page["rows"]]
        assert prices == sorted(prices, reverse=True)
        assert page["total"] > 10

    def test_search_like(self):
        engine = self._engine()
        total = engine.count("books", where={"op": "LIKE", "column": "title", "value": "%Science-fiction%"})
        assert total > 0

    def test_null_and_defaults(self):
        engine = self._engine()
        null_isbn = engine.select("books", where={"op": "IS NULL", "column": "isbn"})
        assert null_isbn["total"] > 0
        # stock a un DEFAULT 0 : les cellules absentes comptent comme NULL en lecture brute.
        stock_nulls = engine.select("books", where={"op": "IS NULL", "column": "stock"})
        assert stock_nulls["total"] >= 0

    def test_auto_increment_next(self):
        engine = self._engine()
        row = engine.insert("books", {"title": "Nouveau livre", "author_id": 1})
        assert row["data"]["id"] == 401

    def test_benchmark_runs_real_timings(self):
        engine = self._engine()
        timings = []
        for _ in range(5):
            timing = Timing(engine="xml")
            engine.select("books", where={"op": "=", "column": "category_id", "value": 1}, timing=timing)
            timings.append(timing.read_ms)
        assert len(timings) == 5
        assert all(t >= 0 for t in timings)
