"""Services Data Plane en mode XML pur (Phase 6I).

Implémentations des opérations Data Plane (bases, tables, colonnes, lignes)
exclusivement sur XML : résolution via le catalogue Control Plane + documents
Data Plane XML, mutations via le moteur XML natif + écriture atomique.
Contrats et erreurs identiques à l'ancienne implémentation (REST/TCP inchangés).
"""

from __future__ import annotations

import json
import uuid as uuid_lib

from ..control_plane import get_backend
from ..errors import NotFoundError
from ..utils.helpers import now_utc
from ..xml_control import records as R
from ..xml_control.service import XmlControlPlaneService
from . import get_data_plane


def _dp():
    return get_data_plane()


def _database_view(database_id):
    view = _dp().get_database(database_id)
    if view is None:
        raise NotFoundError("Base introuvable")
    return view


def _cp_service():
    dp = _dp()
    return dp.cp_service


def _emit_new_database(data, user_name):
    from ..socket_events import emit_new_database
    emit_new_database(data, user_name)


# --------------------------------------------------------------------------
# DATABASES
# --------------------------------------------------------------------------

def create_database(name, description, creator_id, creator_name, comment="",
                    ip_address=None, scope="PERSONAL", common_permission=None):
    from ..services.permission_service import PermissionService
    from ..services.history_service import HistoryService
    from ..services.audit_service import AuditService

    scope = str(scope or "PERSONAL").upper()
    if scope not in {"PERSONAL", "COMMON"}:
        raise ValueError("scope doit être PERSONAL ou COMMON")
    if common_permission is not None:
        common_permission = str(common_permission).upper()
        if common_permission not in {"VIEW", "EDIT", "MANAGE"}:
            raise ValueError("common_permission doit être VIEW, EDIT ou MANAGE")
    if scope == "PERSONAL" and common_permission is not None:
        raise ValueError("common_permission est réservé aux bases COMMON")

    cp = _cp_service()
    # Unicité (owner, name) — règle identique à SQLite.
    for other in cp.list_databases():
        if (other.owner_id or other.creator_id) == creator_id and other.name == name:
            raise ValueError("Une base de ce nom existe déjà pour ce propriétaire")

    database_id = cp.allocate_object_id()
    # key_identifier unique
    key = None
    from ..utils.helpers import generate_key_identifier
    for _ in range(10):
        candidate = generate_key_identifier()
        if _dp().get_database_by_key(candidate) is None:
            key = candidate
            break
    if not key:
        raise RuntimeError("Impossible de générer une clé de base unique")

    record = R.DatabaseRecord(
        internal_id=database_id, uuid=str(uuid_lib.uuid4()), name=name,
        description=description or "", comment=comment or "", creator_id=creator_id,
        owner_id=creator_id, scope=R._to_scope(scope),
        common_permission=R._to_common_permission(common_permission) if common_permission else None,
        document_version=1, sync_status="PENDING", status="ACTIVE",
        key_identifier=key, created_at=now_utc().isoformat(), updated_at=now_utc().isoformat(),
        last_modified_by_id=creator_id, last_modified_by_name=creator_name,
    )
    # 1. Écriture du document XML Data Plane.
    dp = _dp()
    xml_path = dp.write_new_document(database_id, name, description or "", scope)
    record.xml_file_path = xml_path
    record.sync_status = "SYNCED"
    # 2. Catalogue Control Plane.
    cp.create_database(record)
    view = dp.get_database(database_id)

    HistoryService.log(user_id=creator_id, user_name=creator_name, action_type="a créé",
                       element_type="base", element_name=name, description=f"Base XML {name} créée",
                       database_id=database_id, ip_address=ip_address,
                       after=view.to_dict(include_key=True))
    AuditService.log(user_id=creator_id, user_name=creator_name, ip_address=ip_address,
                     action="CREATION_BASE", element_type="base", element_name=name,
                     meta={"database_id": database_id, "scope": scope})
    _emit_new_database(view.to_dict(include_key=True), creator_name)
    return view


