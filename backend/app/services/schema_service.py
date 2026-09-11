"""Introspection du schéma — lecture exclusive du Data Plane XML (Phase 6J-B)."""

from __future__ import annotations

from ..errors import NotFoundError, PermissionDenied
from ..data_plane import get_data_plane
from ..services.permission_service import PermissionService


class SchemaService:
    @staticmethod
    def _column_schema(column):
        return {
            "name": column.get("name"),
            "type": column.get("type"),
            "length": column.get("length", "-"),
            "nullable": bool(column.get("nullable", True)),
            "primary_key": bool(column.get("primary_key")),
            "foreign_key": bool(column.get("foreign_key")),
            "references": column.get("references"),
            "unique": bool(column.get("unique")),
            "default": column.get("default"),
            "auto_increment": bool(column.get("auto_increment")),
            "index": bool(column.get("index")),
            "comment": column.get("comment", ""),
        }

    @staticmethod
    def _table_schema(table):
        columns = [SchemaService._column_schema(c) for c in table.get("columns", [])
                   if c.get("status") != "ARCHIVED"]
        indexes = [{"name": i.get("name"), "columns": list(i.get("columns", [])),
                    "unique": bool(i.get("unique"))} for i in table.get("indexes", [])]
        foreign_keys = [
            {"column": c.get("name"), "references": c.get("references"),
             "on_delete": c.get("on_delete", "NO ACTION"), "on_update": c.get("on_update", "NO ACTION")}
            for c in table.get("columns", []) if c.get("references")
        ]
        for constraint in table.get("constraints", []):
            if constraint.get("kind") == "foreign-key":
                foreign_keys.append({
                    "columns": list(constraint.get("columns", [])),
                    "references": f"{constraint.get('references_table')}({','.join(constraint.get('references_columns', []))})",
                    "on_delete": constraint.get("on_delete", "NO ACTION"),
                    "on_update": constraint.get("on_update", "NO ACTION"),
                })
        return {
            "name": table.get("name"),
            "description": table.get("description", ""),
            "protected": bool(table.get("protected")),
            "status": table.get("status", "ACTIVE"),
            "columns": columns,
            "indexes": indexes,
            "foreign_keys": foreign_keys,
            "primary_key": [c.get("name") for c in table.get("columns", []) if c.get("primary_key")],
            "row_count": len(table.get("rows", [])),
        }

    @staticmethod
    def _from_document(document):
        return {
            "database": document.get("name"),
            "description": document.get("description", ""),
            "scope": document.get("scope", "PERSONAL"),
            "status": document.get("status", "ACTIVE"),
            "version": document.get("version", 1),
            "tables": [SchemaService._table_schema(t) for t in document.get("tables", [])],
        }

    @staticmethod
    def get(database_id, user_id):
        from ..control_plane import get_backend
        database = get_backend().get_database(database_id)
        if not database:
            raise NotFoundError("Base introuvable")
        if not PermissionService.can_database(user_id, database_id, "read"):
            raise PermissionDenied("Accès refusé")
        document = get_data_plane().read_document(database_id)
        return SchemaService._from_document(document)
