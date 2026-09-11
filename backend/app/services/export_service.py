"""Exports calculés depuis le Data Plane XML (Phase 6J-B). Aucune SQLite."""

from __future__ import annotations

import copy

from ..data_plane import get_data_plane, get_table
from ..xml_engine.document import serialize_document, serialize_table
from ..converters.xml_to_sql import convert_xml_to_sql
from .permission_service import PermissionService
from .audit_service import AuditService
from ..socket_events import emit_export_xml, emit_export_sql


class ExportService:
    @staticmethod
    def export_database_to_xml(database_id, user_id=None, user_name=None, ip_address=None,
                               include_secrets=True):
        database = get_data_plane().get_database(database_id)
        if not database:
            return None, "Base introuvable"
        if user_id is not None:
            action = "admin" if include_secrets else "read"
            if not PermissionService.can_database(user_id, database_id, action):
                return None, "Permission d'export refusée"
        try:
            document = get_data_plane().read_document(database_id)
            if not include_secrets:
                document = copy.deepcopy(document)
                for table in document["tables"]:
                    table["file_identifier"] = None
            content = serialize_document(document)
        except Exception as exc:
            return None, str(exc)
        if user_id:
            AuditService.log(user_id=user_id, user_name=user_name, ip_address=ip_address,
                             action="EXPORT_XML", element_type="base", element_name=database.name,
                             meta={"database_id": database_id})
            emit_export_xml(database_id, user_name or "unknown")
        return content, None

    @staticmethod
    def export_database_to_sql(database_id, user_id=None, user_name=None, ip_address=None):
        database = get_data_plane().get_database(database_id)
        if not database:
            return None, "Base introuvable"
        if user_id is not None and not PermissionService.can_database(user_id, database_id, "read"):
            return None, "Permission de lecture refusée"
        try:
            content = serialize_document(get_data_plane().read_document(database_id))
            sql = convert_xml_to_sql(content, database_name=database.name)
        except Exception as exc:
            return None, f"Erreur conversion XML->SQL: {exc}"
        if user_id:
            AuditService.log(user_id=user_id, user_name=user_name, ip_address=ip_address,
                             action="EXPORT_SQL", element_type="base", element_name=database.name,
                             meta={"database_id": database_id})
            emit_export_sql(database_id, user_name or "unknown")
        return sql, None

    @staticmethod
    def export_table_to_xml(table_id, user_id=None, user_name=None, ip_address=None,
                            include_rows=True):
        table = get_table(table_id)
        if not table:
            return None, "Table introuvable"
        if user_id is not None and not PermissionService.can_table(user_id, table_id, "admin"):
            return None, "Permission d'administration requise pour exporter la protection"
        try:
            document = get_data_plane().read_document(table.database_id)
            item = copy.deepcopy(next(t for t in document["tables"]
                                      if t.get("uuid") == table.uuid))
            if not include_rows:
                item["rows"] = []
            content = serialize_table(item)
        except Exception as exc:
            return None, str(exc)
        if user_id:
            AuditService.log(user_id=user_id, user_name=user_name, ip_address=ip_address,
                             action="EXPORT_XML_TABLE", element_type="table", element_name=table.name)
        return content, None

    @staticmethod
    def export_table_to_sql(table_id, user_id=None, user_name=None, ip_address=None):
        table = get_table(table_id)
        if not table:
            return None, "Table introuvable"
        if user_id is not None and not PermissionService.can_table(user_id, table_id, "read"):
            return None, "Permission de lecture refusée"
        try:
            document = get_data_plane().read_document(table.database_id)
            item = copy.deepcopy(next(t for t in document["tables"]
                                      if t.get("uuid") == table.uuid))
            database = get_data_plane().get_database(table.database_id)
            sql = convert_xml_to_sql(serialize_table(item),
                                     database_name=database.name if database else None)
            return sql, None
        except Exception as exc:
            return None, f"Erreur conversion XML->SQL table: {exc}"