def update_database(database_id, data, user_id, user_name, ip_address=None, expected_version=None):
    from ..services.permission_service import PermissionService
    from ..services.history_service import HistoryService

    view = _database_view(database_id)
    if not PermissionService.can_database(user_id, database_id, "write"):
        return None, "Permission d'écriture refusée"
    if view.status == "ARCHIVED":
        return None, "Base archivée, modification impossible"

    # Validation common_permission / scope (avant mutation).
    new_common_permission = None
    final_scope = str(data.get("scope", view.scope)).upper()
    if "common_permission" in data:
        new_common_permission = data["common_permission"]
        if new_common_permission is not None:
            new_common_permission = str(new_common_permission).upper()
            if new_common_permission not in {"VIEW", "EDIT", "MANAGE"}:
                return None, "common_permission doit être VIEW, EDIT ou MANAGE"
        if final_scope == "PERSONAL" and new_common_permission is not None:
            return None, "common_permission est réservé aux bases COMMON"

    before = view.to_dict(include_key=False)

    def mutation(document):
        if data.get("name"):
            document["name"] = data["name"]
        if "description" in data:
            document["description"] = data["description"] or ""
        if "comment" in data:
            document["comment"] = data["comment"] or ""
        if "scope" in data:
            if not PermissionService.can_database(user_id, database_id, "admin"):
                raise PermissionError("Permission admin requise pour changer le scope")
            scope = str(data["scope"]).upper()
            if scope not in {"PERSONAL", "COMMON"}:
                raise ValueError("scope invalide")
            document["scope"] = scope
        if "status" in data:
            status = str(data["status"]).upper()
            if status in {"ACTIVE", "ARCHIVED"}:
                document["status"] = status
        return None

    try:
        _dp().mutate(database_id, mutation, expected_version=expected_version)
    except Exception as exc:
        return None, str(exc)

    # Catalogue : appliquer les changements de métadonnées.
    cp = _cp_service()
    record = cp.get_database(database_id)
    if data.get("name"):
        record.name = data["name"]
    if "description" in data:
        record.description = data["description"] or ""
    if "comment" in data:
        record.comment = data["comment"] or ""
    if "scope" in data:
        record.scope = R._to_scope(str(data["scope"]).upper())
        record.common_permission = R._to_common_permission(new_common_permission) if new_common_permission else None
    if record.scope == R.Scope.PERSONAL:
        record.common_permission = None
    if "common_permission" in data and record.scope == R.Scope.COMMON:
        record.common_permission = R._to_common_permission(new_common_permission) if new_common_permission else None
    record.last_modified_by_id = user_id
    record.last_modified_by_name = user_name
    cp.update_database(record)
    view = _database_view(database_id)

    HistoryService.log(user_id=user_id, user_name=user_name, action_type="a modifié",
                       element_type="base", element_name=view.name, database_id=database_id,
                       ip_address=ip_address, before=before, after=view.to_dict())
    from ..socket_events import emit_modification
    emit_modification("base", view.to_dict(), user_name)
    return view, None


def delete_database(database_id, user_id, user_name, ip_address=None):
    from ..services.permission_service import PermissionService
    from ..services.history_service import HistoryService
    from ..services.audit_service import AuditService

    view = _database_view(database_id)
    if not PermissionService.can_database(user_id, database_id, "admin"):
        return False, "Permission d'administration de la base requise"
    if view.status == "ARCHIVED":
        return False, "Base archivée, restaurez-la avant suppression"

    before = view.to_dict(include_key=False)
    HistoryService.log(user_id=user_id, user_name=user_name, action_type="a supprimé",
                       element_type="base", element_name=view.name,
                       description=f"Base {view.name} supprimée", database_id=database_id,
                       ip_address=ip_address, before=before)
    AuditService.log(user_id=user_id, user_name=user_name, ip_address=ip_address,
                     action="SUPPRESSION_BASE", element_type="base", element_name=view.name,
                     meta={"database_id": database_id})

    cp = _cp_service()
    try:
        # Ordre important : supprimer le Data Plane (fichier XML) AVANT le
        # catalogue — delete_storage relit la base depuis le catalogue.
        _dp().delete_storage(database_id)
        cp.delete_database(database_id)  # RESTRICT sur les grants
    except Exception as exc:
        return False, str(exc)
    from ..socket_events import emit_suppression
    emit_suppression("base", view.name, database_id, user_name)
    return True, None


