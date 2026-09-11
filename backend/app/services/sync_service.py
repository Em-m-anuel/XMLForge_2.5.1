"""Synchronisation autoritaire XML -> document canonique (Phase 6J-B)."""

from __future__ import annotations

from ..data_plane import get_data_plane, get_table
from .permission_service import PermissionService
from .unlock_service import UnlockService
from .history_service import HistoryService
from .audit_service import AuditService
from ..socket_events import emit_modification
from ..xml_engine.document import parse_document


class SyncService:
    @staticmethod
    def sync_database_from_xml(database_id, xml_content, user_id, user_name, ip_address=None,
                               provided_key=None, expected_version=None):
        database = get_data_plane().get_database(database_id)
        if not database:
            return None, "Base introuvable"
        if not PermissionService.can_database(user_id, database_id, "ddl"):
            return None, "Permission DDL refusée"
        if database.status == "ARCHIVED":
            return None, "Base archivée"
        try:
            incoming = parse_document(xml_content, validate=True)
            expected_version = expected_version if expected_version is not None else incoming.get('version')
            for table in get_data_plane().list_tables(database_id):
                if table.is_protected:
                    allowed, message = UnlockService.check_protection(user_id, table, provided_key)
                    if not allowed:
                        return None, message
            before_version = database.document_version

            def replacement(current):
                version = current.get("version", 1)
                current.clear()
                current.update(incoming)
                current["version"] = version

            document, _ = get_data_plane().mutate(database_id, replacement,
                                                  expected_version=expected_version)
            database = get_data_plane().get_database(database_id)
            HistoryService.log(
                user_id=user_id, user_name=user_name, action_type="a synchronisé",
                element_type="base", element_name=database.name, database_id=database_id,
                ip_address=ip_address, before={"version": before_version},
                after={"version": document["version"]},
            )
            AuditService.log(
                user_id=user_id, user_name=user_name, ip_address=ip_address,
                action="SYNC_XML", element_type="base", element_name=database.name,
                meta={"database_id": database_id, "version": document["version"]},
            )
            emit_modification("base", database.to_dict(), user_name)
            return {
                "database": database.to_dict(include_key=False),
                "document_version": document["version"],
                "tables": len(document["tables"]),
                "projection": "XML_ONLY",
            }, None
        except Exception as exc:
            return None, str(exc)

    @staticmethod
    def sync_table_from_xml(table_id, xml_content, user_id, user_name, ip_address=None,
                            provided_key=None, expected_version=None):
        table = get_table(table_id)
        if not table:
            return None, "Table introuvable"
        database = get_data_plane().get_database(table.database_id)
        if not PermissionService.can_table(user_id, table_id, "ddl"):
            return None, "Permission DDL refusée"
        if table.status == "ARCHIVED" or (database and database.status == "ARCHIVED"):
            return None, "Table ou base archivée"
        allowed, message = UnlockService.check_protection(user_id, table, provided_key)
        if not allowed:
            return None, message
        try:
            if expected_version is None:
                return None, "expected_version ou en-tête If-Match requis pour synchroniser une table"
            incoming_document = parse_document(xml_content, validate=True)
            if not incoming_document["tables"]:
                return None, "Aucune table dans le XML"
            incoming = incoming_document["tables"][0]
            old_uuid = table.uuid

            def mutation(document):
                index = next((i for i, item in enumerate(document["tables"])
                              if item.get("uuid") == old_uuid), None)
                if index is None:
                    raise ValueError("Table absente du XML canonique")
                replacement = dict(incoming)
                replacement["uuid"] = old_uuid
                replacement["internal_id"] = table.id
                document["tables"][index] = replacement

            document, _ = get_data_plane().mutate(table.database_id, mutation,
                                                  expected_version=expected_version)
            table = get_table(table_id)
            AuditService.log(user_id=user_id, user_name=user_name, ip_address=ip_address,
                             action="SYNC_XML_TABLE", element_type="table", element_name=table.name,
                             meta={"table_id": table.id, "version": document["version"]})
            return {
                "table": table.to_dict(),
                "database": database.to_dict(),
                "document_version": document["version"],
                "projection": "XML_ONLY",
            }, None
        except Exception as exc:
            return None, str(exc)
