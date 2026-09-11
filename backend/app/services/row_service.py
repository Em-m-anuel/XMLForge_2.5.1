"""CRUD des lignes — Data Plane XML (Phase 6J-B)."""

from __future__ import annotations

from ..data_plane import get_data_plane, get_table
from ..errors import PermissionDenied
from ..xml_engine.xml_native import XmlNativeEngine, coerce_literal, coerce_value
from .history_service import HistoryService
from .audit_service import AuditService
from .permission_service import PermissionService
from .unlock_service import UnlockService


class _XmlRow:
    def __init__(self, **kw):
        self.id = kw.get("id")
        self.uuid = kw.get("uuid")
        self.table_id = kw.get("table_id")
        self.data = kw.get("data", {})

    def to_dict(self):
        return {"id": self.id, "uuid": self.uuid, "table_id": self.table_id,
                "data": self.data, "created_at": None, "updated_at": None}


class RowService:
    @staticmethod
    def _xml_rows(table, limit, offset, filters, search, order_by):
        document = get_data_plane().read_document(table.database_id)
        engine = XmlNativeEngine(document=document)
        tdoc = engine.table(table.name)
        columns = engine._active_columns(tdoc)
        col_names = {c["name"]: c for c in columns}
        rows = tdoc.get("rows", [])

        def matches(row):
            data = row.get("data", {})
            for col, val in (filters or {}).items():
                ctype = col_names[col]["type"] if col in col_names else "TEXT"
                if coerce_value(data.get(col), ctype) != coerce_literal(val, ctype):
                    return False
            if search:
                needle = str(search).lower()
                if not any(needle in str(data.get(c, "")).lower() for c in col_names):
                    return False
            return True

        filtered = [r for r in rows if matches(r)]
        total = len(filtered)
        if order_by:
            for item in reversed(order_by or []):
                col = item["column"] if isinstance(item, dict) else str(item)
                direction = (item.get("direction", "ASC") if isinstance(item, dict) else "ASC").upper()
                ctype = col_names[col]["type"] if col in col_names else "TEXT"
                reverse = direction == "DESC"
                filtered.sort(
                    key=lambda r, _c=col, _t=ctype: (
                        coerce_value(r.get("data", {}).get(_c), _t) is not None,
                        coerce_value(r.get("data", {}).get(_c), _t),
                    ),
                    reverse=reverse,
                )
        page = filtered[max(0, offset):max(0, offset) + max(1, limit)]
        public_rows = [
            {"id": r.get("internal_id"), "uuid": r.get("uuid"), "table_id": table.id,
             "data": {c["name"]: coerce_value(r.get("data", {}).get(c["name"]), c["type"])
                      for c in columns if c["name"] in r.get("data", {})},
             "created_at": None, "updated_at": None}
            for r in page
        ]
        return {"rows": public_rows, "total": total, "limit": limit, "offset": offset,
                "table": table.to_dict()}

    @staticmethod
    def get_by_table(table_id, limit=100, offset=0, user_id=None, filters=None,
                     search=None, order_by=None):
        table = get_table(table_id)
        if not table:
            return None, "Table introuvable"
        try:
            return RowService._xml_rows(table, limit, offset, filters, search, order_by), None
        except Exception as exc:
            return None, str(exc)

    @staticmethod
    def create(table_id, data_dict, creator_id=None, creator_name=None, ip_address=None,
               provided_key=None, expected_version=None):
        table = get_table(table_id)
        if not table:
            return None, "Table introuvable"
        if creator_id is not None and not PermissionService.can_table(creator_id, table_id, "write"):
            return None, "Permission d'écriture refusée"
        allowed, message = UnlockService.check_protection(creator_id, table, provided_key)
        if not allowed:
            return None, message
        holder = {}

        def mutation(document):
            engine = XmlNativeEngine(document=document)
            result = engine.insert(table.name, data_dict)
            tdoc = engine.table(table.name)
            row = tdoc["rows"][-1]
            row["internal_id"] = get_data_plane().allocate_object_id()
            result["internal_id"] = row["internal_id"]
            holder["result"] = result

        try:
            get_data_plane().mutate(table.database_id, mutation, expected_version=expected_version)
        except Exception as exc:
            return None, str(exc)
        result = holder["result"]
        HistoryService.log(user_id=creator_id, user_name=creator_name, action_type="a créé",
                           element_type="ligne", element_name=f"{table.name}#{result['uuid']}",
                           database_id=table.database_id, table_id=table.id, ip_address=ip_address,
                           after=result)
        AuditService.log(user_id=creator_id, user_name=creator_name, ip_address=ip_address,
                         action="CREATION_LIGNE", element_type="ligne",
                         element_name=f"{table.name}#{result['uuid']}",
                         meta={"table_id": table.id, "row_uuid": result["uuid"]})
        return _XmlRow(id=result.get("internal_id"), uuid=result["uuid"],
                       table_id=table.id, data=result["data"]), None

    @staticmethod
    def update(table_id, row_id, data_dict, updater_id=None, updater_name=None, ip_address=None,
               provided_key=None, expected_version=None):
        table = get_table(table_id)
        if not table:
            return None, "Ligne introuvable"
        if updater_id is not None and not PermissionService.can_table(updater_id, table_id, "write"):
            return None, "Permission d'écriture refusée"
        allowed, message = UnlockService.check_protection(updater_id, table, provided_key)
        if not allowed:
            return None, message
        document = get_data_plane().read_document(table.database_id)
        engine = XmlNativeEngine(document=document)
        tdoc = engine.table(table.name)
        target = next((r for r in tdoc.get("rows", []) if r.get("internal_id") == row_id), None)
        if target is None:
            return None, "Ligne introuvable"
        before = {"id": row_id, "uuid": target.get("uuid"), "table_id": table.id,
                  "data": target.get("data", {})}

        def mutation(doc):
            e = XmlNativeEngine(document=doc)
            e.update(table.name, data_dict, row_uuid=target["uuid"], replace=True)

        try:
            get_data_plane().mutate(table.database_id, mutation, expected_version=expected_version)
        except Exception as exc:
            return None, str(exc)
        document = get_data_plane().read_document(table.database_id)
        engine = XmlNativeEngine(document=document)
        tdoc = engine.table(table.name)
        updated = next((r for r in tdoc.get("rows", []) if r.get("internal_id") == row_id), None)
        after = {"id": row_id, "uuid": updated["uuid"], "table_id": table.id,
                 "data": updated.get("data", {})}
        HistoryService.log(user_id=updater_id, user_name=updater_name, action_type="a modifié",
                           element_type="ligne", element_name=f"{table.name}#{row_id}",
                           database_id=table.database_id, table_id=table.id, ip_address=ip_address,
                           before=before, after=after)
        AuditService.log(user_id=updater_id, user_name=updater_name, ip_address=ip_address,
                         action="MODIFICATION_LIGNE", element_type="ligne",
                         element_name=f"{table.name}#{row_id}", meta={"row_uuid": updated["uuid"]})
        return _XmlRow(**after), None

    @staticmethod
    def delete(table_id, row_id, deleter_id=None, deleter_name=None, ip_address=None,
               provided_key=None, expected_version=None):
        table = get_table(table_id)
        if not table:
            return False, "Ligne introuvable"
        if deleter_id is not None and not PermissionService.can_table(deleter_id, table_id, "write"):
            return False, "Permission d'écriture refusée"
        allowed, message = UnlockService.check_protection(deleter_id, table, provided_key)
        if not allowed:
            return False, message
        document = get_data_plane().read_document(table.database_id)
        engine = XmlNativeEngine(document=document)
        tdoc = engine.table(table.name)
        target = next((r for r in tdoc.get("rows", []) if r.get("internal_id") == row_id), None)
        if target is None:
            return False, "Ligne introuvable"
        before = {"id": row_id, "uuid": target.get("uuid"), "table_id": table.id,
                  "data": target.get("data", {})}

        def mutation(doc):
            e = XmlNativeEngine(document=doc)
            e.delete(table.name, row_uuid=target["uuid"])

        try:
            get_data_plane().mutate(table.database_id, mutation, expected_version=expected_version)
        except Exception as exc:
            return False, str(exc)
        HistoryService.log(user_id=deleter_id, user_name=deleter_name, action_type="a supprimé",
                           element_type="ligne", element_name=f"{table.name}#{row_id}",
                           database_id=table.database_id, table_id=table.id, ip_address=ip_address,
                           before=before)
        AuditService.log(user_id=deleter_id, user_name=deleter_name, ip_address=ip_address,
                         action="SUPPRESSION_LIGNE", element_type="ligne",
                         element_name=f"{table.name}#{row_id}", meta={"row_uuid": target["uuid"]})
        return True, None

    @staticmethod
    def bulk_import(table_id, rows_data, creator_id=None, creator_name=None, ip_address=None,
                    provided_key=None):
        created = []
        for data in rows_data:
            row, error = RowService.create(table_id, data, creator_id, creator_name,
                                           ip_address, provided_key)
            if error:
                return None, error
            created.append(row)
        return created, None