def archive_database(database_id, user_id, user_name, ip_address=None):
    from ..services.permission_service import PermissionService
    if not PermissionService.can_database(user_id, database_id, "admin"):
        return None, "Permission d'administration requise"
    return update_database(database_id, {"status": "ARCHIVED"}, user_id, user_name, ip_address)[0]


def restore_database(database_id, user_id, user_name, ip_address=None):
    from ..services.permission_service import PermissionService
    if not PermissionService.can_database(user_id, database_id, "admin"):
        return None, "Permission d'administration requise"
    return update_database(database_id, {"status": "ACTIVE"}, user_id, user_name, ip_address)[0]


# --------------------------------------------------------------------------
# TABLES
# --------------------------------------------------------------------------

def _table_doc_for(database_id, table_id_or_name):
    document = _dp().read_document(database_id)
    table = _dp().resolve_table(database_id, table_id_or_name)
    if table is None:
        raise NotFoundError("Table active introuvable")
    for t in document.get("tables", []):
        if t.get("internal_id") == table.id or t["name"] == table.name:
            return document, t
    raise NotFoundError("Table absente du document XML")


def create_table(name, description, database_id, creator_id, creator_name, is_protected=False,
                 comment="", file_identifier=None, ip_address=None, expected_version=None):
    from ..services.permission_service import PermissionService
    from ..services.history_service import HistoryService
    from ..services.audit_service import AuditService

    if not PermissionService.can_database(creator_id, database_id, "ddl"):
        return None, "Permission de création de table refusée"
    view = _database_view(database_id)
    if view.status == "ARCHIVED":
        return None, "Base archivée"
    table_id = _dp().allocate_object_id()
    table_uuid = str(uuid_lib.uuid4())

    def mutation(document):
        if any(t["name"] == name for t in document["tables"]):
            raise ValueError(f"Table '{name}' existe déjà")
        document["tables"].append({
            "internal_id": table_id, "uuid": table_uuid, "name": name,
            "description": description or "", "comment": comment or "",
            "protected": bool(is_protected), "file_identifier": file_identifier or None,
            "status": "ACTIVE", "columns": [], "constraints": [], "indexes": [], "rows": [],
            "creator_id": creator_id, "creator_name": creator_name,
            "created_at": now_utc().isoformat(), "updated_at": now_utc().isoformat(),
        })

    try:
        _dp().mutate(database_id, mutation, expected_version=expected_version)
    except Exception as exc:
        return None, str(exc)
    table = _dp().resolve_table(database_id, table_id)
    HistoryService.log(user_id=creator_id, user_name=creator_name, action_type="a créé",
                       element_type="table", element_name=name, database_id=database_id,
                       table_id=table_id, ip_address=ip_address,
                       after=table.to_dict(include_secret=False))
    AuditService.log(user_id=creator_id, user_name=creator_name, ip_address=ip_address,
                     action="CREATION_TABLE", element_type="table", element_name=name,
                     meta={"table_id": table_id, "database_id": database_id})
    from ..socket_events import emit_new_table
    emit_new_table(table.to_dict(), creator_name)
    return table, None


