"""Exécuteur de requêtes SQL -> moteur XML natif.

Transforme l'AST produit par ``query/sql_parser.py`` en appels au moteur
``xml_engine/xml_native.py``. Cette couche est volontairement indépendante de
SQLAlchemy et de SQLite : elle ne reçoit qu'un document XMLForge (dict) et une
requête SQL.

Chaîne de responsabilité :

    SQL Query -> Parser (sql_parser) -> AST -> XmlQueryExecutor -> XmlNativeEngine -> document XML
"""

from __future__ import annotations

from ..errors import ValidationFailed
from ..xml_engine.xml_native import Timing, XmlNativeEngine
from .sql_parser import parse_sql_statement


class XmlQueryExecutor:
    """Exécute un AST SQL sur un document XMLForge via le moteur natif."""

    @staticmethod
    def execute_document(document, sql, *, timing=None):
        """Exécute ``sql`` contre ``document`` (dict XMLForge) et retourne un résultat."""
        engine = XmlNativeEngine(document=document)
        return XmlQueryExecutor.execute_engine(engine, sql, timing=timing)

    @staticmethod
    def execute_engine(engine, sql, *, timing=None):
        statement = parse_sql_statement(sql)
        operation = statement["operation"]

        if operation == "select":
            result = engine.select_statement(statement, timing=timing)
            select_list = statement.get("select_list") or []
            # Cas spécial historique : COUNT(*) / COUNT(col) seul -> {"count": N, "table": t}
            if (len(select_list) == 1 and select_list[0].get("kind") == "aggregate"
                    and select_list[0]["aggregate"]["func"] == "COUNT"
                    and not statement.get("group_by")):
                agg = select_list[0]["aggregate"]
                alias = select_list[0].get("alias")
                key = alias or f"COUNT({agg['arg']})"
                value = result["rows"][0].get(key) if result["rows"] else 0
                return {"count": value, "table": statement["table"]}
            return result

        if operation == "insert":
            rows = engine.resolve_insert_rows(statement["table"], statement)
            if len(rows) == 1:
                row = engine.insert(statement["table"], rows[0], timing=timing)
                return {"inserted": 1, "row": row}
            result = engine.insert_many(statement["table"], rows, timing=timing)
            return {"inserted": result["inserted"]}

        if operation == "update":
            return engine.update(statement["table"], statement["data"], where=statement.get("where"), timing=timing)

        if operation == "delete":
            return engine.delete(statement["table"], where=statement.get("where"), timing=timing)

        # DDL
        if operation == "create_table":
            engine.create_table(statement["table"], columns=statement.get("columns"))
            return {"created": statement["table"]}
        if operation == "drop_table":
            engine.drop_table(statement["table"])
            return {"dropped": statement["table"]}
        if operation == "add_column":
            engine.add_column(statement["table"], statement["column"])
            return {"added": statement["column"]["name"], "table": statement["table"]}
        if operation == "drop_column":
            engine.drop_column(statement["table"], statement["column_name"])
            return {"dropped_column": statement["column_name"], "table": statement["table"]}
        if operation == "modify_column":
            engine.modify_column(statement["table"], statement["column"]["name"], statement["column"])
            return {"modified": statement["column"]["name"], "table": statement["table"]}
        if operation == "rename_table":
            engine.rename_table(statement["table"], statement["new_name"])
            return {"renamed": statement["table"], "new_name": statement["new_name"]}
        if operation == "create_index":
            index = engine.create_index(statement["table"], statement["name"], statement["columns"], unique=statement.get("unique", False))
            return {"index": index}
        if operation == "drop_index":
            engine.drop_index(statement.get("table"), statement["name"])
            return {"dropped_index": statement["name"]}
        if operation == "create_database":
            raise ValidationFailed(
                "CREATE DATABASE n'est pas exécutable sur un document existant: "
                "créez la base via POST /api/databases ou DatabaseService.create")

        raise ValidationFailed(f"Opération non supportée par le moteur XML: {operation}")


__all__ = ["XmlQueryExecutor", "Timing"]
