"""Data Plane XML — backend 100% XML (Phase 6I).

Aucune dépendance SQLAlchemy : les bases sont résolues via le catalogue du
Control Plane (``catalog.xml``), les tables/colonnes/lignes via les documents
Data Plane XML, et les mutations passent par le moteur XML natif + écriture
atomique (sans ``_sync_catalog`` ni projection SQLite).
"""

from __future__ import annotations

import copy
import os
import uuid as uuid_lib

from ..control_plane import views
from ..errors import NotFoundError
from ..utils.helpers import generate_key_identifier, slugify
from ..xml_control import store
from ..xml_control.service import XmlControlPlaneService
from ..xml_engine.document import parse_document, serialize_document
from ..xml_engine.storage import atomic_write, database_lock, safe_unlink
from ..xml_engine.xml_native import XmlNativeEngine


class XmlDataPlane:
    name = "xml"

    def __init__(self, config):
        self.config = config
        self.xml_root = config.get("XML_STORAGE_FOLDER")
        self.cp_service = XmlControlPlaneService(
            storage_folder=config.get("CONTROL_STORAGE_FOLDER"),
            common_permission_default=config.get("COMMON_PERMISSION_DEFAULT", "VIEW"))
        # Catalogue (bases) du Control Plane.
        from ..control_plane.xml_backend import XmlControlPlane
        self.cp = XmlControlPlane.from_config(config)

    # ------------------------------------------------------------------ bases
    def get_database(self, database_id):
        return self.cp.get_database(database_id)

    def list_databases(self, include_archived=True):
        return self.cp.list_databases(include_archived=include_archived)

    def get_database_by_key(self, key_identifier):
        return self.cp.get_database_by_key(key_identifier)

    def _database_view(self, database_id):
        view = self.get_database(database_id)
        if view is None:
            raise NotFoundError("Base introuvable")
        return view

    def xml_path(self, database):
        """Chemin absolu du fichier XML Data Plane d'une base."""
        xml_path = getattr(database, "xml_file_path", None)
        if xml_path and os.path.isabs(xml_path):
            return xml_path
        stem = f"{database.id}_{slugify(database.name) or 'database'}"
        return os.path.join(self.xml_root, stem + ".xml")

    # ------------------------------------------------------------------ document IO
    def read_document(self, database_id):
        database = self._database_view(database_id)
        path = self.xml_path(database)
        if not os.path.exists(path):
            raise NotFoundError(f"Fichier XML Data Plane introuvable: {path}")
        with open(path, "rb") as stream:
            return parse_document(stream.read(), validate=True)

    def mutate(self, database_id, mutator, expected_version=None):
        """Mutation atomique d'un document Data Plane (aucun ORM, aucune projection)."""
        database = self._database_view(database_id)
        path = self.xml_path(database)
        if not os.path.exists(path):
            raise NotFoundError(f"Fichier XML Data Plane introuvable: {path}")
        with database_lock(path + ".lock"):
            with open(path, "rb") as stream:
                current = parse_document(stream.read(), validate=True)
            current_version = int(current.get("version", 1))
            if expected_version is not None and int(expected_version) != current_version:
                from ..errors import ConflictError
                raise ConflictError(
                    f"Conflit de version: attendu {expected_version}, version courante {current_version}",
                    details={"current_version": current_version})
            document = copy.deepcopy(current)
            result = mutator(document)
            document["version"] = current_version + 1
            document["internal_id"] = database.id
            document["owner_id"] = getattr(database, "owner_id", None) or \
                getattr(database, "creator_id", None)
            xml_content = serialize_document(document)  # valide XSD
            atomic_write(path, xml_content)
        # Miroir catalogue (document_version / checksum / sync_status).
        self._mirror_catalog(database_id, document["version"], xml_content)
        return document, result

    def write_new_document(self, database_id, name, description="", scope="PERSONAL"):
        """Écrit un document Data Plane vide (création de base)."""
        import uuid as _uuid
        document = {
            "internal_id": database_id, "uuid": str(_uuid.uuid4()), "name": name,
            "description": description or "", "comment": "", "status": "ACTIVE",
            "scope": scope, "owner_id": None, "version": 1, "generator": "XMLForge",
            "created_at": "", "author": "", "tables": [],
        }
        path = os.path.join(self.xml_root, f"{database_id}_{slugify(name) or 'database'}.xml")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        content = serialize_document(document)
        atomic_write(path, content)
        return path

    def delete_storage(self, database_id):
        database = self._database_view(database_id)
        path = self.xml_path(database)
        with database_lock(path + ".lock"):
            safe_unlink(path, missing_ok=True)

    def _mirror_catalog(self, database_id, document_version, xml_content):
        record = self.cp_service.get_database(database_id)
        if record is None:
            return
        record.document_version = document_version
        record.xml_checksum = store.checksum_bytes(xml_content)
        record.sync_status = "SYNCED"
        self.cp_service.update_database(record)

    # ------------------------------------------------------------------ ids
    def allocate_object_id(self):
        return self.cp_service.allocate_object_id(xml_storage_folder=self.xml_root)

    # ------------------------------------------------------------------ tables
    def _table_view(self, database_id, table_doc):
        return views.TableView(
            id=table_doc.get("internal_id"), uuid=table_doc.get("uuid"),
            name=table_doc["name"], description=table_doc.get("description", ""),
            database_id=database_id, creator_id=table_doc.get("creator_id"),
            creator_name=table_doc.get("creator_name"),
            created_at=table_doc.get("created_at"), updated_at=table_doc.get("updated_at"),
            status=table_doc.get("status", "ACTIVE"),
            is_protected=bool(table_doc.get("protected")),
            file_identifier=table_doc.get("file_identifier"),
            columns_count=len([c for c in table_doc.get("columns", [])
                              if c.get("status") != "ARCHIVED"]))

    def list_tables(self, database_id):
        document = self.read_document(database_id)
        return [self._table_view(database_id, t) for t in document.get("tables", [])]

    def resolve_table(self, database_id, table_id_or_name):
        """Résout une table par id (internal_id) ou nom, dans une base donnée."""
        document = self.read_document(database_id)
        if isinstance(table_id_or_name, int) or str(table_id_or_name).isdigit():
            tid = int(table_id_or_name)
            for t in document.get("tables", []):
                if t.get("internal_id") == tid:
                    return self._table_view(database_id, t)
        name = str(table_id_or_name)
        for t in document.get("tables", []):
            if t["name"] == name or (t["name"].lower() == name.lower()):
                return self._table_view(database_id, t)
        return None

    def table_by_id(self, table_id):
        """Résout une table par id global (scan des documents)."""
        try:
            table_id = int(table_id)
        except (TypeError, ValueError):
            return None
        for database in self.list_databases():
            table = self.resolve_table(database.id, table_id)
            if table is not None:
                return table
        return None

    def table_document(self, database_id, table_id_or_name):
        """Retourne (document, table_doc) pour la table demandée."""
        document = self.read_document(database_id)
        table = self.resolve_table(database_id, table_id_or_name)
        if table is None:
            raise NotFoundError("Table active introuvable")
        for t in document.get("tables", []):
            if t.get("internal_id") == table.id or t["name"] == table.name:
                return document, t
        raise NotFoundError("Table absente du document XML")

    # ------------------------------------------------------------------ schéma
    def schema(self, database_id):
        document = self.read_document(database_id)
        from ..services.schema_service import SchemaService
        return SchemaService._from_document(document)

    # ------------------------------------------------------------------ CRUD lignes / DDL
    def execute(self, database_id, statement, user_id=None, provided_key=None,
                expected_version=None, timing=None):
        """Exécute un AST SQL (lecture/écriture) sur le document XML.

        Pour les écritures : le mutateur applique l'opération sur une copie du
        document via ``XmlNativeEngine`` ; l'écriture est atomique. Les lectures
        ne modifient pas le fichier.
        """
        document = self.read_document(database_id)
        operation = statement.get("operation")
        holder = {}

        if operation == "select":
            engine = XmlNativeEngine(document=document)
            result = engine.select_statement(statement, timing=timing)
            select_list = statement.get("select_list") or []
            if (len(select_list) == 1 and select_list[0].get("kind") == "aggregate"
                    and select_list[0]["aggregate"]["func"] == "COUNT"
                    and not statement.get("group_by")):
                agg = select_list[0]["aggregate"]
                key = f"COUNT({agg['arg']})"
                value = result["rows"][0].get(key) if result["rows"] else 0
                return {"count": value, "table": statement["table"]}
            return result

        # Écriture : mutation atomique du document.
        def mutation(doc):
            engine = XmlNativeEngine(document=doc)
            if operation == "insert":
                rows = engine.resolve_insert_rows(statement["table"], statement)
                if len(rows) == 1:
                    holder["result"] = {"inserted": 1, "row": engine.insert(statement["table"], rows[0])}
                else:
                    holder["result"] = engine.insert_many(statement["table"], rows)
            elif operation == "update":
                holder["result"] = engine.update(statement["table"], statement.get("data"),
                                                 where=statement.get("where"))
            elif operation == "delete":
                holder["result"] = engine.delete(statement["table"], where=statement.get("where"))
            elif operation == "create_table":
                engine.create_table(statement["table"], columns=statement.get("columns"))
                holder["result"] = {"created": statement["table"]}
            elif operation == "drop_table":
                engine.drop_table(statement["table"])
                holder["result"] = {"dropped": statement["table"]}
            elif operation == "add_column":
                engine.add_column(statement["table"], statement["column"])
                holder["result"] = {"added": statement["column"]["name"], "table": statement["table"]}
            elif operation == "drop_column":
                engine.drop_column(statement["table"], statement["column_name"])
                holder["result"] = {"dropped_column": statement["column_name"], "table": statement["table"]}
            elif operation == "modify_column":
                engine.modify_column(statement["table"], statement["column"]["name"], statement["column"])
                holder["result"] = {"modified": statement["column"]["name"], "table": statement["table"]}
            elif operation == "rename_table":
                engine.rename_table(statement["table"], statement["new_name"])
                holder["result"] = {"renamed": statement["table"], "new_name": statement["new_name"]}
            elif operation == "create_index":
                index = engine.create_index(statement["table"], statement["name"],
                                            statement["columns"], unique=statement.get("unique", False))
                holder["result"] = {"index": index}
            elif operation == "drop_index":
                engine.drop_index(statement.get("table"), statement["name"])
                holder["result"] = {"dropped_index": statement["name"]}
            else:
                raise NotFoundError(f"Opération non supportée par le Data Plane XML: {operation}")
            return None

        self.mutate(database_id, mutation, expected_version=expected_version)
        return holder["result"]