def update_table(table_id, data, user_id, user_name, provided_key=None, ip_address=None,
                 expected_version=None):
    from ..services.permission_service import PermissionService
    from ..services.unlock_service import UnlockService
    from ..services.history_service import HistoryService

    table = _dp().table_by_id(table_id)
    if table is None:
        return None, "Table introuvable"
    database_id = table.database_id
    if not PermissionService.can_table(user_id, table_id, "ddl"):
        return None, "Permission de modification de structure refusée"
    if table.status == "ARCHIVED":
        return None, "Table archivée"
    allowed, message = UnlockService.check_protection(user_id, table, provided_key)
    if not allowed:
        return None, message
    before = table.to_dict()
    old_name = table.name

    def mutation(document):
        item = next((t for t in document["tables"] if t.get("internal_id") == table_id), None)
        if not item:
            raise ValueError("Table absente du XML")
        new_name = data.get("name")
        if new_name and new_name != item["name"]:
            if any(t["name"] == new_name and t.get("internal_id") != table_id for t in document["tables"]):
                raise ValueError(f"Table '{new_name}' existe déjà")
            item["name"] = new_name
            for other in document["tables"]:
                for col in other.get("columns", []):
                    reference = col.get("references") or ""
                    if reference.startswith(old_name + "."):
                        col["references"] = new_name + reference[len(old_name):]
        if "description" in data:
            item["description"] = data["description"] or ""
        if "comment" in data:
            item["comment"] = data["comment"] or ""
        if "is_protected" in data:
            item["protected"] = bool(data["is_protected"])
        elif "protected" in data:
            item["protected"] = bool(data["protected"])
        if "file_identifier" in data:
            item["file_identifier"] = data["file_identifier"] or None
        if "archived" in data:
            item["status"] = "ARCHIVED" if data["archived"] else "ACTIVE"
        if "status" in data:
            status = str(data["status"]).upper()
            if status not in {"ACTIVE", "ARCHIVED"}:
                raise ValueError("Statut invalide")
            item["status"] = status

    try:
        _dp().mutate(database_id, mutation, expected_version=expected_version)
    except Exception as exc:
        return None, str(exc)
    table = _dp().resolve_table(database_id, table_id)
    HistoryService.log(user_id=user_id, user_name=user_name, action_type="a modifié",
                       element_type="table", element_name=table.name, database_id=database_id,
                       table_id=table_id, ip_address=ip_address, before=before, after=table.to_dict())
    from ..socket_events import emit_modification
    emit_modification("table", table.to_dict(), user_name)
    return table, None


def delete_table(table_id, user_id, user_name, provided_key=None, ip_address=None,
                 expected_version=None):
    from ..services.permission_service import PermissionService
    from ..services.unlock_service import UnlockService
    from ..services.audit_service import AuditService

    table = _dp().table_by_id(table_id)
    if table is None:
        return False, "Table introuvable"
    database_id = table.database_id
    if not PermissionService.can_table(user_id, table_id, "ddl"):
        return False, "Permission de suppression refusée"
    if table.status == "ARCHIVED":
        return False, "Table archivée"
    allowed, message = UnlockService.check_protection(user_id, table, provided_key)
    if not allowed:
        return False, message
    name = table.name

    def mutation(document):
        for other in document["tables"]:
            for col in other.get("columns", []):
                reference = col.get("references") or ""
                if reference.startswith(name + ".") and other.get("internal_id") != table_id:
                    raise ValueError(f"Table référencée par {other['name']}.{col['name']}")
        document["tables"] = [t for t in document["tables"] if t.get("internal_id") != table_id]

    try:
        _dp().mutate(database_id, mutation, expected_version=expected_version)
    except Exception as exc:
        return False, str(exc)
    AuditService.log(user_id=user_id, user_name=user_name, ip_address=ip_address,
                     action="SUPPRESSION_TABLE", element_type="table", element_name=name)
    from ..socket_events import emit_suppression
    emit_suppression("table", name, database_id, user_name)
    return True, None


# --------------------------------------------------------------------------
# COLONNES
# --------------------------------------------------------------------------

def _column_view(database_id, table_id, column_doc):
    from ..control_plane.views import ColumnView
    return ColumnView(
        id=column_doc.get("internal_id"), uuid=column_doc.get("uuid"), name=column_doc["name"],
        type=column_doc.get("type", "TEXT"), length=column_doc.get("length", "-"),
        nullable=bool(column_doc.get("nullable", True)),
        primary_key=bool(column_doc.get("primary_key")),
        foreign_key=bool(column_doc.get("foreign_key")),
        unique=bool(column_doc.get("unique")), auto_increment=bool(column_doc.get("auto_increment")),
        default_value=column_doc.get("default"), references=column_doc.get("references"),
        on_delete=column_doc.get("on_delete", "NO ACTION"), on_update=column_doc.get("on_update", "NO ACTION"),
        indexed=bool(column_doc.get("index")), comment=column_doc.get("comment", ""),
        status=column_doc.get("status", "ACTIVE"), table_id=table_id)


