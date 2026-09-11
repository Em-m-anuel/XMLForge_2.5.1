"""Import XML/SQL vers le Data Plane XML (Phase 6J-B). Aucune SQLite."""

from __future__ import annotations

import uuid as uuid_lib

from ..data_plane import get_data_plane
from ..xml_engine.document import parse_document, serialize_document
from ..converters.sql_to_xml import convert_sql_to_xml
from .database_service import DatabaseService
from .history_service import HistoryService
from .audit_service import AuditService
from ..socket_events import emit_import_xml


class ImportService:
    @staticmethod
    def import_xml(xml_content, database_name, creator_id, creator_name,
                   description="Import XML", ip_address=None, comment="", scope="PERSONAL"):
        try:
            document = parse_document(xml_content, validate=True)
            if database_name:
                document["name"] = database_name
            if description and description != "Import XML":
                document["description"] = description
            if comment:
                document["comment"] = comment
            database = DatabaseService.create(
                name=document["name"], description=document.get("description", ""),
                creator_id=creator_id, creator_name=creator_name,
                comment=document.get("comment", ""), ip_address=ip_address, scope=scope,
            )
            # Un import crée un nouveau graphe : les UUID/internal_id du fichier
            # source ne doivent pas entrer en collision avec une base existante.
            document["internal_id"] = database.id
            document["uuid"] = database.uuid
            document["owner_id"] = creator_id
            document["scope"] = str(scope).upper()
            for table in document.get("tables", []):
                table["internal_id"] = get_data_plane().allocate_object_id()
                table["uuid"] = str(uuid_lib.uuid4())
                for column in table.get("columns", []):
                    column["internal_id"] = get_data_plane().allocate_object_id()
                    column["uuid"] = str(uuid_lib.uuid4())
                for row in table.get("rows", []):
                    row["internal_id"] = get_data_plane().allocate_object_id()
                    row["uuid"] = str(uuid_lib.uuid4())

            def replacement(current):
                version = current.get("version", 1)
                current.clear()
                current.update(document)
                current["version"] = version

            get_data_plane().mutate(database.id, replacement, expected_version=1)
            database = get_data_plane().get_database(database.id)
            HistoryService.log(
                user_id=creator_id, user_name=creator_name, action_type="a importé",
                element_type="base", element_name=database.name, database_id=database.id,
                ip_address=ip_address,
                after={"tables": len(document["tables"]),
                       "rows": sum(len(t.get('rows', [])) for t in document["tables"])},
            )
            AuditService.log(
                user_id=creator_id, user_name=creator_name, ip_address=ip_address,
                action="IMPORT_XML", element_type="base", element_name=database.name,
                meta={"database_id": database.id},
            )
            emit_import_xml(database.to_dict(include_key=False), creator_name)
            return database, None
        except Exception as exc:
            try:
                if 'database' in locals() and database is not None:
                    get_data_plane().delete_storage(database.id)
                    from ..xml_control.service import XmlControlPlaneService
                    XmlControlPlaneService.from_config(
                        get_data_plane().config).delete_database(database.id)
            except Exception:
                pass
            return None, f"Erreur import XML: {exc}"

    @staticmethod
    def import_sql(sql_content, database_name, creator_id, creator_name,
                   description="Import SQL", ip_address=None, comment="", scope="PERSONAL"):
        try:
            xml_content = convert_sql_to_xml(sql_content,
                                             database_name=database_name or "imported_database")
        except Exception as exc:
            return None, f"Erreur parsing SQL: {exc}"
        return ImportService.import_xml(
            xml_content, database_name, creator_id, creator_name,
            description=description, ip_address=ip_address, comment=comment, scope=scope,
        )