def _find_column(document, table_id, column_id_or_name):
    for t in document["tables"]:
        if t.get("internal_id") == table_id:
            for c in t["columns"]:
                if c.get("internal_id") == column_id_or_name or c["name"] == column_id_or_name:
                    return t, c
    return None, None


def create_column(data, creator_id, creator_name, provided_key=None, ip_address=None,
                  expected_version=None):
    from ..services.permission_service import PermissionService
    from ..services.unlock_service import UnlockService
    from ..services.history_service import HistoryService
    from ..services.audit_service import AuditService

    table = _dp().table_by_id(data.get("table_id"))
    if table is None:
        return None, "Table introuvable"
    database_id = table.database_id
    if not PermissionService.can_table(creator_id, table.id, "ddl"):
        return None, "Permission DDL refusée"
    if table.status == "ARCHIVED":
        return None, "Table archivée"
    allowed, message = UnlockService.check_protection(creator_id, table, provided_key)
    if not allowed:
        return None, message
    column_id = _dp().allocate_object_id()
    col_uuid = str(uuid_lib.uuid4())

    def mutation(document):
        tdoc = next(t for t in document["tables"] if t.get("internal_id") == table.id)
        if any(c["name"] == data["name"] for c in tdoc["columns"]):
            raise ValueError(f"Colonne '{data['name']}' existe déjà")
        tdoc["columns"].append({
            "internal_id": column_id, "uuid": col_uuid, "name": data["name"],
            "type": data.get("type", "TEXT").upper(), "length": data.get("length", "-"),
            "nullable": bool(data.get("nullable", True)),
            "primary_key": bool(data.get("primary_key", False)),
            "foreign_key": bool(data.get("foreign_key", False) or data.get("references")),
            "references": data.get("references"), "on_delete": data.get("on_delete", "NO ACTION"),
            "on_update": data.get("on_update", "NO ACTION"), "unique": bool(data.get("unique", False)),
            "auto_increment": bool(data.get("auto_increment", False)),
            "index": bool(data.get("index", False)), "default": data.get("default"),
            "comment": data.get("comment", ""), "status": "ACTIVE",
            "creator_id": creator_id, "creator_name": creator_name,
            "created_at": now_utc().isoformat(), "updated_at": now_utc().isoformat(),
        })

    try:
        _dp().mutate(database_id, mutation, expected_version=expected_version)
    except Exception as exc:
        return None, str(exc)
    document = _dp().read_document(database_id)
    _, column_doc = _find_column(document, table.id, column_id)
    column = _column_view(database_id, table.id, column_doc)
    HistoryService.log(user_id=creator_id, user_name=creator_name, action_type="a ajouté",
                       element_type="colonne", element_name=column.name, database_id=database_id,
                       table_id=table.id, ip_address=ip_address, after=column.to_dict())
    AuditService.log(user_id=creator_id, user_name=creator_name, ip_address=ip_address,
                     action="CREATION_COLONNE", element_type="colonne", element_name=column.name,
                     meta={"column_id": column_id, "table_id": table.id})
    from ..socket_events import emit_new_column
    emit_new_column(column.to_dict(), creator_name)
    return column, None


def update_column(column_id, data, user_id, user_name, provided_key=None, ip_address=None,
                  expected_version=None):
    from ..services.permission_service import PermissionService
    from ..services.unlock_service import UnlockService
    from ..services.history_service import HistoryService

    column = _dp_column(column_id)
    if column is None:
        return None, "Colonne introuvable"
    table = _dp().table_by_id(column.table_id)
    if not PermissionService.can_table(user_id, table.id, "ddl"):
        return None, "Permission DDL refusée"
    if table.status == "ARCHIVED" or column.status == "ARCHIVED":
        return None, "Table ou colonne archivée"
    allowed, message = UnlockService.check_protection(user_id, table, provided_key)
    if not allowed:
        return None, message
    before = column.to_dict()
    old_name = column.name

    def mutation(document):
        tdoc = next(t for t in document["tables"] if t.get("internal_id") == table.id)
        cdoc = next(c for c in tdoc["columns"] if c.get("internal_id") == column_id)
        new_name = data.get("name")
        if new_name and new_name != old_name:
            if any(c["name"] == new_name and c.get("internal_id") != column_id for c in tdoc["columns"]):
                raise ValueError("Nom de colonne déjà utilisé")
            cdoc["name"] = new_name
            for row in tdoc.get("rows", []):
                if old_name in row["data"]:
                    row["data"][new_name] = row["data"].pop(old_name)
            for other in document["tables"]:
                for c in other["columns"]:
                    if c.get("references") == f"{table.name}.{old_name}":
                        c["references"] = f"{table.name}.{new_name}"
        for field in ("type", "length", "nullable", "primary_key", "foreign_key", "references",
                      "on_delete", "on_update", "unique", "auto_increment", "index", "default", "comment"):
            if field in data:
                cdoc[field] = data[field]
        if "status" in data:
            cdoc["status"] = str(data["status"]).upper()
        if "archived" in data:
            cdoc["status"] = "ARCHIVED" if data["archived"] else "ACTIVE"

    try:
        _dp().mutate(table.database_id, mutation, expected_version=expected_version)
    except Exception as exc:
        return None, str(exc)
    column = _dp_column(column_id)
    HistoryService.log(user_id=user_id, user_name=user_name, action_type="a modifié",
                       element_type="colonne", element_name=column.name, database_id=table.database_id,
                       table_id=table.id, ip_address=ip_address, before=before, after=column.to_dict())
    from ..socket_events import emit_modification
    emit_modification("colonne", column.to_dict(), user_name)
    return column, None


def delete_column(column_id, user_id, user_name, provided_key=None, ip_address=None,
                  expected_version=None):
    from ..services.permission_service import PermissionService
    from ..services.unlock_service import UnlockService
    from ..services.audit_service import AuditService

    column = _dp_column(column_id)
    if column is None:
        return False, "Colonne introuvable"
    table = _dp().table_by_id(column.table_id)
    if not PermissionService.can_table(user_id, table.id, "ddl"):
        return False, "Permission DDL refusée"
    allowed, message = UnlockService.check_protection(user_id, table, provided_key)
    if not allowed:
        return False, message
    name = column.name

    def mutation(document):
        for other in document["tables"]:
            for c in other["columns"]:
                if c.get("references") == f"{table.name}.{name}":
                    raise ValueError(f"Colonne référencée par {other['name']}.{c['name']}")
        tdoc = next(t for t in document["tables"] if t.get("internal_id") == table.id)
        tdoc["columns"] = [c for c in tdoc["columns"] if c.get("internal_id") != column_id]
        for row in tdoc.get("rows", []):
            row.get("data", {}).pop(name, None)
        for index in list(tdoc.get("indexes", [])):
            if name in index.get("columns", []):
                tdoc["indexes"].remove(index)

    try:
        _dp().mutate(table.database_id, mutation, expected_version=expected_version)
    except Exception as exc:
        return False, str(exc)
    AuditService.log(user_id=user_id, user_name=user_name, ip_address=ip_address,
                     action="SUPPRESSION_COLONNE", element_type="colonne", element_name=name)
    from ..socket_events import emit_suppression
    emit_suppression("colonne", name, table.database_id, user_name)
    return True, None


def _dp_column(column_id):
    """Résout une colonne par id global (scan des documents)."""
    try:
        column_id = int(column_id)
    except (TypeError, ValueError):
        return None
    for database in _dp().list_databases():
        document = _dp().read_document(database.id)
        for t in document.get("tables", []):
            for c in t.get("columns", []):
                if c.get("internal_id") == column_id:
                    return _column_view(database.id, t.get("internal_id"), c)
    return None


def list_columns(table_id):
    table = _dp().table_by_id(table_id)
    if table is None:
        return []
    document = _dp().read_document(table.database_id)
    _, tdoc = _find_column(document, table_id, table.name)
    if tdoc is None:
        return []
    return [_column_view(table.database_id, table_id, c) for c in tdoc.get("columns", [])]
